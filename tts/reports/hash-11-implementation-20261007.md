작성자: 에닉(유키짱)

# TTS 11 — Hash 자동 낭독 규칙 구현

## 승인 및 범위

2026-10-07 사용자가 계속 진행을 지시한 뒤, 이번에는 벤치마크를 하지 않아도 된다고 지시했다. 이어 기능 검증 완료 시 merge/push/TTS 반영을 직접 승인했다. 따라서 기존 성능 gate를 통과했다고 주장하지 않고 기능 구현과 회귀 검증 후 반영한다. 최초 First Audio INCONCLUSIVE 결과는 hash-11-20261007.md에 그대로 보존한다.

재개 후 시작한 장문 A-gap 1은 새 사용자 입력으로 epoch가 바뀌어 중단됐다. helper는 epoch/run changed 오류로 종료했다. 이 미완료/오염 측정은 gap baseline이나 PASS 근거로 사용하지 않는다. 이후 production benchmark 및 CPU microbenchmark를 실행하지 않았다.

## 구현

기존 technical_prose 토큰 scan에 hash 판단을 통합했다. 전체 hash literal 사전은 추가하지 않았다. compiled hex 검사, len(), 앞 7글자 slicing, 기존 korean_cardinal 함수를 사용한다. 파일/registry를 호출마다 다시 읽거나 regex를 호출마다 compile하지 않는다.

ASCII hex에 문자가 포함되어야 한다. 8~31글자는 같은 줄 바로 앞의 hash/commit/SHA/SHA1/SHA-1/SHA256/SHA-256/digest/checksum/release/revision/rev anchor가 있어야 한다. 32글자 이상은 standalone 가능하다. commit hash 등 고정 두 단어 조합은 바로 앞 hash anchor로 처리된다. 멀리 떨어진 anchor, 숫자-only, URL/path/filename/email/option/assignment/JSON/code/UUID/CSS 안의 값은 hash 축약 대상이 아니다. 일반 숫자는 기존 숫자 읽기를 유지한다.

앞 7글자는 영어 문자/숫자의 확정 한국어 발음으로 읽는다. 끝 발음이 원/세븐이면 자연스러운 조사 ‘으로’, 나머지는 ‘로’를 사용한다. 전체 길이는 한국어 수사로 표현한다. 화면 원문은 수정하지 않는다.

notify가 inline code delimiter를 제거하기 전에 hex-bearing inline code의 backtick을 유지하도록 수정했다. 정상 inline word의 기존 낭독 정책과 fenced code 숨김 정책은 유지한다.

기존 2~10 테스트의 bare 40/64자리 hex는 이제 의도적으로 축약 대상이다. 이 4개 이전 boundary 사례는 backtick code로 명시하여 code 보호 검증을 유지했고, 새 test_education_11에서 bare hash 변환을 별도로 검증했다. 나머지 기대값은 변경하지 않았다.

## 검증

171 tests PASS: education 11/10/9/8/2~7, text normalization, units100, TTS delivery, independent TTS, stream, epoch, voice process, core without TTS. sequence-gap reconcile 2개 테스트도 포함된다.

새 검증은 독립 기대값, 8/10/12/16/20/31/32/40/64/77 길이 및 mixed case, 인접 anchor/줄 경계/먼 anchor, 숫자-only 및 machine literal negative boundaries, notify → normalization code 보호 경로를 포함한다.

Python AST syntax PASS. git diff --check PASS.

## 성능 및 음성 검증 한계

First Audio A/B = NOT RUN on resumed implementation.
Long text gap A/B = NOT RUN.
CPU performance gate = NOT MEASURED.
Actual generated pronunciation of raw hash candidate = NOT VALIDATED.

사용자가 합격으로 판정한 것은 이전에 한국어로 풀어 출력한 낭독 형식과 발음이다. 이것을 원문 hash 자동 변환 후보의 실제 Chatterbox 품질 또는 지연 개선 근거로 주장하지 않는다. 소스 구조상 중복 full scan을 추가하지 않았지만 성능 보존을 수치로 검증하지 않았다.

## Git/production

시작 main: 4d366684679c5015184f429224ef2f206777f5f8.
시작 TTS release: 5f61d98a283358d3. 기존 안정 release를 삭제하지 않는다.
Enikk/Codex core는 종료/재시작하지 않는다. 배포 결과는 별도 deployment 보고서에 기록한다.

EOF
