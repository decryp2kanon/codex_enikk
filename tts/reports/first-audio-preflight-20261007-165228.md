# First Audio optimization preflight

Decision: INCONCLUSIVE; stopped before performance benchmark or optimization.

## Preserved state

- main/origin: 9bb67202b5f6867c12205c9fcc94dac69cf2aa06
- Current production and rollback release: 6466cb74f9c19b11
- TTS service PID: 551318; ready/model_ready/playback_available confirmed.
- Enikk/Codex core PIDs and start times unchanged.
- No service restart, optimization changes, commit or push.
- Source/install parity confirmed for engine and normalization files.

## Measurement limitation

The committed observer subscribes to PulseAudio events, queries sink inputs and then attaches a recorder to the TTS stream. It cannot guarantee observing the first audio frame. Its post-attachment signal is an upper-bound estimate, not a valid first-onset measurement for the requested A/B gate. Existing playback-start logging precedes tempo conversion and paplay invocation, so that timestamp also does not represent actual audio onset.

Two unrelated uncorked streams (MuseScore and OpenUtau) are connected to the same sink. This establishes possible contamination, not proof that either app was audibly playing. No app was stopped, muted or rerouted. Recording the whole shared sink without monitoring contamination would not solve the measurement problem.

The plan explicitly stops when trustworthy onset comparison is unavailable. No baseline numbers were invented; candidate count and benchmark count are both zero.

## Code observations, not performance conclusions

Reference conditioning is prepared on model startup. The visible conditioning reset is a retry callback; it is not evidence of repeated preparation on every successful request. Playback includes ffmpeg tempo conversion before paplay. Their optimization benefit remains unmeasured.

## Next prerequisite

Prepare an onset observer that is ready before submission and reliably attributes the signal to TTS, or validate backend frame timing with known error bounds. Keep reference, tempo and output routing unchanged for A/B. Only after that prerequisite can the prescribed 20 + 20 short runs and two long runs provide a meaningful baseline.

Raw evidence: ~/.local/state/codex_enikk/first-audio-preflight-20261007-165228/preflight.json
