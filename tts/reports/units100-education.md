작성자: 에닉(유키짱)

# TTS 단위 100개 교육 결과

상태: **정규화 교육 PASS (100/100)**. 실제 production 반영과 후속 production benchmark는 아직 진행 전이다.

## 기준과 결과

- corpus: `~/git/codex_enikk-education/1_tts-units-100.txt`
- SHA-256: `c30773e80b6c48fe92afc49c88637d850842a0743c7772c539b2b1f1c91d16d2`; 100줄, 빈 줄 0, 중복 0. 원본은 수정하지 않았다.
- 교육 전 baseline: `~/git/codex_enikk/tts/reports/units100-before-education.md` — normalization 0/100, production TTS PLAYED 54/100, FAILED_EXPLICITLY 46/100.
- 최종 normalization 정확도: **100/100 exact match**. [test_units100_normalization.py](../../tests/test_units100_normalization.py)의 corpus 기대값 100개를 대상으로 확인했다.
- 적용한 숫자 규칙: 정수 한자어 수사, 십·백·천 앞의 1 생략(백·천·천이백), 소수점은 `쩜`, 소수부는 한 자리씩 읽기.
- 적용한 좁은 단위 사전: 이 corpus에 나온 bit/byte 대소문자, SI 단위, 주파수·전기·온도, 시간·속도, 비율·기술 카운터 표현. 한 번 컴파일하는 단일 단위 토큰 registry를 사용하고 일반 영어 사전은 추가하지 않았다.
- 사용자가 직접 제시한 낭독 예시와 일치한다. 세부 약어·시간 표현 중 사용자가 별도로 확정하지 않은 읽기는 baseline 보고서에서 검토 후보로 표시했다.

## 경계와 성능

- identifier, underscore/hyphen token, version, filename, path, URL, email, SHA 유사 문자열, IP, CLI option 등 negative boundary 테스트 PASS.
- 기존 정규화/TTS regression과 신규 corpus/boundary 포함 81 tests PASS.
- paired warm normalization 측정: 같은 프로세스에서 15회 warm-up 후 동일한 100개 corpus를 A/B/B/A 순서로 30회씩 비교했다. A는 현재 installed production normalizer, B는 후보 branch 코드다.

| Metric | A baseline | B candidate | Change |
|---|---:|---:|---:|
| median / 100 items | 0.000745642 s | 0.000278556 s | -62.642% |
| p95 / 100 items | 0.000755335 s | 0.000284883 s | -62.284% |
| mean / 100 items | 0.000744964 s | 0.000277872 s | -62.700% |
| throughput | 134,111 items/s | 358,994 items/s | +167.7% |

30회의 반복값은 측정 command 출력에 보존됐다. 값은 TTS 생성시간이 아니라 normalization only 시간이다.

## 실제 TTS A baseline 참고

교육 전 실제 production TTS 측정은 100개 source item을 제출했고 54개 재생, 46개가 `internal_long_tail` 재시도 후 `FAILED_EXPLICITLY`였다. 100 receipt 모두 존재했고 누락·중복은 0이었다. 단일 짧은 기술 토큰에서 발생한 stochastic generation 실패로 분류했으며, 이를 사전 규칙으로 덮지 않았다. 이 교육은 정규화 출력만 바꾸므로 이 문제를 해결했다고 주장하지 않는다. production 반영 뒤 동일 조건 P benchmark에서 다시 측정해야 한다.

## 검증 및 적용 상태

- 최종 기대값 시험 100/100 PASS.
- `tests.test_text_normalization`, `tests.test_units100_normalization`, `tests.test_tts_delivery`, `tests.test_independent_tts`: 81 PASS.
- `git diff --check`: PASS.
- branch: `fix/yuki-units100-education-20261006`.
- 구현 commit: `268c5dcc9bc9f2980a38ad5491e0b041036e4052`.
- 시작 기준 main/origin: `a26223203bc12851e60d8c834965069f8d47e38c`.
- production source/install, TTS worker, Enikk process/session은 변경하거나 재시작하지 않았다.
- production 5% gate는 normalization-only paired 결과에서 통과한다. 전체 gate는 반영 후 실제 TTS P benchmark까지 측정한 뒤 판정한다.
- 교육 코드·테스트·보고서는 feature worktree의 local commit으로 보존했다. main 반영, push, production update/restart는 아직 하지 않았다.

## 사용자 확정 발음 보정 반복 — 회차 2

