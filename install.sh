#!/usr/bin/env bash
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
prefix="${PREFIX:-/usr/local}"
stage="${DESTDIR:-}"
[[ "$prefix" == /* && "$prefix" != / && "$prefix" != *'..'* ]] || { echo 'PREFIX는 / 이외의 절대 경로여야 합니다.' >&2; exit 1; }
[[ -z "$stage" || "$stage" == /* ]] || { echo 'DESTDIR는 절대 경로여야 합니다.' >&2; exit 1; }
base="${stage}${prefix}"
lib="$base/lib/codex_enikk"
commands=(codex_enikk codex_session_save.sh codex_enikk_restore)
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
for file in enikk.py restore.py README.md LICENSE VERSION uninstall.sh "${commands[@]}"; do
    install -m 644 -- "$source_dir/$file" "$lib/$file"
done
for file in README.md yuki-codex-notify.py yuki-codex-rollout-watch.py yuki-tts-engine.py yuki-f5ttl-f4dp.json; do
    install -m 644 -- "$source_dir/tts/$file" "$lib/tts/$file"
done
chmod 755 "$lib/uninstall.sh"
for name in "${commands[@]}"; do
    chmod 755 "$lib/$name"
    ln -s -- "../lib/codex_enikk/$name" "$base/bin/$name"
done
printf '%s\n' 'codex_enikk-managed-install-v1' > "$lib/.installed-by-codex-enikk"
complete=1
printf '설치 완료: %s/bin/codex_enikk\n' "$base"
