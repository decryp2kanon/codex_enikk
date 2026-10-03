#!/usr/bin/env python3
"""Persistent Chatterbox C2 worker using CUDA when available."""

import fcntl
import importlib.util
import json
import logging
import os
from pathlib import Path
import queue
import re
import signal
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
_notify_spec = importlib.util.spec_from_file_location('engine_notify', ROOT / 'yuki-codex-notify.py')
notify = importlib.util.module_from_spec(_notify_spec)
_notify_spec.loader.exec_module(notify)
STATE = Path(os.environ.get("CODEX_ENIKK_TTS_STATE", Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "codex_enikk" / "tts"))
JOBS = STATE / "jobs"
# The final SUPER-CLEAN C2 reference is configured here (and may be overridden
# explicitly for another installation without duplicating it in the notifier).
REFERENCE = Path(os.environ.get("CODEX_ENIKK_CHATTERBOX_REFERENCE", Path.home() / "Apps/chatterbox-yuki/yuki_super-clean.wav"))
KOREAN_TECH = {
    "SUPER-CLEAN": "슈퍼 클린", "Chatterbox": "채터박스", "Codex": "코덱스",
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


def normalize_paths(text):
    """TTS-only filesystem descriptions, before splitting or number conversion.

    Return explicit replacements as well as text; never mutate the source job.
    URLs and ordinary slash expressions cannot start a match.
    """
    extensions = {
        'py': '파이썬 파일', 'md': '마크다운 파일', 'sh': '셸 스크립트',
        'json': '제이슨 파일', 'txt': '텍스트 파일', 'wav': '웨이브 오디오 파일',
        'log': '로그 파일', 'toml': '톰엘 설정 파일', 'yaml': '야믈 설정 파일',
        'yml': '야믈 설정 파일', 'cpp': '씨 플러스 플러스 소스 파일',
        'cc': '씨 플러스 플러스 소스 파일', 'h': '헤더 파일', 'hpp': '헤더 파일',
        'rs': '러스트 소스 파일', 'js': '자바스크립트 파일', 'ts': '타입스크립트 파일',
    }
    names = {'yuki': '유키', 'engine': '엔진', 'enikk': '에닉', 'readme': '리드미',
             'install': '인스톨', 'license': '라이선스', 'changelog': '체인지로그',
             'makefile': '메이크파일', 'test': '테스트', 'output': '아웃풋',
             'approval': '승인', 'marker': '표시'}
    # Delimited paths may contain Korean filenames. Attached Korean particles
    # after a known extension are prose, not part of that filename.
    pattern = re.compile(
        r"(?<![\w/:.])(?P<path>`?(?:/(?:home|tmp|usr|etc|var|opt)/|~/|\.\.?/)[^\s`\"'<>()[\]{}]+`?)"
        r"(?:\s+(?:파일|경로)(?P<particle>에서|으로|을|를|은|는|이|가|에|로)?(?=\s|[.!?,]|$))?")
    records = []

    def replace(match):
        raw = match.group('path')
        path = raw.strip('`')
        tail = ''
        while path and path[-1] in '.,!?:;':
            tail = path[-1] + tail
            path = path[:-1]
        attached = re.search(r'\.(?:' + '|'.join(extensions) + r')(을|를|은|는|이|가|에서|에|로|으로)$', path, re.I)
        if attached:
            tail = attached.group(1) + tail
            path = path[:-len(attached.group(1))]
        basename = path.rstrip('/').rsplit('/', 1)[-1]
        stem, dot, extension = basename.rpartition('.')
        if not dot:
            stem, extension = basename, ''
        description = extensions.get(extension.lower(), '파일')
        # Machine identifiers are intentionally described, not spelled out.
        machine = (len(stem) > 48 or bool(re.fullmatch(r'[0-9a-fA-F-]{16,}', stem))
                   or any(len(token) > 20 for token in re.split(r'[-_.]', stem)))
        spoken = '' if machine else ' '.join(names.get(token.lower(), token)
                                             for token in re.split(r'[-_.]+', stem) if token)
        spoken = korean_pronunciation(spoken) if spoken else ''
        result = ' '.join(filter(None, (spoken, description, '경로')))
        tail += match.group('particle') or ''
        tail = re.sub(r'^(을|이|은|으로)', lambda m: {'을': '를', '이': '가', '은': '는', '으로': '로'}[m[0]], tail)
        records.append({'original': raw, 'description': result, 'span': match.span(),
                        'replaced_text': match.group(0), 'spoken': result + tail})
        return result + tail

    normalized = pattern.sub(replace, text)
    return normalized, records


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
        # Do not leave a short sentence tail (for example, "해.") as its own
        # generation. Chatterbox frequently reports long_tail for these tiny
        # fragments. Join it to the preceding chunk, or rebalance that pair
        # when both resulting chunks remain above the minimum length.
        if chunks and len(current) < minimum and len(chunks[-1]) + 1 + len(current) <= maximum:
            joined = f"{chunks[-1]} {current}"
            words = joined.split()
            choices = []
            for index in range(1, len(words)):
                left, right = " ".join(words[:index]), " ".join(words[index:])
                # Rebalance only when neither side becomes a short fragment.
                if not (minimum <= len(left) <= maximum and minimum <= len(right) <= maximum):
                    continue
                boundary = bool(re.search(r"[,;:.!?。！？]$|(?:으며|면서|지만|며|하고|이고|하며|때문에)$",
                                          words[index - 1]))
                choices.append((not boundary, abs(len(left) - len(right)), index, left, right))
            if choices:
                _, _, _, left, right = min(choices)
                chunks[-1:] = [left, right]
            else:
                chunks[-1] = joined
        else:
            chunks.append(current)
    return chunks


def recovery_clauses(text):
    """One balanced word-boundary split; prefer punctuation or Korean clauses.

    No punctuation is removed and no token is divided. This is used only after
    two internal long-tail rejections, never on the ordinary scheduler path.
    """
    words = text.split()
    choices = []
    for index in range(1, len(words)):
        left, right = " ".join(words[:index]), " ".join(words[index:])
        # A complete long URL/filename stays one token. Permit a short
        # two-word connective clause, but never a tiny single-word fragment.
        if any(len(part) < (6 if len(part.split()) >= 2 else 8) for part in (left, right)):
            continue
        clause = bool(re.search(r"[,;:]$|(?:으며|면서|지만|며|하고|이고|하며|때문에)$", words[index - 1]))
        choices.append((not clause, abs(len(left) - len(right)), index, left, right))
    if not choices:
        return []
    _, _, _, left, right = min(choices)
    parts = [left, right]
    assert [word for part in parts for word in part.split()] == words
    return parts


def recover_generation(text, attempt, reset, join, trace, valid=lambda: True):
    """At most 2 original + 2 attempts per each of 2 depth-1 clauses.

    Publish nothing until every clause succeeds. The original delivery index
    owns one assembled WAV, so crash recovery and playback ordering stay intact.
    """
    def twice(segment, depth, clause):
        reasons = []
        for number in (1, 2):
            if not valid():
                return None, ['STALE']
            payload, reason = attempt(segment, number, depth, clause)
            if not valid():
                return None, ['STALE']
            if payload is not None:
                return payload, reasons
            reasons.append(reason)
            if valid():
                reset()
        return None, reasons

    payload, reasons = twice(text, 0, 0)
    if payload is not None:
        return payload, None
    # Exception / waveform failures retain their existing explicit failure policy.
    parts = recovery_clauses(text) if reasons == ["internal_long_tail"] * 2 else []
    if not parts:
        return None, "; ".join(reasons)
    trace(f"recovery_split depth=1 original_tokens={len(text.split())} clauses={parts!r} lost=0")
    recovered = []
    for index, part in enumerate(parts):
        payload, failures = twice(part, 1, index)
        if payload is None:
            return None, f"recovery clause={index}: {'; '.join(failures)}"
        recovered.append(payload)
    trace("recovery_accepted depth=1 clauses=2 lost=0")
    return join(recovered), None


class GenerationWarnings(logging.Handler):
    """Capture analyzer signals; token repetition alone remains informational."""
    def __init__(self):
        super().__init__()
        self.reason = None
        self.signals = set()

    def emit(self, record):
        message = record.getMessage()
        for name in ("long_tail", "alignment_repetition", "token_repetition"):
            if re.search(rf"{name}=(?:tensor\()?True\b", message):
                self.signals.add(name)
        if "forcing EOS" in message:
            self.signals.add("forced_eos")
        if "long_tail" in self.signals:
            self.reason = "internal_long_tail"
        elif "alignment_repetition" in self.signals:
            self.reason = "internal_alignment_repetition"


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


class DeliveryJob:
    """Persist chunk acknowledgements; a queued WAV is not delivered yet."""
    def __init__(self, path, item, parts):
        self.path = path
        self.item = item
        self.lock = threading.Lock()
        delivery = item.setdefault("delivery", {"parts": parts, "terminal": {}})
        self.parts = delivery["parts"]
        self.terminal = delivery["terminal"]
        self.complete = False
        self._save()
        self._cleanup_if_complete()

    def _save(self):
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8",
                                             dir=self.path.parent, prefix=".delivery-",
                                             delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(self.item, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self._sync_directory()
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def _sync_directory(self):
        fd = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _cleanup_if_complete(self):
        if all(str(i) in self.terminal for i in range(len(self.parts))):
            if any(status == 'STALE' for status in self.terminal.values()):
                os.replace(self.path, self.path.with_name('.stale-' + self.path.name))
                log(f"Chatterbox job_stale job={self.item['id']}")
            elif any(status != "PLAYED" for status in self.terminal.values()):
                failed_path = self.path.with_name(".failed-" + self.path.name)
                os.replace(self.path, failed_path)
                log(f"Chatterbox job_failed job={self.item['id']} recoverable={failed_path}")
            else:
                if self.item.get("stream_key"):
                    # Durable receipt prevents a stream outbox replay from speaking twice.
                    os.replace(self.path, self.path.with_name(".played-" + self.path.name))
                else:
                    self.path.unlink(missing_ok=True)
                log(f"Chatterbox job_cleanup job={self.item['id']} final=PLAYED")
            self._sync_directory()
            self.complete = True

    def finish(self, number, status, reason=None):
        with self.lock:
            self.terminal[str(number)] = 'STALE' if status == 'stale' else ("PLAYED" if status == "played" else "FAILED_EXPLICITLY")
            if status != "played":
                self.item["delivery"].setdefault("failures", {})[str(number)] = reason or status
            self._save()
            self._cleanup_if_complete()


def play_audio(job, path):
    # Serialize the last validity check and spawn with the user barrier commit.
    with notify.epoch_lock(STATE):
        if not notify.epoch_valid(job.item, STATE):
            return 'stale'
        audio_env = os.environ.copy()
        audio_env.setdefault('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')
        audio_env.setdefault('PULSE_SERVER', f'unix:/run/user/{os.getuid()}/pulse/native')
        child = subprocess.Popen(['/usr/bin/paplay', path], env=audio_env,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        while child.poll() is None:
            if not notify.epoch_valid(job.item, STATE):
                child.terminate()  # Only this worker's exact playback child.
                try:
                    child.wait(timeout=.2)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait()
                log(f"Chatterbox playback_stopped job={job.item['id']} epoch={job.item.get('epoch')} monotonic_ns={time.monotonic_ns()}")
                return 'stale'
            time.sleep(.02)
        if not notify.epoch_valid(job.item, STATE):
            return 'stale'
        if child.returncode:
            raise subprocess.CalledProcessError(child.returncode, child.args)
        return 'played'
    finally:
        if child.poll() is None:
            child.terminate()
            try: child.wait(timeout=.2)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()


def playback(ready):
    previous_end = None
    while True:
        entry = ready.get()
        if entry is None:  # Graceful sentinel, also used by CPU-only tests.
            ready.task_done()
            return
        job, number, path, queued_ns, generated, audio_duration = entry
        job_id = job.item["id"]
        status = "playback_failed"
        failure_reason = None
        try:
            if not notify.epoch_valid(job.item, STATE):
                status = 'stale'
                continue
            started = time.monotonic()
            gap = 0.0 if previous_end is None else max(0.0, started - previous_end)
            log(f"Chatterbox playback start job={job_id} part={number} queue_wait={started-generated:.3f}s previous_gap={gap:.3f}s audio={audio_duration:.2f}s monotonic={started:.6f}")
            if number == 0:
                log(f"Chatterbox first audio latency {(time.monotonic_ns()-queued_ns)/1e9:.3f}s job={job_id}")
            status = play_audio(job, path)
        except Exception as exc:
            failure_reason = f"{type(exc).__name__}: {exc}"
            # An item failure must not terminate the queue consumer.
            try:
                log(f"Chatterbox playback_failed job={job_id} part={number} error={type(exc).__name__} returncode={getattr(exc, 'returncode', None)}")
            except Exception:
                pass
        finally:
            previous_end = time.monotonic()
            try:
                job.finish(number, status, failure_reason)
                log(f"Chatterbox playback done job={job_id} part={number} final={status} monotonic={previous_end:.6f}")
            except Exception as exc:
                # Keep the source job for restart recovery if acknowledgement fails.
                try:
                    log(f"Chatterbox acknowledgement_failed job={job_id} part={number} error={type(exc).__name__}")
                except Exception:
                    pass
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass
            ready.task_done()


def owner_alive(owner):
    try:
        pid, born = owner.split(':')
        fields = Path(f'/proc/{int(pid)}/stat').read_text().rsplit(')', 1)[1].split()
        return fields[0] not in ('Z', 'X') and fields[19] == born
    except (OSError, ValueError, IndexError):
        return False


def discard_stale_job(path, item):
    current_run = os.environ.get('CODEX_ENIKK_TTS_RUN_ID')
    if (current_run and item.get('run_id') != current_run) or not notify.epoch_valid(item, STATE):
        path.rename(path.with_name('.stale-' + path.name))
        log(f"Chatterbox stale_discard job={item.get('id')} run_id={item.get('run_id')}")
        return True
    return False


def watch_owner(owner):
    while owner_alive(owner) and not (STATE / 'cancelled').exists():
        time.sleep(.1)
    # ensure_engine starts a private session; its group contains only this worker
    # and its aplay child. Kill both, including playback after a wrapper crash.
    if os.getpgrp() == os.getpid():
        os.killpg(os.getpgrp(), signal.SIGTERM)
    else:
        os.kill(os.getpid(), signal.SIGTERM)


def run():
    STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
    JOBS.mkdir(mode=0o700, parents=True, exist_ok=True)
    if not REFERENCE.is_file():
        raise FileNotFoundError(REFERENCE)
    with (STATE / "engine.lock").open("a+b") as lock, Path(os.environ.get('CODEX_ENIKK_TTS_MODEL_LOCK', STATE / 'model.lock')).open('a+b') as model_lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        owner = os.environ.get('CODEX_ENIKK_TTS_OWNER')
        if owner:
            (STATE / 'worker.json').write_text(json.dumps({'pid': os.getpid(),
                'born': Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]}))
            threading.Thread(target=watch_owner, args=(owner,), daemon=True).start()
        # Per-run launch lock above; one model across all run namespaces below.
        log(f"Chatterbox waiting_model_lock run_id={os.environ.get('CODEX_ENIKK_TTS_RUN_ID')}")
        fcntl.flock(model_lock, fcntl.LOCK_EX)
        started = time.monotonic()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        log(f"loading Chatterbox multilingual model on {device}; first run may download model files")
        model = ChatterboxMultilingualTTS.from_pretrained(device=device)
        model.prepare_conditionals(str(REFERENCE), exaggeration=0.50)
        canonical_state = conditioning_state(model)
        log(f"Chatterbox C2 ready load_time={time.monotonic()-started:.3f}s reference={REFERENCE} state={canonical_state}")
        ready_info = {'pid': os.getpid(), 'born': Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19],
                      'run_id': os.environ.get('CODEX_ENIKK_TTS_RUN_ID')}
        (STATE / 'model-ready.tmp').write_text(json.dumps(ready_info))
        os.replace(STATE / 'model-ready.tmp', STATE / 'model-ready.json')
        ready = queue.Queue()
        threading.Thread(target=playback, args=(ready,), daemon=True).start()
        in_flight = {}
        while True:
            in_flight = {path: job for path, job in in_flight.items() if not job.complete}
            for path in sorted(JOBS.iterdir()):
                if path in in_flight or not path.is_file() or path.name.startswith("."):
                    continue
                item = json.loads(path.read_text(encoding="utf-8"))
                if discard_stale_job(path, item):
                    continue
                log(f"Chatterbox job_visible job={item['id']} monotonic_ns={time.monotonic_ns()}")
                preprocessing = time.monotonic()
                spoken_text, path_records = normalize_paths(item["text"])
                for record in path_records:
                    log(f"Chatterbox job={item['id']} PATH_NORMALIZED_EXPLICITLY original={record['original']!r} description={record['description']!r}")
                if path_records:
                    natural = item['text']
                    for record in reversed(path_records):
                        start, end = record['span']
                        natural = natural[:start] + natural[end:]
                    log(f"Chatterbox job={item['id']} path_accounting natural_text_tokens={len(natural.split())} path_tokens={len(path_records)} normalized_path_descriptions={len(path_records)}")
                originals = speech_chunks(spoken_text)
                candidates = [korean_pronunciation(part) for part in originals]
                parts = []
                for index, candidate in enumerate(candidates):
                    reason = segment_drop_reason(candidate)
                    log(f"Chatterbox segment job={item['id']} part={len(parts) if not reason else 'none'} source_part={index} original={originals[index]!r} repr={candidate!r} dropped={bool(reason)} reason={reason or '-'}")
                    if not reason:
                        parts.append(candidate.strip())
                log(f"Chatterbox accepted job={item['id']} normalized={item['text']!r} segments={len(parts)} preprocessing={time.monotonic()-preprocessing:.6f}s")
                job = DeliveryJob(path, item, parts)
                in_flight[path] = job
                for number, sentence in enumerate(job.parts):
                    if str(number) in job.terminal:
                        continue
                    if not notify.epoch_valid(item, STATE):
                        job.finish(number, 'stale')
                        continue
                    # Final defense at the synthesis boundary, independent of the splitter.
                    reason = segment_drop_reason(sentence)
                    if reason:
                        log(f"Chatterbox pre-generate drop job={item['id']} part={number} repr={sentence!r} reason={reason}")
                        job.finish(number, "formatting_skipped")
                        continue
                    began = time.monotonic()
                    def trace(message):
                        log(f"Chatterbox job={item['id']} part={number} monotonic={time.monotonic():.6f} {message}")

                    def reset():
                        if not notify.epoch_valid(item, STATE):
                            return
                        reset_start = time.monotonic()
                        torch.cuda.empty_cache()
                        model.prepare_conditionals(str(REFERENCE), exaggeration=0.50)
                        trace(f"conditioning_reset duration={time.monotonic()-reset_start:.6f}s reference={REFERENCE} state={conditioning_state(model)}")

                    def attempt(segment, attempt_number, depth, clause):
                        with notify.epoch_lock(STATE):
                            if not notify.epoch_valid(item, STATE):
                                return None, 'STALE'
                            started = time.monotonic()
                            trace(f"generate_start attempt={attempt_number} depth={depth} clause={clause} text_len={len(segment)} tokens={len(segment.split())} text={segment!r}")
                        warnings = GenerationWarnings()
                        anomaly_logger = logging.getLogger("chatterbox.models.t3.inference.alignment_stream_analyzer")
                        anomaly_logger.addHandler(warnings)
                        try:
                            wav = model.generate(segment, language_id="ko", exaggeration=0.50,
                                                 cfg_weight=0.70).cpu()
                        except Exception as exc:
                            reason = f"generate: {type(exc).__name__}: {exc}"
                            trace(f"generate_rejected attempt={attempt_number} depth={depth} duration={time.monotonic()-started:.6f}s reason={reason!r}")
                            return None, reason
                        finally:
                            anomaly_logger.removeHandler(warnings)
                        if not notify.epoch_valid(item, STATE):
                            return None, 'STALE'
                        raw_duration = wav.shape[-1] / model.sr
                        wav, leading, trailing = trim_edge_silence(wav, model.sr)
                        rejected, waveform_reason, duration = suspicious_audio(wav, model.sr, segment)
                        reason = warnings.reason or (f"waveform: {waveform_reason}" if rejected else None)
                        trace(f"generate_end attempt={attempt_number} depth={depth} clause={clause} duration={time.monotonic()-started:.6f}s raw_audio={raw_duration:.6f}s audio={duration:.6f}s sr={model.sr} leading={leading:.6f}s trailing={trailing:.6f}s seconds_per_char={duration/max(1,len(segment)):.6f} analyzer={sorted(warnings.signals)!r} waveform_rejected={rejected} waveform_reason={waveform_reason!r} reject_reason={reason!r}")
                        if reason:
                            # Opt-in bounded diagnostics outside the repository; never played.
                            debug = os.environ.get("CODEX_ENIKK_TTS_REJECT_DIR")
                            if debug:
                                try:
                                    directory = Path(debug)
                                    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
                                    if len(list(directory.glob("*.wav"))) < 24:
                                        torchaudio.save(str(directory / f"{item['id']}-{number}-{depth}-{clause}-{attempt_number}-{time.monotonic_ns()}.wav"), wav, model.sr)
                                except Exception as exc:
                                    trace(f"rejected_audio_diagnostic_failed error={type(exc).__name__}")
                            return None, reason
                        return (wav, duration), None

                    accepted, last_failure = recover_generation(
                        sentence, attempt, reset,
                        lambda pieces: (torch.cat([piece[0] for piece in pieces], dim=-1),
                                        sum(piece[1] for piece in pieces)), trace,
                        valid=lambda: notify.epoch_valid(item, STATE))
                    if not notify.epoch_valid(item, STATE):
                        job.finish(number, 'stale')
                        continue
                    if accepted is None:
                        trace(f"chunk_failed engine=chatterbox final=FAILED_EXPLICITLY reason={last_failure!r}")
                        job.finish(number, "generation_failed", last_failure)
                        continue
                    wav, duration = accepted
                    output = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                    output.close()
                    torchaudio.save(output.name, wav, model.sr)
                    generated = time.monotonic()
                    log(f"Chatterbox generate done job={item['id']} part={number} generation={generated-began:.3f}s audio={duration:.2f}s")
                    with notify.epoch_lock(STATE):
                        if not notify.epoch_valid(item, STATE):
                            Path(output.name).unlink(missing_ok=True)
                            job.finish(number, 'stale')
                            continue
                        ready.put((job, number, output.name, item["queued_ns"], generated, duration))
                    log(f"Chatterbox playback queued job={item['id']} part={number} final=queued")
            time.sleep(0.05)


if __name__ == "__main__":
    try:
        run()
    except (BlockingIOError, KeyboardInterrupt):
        pass
    except Exception as exc:
        STATE.mkdir(mode=0o700, parents=True, exist_ok=True)
        log(f"Chatterbox failed: {type(exc).__name__}: {exc}; alternate TTS disabled")
