작성자: 도로시(Work)

# 우선 내부 요청 차단

UI 빌드 후보와 분리한 최소 패치. 사용자 요청에 따라 검증 가능한 기록 보호를 우선한다.
기준 fa76d97. 새 UI 및 ENIKK_FIXED_SESSION_UI 환경변수는 사용하지 않는다.

## 범위
차단: thread/start, fork, archive, delete, revert, inject_items, account/logout.
thread/resume는 원래 thread ID + replacement history/path 없음 조건만 허용한다.
이에 해당하는 /new, /clear, /fork, /side, /btw, /archive, /delete, /logout,
다른 세션 /resume와 이전 메시지 편집의 실제 기록 변경 요청을 거부한다.
UI 메뉴 제거는 하지 않는다. 이전 질문 편집 화면 진입 자체도 막지 않는다.
편집 거부 후 이전 질문이 입력창에 복원되는 stock UI 동작은 남는다.

/voice, /init, /memories, /personality 및 설정 메뉴 전체 차단을 보장하지 않는다.
/goal, /model, /plan, /permissions, /compact 및 정상 종료·중단은 변경하지 않는다.
별도 codex CLI나 proxy를 우회한 직접 연결에는 이 보호가 적용되지 않는다.

## 원칙
서버 전달 및 예약 상태 변경 전에 거부한다. 성공 응답을 위조하지 않는다.
revert는 미제공 메서드 오류 -32601로 확정적 사전 거부를 알린다.
나머지 보호 거부는 -32010. 동일 연결로 다음 요청을 처리한다.
기존 ID를 바꾸거나 과거 기록/identity를 수정하지 않는다.

## 검증
자동 테스트: 신규 4 + trigger protocol 34 + submission arbiter 15 통과.
신규 실제 proxy 연결 테스트에서 금지된 모든 메서드 및 다른-ID resume가
upstream에 전달되지 않으며 다음 read가 같은 연결로 전달됨을 확인했다.
각 예약 상태의 상태/owner/token/turn 보존을 확인했다.
실제 Codex 0.160.0 UI + bubblewrap/mock 결과는 .experiment/case-*/result.json.
mock의 PROBE_OK는 모델 호출이 아니며 실제 모델 응답 성공을 뜻하지 않는다.

## 반영
현재 실행 중인 Python 서비스는 디스크 변경을 다시 불러오지 않는다.
설치본 갱신 후에도 사용자가 정상 종료 후 codex_enikk를 실행해야 보호가 활성화된다.
자동 재시작, 운영 세션으로 위험 명령 시험, 세션 백업 복원은 하지 않는다.
최초 설치 단계에서는 커밋/머지/푸시를 수행하지 않았다.


## 설치 결과
11개 UI 경로의 사전 거부/화면 생존/같은-ID 후속 mock 응답 확인.
원본 백업: ~/.local/state/codex_enikk/backups/priority-guard-20261009T212319Z
설치 trigger_service.py SHA256: 24adc36abf2f5f0a6b243c26d9856e0e613495ca8b78a8adb28a2bd85461805f
최초 설치 시 main 작업 파일에도 동일 변경을 보존했고 커밋/머지/푸시는 하지 않았다.
최초 설치 직후에는 실행 중인 프로세스가 구 코드여서 재시작 전 보호가 비활성이었다.


## 재시작 및 커밋 범위 확인
사용자 재시작 후 설치된 코드의 SHA256 일치, 설치 이후 시작된 trigger_service,
TUI의 해당 proxy 연결, 기존 pinned session ID 유지 여부를 읽기 전용으로 확인했다.
운영 세션에 삭제/분기 요청을 보내지는 않았다.
이후 사용자가 검증된 우선 차단 코드·테스트·문서의 커밋 및 푸시를 승인했다.
커밋 범위는 trigger_service.py, tests/test_continuity_command_guard.py, 이 문서뿐이다.
미검증 Rust UI 후보, 개인 기억/정체성 지침, 기타 TTS 작업은 포함하지 않는다.
이 커밋 작업은 추가 배포 또는 재시작을 수행하지 않는다.
UI 실험 원본 결과는 ~/git/codex_enikk-priority-guard/.experiment/case-*/ 에 보존돼 있다.

EOF
