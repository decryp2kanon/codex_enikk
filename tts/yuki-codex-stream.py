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
        self.baseline = None
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
        for turn in thread.get('turns', []):
            for item in turn.get('items', []):
                self.snapshot_item(turn['id'], item, turn.get('status'), baseline=initial)
        # Completed states remain on disk, not in an ever-growing memory cache.
        self.items = {k:v for k,v in self.items.items() if not v['completed'] and not v['interrupted']}

    def event(self, event):
        method = event.get('method')
        p = event.get('params', {})
        if p.get('threadId') != self.thread_id:
            return
        if method in ('item/started', 'item/completed'):
            item = p['item']
            if item.get('type') != 'agentMessage':
                return
            state = self.state(p['turnId'], item['id'])
            if method == 'item/started':
                state['phase'] = item.get('phase')
                return
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
            state['text'] += p['delta']
            self.emit(state)
        elif method == 'turn/completed':
            turn = p['turn']
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
        path = self.jobs / job['filename']
        # The engine archives stream delivery receipts before removing queue entries.
        if path.exists() or path.with_name('.played-' + path.name).exists() or path.with_name('.failed-' + path.name).exists():
            return
        fd, name = tempfile.mkstemp(dir=self.jobs, prefix='.stream-')
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as out:
                json.dump(job, out, ensure_ascii=False)
                out.flush(); os.fsync(out.fileno())
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
        return websocket.create_connection('ws://localhost/', socket=sock, timeout=10)
    except Exception:
        sock.close()
        raise


def observe(endpoint, thread_id, directory, ready=None, submit=None, stop=None):
    accumulator = Accumulator(directory, thread_id, submit or Publisher(), notify.log_status)
    initial = not (Path(directory) / '.baseline').exists()
    while stop is None or not stop.is_set():
        ws = None
        try:
            accumulator.recover()
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
                atomic_json(Path(directory) / '.baseline', {'initialized': True})
            initial = False
            if ready:
                atomic_json(Path(ready), dict(thread=thread_id, ready=True))
            import websocket
            ws.settimeout(.5)
            while stop is None or not stop.is_set():
                try:
                    raw = ws.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                if not raw: raise ConnectionError('app-server closed')
                event = json.loads(raw)
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
        signal.signal(signal.SIGTERM, lambda *_: stop.set())
        signal.signal(signal.SIGINT, lambda *_: stop.set())
        observe(args.socket, args.thread, directory, args.ready, stop=stop)


if __name__ == '__main__':
    main()
