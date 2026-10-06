작성자: 에닉(유키짱)

# 단위 100개 교육 후 Production 재벤치마크 B

## 결과 요약

현재 production이 units100 교육 코드를 포함하는 것을 확인한 뒤, 원본 100줄을 순서대로 한 번씩 production TTS에 제출했어. normalization은 사용자 확정값 기준 100/100 exact였고, 실제 재생 성공은 75/100이야.

- 입력: `/home/ak/git/codex_enikk-education/1_tts-units-100.txt` — 100 lines, 850 bytes, SHA-256 `c30773e80b6c48fe92afc49c88637d850842a0743c7772c539b2b1f1c91d16d2`
- Production normalization accuracy: **100/100** (A: 0/100, +100 percentage points)
- Delivery: **75 PLAYED / 25 FAILED_EXPLICITLY**, success 75.00% (A: 54/46, +21 percentage points; failed items -45.65%)
- Run ID: `6b55260418c0460e9b543def1c2a9a48`; benchmark item namespace: `units100-prod-edu-073cf8b3c0d8`

## Production 및 benchmark 조건

- Main/origin/main: `39f9a3b85d3b404d79b6a94a12fcce80d2a042a7`; education commit이 main의 ancestor임을 확인했어.
- Active release: `43a89707c02f3364`; TTS service PID `4046865`, engine PID `4046870`, service generation `412af561baa844c1a44728267377346a`, model ready: yes.
- Active release manifest의 normalizer SHA-256: `311806fe33dad99f02da12e32a993946491ff2cade38fd594493c7a9cdcf29a5`, override SHA-256: `771dfa5702b31b8284773e0ff976818af3ff86a2646551659e73a5f3fd80e400`, Chatterbox engine SHA-256: `4784bf5fd6ea57da05b65a23490773761aafd6c887845eae99daca4a9ae5df9a`.
- 활성 release, engine 및 normalization hash는 benchmark 전후 동일했고, benchmark 동안 production code/config 수정이나 restart는 없었어.
- Benchmark 시작 전에 대기열은 비어 있었어. 제출은 `100` source lines, 각각 1회; 마지막 playback 완료 후 unrelated 메시지는 측정 구간 밖이었어.
- Model: Chatterbox; reference: `/home/ak/Apps/chatterbox-yuki/yuki_super-clean.wav`; playback path: 1.25x pitch-preserving; GPU detail은 수집하지 않았어.
- Start: 2026-10-06T18:21:38 (first source submit monotonic `618352.216915`); last source submit monotonic `618354.251990`.
- Last benchmark playback completion: 2026-10-06T18:26:19 (monotonic `618633.681027`).

## 100개 정규화 및 delivery 결과

`Exact`는 active production normalizer 출력과 사용자 우선 expected reading의 UTF-8 exact 비교야. `Actual TTS`는 production delivery receipt야.

