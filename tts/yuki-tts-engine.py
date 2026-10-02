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

import numpy as np
from supertonic import TTS


ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get("CODEX_ENIKK_TTS_STATE", Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "codex_enikk" / "tts"))
JOBS = STATE / "jobs"
STYLE = ROOT / "yuki-f5ttl-f4dp.json"


def log(message):
    with (STATE / "notify.log").open("a", encoding="utf-8") as out:
        out.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {message}\n")


LATIN = re.compile(r"[A-Za-z][A-Za-z0-9_+.#/-]*(?:[ \t]+[A-Za-z][A-Za-z0-9_+.#/-]*)*")


def sentences(text):
    """Collapse line wraps and retain a short, explicit paragraph boundary."""
    result = []
    paragraphs = re.split(r"\n{2,}", text)
    for paragraph_number, paragraph in enumerate(paragraphs):
        paragraph = re.sub(r"\n", " ", paragraph).strip()
        parts = [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+", paragraph) if part.strip()]
        for number, part in enumerate(parts):
            paragraph_end = number == len(parts) - 1 and paragraph_number < len(paragraphs) - 1
            result.append((part, 0.18 if paragraph_end else 0.08))
    return result


def language_segments(text):
    """Route Latin terms to English while leaving surrounding text in Korean."""
    result = []
    position = 0
    for match in LATIN.finditer(text):
        if match.start() > position:
            result.append((text[position:match.start()], "ko"))
        result.append((match.group(), "en"))
        position = match.end()
    if position < len(text):
        result.append((text[position:], "ko"))
    return [(part, lang) for part, lang in result if part.strip()]


def trim_and_pause(wav, sample_rate, pause):
    """Remove model edge silence and add a bounded conversational pause."""
    mono = wav.reshape(-1)
    audible = np.flatnonzero(np.abs(mono) > 0.001)
    if audible.size:
        lead = int(sample_rate * 0.015)
        tail = int(sample_rate * 0.035)
        mono = mono[max(0, audible[0] - lead):min(len(mono), audible[-1] + tail + 1)]
    return np.concatenate((mono, np.zeros(int(sample_rate * pause), dtype=mono.dtype)))[None, :]


def generate(tts, style, item, ready):
    job_id, text, queued_ns = item
    number = 0
    for sentence, pause in sentences(text):
        segments = language_segments(sentence)
        for segment_number, (segment, lang) in enumerate(segments):
            raw = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            processed = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
            raw.close()
            processed.close()
            try:
                wav, _ = tts.synthesize(segment, voice_style=style, lang=lang, speed=1.0,
                                        silence_duration=0.05)
                segment_pause = pause if segment_number == len(segments) - 1 else 0.015
                wav = trim_and_pause(wav, tts.sample_rate, segment_pause)
                tts.save_audio(wav, raw.name)
                subprocess.run(["/usr/bin/ffmpeg", "-y", "-loglevel", "error", "-i", raw.name,
                                "-af", "rubberband=tempo=1.3:pitch=1.12246", processed.name],
                               check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                ready.put((job_id, number, processed.name, queued_ns))
                number += 1
                processed = None  # Playback worker owns the file now.
            finally:
                Path(raw.name).unlink(missing_ok=True)
                if processed is not None:
                    Path(processed.name).unlink(missing_ok=True)


def playback(ready):
    previous_end = None
    while True:
        item = ready.get()
        if item is None:
            return
        job_id, number, path, queued_ns = item
        try:
            started = time.monotonic()
            if previous_end is not None:
                log(f"playback gap {started - previous_end:.3f}s job={job_id} part={number}")
            if number == 0:
                log(f"first audio latency {(time.monotonic_ns() - queued_ns) / 1e9:.3f}s job={job_id}")
            subprocess.run(["/usr/bin/aplay", "-q", path], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            previous_end = time.monotonic()
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
