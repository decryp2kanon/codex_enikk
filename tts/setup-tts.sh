#!/usr/bin/env bash
# Verify the optional external Chatterbox runtime.
set -euo pipefail
lib="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
chatterbox_home="${CODEX_ENIKK_CHATTERBOX_HOME:-$HOME/Apps/chatterbox-yuki}"

if [[ ${EUID:-$(id -u)} == 0 && -x /usr/bin/apt-get ]]; then
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y alsa-utils
fi

command -v python3 >/dev/null
command -v aplay >/dev/null
[[ -x "$chatterbox_home/.venv/bin/python" ]]
[[ -f "$chatterbox_home/yuki_super-clean.wav" ]]
"$chatterbox_home/.venv/bin/python" -c 'import chatterbox, torch; assert torch.cuda.is_available()'
