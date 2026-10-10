작성자: 에닉(유키짱)

# TTS 단위 100개 교육 전 A Baseline Benchmark

상태: **완료 (정규화 A + 실제 production TTS A)**

- benchmark corpus: `~/git/codex_enikk-education/1_tts-units-100.txt`
- source lines/chars/bytes: 100/845/850
- source SHA-256: `c30773e80b6c48fe92afc49c88637d850842a0743c7772c539b2b1f1c91d16d2`
- repository main commit: `a26223203bc12851e60d8c834965069f8d47e38c`
- production TTS code version: `2.2.0`, generation: `2ec53324179043d9a594d76842472514`, service generation: `65a64a83c6cd40d5a186d6fc127d9756`
- source/install parity: PASS
- normalization source SHA-256: `311806fe33dad99f02da12e32a993946491ff2cade38fd594493c7a9cdcf29a5`
- custom override SHA-256: `c5c064283888e1a1fc161bafec4cfe17a1a0498b962196e906281aa7d4aa13cb`
- TTS engine SHA-256: `4784bf5fd6ea57da05b65a23490773761aafd6c887845eae99daca4a9ae5df9a`
- TTS service PID: `3825938`; engine PID: `3884921`; Enikk PID: `3873587`; trigger PID: `3873752`
- thread ID: `<redacted-session-id>`; model: Chatterbox; reference: `~/Apps/chatterbox-yuki/yuki_super-clean.wav`; playback speed: `1.25x`
- upstream backend: production normalizer is custom-only; NeMo process absent in the production run snapshot
- GPU/device detail: not captured for this benchmark

## Expected reading policy

정수는 한자어 수사로 읽고 십·백·천 단위 앞의 불필요한 `일`은 생략했다(예: 백, 천, 천이백, 육만오천오백삼십육). 소수는 `쩜` 뒤 숫자를 하나씩 읽는다. bit/byte 대소문자 구별을 유지한다. 사용자가 직접 제시한 예시 20개는 그대로 반영했다. 그 밖의 단위/약어는 정형 기술발음으로 정리한 교육 기대값이며, 단위 `s/sec/min/h/hr`, 약어 `req/msg/fps`, `block/day`의 세부 표현은 사용자 확정값이 아니므로 교육 완료 전 검토 후보로 표시한다.

## Current normalization exact comparison

- CURRENT_ACCURACY=0/100 (corrected expected table; all current normalized strings differ)
- Current output came from the active installed production normalizer; exact UTF-8 string equality.

