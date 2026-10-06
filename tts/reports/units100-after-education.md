작성자: 에닉(유키짱)

# 단위 100개 교육 후 Production TTS 재벤치마크

## 목적과 범위

교육 후 현재 production TTS를 동일한 100개 corpus로 측정한 B 결과야. 이 작업에서는 코드, 설정, 설치본을 수정하지 않았고 TTS나 Enikk를 재시작하지 않았어. 기존 A 보고서는 보존했어.

## 입력 및 실행 조건

- 입력: `/home/ak/git/codex_enikk-education/1_tts-units-100.txt`
- 줄/바이트: 100줄 / 850 bytes
- SHA-256: `c30773e80b6c48fe92afc49c88637d850842a0743c7772c539b2b1f1c91d16d2`
- 기준 A: `tts/reports/units100-before-education.md`
- main commit: `a26223203bc12851e60d8c834965069f8d47e38c`
- 현재 production release: `a492cdc27ea17847`; 측정 worker는 이전에 로드된 release `b37bd7a1ad4e1f59`였어.
- normalizer 및 TTS engine 해시는 A 기록과 일치했어. 따라서 이 B는 교육 변경이 production에 반영된 상태를 검증한 측정이 아니야. 현재 production 출력은 입력 원문 그대로였어.
- benchmark run: `f72c1d24d74e4e68b7e8970f1b040075`; 실행 전 queue는 비어 있었고 benchmark 시간대에 unrelated playback은 확인되지 않았어.
- Enikk PID 3873587 및 trigger PID 3873752 유지; TTS restart 없음.

## 정규화 결과

현재 production normalizer의 100개 결과는 모두 원문 문자열 그대로였어. A 보고서의 exact expected Korean reading과 비교하면 0/100 exact match야. 각 행의 normalized는 current production이 반환한 값이고, TTS 열은 해당 항목의 최종 delivery 결과야.

