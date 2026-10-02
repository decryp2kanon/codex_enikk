"""Read-only current conversation mirror, independent of TTS generation."""
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import threading

LIMIT = 200_000
ANSI = re.compile(r'\x1b\][^\x07]*(?:\x07|\x1b\\)|\x1b\[[0-?]*[ -/]*[@-~]')


def block(item):
    kind = item.get('type')
    if kind == 'userMessage':
        text = '\n'.join(p['text'] for p in item.get('content', [])
                         if p.get('type') == 'text' and isinstance(p.get('text'), str))
        label = 'USER'
    elif kind == 'agentMessage' and item.get('phase') in (None, 'commentary', 'final_answer'):
        text = item.get('text', '')
        label = 'ENIKK'
    else:
        return b''
    if not isinstance(text, str) or not text.strip():
        return b''
    return f'[{label}]\n{ANSI.sub("", text)}\n\n'.encode('utf-8')


def recent_bytes(connection, thread_id, limit=LIMIT):
    """Walk indexed history backwards; keep a contiguous suffix of whole blocks."""
    chunks, size = [], 0
    cursor = connection.execute(
        "SELECT item_json FROM thread_items WHERE thread_id=? "
        "AND item_type IN ('userMessage','agentMessage') ORDER BY rollout_ordinal DESC",
        (thread_id,))
    try:
        for (raw,) in cursor:
            data = block(json.loads(raw))
            if not data:
                continue
            if size + len(data) > limit:
                if not chunks:
                    label, body = data.split(b'\n', 1)
                    prefix = label + b'\n[... older content truncated ...]\n'
                    budget = max(0, limit - len(prefix))
                    tail = body[-budget:] if budget else b''
                    # Only an incomplete leading UTF-8 codepoint can be omitted.
                    chunks.append(prefix + tail.decode('utf-8', 'ignore').encode('utf-8'))
                break
            chunks.append(data)
            size += len(data)
    finally:
        cursor.close()  # Never hold a read transaction between refreshes.
    return b''.join(reversed(chunks))


def atomic_write(path, data):
    if path.is_symlink():
        raise OSError('conversation mirror must not be a symlink')
    if path.exists() and path.read_bytes() == data:
        return
    fd, name = tempfile.mkstemp(prefix='.codex-latest-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


class Mirror:
    """One lightweight data_version check/second; query only after DB changes.

    The private app-server observer can update the selected thread. No delta,
    synthesis or playback callback waits for the database or mirror writer.
    """
    def __init__(self, database, thread_id, destination, selection=None):
        self.database = Path(database)
        self.thread_id = thread_id
        self.destination = Path(destination)
        self.selection = Path(selection) if selection else None
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, name='conversation-mirror', daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stop.set()
        self.thread.join(2)

    def run(self):
        connection = None
        previous = None
        error = None
        while True:
            try:
                if connection is None:
                    connection = sqlite3.connect(self.database.resolve().as_uri() + '?mode=ro',
                                                 uri=True, timeout=.1, isolation_level=None)
                    connection.execute('PRAGMA query_only=ON')
                    previous = None
                selected = self.thread_id
                if self.selection and self.selection.exists():
                    selected = json.loads(self.selection.read_text())['thread']
                version = connection.execute('PRAGMA data_version').fetchone()[0]
                current = (selected, version)
                if current != previous:
                    atomic_write(self.destination, recent_bytes(connection, selected))
                    previous = current
                error = None
            except (OSError, sqlite3.Error, ValueError, KeyError, TypeError) as exc:
                message = f'conversation mirror: {type(exc).__name__}: {exc}'
                if message != error:
                    print(message, file=sys.stderr)
                    error = message
                if connection:
                    connection.close()
                    connection = None
            if self.stop.is_set():
                break
            self.stop.wait(1)
        if connection:
            connection.close()
