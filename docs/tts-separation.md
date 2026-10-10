# Independent Enikk voice service

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
enikk_tts --tts-debug
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

`enikk_tts --tts-debug` follows the current notify/engine log with `tail -F`,
switches to the new run after a voice restart, and prints readiness/error changes.
Ctrl+C closes only the viewer. It does not start, stop or restart either service.

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

## One-way IPC and readiness

The existing authoritative core observer sends protocol-v1 Unix datagrams to
`$XDG_RUNTIME_DIR/enikk-tts.sock` (0600, same-user credentials). Voice opens no
Codex connection, writer or turn. Each message carries producer UUID, thread,
sequence and monotonic timestamp. Each service and voice connection has a new
generation; queued jobs and receipts are confined to that generation.

- Send is nonblocking, with no application backlog and no send retries.
- Maximum datagram: 60 KiB; kernel receive queue is finite.
- Maximum pending synthesis jobs: 128 and 4 MiB of JSON; maximum item: 1 MiB.
- Heartbeat: 250 ms; connection loss: 3 seconds.
- Queued transport events older than 2 seconds are dropped.
- Engine readiness deadline: 120 seconds.
- Voice failures back off 2, 4, 8, 16, 30 seconds; six consecutive failures require
  explicit restart. Unsupported protocol affects voice only.
- Sequence gaps cancel voice work and establish a new generation. Missing text is
  never joined to later deltas. Duplicate/older sequences are discarded.
- READY requires model-ready evidence and an available audio server. Only new
  assistant item starts after READY are accepted. The whole item already underway,
  including its later deltas and completion snapshot, is skipped.
- Complete sentences use the existing normalization/chunking/delivery engine.
  Start/reconnect never replays a historical snapshot or a previous generation.
- Queue-full is logged as SKIPPED, never PLAYED.
- With core absent the service waits and cannot create a conversation.

Core mirror selection is under `codex_enikk/core/mirror-thread.json`; TTS cannot
update it. The existing pin, CODEX_HOME, journal and integrity checks are preserved.

## First transition and verification

An already running 2.1.8 wrapper still owns its original server and voice children.
Updating files cannot change that running process. Prepare code, isolated tests,
voice installation and a recovery copy first. Obtain the user's separate approval
before the single initial core shutdown/update/resume. Do not reuse an older
deployment approval, patch a running process or create a replacement thread.

After the approved transition, record new core PID/start identifiers and the same
thread. Test voice start/stop/restart/crash/update against that baseline, including
core file hashes, trigger, mirror and continuity evidence. Until those production
tests pass, report "prepared, transition pending", not "complete".

Isolated process tests use a fake audio worker and real local IPC. They prove
lifecycle/queue behavior, not GPU model readiness or audible pronunciation.
The existing synthesis engine, normalization, retry, guard, speed and reference
are unchanged by separation. Unit-expression education remains paused.

EOF
