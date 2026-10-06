"""Append-only conversation evidence. No prompts, identities or past commands."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile


def directory_sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def atomic_json(path, value):
    fd, temporary = tempfile.mkstemp(prefix='.checkpoint-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(value, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, path)
        directory_sync(path.parent)
    finally:
        Path(temporary).unlink(missing_ok=True)


class Continuity:
    def __init__(self, home, root):
        self.home = Path(home).resolve()
        self.root = Path(root) / hashlib.sha256(str(self.home).encode()).hexdigest()
        if self.root.is_symlink() or self.root.parent.is_symlink():
            raise ValueError('Unsafe continuity evidence directory')
        self.state = self.root / 'checkpoint.json'
        self.journal = self.root / 'original.jsonl'

    def load(self):
        if self.state.is_symlink():
            raise ValueError('Continuity checkpoint is a symlink')
        if not self.state.exists():
            if self.journal.exists():
                raise ValueError('Orphan continuity journal: preserve it and recover the checkpoint')
            return None
        try:
            data = json.loads(self.state.read_text())
            if (data['version'] != 1 or data['home'] != str(self.home)
                    or not isinstance(data['session_id'], str)
                    or not isinstance(data['bytes'], int) or data['bytes'] < 1
                    or len(data['sha256']) != 64):
                raise ValueError()
            relative = Path(data['rollout'])
            if relative.is_absolute() or '..' in relative.parts or relative.parts[0] not in ('sessions', 'archived_sessions'):
                raise ValueError()
        except (KeyError, TypeError, IndexError, ValueError):
            raise ValueError('Invalid continuity checkpoint; restore evidence, never rebind') from None
        return data

    def require_binding(self):
        previous = self.load()
        if previous is None:
            return
        pin = self.home / 'enikk-continuity.json'
        if pin.is_symlink() or not pin.is_file():
            raise ValueError('Continuity pin missing; refusing to select another conversation')
        try:
            current = json.loads(pin.read_text())['session_id']
        except (KeyError, TypeError, ValueError):
            raise ValueError('Invalid continuity pin') from None
        if current != previous['session_id']:
            raise ValueError('Continuity thread changed; refusing to resume')

    def verify_journal(self, state):
        if self.journal.is_symlink() or not self.journal.is_file():
            raise ValueError('Missing or unsafe continuity journal')
        digest = hashlib.sha256()
        remaining = state['bytes']
        with self.journal.open('rb') as stream:
            while remaining:
                block = stream.read(min(1024 * 1024, remaining))
                if not block:
                    raise ValueError('Continuity journal truncated')
                digest.update(block)
                remaining -= len(block)
        if digest.hexdigest() != state['sha256']:
            raise ValueError('Continuity journal modified')

    def database_check(self, session_id, path):
        state = self.home / 'state_5.sqlite'
        history = self.home / 'thread_history_1.sqlite'
        for database in (state, history):
            if not database.exists():
                continue
            if database.is_symlink():
                raise ValueError('Unsafe continuity database')
            with closing(sqlite3.connect(database.as_uri() + '?mode=ro', uri=True, timeout=1)) as connection:
                if connection.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
                    raise ValueError('Continuity database integrity failure: ' + database.name)
                if database == state:
                    row = connection.execute('SELECT rollout_path FROM threads WHERE id=?', (session_id,)).fetchone()
                    if row is None or Path(row[0]).resolve() != path.resolve():
                        raise ValueError('Pinned thread/database rollout mismatch')
                else:
                    row = connection.execute('SELECT next_rollout_byte_offset FROM thread_history_projection_state WHERE thread_id=?', (session_id,)).fetchone()
                    if row is not None and not 0 <= row[0] <= path.stat().st_size:
                        raise ValueError('Thread projection exceeds original rollout')

    def inspect(self, session_id, path, save=False, allow_partial=False):
        self.require_binding()
        previous = self.load()
        path = Path(path)
        relative = path.relative_to(self.home)
        if path.is_symlink() or not path.resolve().is_relative_to(self.home):
            raise ValueError('Unsafe continuity rollout')
        if previous:
            if relative.as_posix() != previous['rollout'] or session_id != previous['session_id']:
                raise ValueError('Pinned rollout changed')
            self.verify_journal(previous)
        old_bytes = previous['bytes'] if previous else 0
        old_digest = hashlib.sha256()
        digest = hashlib.sha256()
        total = compactions = 0
        partial = False
        # Hold a bounded read of this inode; live append is picked up next time.
        with path.open('rb') as source, tempfile.TemporaryFile() as tail:
            limit = os.fstat(source.fileno()).st_size
            while total < limit:
                line = source.readline(limit - total)
                if not line.endswith(b'\n'):
                    partial = True
                    if not allow_partial:
                        raise ValueError('Incomplete rollout tail; preserve original and recover before resume')
                    break
                try:
                    record = json.loads(line.decode('utf-8'))
                    if not isinstance(record, dict):
                        raise ValueError('record is not an object')
                except (UnicodeError, ValueError) as exc:
                    raise ValueError(f'Corrupt rollout at byte {total}: {exc}') from None
                if total == 0 and (record.get('type') != 'session_meta' or not isinstance(record.get('payload'), dict) or record['payload'].get('id') != session_id):
                    raise ValueError('Rollout metadata does not match pinned thread')
                compactions += record.get('type') == 'compacted'
                end = total + len(line)
                if total < old_bytes:
                    old_digest.update(line[:min(len(line), old_bytes - total)])
                if end > old_bytes:
                    tail.write(line[max(0, old_bytes - total):])
                digest.update(line)
                total = end
            if not total or total < old_bytes:
                raise ValueError('Original conversation truncated')
            if previous and old_digest.hexdigest() != previous['sha256']:
                raise ValueError('Previously preserved conversation rewritten')
            if path.stat().st_ino != os.fstat(source.fileno()).st_ino or path.stat().st_size < limit:
                raise ValueError('Rollout replaced or truncated during verification')
            self.database_check(session_id, path)
            result = dict(version=1, home=str(self.home), session_id=session_id,
                          rollout=relative.as_posix(), bytes=total, sha256=digest.hexdigest(),
                          compactions=compactions)
            if save and (previous is None or total != old_bytes):
                self.root.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
                self.root.parent.chmod(0o700)
                self.root.mkdir(exist_ok=True, mode=0o700)
                if self.root.is_symlink() or self.journal.is_symlink():
                    raise ValueError('Unsafe continuity evidence directory')
                self.root.chmod(0o700)
                # A crash may leave extra uncommitted bytes after the last checkpoint.
                # Only discard those after both original and committed evidence verify.
                fd = os.open(self.journal, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
                with os.fdopen(fd, 'r+b') as out:
                    out.truncate(old_bytes)
                    out.seek(old_bytes)
                    tail.seek(0)
                    while block := tail.read(1024 * 1024):
                        out.write(block)
                    out.flush()
                    os.fsync(out.fileno())
                atomic_json(self.state, result)
            return result | {'partial_tail': partial, 'checkpoint_present': previous is not None}

    def search(self, query, direct_user_only=False):
        state = self.load()
        if state is None:
            raise ValueError('No preserved continuity journal; start the guarded wrapper once')
        self.verify_journal(state)
        with self.journal.open('rb') as source:
            while source.tell() < state['bytes']:
                offset = source.tell()
                record = json.loads(source.readline())
                payload = record.get('payload', {})
                if record.get('type') != 'response_item' or payload.get('type') != 'message':
                    continue
                role = payload.get('role')
                if role not in ('user', 'assistant') or direct_user_only and role != 'user':
                    continue
                text = '\n'.join(part.get('text', '') for part in payload.get('content', []) if isinstance(part, dict))
                if direct_user_only and '[USER · 도로시 경유]' in text:
                    continue
                if query.casefold() in text.casefold():
                    yield dict(session_id=state['session_id'], rollout=state['rollout'],
                               byte_offset=offset, timestamp=record.get('timestamp'), role=role, text=text)
