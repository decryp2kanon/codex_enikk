# Local Dorothy trigger (enabled by default)

Start the wrapper with `codex_enikk` to use the default wrapper-owned submission
proxy and trigger receiver. The current session must first finish its turn/tools
and drain TTS before a normal same-thread restart. Do not bypass the wrapper lock.
Set `CODEX_ENIKK_TRIGGER=0` to disable it. Updating an already-running wrapper
does not change its active receiver; a normal restart is required.

After validation/installation, Dorothy can run:

```sh
enikk-trigger "$HOME/dorothy-command.md"
```

The only production command source is that fixed inbox. It must be a regular
UTF-8 file, owned by this user, not group/world writable, at most 1 MiB, and end
with an exact EOF line (trailing blank lines are ignored). The parent must not be
group/world writable. `handoff_command.py` writes safe mode-0600 files. The client
cannot supply a different path, body, source, or approval metadata.

`enikk-trigger --fixture` submits only a built-in harmless status request, saved
as its own immutable command snapshot. It never reads the production inbox.
This is the only command permitted for the initial live validation.

## Submission isolation

The native TUI connects through a private Unix WebSocket proxy. The trigger uses
`~/.local/state/codex_enikk/trigger/trigger.sock` (0600 under a 0700 directory).
Both paths take the same reservation before forwarding a turn-start operation.
USER active/reserved makes Dorothy BUSY. DOROTHY active/reserved makes a native
new submission receive an explicit busy error; it is not silently queued or
steered. Existing native steering of its own USER turn remains available.
Approval responses, tool traffic, events and native interrupts are relayed.
Only one observer stream changes authoritative turn lifecycle state.

The proxy is not a general permission sandbox. Current-user peer credentials
authenticate transport, not strings such as `[USER]` inside the command. Snapshot
text is user-delegated task input, never automatic merge/release/deploy approval.
Another malicious process with the same OS user/root remains outside this boundary.

## Durable delivery and recovery

The receiver writes a read-only `command.md`, an append-only `instructions/`
directory, integrity manifest and durable UNKNOWN_EFFECT intent before sending
`turn/start`. The command SHA identifies the task; identical commands are not
re-executed. An ambiguous response/disconnect is not automatically retried.
Restart with an unresolved intent/accepted turn fails closed and requires trusted
operator reconciliation. It does not substitute the mutable inbox. A completed
turn records its terminal outcome; this is not a claim that a task's tests or PR
gates passed. Those remain the executing Enikk task's responsibility.

Thread switching/context-changing operations invalidate automatic intake until
reconciled. The receiver is tied to the selected startup thread, not an arbitrary
new conversation. A native reconnect can restore an idle state only when there
is no unresolved reservation and the observer remains connected.

Exit codes: ACCEPTED=0, BUSY=2, DUPLICATE=3, INVALID_EOF=4,
NO_RUNNING_ENIKK=5, INVALID_PATH=6, SECURITY_ERROR=7, UNKNOWN_EFFECT=8.
ACCEPTED means the server acknowledged the turn, not that its work succeeded.
Do not retry UNKNOWN_EFFECT automatically. No public network listener is used.

This candidate must pass same-thread native TUI, approval/tool, harmless trigger,
duplicate, continuity and Yuki checks before its PR may be updated. Unit fixtures
alone do not establish those live results.
