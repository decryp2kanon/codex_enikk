# Chatterbox TTS

`codex_enikk` reads completed CODEX progress and final messages with a persistent
Chatterbox worker. User input, reasoning, tool output, code blocks, and raw logs are excluded.

The external runtime defaults to `~/Apps/chatterbox-yuki` and requires:

- `.venv/bin/python` with `chatterbox-tts==0.1.7`
- `yuki_super-clean.wav`
- ALSA `aplay`

The fixed voice is SUPER-CLEAN C2: Korean, exaggeration `0.50`, and CFG weight `0.70`.
Failures reset conditioning and retry once. After two failed generation attempts, the chunk
is recorded as FAILED_EXPLICITLY with its text and reason; other chunks continue.
`setup-tts.sh` creates the venv and installs dependencies. CUDA is selected when available;
otherwise the worker uses CPU. Model files are downloaded by Chatterbox on first use and kept
in its normal user cache.

The bundled SUPER-CLEAN reference is installed automatically. To explicitly replace it with
another authorized reference, use the advanced override:

```bash
sudo env CODEX_ENIKK_CHATTERBOX_REFERENCE_SOURCE=/path/yuki_super-clean.wav ./install.sh
```

The installer validates the WAV with `torchaudio`. Updates preserve the existing venv, model
cache, and reference unless the override is explicitly supplied.
Set `CODEX_ENIKK_TTS=0` to disable TTS or `CODEX_ENIKK_CHATTERBOX_HOME` to select another
external Chatterbox directory. TTS failure never prevents the Codex wrapper from running.

Playback acknowledgements are saved atomically per chunk. Jobs are removed only after all
chunks are PLAYED. Playback errors are isolated to the item and do not stop the consumer.
Jobs containing explicit failures are retained as `.failed-*` files in the TTS state `jobs/`
directory, including the original message, chunk text, and failure reasons. They are parked
for explicit recovery, not automatically retried forever. On restart, interrupted ordinary
jobs resume chunks without saved terminal acknowledgements. A crash after audible playback
but before its acknowledgement can replay that chunk; acknowledged chunks are not replayed.