사용자가 직접 확정한 발음 중 기존 기대값과 다른 두 항목을 우선값으로 반영했어. 예외는 exact, case-sensitive 입력에만 적용돼. 입력 코퍼스는 수정하지 않았어.

- `100 kb/s` → `백 킬로바이트 퍼 세컨드` (사용자 확정값이 `b=bit` 일반 원칙보다 우선하는 exact exception)
- `225 block/s` → `천 블락스 퍼 세컨드`; `225 blocks/s`도 같은 발음으로 확인
- `50 mb/s` → `오십메가 퍼 세컨드` (소문자 정확 표기만 예외; `50 MB/s`는 byte 의미를 보존)
- `1000 ms`, `1.5 GB/s`, `2 s`, `144 Hz`는 사용자가 확정한 출력과 동일함.
- 수정 반복 수: 사용자 확정값 반영 1회. 전체 100개 exact normalization 재검사: 100/100 PASS.
- 회귀/경계 포함 관련 테스트: 82 PASS (`PYTHONPATH=tests python3 -m unittest test_text_normalization test_units100_normalization test_tts_delivery test_independent_tts`).

### 최종 코퍼스 판정

`Normalization`은 candidate 코드 결과와 사용자 우선 expected reading의 exact 비교야. `Audio`는 실제 Chatterbox 출력의 사람이 듣는 자연스러움 판정이야. Audio 청취를 하지 않은 행은 PASS로 간주하지 않아.

