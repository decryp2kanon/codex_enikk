#!/usr/bin/env python3
"""Speak completed turns from the Codex Enikk session already running in TUI."""

import importlib.util
import json
import os
from pathlib import Path
import time


HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser().resolve()
STATE = HOME / "enikk-continuity.json"
spec = importlib.util.spec_from_file_location("yuki_notify", Path(__file__).with_name("yuki-codex-notify.py"))
notify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notify)


class Tail:
    def __init__(self, path, session):
        self.path, self.session = path, session
        self.offset = path.stat().st_size  # Never replay a prior answer.

    def poll(self):
        if self.path.stat().st_size < self.offset:
            self.offset = self.path.stat().st_size
        with self.path.open("rb") as stream:
            stream.seek(self.offset)
            while True:
                raw = stream.readline()
                if not raw or not raw.endswith(b"\n"):
                    break
                self.offset = stream.tell()
                try:
                    record = json.loads(raw)
                except (ValueError, UnicodeError):
                    continue
                payload = record.get("payload") or {}
                if record.get("type") != "event_msg" or payload.get("type") != "item_completed":
                    continue
                item = payload.get("item") or {}
                if item.get("type") != "AgentMessage" or item.get("phase") not in ("commentary", "final_answer"):
                    continue
                parts = item.get("content") or []
                answer = "\n".join(part.get("text", "") for part in parts
                                   if isinstance(part, dict) and part.get("type") in ("Text", "output_text"))
                turn = payload.get("turn_id")
                if isinstance(answer, str) and answer.strip() and isinstance(turn, str) and turn:
                    notify.handle_notification({"type": "agent-turn-complete", "thread-id": self.session,
                                                "turn-id": turn, "last-assistant-message": answer})


def selected():
    session = json.loads(STATE.read_text(encoding="utf-8"))["session_id"]
    matches = list((HOME / "sessions").rglob(f"*{session}.jsonl"))
    return (matches[0], session) if matches else None


def main():
    notify.STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    notify.ensure_engine()
    current = None
    last_scan = 0.0
    while notify.run_active():
        if time.monotonic() - last_scan > 2:
            last_scan = time.monotonic()
            try:
                active = selected()
                if active and (current is None or (current.path, current.session) != active):
                    current = Tail(*active)
            except (OSError, ValueError, KeyError):
                pass
        if current:
            try:
                current.poll()
            except OSError:
                current = None
        time.sleep(0.1)


if __name__ == "__main__":
    main()
