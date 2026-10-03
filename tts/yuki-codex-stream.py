#!/usr/bin/env python3
"""Observe one app-server thread; durably submit complete assistant sentences."""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import signal
import subprocess
import threading
import tempfile
import time

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('yuki_notify', ROOT / 'yuki-codex-notify.py')
notify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notify)


def atomic_json(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix='.stream-')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(value, out, ensure_ascii=False)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
        fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        Path(name).unlink(missing_ok=True)


def boundaries(text, final=False):
    """Markdown-aware boundaries, including unambiguous Korean delta endings."""
    fence = None
    inline = False
    brackets = []
    start = 0
    i = 0
    while i < len(text):
        if (i == 0 or text[i-1] == '\n') and text[i:i+3] in ('```', '~~~'):
            marker = text[i:i+3]
            fence = None if fence == marker else (marker if fence is None else fence)
            end = text.find('\n', i)
            if end < 0:
                break
            i = end + 1
            continue
        c = text[i]
        if not fence:
            if c == '`':
                inline = not inline
            elif not inline:
                if c in '[(':
                    brackets.append(c)
                elif c in '])' and brackets:
                    brackets.pop()
                elif not brackets and c in '.?!。？！':
                    end = i + 1
                    while end < len(text) and text[end] in '.?!。？！\"\'”’':
                        end += 1
                    token = text[start:end].split()[-1] if text[start:end].split() else ''
                    # No future delta is needed for Korean prose punctuation.
                    # An ASCII period may still be a partial decimal/domain/path:
                    # retain lookahead for those ambiguous tokens.
                    immediate = (end == len(text) and i > 0 and
                                 bool(re.fullmatch(r'[가-힣]', text[i-1])) and
                                 '/' not in token and ':' not in token and
                                 '.' not in token.rstrip('.?!。？！\"\'”’'))
                    if (end < len(text) and text[end].isspace()) or immediate:
                        token = text[start:end].split()[-1] if text[start:end].split() else ''
                        # A numbered list marker or familiar abbreviation is not a sentence.
                        if not re.fullmatch(r'\d+[.]', token) and token.lower() not in {'e.g.', 'i.e.', 'mr.', 'mrs.', 'dr.', 'vs.', 'etc.'}:
                            yield end
                            start = end
                        i = end - 1
        i += 1
    if final and start < len(text):
        # An unfinished fenced code block must never become spoken code.
        if fence:
            tail = text[start:]
            cut = re.search(r'(?m)^\s*(?:```|~~~)', tail)
            if cut and tail[:cut.start()].strip():
                yield start + cut.start()
        else:
            yield len(text)


