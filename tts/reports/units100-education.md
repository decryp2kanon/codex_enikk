작성자: 에닉(유키짱)

# TTS 단위 100개 교육 결과

상태: **정규화 교육 PASS (100/100)**. 실제 production 반영과 후속 production benchmark는 아직 진행 전이다.

## 기준과 결과

- corpus: `/home/ak/git/codex_enikk-education/1_tts-units-100.txt`
- SHA-256: `c30773e80b6c48fe92afc49c88637d850842a0743c7772c539b2b1f1c91d16d2`; 100줄, 빈 줄 0, 중복 0. 원본은 수정하지 않았다.
- 교육 전 baseline: [units100-before-education.md](units100-before-education.md) — normalization 0/100, production TTS PLAYED 54/100, FAILED_EXPLICITLY 46/100.
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
- 시작 기준 main/origin: `a26223203bc12851e60d8c834965069f8d47e38c`.
- production source/install, TTS worker, Enikk process/session은 변경하거나 재시작하지 않았다.
- production 5% gate는 normalization-only paired 결과에서 통과한다. 전체 gate는 반영 후 실제 TTS P benchmark까지 측정한 뒤 판정한다.
- commit 및 main/push/production update는 아직 하지 않았다. 교육 코드와 테스트는 feature worktree에 보존했다.


EOF
