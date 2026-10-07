# First-audio gap allocation experiment — 2026-10-07

## Result
Candidate 25 was temporarily applied, then accepted after user listening. The user explicitly requested full application (commit/main/push/TTS update and restart). The first Korean phrase is unchanged. Its remaining normalized words are regrouped with a 25-character target, minimum 12 and existing maximum 55, preserving complete words and punctuation. This produces 17 / 25 / 20 on the fixed mixed sentence instead of 17 / 12 / 33. No per-sentence literal overrides. Only eligible raw Korean leading prose is affected. All original words match across recorded candidates.

## Same-input warm comparison
| Policy | Runs | First onset median (s) | Submit-to-playback-done median (s) | Gap p95 (s) | Gaps >1s |
|---|---:|---:|---:|---:|---:|
| Starting candidate 17/12/33 | 20 | 2.085 | 10.454 | 1.624 | 12/40 |
| Reallocation 17/25/20 | 20 | 2.100 | 9.152 | 0.681 | 1/40 |
| Aggressive merge 17/46, rejected | 5 | 2.083 | 9.924 | 1.982 | 5/5 |

First-onset median change +0.72%; completion median change -12.46%. Independent bootstrap 95% CI for completion median B minus A: [-1.8972260244525387, -0.46923225704813376] seconds. All 45 scored runs played; zero retries and zero monitor contamination errors. The new candidate still has one >1s gap (max 1.616s); it does not eliminate all pauses.

For context only, the earlier 30/33 policy had a 9.420s completion median; it was measured in an earlier session, not a new simultaneous control. Relative to that historical measurement the current completion improvement is approximately 2.85%, not 25%. The user's overall 25% completion goal is not achieved.

## Measurement limits
First onset is a prearmed sink-monitor signal estimate, not physical speaker onset. Completion uses the final playback-done monotonic event; physical device completion is unmeasured. Gap values estimate backend missing-frame intervals matched to part boundaries. Physical/acoustic gap timing is unmeasured. A/B files preserve recorded PCM and reconstruct measured pauses and initial wait after a marker beep. No volume/speed adjustments.

Scored runs consist of five initial screenings plus fifteen repeat confirmations per selected policy; all are retained. Warmups excluded from statistics. One attempted aggressive-merge screening detected unrelated playback before a scored submission; it was stopped and retried under a separate label after silence. No submitted failure was removed. Tests were not concurrent with scored measurements.

## Regression and deployment
210 distinct relevant tests passed (short phrase, normalization, TTS suites including delivery, education, independent TTS, voice process, core-without-TTS). Delivery 33 tests also passed separately. git diff --check passed. No model, reference, sampling, guard/retry, voice, volume, speed or 170ms tail attenuation changes. No additional inference. No core lifecycle actions. Core PID/start-time snapshot unchanged.

Active temporary release: 7161efd1b55637e0. ready/model_ready/playback_available true, last_error null. Source/install engine byte parity checked. Starting release ec7b0ff71c58602f and older stable b9b120d6ebeb129c retained. No commit or push. No full long-document benchmark or user quality PASS claimed; final acceptance remains pending listening and any required broader checks.

## Listening
Same sentence, separate files; marker beep followed by reconstructed submission wait and recorded speech:

A: /home/ak/.local/state/codex_enikk/first-audio-gap-allocation-20261007/A-before-beep-delay.wav

B: /home/ak/.local/state/codex_enikk/first-audio-gap-allocation-20261007/B-reallocated-beep-delay.wav

Raw measurement files reside in /home/ak/.local/state/codex_enikk/first-audio-short-chunk-20261007 with labels G0, G25, G55retry. This experiment's scripts, source snapshots, results and final state: /home/ak/.local/state/codex_enikk/first-audio-gap-allocation-20261007.

## User acceptance and final application
The user reported “좋아졌어” and then “일단 지금 밸런스 잡혔어 풀반영 하자”. This accepts the current balance despite the remaining occasional gap and unmet 25% total-completion goal. Deployment uses exactly the tested candidate; no additional tuning. The original first-short-phrase candidate alone was not accepted as the final implementation; it is combined here with remainder reallocation. Final deployment identifiers are recorded in the local application artifact after push/status checks.