class Accumulator:
    def __init__(self, directory, thread_id, submit, log=lambda message: None):
        self.directory = Path(directory)
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.thread_id = thread_id
        self.submit = submit
        self.log = log
        self.items = {}
        baseline = self.directory / '.baseline'
        self.baseline = set(json.loads(baseline.read_text()).get('ignored_turns', [])) if baseline.exists() else set()
        self.reconcile_turns = set()

    def path(self, turn, item):
        key = hashlib.sha256(f'{self.thread_id}\0{turn}\0{item}'.encode()).hexdigest()
        return self.directory / (key + '.json')

    def state(self, turn, item):
        key = (turn, item)
        if key not in self.items:
            path = self.path(*key)
            self.items[key] = json.loads(path.read_text()) if path.exists() else dict(
                turn=turn, item=item, text='', consumed=0, completed=False,
                epoch=notify.current_epoch().get('epoch'),
                interrupted=False, phase=None, outbox=[])
        return self.items[key]

    def save(self, state):
        atomic_json(self.path(state['turn'], state['item']), state)

    def recover(self):
        jobs = [job for path in self.directory.glob('*.json')
                for job in json.loads(path.read_text()).get('outbox', [])]
        for job in sorted(jobs, key=lambda job: job['filename']):
            self.submit(job)

    def emit(self, state, final=False):
        if state['interrupted'] or state.get('needs_snapshot') or state['phase'] not in ('commentary', 'final_answer'):
            return
        old = state['consumed']
        for offset in boundaries(state['text'][old:], final):
            complete_ns = time.monotonic_ns()
            end = old + offset
            raw = state['text'][state['consumed']:end]
            text = notify.clean_text(raw)
            begin = state['consumed']
            if text and any(ch.isalnum() for ch in text):
                key = hashlib.sha256(f"{self.thread_id}\0{state['turn']}\0{state['item']}\0{begin}\0{end}".encode()).hexdigest()
                job = dict(id=key[:12], stream_key=key, text=text,
                           epoch=state.get('epoch'),
                           run_id=os.environ.get('CODEX_ENIKK_TTS_RUN_ID'),
                           queued_ns=time.monotonic_ns(),
                           sentence_complete_ns=complete_ns,
                           filename=f'{time.time_ns():020d}-{key}',
                           source=dict(thread=self.thread_id, turn=state['turn'], item=state['item'], start=begin, end=end))
                state['outbox'].append(job)
            else:
                job = None
            state['consumed'] = end
            # Write-ahead outbox: a crash between this checkpoint and queue publication is recoverable.
            self.save(state)
            if job:
                self.log(f"SENTENCE_FLUSH job={job['id']} complete_ns={complete_ns} flush_ns={time.monotonic_ns()}")
                self.submit(job)
                self.log(f"submitted job={job['id']} item={state['item']} start={begin} end={end}")

    def snapshot_item(self, turn, item, status, baseline=False):
        if item.get('type') != 'agentMessage':
            return
        state = self.state(turn, item['id'])
        text = item.get('text', '')
        if baseline and not self.path(turn, item['id']).exists():
            state.update(text=text, consumed=len(text), phase=item.get('phase'), completed=status=='completed', interrupted=status=='interrupted')
            self.save(state)
            return
        prefix = state['text'][:state['consumed']]
        if not text.startswith(prefix):
            state['conflict'] = text
            self.save(state)
            raise ValueError('snapshot changed previously submitted text; preserved for review')
        state.update(text=text, phase=item.get('phase', state['phase']), needs_snapshot=False)
        if status == 'interrupted':
            state['interrupted'] = True
        self.emit(state, final=status=='completed')
        state['completed'] = status == 'completed'
        self.save(state)

    def snapshot(self, thread, initial=False, reconnecting=False):
        if initial:
            self.baseline.update(turn['id'] for turn in thread.get('turns', []))
            # The durable .baseline turn IDs already exclude this history from
            # both events and reconnects. Do not fsync a redundant file per item.
            return
        # Active items may be absent from thread/resume until item completion.
        # Deltas have no offsets: appending across a disconnected interval would
        # silently splice unrelated words. Reconcile that turn from full items.
        if reconnecting:
            self.reconcile_turns.update(turn['id'] for turn in thread.get('turns', [])
                                        if turn.get('status') == 'inProgress')
            for path in self.directory.glob('*.json'):
                saved = json.loads(path.read_text())
                if not saved.get('completed') and not saved.get('interrupted'):
                    self.reconcile_turns.add(saved['turn'])
                    state = self.state(saved['turn'], saved['item'])
                    state['needs_snapshot'] = True
                    self.save(state)
        # Reconcile the latest submitted user before replaying any old outbox.
        if not initial:
            users = [(turn['id'], item['id']) for turn in thread.get('turns', [])
                     if turn['id'] not in self.baseline for item in turn.get('items', [])
                     if item.get('type') == 'userMessage']
            if users:
                turn, user = users[-1]
                notify.advance_epoch(self.thread_id, turn, user,
                                     notify.user_ordinal(self.thread_id, turn, user))
        for turn in thread.get('turns', []):
            if not initial and turn['id'] in self.baseline:
                continue
            snapshot_epoch = None
            for item in turn.get('items', []):
                if item.get('type') == 'userMessage':
                    snapshot_epoch = item['id']
                if item.get('type') == 'agentMessage' and not self.path(turn['id'], item['id']).exists():
                    self.state(turn['id'], item['id'])['epoch'] = snapshot_epoch
                self.snapshot_item(turn['id'], item, turn.get('status'), baseline=initial)
        # Completed states remain on disk, not in an ever-growing memory cache.
        self.items = {k:v for k,v in self.items.items() if not v['completed'] and not v['interrupted']}

    def event(self, event):
        method = event.get('method')
        p = event.get('params', {})
        if p.get('threadId') != self.thread_id:
            return
        if p.get('turnId', p.get('turn', {}).get('id')) in self.baseline:
            return
        if method == 'turn/started':
            self.log(f"RESPONSE_START turn={p['turn']['id']} monotonic_ns={time.monotonic_ns()}")
            for item in p['turn'].get('items', []):
                if item.get('type') == 'userMessage':
                    notify.advance_epoch(self.thread_id, p['turn']['id'], item['id'],
                                         notify.user_ordinal(self.thread_id, p['turn']['id'], item['id']))
        if method in ('item/started', 'item/completed'):
            item = p['item']
            if item.get('type') == 'userMessage':
                self.log(f"USER_SUBMIT_EVENT item={item['id']} turn={p['turnId']} monotonic_ns={time.monotonic_ns()}")
                notify.advance_epoch(self.thread_id, p['turnId'], item['id'],
                                     notify.user_ordinal(self.thread_id, p['turnId'], item['id']))
                return
            if item.get('type') != 'agentMessage':
                return
            state = self.state(p['turnId'], item['id'])
            if method == 'item/started':
                state['phase'] = item.get('phase')
                return
            self.log(f"ITEM_COMPLETED item={item['id']} monotonic_ns={time.monotonic_ns()}")
            self.snapshot_item(p['turnId'], item, 'item_completed')
        elif method == 'item/agentMessage/delta':
            state = self.state(p['turnId'], p['itemId'])
            if state['completed'] or state['interrupted']:
                return
            if p['turnId'] in self.reconcile_turns or state.get('needs_snapshot'):
                if not state.get('needs_snapshot'):
                    state['needs_snapshot'] = True
                    self.save(state)
                return
            if not state['text']:
                self.log(f"FIRST_DELTA_RECEIVED item={p['itemId']} monotonic_ns={time.monotonic_ns()}")
            state['text'] += p['delta']
            self.emit(state)
        elif method == 'turn/completed':
            turn = p['turn']
            self.log(f"FINAL_COMPLETED turn={turn['id']} monotonic_ns={time.monotonic_ns()}")
            for key, state in list(self.items.items()):
                if key[0] == turn['id'] and turn['status'] != 'completed':
                    state['interrupted'] = True
                    self.save(state)
            for item in turn.get('items', []):
                self.snapshot_item(turn['id'], item, turn['status'])
            if turn['status'] == 'completed':
                if any(state.get('needs_snapshot') for key, state in self.items.items() if key[0] == turn['id']):
                    raise ConnectionError('completed item needs authoritative reconnect snapshot')
                for key, state in list(self.items.items()):
                    if key[0] == turn['id']:
                        self.emit(state, final=True)
                        state['completed'] = True
                        self.save(state)
            self.items = {k:v for k,v in self.items.items() if k[0] != turn['id']}
            self.reconcile_turns.discard(turn['id'])