| # | Raw | Current normalized | Expected | Exact | Actual TTS |
|---:|---|---|---|---|---|
| 1 | `100 kb/s` | 백 킬로바이트 퍼 세컨드 | 백 킬로바이트 퍼 세컨드 | PASS | FAILED_EXPLICITLY |
| 2 | `1000 ms` | 천 밀리세컨드 | 천 밀리세컨드 | PASS | PLAYED |
| 3 | `225 block/s` | 천 블락스 퍼 세컨드 | 천 블락스 퍼 세컨드 | PASS | PLAYED |
| 4 | `50 MB/s` | 오십 메가바이트 퍼 세컨드 | 오십 메가바이트 퍼 세컨드 | PASS | PLAYED |
| 5 | `1.5 GB/s` | 일 쩜 오 기가바이트 퍼 세컨드 | 일 쩜 오 기가바이트 퍼 세컨드 | PASS | PLAYED |
| 6 | `250 Mbps` | 이백오십 메가비트 퍼 세컨드 | 이백오십 메가비트 퍼 세컨드 | PASS | PLAYED |
| 7 | `1 Gbps` | 일 기가비트 퍼 세컨드 | 일 기가비트 퍼 세컨드 | PASS | PLAYED |
| 8 | `32 kB` | 삼십이 킬로바이트 | 삼십이 킬로바이트 | PASS | PLAYED |
| 9 | `64 KB` | 육십사 킬로바이트 | 육십사 킬로바이트 | PASS | PLAYED |
| 10 | `128 MB` | 백이십팔 메가바이트 | 백이십팔 메가바이트 | PASS | PLAYED |
| 11 | `8 GB` | 팔 기가바이트 | 팔 기가바이트 | PASS | PLAYED |
| 12 | `16 GiB` | 십육 기비바이트 | 십육 기비바이트 | PASS | FAILED_EXPLICITLY |
| 13 | `500 µs` | 오백 마이크로세컨드 | 오백 마이크로세컨드 | PASS | PLAYED |
| 14 | `2 s` | 이 초 | 이 초 | PASS | PLAYED |
| 15 | `30 sec` | 삼십 세컨드 | 삼십 세컨드 | PASS | PLAYED |
| 16 | `5 min` | 오 분 | 오 분 | PASS | FAILED_EXPLICITLY |
| 17 | `2 h` | 이 시간 | 이 시간 | PASS | PLAYED |
| 18 | `24 hr` | 이십사 아워 | 이십사 아워 | PASS | PLAYED |
| 19 | `60 Hz` | 육십 헤르츠 | 육십 헤르츠 | PASS | FAILED_EXPLICITLY |
| 20 | `144 Hz` | 백사십사 헤르츠 | 백사십사 헤르츠 | PASS | PLAYED |
| 21 | `3.2 GHz` | 삼 쩜 이 기가헤르츠 | 삼 쩜 이 기가헤르츠 | PASS | PLAYED |
| 22 | `450 MHz` | 사백오십 메가헤르츠 | 사백오십 메가헤르츠 | PASS | PLAYED |
| 23 | `25 kHz` | 이십오 킬로헤르츠 | 이십오 킬로헤르츠 | PASS | PLAYED |
| 24 | `48 kHz` | 사십팔 킬로헤르츠 | 사십팔 킬로헤르츠 | PASS | FAILED_EXPLICITLY |
| 25 | `96 kHz` | 구십육 킬로헤르츠 | 구십육 킬로헤르츠 | PASS | FAILED_EXPLICITLY |
| 26 | `220 V` | 이백이십 볼트 | 이백이십 볼트 | PASS | FAILED_EXPLICITLY |
| 27 | `12 V` | 십이 볼트 | 십이 볼트 | PASS | FAILED_EXPLICITLY |
| 28 | `5 A` | 오 암페어 | 오 암페어 | PASS | PLAYED |
| 29 | `750 W` | 칠백오십 와트 | 칠백오십 와트 | PASS | PLAYED |
| 30 | `65 W` | 육십오 와트 | 육십오 와트 | PASS | FAILED_EXPLICITLY |
| 31 | `85 °C` | 팔십오 도씨 | 팔십오 도씨 | PASS | FAILED_EXPLICITLY |
| 32 | `37 °C` | 삼십칠 도씨 | 삼십칠 도씨 | PASS | PLAYED |
| 33 | `10%` | 십 퍼센트 | 십 퍼센트 | PASS | PLAYED |
| 34 | `99.9%` | 구십구 쩜 구 퍼센트 | 구십구 쩜 구 퍼센트 | PASS | PLAYED |
| 35 | `0.1%` | 영 쩜 일 퍼센트 | 영 쩜 일 퍼센트 | PASS | FAILED_EXPLICITLY |
| 36 | `250 tx/s` | 이백오십 티엑스 퍼 세컨드 | 이백오십 티엑스 퍼 세컨드 | PASS | PLAYED |
| 37 | `1200 tx/min` | 천이백 티엑스 퍼 분 | 천이백 티엑스 퍼 분 | PASS | PLAYED |
| 38 | `32 peer/s` | 삼십이 피어 퍼 세컨드 | 삼십이 피어 퍼 세컨드 | PASS | PLAYED |
| 39 | `8 peer/min` | 팔 피어 퍼 분 | 팔 피어 퍼 분 | PASS | PLAYED |
| 40 | `15 node/s` | 십오 노드 퍼 세컨드 | 십오 노드 퍼 세컨드 | PASS | FAILED_EXPLICITLY |
| 41 | `120 req/s` | 백이십 알이큐 퍼 세컨드 | 백이십 알이큐 퍼 세컨드 | PASS | PLAYED |
| 42 | `500 request/s` | 오백 리퀘스트 퍼 세컨드 | 오백 리퀘스트 퍼 세컨드 | PASS | PLAYED |
| 43 | `300 msg/s` | 삼백 메시지 퍼 세컨드 | 삼백 메시지 퍼 세컨드 | PASS | FAILED_EXPLICITLY |
| 44 | `90 packet/s` | 구십 패킷 퍼 세컨드 | 구십 패킷 퍼 세컨드 | PASS | PLAYED |
| 45 | `75 event/s` | 칠십오 이벤트 퍼 세컨드 | 칠십오 이벤트 퍼 세컨드 | PASS | PLAYED |
| 46 | `42 job/s` | 사십이 잡 퍼 세컨드 | 사십이 잡 퍼 세컨드 | PASS | PLAYED |
| 47 | `18 task/s` | 십팔 태스크 퍼 세컨드 | 십팔 태스크 퍼 세컨드 | PASS | PLAYED |
| 48 | `7 thread/s` | 칠 스레드 퍼 세컨드 | 칠 스레드 퍼 세컨드 | PASS | PLAYED |
| 49 | `4 process/s` | 사 프로세스 퍼 세컨드 | 사 프로세스 퍼 세컨드 | PASS | PLAYED |
| 50 | `60 frame/s` | 육십 프레임 퍼 세컨드 | 육십 프레임 퍼 세컨드 | PASS | PLAYED |
| 51 | `30 fps` | 삼십 에프피에스 | 삼십 에프피에스 | PASS | FAILED_EXPLICITLY |
| 52 | `120 fps` | 백이십 에프피에스 | 백이십 에프피에스 | PASS | FAILED_EXPLICITLY |
| 53 | `2 block/min` | 이 블록 퍼 분 | 이 블록 퍼 분 | PASS | PLAYED |
| 54 | `6 block/h` | 육 블록 퍼 시간 | 육 블록 퍼 시간 | PASS | FAILED_EXPLICITLY |
| 55 | `144 block/day` | 백사십사 블록 퍼 데이 | 백사십사 블록 퍼 데이 | PASS | PLAYED |
| 56 | `250 hash/s` | 이백오십 해시 퍼 세컨드 | 이백오십 해시 퍼 세컨드 | PASS | PLAYED |
| 57 | `1 kH/s` | 일 킬로해시 퍼 세컨드 | 일 킬로해시 퍼 세컨드 | PASS | PLAYED |
| 58 | `5 MH/s` | 오 메가해시 퍼 세컨드 | 오 메가해시 퍼 세컨드 | PASS | PLAYED |
| 59 | `2 GH/s` | 이 기가해시 퍼 세컨드 | 이 기가해시 퍼 세컨드 | PASS | PLAYED |
| 60 | `120 TH/s` | 백이십 테라해시 퍼 세컨드 | 백이십 테라해시 퍼 세컨드 | PASS | PLAYED |
| 61 | `250 byte/s` | 이백오십 바이트 퍼 세컨드 | 이백오십 바이트 퍼 세컨드 | PASS | PLAYED |
| 62 | `4 kB/s` | 사 킬로바이트 퍼 세컨드 | 사 킬로바이트 퍼 세컨드 | PASS | PLAYED |
| 63 | `20 MB/min` | 이십 메가바이트 퍼 분 | 이십 메가바이트 퍼 분 | PASS | PLAYED |
| 64 | `1 GB/min` | 일 기가바이트 퍼 분 | 일 기가바이트 퍼 분 | PASS | PLAYED |
| 65 | `50 GB/day` | 오십 기가바이트 퍼 데이 | 오십 기가바이트 퍼 데이 | PASS | PLAYED |
| 66 | `2 TB/day` | 이 테라바이트 퍼 데이 | 이 테라바이트 퍼 데이 | PASS | PLAYED |
| 67 | `15 IOPS` | 십오 아이옵스 | 십오 아이옵스 | PASS | FAILED_EXPLICITLY |
| 68 | `500 IOPS` | 오백 아이옵스 | 오백 아이옵스 | PASS | FAILED_EXPLICITLY |
| 69 | `5000 IOPS` | 오천 아이옵스 | 오천 아이옵스 | PASS | PLAYED |
| 70 | `2 ms/op` | 이 밀리세컨드 퍼 오퍼레이션 | 이 밀리세컨드 퍼 오퍼레이션 | PASS | PLAYED |
| 71 | `10 op/s` | 십 오퍼레이션 퍼 세컨드 | 십 오퍼레이션 퍼 세컨드 | PASS | PLAYED |
| 72 | `200 call/s` | 이백 콜 퍼 세컨드 | 이백 콜 퍼 세컨드 | PASS | PLAYED |
| 73 | `80 query/s` | 팔십 쿼리 퍼 세컨드 | 팔십 쿼리 퍼 세컨드 | PASS | PLAYED |
| 74 | `25 write/s` | 이십오 라이트 퍼 세컨드 | 이십오 라이트 퍼 세컨드 | PASS | PLAYED |
| 75 | `40 read/s` | 사십 리드 퍼 세컨드 | 사십 리드 퍼 세컨드 | PASS | PLAYED |
| 76 | `64 connection/s` | 육십사 커넥션 퍼 세컨드 | 육십사 커넥션 퍼 세컨드 | PASS | PLAYED |
| 77 | `12 session/s` | 십이 세션 퍼 세컨드 | 십이 세션 퍼 세컨드 | PASS | PLAYED |
| 78 | `3 retry/s` | 삼 리트라이 퍼 세컨드 | 삼 리트라이 퍼 세컨드 | PASS | PLAYED |
| 79 | `5 error/min` | 오 에러 퍼 분 | 오 에러 퍼 분 | PASS | FAILED_EXPLICITLY |
| 80 | `1 fail/h` | 일 페일 퍼 시간 | 일 페일 퍼 시간 | PASS | FAILED_EXPLICITLY |
| 81 | `10 km/h` | 십 킬로미터 퍼 아워 | 십 킬로미터 퍼 아워 | PASS | PLAYED |
| 82 | `100 km/h` | 백 킬로미터 퍼 아워 | 백 킬로미터 퍼 아워 | PASS | PLAYED |
| 83 | `5 m/s` | 오 미터 퍼 세컨드 | 오 미터 퍼 세컨드 | PASS | PLAYED |
| 84 | `9.8 m/s²` | 구 쩜 팔 미터 퍼 세컨드 제곱 | 구 쩜 팔 미터 퍼 세컨드 제곱 | PASS | PLAYED |
| 85 | `1.2 MB` | 일 쩜 이 메가바이트 | 일 쩜 이 메가바이트 | PASS | PLAYED |
| 86 | `2.4 GB` | 이 쩜 사 기가바이트 | 이 쩜 사 기가바이트 | PASS | PLAYED |
| 87 | `0.5 ms` | 영 쩜 오 밀리세컨드 | 영 쩜 오 밀리세컨드 | PASS | FAILED_EXPLICITLY |
| 88 | `12.5 ms` | 십이 쩜 오 밀리세컨드 | 십이 쩜 오 밀리세컨드 | PASS | PLAYED |
| 89 | `250 ns` | 이백오십 나노세컨드 | 이백오십 나노세컨드 | PASS | PLAYED |
| 90 | `100 µs` | 백 마이크로세컨드 | 백 마이크로세컨드 | PASS | FAILED_EXPLICITLY |
| 91 | `3 core` | 삼 코어 | 삼 코어 | PASS | PLAYED |
| 92 | `8 core` | 팔 코어 | 팔 코어 | PASS | FAILED_EXPLICITLY |
| 93 | `16 core` | 십육 코어 | 십육 코어 | PASS | FAILED_EXPLICITLY |
| 94 | `32 thread` | 삼십이 스레드 | 삼십이 스레드 | PASS | PLAYED |
| 95 | `4096 byte` | 사천구십육 바이트 | 사천구십육 바이트 | PASS | PLAYED |
| 96 | `65536 byte` | 육만오천오백삼십육 바이트 | 육만오천오백삼십육 바이트 | PASS | PLAYED |
| 97 | `2048 bit` | 이천사십팔 비트 | 이천사십팔 비트 | PASS | PLAYED |
| 98 | `256 bit` | 이백오십육 비트 | 이백오십육 비트 | PASS | FAILED_EXPLICITLY |
| 99 | `64 bit` | 육십사 비트 | 육십사 비트 | PASS | PLAYED |
| 100 | `32 bit` | 삼십이 비트 | 삼십이 비트 | PASS | PLAYED |

