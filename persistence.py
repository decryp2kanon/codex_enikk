"""SQLite snapshots and relocated, empty-home restore validation."""
from contextlib import closing
from pathlib import Path
import sqlite3
import time

DATABASES = ('state_5.sqlite', 'thread_history_1.sqlite')


def readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=1)


def validate_database(path):
    with closing(readonly(path)) as connection:
        if connection.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise ValueError(f'Invalid SQLite snapshot: {path.name}')


def snapshots(source, destination):
    """Include committed WAL pages without copying a live database file."""
    result = {}
    for name in DATABASES:
        path = source / name
        if not path.exists():
            continue
        if path.is_symlink() or not path.is_file():
            raise ValueError(f'Unsafe SQLite source: {name}')
        start = time.monotonic()
        def progress(*_):
            if time.monotonic() - start > 30:
                raise TimeoutError(f'SQLite snapshot timed out: {name}; retry after closing Codex')
        output = destination / name
        with closing(readonly(path)) as src, closing(sqlite3.connect(output)) as dst:
            src.backup(dst, pages=256, progress=progress, sleep=.01)
        output.chmod(0o600)
        validate_database(output)
        result[name] = time.monotonic() - start
    return result


def validate_rollouts(directory, original_home, sizes, relocate_to=None):
    """Validate snapshot references; modify only staged copies on restore."""
    state = directory / 'state_5.sqlite'
    history = directory / 'thread_history_1.sqlite'
    if not state.exists():
        if history.exists():
            raise ValueError('thread_history snapshot requires state snapshot; close Codex and retry')
        return
    paths = {}
    with closing(readonly(state)) as connection:
        for thread_id, path in connection.execute('SELECT id, rollout_path FROM threads'):
            try:
                relative = Path(path).relative_to(original_home)
            except ValueError:
                raise ValueError(f'Rollout outside backed-up CODEX_HOME: {thread_id}') from None
            if '..' in relative.parts or not relative.parts or relative.parts[0] not in ('sessions', 'archived_sessions'):
                raise ValueError(f'Unsafe rollout reference: {thread_id}')
            key = 'codex/' + relative.as_posix()
            if key not in sizes:
                raise ValueError(f'Missing rollout for {thread_id}; close Codex and retry')
            paths[thread_id] = (relative, sizes[key])
    if history.exists():
        with closing(readonly(history)) as connection:
            for thread_id, offset in connection.execute(
                    'SELECT thread_id, next_rollout_byte_offset FROM thread_history_projection_state'):
                if thread_id not in paths or offset < 0 or offset > paths[thread_id][1]:
                    raise ValueError(f'Snapshot/rollout mismatch for {thread_id}; close Codex and retry')
    if relocate_to is not None:
        # This database is an isolated staged snapshot, never a user's live DB.
        with closing(sqlite3.connect(state)) as connection:
            with connection:
                connection.executemany('UPDATE threads SET rollout_path=? WHERE id=?',
                                       [(str(relocate_to / relative), thread_id)
                                        for thread_id, (relative, _) in paths.items()])
