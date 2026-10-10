# Chatterbox TTS — independent service


The core owns Codex TUI/app-server, trigger, mirror and continuity checks.
Voice synthesis runs under an independent systemd user service. Neither component
starts, stops or updates the other. Core requires system Python 3.10+ and
`python3-websocket`; it does not use the Chatterbox virtual environment.

## Install and control

From the source repository, run `PREFIX="$HOME/.local" ./install-tts.sh`.
This installs only voice code and registers a stopped user service. It does not
download models, alter the existing venv/reference, or start Codex.

```bash
codex_enikk
enikk_tts start
enikk_tts status
enikk_tts stop
enikk_tts restart
enikk_tts update "$HOME/git/codex_enikk"
enikk_tts restart
enikk_tts rollback RELEASE_ID
enikk_tts restart
journalctl --user -u enikk-tts.service
```

Voice dependencies remain in `~/Apps/chatterbox-yuki/.venv`, with the existing
`yuki_super-clean.wav` reference, cached model and PulseAudio tools.
No installer here calls the legacy `tts/setup-tts.sh`.
`codex_enikk --tts-debug` prints the independent status/log commands; it no longer
starts or owns a voice worker.

## Ownership and release boundary

Core: `~/.local/lib/codex_enikk`, `~/.local/state/codex_enikk`.
Voice: `~/.local/lib/enikk_tts/releases/<hash>` selected by atomic `active` symlink,
`~/.local/state/enikk_tts`. The running service resolves its release directory
once, so later updates cannot mix engine modules. Release manifests, compile and
import checks precede selection. Failed staging leaves the selected release intact.
Old releases and logs are retained. Update/rollback select files only; restart
explicitly applies them. A failed model start leaves core running and is reported
by status; rollback never restores queued speech.

Control operations share a local flock. systemd owns the entire voice cgroup
(`KillMode=control-group`, no automatic restart). Repeated start is idempotent.
Explicit stop stays stopped. No core process is signalled by voice control.
The legacy education supervisor cannot restart core; automatic education is paused.

See [the complete lifecycle and IPC contract](../docs/tts-separation.md).

### Bounded Chatterbox recovery

Normal chunks retain the existing scheduler, SUPER-CLEAN C2 parameters, numeric
pronunciation and waveform guards. Internal long-tail signals are informational:
they are logged but do not reject an otherwise accepted waveform or trigger retry.
Alignment repetition, generation exceptions and waveform rejection still use
their existing failure policy. Legacy recovery supports two internal long-tail rejections of the same
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
and internal long-tail alone are informational. `CODEX_ENIKK_TTS_REJECT_DIR` optionally retains up to 24
rejected WAVs for diagnosis; use a private directory outside the repository.
Rejected audio is never queued. A passed waveform check alone does not establish
that an internal analyzer warning is a false positive.

Experimental detached-tail attenuation applies only after accepted generation
with a long-tail warning. The existing analyzer's completion frame supplies only
a lower-bound hint (25Hz S3 tokens), not an exact spoken-word endpoint. Only the
last 2.5 seconds are inspected: a quiet gap of at least 60ms followed by weak
activity spanning at most 1.8s, whose frame RMS is at most 125% of the preceding
local speech RMS peak and at most 0.04, may be attenuated by 60dB. Quiet-frame
RMS must be at most 0.003 and peak at most 0.02. The initial boundary is 120ms after the gap start or completion hint, whichever
is later. Following user listening comparisons, attenuation starts 170ms earlier
than that initial boundary (clamped at zero). This intentionally relaxes the
previous speech padding and may attenuate a final syllable on other inputs. Quiet gaps overlapping
the completion hint are eligible too; gaps ending before it remain protected.
A 20ms gain ramp avoids
abrupt boundaries. Candidates are examined in chronological order to catch the
earlier onset of repeated tail bursts. This stronger setting was explicitly
requested for listening feedback and increases the risk of false detection. No samples
are removed, so duration and queue timing are preserved. Ambiguous boundaries,
missing analyzer information and processing exceptions preserve the original.
This heuristic can miss noise or mistake a quiet final word for noise; it is
an experimental setting for listening feedback, not a validated speech/noise
classifier. Existing waveform/alignment guards run before attenuation. Ordinary
generation without a long-tail warning does not run the detector. Diagnostics
record `tail_trim_applied`, `tail_trim_skipped`, and actual successful playback
as `long_tail_detected_but_played`.

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
`~/git/codex_enikk/tts/yuki-chatterbox-engine.py` is spoken as
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


### Korean text normalization

Reading text uses only the Yuki custom normalization layer. There is no optional external normalization backend, dictionary source layer, or secondary normalization process.

The custom layer keeps narrow, USER-confirmed rules for project names, selected technical terms, unit/number exceptions, path descriptions, and context-specific protections. Identifier, path, URL, email, version, and filename boundaries are guarded so prose normalization does not silently rewrite technical identifiers.

Protected spans use input-disjoint markers that must survive exactly once; missing or duplicated markers fail explicitly. Normalization runs before safe chunk splitting, and the guard analyzes the same text sent to generation. Displayed source text and path replacement accounting are retained.

Apply voice code with `enikk_tts update /path/to/source` then `enikk_tts restart`. Keep the core running.

Hash pronunciation accepts adjacent-anchor hex tokens from 7 characters;
6 or fewer remain excluded. Standalone detection still requires 32 characters,
and inline/fenced code and machine literals remain protected.

Hash labels may end in a colon. A single hex value in inline backticks immediately
after a hash label on the same line is treated as a displayed prose hash and read
with the usual prefix/length policy. This also accepts Korean labels such as
커밋 and 해시. Unlabeled inline hashes, inline commands, fenced code and other
machine literals retain their protection. No literal hash value is registered.

UUID values in prose have a separate full-token grammar for five hexadecimal
groups of lengths 8, 4, 4, 4 and 12. Each character is spoken with the shared
hex character names, with `대시` between groups. Case is ignored for speech;
all characters and groups are retained, with no hash abbreviation. Korean
particles/endings may follow the value. Code, URL, path, filename, assignment
and JSON machine-literal boundaries remain opaque. Screen/source text is unchanged.

Mixed Korean prose also accepts attached hash particles, registered lexical
words with common Korean verb endings, SHA algorithm labels, numeric counts,
rates, compact ranges and numeric fractions. Range separators and decimal dots
may carry Markdown escapes. Numeric PR/issue references require an adjacent
reference label. These are full-token grammars, not full-sentence exceptions;
URL, code, path and assignment tokens remain outside them.

## Markdown table speech

Bounded pipe-table rows are spoken as comma-separated cells. Separator rows are silent. Streaming waits for the end of each table row so punctuation inside a cell cannot expose partial delimiters. Literal pipes inside inline code or escaped cell content remain intact; the source conversation and displayed Markdown are unchanged.