| # | Raw | Expected / candidate output | Normalization | Audio |
|---:|---|---|---|---|
| 1 | `100 kb/s` | 백 킬로바이트 퍼 세컨드 | PASS | UNVERIFIED |
| 2 | `1000 ms` | 천 밀리세컨드 | PASS | UNVERIFIED |
| 3 | `225 block/s` | 천 블락스 퍼 세컨드 | PASS | UNVERIFIED |
| 4 | `50 MB/s` | 오십 메가바이트 퍼 세컨드 | PASS | UNVERIFIED |
| 5 | `1.5 GB/s` | 일 쩜 오 기가바이트 퍼 세컨드 | PASS | UNVERIFIED |
| 6 | `250 Mbps` | 이백오십 메가비트 퍼 세컨드 | PASS | UNVERIFIED |
| 7 | `1 Gbps` | 일 기가비트 퍼 세컨드 | PASS | UNVERIFIED |
| 8 | `32 kB` | 삼십이 킬로바이트 | PASS | UNVERIFIED |
| 9 | `64 KB` | 육십사 킬로바이트 | PASS | UNVERIFIED |
| 10 | `128 MB` | 백이십팔 메가바이트 | PASS | UNVERIFIED |
| 11 | `8 GB` | 팔 기가바이트 | PASS | UNVERIFIED |
| 12 | `16 GiB` | 십육 기비바이트 | PASS | UNVERIFIED |
| 13 | `500 µs` | 오백 마이크로세컨드 | PASS | UNVERIFIED |
| 14 | `2 s` | 이 초 | PASS | UNVERIFIED |
| 15 | `30 sec` | 삼십 세컨드 | PASS | UNVERIFIED |
| 16 | `5 min` | 오 분 | PASS | UNVERIFIED |
| 17 | `2 h` | 이 시간 | PASS | UNVERIFIED |
| 18 | `24 hr` | 이십사 아워 | PASS | UNVERIFIED |
| 19 | `60 Hz` | 육십 헤르츠 | PASS | UNVERIFIED |
| 20 | `144 Hz` | 백사십사 헤르츠 | PASS | UNVERIFIED |
| 21 | `3.2 GHz` | 삼 쩜 이 기가헤르츠 | PASS | UNVERIFIED |
| 22 | `450 MHz` | 사백오십 메가헤르츠 | PASS | UNVERIFIED |
| 23 | `25 kHz` | 이십오 킬로헤르츠 | PASS | UNVERIFIED |
| 24 | `48 kHz` | 사십팔 킬로헤르츠 | PASS | UNVERIFIED |
| 25 | `96 kHz` | 구십육 킬로헤르츠 | PASS | UNVERIFIED |
| 26 | `220 V` | 이백이십 볼트 | PASS | UNVERIFIED |
| 27 | `12 V` | 십이 볼트 | PASS | UNVERIFIED |
| 28 | `5 A` | 오 암페어 | PASS | UNVERIFIED |
| 29 | `750 W` | 칠백오십 와트 | PASS | UNVERIFIED |
| 30 | `65 W` | 육십오 와트 | PASS | UNVERIFIED |
| 31 | `85 °C` | 팔십오 도씨 | PASS | UNVERIFIED |
| 32 | `37 °C` | 삼십칠 도씨 | PASS | UNVERIFIED |
| 33 | `10%` | 십 퍼센트 | PASS | UNVERIFIED |
| 34 | `99.9%` | 구십구 쩜 구 퍼센트 | PASS | UNVERIFIED |
| 35 | `0.1%` | 영 쩜 일 퍼센트 | PASS | UNVERIFIED |
| 36 | `250 tx/s` | 이백오십 티엑스 퍼 세컨드 | PASS | UNVERIFIED |
| 37 | `1200 tx/min` | 천이백 티엑스 퍼 분 | PASS | UNVERIFIED |
| 38 | `32 peer/s` | 삼십이 피어 퍼 세컨드 | PASS | UNVERIFIED |
| 39 | `8 peer/min` | 팔 피어 퍼 분 | PASS | UNVERIFIED |
| 40 | `15 node/s` | 십오 노드 퍼 세컨드 | PASS | UNVERIFIED |
| 41 | `120 req/s` | 백이십 알이큐 퍼 세컨드 | PASS | UNVERIFIED |
| 42 | `500 request/s` | 오백 리퀘스트 퍼 세컨드 | PASS | UNVERIFIED |
| 43 | `300 msg/s` | 삼백 메시지 퍼 세컨드 | PASS | UNVERIFIED |
| 44 | `90 packet/s` | 구십 패킷 퍼 세컨드 | PASS | UNVERIFIED |
| 45 | `75 event/s` | 칠십오 이벤트 퍼 세컨드 | PASS | UNVERIFIED |
| 46 | `42 job/s` | 사십이 잡 퍼 세컨드 | PASS | UNVERIFIED |
| 47 | `18 task/s` | 십팔 태스크 퍼 세컨드 | PASS | UNVERIFIED |
| 48 | `7 thread/s` | 칠 스레드 퍼 세컨드 | PASS | UNVERIFIED |
| 49 | `4 process/s` | 사 프로세스 퍼 세컨드 | PASS | UNVERIFIED |
| 50 | `60 frame/s` | 육십 프레임 퍼 세컨드 | PASS | UNVERIFIED |
| 51 | `30 fps` | 삼십 에프피에스 | PASS | UNVERIFIED |
| 52 | `120 fps` | 백이십 에프피에스 | PASS | UNVERIFIED |
| 53 | `2 block/min` | 이 블록 퍼 분 | PASS | UNVERIFIED |
| 54 | `6 block/h` | 육 블록 퍼 시간 | PASS | UNVERIFIED |
| 55 | `144 block/day` | 백사십사 블록 퍼 데이 | PASS | UNVERIFIED |
| 56 | `250 hash/s` | 이백오십 해시 퍼 세컨드 | PASS | UNVERIFIED |
| 57 | `1 kH/s` | 일 킬로해시 퍼 세컨드 | PASS | UNVERIFIED |
| 58 | `5 MH/s` | 오 메가해시 퍼 세컨드 | PASS | UNVERIFIED |
| 59 | `2 GH/s` | 이 기가해시 퍼 세컨드 | PASS | UNVERIFIED |
| 60 | `120 TH/s` | 백이십 테라해시 퍼 세컨드 | PASS | UNVERIFIED |
| 61 | `250 byte/s` | 이백오십 바이트 퍼 세컨드 | PASS | UNVERIFIED |
| 62 | `4 kB/s` | 사 킬로바이트 퍼 세컨드 | PASS | UNVERIFIED |
| 63 | `20 MB/min` | 이십 메가바이트 퍼 분 | PASS | UNVERIFIED |
| 64 | `1 GB/min` | 일 기가바이트 퍼 분 | PASS | UNVERIFIED |
| 65 | `50 GB/day` | 오십 기가바이트 퍼 데이 | PASS | UNVERIFIED |
| 66 | `2 TB/day` | 이 테라바이트 퍼 데이 | PASS | UNVERIFIED |
| 67 | `15 IOPS` | 십오 아이옵스 | PASS | UNVERIFIED |
| 68 | `500 IOPS` | 오백 아이옵스 | PASS | UNVERIFIED |
| 69 | `5000 IOPS` | 오천 아이옵스 | PASS | UNVERIFIED |
| 70 | `2 ms/op` | 이 밀리세컨드 퍼 오퍼레이션 | PASS | UNVERIFIED |
| 71 | `10 op/s` | 십 오퍼레이션 퍼 세컨드 | PASS | UNVERIFIED |
| 72 | `200 call/s` | 이백 콜 퍼 세컨드 | PASS | UNVERIFIED |
| 73 | `80 query/s` | 팔십 쿼리 퍼 세컨드 | PASS | UNVERIFIED |
| 74 | `25 write/s` | 이십오 라이트 퍼 세컨드 | PASS | UNVERIFIED |
| 75 | `40 read/s` | 사십 리드 퍼 세컨드 | PASS | UNVERIFIED |
| 76 | `64 connection/s` | 육십사 커넥션 퍼 세컨드 | PASS | UNVERIFIED |
| 77 | `12 session/s` | 십이 세션 퍼 세컨드 | PASS | UNVERIFIED |
| 78 | `3 retry/s` | 삼 리트라이 퍼 세컨드 | PASS | UNVERIFIED |
| 79 | `5 error/min` | 오 에러 퍼 분 | PASS | UNVERIFIED |
| 80 | `1 fail/h` | 일 페일 퍼 시간 | PASS | UNVERIFIED |
| 81 | `10 km/h` | 십 킬로미터 퍼 아워 | PASS | UNVERIFIED |
| 82 | `100 km/h` | 백 킬로미터 퍼 아워 | PASS | UNVERIFIED |
| 83 | `5 m/s` | 오 미터 퍼 세컨드 | PASS | UNVERIFIED |
| 84 | `9.8 m/s²` | 구 쩜 팔 미터 퍼 세컨드 제곱 | PASS | UNVERIFIED |
| 85 | `1.2 MB` | 일 쩜 이 메가바이트 | PASS | UNVERIFIED |
| 86 | `2.4 GB` | 이 쩜 사 기가바이트 | PASS | UNVERIFIED |
| 87 | `0.5 ms` | 영 쩜 오 밀리세컨드 | PASS | UNVERIFIED |
| 88 | `12.5 ms` | 십이 쩜 오 밀리세컨드 | PASS | UNVERIFIED |
| 89 | `250 ns` | 이백오십 나노세컨드 | PASS | UNVERIFIED |
| 90 | `100 µs` | 백 마이크로세컨드 | PASS | UNVERIFIED |
| 91 | `3 core` | 삼 코어 | PASS | UNVERIFIED |
| 92 | `8 core` | 팔 코어 | PASS | UNVERIFIED |
| 93 | `16 core` | 십육 코어 | PASS | UNVERIFIED |
| 94 | `32 thread` | 삼십이 스레드 | PASS | UNVERIFIED |
| 95 | `4096 byte` | 사천구십육 바이트 | PASS | UNVERIFIED |
| 96 | `65536 byte` | 육만오천오백삼십육 바이트 | PASS | UNVERIFIED |
| 97 | `2048 bit` | 이천사십팔 비트 | PASS | UNVERIFIED |
| 98 | `256 bit` | 이백오십육 비트 | PASS | UNVERIFIED |
| 99 | `64 bit` | 육십사 비트 | PASS | UNVERIFIED |
| 100 | `32 bit` | 삼십이 비트 | PASS | UNVERIFIED |

