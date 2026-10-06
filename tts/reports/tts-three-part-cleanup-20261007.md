# TTS measurement, dictionary and boundary cleanup candidate

Status: performance regression; candidate not committed, pushed or deployed.

Production remains commit 38fbece / release 8daac6b25e76711a. No Enikk/Codex core or TTS service restart was performed during this task.

## Changes

- Playback observer attaches to the TTS descendant PulseAudio stream and records readiness, bytes, errors and observed signal. It does not measure physical speaker onset.
- Removed the report_v31.1.md production literal exception. Registered basename components, numeric version components and extensions now share a general rule. Version numbers use Korean cardinal readings.
- Protect quoted assignments, nested/unfinished JSON, commands, URLs and fenced code before Markdown interpretation. Ordinary inline display words retain the established pronunciation policy.

## Measurement evidence

The first fixed five-run observer batch captured no signals because paplay was reported as pacat. These raw failures are preserved. The corrected, separately declared diagnostic batch captured 5/5 TTS signals, all PLAYED with zero retries. Observed post-attachment upper bounds: 2.814, 2.761, 2.759, 2.685, 2.713 seconds. These are not physical First Audio measurements or evidence of latency improvement. Entity killed at target stream removal is preserved in recorder stderr.

## CPU benchmark

31 paired alternating ABBA/BAAB rounds; same process, inputs and repetitions; warmup before measurement. Pipeline: cleanup, paths, normalization. A is the saved 38fbece modules; B is this local candidate. No input-result caching.

| Set | A microseconds/item | B microseconds/item | Change |
|---|---:|---:|---:|
| korean | 20.23 | 21.65 | +7.04% |
| english | 45.19 | 46.10 | +2.03% |
| technical | 45.93 | 61.93 | +34.83% |
| corpus2 | 13.51 | 14.45 | +6.95% |
| corpus3 | 15.17 | 16.17 | +6.63% |
| corpus4 | 7.16 | 7.93 | +10.74% |
| corpus5 | 7.54 | 8.34 | +10.51% |
| corpus6 | 7.41 | 8.17 | +10.14% |
| corpus7 | 20.94 | 27.94 | +33.40% |
| corpus8 | 6.71 | 7.44 | +10.90% |
| corpus9 | 7.21 | 8.03 | +11.39% |
| corpus10 | 7.25 | 8.26 | +14.06% |

The candidate exceeds the +2% preservation gate. Absolute changes are small CPU costs, not corresponding First Audio percentages. No production adoption is justified by this benchmark. Corpus 1 was not included in this CPU run; no complete 1–10 performance PASS is claimed.

## Exception audit and limits

No new full-input, hash, UUID or education-row mappings were introduced. Registered lexical and filename components are shared policy. Existing legacy callback phrase guards and approved one-hour/branch coordinating-particle policies remain; this is not a claim that all historical exception code was removed. Physical onset and the historical missing-recording root cause remain unmeasured/unproven.

Raw evidence: /home/ak/.local/state/codex_enikk/tts-three-part-cleanup-20261007

The changes are left uncommitted for review and further simplification. Existing production is preserved.

Relevant targeted regression: 174 tests passed; git diff --check passed. Final read-only status: service PID 517114 unchanged, state ready, model_ready and playback_available true. last_error records event sequence gap; reconciling active voice item. This task did not alter sequence-gap reconciliation or restart the service to clear the diagnostic.

Full repository unit discovery: 392 tests passed in 41.576 seconds.
