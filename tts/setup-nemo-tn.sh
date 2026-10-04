#!/usr/bin/env bash
set -euo pipefail
# CPU-only isolated dependencies. Never run pip in the Chatterbox environment.
tn_home="${CODEX_ENIKK_TN_HOME:-$HOME/Apps/enikk-nemo-tn}"
mkdir -p -- "$tn_home"
if [[ ! -x "$tn_home/.venv/bin/python" ]]; then
    python3 -m venv "$tn_home/.venv"
fi
"$tn_home/.venv/bin/python" -m pip install --upgrade 'pip>=24,<27' 'wheel'
"$tn_home/.venv/bin/python" -m pip install 'nemo_text_processing==1.2.0' 'pynini==2.1.6.post1'
"$tn_home/.venv/bin/python" - "$(dirname -- "${BASH_SOURCE[0]}")/yuki-text-normalization.py" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location('yuki_tn', sys.argv[1])
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
m.initialize()
assert m.normalize('2026년 10월 4일')
m._client.close()
PY