class Publisher:
    def __init__(self, state=notify.STATE, start_engine=True):
        self.state = Path(state)
        self.jobs = self.state / 'jobs'
        self.jobs.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.start_engine = start_engine

    def __call__(self, job):
        if not notify.run_active():
            return
        current_run = os.environ.get('CODEX_ENIKK_TTS_RUN_ID')
        if current_run and job.get('run_id') != current_run:
            notify.log_status(f"stale job blocked job={job['id']} run_id={job.get('run_id')}")
            return
        if not notify.epoch_valid(job, self.state):
            notify.log_status(f"stale epoch publication blocked job={job['id']}")
            return
        path = self.jobs / job['filename']
        # The engine archives stream delivery receipts before removing queue entries.
        if path.exists() or path.with_name('.played-' + path.name).exists() or path.with_name('.failed-' + path.name).exists():
            return
        fd, name = tempfile.mkstemp(dir=self.jobs, prefix='.stream-')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as out:
                json.dump(job, out, ensure_ascii=False)
                out.flush(); os.fsync(out.fileno())
            with notify.epoch_lock(self.state):
                if not notify.epoch_valid(job, self.state):
                    return
                try:
                    os.link(name, path)  # Never overwrite an in-flight delivery checkpoint.
                except FileExistsError:
                    return
            fd = os.open(self.jobs, os.O_RDONLY | os.O_DIRECTORY)
            try: os.fsync(fd)
            finally: os.close(fd)
        finally:
            Path(name).unlink(missing_ok=True)
        if self.start_engine:
            notify.ensure_engine()
        notify.log_status(f"stream queued job={job['id']} sentence_len={len(job['text'])} job_created_ns={time.monotonic_ns()}")


