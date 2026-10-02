#!/usr/bin/env python3
"""Resident Supertonic model with ordered, pipelined sentence playback."""

import fcntl
import json
import os
from pathlib import Path
import queue
import re
import subprocess
import tempfile
import threading
import time

from supertonic import TTS


ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get("CODEX_ENIKK_TTS_STATE", Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "codex_enikk" / "tts"))
JOBS = STATE / "jobs"
STYLE = ROOT / "yuki-f5ttl-f4dp.json"


def log(message):
    with (STATE / "notify.log").open("a", encoding="utf-8") as out:
        out.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {message}\n")


def sentences(text):
    """Keep punctuation with its sentence; the final remainder is complete too."""
    return [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+", text) if part.strip()]


def generate(tts, style, item, ready):
    job_id, text, queued_ns = item
    for number, sentence in enumerate(sentences(text)):
        raw = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        processed = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        raw.close()
        processed.close()
        try:
            wav, _ = tts.synthesize(sentence, voice_style=style, lang="ko", speed=1.0)
            tts.save_audio(wav, raw.name)
            subprocess.run(["/usr/bin/ffmpeg", "-y", "-loglevel", "error", "-i", raw.name,
                            "-af", "rubberband=tempo=1.3:pitch=1.12246", processed.name],
                           check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            ready.put((job_id, number, processed.name, queued_ns))
            processed = None  # Playback worker owns the file now.
        finally:
            Path(raw.name).unlink(missing_ok=True)
            if processed is not None:
                Path(processed.name).unlink(missing_ok=True)


def playback(ready):
    while True:
        item = ready.get()
        if item is None:
            return
        job_id, number, path, queued_ns = item
        try:
            if number == 0:
                log(f"first audio latency {(time.monotonic_ns() - queued_ns) / 1e9:.3f}s job={job_id}")
            subprocess.run(["/usr/bin/aplay", "-q", path], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except (OSError, subprocess.CalledProcessError) as exc:
            log(f"playback failed job={job_id}: {type(exc).__name__}")
        finally:
            Path(path).unlink(missing_ok=True)
            ready.task_done()


def main():
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    JOBS.mkdir(mode=0o700, parents=True, exist_ok=True)
    with (STATE / "engine.lock").open("a+b") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        log("loading Supertonic model")
        tts = TTS(model="supertonic-3")
        style = tts.get_voice_style_from_path(STYLE)
        log("Supertonic model and style ready")
        ready = queue.Queue()
        player = threading.Thread(target=playback, args=(ready,), daemon=True)
        player.start()
        while True:
            for path in sorted(JOBS.iterdir()):
                if not path.is_file() or path.name.startswith("."):
                    continue
                try:
                    item = json.loads(path.read_text(encoding="utf-8"))
                    path.unlink()
                    generate(tts, style, (item["id"], item["text"], item["queued_ns"]), ready)
                except Exception as exc:
                    log(f"generation failed: {type(exc).__name__}")
            time.sleep(0.05)


if __name__ == "__main__":
    main()
