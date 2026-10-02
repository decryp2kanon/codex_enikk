#!/usr/bin/env bash
# Provision the optional TTS runtime without modifying system Python packages.
set -euo pipefail
lib="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
venv="$lib/tts-venv"

if [[ ${EUID:-$(id -u)} == 0 && -x /usr/bin/apt-get ]]; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv ffmpeg alsa-utils librubberband2 libsndfile1
fi

command -v python3 >/dev/null
command -v ffmpeg >/dev/null
command -v aplay >/dev/null
ffmpeg -hide_banner -filters 2>/dev/null | grep -q '[[:space:]]rubberband[[:space:]]'

if [[ -x "$venv/bin/python" ]] && "$venv/bin/python" -c 'import supertonic; assert supertonic.__version__ == "1.3.1"' 2>/dev/null; then
    exit 0
fi

temporary="$(mktemp -d "$lib/.tts-venv.XXXXXXXX")"
trap 'rm -rf -- "$temporary"' EXIT
python3 -m venv "$temporary"
"$temporary/bin/python" -m pip install --disable-pip-version-check 'supertonic==1.3.1'
rm -rf -- "$venv"
mv -- "$temporary" "$venv"
trap - EXIT
