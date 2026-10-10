# Local Dorothy trigger (enabled by default)

Start the wrapper with `codex_enikk` to use the default wrapper-owned submission
proxy and trigger receiver. The current session must first finish its turn/tools
and drain TTS before a normal same-thread restart. Do not bypass the wrapper lock.
Set `CODEX_ENIKK_TRIGGER=0` to disable it. Updating an already-running wrapper
does not change its active receiver; a normal restart is required.

After validation/installation, Dorothy can run:

```sh
enikk-trigger "$HOME/.local/state/codex_enikk/bridge/dorothy-command.md"
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

## Visible command

The submitted USER message contains a Korean delegation notice, snapshot path,
and the complete validated UTF-8 command body without truncation. The displayed
body and immutable snapshot use the same captured bytes. Mutable inbox changes
do not amend an accepted task. Existing turns are not resent after an update.


## 작업 중 명령 대기열

진행 중인 turn을 steer하거나 중단하지 않고 새 명령 원문을 읽기 전용 snapshot으로 보존한다.
응답 `QUEUED`는 대기열 접수이며 실제 실행 시작인 `ACCEPTED`와 구분한다.
완료/중단 이벤트 후 FIFO 순서로 전달하며 inbox를 덮어써도 이미 접수된 원문은 바뀌지 않는다.
최대 32개 대기 항목이며 한도에서는 `QUEUE_FULL`로 거절한다. 같은 snapshot은 중복 실행하지 않는다.
발송 전의 `QUEUED`만 재시작 후 자동 재개한다. 발송 중 `SENDING`이나 효과가 불명확한
`UNKNOWN_EFFECT`는 자동 재전송하지 않는다. 새 명령은 보존하지만 미확정 작업이 해결될 때까지 기다린다.
서버의 일치하는 응답/완료 이벤트나 미확정 예약이 없는 상태의 authoritative idle 응답만 상태 복구 근거로 사용한다.
시간 제한의 started_at은 큐 접수 시점이 아니라 발송 예약 시점에 설정한다.
대기 중인 명령 취소: `enikk-trigger --cancel TASK_ID`. 실행 중인 작업은 이 명령으로 중단하지 않는다.
큐 처리는 완료 이벤트로 깨우며 로그/프로세스를 주기적으로 polling하지 않는다.

## Shared file locations

The command inbox is `~/.local/state/codex_enikk/bridge/dorothy-command.md`. The receiver migrates the legacy home inbox on its next normal startup, after acquiring its receiver lock. It refuses conflicting destinations and unsafe files. Incomplete command text is preserved without submission; EOF validation still happens when submitting. A running receiver retains its old inbox until the user restarts Enikk; do not move that file early.

The separate bidirectional bridge log is `~/.local/state/codex_enikk/bridge/yuki-dorothy.md`, with the same path plus `.lock` for flock. Pause both writers before renaming the log and original lock; preserve the event database and subscription. Path migration does not transfer a Work subscription to Chat.