| # | Raw input | Current normalized | Expected Korean reading (A) | Exact | TTS |
|---:|---|---|---|---|---|
| 1 | `100 kb/s` | `100 kb/s` | 백 킬로비트 퍼 세컨드 | FAIL | PLAYED |
| 2 | `1000 ms` | `1000 ms` | 천 밀리세컨드 | FAIL | FAILED_EXPLICITLY |
| 3 | `225 block/s` | `225 block/s` | 이백이십오 블록 퍼 세컨드 | FAIL | PLAYED |
| 4 | `50 MB/s` | `50 MB/s` | 오십 메가바이트 퍼 세컨드 | FAIL | FAILED_EXPLICITLY |
| 5 | `1.5 GB/s` | `1.5 GB/s` | 일 쩜 오 기가바이트 퍼 세컨드 | FAIL | PLAYED |
| 6 | `250 Mbps` | `250 Mbps` | 이백오십 메가비트 퍼 세컨드 | FAIL | FAILED_EXPLICITLY |
| 7 | `1 Gbps` | `1 Gbps` | 일 기가비트 퍼 세컨드 | FAIL | PLAYED |
| 8 | `32 kB` | `32 kB` | 삼십이 킬로바이트 | FAIL | FAILED_EXPLICITLY |
| 9 | `64 KB` | `64 KB` | 육십사 킬로바이트 | FAIL | FAILED_EXPLICITLY |
| 10 | `128 MB` | `128 MB` | 백이십팔 메가바이트 | FAIL | FAILED_EXPLICITLY |
| 11 | `8 GB` | `8 GB` | 팔 기가바이트 | FAIL | PLAYED |
| 12 | `16 GiB` | `16 GiB` | 십육 기비바이트 | FAIL | FAILED_EXPLICITLY |
| 13 | `500 µs` | `500 µs` | 오백 마이크로세컨드 | FAIL | FAILED_EXPLICITLY |
| 14 | `2 s` | `2 s` | 이 초 | FAIL | PLAYED |
| 15 | `30 sec` | `30 sec` | 삼십 세컨드 | FAIL | PLAYED |
| 16 | `5 min` | `5 min` | 오 분 | FAIL | FAILED_EXPLICITLY |
| 17 | `2 h` | `2 h` | 이 시간 | FAIL | PLAYED |
| 18 | `24 hr` | `24 hr` | 이십사 아워 | FAIL | PLAYED |
| 19 | `60 Hz` | `60 Hz` | 육십 헤르츠 | FAIL | PLAYED |
| 20 | `144 Hz` | `144 Hz` | 백사십사 헤르츠 | FAIL | PLAYED |
| 21 | `3.2 GHz` | `3.2 GHz` | 삼 쩜 이 기가헤르츠 | FAIL | PLAYED |
| 22 | `450 MHz` | `450 MHz` | 사백오십 메가헤르츠 | FAIL | FAILED_EXPLICITLY |
| 23 | `25 kHz` | `25 kHz` | 이십오 킬로헤르츠 | FAIL | PLAYED |
| 24 | `48 kHz` | `48 kHz` | 사십팔 킬로헤르츠 | FAIL | PLAYED |
| 25 | `96 kHz` | `96 kHz` | 구십육 킬로헤르츠 | FAIL | FAILED_EXPLICITLY |
| 26 | `220 V` | `220 V` | 이백이십 볼트 | FAIL | FAILED_EXPLICITLY |
| 27 | `12 V` | `12 V` | 십이 볼트 | FAIL | FAILED_EXPLICITLY |
| 28 | `5 A` | `5 A` | 오 암페어 | FAIL | PLAYED |
| 29 | `750 W` | `750 W` | 칠백오십 와트 | FAIL | FAILED_EXPLICITLY |
| 30 | `65 W` | `65 W` | 육십오 와트 | FAIL | FAILED_EXPLICITLY |
| 31 | `85 °C` | `85 °C` | 팔십오 도씨 | FAIL | PLAYED |
| 32 | `37 °C` | `37 °C` | 삼십칠 도씨 | FAIL | PLAYED |
| 33 | `10%` | `10%` | 십 퍼센트 | FAIL | FAILED_EXPLICITLY |
| 34 | `99.9%` | `99.9%` | 구십구 쩜 구 퍼센트 | FAIL | FAILED_EXPLICITLY |
| 35 | `0.1%` | `0.1%` | 영 쩜 일 퍼센트 | FAIL | FAILED_EXPLICITLY |
| 36 | `250 tx/s` | `250 tx/s` | 이백오십 티엑스 퍼 세컨드 | FAIL | PLAYED |
| 37 | `1200 tx/min` | `1200 tx/min` | 천이백 티엑스 퍼 분 | FAIL | PLAYED |
| 38 | `32 peer/s` | `32 peer/s` | 삼십이 피어 퍼 세컨드 | FAIL | FAILED_EXPLICITLY |
| 39 | `8 peer/min` | `8 peer/min` | 팔 피어 퍼 분 | FAIL | PLAYED |
| 40 | `15 node/s` | `15 node/s` | 십오 노드 퍼 세컨드 | FAIL | FAILED_EXPLICITLY |
| 41 | `120 req/s` | `120 req/s` | 백이십 알이큐 퍼 세컨드 | FAIL | FAILED_EXPLICITLY |
| 42 | `500 request/s` | `500 request/s` | 오백 리퀘스트 퍼 세컨드 | FAIL | FAILED_EXPLICITLY |
| 43 | `300 msg/s` | `300 msg/s` | 삼백 메시지 퍼 세컨드 | FAIL | FAILED_EXPLICITLY |
| 44 | `90 packet/s` | `90 packet/s` | 구십 패킷 퍼 세컨드 | FAIL | PLAYED |
| 45 | `75 event/s` | `75 event/s` | 칠십오 이벤트 퍼 세컨드 | FAIL | PLAYED |
| 46 | `42 job/s` | `42 job/s` | 사십이 잡 퍼 세컨드 | FAIL | PLAYED |
| 47 | `18 task/s` | `18 task/s` | 십팔 태스크 퍼 세컨드 | FAIL | PLAYED |
| 48 | `7 thread/s` | `7 thread/s` | 칠 스레드 퍼 세컨드 | FAIL | FAILED_EXPLICITLY |
| 49 | `4 process/s` | `4 process/s` | 사 프로세스 퍼 세컨드 | FAIL | FAILED_EXPLICITLY |
| 50 | `60 frame/s` | `60 frame/s` | 육십 프레임 퍼 세컨드 | FAIL | FAILED_EXPLICITLY |
| 51 | `30 fps` | `30 fps` | 삼십 에프피에스 | FAIL | FAILED_EXPLICITLY |
| 52 | `120 fps` | `120 fps` | 백이십 에프피에스 | FAIL | FAILED_EXPLICITLY |
| 53 | `2 block/min` | `2 block/min` | 이 블록 퍼 분 | FAIL | FAILED_EXPLICITLY |
| 54 | `6 block/h` | `6 block/h` | 육 블록 퍼 시간 | FAIL | FAILED_EXPLICITLY |
| 55 | `144 block/day` | `144 block/day` | 백사십사 블록 퍼 데이 | FAIL | PLAYED |
| 56 | `250 hash/s` | `250 hash/s` | 이백오십 해시 퍼 세컨드 | FAIL | PLAYED |
| 57 | `1 kH/s` | `1 kH/s` | 일 킬로해시 퍼 세컨드 | FAIL | FAILED_EXPLICITLY |
| 58 | `5 MH/s` | `5 MH/s` | 오 메가해시 퍼 세컨드 | FAIL | PLAYED |
| 59 | `2 GH/s` | `2 GH/s` | 이 기가해시 퍼 세컨드 | FAIL | PLAYED |
| 60 | `120 TH/s` | `120 TH/s` | 백이십 테라해시 퍼 세컨드 | FAIL | PLAYED |
| 61 | `250 byte/s` | `250 byte/s` | 이백오십 바이트 퍼 세컨드 | FAIL | FAILED_EXPLICITLY |
| 62 | `4 kB/s` | `4 kB/s` | 사 킬로바이트 퍼 세컨드 | FAIL | PLAYED |
| 63 | `20 MB/min` | `20 MB/min` | 이십 메가바이트 퍼 분 | FAIL | PLAYED |
| 64 | `1 GB/min` | `1 GB/min` | 일 기가바이트 퍼 분 | FAIL | PLAYED |
| 65 | `50 GB/day` | `50 GB/day` | 오십 기가바이트 퍼 데이 | FAIL | PLAYED |
| 66 | `2 TB/day` | `2 TB/day` | 이 테라바이트 퍼 데이 | FAIL | PLAYED |
| 67 | `15 IOPS` | `15 IOPS` | 십오 아이옵스 | FAIL | PLAYED |
| 68 | `500 IOPS` | `500 IOPS` | 오백 아이옵스 | FAIL | PLAYED |
| 69 | `5000 IOPS` | `5000 IOPS` | 오천 아이옵스 | FAIL | PLAYED |
| 70 | `2 ms/op` | `2 ms/op` | 이 밀리세컨드 퍼 오퍼레이션 | FAIL | PLAYED |
| 71 | `10 op/s` | `10 op/s` | 십 오퍼레이션 퍼 세컨드 | FAIL | PLAYED |
| 72 | `200 call/s` | `200 call/s` | 이백 콜 퍼 세컨드 | FAIL | PLAYED |
| 73 | `80 query/s` | `80 query/s` | 팔십 쿼리 퍼 세컨드 | FAIL | PLAYED |
| 74 | `25 write/s` | `25 write/s` | 이십오 라이트 퍼 세컨드 | FAIL | PLAYED |
| 75 | `40 read/s` | `40 read/s` | 사십 리드 퍼 세컨드 | FAIL | PLAYED |
| 76 | `64 connection/s` | `64 connection/s` | 육십사 커넥션 퍼 세컨드 | FAIL | PLAYED |
| 77 | `12 session/s` | `12 session/s` | 십이 세션 퍼 세컨드 | FAIL | PLAYED |
| 78 | `3 retry/s` | `3 retry/s` | 삼 리트라이 퍼 세컨드 | FAIL | PLAYED |
| 79 | `5 error/min` | `5 error/min` | 오 에러 퍼 분 | FAIL | PLAYED |
| 80 | `1 fail/h` | `1 fail/h` | 일 페일 퍼 시간 | FAIL | PLAYED |
| 81 | `10 km/h` | `10 km/h` | 십 킬로미터 퍼 아워 | FAIL | PLAYED |
| 82 | `100 km/h` | `100 km/h` | 백 킬로미터 퍼 아워 | FAIL | PLAYED |
| 83 | `5 m/s` | `5 m/s` | 오 미터 퍼 세컨드 | FAIL | FAILED_EXPLICITLY |
| 84 | `9.8 m/s²` | `9.8 m/s²` | 구 쩜 팔 미터 퍼 세컨드 제곱 | FAIL | FAILED_EXPLICITLY |
| 85 | `1.2 MB` | `1.2 MB` | 일 쩜 이 메가바이트 | FAIL | FAILED_EXPLICITLY |
| 86 | `2.4 GB` | `2.4 GB` | 이 쩜 사 기가바이트 | FAIL | FAILED_EXPLICITLY |
| 87 | `0.5 ms` | `0.5 ms` | 영 쩜 오 밀리세컨드 | FAIL | FAILED_EXPLICITLY |
| 88 | `12.5 ms` | `12.5 ms` | 십이 쩜 오 밀리세컨드 | FAIL | FAILED_EXPLICITLY |
| 89 | `250 ns` | `250 ns` | 이백오십 나노세컨드 | FAIL | FAILED_EXPLICITLY |
| 90 | `100 µs` | `100 µs` | 백 마이크로세컨드 | FAIL | PLAYED |
| 91 | `3 core` | `3 core` | 삼 코어 | FAIL | PLAYED |
| 92 | `8 core` | `8 core` | 팔 코어 | FAIL | PLAYED |
| 93 | `16 core` | `16 core` | 십육 코어 | FAIL | PLAYED |
| 94 | `32 thread` | `32 thread` | 삼십이 스레드 | FAIL | PLAYED |
| 95 | `4096 byte` | `4096 byte` | 사천구십육 바이트 | FAIL | FAILED_EXPLICITLY |
| 96 | `65536 byte` | `65536 byte` | 육만오천오백삼십육 바이트 | FAIL | PLAYED |
| 97 | `2048 bit` | `2048 bit` | 이천사십팔 비트 | FAIL | FAILED_EXPLICITLY |
| 98 | `256 bit` | `256 bit` | 이백오십육 비트 | FAIL | PLAYED |
| 99 | `64 bit` | `64 bit` | 육십사 비트 | FAIL | PLAYED |
| 100 | `32 bit` | `32 bit` | 삼십이 비트 | FAIL | PLAYED |

