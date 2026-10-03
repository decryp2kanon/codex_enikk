#!/usr/bin/env python3
"""Queue only Codex's completed user-facing answer for resident TTS."""

import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime


ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get("CODEX_ENIKK_TTS_STATE", Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "codex_enikk" / "tts"))
SEEN = STATE / "seen"
JOBS = STATE / "jobs"
LOG = STATE / "notify.log"


@contextmanager
def epoch_lock(state=None):
    state = Path(state or STATE)
    state.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (state / 'epoch.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield


def current_epoch(state=None):
    try:
        return json.loads((Path(state or STATE) / 'epoch.json').read_text())
    except FileNotFoundError:
        return {}


def epoch_valid(job, state=None):
    active = current_epoch(state)
    return not active or (job.get('epoch') == active['epoch'] and
                          job.get('source', {}).get('thread') == active['thread'] and
                          job.get('source', {}).get('turn') == active['turn'])


def user_ordinal(thread, turn, item):
    """Use persisted protocol order when replayed events arrive out of order."""
    db = Path(os.environ.get('CODEX_HOME', Path.home() / '.codex')) / 'thread_history_1.sqlite'
    try:
        with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True, timeout=.1) as conn:
            row = conn.execute('SELECT rollout_ordinal FROM thread_items WHERE thread_id=? AND turn_id=? AND item_id=?',
                               (thread, turn, item)).fetchone()
            return row[0] if row else None
    except (sqlite3.Error, ValueError):
        return None


def advance_epoch(thread, turn, user, ordinal=None, state=None):
    state = Path(state or STATE)
    with epoch_lock(state):
        old = current_epoch(state)
        seen = old.get('seen_users', [])
        # Persistence may lag item/started; resolve the active user's ordinal
        # again before comparing a later replay, rather than accepting it blind.
        if old and old.get('ordinal') is None:
            old['ordinal'] = user_ordinal(old['thread'], old['turn'], old['epoch'])
        if user in seen or (old.get('thread') == thread and ordinal is not None and
                            old.get('ordinal') is not None and ordinal <= old['ordinal']):
            return False
        if turn in old.get('retired_turns', []):
            return False
        retired = old.get('retired_turns', [])
        if old.get('turn') and old['turn'] != turn:
            retired = retired + [old['turn']]
        value = dict(epoch=user, thread=thread, turn=turn, ordinal=ordinal,
                     seen_users=seen + [user], retired_turns=retired, submitted_ns=time.monotonic_ns())
        fd, name = tempfile.mkstemp(dir=state, prefix='.epoch-')
        try:
            with os.fdopen(fd, 'w') as out:
                json.dump(value, out); out.flush(); os.fsync(out.fileno())
            os.replace(name, state / 'epoch.json')
        finally:
            Path(name).unlink(missing_ok=True)
        log_status(f"USER_SUBMIT epoch={user} turn={turn} monotonic_ns={value['submitted_ns']}")
        return True


def clean_text(text):
    # Keep the answer's wording while omitting code and Markdown decoration.
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    lines = []
    for line in text.splitlines():
        if re.fullmatch(r"\s*\|?[\s:|-]+\|?\s*", line):
            continue
        line = re.sub(r"^\s*(?:#{1,6}\s*|>\s*|[-*+]\s+|\d+[.)]\s+)", "", line)
        lines.append(line)
    text = "\n".join(lines).replace("**", "").replace("__", "")
    text = re.sub(r"[^\S\n]+", " ", text)
    text = re.sub(r"\n(?:[ \t]*\n)+", "\n\n", text)
    return text.strip()


def log_status(message):
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(LOG, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as stream:
        stream.write(f"{datetime.now().isoformat(timespec='seconds')} {message}\n")


def run_active():
    owner = os.environ.get('CODEX_ENIKK_TTS_OWNER')
    if not owner:
        return True
    try:
        pid, born = owner.split(':')
        fields = Path(f'/proc/{int(pid)}/stat').read_text().rsplit(')', 1)[1].split()
        return fields[0] not in ('Z', 'X') and fields[19] == born and not (STATE / 'cancelled').exists()
    except (OSError, ValueError, IndexError):
        return False


def ensure_engine():
    if not run_active():
        return
    with (STATE / "engine.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return  # The resident model is already running.
        fcntl.flock(lock, fcntl.LOCK_UN)
    chatterbox_root = Path(os.environ.get("CODEX_ENIKK_CHATTERBOX_HOME", Path.home() / "Apps/chatterbox-yuki"))
    chatterbox_python = chatterbox_root / ".venv/bin/python"
    use_chatterbox = (ROOT / "yuki-chatterbox-engine.py").is_file() and chatterbox_python.is_file()
    if not use_chatterbox:
        log_status("Chatterbox unavailable; TTS skipped")
        return
    engine = ROOT / "yuki-chatterbox-engine.py"
    python = chatterbox_python
    # The selected engine takes the same lock before loading its persistent model.
    with LOG.open("a", encoding="utf-8") as output:
        subprocess.Popen([str(python), str(engine)],
                         stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                         start_new_session=True, close_fds=True)


def engine_ready():
    try:
        ready = json.loads((STATE / 'model-ready.json').read_text())
        fields = Path(f"/proc/{int(ready['pid'])}/stat").read_text().rsplit(')', 1)[1].split()
        return (fields[0] not in ('Z', 'X') and fields[19] == ready['born']
                and ready['run_id'] == os.environ.get('CODEX_ENIKK_TTS_RUN_ID'))
    except (OSError, ValueError, KeyError, IndexError):
        return False


def handle_notification(payload):
    if not run_active():
        return False
    if payload.get("type") != "agent-turn-complete":
        return False
    session = payload.get("thread-id")
    turn = payload.get("turn-id")
    answer = payload.get("last-assistant-message")
    if not all(isinstance(value, str) and value for value in (session, turn, answer)):
        return False
    text = clean_text(answer)
    if not text:
        return False

    for directory in (STATE, SEEN, JOBS):
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Include the displayed text so multiple commentary messages in one turn are
    # distinct, while a replay of the same completed message remains idempotent.
    event_id = hashlib.sha256(f"{session}\0{turn}\0{text}".encode()).hexdigest()
    marker = SEEN / event_id
    try:
        fd = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    os.close(fd)

    job = JOBS / f"{time.time_ns():020d}-{event_id}"
    try:
        temporary = JOBS / f".{event_id}.tmp"
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump({"id": event_id[:12], "text": text, "queued_ns": time.monotonic_ns(),
                       "run_id": os.environ.get("CODEX_ENIKK_TTS_RUN_ID")}, stream)
        os.replace(temporary, job)
        ensure_engine()
        log_status(f"queued completed turn job={event_id[:12]} original_len={len(answer)} cleaned_len={len(text)}")
    except Exception:
        job.unlink(missing_ok=True)
        temporary.unlink(missing_ok=True)
        marker.unlink(missing_ok=True)
        raise
    return True


def main():
    if len(sys.argv) != 2:
        return
    try:
        handle_notification(json.loads(sys.argv[1]))
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        log_status(f"notification failed: {type(exc).__name__}")


if __name__ == "__main__":
    main()
