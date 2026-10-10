작성자: 에닉(유키짱)

# First Audio 최적화 — 2026-10-07

최종 판정: **INCONCLUSIVE**. 안전하고 재현 가능한 전체 First Audio 개선을 확인하지 못함. 후보 3개 사용 및 연속 무효 후보 2개로 자동 최적화 종료. 모든 후보 소스/production 원복.

작업 시작 2026-10-07T02:24:59+09:00, 종료 2026-10-07T03:31:42.001939+09:00, 누적 66.7분. 최대 3시간/후보 3개 한도 준수. 최초 병목은 02:29에 특정했다.

시작/최종 Git HEAD `ee6d50c248cfe28dc7c24de05e0ba8e87c4817c8` / `ee6d50c248cfe28dc7c24de05e0ba8e87c4817c8`. 시작/최종 release `d5a81f0e2e5a41ce` / `d5a81f0e2e5a41ce`. commit/push: 최적화 commit/merge/push 없음; main == origin/main, 원래 코드 유지.

## 측정 정의와 한계

First Audio는 source 제출 직전 monotonic 시각부터 PulseAudio `jack_out.monitor`에서 처음 |amplitude| > 0.001인 sample이 확인될 때까지다. 모델/큐 대기, 거부, retry, recovery, 재생 준비가 포함된다. 기존 playback start 로그는 ffmpeg/tempo 변환과 paplay 이전의 dispatch로 확인되어 별도 지표로만 보존했다. 물리 스피커 시작/종료는 UNMEASURED이며 backend 측정을 물리 장치 시각으로 주장하지 않는다.

GTX 1080, 같은 reference/tempo 1.25/제출 경로/입력, ready+model_ready, queue empty, fixed idle 2s 조건. 재시작 후 고정 한국어 warmup 1회는 별도 파일로 기록했다. A는 최초 10회와 안정 release로 돌아온 뒤 10회를 모두 포함해 총 20회이며 두 service lifecycle를 데이터에 보존했다. 실행 순서는 A1~10 → B1 → B2 → A11~20 → B3이며 완전 무작위 교차 실험은 아니다. 불리한 run을 제외하거나 교체하지 않았다. p90/p95는 nearest-rank다.

## First Audio 결과 (초)

| 그룹 | n | min | median | mean | p90 | p95 | max | stddev | CV | retry | long-tail | 실패 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A-hash | 20 | 3.440 | 3.750 | 4.524 | 7.374 | 8.011 | 12.511 | 2.196 | 0.485 | 3 | 4 | 0 |
| A-korean | 20 | 2.671 | 3.029 | 4.701 | 9.718 | 10.011 | 10.165 | 2.590 | 0.551 | 8 | 11 | 0 |
| B1-hash | 10 | 2.177 | 2.378 | 3.384 | 5.150 | 5.213 | 5.213 | 1.362 | 0.403 | 6 | 6 | 0 |
| B1-korean | 10 | 2.020 | 3.297 | 3.353 | 4.727 | 4.746 | 4.746 | 1.278 | 0.381 | 6 | 6 | 0 |
| B2-hash | 20 | 3.487 | 3.687 | 4.651 | 7.523 | 7.798 | 11.681 | 2.140 | 0.460 | 4 | 5 | 0 |
| B2-korean | 20 | 2.593 | 2.851 | 4.125 | 6.282 | 9.672 | 10.013 | 2.285 | 0.554 | 6 | 8 | 0 |
| B3-hash | 20 | 3.489 | 3.730 | 4.705 | 7.261 | 11.957 | 11.998 | 2.548 | 0.541 | 3 | 5 | 0 |
| B3-korean | 20 | 2.652 | 2.899 | 4.527 | 6.110 | 9.990 | 12.184 | 2.591 | 0.572 | 9 | 11 | 0 |

| 그룹 | >2s | >3s | >5s | >10s |
|---|---:|---:|---:|---:|
| A-hash | 20 | 20 | 3 | 1 |
| A-korean | 20 | 12 | 8 | 2 |
| B1-hash | 10 | 4 | 2 | 0 |
| B1-korean | 10 | 5 | 0 | 0 |
| B2-hash | 20 | 20 | 4 | 1 |
| B2-korean | 20 | 9 | 6 | 1 |
| B3-hash | 20 | 20 | 3 | 2 |
| B3-korean | 20 | 8 | 8 | 1 |

### Raw First Audio (제출 순서)

**A-hash**: 3.738195, 3.863828, 3.590421, 12.510533, 3.763137, 3.614583, 3.484570, 3.593578, 3.891475, 3.599879, 8.010958, 7.374494, 3.784635, 3.676582, 3.852077, 3.484507, 3.439774, 3.808161, 3.762473, 3.640119

**A-korean**: 2.707791, 3.000556, 2.741106, 5.982418, 2.671096, 10.164893, 9.717638, 5.721728, 10.011230, 2.803734, 6.193021, 6.199583, 2.693110, 2.698384, 3.039890, 3.018263, 2.764714, 3.122987, 2.760617, 5.997886

**B1-hash**: 2.181386, 2.176809, 5.213139, 5.150298, 4.849559, 2.341549, 2.378173, 2.200829, 4.975698, 2.377059

