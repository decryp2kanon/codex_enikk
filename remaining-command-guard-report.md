# Remaining command guard — 2026-10-10

Author: Dorothy(Work), reviewed by Enikk(유키짱).
Base: d7d2cc2; supported native UI: codex-cli 0.160.0.

## Scope

This extends the existing request-proxy guard. It does not replace the Codex UI,
rewrite identity/instructions, restore old conversation data, or restart Enikk.
Rejected requests are rejected before forwarding and before arbiter reservation.
Existing delete/archive/new/fork/revert/logout protection remains.

| Entry | Protected operation | Preserved behavior / evidence limit |
| --- | --- | --- |
| /init | Exact stock expanded prompt in turn/start and turn/steer | Ordinary discussion of init/AGENTS.md allowed; source fixture hash pinned to 0.160.0 |
| /voice | Realtime start and audio/text/speech append | Stop/read methods retained; live microphone was not tested |
| /memories | memory/reset, thread/memoryMode/set, memory config writes | Read-only queries retained |
| Personality/instructions | Non-null direct overrides and protected configuration writes/overrides | /personality is not a slash command in this source version; no promise of unchanging model behavior |
| /agents, /subagents, /resume | Other-ID read/resume/submission/interrupt rejected | Same-ID reads, normal turns, interrupt and resume retained; not every picker state tested |
| /plugins | Install/uninstall/reconcile/checkout and plugin config changes, thread disabledPluginIds replacement | Browse/read retained; not a blanket ban on every plugin API |
| /hooks, /experimental | Protected hooks/features configuration writes | Read-only menus retained |
| /approve | Explicit guardian-denial approval request and protected reviewer config writes | Not a blanket removal of permissions controls |
| Ctrl+Z | Scoped SIGTSTP ignore inherited by the native TUI | Normal exit/interrupt retained; SIGSTOP and external termination cannot be blocked this way |

## Deliberate compatibility boundary

The wrapper still accepts extra CLI arguments, but this guard does NOT support
explicit personality, features, protected config, baseInstructions, or
developerInstructions overrides, even when they appear equal to a config file.
Custom TUI/terminal-visualization instruction retransmission can therefore fail
with an explicit ENIKK_CONTINUITY_BLOCKED error. Nothing is silently removed.
Use the verified default invocation, `codex_enikk`, for this deployment.

A config/read result is not treated as the resumed thread's settings. We removed
that inference after Enikk's NO-GO review. Missing/null optional direct fields
preserve the server's saved behavior. Only existing collaboration instructions
from the validated same-ID resume response may be retransmitted; built-in
plan/default with null developer_instructions remains allowed.

Deployment preflight observed no -c/--config flags in the running native TUI and
no non-null protected scalar instruction/personality config in a read-only
config query. Terminal visualization is off by default in upstream 0.160.0.
This is evidence for the CURRENT default setup, not universal custom-config support.

## Validation

Final relevant automated regression: 140 tests PASS (guard, trigger, startup,
arbiter, terminal restoration, installed core without TTS, wrapper).

Isolated bubblewrap stock TUI/mock: 13 entry paths retain a live TUI and can send
a follow-up on the same fixture ID and receive PROBE_OK. /init issued a rejected
turn/start. Ctrl+Z preserved an already-written draft and an attached valid PNG,
then submitted both successfully. Model/plan remain usable. Other menu tests
are browse/dismiss regressions; empty fixtures do NOT prove every mutation UI.
Request-level denial tests cover the protected mutations separately.
Evidence: ~/.local/state/enikk-dorothy-bridge/guard-ui-validation/.

Live isolated app-server + candidate proxy, separate CODEX_HOME and disposable
thread: protected requests rejected; normal model/plan settings accepted; actual
model response passed. Only the test server was stopped. Restarting it and
resuming the same test ID recalled the prior test token. Final live evidence:
/tmp/enikk-guard-live-7xi8l0ub/result.json. Temporary auth copy was removed.
This was a protocol live test, not a claim of all native keyboard paths with a model.

Review: Enikk initially returned NO-GO for file-config baseline and direct
instruction compatibility. The revised, deliberately limited policy received
code-review GO for the currently verified default setup. Enikk did not rerun tests.

Not delivered: the unverified Rust UI patch, blocking edit-screen entry, universal
input/attachment preservation in every menu, arbitrary instruction retransmission,
or a guarantee that all model context/memory can never be lost. Stock edit-screen
limitations documented in priority-guard-report.md remain.

## Installation and recovery

Only enikk.py and trigger_service.py are changed in the managed installation.
No running Enikk process is stopped or restarted. USER_RESTART_REQUIRED: the
running Python services do not reload these changes automatically.

Backup: ~/.local/state/codex_enikk/backups/remaining-command-guard-20261010T003117Z
The backup manifest includes old file hashes and existing runtime start times.
To restore the prior two files on disk (does not restart anything):

```bash
python3 ~/.local/state/codex_enikk/backups/remaining-command-guard-20261010T003117Z/restore.py
```

The user controls normal shutdown/restart. Source commit/push and installation
parity are verified separately at delivery. No merge or history rewriting.
