# Optional upstream Korean normalization sources

This directory separates source adapters from Yuki custom exceptions. The
selected dictionary contains only rule IDs UDK-001..009 listed in
`manifest.json`; `nemo_adapter.py` owns the persistent CPU NeMo process;
`orchestrator.py` is the only source dispatch boundary. The custom exceptions
remain in the adjacent `yuki-text-normalization-overrides.py`.

The normalizer calls the orchestrator once. With the default
`CODEX_ENIKK_TTS_UPSTREAM=1`, it preserves the existing order:
selected dictionary -> Yuki protections and custom fixes -> NeMo TN ->
checked restoration. NeMo stays an isolated CPU subprocess and is imported
only in that child.

With `CODEX_ENIKK_TTS_UPSTREAM=0`, the orchestrator does not import the selected
dictionary or NeMo adapter and does not start the NeMo subprocess. It calls the
Yuki custom exception module with an identity TN callback. Custom names,
confirmed pronunciations, protection spans, and path handling remain available;
the 9 selected upstream dictionary tokens and all upstream number/date/unit
grammar are bypassed. The switch is checked before loading source modules.

A CPU micro-check used 10 representative existing normalization examples over
20 passes (200 calls), with seven alternating identity/custom-only measurements.
Custom-only median was 4.36 ms for 200 calls (about 21.8 microseconds per call).
The pure identity median was 7 microseconds total and is only a no-op floor,
not a like-for-like NeMo comparison. Custom exception processing stays bounded
and the custom-only mode avoids NeMo process startup and IPC.

The layer order intentionally matches the existing runtime. Before the change,
the child applied the 9-rule dictionary and then called
`overrides.normalize_with_exceptions(text, NeMo.normalize)`; custom protection
and restoration wrapped the public NeMo TN callback.

To fully remove NeMo later, delete `nemo_adapter.py`, remove its file from the
install/update lists, remove `setup-nemo-tn.sh` and its setup invocation, and
remove the NeMo-only integration fixture/docs. Keep `orchestrator.py`,
`selected_korean_dictionary.py`, and custom overrides. Then configure
`CODEX_ENIKK_TTS_UPSTREAM=0`: startup and normalization require no NeMo package,
helper path, or process. The custom module and TTS engine do not need edits.

To remove every optional upstream source instead, the source registry and files
can be removed in a separate change; this task only makes NeMo independently
removable. Install/update copy adapter modules but do not initialize NeMo.
The TTS setup invokes NeMo preparation only while the global switch is enabled.

MeloTTS-derived entries are attributed in `LICENSE-MELO.txt`. Coqui-derived
mapping facts are reimplemented locally; no Coqui source file is copied.
