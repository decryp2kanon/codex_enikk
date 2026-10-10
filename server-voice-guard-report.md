# Server-side realtime voice guard

The Enikk-owned app-server rejects `thread/realtime/start` before loading a thread or attaching a realtime call when `CODEX_ENIKK_DISABLE_REALTIME=1`. This covers default WebSocket, WebRTC and existing-call transports. Text turns remain supported. The user-requested Korean error is returned as JSON-RPC invalid request (-32600). Phone UI rendering of that error is client-controlled and is not verified.

Source: stock 0.160.0 commit `a956835d020762cb2b570053af06f643a11c0ecc`; patch: `patches/voice-guard-0.160.0.patch`. Build in separate checkout with Rust 1.95.0: `cargo +1.95.0 build -p codex-cli --bin codex --release --locked -j 4` from codex-rs. The upstream release lockfile needs its workspace package versions aligned with 0.160.0; no external dependency change was required.

`core_runtime.py` selects the private binary only when the installation manifest exists, verifies SHA256, and enables the guard in the child environment. A missing or altered binary fails explicitly rather than falling back to an unguarded server. The global Codex binary is unchanged.

Validation: Python runtime tests (2), installed core/no-TTS regression (1), and isolated live-model probe passed. The probe rejected three voice transports both before and after restarting only the disposable test server, obtained a real text reply, resumed the same test thread ID, and recalled the test token. Result: `/tmp/enikk-voice-guard-live-r61rc7ez/result.json`. The test uses separate CODEX_HOME and does not modify the production conversation.

Rust tests initially failed because the upstream test builder supplied a debug-only argument to a release binary. The new tests explicitly use normal plugin startup, removing that argument. Final scoped Rust run: 2 passed, 0 failed (nextest run b27be504-d7ba-4ceb-bd70-0d604f2fdf50). Installed private binary, manifest and runtime after preserving the previous runtime and a disk-only restore script under `/home/ak/.local/state/codex_enikk/backups/server-voice-guard-20261010T024453Z`. Installed runtime startup and Korean voice rejection smoke check passed. Existing production PID and session remain unchanged; USER_RESTART_REQUIRED. Remote-control enablement was persisted for user restart.

Production Enikk is not restarted by this change. User restart is required after installation. This protects the Enikk-owned server; it does not block standalone ChatGPT voice sessions elsewhere or claim absolute memory preservation.
