# Chatterbox TTS

`codex_enikk` reads completed CODEX progress and final messages with a persistent
Chatterbox worker. User input, reasoning, tool output, code blocks, and raw logs are excluded.

The external runtime defaults to `~/Apps/chatterbox-yuki` and requires:

- `.venv/bin/python` with `chatterbox-tts==0.1.7`
- `yuki_super-clean.wav`
- ALSA `aplay`

The fixed voice is SUPER-CLEAN C2: Korean, exaggeration `0.50`, and CFG weight `0.70`.
Failures reset conditioning and retry once. After two failed generation attempts, the chunk
is recorded as FAILED_EXPLICITLY with its text and reason; other chunks continue.
`setup-tts.sh` creates the venv and installs dependencies. CUDA is selected when available;
otherwise the worker uses CPU. Model files are downloaded by Chatterbox on first use and kept
in its normal user cache.

The bundled SUPER-CLEAN reference is installed automatically. To explicitly replace it with
another authorized reference, use the advanced override:

```bash
sudo env CODEX_ENIKK_CHATTERBOX_REFERENCE_SOURCE=/path/yuki_super-clean.wav ./install.sh
```

The installer validates the WAV with `torchaudio`. Updates preserve the existing venv, model
cache, and reference unless the override is explicitly supplied.
Set `CODEX_ENIKK_TTS=0` to disable TTS or `CODEX_ENIKK_CHATTERBOX_HOME` to select another
external Chatterbox directory. TTS failure never prevents the Codex wrapper from running.

Playback acknowledgements are saved atomically per chunk. Jobs are removed only after all
chunks are PLAYED. Playback errors are isolated to the item and do not stop the consumer.
Jobs containing explicit failures are retained as `.failed-*` files in the TTS state `jobs/`
directory, including the original message, chunk text, and failure reasons. They are parked
as diagnostics, not automatically retried forever. Each wrapper launch creates a private
`runs/run-*` namespace for jobs, receipts and stream outboxes. A new launch never imports
old-run jobs, including unfinished generations, failed jobs or an interrupted old turn.
Within the same live run, a worker restart can resume unacknowledged chunks; a crash between
audible playback and acknowledgement can still repeat that chunk in that same run.

Normal exit marks the run cancelled. A worker watchdog validates its owner's PID and process
start time; owner death or cancellation terminates the worker's private process group,
including `aplay`. Startup cancels prior runs and stops their identity-checked worker groups.
Old files remain for diagnosis but are excluded from all new-run delivery. One global model
lock prevents simultaneous GPU models, while each run has its own launch lock.

## Sentence streaming (Codex 0.158.0 / 0.160.0)

The wrapper starts a private supported Codex app-server and a sentence observer
by default, retaining the native TUI. Set `CODEX_ENIKK_STREAMING_TTS=0`
for standalone `--no-daemon` and the completed-message watcher. Other
Codex versions, missing dependencies, or startup failures use that existing path.
Setup pins `websocket-client==1.9.0` in the existing Chatterbox venv. Install/update
copy the helper; reference, existing venv and model cache are preserved.
Startup reports `tts_mode=starting`, then `streaming` or `legacy_fallback` with a reason.
The helper subscribes and records the historical turn baseline before opening the native TUI.
Model/reference loading runs concurrently: `streaming` means the observer is connected, while
`TTS_READY` in `notify.log` records audio readiness separately. Sentences arriving before audio
readiness are durably queued in the current run and consumed in order by its worker. They are
never replayed in a later run. A model readiness timeout logs `TTS_READY_FAILED` and preserves
current-run pending content without blocking Codex; server/helper startup failure still uses
the standalone path. Historical ignored turn IDs are saved once, without per-item checkpoints. Runtime mode is also saved
in the current run's `runtime.log`; timings and subscription details are in `notify.log`.

The private server owns the existing unrestricted permission policy because
remote resume rejects CLI permission overrides. Its `notify=[]` override disables
the global completed-answer hook; the JSONL watcher is not started in remote mode.
Standalone fallback also overrides the global notify hook so only its scoped watcher submits.
This gives each item one TTS owner without changing the user's global configuration.
The helper observes the launch thread only; switching threads inside the TUI is
not yet validated. Server/helper lifecycle is managed by the wrapper. A startup
failure falls back before launching the TUI, after stopping the candidate helper.
A helper failure after attachment does not start a second legacy TTS reader.

Complete sentences are durably published before final completion. On reconnect,
an active item may be missing from `thread/resume`. Its offsetless deltas must not
be spliced across that gap: the affected turn is reconciled using authoritative
completed items/snapshots. Only this disconnected interval waits for full text;
ordinary connected turns continue sentence streaming. On termination, the helper
gets a bounded final snapshot drain while the server is still alive. Interrupted
unfinished text is not flushed. A changed consumed prefix fails closed and retains
the conflict for review.

