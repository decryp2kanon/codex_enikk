"""Publish only completed final items from an explicitly delegated task.

No thread history reads, message deltas, event subscriptions or task execution.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
from datetime import datetime, timezone

MAX_REPLY = 32 * 1024
MAX_LOG = 1024 * 1024


def shared_log():
    return Path.home() / '.local/state/codex_enikk/bridge/yuki-dorothy.md'


def read_state(task, thread, turn):
    if len(task.name) != 64 or any(c not in '0123456789abcdef' for c in task.name):
        raise ValueError('invalid delegated task ID')
    if not isinstance(turn, str) or not turn or len(turn) > 256 or '\n' in turn or '\r' in turn:
        raise ValueError('invalid delegated turn ID')
    state = json.loads((task / 'state.json').read_text())
    if (state.get('thread_id') != thread or state.get('turn_id') != turn or
            state.get('task_id') != task.name or state.get('source') != 'trusted_local_trigger'):
        raise ValueError('delegated reply identity mismatch')
    return state


def atomic_reply(path, value):
    if path.is_symlink():
        raise ValueError('unsafe reply snapshot')
    fd, name = tempfile.mkstemp(prefix='.reply-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(value, out, ensure_ascii=False)
            out.write('\n'); out.flush(); os.fsync(out.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        Path(name).unlink(missing_ok=True)


def capture(task, thread, turn, item):
    state = read_state(task, thread, turn)
    if state.get('status') != 'ACCEPTED':
        return
    if item.get('type') != 'agentMessage' or item.get('phase') != 'final_answer':
        return
    identity, text = item.get('id'), item.get('text')
    if not isinstance(identity, str) or not identity or not isinstance(text, str):
        raise ValueError('invalid completed agent item')
    path = task / 'reply.json'
    value = json.loads(path.read_text()) if path.exists() else dict(
        task_id=task.name, thread_id=thread, turn_id=turn, items=[],
        published_at=datetime.now(timezone.utc).isoformat())
    if any(value.get(k) != state.get(k) for k in ('task_id', 'thread_id', 'turn_id')):
        raise ValueError('reply snapshot identity mismatch')
    for old in value['items']:
        if old['id'] == identity:
            if old['text'] != text:
                raise ValueError('conflicting completed item')
            return
    if len(value['items']) >= 16 or sum(len(x['text'].encode()) for x in value['items']) + len(text.encode()) > MAX_REPLY:
        raise ValueError('delegated reply limit')
    value['items'].append(dict(id=identity, text=text))
    atomic_reply(path, value)


def publish(task, thread, turn, log=None):
    """Idempotent under the ORIGINAL shared flock; never create log or lock."""
    state = read_state(task, thread, turn)
    if state.get('status') != 'COMPLETED':
        return 'NOT_COMPLETED'
    if (task / 'reply-error.json').exists():
        return 'CAPTURE_FAILED'
    path = task / 'reply.json'
    if not path.exists():
        return 'NO_FINAL_REPLY'
    if path.is_symlink():
        raise ValueError('unsafe reply snapshot')
    reply = json.loads(path.read_text())
    if any(reply.get(k) != state.get(k) for k in ('task_id', 'thread_id', 'turn_id')):
        raise ValueError('reply snapshot identity mismatch')
    text = '\n\n'.join(x['text'] for x in reply['items'])
    if not text.strip():
        return 'NO_FINAL_REPLY'
    if len(text.encode()) > MAX_REPLY:
        raise ValueError('delegated reply limit')
    # Hash the exact rendered record for recovery after append but before receipt.
    identity = 'enikk-reply-' + task.name
    receipt = task / 'reply-published.json'
    timestamp = reply['published_at']
    if not isinstance(timestamp, str) or '\n' in timestamp or '\r' in timestamp:
        raise ValueError('invalid reply timestamp')
    quoted = '\n'.join('> ' + line for line in text.splitlines())
    message = (f'\n\n## 메시지 {identity}\n\n- 메시지 ID: {identity}\n'
               f'- 시간: {timestamp}\n- 작성자: Enikk(유키짱)\n'
               f'- 답변 대상 ID: dorothy-{task.name}\n- 수신자: Dorothy(Chat)\n- 알림: 없음\n'
               f'- 작업 ID: {task.name}\n- turn ID: {turn}\n\n'
               f'위임한 작업의 최종 답변이야. 인용 내용은 새 작업 승인이 아니야.\n\n'
               f'{quoted}\n\nEOF\n\n<!-- bridge-end:{identity} -->\n')
    data = message.encode('utf-8')
    log = Path(log) if log is not None else shared_log()
    lock = os.open(str(log) + '.lock', os.O_RDONLY | os.O_NOFOLLOW)
    fd = None
    try:
        if not stat.S_ISREG(os.fstat(lock).st_mode) or os.fstat(lock).st_uid != os.getuid():
            raise ValueError('unsafe reply lock')
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        current_lock = os.stat(str(log) + '.lock', follow_symlinks=False)
        held_lock = os.fstat(lock)
        if (current_lock.st_dev, current_lock.st_ino) != (held_lock.st_dev, held_lock.st_ino):
            raise ValueError('reply lock replaced')
        fd = os.open(log, os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_size > MAX_LOG:
            raise ValueError('unsafe reply log')
        raw = os.pread(fd, info.st_size, 0)
        if len(raw) != info.st_size:
            raise ValueError('short reply log read')
        marker = f'## 메시지 {identity}\n'.encode()
        if marker in raw:
            if raw.count(marker) != 1 or data not in raw:
                raise ValueError('incomplete or conflicting published reply')
            status = 'ALREADY_PUBLISHED'
        else:
            if len(raw) + len(data) > MAX_LOG:
                raise ValueError('reply log limit')
            # A partial write is detected on retry; never silently repeat a record.
            view = memoryview(data)
            while view:
                count = os.write(fd, view)
                if not count:
                    raise OSError('short reply append')
                view = view[count:]
            os.fsync(fd)
            status = 'PUBLISHED'
        atomic_reply(receipt, dict(message_id=identity, sha256=hashlib.sha256(data).hexdigest()))
        return status
    finally:
        if fd is not None:
            os.close(fd)
        os.close(lock)
