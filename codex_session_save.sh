#!/usr/bin/env bash
set -euo pipefail
entry="$(readlink -f -- "${BASH_SOURCE[0]}")"
exec "$(dirname -- "$entry")/codex_enikk" "$@"