| # | Raw input | Expected Korean reading | Current normalized output | Exact | Actual TTS |
|---:|---|---|---|---|---|
| 1 | `100 kb/s` | 백 킬로비트 퍼 세컨드 | `100 kb/s` | FAIL | PLAYED |
| 2 | `1000 ms` | 천 밀리세컨드 | `1000 ms` | FAIL | FAILED_EXPLICITLY |
| 3 | `225 block/s` | 이백이십오 블록 퍼 세컨드 | `225 block/s` | FAIL | FAILED_EXPLICITLY |
| 4 | `50 MB/s` | 오십 메가바이트 퍼 세컨드 | `50 MB/s` | FAIL | FAILED_EXPLICITLY |
| 5 | `1.5 GB/s` | 일 쩜 오 기가바이트 퍼 세컨드 | `1.5 GB/s` | FAIL | FAILED_EXPLICITLY |
| 6 | `250 Mbps` | 이백오십 메가비트 퍼 세컨드 | `250 Mbps` | FAIL | FAILED_EXPLICITLY |
| 7 | `1 Gbps` | 일 기가비트 퍼 세컨드 | `1 Gbps` | FAIL | PLAYED |
| 8 | `32 kB` | 삼십이 킬로바이트 | `32 kB` | FAIL | FAILED_EXPLICITLY |
| 9 | `64 KB` | 육십사 킬로바이트 | `64 KB` | FAIL | FAILED_EXPLICITLY |
| 10 | `128 MB` | 백이십팔 메가바이트 | `128 MB` | FAIL | FAILED_EXPLICITLY |
| 11 | `8 GB` | 팔 기가바이트 | `8 GB` | FAIL | FAILED_EXPLICITLY |
| 12 | `16 GiB` | 십육 기비바이트 | `16 GiB` | FAIL | PLAYED |
| 13 | `500 µs` | 오백 마이크로세컨드 | `500 µs` | FAIL | PLAYED |
| 14 | `2 s` | 이 초 | `2 s` | FAIL | FAILED_EXPLICITLY |
| 15 | `30 sec` | 삼십 세컨드 | `30 sec` | FAIL | FAILED_EXPLICITLY |
| 16 | `5 min` | 오 분 | `5 min` | FAIL | PLAYED |
| 17 | `2 h` | 이 시간 | `2 h` | FAIL | FAILED_EXPLICITLY |
| 18 | `24 hr` | 이십사 아워 | `24 hr` | FAIL | FAILED_EXPLICITLY |
| 19 | `60 Hz` | 육십 헤르츠 | `60 Hz` | FAIL | FAILED_EXPLICITLY |
| 20 | `144 Hz` | 백사십사 헤르츠 | `144 Hz` | FAIL | PLAYED |
| 21 | `3.2 GHz` | 삼 쩜 이 기가헤르츠 | `3.2 GHz` | FAIL | FAILED_EXPLICITLY |
| 22 | `450 MHz` | 사백오십 메가헤르츠 | `450 MHz` | FAIL | PLAYED |
| 23 | `25 kHz` | 이십오 킬로헤르츠 | `25 kHz` | FAIL | FAILED_EXPLICITLY |
| 24 | `48 kHz` | 사십팔 킬로헤르츠 | `48 kHz` | FAIL | FAILED_EXPLICITLY |
| 25 | `96 kHz` | 구십육 킬로헤르츠 | `96 kHz` | FAIL | FAILED_EXPLICITLY |
| 26 | `220 V` | 이백이십 볼트 | `220 V` | FAIL | FAILED_EXPLICITLY |
| 27 | `12 V` | 십이 볼트 | `12 V` | FAIL | PLAYED |
| 28 | `5 A` | 오 암페어 | `5 A` | FAIL | PLAYED |
| 29 | `750 W` | 칠백오십 와트 | `750 W` | FAIL | FAILED_EXPLICITLY |
| 30 | `65 W` | 육십오 와트 | `65 W` | FAIL | FAILED_EXPLICITLY |
| 31 | `85 °C` | 팔십오 도씨 | `85 °C` | FAIL | PLAYED |
| 32 | `37 °C` | 삼십칠 도씨 | `37 °C` | FAIL | PLAYED |
| 33 | `10%` | 십 퍼센트 | `10%` | FAIL | FAILED_EXPLICITLY |
| 34 | `99.9%` | 구십구 쩜 구 퍼센트 | `99.9%` | FAIL | FAILED_EXPLICITLY |
| 35 | `0.1%` | 영 쩜 일 퍼센트 | `0.1%` | FAIL | FAILED_EXPLICITLY |
| 36 | `250 tx/s` | 이백오십 티엑스 퍼 세컨드 | `250 tx/s` | FAIL | PLAYED |
| 37 | `1200 tx/min` | 천이백 티엑스 퍼 분 | `1200 tx/min` | FAIL | PLAYED |
| 38 | `32 peer/s` | 삼십이 피어 퍼 세컨드 | `32 peer/s` | FAIL | PLAYED |
| 39 | `8 peer/min` | 팔 피어 퍼 분 | `8 peer/min` | FAIL | PLAYED |
| 40 | `15 node/s` | 십오 노드 퍼 세컨드 | `15 node/s` | FAIL | PLAYED |
| 41 | `120 req/s` | 백이십 알이큐 퍼 세컨드 | `120 req/s` | FAIL | FAILED_EXPLICITLY |
| 42 | `500 request/s` | 오백 리퀘스트 퍼 세컨드 | `500 request/s` | FAIL | PLAYED |
| 43 | `300 msg/s` | 삼백 메시지 퍼 세컨드 | `300 msg/s` | FAIL | PLAYED |
| 44 | `90 packet/s` | 구십 패킷 퍼 세컨드 | `90 packet/s` | FAIL | PLAYED |
| 45 | `75 event/s` | 칠십오 이벤트 퍼 세컨드 | `75 event/s` | FAIL | FAILED_EXPLICITLY |
| 46 | `42 job/s` | 사십이 잡 퍼 세컨드 | `42 job/s` | FAIL | PLAYED |
| 47 | `18 task/s` | 십팔 태스크 퍼 세컨드 | `18 task/s` | FAIL | FAILED_EXPLICITLY |
| 48 | `7 thread/s` | 칠 스레드 퍼 세컨드 | `7 thread/s` | FAIL | PLAYED |
| 49 | `4 process/s` | 사 프로세스 퍼 세컨드 | `4 process/s` | FAIL | PLAYED |
| 50 | `60 frame/s` | 육십 프레임 퍼 세컨드 | `60 frame/s` | FAIL | PLAYED |
| 51 | `30 fps` | 삼십 에프피에스 | `30 fps` | FAIL | FAILED_EXPLICITLY |
| 52 | `120 fps` | 백이십 에프피에스 | `120 fps` | FAIL | FAILED_EXPLICITLY |
| 53 | `2 block/min` | 이 블록 퍼 분 | `2 block/min` | FAIL | PLAYED |
| 54 | `6 block/h` | 육 블록 퍼 시간 | `6 block/h` | FAIL | FAILED_EXPLICITLY |
| 55 | `144 block/day` | 백사십사 블록 퍼 데이 | `144 block/day` | FAIL | PLAYED |
| 56 | `250 hash/s` | 이백오십 해시 퍼 세컨드 | `250 hash/s` | FAIL | FAILED_EXPLICITLY |
| 57 | `1 kH/s` | 일 킬로해시 퍼 세컨드 | `1 kH/s` | FAIL | PLAYED |
| 58 | `5 MH/s` | 오 메가해시 퍼 세컨드 | `5 MH/s` | FAIL | FAILED_EXPLICITLY |
| 59 | `2 GH/s` | 이 기가해시 퍼 세컨드 | `2 GH/s` | FAIL | FAILED_EXPLICITLY |
| 60 | `120 TH/s` | 백이십 테라해시 퍼 세컨드 | `120 TH/s` | FAIL | PLAYED |
| 61 | `250 byte/s` | 이백오십 바이트 퍼 세컨드 | `250 byte/s` | FAIL | FAILED_EXPLICITLY |
| 62 | `4 kB/s` | 사 킬로바이트 퍼 세컨드 | `4 kB/s` | FAIL | PLAYED |
| 63 | `20 MB/min` | 이십 메가바이트 퍼 분 | `20 MB/min` | FAIL | PLAYED |
| 64 | `1 GB/min` | 일 기가바이트 퍼 분 | `1 GB/min` | FAIL | PLAYED |
| 65 | `50 GB/day` | 오십 기가바이트 퍼 데이 | `50 GB/day` | FAIL | PLAYED |
| 66 | `2 TB/day` | 이 테라바이트 퍼 데이 | `2 TB/day` | FAIL | PLAYED |
| 67 | `15 IOPS` | 십오 아이옵스 | `15 IOPS` | FAIL | PLAYED |
| 68 | `500 IOPS` | 오백 아이옵스 | `500 IOPS` | FAIL | FAILED_EXPLICITLY |
| 69 | `5000 IOPS` | 오천 아이옵스 | `5000 IOPS` | FAIL | PLAYED |
| 70 | `2 ms/op` | 이 밀리세컨드 퍼 오퍼레이션 | `2 ms/op` | FAIL | FAILED_EXPLICITLY |
| 71 | `10 op/s` | 십 오퍼레이션 퍼 세컨드 | `10 op/s` | FAIL | FAILED_EXPLICITLY |
| 72 | `200 call/s` | 이백 콜 퍼 세컨드 | `200 call/s` | FAIL | PLAYED |
| 73 | `80 query/s` | 팔십 쿼리 퍼 세컨드 | `80 query/s` | FAIL | PLAYED |
| 74 | `25 write/s` | 이십오 라이트 퍼 세컨드 | `25 write/s` | FAIL | FAILED_EXPLICITLY |
| 75 | `40 read/s` | 사십 리드 퍼 세컨드 | `40 read/s` | FAIL | FAILED_EXPLICITLY |
| 76 | `64 connection/s` | 육십사 커넥션 퍼 세컨드 | `64 connection/s` | FAIL | PLAYED |
| 77 | `12 session/s` | 십이 세션 퍼 세컨드 | `12 session/s` | FAIL | FAILED_EXPLICITLY |
| 78 | `3 retry/s` | 삼 리트라이 퍼 세컨드 | `3 retry/s` | FAIL | PLAYED |
| 79 | `5 error/min` | 오 에러 퍼 분 | `5 error/min` | FAIL | PLAYED |
| 80 | `1 fail/h` | 일 페일 퍼 시간 | `1 fail/h` | FAIL | PLAYED |
| 81 | `10 km/h` | 십 킬로미터 퍼 아워 | `10 킬로미터 퍼 아워` | FAIL | PLAYED |
| 82 | `100 km/h` | 백 킬로미터 퍼 아워 | `100 킬로미터 퍼 아워` | FAIL | PLAYED |
| 83 | `5 m/s` | 오 미터 퍼 세컨드 | `5 m/s` | FAIL | PLAYED |
| 84 | `9.8 m/s²` | 구 쩜 팔 미터 퍼 세컨드 제곱 | `9.8 m/s²` | FAIL | PLAYED |
| 85 | `1.2 MB` | 일 쩜 이 메가바이트 | `1.2 MB` | FAIL | FAILED_EXPLICITLY |
| 86 | `2.4 GB` | 이 쩜 사 기가바이트 | `2.4 GB` | FAIL | FAILED_EXPLICITLY |
| 87 | `0.5 ms` | 영 쩜 오 밀리세컨드 | `0.5 ms` | FAIL | FAILED_EXPLICITLY |
| 88 | `12.5 ms` | 십이 쩜 오 밀리세컨드 | `12.5 ms` | FAIL | PLAYED |
| 89 | `250 ns` | 이백오십 나노세컨드 | `250 ns` | FAIL | FAILED_EXPLICITLY |
| 90 | `100 µs` | 백 마이크로세컨드 | `100 µs` | FAIL | FAILED_EXPLICITLY |
| 91 | `3 core` | 삼 코어 | `3 core` | FAIL | PLAYED |
| 92 | `8 core` | 팔 코어 | `8 core` | FAIL | PLAYED |
| 93 | `16 core` | 십육 코어 | `16 core` | FAIL | PLAYED |
| 94 | `32 thread` | 삼십이 스레드 | `32 thread` | FAIL | PLAYED |
| 95 | `4096 byte` | 사천구십육 바이트 | `4096 byte` | FAIL | PLAYED |
| 96 | `65536 byte` | 육만오천오백삼십육 바이트 | `65536 byte` | FAIL | PLAYED |
| 97 | `2048 bit` | 이천사십팔 비트 | `2048 bit` | FAIL | PLAYED |
| 98 | `256 bit` | 이백오십육 비트 | `256 bit` | FAIL | PLAYED |
| 99 | `64 bit` | 육십사 비트 | `64 bit` | FAIL | PLAYED |
| 100 | `32 bit` | 삼십이 비트 | `32 bit` | FAIL | FAILED_EXPLICITLY |

