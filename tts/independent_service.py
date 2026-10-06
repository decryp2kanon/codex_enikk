#!/usr/bin/env python3
"""Independent voice receiver. Never connects to Codex or writes session history."""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import struct
import subprocess
import tempfile
import time
import uuid

PROTOCOL = 1
MAX_MESSAGE = 60 * 1024
MAX_JOBS = 128
MAX_QUEUE_BYTES = 4 * 1024 * 1024
MAX_ITEM_BYTES = 1024 * 1024
ROOT = Path(__file__).resolve().parent

def atomic(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.status-')
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(value, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)

def default_state():
    return Path(os.environ.get('ENIKK_TTS_STATE',
        str(Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'enikk_tts')))

def default_socket():
    return Path(os.environ.get('ENIKK_TTS_SOCKET',
        str(Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid()))) / 'enikk-tts.sock')))

class Gate:
    """Only new item starts after model-ready. Missing events discard the item."""
    def __init__(self, ready_ns, thread):
        self.ready_ns, self.thread = ready_ns, thread
        self.allowed = set()
        self.seen = set()
        self.sizes = {}

    def filter(self, envelope):
        if envelope['sent_ns'] < self.ready_ns:
            return None
        event = envelope.get('event')
        if not isinstance(event, dict):
            return None
        p = event.get('params', {})
        if not isinstance(p, dict) or p.get('threadId') != self.thread:
            return None
        method = event.get('method')
        turn = p.get('turnId', p.get('turn', {}).get('id'))
        item = p.get('item', {})
        key = (turn, p.get('itemId', item.get('id')))
        if method == 'item/started' and item.get('type') == 'agentMessage':
            if key in self.seen:
                return None
            if len(self.seen) >= 4096:
                raise ValueError('item boundary capacity; rotate generation')
            self.seen.add(key)
            self.allowed.add(key)
            self.sizes[key] = 0
            return event
        if method in ('item/started', 'item/completed') and item.get('type') == 'userMessage':
            return event
        if method == 'item/agentMessage/delta':
            if key not in self.allowed:
                return None
            self.sizes[key] += len(p.get('delta', '').encode())
            if self.sizes[key] > MAX_ITEM_BYTES:
                self.allowed.discard(key)
                raise ValueError('assistant item too large')
            return event
        if method == 'item/completed':
            return event if key in self.allowed else None
        if method == 'turn/started':
            return event
        if method == 'turn/completed':
            value = dict(event)
            value['params'] = dict(p)
            value['params']['turn'] = dict(p['turn'])
            value['params']['turn']['items'] = [
                x for x in p['turn'].get('items', []) if (turn, x.get('id')) in self.allowed]
            self.allowed = {k for k in self.allowed if k[0] != turn}
            self.sizes = {k:v for k,v in self.sizes.items() if k[0] != turn}
            return value
        return None