## A/B delivery 및 실패 지표

| Metric | A before | B production | Change |
|---|---:|---:|---:|
| Normalization exact accuracy | 0/100 | 100/100 | +100 percentage points |
| Submitted / PLAYED / failed | 100 / 54 / 46 | 100 / 75 / 25 | success +21; failure -21 |
| Success rate | 54.00% | 75.00% | +21.00 pp (+38.89% relative) |
| FAILED_EXPLICITLY | 46 | 25 | -21 (-45.65%) |
| Generation attempts | 164 | 140 | -24 (-14.63%) |
| Retries | 64 | 40 | -24 (-37.50%) |
| First-attempt successes | 36 | 60 | +24 (+66.67%) |
| Retry successes | 18 | 15 | -3 |
| internal_long_tail rejected attempts | 108 | 65 | -43 (-39.81%) |
| recovery_split / recovery_accepted | 0 / 0 | 0 / 0 | no change |
| Waveform rejection / OOM / exception | 0 / 0 / 0 reported | 0 / 0 / 0 | no observed errors |
| First audio latency | 3.619 s | 6.543 s | +2.924 s (+80.78%) |
| First submission → last playback completion | 276.063 s | 281.464 s | +5.401 s (+1.96%) |
| First playback → last completion | 272.444 s | 274.922 s | +2.478 s (+0.91%) |

