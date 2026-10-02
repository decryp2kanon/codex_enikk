# Local Enikk TTS

This optional integration speaks completed Codex commentary and final messages. It ignores user
messages, reasoning, tool output, and raw logs. Supertonic 3 and the bundled custom style stay
resident in one worker; synthesis and ordered playback use separate queues.

Runtime requirements:

- Python 3.10+ with `supertonic`
- `ffmpeg` built with the `rubberband` audio filter
- ALSA `aplay`

The voice settings are fixed at Korean, Supertonic speed `1.0`, Rubber Band tempo `1.3`, and pitch
`1.12246`. Model files are downloaded and cached by Supertonic and are never stored in this
repository. If a dependency is absent, `codex_enikk` continues without TTS.

Runtime state and deduplication markers use
`$XDG_STATE_HOME/codex_enikk/tts` (default `~/.local/state/codex_enikk/tts`). Override it with
`CODEX_ENIKK_TTS_STATE` when needed.
