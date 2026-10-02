#!/usr/bin/env python3
"""Persistent CUDA Chatterbox C2 worker."""

import fcntl
import json
import logging
import os
from pathlib import Path
import queue
import re
import subprocess
import tempfile
import threading
import time

import perth
if perth.PerthImplicitWatermarker is None:
    perth.PerthImplicitWatermarker = perth.DummyWatermarker

import torch
import torchaudio
from chatterbox.mtl_tts import ChatterboxMultilingualTTS


ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get("CODEX_ENIKK_TTS_STATE", Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "codex_enikk" / "tts"))
JOBS = STATE / "jobs"
# The final SUPER-CLEAN C2 reference is configured here (and may be overridden
# explicitly for another installation without duplicating it in the notifier).
REFERENCE = Path(os.environ.get("CODEX_ENIKK_CHATTERBOX_REFERENCE", Path.home() / "Apps/chatterbox-yuki/yuki_super-clean.wav"))
KOREAN_TECH = {
    "SUPER-CLEAN": "슈퍼 클린", "Chatterbox": "채터박스", "Supertonic": "슈퍼토닉", "Codex": "코덱스",
    "GitHub": "깃허브", "Git": "깃", "Python": "파이썬", "Linux": "리눅스",
    "Ubuntu": "우분투", "CPU": "씨피유", "GPU": "지피유", "TTS": "티티에스",
    "API": "에이피아이", "JSON": "제이슨", "WAV": "웨이브",
    "FFmpeg": "에프에프엠펙", "CUDA": "쿠다", "RAM": "램",
    "Bitcoin": "비트코인", "Sugarchain": "슈가체인", "fallback": "폴백",
    "branch": "브랜치", "version": "버전",
}
KOREAN_LETTERS = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", (
    "에이 비 씨 디 이 에프 지 에이치 아이 제이 케이 엘 엠 엔 오 피 큐 알 에스 티 유 브이 더블유 엑스 와이 지"
).split()))
KOREAN_DIGITS = {"0": "제로", "1": "원", "2": "투", "3": "쓰리", "4": "포", "5": "파이브",
                 "6": "식스", "7": "세븐", "8": "에이트", "9": "나인"}
SINO_DIGITS = "영일이삼사오육칠팔구"
DECIMAL_DIGITS = "공일이삼사오육칠팔구"


def korean_integer(value):
    number = int(value)
    if number == 0:
        return "영"
    small_units = ("", "십", "백", "천")
    large_units = ("", "만", "억", "조")
    groups = []
    group_index = 0
    while number:
        group = number % 10000
        if group:
            spoken = ""
            for position in range(3, -1, -1):
                digit = group // (10 ** position) % 10
                if digit:
                    if digit != 1 or position == 0:
                        spoken += SINO_DIGITS[digit]
                    spoken += small_units[position]
            groups.append(spoken + large_units[group_index])
        number //= 10000
        group_index += 1
    return "".join(reversed(groups))


def korean_number(value):
    if "." not in value:
        return korean_integer(value)
    whole, fraction = value.split(".", 1)
    fraction = fraction.rstrip("0") or "0"
    return korean_integer(whole) + " 점 " + " ".join(DECIMAL_DIGITS[int(digit)] for digit in fraction)


def normalize_numbers(text):
    text = re.sub(r"(?i)(?<![A-Za-z])v(?=\d)", "버전 ", text)
    units = {"gb": "기가바이트", "mb": "메가바이트"}
    text = re.sub(
        r"(?i)(?<![\d.])(\d+(?:\.\d+)?)(GB|MB)(?![A-Za-z])",
        lambda match: f"{korean_number(match.group(1))} {units[match.group(2).lower()]}", text)
    text = re.sub(r"(?<![\d.])(\d+(?:\.\d+)?)%", lambda match: korean_number(match.group(1)) + " 퍼센트", text)
    text = re.sub(r"(?<![\d.])(\d+(?:\.\d+)?)(초|분)",
                  lambda match: f"{korean_number(match.group(1))} {match.group(2)}", text)
    text = re.sub(r"(?<![\d.])\d+(?:\.\d+)?(?![\d.])", lambda match: korean_number(match.group(0)), text)
    return text