### Generation, audio, RTF 분포

B의 p95는 nearest-rank 방식이야. source item generation time은 각 item의 모든 attempt duration 합계; successful generation은 성공한 attempt duration; RTF는 성공 item의 accepted generation duration ÷ generated audio duration이야.

| Metric (seconds except RTF) | A min / median / p95 / max / mean | B min / median / p95 / max / mean |
|---|---|---|
| Per-item generation, all attempts | 1.199 / 2.769 / 4.032 / 5.242 / 2.634 | 1.162 / 1.813 / 5.034 / 5.200 / 2.694 |
| Individual attempt duration | 1.026 / 1.569 / 2.393 / 2.708 / 1.606 | 1.162 / 1.827 / 2.600 / 2.975 / 1.924 |
| Successful item generation duration | 0.751 / 1.191 / 3.295 / 3.574 / 1.511 | 1.162 / 1.594 / 2.279 / 2.528 / 1.628 |
| Successful generated audio duration | 0.660 / 1.560 / 2.440 / 2.760 / 1.551 | 0.640 / 1.580 / 3.000 / 3.600 / 1.674 |
| Successful RTF | 0.751 / 1.191 / 3.295 / 3.574 / 1.511 | 0.699 / 1.005 / 1.267 / 1.816 / 1.022 |

