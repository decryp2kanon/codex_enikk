# Yuki TTS Deferred Issues

반복 감사에서 이미 조사했지만 현재 접근으로 자동 해결하지 않기로 한 항목을 보관한다.
TTS 단어장/정규화 반복 작업은 ACTIVE 항목을 자동 스킵하고 신규 이슈를 우선 조사한다.
새로운 청취 근거, 새로운 검증 가능한 접근, 또는 USER의 명시적 재개 지시가 있을 때만 다시 연다.

## 태그

- `[HUMAN_PRONUNCIATION]`: 사람 청취로 부자연스러움 확인, 별도 발음 처리 필요
- `[GENERATION_FAILURE]`: 음성 생성 실패로 검증 미완료
- `[CONTEXT_AMBIGUOUS]`: 문맥 의미가 불명확해 자동 수정 위험
- `[UPSTREAM_GRAMMAR]`: upstream 정규화/grammar 한계
- `[POLICY_UNDEFINED]`: 원하는 낭독 규칙 자체가 아직 미정
- `[NEEDS_NEW_APPROACH]`: 기존 접근 반복으로 개선 근거 없음
- `[PERFORMANCE>1%]`: baseline 대비 처리 속도 1.0% 초과 악화
- `[RUNTIME]`: 단어장과 분리해야 하는 runtime/guard 문제

## ACTIVE

### [NEEDS_NEW_APPROACH] Python / Python 3.10
- 기존 정규화/ASR 반복으로 실제 발음 오류와 ASR 오인식을 분리하지 못함.
- 기존 시도: 파이썬 치환, spacing, 버전 문맥 보호/복원.
- 일반 버전 문맥 후보 warm normalization 약 +12.060% 악화는 `[PERFORMANCE>1%]`에도 해당.
- 재개 조건: 새로운 사람 청취 근거 또는 기존과 다른 phonetic/G2P/엔진단 접근.

### [HUMAN_PRONUNCIATION] commit
- 28회차 raw/1.25x × Whisper small/base 및 반복 문맥에서 의심.
- USER 직접 청취로 부자연스러움 확인.
- 예정 방향: 고정 기술용어 lookup으로 `커밋` 검증.
- 재개 조건: 별도 lookup 최적화 작업에서 1% 성능 게이트와 identifier/path/URL/email 경계 검증.

### [HUMAN_PRONUNCIATION] checkout
- 28회차 교차검증 후 USER 직접 청취로 부자연스러움 확인.
- 예정 방향: 고정 기술용어 lookup으로 `체크아웃` 검증.
- 재개 조건: 별도 lookup 최적화 작업에서 1% 성능 게이트와 경계 검증.

### [HUMAN_PRONUNCIATION] merge
- 28회차 교차검증 후 USER 직접 청취로 부자연스러움 확인.
- 예정 방향: 고정 기술용어 lookup으로 `머지` 검증.
- 재개 조건: 별도 lookup 최적화 작업에서 1% 성능 게이트와 경계 검증.

### [GENERATION_FAILURE] reference
- 28회차에서 원문 재시도와 split recovery까지 `internal_long_tail`로 거부.
- WAV/ASR 검증 미완료.
- 재개 조건: 생성 실패 원인 분리 또는 새로운 재현 경로 확보.

### [CONTEXT_AMBIGUOUS] 수 없음.txt
- 현재 `수요일 없음.txt`로 오정규화됨.
- 공백 포함 파일명인지 문장+확장자인지 의미가 불명확해 자동 수정 보류.
- 재개 조건: 실제 사용 문맥 확보.

### [UPSTREAM_GRAMMAR] 2시간 3분 4초
- 연속 시간 표현에서 NeMo grammar warning과 원문 반환.
- 성공 지원으로 간주하지 않음.
- 재개 조건: 실제 음성 재현 또는 안전한 전용 시간 parser 접근.

### [POLICY_UNDEFINED] commit SHA / technical identifier reading
- SHA 내부 숫자·영문을 일반 cardinal처럼 읽는 사례가 있음.
- 원하는 읽기 정책과 청취 근거가 미정.
- 재개 조건: USER가 원하는 식별자 낭독 규칙 확정 및 경계 테스트 설계.

### [RUNTIME] repeated internal_long_tail / recovery cost
- 여러 감사에서 반복 관측.
- 단어장 문제와 분리해야 하며 guard를 느슨하게 해서는 안 됨.
- 재개 조건: 별도 runtime 원인분리/성능 검증 작업.

## 성능 보류 규칙

- baseline 대비 처리 시간이 **1.0% 이하 악화**면 일반 검증 흐름에서 처리 가능하다.
- **1.0% 초과 악화**면 자동 commit/merge/push/production update 금지.
- 해당 후보를 이 문서 ACTIVE에 `[PERFORMANCE>1%]` 태그로 추가한다.
- 항목에는 baseline, candidate, 저하율, 테스트 결과, 재현 문장을 함께 기록한다.

## 반복 감사 운영 규칙

- ACTIVE 항목은 일반 TTS 단어장 반복 감사에서 자동 스킵한다.
- 같은 접근을 표현만 바꿔 반복하지 않는다.
- 새 이슈가 기존 ACTIVE 항목과 동일 원인인지 먼저 확인하고 중복 등록하지 않는다.
- 해결되어 production에 반영된 항목은 ACTIVE에서 RESOLVED로 이동하고 해결 commit을 기록한다.

## RESOLVED

현재 없음.
