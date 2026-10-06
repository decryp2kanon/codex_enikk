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
_tn_spec = importlib.util.spec_from_file_location('yuki_tn', ROOT / 'yuki-text-normalization.py')
tn = importlib.util.module_from_spec(_tn_spec)
_tn_spec.loader.exec_module(tn)


def log(message):
    with (STATE / "notify.log").open("a", encoding="utf-8") as out:
        out.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} {message}\n")


def conditioning_state(model):
    conds = model.conds
    speaker = conds.t3.speaker_emb
    return f"conds={id(conds)} speaker={id(speaker)} shape={tuple(speaker.shape)} mean={speaker.float().mean().item():.6f}"


def normalize_paths(text):
    """Delegate Yuki path descriptions; retain source replacement accounting."""
    return tn.overrides.normalize_paths(text)


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
        # fragments. Preserve the text by joining it to the preceding chunk.
        if chunks and len(current) < minimum and len(chunks[-1]) + 1 + len(current) <= maximum:
            chunks[-1] = f"{chunks[-1]} {current}"
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
        # Keep conditional/time clauses together when recovering a rejected
        # sentence, rather than balancing through the following noun phrase.
        clause = bool(re.search(r"[,;:]$|(?:으며|면서|지만|며|하고|이고|하며|때문에|으면|다면|라면|하면|되면)$", words[index - 1]))
        # '분석한 다음' ends a time clause; '다음 단계' starts a noun phrase.
        clause = clause or (index >= 2 and words[index - 1] == '다음'
                            and bool(re.search(r"(?:한|된|은)$", words[index - 2])))
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


def retire_alignment_hooks(model):
    """Release completed analyzers; each T3 call installs a fresh analyzer.

    Preserve all other framework/user hooks. Run only after generate returns or
    raises, while this worker remains the sole generation owner.
    """
    transformer = getattr(getattr(model, 't3', None), 'tfmr', None)
    for layer in getattr(transformer, 'layers', ()):
        attention = getattr(layer, 'self_attn', None)
        hooks = getattr(attention, '_forward_hooks', {})
        for key, hook in list(hooks.items()):
            if (getattr(hook, '__module__', '') ==
                    'chatterbox.models.t3.inference.alignment_stream_analyzer'
                    and getattr(hook, '__name__', '') == 'attention_forward_hook'):
                del hooks[key]


class GenerationWarnings(logging.Handler):
    """Capture signals; long-tail and token repetition remain informational."""
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
        if "alignment_repetition" in self.signals:
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


def soften_detached_tail(wav, sample_rate, completed_seconds):
    """Experimental stronger attenuation after a final-region quiet gap.

    Completion is only a lower-bound hint, not a word-end guarantee. Never
    shorten audio, change the prefix, or infer a boundary from low energy alone.
    """
    if sample_rate <= 0 or completed_seconds is None:
        return wav, {'reason': 'no_completion_hint'}
    total = wav.shape[-1]
    if not 0 <= completed_seconds < total / sample_rate:
        return wav, {'reason': 'invalid_completion_hint'}
    frame = max(1, round(sample_rate * .02))
    begin = max(0, total - round(sample_rate * 2.5))
    mono = wav[..., begin:].detach().float()
    if mono.ndim > 1:
        mono = mono.mean(dim=0)
    count = mono.numel() // frame
    if count < 20:
        return wav, {'reason': 'short_tail_window'}
    blocks = mono[:count * frame].reshape(count, frame)
    rms = blocks.square().mean(dim=1).sqrt().tolist()
    peaks = blocks.abs().amax(dim=1).tolist()
    quiet = [r <= .003 and p <= .02 for r, p in zip(rms, peaks)]
    runs = []
    start = None
    for i, is_quiet in enumerate(quiet + [False]):
        if is_quiet and start is None:
            start = i
        elif not is_quiet and start is not None:
            if i - start >= 3:
                runs.append((start, i))
            start = None
    skips = {'before_completion_hint': 0, 'extended_activity': 0,
             'strong_resumption': 0, 'unframed_activity': 0}
    for gap_start, gap_end in runs:
        # Allow a gap overlapping the final-text hint; the user-selected 170ms
        # advance below is experimental and can overlap the last spoken word.
        gap_sample = begin + gap_start * frame
        if (begin + gap_end * frame) / sample_rate < completed_seconds:
            skips['before_completion_hint'] += 1
            continue
        active = [i for i in range(gap_end, count) if not quiet[i]]
        if not active or (active[-1] - active[0] + 1) * frame > sample_rate * 1.8:
            skips['extended_activity'] += 1
            continue
        reference = max(rms[max(0, gap_start - 20):gap_start], default=0.)
        if reference < .004 or max(rms[i] for i in active) > min(.04, reference * 1.25):
            skips['strong_resumption'] += 1
            continue
        # Also reject a long burst hidden in the unframed remainder.
        if mono[count * frame:].numel() and mono[count * frame:].abs().max().item() > .02:
            skips['unframed_activity'] += 1
            continue
        cut = max(gap_sample + round(sample_rate * .12),
                  round((completed_seconds + .12) * sample_rate))
        # Listening-selected advance, applied only to accepted tail candidates.
        cut = max(0, cut - round(sample_rate * .170))
        if cut >= total:
            continue
        result = wav.clone()
        gain = torch.full((total - cut,), .001, dtype=result.dtype, device=result.device)
        ramp = min(round(sample_rate * .02), gain.numel())
        gain[:ramp] = torch.linspace(1., .001, ramp, dtype=result.dtype, device=result.device)
        result[..., cut:] *= gain
        return result, {'reason': 'detached_tail_after_quiet_gap',
                        'start_seconds': cut / sample_rate, 'attenuation_db': 60,
                        'advance_seconds': .170,
                        'completion_hint_seconds': completed_seconds,
                        'quiet_gap_seconds': (gap_end - gap_start) * frame / sample_rate}
    return wav, {'reason': 'ambiguous_or_no_detached_tail',
                 'completion_hint_seconds': completed_seconds, 'skip_counts': skips}