B generated audio total: `125.580` s; 1.25x estimated audible duration: `100.464` s. A report’s RTF values mirror its successful-generation-time values, so its RTF aggregation cannot be confirmed to use the same per-item audio denominator; treat the RTF rows as reported rather than a strict like-for-like delta.

### Gap 분포

첫 재생 전 idle은 제외했고, gap은 benchmark 재생물 사이의 `current playback start - previous playback done`으로 계산했어.

| Metric | A | B | Change |
|---|---:|---:|---:|
| gap count / median | 53 / 2.287 s | 74 / 0.301 s | median -86.84% |
| p95 / max / mean | 13.010 / 19.796 / 3.721 s | 9.625 / 17.166 / 2.201 s | p95 -26.01%; max -13.28%; mean -40.86% |
| >1 s / >2 s / >5 s | 31 / 28 / 14 | 27 / 23 / 16 | -12.90% / -17.86% / +14.29% |

## Accounting 및 해석

- 영수증 100개가 source line 1–100을 정확히 한 번씩 포함했어. Missing 0, duplicate 0, out-of-order 0. PLAYED 75개는 source 순서를 유지했어.
- 25개 실패는 모두 최종 `FAILED_EXPLICITLY`; `internal_long_tail` 거부 attempt 합계는 65였어. recovery split/accepted는 0/0, waveform rejection 0, OOM·예외도 benchmark job에서 관측되지 않았어.
- 성공률은 54%에서 75%로 개선됐고 retry 및 long-tail 횟수가 감소했어. 반면 단일 production run이므로 stochastic variation의 영향을 분리할 수 없어. 이 결과만으로 발음 자연스러움까지 판정하지는 않아.
- TTS benchmark는 교육 반영 production 상태에서 완료했어. 이번 작업 중 코드, 설정, release symlink를 변경하지 않았고 TTS/Enikk를 재시작하지 않았어.

EOF
