#!/usr/bin/env bash
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
prefix="${PREFIX:-$HOME/.local}"
[[ "$prefix" == /* && "$prefix" != / ]] || exit 1
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"
lib="$prefix/lib/enikk_tts"
if [[ -e "$prefix/bin/enikk_tts" || -L "$prefix/bin/enikk_tts" ]]; then
    [[ "$(readlink "$prefix/bin/enikk_tts")" == ../lib/enikk_tts/enikk_tts ]] || exit 1
fi
mkdir -p "$lib" "$prefix/bin"
# Control files live outside immutable engine releases and never import an engine.
for file in enikk_tts; do
    temporary="$(mktemp "$lib/.$file.XXXXXXXX")"
    install -m 755 "$source_dir/$file" "$temporary"
    mv "$temporary" "$lib/$file"
done
if [[ ! -L "$prefix/bin/enikk_tts" ]]; then
    ln -s ../lib/enikk_tts/enikk_tts "$prefix/bin/enikk_tts"
fi
ENIKK_TTS_INSTALL="$lib" python3 -B "$source_dir/tts_release.py" update "$source_dir"
if [[ "${ENIKK_TTS_INSTALL_SERVICE:-1}" == 1 ]]; then
    unit="$HOME/.config/systemd/user/enikk-tts.service"
    mkdir -p "$(dirname "$unit")"
    [[ "$lib" != *'%'* && "$lib" != *'"'* && "$lib" != *$'\n'* ]] || exit 1
    cat > "$unit" <<UNIT
[Unit]
Description=Enikk independent voice service

[Service]
Type=simple
ExecStart=/usr/bin/python3 -B "$lib/active/independent_service.py"
KillMode=control-group
TimeoutStopSec=12
Restart=no
UMask=0077
Environment=PYTHONDONTWRITEBYTECODE=1

[Install]
WantedBy=default.target
UNIT
    systemctl --user daemon-reload
fi
printf '%s\n' 'TTS installed; left stopped. Start explicitly with enikk_tts start.'
