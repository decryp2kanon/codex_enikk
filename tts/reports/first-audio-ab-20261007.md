# First Audio A/B: first natural clause candidate

Final status: adopted with explicit user authorization. Listening confirmed natural speech and, after deployment, no volume problem. Backend timing improvement is observed; no physical speaker/device onset or ending is claimed. The earlier recording amplitude difference remains unexplained.

Baseline main/origin: 9bb67202b5f6867c12205c9fcc94dac69cf2aa06; rollback release: 6466cb74f9c19b11; candidate release: b9b120d6ebeb129c. One candidate tested; no commit/push.

## Protocol and measurement limits

A/B each used one warmup per short input, 20 Korean + 20 hash runs, and two identical full long runs. All 84 planned measured runs played; no runs removed/replaced, zero retries. Diagnostic monitor fixes are separate from performance runs and are preserved.

The continuous sink monitor was connected before submission, 48kHz stereo, threshold 0.001, requested latency 10ms. Other uncorked streams caused rejection. Capture delivery timestamps estimate backend onset; they are not physical speaker onset. All runs use the same output route, reference, model, tempo and normalizer. GPU frequency/thermal state was not pinned, and sequential A/B sampling does not fully eliminate stochastic drift.

Backend gap estimates match continuously delivered frame spans to original playback log windows. Actual physical playback start/end remains unmeasured. Audible gap estimates use the same threshold at each chunk end/start and include quiet waveform tails. Dispatch-log gaps are a third proxy, excluding conversion/device startup. These estimates must not be relabeled as physical gaps.

## Root cause and minimal change

Conditioning cache and inference mode already reuse setup. The dominant wait is first-chunk generation. The candidate splits only the first 32–55-character chunk if a complete Korean connective clause has 14–28 characters and >=3 words, with a >=12-character/>=2-word remainder. It reuses recovery_clauses and preserves every token and punctuation; no literal input mapping.

For the Korean input, the first generated text becomes `현재 시스템 상태는 정상이며` instead of the entire 32-character sentence. Hash input and the fixed long input retain identical chunks, so their timing/warning differences are not attributed to this rule. This is not a claim that every TTS sentence becomes 24% faster.

## Short results

| Input | A median | B median | Change | A p95 | B p95 |
|---|---:|---:|---:|---:|---:|
| korean | 2.782209s | 2.102376s | -24.435% | 3.189900s | 2.860135s |
| hash | 3.750932s | 3.756696s | +0.154% | 3.983318s | 4.187751s |

Korean median improves by 0.680s (24.435%); independent bootstrap median delta 95% interval -0.969 to -0.601s. Hash median +0.154%; hash p95 3.983→4.188s is preserved as unresolved tail sampling variability. Unchanged chunks do not establish a causal slowdown. Twenty samples provide a limited p95 estimate.

Korean warning counts: 6/20 parts at A, 7/40 at B. Hash: 6/20 vs 5/20. These are long-tail warning-and-play events, not retries/failures. No guard, model/reference/tempo or 170ms tail attenuation changes.

## Long results

Each version completed 2×286 chunks, with 570 internal gaps. No playback failures or monitor errors.

| Gap metric | A | B |
|---|---:|---:|
| backend_frame_gap median | 0.165110 | 0.165150 |
| backend_frame_gap p95 | 0.186289 | 0.186319 |
| backend_frame_gap max | 0.186474 | 0.207167 |
| backend_frame_gap over_1s | 0.000000 | 0.000000 |
| backend_frame_gap over_2s | 0.000000 | 0.000000 |
| backend_frame_gap over_5s | 0.000000 | 0.000000 |
| audible_gap median | 0.251108 | 0.272475 |
| audible_gap p95 | 1.360446 | 1.253951 |
| audible_gap max | 1.893888 | 1.851079 |
| audible_gap over_1s | 70.000000 | 49.000000 |
| audible_gap over_2s | 0.000000 | 0.000000 |
| audible_gap over_5s | 0.000000 | 0.000000 |
| dispatch_gap median | 0.007000 | 0.007000 |
| dispatch_gap p95 | 0.013000 | 0.013000 |
| dispatch_gap max | 0.020000 | 0.021000 |
| dispatch_gap over_1s | 0.000000 | 0.000000 |
| dispatch_gap over_2s | 0.000000 | 0.000000 |
| dispatch_gap over_5s | 0.000000 | 0.000000 |

Backend median/p95 essentially unchanged. Audible median +0.021s is inside the +0.05s allowance; audible p95 and >1s counts decrease, >2s/>5s remain zero. Long-tail warnings 116→78 across 572 parts each, but long-file chunking is identical; no causal warning reduction claim.

## Tests and content checks

395 unit tests passed; git diff --check passed. All compared sources join to the identical spoken token sequence, and all played IDs are complete/in order. Structural preservation cannot prove natural prosody or absence of synthesized spoken omissions; manual listening remains necessary. One final done-log race was recovered only from the saved original job log, with the initial receipt snapshot retained; no rerun or timestamp adjustment.

## Listening and rollback

Manual voice identity, endings and natural connective pacing: PENDING. Plan section 13 requires withholding adoption when listening cannot be confirmed. Candidate service was stopped and release 6466cb74f9c19b11 selected/start requested again. Core PIDs/start times are verified separately in final-state evidence.

Representatives are nearest-median runs A9 and B17. All raw recordings remain. Listening files retain PCM and insert the measured inter-chunk frame hiatus absent from paused-monitor samples; no noise trim or word editing was added to these comparison files.

- Before: ~/.local/state/codex_enikk/first-audio-ab-20261007/A-listen.wav
- After: ~/.local/state/codex_enikk/first-audio-ab-20261007/B-listen.wav

Raw data/logs/WAVs/runner: ~/.local/state/codex_enikk/first-audio-ab-20261007

Started 2026-10-07T16:56:36.305690+09:00; written 2026-10-07T18:23:55.329810+09:00; elapsed 87.3 minutes. No additional candidate search was started while quality verification remained pending.

Rollback verified: active 6466cb74f9c19b11, installed engine equals the saved baseline; service ready, model_ready/playback_available true, last_error null. Enikk/Codex core PIDs/start times unchanged. main/origin remain 9bb6720. No commit/push of the candidate.

## User-authorized adoption and volume follow-up

The user explicitly requested applying the candidate first, then addressing reduced volume. Representative A/B full-recording RMS: -35.489 / -44.045 dBFS. Across 20 Korean recordings, median RMS: -36.817 / -43.685 dBFS. Full-recording RMS includes pauses and must not be treated as a perceptual loudness measurement. The candidate changes chunk boundaries only; the cause of the amplitude difference remains unconfirmed. No gain compensation is included in this commit. Baseline release remains available for rollback.

## Deployment and final listening confirmation

Implementation commit dd58e69c192ce936d26c57a11b22db6fc53e5e3b was pushed to main. Active release b9b120d6ebeb129c matches the source engine; ready/model_ready/playback_available are true and last_error is null. Enikk/Codex core PIDs and start times remain unchanged.

After restart, two Korean diagnostic recordings measured -29.838 and -29.126 dBFS RMS; one unchanged hash input measured -28.245 dBFS. Observed playback streams used 100% (0 dB) gain. These are diagnostics, not replacement A/B samples. The earlier low amplitude was not reproduced; its cause is unconfirmed. No amplitude compensation code was added. The user listened to the current recording and explicitly confirmed there is no volume problem.
