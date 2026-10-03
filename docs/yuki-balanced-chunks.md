# Balanced-tail scheduler candidate (not performance-validated)

This candidate changes only the scheduler's final short-tail join. When that
join can instead form two whole-word chunks of at least 20 characters each,
it selects a punctuation/Korean connective boundary, then favors balanced
lengths. Otherwise it keeps the existing join. The target (28), maximum (55),
normal sentence processing, pronunciation, and bounded generation recovery
remain unchanged. Existing indivisible oversized tokens remain oversized.

This is a draft candidate, not a demonstrated latency improvement. It must
not be deployed on the strength of offline splitting alone.

## Historical evidence

A fixed local log snapshot contained 155 completed generations:

- 121 succeeded on their first attempt; none took 10 seconds or longer.
- 34 used retry/recovery; 11 took 10 seconds or longer.
- Generation median: 3.295 seconds; maximum: 31.977 seconds.
- 44 rejected attempts reported `internal_long_tail`; one reported a waveform
  duration violation. Counts include recovery-clause attempts.
- Queue wait: median 0.001 seconds, maximum 6.630 seconds (155 samples).
- Within-job playback gaps: median 0.0125 seconds, maximum 27.600 seconds
  (48 samples). Inter-job idle gaps are excluded from these figures.

Two reported examples took 10.609 and 11.607 seconds to generate after an
internal long-tail rejection. Their actual preceding playback gaps were
6.201 and 6.955 seconds, respectively. Generation time is not silent time.

Longer normalized inputs were associated with more first-attempt rejection:
14/34 for 40–55 characters versus 10/59 for 30–39. These are different texts,
not a controlled experiment. The cohort excludes cancelled/finally failed
items without a completed-generation record. No causal or p95 claim is made.
Raw user text and logs are kept outside the repository.

## Offline paired replay

The same 112 accepted job texts were passed through the original and candidate
schedulers, before pronunciation normalization:

| Metric | Original | Candidate |
| --- | ---: | ---: |
| Chunks | 161 | 178 |
| Length median | 30 | 28 |
| Chunks at least 40 characters | 34 | 17 |
| Chunks below 20 characters | 15 | 15 |
| Longest chunk | 72 | 72 |

17 jobs changed; token sequence differences were zero. Of the two reported
delay cases, the 10.609-second case retains its original 28/38-character
scheduler chunks; the 11.607-second case changes from 45 to 21/23 characters.
The candidate therefore does not even alter every reported slow input. The oversized existing
token behavior is unchanged. Historical generation lengths and these scheduler
lengths occur at different pipeline stages and should not be directly equated.

## Required follow-up before adoption

Actual before/after generation benchmark sample size is **zero**. The existing
worker automatically sends accepted output to playback and exposes no safe
file-only benchmark route. This task prohibits restarting/changing it or
loading a second GPU model, so no generated test audio was played or produced.

Once a separately authorized safe benchmark is available, repeat identical
failure and control sentences under the same model/reference/C2 settings.
Measure rejection/recovery frequency, generation >=10s, median/max generation,
total job duration and audible gaps. Preserve every token and audio guard.
More chunks mean more calls and can increase total latency or disrupt prosody;
shorter inputs alone do not prove better generation. Do not weaken guards or
increase retry budgets to make the candidate appear successful.

PulseAudio playback, cancellation/stale protection, voice settings, model,
retry/reset/depth-1 split recovery and installation are untouched.