### 실제 음성 검증 상태

실제 음성의 Chatterbox human-listening/ASR 교차검증은 이번 실행에서 수행되지 않았어. TTS worker가 현재 production release를 사용 중이라 candidate branch output을 실제로 생성하려면 production TTS routing/update 또는 worker lifecycle 조작이 필요했는데, 이 작업 범위에서는 production update/merge/push를 하지 않고 현재 TTS를 재시작하지 않기로 했어. 따라서 100개 항목의 발음 자연스러움은 미검증이고, 음향 기준의 전체 졸업은 보류 상태야. 기존 54/100 production 결과도 candidate audio 개선 증거로 재사용하지 않았어.

정규화 코드만으로 해소할 수 없는 음향 이슈가 확인된 것은 아니야. 다만 음향 검증을 하지 않았으므로 무조건 PASS라고 보고하지 않아. 실제 Chatterbox audio로 판단하려면 이 feature branch의 candidate normalizer가 연결된 격리된 TTS test path와 청취/ASR evidence가 필요해.

### 이 반복에서의 Git 범위

- 변경 파일: `tts/yuki-text-normalization-overrides.py`, `tests/test_units100_normalization.py`, `tts/reports/units100-education.md`.
- main/origin/production에는 반영하지 않았어.
- 아래 commit은 normalization 100/100 및 자동 테스트를 보존하며 acoustic status는 pending으로 명시해.

EOF