def connect(endpoint):
    import websocket
    sock = socket.socket(socket.AF_UNIX)
    sock.settimeout(10)
    try:
        sock.connect(endpoint)
        # recv() still performs strict bytes.decode('utf-8'). Avoid the library's
        # duplicate Python-level validation pass over large Korean histories.
        return websocket.create_connection('ws://localhost/', socket=sock, timeout=10,
                                           skip_utf8_validation=True)
    except Exception:
        sock.close()
        raise


def mirror_selection(event):
    """Track the native client's selection on this private server, not deltas."""
    method, params = event.get('method'), event.get('params', {})
    thread = None
    if method == 'thread/started':
        thread = params.get('thread', {}).get('id')
    elif method == 'turn/started':
        thread = params.get('threadId')
    if isinstance(thread, str) and thread:
        path = notify.STATE / 'mirror-thread.json'
        try:
            if not path.exists() or json.loads(path.read_text()).get('thread') != thread:
                # No fsync on the streaming path; the mirror polls separately.
                fd, name = tempfile.mkstemp(dir=path.parent, prefix='.mirror-')
                try:
                    with os.fdopen(fd, 'w') as out:
                        json.dump({'thread': thread}, out)
                    os.replace(name, path)
                finally:
                    Path(name).unlink(missing_ok=True)
        except (OSError, ValueError) as exc:
            notify.log_status(f'mirror selection failed: {type(exc).__name__}')


def observe(endpoint, thread_id, directory, ready=None, submit=None, stop=None):
    accumulator = Accumulator(directory, thread_id, submit or Publisher(), notify.log_status)
    initial = not (Path(directory) / '.baseline').exists()
    while stop is None or not stop.is_set():
        ws = None
        try:
            ws = connect(endpoint)
            ws.send(json.dumps(dict(id=1, method='initialize', params=dict(clientInfo=dict(name='codex_enikk_tts', version='1')))))
            while True:
                e = json.loads(ws.recv())
                if e.get('id') == 1:
                    if 'error' in e: raise RuntimeError(str(e['error']))
                    break
            ws.send(json.dumps(dict(method='initialized')))
            ws.send(json.dumps(dict(id=2, method='thread/resume', params=dict(threadId=thread_id))))
            while True:
                e = json.loads(ws.recv())
                if e.get('id') == 2:
                    if 'error' in e: raise RuntimeError(str(e['error']))
                    accumulator.snapshot(e['result']['thread'], initial=initial, reconnecting=not initial)
                    break
            if initial:
                atomic_json(Path(directory) / '.baseline', {'initialized': True, 'ignored_turns': sorted(accumulator.baseline)})
            initial = False
            accumulator.recover()
            if ready:
                atomic_json(Path(ready), dict(thread=thread_id, ready=True,
                            run_id=os.environ.get('CODEX_ENIKK_TTS_RUN_ID'), state=str(notify.STATE),
                            tts_ready=notify.engine_ready()))
                notify.log_status(f"stream_ready thread={thread_id} run_id={os.environ.get('CODEX_ENIKK_TTS_RUN_ID')}")
            import websocket
            ws.settimeout(.5)
            while stop is None or not stop.is_set():
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                if not raw: raise ConnectionError('app-server closed')
                event = json.loads(raw)
                mirror_selection(event)
                # Observer never answers approval/tool RPC requests or sends turn input.
                accumulator.event(event)
            # The wrapper keeps the server alive during this bounded drain. A
            # final item can race TUI exit; reconcile its authoritative snapshot
            # before releasing ownership, without flushing an interrupted tail.
            if stop is not None and stop.is_set():
                ws.settimeout(2)
                drain_deadline = time.monotonic() + 2
                ws.send(json.dumps(dict(id=3, method='thread/resume', params=dict(threadId=thread_id))))
                while time.monotonic() < drain_deadline:
                    event = json.loads(ws.recv())
                    if event.get('id') == 3:
                        if 'error' in event: raise RuntimeError(str(event['error']))
                        accumulator.snapshot(event['result']['thread'], reconnecting=True)
                        notify.log_status('stream shutdown snapshot reconciled')
                        break
        except ValueError:
            notify.log_status('stream conflict: stopped; checkpoint preserved')
            raise
        except Exception as exc:
            notify.log_status(f'stream reconnect reason={type(exc).__name__}')
            if stop is not None and stop.wait(1): break
            if stop is None: time.sleep(1)
        finally:
            if ws is not None: ws.close()