**B1-korean**: 2.070653, 2.165157, 2.057162, 4.746444, 4.727414, 4.702604, 4.532037, 2.078802, 4.429091, 2.019779

**B2-hash**: 3.833028, 3.487483, 3.768037, 3.550994, 3.762929, 3.723704, 3.618708, 3.701182, 3.700118, 3.674264, 3.643566, 3.642747, 7.523155, 3.658852, 3.528315, 7.798029, 7.498469, 3.655248, 3.572589, 11.680715

**B2-korean**: 2.862111, 2.716060, 2.761757, 6.282425, 2.669811, 2.593382, 3.040201, 10.012716, 9.672014, 2.697107, 3.014663, 2.625720, 5.759885, 2.673186, 2.632235, 3.060293, 2.818380, 5.770150, 5.998698, 2.840494

**B3-hash**: 3.681531, 3.538121, 3.591869, 3.870206, 11.998237, 3.721638, 3.743027, 3.849714, 7.260816, 3.576909, 3.623636, 3.689481, 3.892258, 3.739202, 3.572355, 3.909387, 11.957317, 3.592241, 3.804455, 3.488890

**B3-korean**: 5.774248, 5.833890, 2.779045, 2.760596, 2.804955, 2.737806, 2.799063, 2.848800, 2.652199, 2.830635, 2.997030, 2.731402, 5.703716, 5.726747, 2.694268, 2.950181, 9.990499, 5.634324, 12.183992, 6.110465

## 확인된 병목

느린 A-hash-4의 root generation은 3.941537 + 3.677739초, reference reset은 0.160894 + 0.152346초, recovery generation은 2.227421 + 2.245528초였다. First Audio는 12.510533초. queue/visible은 약 0.009초, preprocessing은 0.000183초다. 수초 지연의 주원인은 생성과 internal_long_tail 거부 후 retry/recovery였으며 normalizer scan은 아니다.

실제 흐름: Publisher 제출 → job 파일 가시화 → worker normalization/chunking → generate/guard → 필요시 reset/retry/recovery → WAV 준비 → playback dispatch → ffmpeg atempo → paplay → monitor onset. 순수 모델 GPU 구간, 정확한 enqueue/dequeue 단독 구간, 물리 장치 start/end는 미측정이다.

| 그룹 | submit→job visible median | preprocessing median | submit→첫 generate median |
|---|---:|---:|---:|
| A-hash | 0.024220s | 0.000231s | 0.030192s |
| A-korean | 0.022915s | 0.000145s | 0.028583s |
| B1-hash | 0.038921s | 0.000344s | 0.045037s |
| B1-korean | 0.041079s | 0.000253s | 0.048637s |
| B2-hash | 0.029121s | 0.000224s | 0.034927s |
| B2-korean | 0.038390s | 0.000153s | 0.044362s |
| B3-hash | 0.033137s | 0.000225s | 0.038968s |
| B3-korean | 0.029224s | 0.000146s | 0.035058s |

## 후보와 판정

1. **첫 청크 균형 분할**: 기존 recovery_clauses를 첫 청크에 적용했다. first prefix가 빨리 재생되는 run은 생겼으나 retry가 증가하고 새 청크 경계에서 약 3초의 대기가 발생했다. 한국어도 20회 A와 비교하면 개선을 확정할 수 없다. REGRESSION, 원복. 최초 10회 비교와 확대 20회 A 비교를 혼동하지 않는다.

2. **감시 외 attention 층 SDPA 유지**: alignment 층 9/12/13과 guard를 그대로 유지하고 나머지 27층의 공유 config를 분리했다. CPU tiny-Llama prompt/cached decode에서 hidden 최대 차이 4.77e-7, alignment 최대 차이 2.98e-8였고 관련 173개 테스트가 통과했다. 실제 hash First Audio 차이는 작고 전체 비교의 불확실성 구간은 0을 포함한다. INCONCLUSIVE, 원복.

3. **reference conditioning pristine cache**: 준비된 음성 tensor를 값으로 복사해 retry 시 복구하고 reference metadata가 변경되면 원래 prepare_conditionals로 돌아간다. 단순 deepcopy의 non-leaf Torch 호환성 문제는 안전 fallback에서 발견됐으며 같은 후보 안에서 detach().clone()으로 보완했다. 실제 CUDA tensor 값 동일/alias 분리 검증과 관련 173개 테스트 통과. 최초 비활성 cache release에서는 benchmark하지 않았다. 최종 판정/효과는 아래 값과 candidate metadata에 기록했다.

각 후보는 별개로 시험했으며 후보 3에 후보 1/2 코드를 섞지 않았다. guard/threshold/sampling/model weights/reference/tempo/sequence-gap/core 코드는 변경하지 않았다.

### retry conditioning reset (기존 로그 구간)

| 그룹 | reset 수 | median | cache hit |
|---|---:|---:|---:|
| A-hash | 4 | 0.161482s | 0 |
| A-korean | 11 | 0.149947s | 0 |
| B1-hash | 6 | 0.154012s | 0 |
| B1-korean | 6 | 0.150021s | 0 |
| B2-hash | 5 | 0.159172s | 0 |
| B2-korean | 8 | 0.154024s | 0 |
| B3-hash | 5 | 0.016595s | 5 |
| B3-korean | 11 | 0.015546s | 11 |