def optional_tail_softening(wav, sample_rate, model, warnings, leading, trace):
    """Fail open to original audio; diagnostic processing never causes retry."""
    if 'long_tail' not in warnings.signals:
        return wav
    trace('long_tail_detected')
    started = time.monotonic()
    try:
        analyzer = getattr(getattr(getattr(model, 't3', None), 'patched_model', None),
                           'alignment_stream_analyzer', None)
        frame = getattr(analyzer, 'completed_at', None)
        if analyzer is None or not getattr(analyzer, 'complete', False) or frame is None:
            completed = None
        else:
            # Installed multilingual S3 tokenizer uses 25Hz speech tokens.
            completed = max(0., float(frame) / 25. - leading)
        processed, record = soften_detached_tail(wav, sample_rate, completed)
        event = 'tail_trim_applied' if processed is not wav else 'tail_trim_skipped'
        trace(f'{event} processing_seconds={time.monotonic()-started:.6f} {record!r}')
        return processed
    except Exception as exc:
        trace(f'tail_trim_skipped reason=processing_exception error={type(exc).__name__}')
        return wav


def korean_pronunciation(text):
    """Normalize reading text with Yuki custom rules."""
    return tn.normalize(text)


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
        self.long_tail_parts = set()
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
    # Playback-only 1.25x tempo, preserving pitch: duration becomes 80%.
    # Conversion and playback are both cancellable, owned child processes.
    speed_path = None
    child = None

    def wait_child(phase):
        while child.poll() is None:
            if not notify.epoch_valid(job.item, STATE):
                child.terminate()
                try: child.wait(timeout=.2)
                except subprocess.TimeoutExpired:
                    child.kill(); child.wait()
                log(f"Chatterbox {phase}_stopped job={job.item['id']} epoch={job.item.get('epoch')} monotonic_ns={time.monotonic_ns()}")
                return 'stale'
            time.sleep(.02)
        if not notify.epoch_valid(job.item, STATE):
            return 'stale'
        if child.returncode:
            raise subprocess.CalledProcessError(child.returncode, child.args)
        return 'done'

    try:
        # Reject stale jobs before creating a file or launching ffmpeg.
        with notify.epoch_lock(STATE):
            if not notify.epoch_valid(job.item, STATE):
                return 'stale'
            with tempfile.NamedTemporaryFile(prefix='yuki-1.25x-', suffix='.wav', delete=False) as tmp:
                speed_path = tmp.name
            child = subprocess.Popen([
                '/usr/bin/ffmpeg', '-nostdin', '-y', '-hide_banner', '-loglevel', 'error',
                '-i', path, '-filter:a', 'atempo=1.25', speed_path
            ], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if wait_child('tempo_conversion') == 'stale':
            return 'stale'

        with notify.epoch_lock(STATE):
            if not notify.epoch_valid(job.item, STATE):
                return 'stale'
            audio_env = os.environ.copy()
            audio_env.setdefault('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')
            audio_env.setdefault('PULSE_SERVER', f'unix:/run/user/{os.getuid()}/pulse/native')
            child = subprocess.Popen(['/usr/bin/paplay', speed_path], env=audio_env,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return 'stale' if wait_child('playback') == 'stale' else 'played'
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try: child.wait(timeout=.2)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait()
        if speed_path:
            Path(speed_path).unlink(missing_ok=True)


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
            if status == 'played' and number in getattr(job, 'long_tail_parts', set()):
                log(f"Chatterbox long_tail_detected_but_played job={job_id} part={number}")
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
        tn.initialize()
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
                try:
                    normalized_text = korean_pronunciation(spoken_text)
                except Exception as error:
                    failed = DeliveryJob(path, item, [item['text']])
                    for number in range(len(failed.parts)):
                        if str(number) not in failed.terminal:
                            failed.finish(number, 'failed', 'normalization: ' + str(error))
                    log(f"Chatterbox normalization_failed job={item['id']} error={error!r}")
                    continue
                originals = speech_chunks(normalized_text)
                candidates = originals
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
                            retire_alignment_hooks(model)
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
                        wav = optional_tail_softening(wav, model.sr, model, warnings, leading, trace)
                        if 'long_tail' in warnings.signals:
                            job.long_tail_parts.add(number)
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