## Actual production TTS 결과

| Metric | B 결과 | A 기준 | B 대 A |
|---|---:|---:|---:|
| 제출/PLAYED/실패 | 100 / 59 / 41 | 100 / 54 / 46 | 성공 +5건, +5.00%p; 실패 -5건 (-10.87%) |
| 성공률 | 59.00% | 54.00% | +5.00%p |
| generation attempts / retries | 165 / 65 | 164 / 64 | +1 / +1 |
| first-attempt success | 35 | 36 | -1 |
| internal_long_tail | 105 | 108 | -3 (-2.78%) |
| recovery split / accepted | 0 / 0 | 0 / 0 | 변화 없음 |
| waveform rejection / OOM / exception | 0 / 0 / 0 | 보고된 값 없음 | B에서 관측 0 |
| missing / duplicate / order | 0 / 0 / 순서 정상 | A 보고의 총계 | B 누락·중복 없이 순서 정상 |
| first audio latency | 3.430 s | 보고되지 않음 | — |
| first playback → last completion | 281.476 s | 272.444 s | +9.032 s (+3.31%) |
| first submit → last completion | 284.905 s | 276.063 s | +8.842 s (+3.20%) |
| inter-playback gap median / p95 / max / mean | 1.599 / 15.956 / 28.913 / 3.415 s | 2.287 / 13.010 / 19.796 / 3.721 s | -30.08% / +22.64% / +46.05% / -8.23% |
| gap >1 / >2 / >5 s | 31 / 23 / 12 | 31 / 28 / 14 | 0 / -5 / -2 |

