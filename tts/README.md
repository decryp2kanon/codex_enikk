# Chatterbox TTS

`codex_enikk` reads completed CODEX progress and final messages with a persistent CUDA
Chatterbox worker. User input, reasoning, tool output, code blocks, and raw logs are excluded.

The external runtime defaults to `~/Apps/chatterbox-yuki` and requires:

- `.venv/bin/python` with Chatterbox Multilingual and CUDA support
- `yuki_super-clean.wav`
- ALSA `aplay`

The fixed voice is SUPER-CLEAN C2: Korean, exaggeration `0.50`, and CFG weight `0.70`.
Failures reset conditioning and retry once; a second failure skips only that chunk.
Set `CODEX_ENIKK_TTS=0` to disable TTS or `CODEX_ENIKK_CHATTERBOX_HOME` to select another
external Chatterbox directory. TTS failure never prevents the Codex wrapper from running.
