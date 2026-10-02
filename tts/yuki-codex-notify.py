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
from datetime import datetime


ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get("CODEX_ENIKK_TTS_STATE", Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "codex_enikk" / "tts"))
SEEN = STATE / "seen"
JOBS = STATE / "jobs"
LOG = STATE / "notify.log"


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


def ensure_engine():
    with (STATE / "engine.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return  # The resident model is already running.
        fcntl.flock(lock, fcntl.LOCK_UN)
    # The engine takes the same lock before loading the model.
    with LOG.open("a", encoding="utf-8") as output:
        subprocess.Popen([sys.executable, str(ROOT / "yuki-tts-engine.py")],
                         stdin=subprocess.DEVNULL, stdout=output, stderr=output,
                         start_new_session=True, close_fds=True)


def handle_notification(payload):
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
            json.dump({"id": event_id[:12], "text": text, "queued_ns": time.monotonic_ns()}, stream)
        os.replace(temporary, job)
        ensure_engine()
        log_status("queued completed turn")
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