reset duration은 기존 로그 위치의 CPU/dispatch 경과값이다. GPU 복사 완료 시각 전체를 단독으로 확정하는 지표가 아니며, 부분 비용 감소를 First Audio 전체 개선으로 대체하지 않는다.

### 불확실성 진단

고정 seed의 분석용 5,000회 unpaired bootstrap으로 median/mean 차이의 기술적 구간을 함께 기록했다. 모델 생성 RNG는 건드리지 않았다. 표본이 적고 순차 cohort이므로 이 구간만으로 인과를 확정하지 않는다.

- B1 hash: median -36.60%, delta -1.372718s, bootstrap 95% 구간 [-1.5615149777731858, 1.298045655770693]s.
- B1 korean: median +8.85%, delta +0.268048s, bootstrap 95% 구간 [-3.7814204760361463, 1.767322865431197]s.
- B2 hash: median -1.68%, delta -0.063143s, bootstrap 95% 구간 [-0.15291303396224976, 0.10445331974187866]s.
- B2 korean: median -5.87%, delta -0.177774s, bootstrap 95% 구간 [-3.1529807780170813, 1.381012356840074]s.
- B3 hash: median -0.53%, delta -0.019914s, bootstrap 95% 구간 [-0.1551983252284117, 0.18150176847120747]s.
- B3 korean: median -4.28%, delta -0.129586s, bootstrap 95% 구간 [-3.0983958634897135, 2.766874975641258]s.

## 장문 중간 gap

고정 파일 `~/tts-text-for-bench.md`, SHA-256 `14825803bf1de37162d2c3544151cf99c6ac12d1da13408a4697f353637ee8dd`. A 전체 286 parts 중 PLAYED 285 / FAILED_EXPLICITLY 1, retry 54, long-tail 71, recovery split 16, missing/duplicate/out-of-order 0. 외부 playback contamination은 없었다.

Gap은 monitor에서 확인한 다음 청크 음성 시작에서 직전 paplay 완료 관측값을 뺀 대체 지표다. 첫 지연과 마지막 tail은 제외한다. 물리 playback 종료 시각은 미측정이며 paplay 완료를 물리 스피커 종료로 주장하지 않는다.

A gap sample 284: median 0.201106s, p95 2.868469s, max 10.173874s; >1s 21, >2s 17, >5s 10.

후보들의 First Audio 판정이 REGRESSION/INCONCLUSIVE이므로 후보 장문 최종 gap/독립 청취 PASS 검증은 진행하지 않았다. A의 전체 gap 원시값은 보존했고 gap 보호 완료라고 주장하지 않는다. 원래 release로 복구했으므로 후보를 production에 남기지 않았다.

## 음질/누락/회귀

Chatterbox voice/reference/model/sampling/tempo/guards를 유지했다. 사전 기능·runtime 검증은 후보 1 175개, 후보 2/3 각각 173개 통과. reference 변경/missing fallback과 request state alias 분리를 검증했고 clone는 실제 CUDA tensor 값과 동일했다. 짧은 benchmark receipt를 전수 점검해 missing/duplicate/order/foreign 여부를 JSON에 기록했다. 정상 재생 receipt를 주관적 음질 PASS로 간주하지 않는다. 독립 청취 평가가 완료되지 않은 후보는 음질 검증 완료라고 주장하지 않는다.

CPU thread 수를 16→1로 바꾸는 별도 진단도 했으나 원래 analyzer CPU 비용 차이가 1ms 미만이고 장문 case에서는 개선도 없어 실제 코드 후보로 만들지 않았다.

## 종료/복구 상태

후보 수 3, 최종 판정 INCONCLUSIVE, 도전 목표 달성 False. 안전하고 재현 가능한 전체 First Audio 개선을 확인하지 못함. 후보 3개 사용 및 연속 무효 후보 2개로 자동 최적화 종료. 모든 후보 소스/production 원복.

최종 release `d5a81f0e2e5a41ce`, state=ready, model_ready=True, playback_available=True, last_error=None.

Enikk/Codex core PID 및 시작 시각은 작업 전후 동일했다. 종료/강제종료/재시작하지 않았다. TTS 서비스만 임시 적용과 rollback을 위해 재시작했다. 실패/불확실 후보는 main commit/push하지 않았고 원래 소스와 production을 유지한다. 후보 patch와 원시 log/audio는 별도 상태 디렉터리에 보존했다.

남은 병목은 정상 첫 inference 자체의 수초 비용과 long-tail 거부/retry다. 다음 단계는 거부된 음성까지 보존해 판정이 실제 불량 음성과 일치하는지 감사하는 것이다. guard 완화·모델 변경·추가 후보를 자동으로 실행하지 않았다.

[전체 원시값·통계·receipt 감사](first-audio-optimization-20261007-data.json)

상태 자료: `~/.local/state/codex_enikk/first-audio-optimization-20261007`

EOF