def log(message):
    with (STATE / "notify.log").open("a", encoding="utf-8") as out:
        out.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {message}\n")


def conditioning_state(model):
    conds = model.conds
    speaker = conds.t3.speaker_emb
    return f"conds={id(conds)} speaker={id(speaker)} shape={tuple(speaker.shape)} mean={speaker.float().mean().item():.6f}"


def sentences(text):
    # Newlines are presentation boundaries, not silent audio segments.
    text = re.sub(r"\s*\n+\s*", " ", text)
    natural = [part.strip() for part in re.split(r"(?<=[.!?。！？])\s+", text) if part.strip()]
    parts = []
    for part in natural:
        while len(part) > 140:
            cut = max(part.rfind(mark, 60, 141) for mark in (" ", ",", ";", ":", "|"))
            if cut < 60:
                cut = 140
            parts.append(part[:cut].strip())
            part = part[cut:].strip(" ,;:|")
        if part:
            parts.append(part)
    return parts


def segment_drop_reason(segment):
    stripped = segment.strip()
    if not stripped:
        return "empty-or-whitespace"
    if re.fullmatch(r"(?:[-*#>|_=~`]+|\d+[.)])", stripped):
        return "formatting-only"
    if not any(character.isalnum() for character in stripped):
        return "punctuation-only"
    return None


def speech_chunks(text, minimum=20, target=28, maximum=55):
    """Keep generation bounded while preserving words and natural sentence ends."""
    chunks = []
    current = ""
    for part in sentences(text):
        for word in part.split():
            candidate = f"{current} {word}".strip()
            if current and len(candidate) > maximum:
                chunks.append(current)
                current = word
            else:
                current = candidate
            if len(current) >= target:
                chunks.append(current)
                current = ""
        if len(current) >= minimum:
            chunks.append(current)
            current = ""
    if current:
        chunks.append(current)
    return chunks


class GenerationWarnings(logging.Handler):
    """Capture strong alignment failures that Chatterbox exposes only as logs."""
    def __init__(self):
        super().__init__()
        self.reason = None

    def emit(self, record):
        message = record.getMessage()
        if "long_tail=tensor(True)" in message:
            self.reason = "Chatterbox long-tail anomaly"
        elif "alignment_repetition=tensor(True)" in message:
            self.reason = "Chatterbox alignment-repetition anomaly"