Korean prose ending in sentence punctuation at the end of a delta is emitted
immediately, without waiting for whitespace, another sentence, or item completion.
Each completed sentence owns a separate job. Ambiguous ASCII periods still need
lookahead to protect decimals, domains and filenames; Markdown code/link interiors
remain protected. Newlines alone do not complete unfinished prose.
The five-second isolation fixture verifies that the first job exists on disk
before a second sentence arrives. Logs expose sentence completion/flush, durable
job creation, worker visibility, generation and playback monotonic times. A busy
worker or initial model load can delay generation even after immediate submission.

### Bounded Chatterbox recovery

Normal chunks retain the existing scheduler, SUPER-CLEAN C2 parameters, numeric
pronunciation and audio guards. Two internal long-tail rejections of the same
chunk permit one split into two clauses at complete word boundaries. Punctuation,
URLs, filenames, numbers and technical tokens are not cut or discarded. Original
and recovery whitespace-token sequences must match exactly. Each clause has at
most two attempts; maximum depth is one and total generation attempts are at most
six. Exceptions and waveform rejections retain the existing two-attempt policy.
Each rejection resets conditioning from the same reference.

All recovery clauses must pass before their WAVs are assembled in order and
queued as the original delivery chunk. This retains existing crash/acknowledgement
semantics, but retries and assembly can produce multi-second gaps. Exhausted or
unsplittable chunks remain `FAILED_EXPLICITLY` in recoverable `.failed-*` records;
these are **not** successful delivery and are not retried forever.

Diagnostics distinguish internal long-tail/alignment warnings from waveform guard
rejections and record monotonic generation/reset/playback timings. Token repetition
alone is informational. `CODEX_ENIKK_TTS_REJECT_DIR` optionally retains up to 24
rejected WAVs for diagnosis; use a private directory outside the repository.
Rejected audio is never queued. A passed waveform check alone does not establish
that an internal analyzer warning is a false positive.

### Release status

Live natural-language runs demonstrated 12/12 playback, including bounded recovery.
Live reconnect testing exposed and fixed missing delta concatenation; wrapper
exit testing exposed and fixed the final-item drain race. The global notify hook
also needed disabling to prevent whole-answer replay beside streaming.
The formerly failing filename is now described before synthesis (see below).
Two live 12-sentence runs containing four filesystem paths each delivered 24/24
chunks, with no failures, duplicates or ordering errors. Median gaps were 0.015s;
maximum gaps were 0.155s and 0.017s. Audio began 3.615s and 3.279s before final
completion. However, the normalized former failure fixture still triggered one
internal long-tail rejection before its successful retry. Such bounded recovery
is a successful delivery, not a release failure. Guards and retry limits remain
unchanged. Release accounting separates first-attempt, retry and depth-one split
successes; their sum must equal PLAYED. Final failures, missing/duplicate/out-of-order
delivery or playback of rejected audio fail the gate. These tests do not prove
universal no-loss generation or detect every speech-like acoustic artifact.

The immediate-sentence change also passed two 12-sentence native-wrapper runs
(24/24 PLAYED; 19 first-attempt successes, five successful retries, zero final
failures). In the warm default run, sentence completion to flush was 6.5ms,
flush to job publication 5.4ms, and publication to generation start 29.8ms.
Generation began before the second sentence completed. First playback was 5.377s
after response start and 6.432s before final completion. Median/max gaps were
0.011s/2.446s; bounded retries can still cause audible pauses.

### TTS-only filesystem path descriptions

Before the existing scheduler and numeric pronunciation, clear filesystem paths
(`~/`, `./`, `../`, `/home/`, `/tmp/`, `/usr/`, `/etc/`, `/var/`, `/opt/`) become
basename/extension descriptions. For example,
`/home/ak/git/codex_enikk/tts/yuki-chatterbox-engine.py` is spoken as
“유키 채터박스 엔진 파이썬 파일 경로”. Native TUI text and source jobs retain the
original path. URL and general slash expressions are not filesystem matches.
Backticks and surrounding punctuation are handled separately; an immediately
following redundant “파일/경로” noun is merged while preserving its particle.
Long machine identifiers use the extension description instead of spelling them.

Each replacement is logged as `PATH_NORMALIZED_EXPLICITLY`, with source and spoken
description. Path accounting records ordinary text tokens and replacement counts;
intentional path/noun rewriting is separate from accidental natural-text loss.
Unknown filename tokens retain existing pronunciation behavior; this is not a
general URL, code or transliteration system. Existing persisted delivery parts
are unchanged on resume. All artifact guards, conditioning reset and bounded
recovery still apply to the resulting speech text.

Stream checkpoints live in the existing TTS state's `streams/` directory.
Completed stream jobs retain `.played-*` receipts; failed jobs retain `.failed-*`
records under that run's `jobs/`. These prevent same-run outbox recovery from replaying acknowledged
jobs. They contain visible spoken text and are private runtime state, never
repository assets. Retention/pruning is not automated.
