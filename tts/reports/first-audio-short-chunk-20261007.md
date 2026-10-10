# First Audio aggressive first-phrase experiment — 2026-10-07

작성자: Enikk(에닉)

## Outcome

NOT ADOPTED: the aggressive candidates either increased first-generation time or introduced playback pauses. Candidate 3 improved the mixed sentence median but failed the gap gate. The existing source and production release were restored. No candidate commit, merge, push or final adoption.

Baseline/final main: `a41e3232fc852d0346033aebb2c70d8487e22ca1`. Baseline/final release: `b9b120d6ebeb129c`. Elapsed approximately 52 minutes. Maximum three candidates used; no fourth candidate.

## Method and limits

Backend onset was estimated with a pre-armed continuous JACK sink monitor. Physical speaker/device onset was unmeasured. Gap estimates use missing monitor-frame delivery intervals matched to original per-part start/end log windows; they are packet-delivery proxies, not physical-device or psychoacoustic silence measurements. Raw recordings, packet timestamps, logs, configuration and scripts are preserved. No gain normalization was applied to listening files.

Each baseline/final input has 20 measurements. Candidates 1/2/3 were initially screened with 5 per input; Candidate 3 subsequently received a separate 20-per-input block. The five-run screening results are not final population estimates. One warmup per input and a declared 2s idle window were separated from measured runs. Actual recorder setup adds further delay.

The first diagnostic Korean A block overlapped a 42.484s CPU regression suite. The entire block was retained as diagnostic and excluded from the final comparison; an independently declared clean 20-run Korean block followed all tests. The hash/mixed A blocks did not overlap tests. No favorable individual run was selected or substituted. A/B were sequential, GPU frequencies were not pinned, and tail estimates from 20 runs remain limited.

201 total recordings including warmups and diagnostics: all played, zero retries, zero monitor contamination errors. Final gate compares 60 baseline and 60 candidate short runs; screening and diagnostic samples are separate. Long-tail warnings remained warning-and-play and were counted from generate_end analyzer logs rather than the obsolete rejected-long-tail counter.

## Candidate policies

| Candidate | Korean first chunk | Mixed first chunk | Temporary release | Result |
|---|---:|---:|---|---|
| Baseline | 15 chars | 30 chars | b9b120d6ebeb129c | Restored |
| 1 | 6 chars | 9 chars | 96d02689476446fc | Korean slower; mixed pauses |
| 2 | 10 chars | 12 chars | 007cada7e1e08714 | Earlier start, excessive gaps |
| 3 | 15 chars | 17 chars | ec7b0ff71c58602f | Mixed faster; gap regression |

Only first-chunk splitting changed. Raw Korean prose and unchanged leading source words were required; transformed hash/UUID/number/path tokens could not complete an early phrase. Protected/technical-leading inputs retained the previous policy. No full-input overrides. Model, reference, tempo, sampling, long-tail/retry guard, sequence-gap and 170ms/60dB tail attenuation were unchanged.

## First Audio results — backend onset estimate

| Input/version | n | median (s) | p95 (s) | median change |
|---|---:|---:|---:|---:|
| korean baseline | 20 | 1.980 | 2.617 | — |
| korean candidate 3 final | 20 | 2.030 | 2.873 | +2.55% |
| hash baseline | 20 | 3.728 | 3.939 | — |
| hash candidate 3 final | 20 | 3.742 | 4.036 | +0.38% |
| mixed baseline | 20 | 2.939 | 3.355 | — |
| mixed candidate 3 final | 20 | 2.114 | 2.839 | -28.05% |

Mixed median improves by 0.824s; independent bootstrap median delta 95% interval [-0.9661326593486592, -0.4696858860552323] seconds. Korean/hash chunk text is identical, so their differences are not attributed to shorter first chunks.

Screening Korean medians: candidate 1 2.387s, candidate 2 1.796s (n=5 each). A six-character first input sometimes generated about three seconds of audio and took over two seconds to complete, despite no retry. Less text does not reliably imply faster generation.

## Gap regression

| Version/input | gap samples | median (s) | p95 (s) | max (s) | >1s |
|---|---:|---:|---:|---:|---:|
| Aclean-korean | 20 | 0.122 | 0.615 | 0.655 | 0 |
| C1-korean | 5 | 0.122 | 0.886 | 0.997 | 0 |
| C2-korean | 5 | 0.783 | 1.194 | 1.296 | 1 |
| C3final-korean | 20 | 0.112 | 0.420 | 0.826 | 0 |
| A-mixed | 20 | 0.101 | 0.172 | 0.314 | 0 |
| C1-mixed | 10 | 0.933 | 1.202 | 1.317 | 3 |
| C2-mixed | 10 | 0.698 | 1.297 | 1.402 | 2 |
| C3final-mixed | 40 | 0.176 | 1.381 | 1.402 | 10 |

