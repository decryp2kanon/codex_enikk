#!/usr/bin/env bash
# Update only a managed installation; retain the previous version for rollback.
set -euo pipefail
source_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
prefix="${PREFIX:-/usr/local}"
stage="${DESTDIR:-}"
[[ "$prefix" == /* && "$prefix" != / && "$prefix" != *'..'* ]] || exit 1
[[ -z "$stage" || "$stage" == /* ]] || exit 1
lib="${stage}${prefix}/lib/codex_enikk"
[[ ! -L "$lib" && -f "$lib/.installed-by-codex-enikk" ]] || {
    echo '관리 설치를 찾지 못했습니다. 먼저 install.sh로 설치하세요.' >&2
    exit 1
}
[[ "$(cat "$lib/.installed-by-codex-enikk")" == codex_enikk-managed-install-v1 ]] || exit 1
[[ "$source_dir" != "$(cd -- "$lib" && pwd)" ]] || {
    echo '다운로드한 새 소스 폴더의 update.sh를 실행하세요.' >&2
    exit 1
}
python3 -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); compile(p.read_text(), str(p), "exec")' "$source_dir/enikk.py"
for file in enikk.py VERSION README.md; do
    [[ -f "$source_dir/$file" && -f "$lib/$file" && ! -L "$lib/$file" ]] || exit 1
done
[[ -d "$source_dir/tts" ]] || exit 1
previous="$(mktemp -d "$lib/previous-XXXXXXXX")"
for file in enikk.py VERSION README.md; do
    cp -a -- "$lib/$file" "$previous/$file"
done
if [[ -d "$lib/tts" ]]; then
    cp -a -- "$lib/tts" "$previous/tts"
fi
temporary=""
cleanup() {
    [[ -z "$temporary" ]] || rm -f -- "$temporary"
}
trap cleanup EXIT
for file in README.md VERSION enikk.py; do
    temporary="$(mktemp "$lib/.$file.XXXXXXXX")"
    install -m 644 -- "$source_dir/$file" "$temporary"
    mv -f -- "$temporary" "$lib/$file"
    temporary=""
done
tts_temporary="$(mktemp -d "$lib/.tts.XXXXXXXX")"
for file in README.md setup-tts.sh yuki-chatterbox-engine.py yuki-codex-notify.py yuki-codex-rollout-watch.py yuki-codex-stream.py; do
    install -m 644 -- "$source_dir/tts/$file" "$tts_temporary/$file"
done
mkdir -- "$tts_temporary/assets"
install -m 644 -- "$source_dir/tts/assets/yuki_super-clean.wav" "$tts_temporary/assets/yuki_super-clean.wav"
chmod 755 "$tts_temporary/setup-tts.sh"
rm -rf -- "$lib/tts"
mv -- "$tts_temporary" "$lib/tts"
if [[ -z "$stage" && "${CODEX_ENIKK_INSTALL_TTS:-1}" != 0 ]]; then
    if ! "$lib/tts/setup-tts.sh"; then
        printf '%s\n' '경고: 선택적 TTS 업데이트에 실패했습니다. Codex 기본 기능은 정상적으로 사용할 수 있습니다.' >&2
    fi
fi
printf '이전 버전 보존: %s\n' "$previous"
"${stage}${prefix}/bin/codex_enikk" --version
printf '%s\n' '업데이트 완료. 기존 앱을 종료한 뒤 codex_enikk를 다시 실행하세요.'
