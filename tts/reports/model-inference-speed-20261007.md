# Model inference acceleration experiment — 2026-10-07

Result: **NO ADOPTION**. Two execution-only candidates were screened on the installed GTX 1080 / PyTorch 2.6.0+cu124. Neither showed a useful improvement; the second clearly regressed. Stopped after two consecutive ineffective candidates. The balanced production source and release are unchanged. The 25% extra improvement target was not achieved.

Elapsed: 12.4 minutes. HEAD 5ab257fc6039101d67b80a9352ff16228f2126e0; release 7161efd1b55637e0; tag tts-first-audio-balanced-20261007 remains the accepted recovery point.

## Diagnosis

An isolated model process was used because the 8GiB GPU could not safely hold two model copies. Only TTS was stopped and restarted around each bounded diagnostic; Enikk/Codex core PID and start-time snapshots were identical. No repository runtime source, model weights, package installation, reference, sampling parameters, guards, chunk policy, voice, playback tempo, normalization or 170ms tail attenuation was changed. The external package sources were read only.

Stage timers use explicit CUDA synchronization in the isolated diagnostic. They include synchronization overhead and are not production First Audio measurements. The first of four generations is warmup; three measured phrases cover the accepted 17/25/20 mixed-sentence chunks.

| Phrase | Generation (s) | T3 tokens (s) | Flow (s) | Vocoder (s) | Alignment copy (s) |
|---|---:|---:|---:|---:|---:|
| 현재 작업 결과를 먼저 확인하고 | 1.742 | 0.906 | 0.789 | 0.046 | 0.029 |
| 해시와 숫자 및 경로의 처리 상태를 비교한 뒤 | 2.152 | 1.184 | 0.917 | 0.050 | 0.032 |
| 다음 요청을 순서대로 진행하겠습니다. | 1.875 | 1.029 | 0.795 | 0.050 | 0.032 |

The alignment copy is approximately 1–2% of total generation in these measurements. A separate 200-iteration tensor transfer microbenchmark was much faster when slicing before copying, but this does not justify a 25% First Audio claim. The large costs were speech-token prediction and flow conversion.

A CUDA profiler recording of one S3 conversion observed 16,491 GPU events and approximately 794.84ms summed GPU kernel time; attention was 37.27%, addmm 21.88%, mm 11.27% and cuDNN convolution 9.78% of summed GPU time. CPU and GPU totals overlap and must not be added as serial latency. Profiling perturbs execution; percentages are diagnostic, not production performance gates. An initial profile script had a stdlib module-name collision, was renamed, and the profile was rerun successfully; the failed import contains no scored data.

## Candidate 1: cuDNN automatic kernel selection

The same fixed speech tokens and reference conditioning were converted with benchmark=False (A) and True (B). Each input had five alternating ABBA/B A A B rounds, ten runs per side. Cold first calls and every timed value are retained. A fixed diagnostic seed sets identical flow noise; it is not a production RNG change.

| Speech tokens | A median (s) | B median (s) | Change | Maximum waveform difference |
|---|---:|---:|---:|---:|
| 64 | 0.835332 | 0.833975 | -0.16% | 3.91e-07 |
| 81 | 0.996491 | 0.996523 | +0.00% | 1.83e-06 |
| 158 | 1.298192 | 1.293409 | -0.37% | 1.31e-06 |

Verdict: ineffective (less than 1% change, with no useful whole-generation improvement established). Not installed.

## Candidate 2: mathematical SDPA backend for S3 conversion

Only the S3 attention execution backend differed. Each of three fixed-token inputs had eight ABBA/B A A B rounds, sixteen runs per side. Default backend state was retained for A, the MATH backend was scoped for B and restored on context exit. Neither T3 sampling nor the generation integrity policies were changed.

| Speech tokens | A median (s) | B median (s) | Change | Maximum waveform difference |
|---|---:|---:|---:|---:|
| 92 | 1.011025 | 1.674605 | +65.63% | 2.4e-06 |
| 77 | 0.990037 | 1.698482 | +71.56% | 3.87e-06 |
| 146 | 1.274000 | 2.174203 | +70.66% | 3.72e-05 |

Verdict: regression (approximately 66–72% slower for the measured S3 stage). Not installed. Output numerical differences are recorded; they are not a user listening PASS.

## Interpretation and bounds

These are model-stage screens, not end-to-end production A/B benchmarks. No candidate reached the production verification stage, so no production First Audio improvement, gap improvement, physical speaker timing, long-document quality PASS or additional regression test PASS is claimed. Whole-generation predictions must not be extrapolated from these isolated stage results. No new automatic candidate is attempted after the two ineffective screens.

Potential larger improvements would require additional separately assessed techniques. This experiment does not prove that 25% improvement is impossible, only that the two safe execution changes examined did not achieve it.

## Recovery / final status

HEAD/main unchanged: 5ab257fc6039101d67b80a9352ff16228f2126e0. Active release unchanged: 7161efd1b55637e0. Source/install/baseline engine byte parity verified. ready=true, model_ready=true, playback_available=true, last_error=null. Core unchanged. No commit or push. No production optimization candidate remains installed.

Raw data and diagnostic scripts: ~/.local/state/codex_enikk/inference-speed-20261007. diagnosis.json, cudnn-results.json, math-attention-results.json, s3-profile.json, s3-trace.json, start.json and finish.json are retained, including all measured values.

## Primary API references

- [PyTorch 2.6 backend controls](https://docs.pytorch.org/docs/2.6/backends.html)
- [PyTorch 2.6 scaled dot-product attention](https://docs.pytorch.org/docs/2.6/generated/torch.nn.functional.scaled_dot_product_attention.html)
- [PyTorch 2.6 CUDA measurement / graph constraints](https://docs.pytorch.org/docs/2.6/notes/cuda.html)