### 생성 및 오디오 분포

| 분포 (초) | min | median | p95 | max | mean |
|---|---:|---:|---:|---:|---:|
| generation attempt duration | 1.037 | 1.565 | 2.281 | 3.263 | 1.620 |
| source item의 전체 attempt 비용 | 1.142 | 2.761 | 4.087 | 5.444 | 2.673 |
| 성공 항목의 accepted attempt | 1.106 | 1.539 | 2.287 | 2.578 | 1.560 |
| 성공 항목 audio duration | 0.640 | 1.460 | 3.000 | 3.900 | 1.588 |
| 성공 항목 RTF¹ | 0.661 | 1.232 | 3.420 | 3.772 | 1.599 |

성공한 오디오 총 길이는 93.720초였고, 1.25x 재생 추정치는 74.976초야. RTF¹은 성공한 항목별 모든 attempt generation 비용을 실제 audio duration으로 나눈 값이야. A 보고서의 RTF 집계식이 명확히 적혀 있지 않아 RTF 비교는 근사 참고로 봐야 해.

## A/B 해석

B에서 PLAYED가 54개에서 59개로 늘고 명시적 실패가 46개에서 41개로 줄었어. 다만 normalization은 여전히 0/100이고, 현재 production에 교육 변경이 로드되지 않았으므로 교육 효과로 결론 내릴 수 없어. 재시도와 전체 시도 횟수는 각 1회 늘었고 long-tail은 3건 줄었어. gap 중앙값과 평균은 낮아졌지만 p95와 최대 gap은 커졌어. 이는 실행별 변동을 포함하는 단일 stochastic benchmark 비교야.

## 무결성 및 변경 여부

- 제출은 원본 100줄을 각 1회, 순서대로 했고 terminal receipt 100개가 1–100을 빠짐없이 덮었어.
- missing 0, duplicate 0, 순서 오류 0; unrelated TTS playback 혼입은 관측되지 않았어.
- production code/config 변경 없음. TTS 및 Enikk 재시작 없음.
- 전체 production digest를 독립적으로 재계산한 증거는 없어. 다만 활성 release, 로드된 worker release, normalizer/TTS engine 해시를 확인했고 A 기록의 실행 파일 해시와 일치했어.
- 결과는 현재 production 상태의 B 측정이며, 교육 candidate의 설치 후 측정으로 간주하면 안 돼.

EOF
