# Delegated final replies

The request proxy captures only authoritative observer `item/completed` events
for its currently reserved DOROTHY task, exact thread ID and accepted turn ID.
Only `agentMessage` items explicitly marked `phase: final_answer` are retained.
It never reads bulk thread history or collects deltas, commentary, unclassified
messages, native USER replies or other turns/connections.

Completed items are stored in the private task directory as `reply.json`.
Publication happens only after that same turn completes successfully. A failed,
interrupted or incomplete turn does not publish a partial result. Item conflicts,
limits and capture errors suppress publication. Task completion and reply delivery
are separate states; `COMPLETED` alone is not proof that a reply was delivered.

The final text is appended to
`~/.local/state/codex_enikk/bridge/yuki-dorothy.md` with the existing `.lock` flock,
UTF-8, fsync, a deterministic `enikk-reply-TASK_ID` and recipient `Dorothy(Chat)`.
The original history and lock inode are preserved. Quoting every response line
prevents model text from injecting additional bridge records. No log or lock is
silently created. Limits are 16 final items, 32 KiB text and a 1 MiB shared log.

`reply-delivery.json` records success or failure. `reply-published.json` is a
receipt. Duplicate item events and repeated publication do not create duplicate
records. A crash after fsync but before the receipt can reconcile the exact
record; a partial or conflicting append fails closed. A busy lock leaves the
answer snapshot intact, reports failure and does not automatically retry or
start another turn. An operator can explicitly call `delegated_reply.publish`
with the original task, thread, turn and log to retry after investigating.

This is file-based answer return, not automatic Chat notification. Records use
`알림: 없음`; Work event subscriptions and the Bridge DB remain unchanged.
Dorothy must read the file with the shared-lock protocol. Subscribe/claim/reply
routing from Work to Chat is a separate, unverified feature.

Installing the module and updated proxy prepares the next normal Enikk startup.
An already-running proxy does not hot-reload; only the USER restarts Enikk.
Validate a production delegated roundtrip after that restart before claiming
production success. The live probe creates a private CODEX_HOME and disposable
thread; its success does not prove automatic Chat receiving in production.
