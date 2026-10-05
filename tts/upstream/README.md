# Optional upstream-derived Korean dictionary layer

This directory contains a small, removable exact-token dictionary layer. It is
kept separate from `yuki-text-normalization-overrides.py` and from NVIDIA NeMo.
The layer covers only rule IDs UDK-001..009 listed in `manifest.json`; it does
not import G2P, a neural model, or an external package.

The normalizer has one explicit call into `_upstream_normalize(text)`. It runs before the
existing Yuki exceptions and NeMo TN. `CODEX_ENIKK_TTS_UPSTREAM=0` disables the
layer. If the runtime module is absent, the call passes the original text
through, preserving the pre-existing Yuki + NeMo path. Other import/runtime
errors remain visible rather than being hidden as successful normalization.

To update rules, replace this directory's runtime module, manifest, tests, and
applicable license notice together. To remove the feature, remove the one
`apply_upstream(text)` integration call and this directory; the normalizer then
continues with its original Yuki + NeMo flow. No custom override changes are
needed. Install/update scripts manage only the runtime module, manifest, README,
and notices, not experimental corpus or WAV files.

MeloTTS-derived entries are attributed in `LICENSE-MELO.txt`. Coqui-derived
mapping facts are reimplemented locally; no Coqui source file is copied.