def load_stream():
    spec = importlib.util.spec_from_file_location('voice_stream', ROOT / 'yuki-codex-stream.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class Generation:
    def __init__(self, base, producer, thread, service_generation):
        self.id = uuid.uuid4().hex
        self.state = base / 'runs' / ('run-' + self.id)
        self.state.mkdir(mode=0o700, parents=True)
        self.producer, self.thread = producer, thread
        self.service_generation = service_generation
        born = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]
        os.environ.update(CODEX_ENIKK_TTS_STATE=str(self.state),
            CODEX_ENIKK_TTS_RUN_ID=self.id, CODEX_ENIKK_TTS_OWNER=f'{os.getpid()}:{born}',
            CODEX_ENIKK_TTS_MODEL_LOCK=str(base / 'engine.lock'),
            CODEX_ENIKK_STARTUP_NS=str(time.monotonic_ns()))
        self.stream = load_stream()
        self.gate = None
        self.error = None
        self.dropped = 0
        self.started = time.monotonic()
        atomic(self.state / 'run.json', {'run_id': self.id, 'producer': producer,
            'thread': thread, 'service_generation': service_generation, 'pid': os.getpid()})
        publisher = self.stream.Publisher(start_engine=False)
        def bounded(job):
            pending = []
            for p in publisher.jobs.iterdir():
                if p.name.startswith('.'): continue
                try: pending.append(p.stat().st_size)
                except FileNotFoundError: pass
            if len(pending) >= MAX_JOBS or sum(pending) + len(json.dumps(job).encode()) > MAX_QUEUE_BYTES:
                self.dropped += 1
                self.stream.notify.log_status('SKIPPED reason=voice_queue_full')
                return
            publisher(job)
        self.accumulator = self.stream.Accumulator(self.state / 'items', thread, bounded,
                                                   self.stream.notify.log_status)
        python = Path(os.environ.get('CODEX_ENIKK_CHATTERBOX_HOME',
                         str(Path.home() / 'Apps/chatterbox-yuki'))) / '.venv/bin/python'
        if not python.is_file() or not shutil.which('paplay'):
            raise RuntimeError('voice dependencies unavailable')
        self.playback_available = subprocess.run(['pactl', 'info'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2).returncode == 0
        if not self.playback_available:
            raise RuntimeError('audio server unavailable')
        self.log = (self.state / 'notify.log').open('ab')
        self.engine = subprocess.Popen([str(python), str(ROOT / 'yuki-chatterbox-engine.py')],
            stdin=subprocess.DEVNULL, stdout=self.log, stderr=self.log, start_new_session=True,
            env=os.environ | {'PYTHONDONTWRITEBYTECODE': '1'})

    def accept(self, message):
        if self.engine.poll() is not None:
            raise RuntimeError('voice engine exited')
        if not self.stream.notify.engine_ready():
            if time.monotonic() - self.started > 120:
                raise RuntimeError('model readiness timeout')
            return
        if self.gate is None:
            self.gate = Gate(time.monotonic_ns(), self.thread)
        event = self.gate.filter(message)
        if event:
            self.accumulator.event(event)

    def close(self):
        (self.state / 'cancelled').touch()
        engine = getattr(self, 'engine', None)
        if engine and engine.poll() is None:
            # This is an owned Popen child and group, never a discovered PID.
            try: os.killpg(engine.pid, signal.SIGTERM)
            except ProcessLookupError: pass
            try: engine.wait(timeout=4)
            except subprocess.TimeoutExpired:
                try: os.killpg(engine.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                engine.wait()
        log = getattr(self, 'log', None)
        if log: log.close()

def valid_message(raw):
    data = json.loads(raw)
    if not isinstance(data, dict) or data.get('protocol') != PROTOCOL:
        raise ValueError('unsupported IPC protocol')
    for key in ('producer', 'thread'):
        if not isinstance(data.get(key), str) or not 0 < len(data[key]) <= 128:
            raise ValueError('invalid connection identity')
    for key in ('sequence', 'sent_ns'):
        if type(data.get(key)) is not int or data[key] < 0:
            raise ValueError('invalid event order')
    if data.get('event') is not None and not isinstance(data['event'], dict):
        raise ValueError('invalid event')
    return data

def serve():
    base, path = default_state(), default_socket()
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock = (base / 'service.lock').open('a+b')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    service_generation = uuid.uuid4().hex
    stopped = False
    def stop(*_):
        nonlocal stopped
        stopped = True
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_PASSCRED, 1)
    # A separate socket lock also excludes alternate state directories.
    socket_lock = path.with_suffix('.lock').open('a+b')
    fcntl.flock(socket_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    if path.is_symlink():
        raise ValueError('unsafe socket path')
    if path.exists():
        import stat
        if not stat.S_ISSOCK(path.stat().st_mode) or path.stat().st_uid != os.getuid():
            raise ValueError('unsafe stale socket')
        path.unlink()
    sock.bind(str(path)); os.chmod(path, 0o600); sock.settimeout(.25)
    generation = None
    sequence = None
    producer = None
    last = 0
    retry_at = 0
    failures = 0
    error = None
    last_status = 0
    retired = set()
    version = (ROOT / 'VERSION').read_text().strip() if (ROOT / 'VERSION').exists() else 'development'
    def cancel():
        nonlocal generation
        if generation:
            generation.close()
            generation = None
    def report(state=None):
        atomic(base / 'status.json', {
            'pid': os.getpid(), 'born': Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19],
            'service_generation': service_generation,
            'code_version': version, 'protocol': PROTOCOL, 'producer': producer,
            'thread': generation.thread if generation else None,
            'generation': generation.id if generation else None,
            'run': str(generation.state) if generation else None,
            'state': state or ('ready' if generation and generation.gate else
                              'model_loading' if generation else 'waiting_for_core'),
            'model_ready': bool(generation and generation.gate),
            'playback_available': bool(generation and generation.playback_available),
            'last_error': error, 'updated_at': time.time()})
    try:
        report()
        while not stopped:
            try:
                raw, ancillary, flags, _ = sock.recvmsg(MAX_MESSAGE, socket.CMSG_SPACE(12))
                credentials = [struct.unpack('3i', d[:12]) for level, kind, d in ancillary
                               if level == socket.SOL_SOCKET and kind == socket.SCM_CREDENTIALS]
                if flags & socket.MSG_TRUNC or not credentials or credentials[0][1] != os.getuid():
                    raise ValueError('invalid local event credentials or size')
                message = valid_message(raw)
                now = time.monotonic()
                if not -1_000_000_000 <= time.monotonic_ns() - message['sent_ns'] <= 2_000_000_000:
                    continue  # Never play queued history after warmup/reconnect.
                if message['producer'] in retired:
                    continue
                if producer and producer != message['producer']:
                    if now - last < 3:
                        continue  # A second core cannot take over an active connection.
                    retired.add(producer)
                    if len(retired) > 128:
                        raise RuntimeError('too many producer changes; restart voice service')
                if producer == message['producer'] and sequence is not None and message['sequence'] <= sequence:
                    continue
                changed = producer != message['producer']
                gap = sequence is not None and message['sequence'] != sequence + 1
                if changed or gap:
                    cancel()
                    if gap and not changed:
                        failures += 1
                        retry_at = now + min(30, 2 ** min(failures, 5))
                        error = 'event sequence gap; voice generation discarded'
                producer, sequence, last = message['producer'], message['sequence'], now
                if generation and generation.thread != message['thread']:
                    cancel()
                if generation is None and now >= retry_at and failures < 6:
                    candidate = Generation.__new__(Generation)
                    try:
                        candidate.__init__(base, producer, message['thread'], service_generation)
                        generation = candidate
                    except Exception:
                        if hasattr(candidate, 'state'): candidate.close()
                        raise
                if generation:
                    generation.accept(message)
                    if generation.gate: failures = 0
            except socket.timeout:
                if generation and time.monotonic() - last > 3:
                    cancel()
                    error = 'core connection lost; voice cancelled'
                    sequence = None
            except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
                cancel()
                error = str(exc)
                failures += 1
                retry_at = time.monotonic() + min(30, 2 ** min(failures, 5))
            if time.monotonic() - last_status >= .5:
                report('error' if failures >= 6 else None)
                last_status = time.monotonic()
    finally:
        cancel()
        report('stopped')
        sock.close()
        path.unlink(missing_ok=True)
        lock.close()
        socket_lock.close()

if __name__ == '__main__':
    serve()
