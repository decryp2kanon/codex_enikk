# TTS separation report — prepared, first transition pending

Date: 2026-10-06 KST.

**Status: implementation, isolated verification, main/push and stopped voice installation are complete.
The running Enikk core remains 2.1.8. Production separation is not yet complete.**

## Changes

Implementation: `10efdd7`. Read-only status correction: `55d311b`.
Source version: 2.2.0. Voice release: `b37bd7a1ad4e1f59`.

- `core_runtime.py` owns the private Codex app-server. Core starts it without TTS files,
  Chatterbox Python, model, reference or playback programs.
- `enikk.py` uses core Python for trigger and core-owned mirror selection.
  The old wrapper-owned voice run and streaming lifecycle were removed.
- `trigger_service.py` relays only relevant events from its existing authoritative observer;
  `voice_events.py` uses bounded, nonblocking, one-way local datagrams.
- `tts/independent_service.py` owns voice generations, readiness, connection loss, queue limits
  and its engine children under an independent systemd user service.
- `enikk_tts`, `tts_control.py`, `tts_release.py`, `install-tts.sh` provide independent
  control and manifest-verified atomic releases, including versioned control code.
- Core install/update no longer installs, overwrites or starts TTS.
- Legacy automatic education postprocessing is paused and cannot restart core.

The normalization, stream accumulator, synthesis/delivery engine, retry/guard/speed and reference
code are unchanged. No model download, venv change, identity injection or session replacement occurred.
`continuity.py`, pin handling and the journal path were preserved.

## Verified before production transition

| Test | Result |
|---|---|
| Full unit/integration suite | 314 tests passed in 40.995 s |
| Read-only status fix and release tests | 15 tests passed, including installed CLI status preserving the release manifest |
| Installed core with no TTS/venv/model/reference/playback command | Real local RPC text submission, interrupt, mirror output and continuity checkpoint passed with a fake Codex server |
| Real receiver/worker processes | Stop/restart, mid-item exclusion, crash, reconnect isolation, queue-full explicit skip passed with fake audio |
| Actual systemd user service | Survived wrapper subreaper cleanup; stop removed its children; crash/restart produced a new generation; core absence left service waiting |
| Slow/absent/full receiver | Publisher remained nonblocking; drops/gaps did not change core operation |
| Interrupted release switch | Killing the switching process preserved the selected old release; switch and rollback verified |
| TTS install/update vs core | Core sentinel files and real production core file hashes unchanged |
| Core update vs TTS | Independently installed voice sentinel unchanged |
| Shell syntax and Git whitespace | Passed |
| Production original-record continuity check | Passed; same thread, 242255509 bytes, 63 compactions, no partial tail |

The full suite's temporary fixture warnings about absent mirror databases are expected in tests
that deliberately omit the database. The installed-core integration separately checks actual mirror content.

An installed status query initially generated Python bytecode inside a voice release.
This was found by manifest verification, corrected by disabling launcher bytecode writes,
covered by an installed-command regression test, and reverified on Nana. Only that generated
bytecode cache was removed; no logs, conversation records or existing backups were deleted.

## Production before/after preparation

| Component | Before | After preparation |
|---|---:|---:|
| Wrapper PID | 3756344 | 3756344, same start identity |
| Native Codex PID | 3756941 | 3756941, same start identity |
| App-server PID | 3756478 | 3756478, same start identity |
| Trigger PID | 3756724 | 3756724, same start identity |
| Thread | `01a0dc7e-bc10-74f3-9324-e0d4474c2f65` | Same |
| Installed core | 2.1.8 | 2.1.8, all 58 recorded file hashes unchanged |
| Existing voice run | `run-evgn3d_r` | Existing wrapper-owned voice unchanged |
| New independent TTS | Absent | Installed, inactive, MainPID=0 |

Original-record SHA256 at verification:
`346528e87bf7db6c2459a12ce24c496cc68e40effa685322478a9254586503c1`.

These observations prove structural continuity at the checked times, not complete semantic memory.
No additional identity-memory test was presented as evidence of restoration.

## Installation and preserved evidence

- Source: `/home/ak/git/codex_enikk`
- Isolated worktree: `/home/ak/git/codex_enikk-independent-tts`
- Voice install: `/home/ak/.local/lib/enikk_tts`
- Selected voice release: `releases/b37bd7a1ad4e1f59`
- Service: `/home/ak/.config/systemd/user/enikk-tts.service`, inactive and not enabled
- Voice state when started: `/home/ak/.local/state/enikk_tts`
- Verified original installation copy:
  `/home/ak/.local/state/codex_enikk/migrations/tts-separation-20261006/core-2.1.8`
- Baseline, prepared verification and test logs:
  `/home/ak/.local/state/codex_enikk/migrations/tts-separation-20261006/`

Existing user autostart/service definitions were inspected; no additional Enikk/Yuki startup
entry was found in those locations. Legacy source education restart paths were disabled in the
prepared version. The still-running old trigger has not been patched or restarted.

## First transition — separate approval required

The current 2.1.8 wrapper owns its original TTS children and has no new event relay.
A stopped voice installation alone cannot detach those live children. A first core restart is
therefore required. The handover sections 8 and 10 explicitly reserve separate approval for it.

Prepared procedure:

1. Recheck live PID/start identity, active/queued work, current pin and original-record integrity.
   Finish or wait for active work; do not interrupt an in-progress user task.
2. Stop the verified old wrapper through its normal SIGTERM cleanup once. Preserve its exit backup.
3. Apply the tested core update:
   `PREFIX=/home/ak/.local bash /home/ak/git/codex_enikk/update.sh`.
4. Relaunch `codex_enikk` with the same environment and `CODEX_HOME=/home/ak/.codex`.
   Confirm that it resumes the original pinned thread, not a new conversation.
5. Record the new core PID/start/thread/hash baseline, then explicitly start independent TTS.
6. Test voice stop/start/restart/crash/update while verifying that the new core baseline remains
   unchanged and text/tools/trigger/mirror/continuity continue working.
7. Verify actual model readiness and playback on the new release. Report any remaining limitation.

If core startup fails, keep evidence of the failed installation and use the verified 2.1.8
installation copy to recover the same pinned conversation. Do not overwrite session DBs,
change CODEX_HOME or substitute a new thread.

## Commands after the approved transition

```bash
enikk_tts start
enikk_tts stop
enikk_tts restart
enikk_tts status

enikk_tts update /home/ak/git/codex_enikk
enikk_tts restart

enikk_tts rollback b37bd7a1ad4e1f59
enikk_tts restart

journalctl --user -u enikk-tts.service
```

This first voice release is the rollback baseline for later releases; there is no older independent
production release yet. Rolling voice back never rolls core back or restores speech queues.

## Remaining checks

Production model loading, audible output, and unchanged core behavior across live TTS lifecycle
operations are pending the approved first transition. Isolated fake-audio results do not prove
those production outcomes. Pronunciation accuracy is also not established by playback success.

The service starts speaking only items begun after model/event readiness; the remainder of an
answer already underway is omitted. This follows the handover's explicit default.
Protocol/bounds/retry details are in [the operations contract](docs/tts-separation.md).

Unit-expression education remains paused. No educational benchmark or automatic training was run.

EOF
