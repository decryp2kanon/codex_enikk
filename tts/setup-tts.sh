#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID:-$(id -u)} == 0 && -n "${SUDO_USER:-}" && "$SUDO_USER" != root ]]; then
    target_user="$SUDO_USER"
    target_home="$(getent passwd "$target_user" | cut -d: -f6)"
else
    target_user="$(id -un)"
    target_home="$HOME"
fi
[[ -n "$target_home" && -d "$target_home" ]] || { echo 'TTS 사용자 홈을 찾을 수 없습니다.' >&2; exit 1; }
chatterbox_home="${CODEX_ENIKK_CHATTERBOX_HOME:-$target_home/Apps/chatterbox-yuki}"
reference="$chatterbox_home/yuki_super-clean.wav"
source_reference="${CODEX_ENIKK_CHATTERBOX_REFERENCE_SOURCE:-}"
bundled_reference="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)/assets/yuki_super-clean.wav"
if [[ ${EUID:-$(id -u)} == 0 && -x /usr/bin/apt-get ]]; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv alsa-utils libsndfile1
fi
command -v python3 >/dev/null
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
command -v aplay >/dev/null
run_user() {
    if [[ ${EUID:-$(id -u)} == 0 && "$target_user" != root ]]; then
        sudo -u "$target_user" -H -- "$@"
    else
        "$@"
    fi
}
install -d -m 755 -o "$target_user" -g "$(id -gn "$target_user")" "$chatterbox_home"
if [[ -n "$source_reference" ]]; then
    [[ -f "$source_reference" ]] || { echo "reference 원본이 없습니다: $source_reference" >&2; exit 1; }
    install -m 644 -o "$target_user" -g "$(id -gn "$target_user")" -- "$source_reference" "$reference"
elif [[ ! -f "$reference" ]]; then
    [[ -f "$bundled_reference" ]] || { echo "bundled reference가 없습니다: $bundled_reference" >&2; exit 1; }
    install -m 644 -o "$target_user" -g "$(id -gn "$target_user")" -- "$bundled_reference" "$reference"
fi
if [[ ! -s "$reference" ]]; then
    echo "유키짱 reference가 비어 있습니다: $reference" >&2
    exit 1
fi
if [[ ! -x "$chatterbox_home/.venv/bin/python" ]]; then
    run_user python3 -m venv "$chatterbox_home/.venv"
fi
if ! run_user "$chatterbox_home/.venv/bin/python" -c \
    'import importlib.metadata as m; assert m.version("chatterbox-tts") == "0.1.7"' 2>/dev/null; then
    run_user "$chatterbox_home/.venv/bin/python" -m pip install 'chatterbox-tts==0.1.7'
fi
if ! run_user "$chatterbox_home/.venv/bin/python" -c 'import websocket; import importlib.metadata as m; assert m.version("websocket-client") == "1.9.0"' 2>/dev/null; then
    run_user "$chatterbox_home/.venv/bin/python" -m pip install 'websocket-client==1.9.0'
fi
run_user "$chatterbox_home/.venv/bin/python" - "$reference" <<'PY'
import sys, torchaudio
import chatterbox, perth, torch
waveform, rate = torchaudio.load(sys.argv[1])
assert waveform.numel() and rate > 0, "empty or invalid reference WAV"
print(f"Chatterbox 0.1.7 ready; reference={sys.argv[1]}; device={'cuda' if torch.cuda.is_available() else 'cpu'}")
PY
