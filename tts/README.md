# Local Enikk TTS

This optional integration speaks completed Codex commentary and final messages. It ignores user
messages, reasoning, tool output, and raw logs. Supertonic 3 and the bundled custom style stay
resident in one worker; synthesis and ordered playback use separate queues.

Latin technical terms embedded in Korean are routed to `lang=en`; surrounding text remains
`lang=ko`. Every segment uses the same custom style and fixed speed/post-processing settings.
Segments enter the playback queue as soon as they are ready, preventing a complex mixed-language
sentence from starving playback while the whole sentence is synthesized.

Single newlines are spoken continuously. Blank lines receive a short paragraph pause. Model edge
silence is trimmed and replaced with bounded pauses so WAV and `aplay` boundaries do not introduce
long gaps.

Runtime requirements:

- Python 3.10+ with `supertonic`
- `ffmpeg` built with the `rubberband` audio filter
- ALSA `aplay`

`install.sh` creates the private runtime at `lib/codex_enikk/tts-venv` and installs
`supertonic==1.3.1` there. On an Ubuntu root installation it also installs `python3-venv`,
`ffmpeg`, `alsa-utils`, `librubberband2`, and `libsndfile1` through APT. A user-prefix installation
expects those OS packages to already exist. Set `CODEX_ENIKK_INSTALL_TTS=0` while installing or
updating to skip provisioning.

The voice settings are fixed at Korean, Supertonic speed `1.0`, Rubber Band tempo `1.3`, and pitch
`1.12246`. Model files are downloaded and cached by Supertonic and are never stored in this
repository. If a dependency is absent, `codex_enikk` continues without TTS.
The Supertonic 3 model is downloaded on first speech generation into Supertonic's user cache
(normally `~/.cache/supertonic3`) and reused thereafter. Uninstall removes the private venv and
installed style, but keeps this user cache to avoid deleting user data and forcing a later download.

Set `CODEX_ENIKK_TTS=0` when launching `codex_enikk` to disable TTS without uninstalling it.

Runtime state and deduplication markers use
`$XDG_STATE_HOME/codex_enikk/tts` (default `~/.local/state/codex_enikk/tts`). Override it with
`CODEX_ENIKK_TTS_STATE` when needed.