def report_engine_ready():
    """One run-local status line; never write into the native TUI's terminal."""
    started = os.environ.get('CODEX_ENIKK_STARTUP_NS')
    if not started or not notify.run_active() or not notify.engine_ready():
        return
    elapsed = (time.monotonic_ns() - int(started)) / 1e9
    pending = 0
    for path in (notify.STATE / 'jobs').glob('*'):
        if path.name.startswith('.'):
            continue
        try:
            job = json.loads(path.read_text())
        except (OSError, ValueError):
            continue  # Atomic job publication/cleanup may race this read.
        terminal = job.get('delivery', {}).get('terminal', {})
        if (job.get('run_id') == os.environ.get('CODEX_ENIKK_TTS_RUN_ID')
                and notify.epoch_valid(job)
                and job.get('text', '').strip()
                and not (terminal and len(terminal) == len(job.get('delivery', {}).get('parts', [job['text']]))
                         and all(v in ('PLAYED', 'FAILED_EXPLICITLY') for v in terminal.values()))):
            pending += 1
    message = f'Yuki TTS ready ({elapsed:.1f}s)'
    if pending:
        message += f" — {pending} queued sentence{'s' if pending != 1 else ''}"
    with (notify.STATE / 'runtime.log').open('a+', encoding='utf-8') as out:
        fcntl.flock(out, fcntl.LOCK_EX)
        out.seek(0)
        if 'Yuki TTS ready (' in out.read() or not notify.run_active() or not notify.engine_ready():
            return
        out.write(message + '\n')
        out.flush()


def monitor_engine(stop):
    """Observe model warmup without blocking the subscription or native TUI."""
    deadline = time.monotonic() + 60
    while not stop.is_set():
        if not notify.run_active():
            stop.set()
            return
        if notify.engine_ready():
            notify.log_status(f"TTS_READY monotonic_ns={time.monotonic_ns()}")
            try:
                report_engine_ready()
            except (OSError, ValueError) as exc:
                notify.log_status(f"TTS_STATUS_FAILED reason={type(exc).__name__}")
            return
        if time.monotonic() >= deadline:
            notify.log_status("TTS_READY_FAILED reason=readiness_timeout pending=current_run_preserved")
            return
        stop.wait(.05)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--socket', required=True)
    parser.add_argument('--thread', required=True)
    parser.add_argument('--ready')
    args = parser.parse_args()
    directory = notify.STATE / 'streams' / hashlib.sha256(args.thread.encode()).hexdigest()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (directory / '.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        stop = threading.Event()
        def monitor_owner():
            while not stop.wait(.1):
                if not notify.run_active():
                    stop.set()
        threading.Thread(target=monitor_owner, daemon=True).start()
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        # Queue publication never depends on model readiness. The existing run
        # namespace/owner cancellation prevents these jobs crossing a restart.
        try:
            notify.ensure_engine()
        except (OSError, subprocess.SubprocessError) as exc:
            notify.log_status(f"TTS_READY_FAILED reason=spawn_{type(exc).__name__} pending=current_run_preserved")
        threading.Thread(target=monitor_engine, args=(stop,), daemon=True).start()
        try:
            observe(args.socket, args.thread, directory, args.ready,
                    submit=Publisher(start_engine=False), stop=stop)
        finally:
            stop.set()


if __name__ == '__main__':
    main()
