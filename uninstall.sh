#!/usr/bin/env bash
set -euo pipefail
prefix="${PREFIX:-/usr/local}"
stage="${DESTDIR:-}"
[[ "$prefix" == /* && "$prefix" != / && "$prefix" != *'..'* ]] || { echo '잘못된 PREFIX' >&2; exit 1; }
[[ -z "$stage" || "$stage" == /* ]] || { echo '잘못된 DESTDIR' >&2; exit 1; }
base="${stage}${prefix}"
lib="$base/lib/codex_enikk"
if [[ ! -e "$lib" && ! -L "$lib" ]]; then
    echo '설치된 codex_enikk가 없습니다.'
    exit 0
fi
if [[ -L "$lib" || ! -f "$lib/.installed-by-codex-enikk" || "$(cat "$lib/.installed-by-codex-enikk")" != codex_enikk-managed-install-v1 ]]; then
    echo "설치 소유권을 확인할 수 없어 중단합니다: $lib" >&2
    exit 1
fi
for name in codex_enikk codex_session_save.sh codex_enikk_restore; do
    if [[ -L "$base/bin/$name" && "$(readlink -- "$base/bin/$name")" == "../lib/codex_enikk/$name" ]]; then
        rm -- "$base/bin/$name"
    fi
done
# Only the private, marker-verified installation directory is removed.
rm -rf -- "$lib"
printf '%s\n' '제거 완료. Codex 원본 세션과 백업은 유지됩니다.'
