#!/usr/bin/env bash
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
prefix="${PREFIX:-/usr/local}"
stage="${DESTDIR:-}"
[[ "$prefix" == /* && "$prefix" != / && "$prefix" != *'..'* ]] || { echo 'PREFIX는 / 이외의 절대 경로여야 합니다.' >&2; exit 1; }
[[ -z "$stage" || "$stage" == /* ]] || { echo 'DESTDIR는 절대 경로여야 합니다.' >&2; exit 1; }
base="${stage}${prefix}"
lib="$base/lib/codex_enikk"
commands=(codex_enikk codex_session_save.sh codex_enikk_restore check-codex-compat enikk-trigger)
command -v python3 >/dev/null
python3 -c 'import sys; assert sys.version_info >= (3, 10), "Python 3.10+ required"'
if [[ -e "$lib" || -L "$lib" ]]; then
    echo "기존 설치 경로가 있습니다. 먼저 해당 설치를 제거해주세요: $lib" >&2
    exit 1
fi
for name in "${commands[@]}"; do
    if [[ -e "$base/bin/$name" || -L "$base/bin/$name" ]]; then
        echo "기존 명령을 덮어쓰지 않습니다: $base/bin/$name" >&2
        exit 1
    fi
done
mkdir -p -- "$base/lib" "$base/bin"
mkdir -- "$lib"
mkdir -- "$lib/tts"
mkdir -- "$lib/tts/assets"
complete=0
cleanup() {
    if [[ "$complete" == 0 ]]; then
        for name in "${commands[@]}"; do
            if [[ -L "$base/bin/$name" && "$(readlink -- "$base/bin/$name")" == "../lib/codex_enikk/$name" ]]; then
                rm -- "$base/bin/$name"
            fi
        done
        rm -rf -- "$lib"
    fi
}
trap cleanup EXIT
for file in enikk.py latest.py persistence.py restore.py check_codex_compat.py handoff_command.py submission_arbiter.py trigger_transport.py trigger_service.py trigger_client.py README.md LICENSE VERSION uninstall.sh "${commands[@]}"; do
    install -m 644 -- "$source_dir/$file" "$lib/$file"
done
for file in README.md setup-tts.sh setup-nemo-tn.sh yuki-text-normalization.py yuki-chatterbox-engine.py yuki-codex-notify.py yuki-codex-rollout-watch.py yuki-codex-stream.py; do
    install -m 644 -- "$source_dir/tts/$file" "$lib/tts/$file"
done
install -m 644 -- "$source_dir/tts/assets/yuki_super-clean.wav" "$lib/tts/assets/yuki_super-clean.wav"
chmod 755 "$lib/tts/setup-tts.sh"
chmod 755 "$lib/uninstall.sh"
for name in "${commands[@]}"; do
    chmod 755 "$lib/$name"
    ln -s -- "../lib/codex_enikk/$name" "$base/bin/$name"
done
printf '%s\n' 'codex_enikk-managed-install-v1' > "$lib/.installed-by-codex-enikk"
complete=1
if [[ -z "$stage" && "${CODEX_ENIKK_INSTALL_TTS:-1}" != 0 ]]; then
    if ! "$lib/tts/setup-tts.sh"; then
        printf '%s\n' '경고: 선택적 TTS 설치에 실패했습니다. Codex 기본 기능은 정상적으로 사용할 수 있습니다.' >&2
    fi
fi
printf '설치 완료: %s/bin/codex_enikk\n' "$base"