Mixed first-boundary median also increases from approximately 0.101s to 0.165s, and first-boundary p95 from 0.172s to 0.892s. Including the new second boundary, p95 rises to 1.381s and 10/40 estimated gaps exceed one second, versus 0/20 at baseline. The increase is more substantial than the small median difference alone suggests. Dispatch-log gaps can stay short while backend/conversion wait and generation timing create audible pauses.

The first phrase can play sooner, but shorter playback duration may not cover generation of the following chunk. Introducing a short middle fragment also leaves too little playing time to prepare the later long chunk. This is the main observed tradeoff.

Because this short-input gap gate failed, the two full-document A/B runs and final subjective adoption gate were not attempted. No claim of long-document PASS or clip/pop removal is made. Avoiding additional benchmarks after a clear rejection keeps the experiment bounded.

## Tests and content preservation

Final candidate suite: 402 tests passed in 41.865s; git diff --check passed. Earlier source-string test expectations and the mocked split-call signature were updated for keyword arguments; no normalization expected values were relaxed. New cases covered 20 unseen Korean prefixes, protected technical/machine-leading sources, transformed hash characters, minimum length/remainder and longer complete phrases.

Original per-job logs confirm identical joined normalized token sequences across the compared policies. All jobs played; structural preservation alone cannot establish natural prosody or absence of synthesized missing words. No manual listening PASS is claimed for the new candidates.

Candidate engines, tests and patch were archived outside the repository. Tracked source/test harness files were restored to main; the candidate-only test was archived and removed to avoid leaving failing tests against baseline. Unrelated preexisting untracked reports were untouched.

## Listening files

Speech-only files preserve recorded PCM and reconstruct omitted inter-stream monitor intervals using packet timestamps. submit-delay files additionally prepend measured waiting time as synthetic silence. They demonstrate approximate timing and pacing; they are not continuous recordings starting at submission or physical speaker recordings. Representatives are chosen nearest the median onset, not for favorable quality.

Current mixed input:
```bash
paplay ~/.local/state/codex_enikk/first-audio-short-chunk-20261007/A-mixed-submit-delay.wav
```

Most aggressive mixed input:
```bash
paplay ~/.local/state/codex_enikk/first-audio-short-chunk-20261007/C1-mixed-submit-delay.wav
```

Moderately aggressive mixed input:
```bash
paplay ~/.local/state/codex_enikk/first-audio-short-chunk-20261007/C2-mixed-submit-delay.wav
```

Final conservative candidate mixed input:
```bash
paplay ~/.local/state/codex_enikk/first-audio-short-chunk-20261007/C3final-mixed-submit-delay.wav
```

Actual fixed mixed input:

> 현재 작업 결과를 먼저 확인하고 해시와 숫자 및 경로의 처리 상태를 비교한 뒤 다음 요청을 순서대로 진행하겠습니다.

## Final state

Production restored to b9b120d6ebeb129c; state=ready, model_ready=true, playback_available=true, last_error=null. Source matches saved baseline and installed engine. main remains a41e323; no new commit/push. Enikk PID 1444, trigger PID 1632, Codex resume PID 1834 and their start times are unchanged.

Evidence directory: `~/.local/state/codex_enikk/first-audio-short-chunk-20261007`

## Subsequent explicit user instruction

After reviewing the faster-start result and the reported gap regression, the user requested applying candidate 3. The original gap gate remains failed; this instruction authorizes production application with that disclosed tradeoff, not a new benchmark PASS. The exact previously tested candidate is restored for TTS application. No new optimization or benchmark is performed. Git commit/push has not been requested in this turn. Baseline release b9b120d6ebeb129c remains preserved for rollback.

## Final follow-up
The short-first-phrase candidate alone remained unsatisfactory due to middle pauses. A subsequent remainder allocation experiment preserved its leading phrase but regrouped the remainder with a 25-character target. On the fixed mixed input this changed 17/12/33 to 17/25/20. The user confirmed listening improvement and explicitly requested full application. See first-audio-gap-allocation-20261007.md for the final selected implementation and its measurement limits. The original NOT_ADOPTED result above is historical, not a rejection of the later combined implementation.