## Normalization performance A

Active production normalizer, 10 whole-corpus warm-up passes followed by 30 timed passes over the same 100 inputs. One iteration = 100 normalize() calls in a single process. Percentile uses nearest rank.

| Metric | Result |
|---|---:|
| total corpus time mean | 0.000805 s / 100 |
| total corpus time median | 0.000783 s / 100 |
| p95 | 0.000904 s / 100 |
| per-item median | 0.007835 ms |
| throughput (median) | 127638.3 items/s |
| all 30 iteration times | `0.000786, 0.000794, 0.000792, 0.000772, 0.000770, 0.000778, 0.000785, 0.000772, 0.000773, 0.000842, 0.000839, 0.000812, 0.000771, 0.000774, 0.000790, 0.000834, 0.000835, 0.000772, 0.000787, 0.000772, 0.000785, 0.000904, 0.000782, 0.000767, 0.000776, 0.000774, 0.000773, 0.000772, 0.000841, 0.001129` |

## Actual production TTS performance A

- Delivery accounting: submitted=100; PLAYED=54; FAILED_EXPLICITLY=46; stale=0; missing=0; duplicate=0; one source part per item; source-order preserved among playable receipts.
- Timing window: first source submission 2026-10-06T14:43:47.495+09:00; last source submission 2026-10-06T14:43:48.048+09:00; first playback 2026-10-06T14:43:51.114+09:00; last playback completion 2026-10-06T14:48:23.559+09:00.
- first playback to last completion: 272.444s; first submission to last completion: 276.063s; first audio latency from first submission: 3.619s.
- Generation attempts=164; retry attempts=64; first-attempt successes=36; successful retry deliveries=18; internal_long_tail rejected attempts=108; recovery_split=0; recovery_accepted=0; waveform rejections=0; final failures=46; OOM/exception=0 reported in this run.
- Generation duration per item (all attempts summed): min/median/p95/max/mean = 1.199/2.769/4.032/5.242/2.634s.
- Individual attempt duration: min/median/p95/max/mean = 1.026/1.569/2.393/2.708/1.606s.
- Successful item generation duration: min/median/p95/max/mean = 0.751/1.191/3.295/3.574/1.511s.
- Successful audio duration per item: min/median/p95/max/mean = 0.660/1.560/2.440/2.760/1.551s; total playable audio=83.780s; estimated audible at 1.25x=67.024s.
- Successful RTF generation/audio: min/median/p95/max/mean = 0.751/1.191/3.295/3.574/1.511.
- Inter-playback gaps excluding initial idle: n/median/p95/max/mean = 53/2.287/13.010/19.796/3.721s; >1s=31, >2s=28, >5s=14.
- Preprocessing latency n/median/p95/max/mean=100/0.000122/0.000214/0.000273/0.000138s.
- Run ID `2ec53324179043d9a594d76842472514`; source item `units100-benchmark`; all 100 receipts persisted under `~/.local/state/enikk_tts/runs/run-2ec53324179043d9a594d76842472514/jobs`; raw WAV was not copied to the repository.

## TTS failure analysis

46 inputs ended FAILED_EXPLICITLY. Logs attribute final failures to repeated `internal_long_tail` rejection after two attempts. The one-token/short technical expressions were not split for recovery, so no recovery path ran. These are generation/guard outcomes; they were not normalized or reworded during A. The baseline benchmark intentionally left these results unchanged.

## Limits and follow-up gate

This is the immutable pre-education A baseline. It records the 100-item normalization and real production TTS run. Exact expected spellings beyond the user-listed examples are conventional proposals; ambiguous spellings listed above must be resolved before treating the education corpus as a final pronunciation specification. The 54/100 successful TTS delivery rate is an A metric; no claim of acoustic correctness was made from ASR or from generated delivery alone.

CODE_CHANGED=no
PRODUCTION_CHANGED=no
ENIKK_RESTARTED=no

EOF