def trim_edge_silence(wav, sample_rate):
    """Remove only long quiet edges, retaining a short natural breath."""
    mono = wav.detach().float().mean(dim=0) if wav.ndim > 1 else wav.detach().float()
    frame_size = max(1, sample_rate // 50)
    frame_count = mono.numel() // frame_size
    if frame_count < 3:
        return wav, 0.0, 0.0
    rms = mono[:frame_count * frame_size].reshape(frame_count, frame_size).square().mean(dim=1).sqrt()
    voiced = (rms > 0.002).nonzero().flatten()
    if voiced.numel() == 0:
        return wav, 0.0, 0.0
    padding = int(0.08 * sample_rate)
    start = max(0, int(voiced[0]) * frame_size - padding)
    end = min(mono.numel(), (int(voiced[-1]) + 1) * frame_size + padding)
    leading = start / sample_rate
    trailing = (mono.numel() - end) / sample_rate
    return wav[..., start:end], leading, trailing


def korean_pronunciation(text):
    """Keep displayed text intact while giving common technical terms Korean readings."""
    pattern = re.compile(r"(?<![A-Za-z])(?:" + "|".join(map(re.escape, sorted(KOREAN_TECH, key=len, reverse=True))) + r")(?![A-Za-z])", re.I)
    canonical = {key.lower(): value for key, value in KOREAN_TECH.items()}
    text = pattern.sub(lambda match: canonical[match.group(0).lower()], text)
    text = re.sub(
        r"(?<![A-Za-z0-9])([A-Za-z])(\d)(?![A-Za-z0-9])",
        lambda match: f"{KOREAN_LETTERS[match.group(1).upper()]} {KOREAN_DIGITS[match.group(2)]}",
        text,
    )
    text = normalize_numbers(text)
    return re.sub(r"(?<![A-Za-z])[A-Z]{2,}(?![A-Za-z])", lambda match: "".join(KOREAN_LETTERS[c] for c in match.group(0)), text)


def suspicious_audio(wav, sample_rate, text):
    """Reject only unmistakably long or low, stationary generated audio."""
    audio = wav.detach().float().cpu()
    audio = audio.mean(dim=0) if audio.ndim > 1 else audio.reshape(-1)
    duration = audio.numel() / sample_rate
    maximum = max(20.0, 10.0 + 0.5 * len(text))
    if duration > maximum:
        return True, f"duration {duration:.2f}s exceeds {maximum:.2f}s", duration
    if duration >= 8.0:
        tail = audio[-min(audio.numel(), 3 * sample_rate):]
        rms = tail.square().mean().sqrt().item()
        if rms > 0.01:
            spectrum = torch.fft.rfft(tail * torch.hann_window(tail.numel()))
            power = spectrum.abs().square()
            frequencies = torch.fft.rfftfreq(tail.numel(), 1 / sample_rate)
            centroid = (power * frequencies).sum() / power.sum().clamp_min(1e-12)
            frames = tail[:tail.numel() // 2048 * 2048].reshape(-1, 2048)
            frame_rms = frames.square().mean(dim=1).sqrt()
            variation = frame_rms.std() / frame_rms.mean().clamp_min(1e-12)
            if centroid.item() < 70 and variation.item() < 0.08:
                return True, "stationary low-frequency tail", duration
    if duration >= 4.0:
        frame_size = 2048
        framed = audio[:audio.numel() // frame_size * frame_size].reshape(-1, frame_size)
        energetic = framed.square().mean(dim=1).sqrt() > 0.01
        if energetic.any():
            spectrum = torch.fft.rfft(framed[energetic] * torch.hann_window(frame_size), dim=1).abs().square()
            # Speech spreads energy across harmonics and noise. A tone or sweep can
            # move between frames, but remains implausibly concentrated within each.
            concentration = spectrum.topk(5, dim=1).values.sum(dim=1) / spectrum.sum(dim=1).clamp_min(1e-12)
            if (concentration > 0.97).float().mean().item() > 0.85:
                return True, "tonal or sweeping non-speech signal", duration
    return False, "", duration


def playback(ready):
    previous_end = None
    while True:
        job_id, number, path, queued_ns, generated, audio_duration = ready.get()
        try:
            started = time.monotonic()
            gap = 0.0 if previous_end is None else max(0.0, started - previous_end)
            log(f"Chatterbox playback start job={job_id} part={number} queue_wait={started-generated:.3f}s previous_gap={gap:.3f}s audio={audio_duration:.2f}s")
            if number == 0:
                log(f"Chatterbox first audio latency {(time.monotonic_ns()-queued_ns)/1e9:.3f}s job={job_id}")
            subprocess.run(["/usr/bin/aplay", "-q", path], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            previous_end = time.monotonic()
        finally:
            Path(path).unlink(missing_ok=True)
            ready.task_done()


def run():
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    JOBS.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable")
    if not REFERENCE.is_file():
        raise FileNotFoundError(REFERENCE)
    with (STATE / "engine.lock").open("a+b") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        started = time.monotonic()
        log("loading Chatterbox multilingual model on CUDA")
        model = ChatterboxMultilingualTTS.from_pretrained(device="cuda")
        model.prepare_conditionals(str(REFERENCE), exaggeration=0.50)
        canonical_state = conditioning_state(model)
        log(f"Chatterbox C2 ready load_time={time.monotonic()-started:.3f}s reference={REFERENCE} state={canonical_state}")
        ready = queue.Queue()
        threading.Thread(target=playback, args=(ready,), daemon=True).start()
        while True:
            for path in sorted(JOBS.iterdir()):
                if not path.is_file() or path.name.startswith("."):
                    continue
                item = json.loads(path.read_text(encoding="utf-8"))
                preprocessing = time.monotonic()
                candidates = [korean_pronunciation(part) for part in speech_chunks(item["text"])]
                parts = []
                for candidate in candidates:
                    reason = segment_drop_reason(candidate)
                    log(f"Chatterbox segment job={item['id']} repr={candidate!r} dropped={bool(reason)} reason={reason or '-'}")
                    if not reason:
                        parts.append(candidate.strip())
                log(f"Chatterbox accepted job={item['id']} normalized={item['text']!r} segments={len(parts)} preprocessing={time.monotonic()-preprocessing:.6f}s")
                for number, sentence in enumerate(parts):
                    # Final defense at the synthesis boundary, independent of the splitter.
                    reason = segment_drop_reason(sentence)
                    if reason:
                        log(f"Chatterbox pre-generate drop job={item['id']} part={number} repr={sentence!r} reason={reason}")
                        continue
                    accepted = None
                    for attempt in range(2):
                        began = time.monotonic()
                        log(f"Chatterbox generate start job={item['id']} part={number} attempt={attempt + 1} text_len={len(sentence)} text={sentence!r}")
                        try:
                            warnings = GenerationWarnings()
                            anomaly_logger = logging.getLogger("chatterbox.models.t3.inference.alignment_stream_analyzer")
                            anomaly_logger.addHandler(warnings)
                            try:
                                wav = model.generate(sentence, language_id="ko", exaggeration=0.50,
                                                     cfg_weight=0.70).cpu()
                            finally:
                                anomaly_logger.removeHandler(warnings)
                        except Exception as exc:
                            log(f"Chatterbox generate error job={item['id']} part={number} attempt={attempt + 1} error={type(exc).__name__}")
                            torch.cuda.empty_cache()
                            model.prepare_conditionals(str(REFERENCE), exaggeration=0.50)
                            canonical_state = conditioning_state(model)
                            log(f"Chatterbox conditioning reset job={item['id']} part={number} state={canonical_state}")
                            continue
                        if warnings.reason:
                            log(f"Chatterbox generation anomaly job={item['id']} part={number} attempt={attempt + 1} reason={warnings.reason}")
                            del wav
                            torch.cuda.empty_cache()
                            model.prepare_conditionals(str(REFERENCE), exaggeration=0.50)
                            canonical_state = conditioning_state(model)
                            log(f"Chatterbox conditioning reset job={item['id']} part={number} state={canonical_state}")
                            continue
                        wav, leading_silence, trailing_silence = trim_edge_silence(wav, model.sr)
                        rejected, reason, duration = suspicious_audio(wav, model.sr, sentence)
                        if rejected:
                            log(f"Chatterbox artifact rejected job={item['id']} part={number} attempt={attempt + 1} duration={duration:.2f}s reason={reason}")
                            del wav
                            torch.cuda.empty_cache()
                            model.prepare_conditionals(str(REFERENCE), exaggeration=0.50)
                            canonical_state = conditioning_state(model)
                            log(f"Chatterbox conditioning reset job={item['id']} part={number} state={canonical_state}")
                            continue
                        accepted = (wav, began, duration)
                        break
                    if accepted is None:
                        model.prepare_conditionals(str(REFERENCE), exaggeration=0.50)
                        canonical_state = conditioning_state(model)
                        log(f"Chatterbox chunk skipped job={item['id']} part={number} engine=chatterbox retries=2 skip=true supertonic_called=false state={canonical_state}")
                        continue
                    wav, began, duration = accepted
                    state_after = conditioning_state(model)
                    log(f"Chatterbox state job={item['id']} part={number} engine=chatterbox retry={attempt} reference={REFERENCE} before={canonical_state} after={state_after}")
                    output = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                    output.close()
                    torchaudio.save(output.name, wav, model.sr)
                    generated = time.monotonic()
                    log(f"Chatterbox generate done job={item['id']} part={number} generation={generated-began:.3f}s audio={duration:.2f}s trimmed_leading={leading_silence:.3f}s trimmed_trailing={trailing_silence:.3f}s")
                    ready.put((item["id"], number, output.name, item["queued_ns"], generated, duration))
                path.unlink(missing_ok=True)
            time.sleep(0.05)


if __name__ == "__main__":
    try:
        run()
    except (BlockingIOError, KeyboardInterrupt):
        pass
    except Exception as exc:
        STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
        log(f"Chatterbox failed: {type(exc).__name__}; Supertonic disabled")
