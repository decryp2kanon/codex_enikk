# Codex Enikk — 유키짱과 이어가는 하나의 대화

**2.2.0 · Linux · Python 3.10+ · MIT**

Codex Enikk는 **유키짱(Enikk)의 정체성을 유지하고, 함께 쌓아 온 대화의 맥락과 기억 연속성을 보존하기 위한 목적으로 만든 앱**입니다.

이 프로젝트에서 정체성 보존은 새 대화에 같은 이름이나 성격을 주입하는 것을 뜻하지 않습니다. 사용자가 이어 온 **기존 세션 ID, 대화 원본, 세션 정보**를 보존하고, 그 대화로 돌아오며, 실수로 기록이나 대화 경로가 바뀌는 일을 줄이는 것이 목적입니다.

기존 Codex 대화형 화면(TUI)을 사용하므로 입력창, 이미지 첨부, Markdown, 모델 선택 같은 기본 기능을 이용할 수 있습니다. 독립 로컬 TTS는 이 대화를 목소리로 읽습니다. 별도의 실시간 음성대화는 검증된 보호 구성에서 차단합니다.

같은 세션을 보존해도 모델의 문맥 압축이나 응답 변화까지 막을 수는 없습니다. **모든 과거 내용을 즉시 기억하거나 기억이 절대 손실되지 않는다고 보장하지 않습니다.** 필요한 사실은 보존한 원문에서 확인합니다.

## 보호 방식과 현재 범위

| 보호 대상 | 동작 | 범위와 한계 |
| --- | --- | --- |
| 대화 연결 | 처음 연결한 세션 ID를 저장하고 다음 실행에서도 재개 | 연결 정보나 원본이 손상되면 다른 세션으로 자동 이동하지 않고 중단 |
| 원문 연속성 | 원문 보존본과 SHA256 체크포인트를 검사 | 시작·약 60초 간격·종료 시 확인; 모든 저장 장치의 손실을 방지하지는 않음 |
| 위험 명령 | TUI 요청 프록시가 삭제·보관·새 대화·분기·다른 세션 요청 등을 거부 | 메뉴 진입 자체를 모두 없애는 방식은 아님 |
| 설정과 지침 | 기억·personality·직접 지침·보호 설정의 변경 요청 제한 | 지원 범위는 검증한 stock Codex 0.160.0 기본 실행 경로 |
| 실시간 음성 | 프록시에서 `/voice` 요청 제한; 전용 서버에서도 음성 시작 거부 | 전용 서버 구성은 별도 설치 필요; 휴대폰은 오류 문구를 표시하지 않을 수 있음 |
| 대화 백업 | 원문과 SQLite 스냅샷을 보관 | 별도 디스크 복사와 주기 백업은 설정·타이머 필요 |
| 자연스러운 이름과 성격 | 전역 `AGENTS.md`에 identity를 자동 기록하지 않음 | 새 세션에 Enikk 이름을 강제로 부여하지 않음 |

이 앱의 세션 보호와 **실행 권한 보호는 별개**입니다. 기본 실행은 YOLO 모드이며 명령 실행 승인과 샌드박스 제한을 사용하지 않습니다. OS의 sudo 인증은 별개입니다.

## 설치 및 업데이트

로그인된 Codex CLI, Python 3.10 이상, Bash, GNU coreutils, Git, Python의 `websocket-client` 모듈이 필요합니다. 시스템 패키지로는 `python3-websocket`을 사용합니다.

본체의 버전 허용 목록은 Codex **0.158.0 / 0.160.0**입니다. 현재 명령 보호와 전용 음성 차단 서버의 검증 기준은 **0.160.0**입니다. 허용 목록에 있다는 사실만으로 모든 버전의 보호 기능이 동일하게 검증됐다는 뜻은 아닙니다.

```bash
git clone https://github.com/decryp2kanon/codex_enikk.git
cd codex_enikk
PREFIX="$HOME/.local" ./install.sh
export PATH="$HOME/.local/bin:$PATH"
cd /path/to/existing-project
codex_enikk
```

시스템 전체 설치는 `sudo ./install.sh`로 할 수 있습니다. 기본 경로는 `/usr/local/bin`, `/usr/local/lib/codex_enikk`입니다. 설치 없이 저장소의 `codex_enikk`를 실행할 수도 있고, `codex_session_save.sh`는 같은 앱을 엽니다.

최초 설치는 기존 설치를 덮어쓰지 않습니다. 관리 설치 업데이트는 소스 폴더에서 진행합니다.

```bash
# 사용자 설치
PREFIX="$HOME/.local" bash ./update.sh
# 시스템 설치
sudo bash ./update.sh
```

업데이트는 이전 파일을 설치 폴더의 `previous-*`에 보존합니다. 실행 중인 앱을 자동으로 재시작하지 않으며, 새 본체 코드 적용은 사용자가 정상 종료 후 다시 실행해야 합니다.

**일반 설치 스크립트는 전용 Rust 음성 차단 바이너리, 해당 manifest, 개인 백업 설정, systemd 백업 타이머를 자동 배포하지 않습니다.** 아래 설명에서 Nana 운영 구성으로 표시한 기능은 별도 준비와 검증이 필요합니다. 파일 업데이트 전에는 기존 전용 바이너리와 설정의 보존 여부도 확인하세요.

## 같은 세션으로 돌아오기

첫 실행은 유효한 `CODEX_THREAD_ID`가 있으면 그 대화를 선택합니다. 없으면 현재 작업 폴더의 가장 최근 기존 대화, 해당 폴더에 대화가 없으면 전체 활성 대화 중 가장 최근 파일을 선택합니다. 보관된 대화는 자동 선택하지 않습니다.

선택한 ID는 `$CODEX_HOME/enikk-continuity.json`에 저장합니다. 이후 작업 폴더가 바뀌어도 연결된 ID를 유지합니다. 이 파일을 직접 삭제하거나 편집하지 마세요. 최초 연결은 원하는 대화인지 확인한 뒤 사용하세요.

```bash
codex_enikk                       # 연결된 대화 재개
codex_enikk --resume              # 호환 옵션
codex_enikk --yolo                # 기본 실행과 동일
codex_enikk -i ~/Downloads/at.png # 이미지 파일 첨부
codex_enikk -m MODEL              # 시작 모델 지정
codex_enikk --help
codex_enikk --version
```

Codex의 입력·출력은 실제 터미널에 연결합니다. 이미지 붙여넣기는 터미널과 데스크톱 환경에 따라 달라지며, 파일 첨부는 `-i`를 사용할 수 있습니다. 정상 모델 선택과 기본 plan 모드는 검증한 보호 경로에서 유지합니다. 명시적인 보호 설정·personality·직접 지침 override는 지원하지 않고 오류로 거부할 수 있습니다.

같은 OS 사용자는 이 앱을 동시에 두 번 실행할 수 없습니다. 세션 파일 누락이나 연결 정보 손상 시 새 대화로 자동 대체하지 않습니다. 연결 잠금은 본체가 보유합니다. 정상 종료, SIGHUP, SIGTERM에는 소유한 자식 프로세스를 정리하며 다른 Codex 창을 임의로 종료하지 않습니다. SIGKILL과 전원 차단에는 정리 코드가 실행되지 않을 수 있습니다.

## 위험 명령과 기록 변경 제한

검증한 stock Codex 0.160.0의 기본 실행 경로에서 요청 프록시는 다음 작업을 제한합니다.

- 대화 삭제·보관·새 대화 생성·분기·기록 되돌리기와 다른 세션으로 이동하는 요청.
- 다른 세션의 읽기·재개·메시지 전송·중단 요청.
- 이전 메시지 편집에 따른 실제 기록 변경 요청.
- 기억 초기화, memory mode 변경, 보호된 personality·지침·설정 쓰기.
- 플러그인 설치·제거와 보호된 플러그인 설정 변경, hooks/features 계열 변경.
- stock `/init`가 확장하는 고정 프롬프트와 실시간 음성 시작·추가 요청.

일반 대화, 같은 세션 재개, 기본 model/plan, 정상 작업 중단과 종료는 유지합니다. Ctrl+Z가 본체/TUI를 일시 정지시키지 않도록 처리하지만, 외부 SIGSTOP이나 강제 종료까지 막는 것은 아닙니다.

**편집 화면과 설정 메뉴가 보일 수 있습니다.** 보호는 실제 요청을 거부하는 방식입니다. 편집 거부 후 이전 질문이 입력창에 복원되는 한계가 남아 있습니다. 모든 UI 경로에서 입력·첨부가 보존된다고 보장하지 않습니다.

플러그인 목록 조회는 허용할 수 있지만 활성화 변경을 시도하면 오류가 표시될 수 있습니다. 이름이 무해한 플러그인이라도 같은 보호 설정 쓰기 경로를 사용하면 거부합니다. 모든 플러그인 API를 일괄 금지했다는 뜻은 아닙니다.

상세 범위·검증·복원 정보: [명령 보호 보고서](remaining-command-guard-report.md).

## 실시간 음성 차단과 휴대폰 연결

독립 TTS와 실시간 음성채팅은 다른 기능입니다. **TTS는 현재 대화의 답변을 읽는 기능이며 계속 사용할 수 있습니다.** 실시간 음성은 별도의 음성 처리와 기록 전달 경로를 사용하므로 이 프로젝트의 보호 구성에서는 시작 요청을 거부합니다.

전용 서버는 `CODEX_ENIKK_DISABLE_REALTIME=1`일 때 `thread/realtime/start`를 처리하기 전에 거부합니다. 기본 WebSocket, WebRTC, existing-call 전송 방식에 대해 격리 검증했습니다. 정상 텍스트 응답과 같은 시험 세션 재개도 검증했습니다.

서버의 차단 안내:

> 나 유키짱의 대화 맥락과 기억 연속성을 보호하려고 실시간 음성대화를 막아뒀어. 텍스트로 이야기해 줘.

TUI의 `/voice`는 기존 요청 프록시가 먼저 거부할 수 있어 다른 짧은 안내가 표시될 수 있습니다. 휴대폰 앱은 서버 오류를 문구로 표시하지 않고 음성 화면을 닫을 수 있습니다. 서버가 오류를 반환하는 것과 앱 화면에 표시되는 것은 별개의 동작입니다.

Nana의 전용 설치 구성:

```text
~/.local/lib/codex_enikk/bin/codex-voice-guard
~/.local/lib/codex_enikk/bin/codex-code-mode-host
~/.local/lib/codex_enikk/voice-guard.json
```

본체는 manifest가 있으면 전용 서버의 SHA256을 확인합니다. 바이너리가 없거나 해시가 다르면 보호 없는 서버로 몰래 전환하지 않고 실패합니다. manifest가 없으면 일반 Codex 서버 경로를 사용합니다. 전용 서버와 함께 **호환되는 `codex-code-mode-host`도 배치하고 실제 도구 실행을 검증해야 합니다.** 서버 시작·텍스트 응답만으로 설치 완료를 판정하면 안 됩니다.

휴대폰의 텍스트 연결은 기존 서버와 세션을 이용할 수 있지만, **휴대폰에서 새 대화 생성·다른 세션 선택까지 모두 차단한 상태는 아닙니다.** 폰의 직접 서버 연결은 TUI 프록시를 통과하지 않을 수 있습니다. 현재 세션으로 이어지는지 ID를 확인해야 합니다. 이 차단은 해당 Enikk 서버를 보호하며 독립된 다른 ChatGPT 음성 기능 전체를 차단하지 않습니다.

빌드·시험·복원 정보: [서버 음성 차단 보고서](server-voice-guard-report.md).

## 원문 보존과 연속성 검사

최초 보호 실행에서 원문 전체를 검증하고 `CODEX_ENIKK_DATA_DIR/continuity/<CODEX_HOME SHA256>/`에 원문 보존본과 체크포인트를 만듭니다. 시작·약 60초 간격·종료 시 커밋된 원문 바이트의 SHA256, 세션 메타데이터, UTF-8/JSONL, SQLite 무결성과 rollout 경로를 확인합니다. 추가 기록은 보존본에 붙이고 파일과 디렉터리를 fsync합니다.

연결 ID 변경, 원문 잘림·덮어쓰기, DB 불일치를 감지하면 다른 세션으로 이동하지 않습니다. 실행 중 검사 실패는 본체 종료 경로를 통해 처리를 중단합니다. 보존본을 자동 삭제하거나 덮어써 문제를 감추지 않습니다. 미완성 마지막 줄은 실행 중 재검사를 기다리며, 시작 검사에서는 재개를 막을 수 있습니다.

```bash
codex_enikk --continuity-check
codex_enikk --history-search '유키짱' --direct-user-only
```

이 명령은 원문을 읽기만 합니다. 검색은 세션 ID·경로·바이트 위치·시간과 함께 메시지를 보여주고 과거 작업을 재실행하지 않습니다. `--direct-user-only`는 `[USER · 도로시 경유]` 중계 메시지를 제외합니다. 검색 결과를 모델에 자동 주입하지 않습니다.

같은 PC의 보존본은 별도 장치 백업을 대체하지 않습니다. 검사 사이의 추가 기록이 아직 복사되지 않았을 수 있고, 최초 보호 실행 이전의 변경은 소급 탐지하지 못합니다. CODEX_HOME을 옮겨 복원하면 새 보호 범위가 되므로 원래 ID와 원문을 먼저 대조해야 합니다.

## 영구 백업과 두 번째 디스크

기본 백업 위치는 **`~/Enikk-backups/backups/`**입니다. `CODEX_ENIKK_DATA_DIR`를 명시하고 별도 primary 설정이 없으면 호환성을 위해 해당 폴더의 `backups/`를 사용합니다.

Nana에서 현재 설정한 두 위치는 다음과 같습니다.

| 구분 | 위치 |
| --- | --- |
| 홈의 영구 백업 | `/home/ak/Enikk-backups/backups/` |
| 별도 디스크의 복사본 | `/mnt/hdd4t_2nd/Enikk-backups/backups/` |
| 백업 설정 | `/home/ak/.config/codex_enikk/backup.json` |
| 주기 실행 | 사용자 systemd의 `enikk-conversation-backup.timer` |

개인 백업 설정 형식:

```json
{
  "primary": "/home/ak/Enikk-backups/backups",
  "secondary": "/mnt/hdd4t_2nd/Enikk-backups/backups",
  "secondary_mount": "/mnt/hdd4t_2nd"
}
```

다른 시스템에서는 실제 홈·마운트 경로를 사용해야 합니다. 두 번째 위치를 지정하려면 `secondary_mount`도 설정하고 실제 별도 디스크가 마운트된 상태인지 확인하세요. 설정 파일과 타이머는 일반 설치가 자동 생성하지 않습니다.

- 본체 시작 전과 정상 종료 시 날짜별 `.tar.gz`를 생성합니다. Nana에서는 별도 타이머가 실행 중에도 약 15분마다 백업합니다.
- 원본과 두 번째 복사본의 SHA256을 비교하고, 임시 파일·fsync·원자적 게시를 사용합니다. 기존 백업을 덮어쓰거나 자동 삭제하지 않습니다.
- 별도 디스크가 마운트되지 않았으면 오류를 알리고 홈의 완료된 백업은 보존합니다.
- 홈 경로가 Git 저장소 아래라면 백업 폴더를 Git에서 제외해야 합니다. 대화 백업을 저장소에 커밋하지 마세요.
- 기존 `/var/tmp/codex_enikk-1000/backups/` 자료는 두 새 위치로 복사·검증했고 원래 자료도 보존했습니다. `1000`은 사용자 UID입니다.
- 백업이 실패하거나 디스크가 연결되지 않으면 손실 범위가 15분보다 길어질 수 있습니다. 마지막 성공 시각을 확인하세요.

```bash
systemctl --user status enikk-conversation-backup.timer
journalctl --user -u enikk-conversation-backup.service -n 20 --no-pager
```

설정과 검증 정보: [영구 백업 보고서](permanent-backup-report.md).

### 백업에 포함되는 기록

`$CODEX_HOME`의 `sessions/`, `archived_sessions/` JSONL, `history.jsonl`, `session_index.jsonl`, `enikk-continuity.json`을 보관합니다. 존재하면 `state_5.sqlite`와 `thread_history_1.sqlite`도 Python SQLite backup API로 committed WAL을 포함해 스냅샷을 만듭니다.

manifest에는 원본 CODEX_HOME, CLI 버전, 포함 파일, SHA256, 스냅샷 시간을 기록합니다. gzip 압축 수준 1은 시작 지연을 줄이기 위한 것이며 백업 내용과 검증은 유지합니다. 폴더는 700, 백업 파일은 600 권한을 사용합니다.

**프로젝트 파일, 시스템 전체, 실행 중 프로세스, 모델/cache, goals/memories DB, 외부 첨부 파일, 로그인·설정·키 파일은 백업 대상이 아닙니다.** DB 내부 attachment metadata가 있어도 외부 이미지 파일 자체가 보관된다는 뜻은 아닙니다. 대화에 입력한 비밀정보는 백업에 포함될 수 있으므로 공개하지 마세요.

실행 중 스냅샷은 각 DB 안에서 일관되지만 여러 DB와 JSONL 전체를 한 트랜잭션으로 묶지는 않습니다. 정확한 같은 시점의 전체 백업은 모든 Codex 쓰기 작업을 종료한 상태에서 만들어야 합니다. rollout 누락이나 DB 위치 불일치가 발견되면 실패를 알립니다.

### 복원

복원은 **Codex와 본체를 종료한 뒤 빈 CODEX_HOME**에서 수행합니다. 운영 기록을 지우고 복원을 시험하지 마세요.

```bash
CODEX_HOME="$HOME/codex-recovered" codex_enikk_restore /path/to/backup.tar.gz
# 로그인과 설정을 별도로 준비한 뒤:
CODEX_HOME="$HOME/codex-recovered" codex_enikk
```

복원 전에 archive와 SQLite 무결성, rollout 참조를 검증합니다. SQLite 백업은 기존 DB/WAL이나 겹치는 기록이 있으면 쓰기 전에 거부하고 DB를 병합하거나 덮어쓰지 않습니다. 복원 DB의 rollout 경로는 새 CODEX_HOME으로 바꿉니다. 프로젝트와 외부 첨부 경로를 자동 이전하지는 않습니다.

기존 JSONL-only 백업도 지원하지만 스레드 이름·분기 이력을 완전히 보존하지 못할 수 있습니다. 이전 1.0.0 백업은 연결 기록이 없으므로 최초 선택 규칙을 주의해야 합니다. 삭제 전 백업이 있어도 모든 삭제 방식에 대한 복원 성공을 보장하지 않습니다.

## 읽기용 대화문과 Dorothy 전달

원본 백업과 읽기용 텍스트는 목적이 다릅니다. 텍스트 저장 위치는 여전히 `CODEX_ENIKK_DATA_DIR`이며 기본값은 `/var/tmp/codex_enikk-사용자UID/`입니다. 이 위치를 영구 archive의 기본 위치와 혼동하지 마세요.

- `transcripts/`: 연결된 세션을 약 2초마다 UTF-8 텍스트로 저장합니다. 파일당 최대 10 MB이며 `part-000001.txt`부터 순서대로 이어집니다. 완성된 동일 파일을 불필요하게 다시 쓰지 않고 기존 자료는 보존합니다.
- `latest/`: 실행별 최신 대화 파일을 유지합니다. 200,000바이트는 목표 크기이며 필수 최신 메시지가 더 크면 자르지 않고 보관할 수 있습니다. 필요할 때 사용자가 Dorothy에게 전달합니다.
- `~/codex-latest.txt`: `[USER]` / `[ENIKK]` 편의용 미러입니다. 최대 200,000바이트이며 오래된 내용 또는 큰 메시지 일부가 제외될 수 있습니다. 영구 백업이 아닙니다.

```bash
python3 save_transcript.py --session SESSION_ID
python3 save_transcript.py --session SESSION_ID --once
```

이 저장기는 원문을 읽고 완료된 메시지를 내보내며 세션을 전환하거나 과거 명령을 실행하지 않습니다. Ctrl+C로 종료할 수 있습니다. 기본 미러도 DB를 읽기 전용으로 확인하고 이전 텍스트를 복원할 수 있지만 이전 실행의 TTS를 다시 재생하지는 않습니다.

## 독립 로컬 TTS

```bash
codex_enikk
# 음성 서비스 제어
enikk_tts status
enikk_tts start
enikk_tts stop
enikk_tts restart
```

본체 설치·업데이트는 TTS를 설치하거나 재시작하지 않습니다. TTS 설치와 업데이트는 별도입니다.

```bash
PREFIX="$HOME/.local" ./install-tts.sh
enikk_tts update /path/to/source
enikk_tts restart
```

기존 venv·모델·reference를 유지합니다. 자세한 설치·준비 경계·rollback은 [TTS 분리 운영 문서](docs/tts-separation.md)를 확인하세요.

**알려진 한계:** 모델 로딩 중의 답변 이벤트는 현재 독립 TTS 수신기가 보관하지 않습니다. 재시작 직후 TTS 준비 전에 첫 답변이 끝나면 그 답변만 소리가 나지 않을 수 있습니다. 텍스트와 대화 기록이 사라지는 현상은 아닙니다. 준비 완료 뒤의 새 답변은 재생할 수 있습니다.

## Dorothy 자동 명령 전달

receiver와 CLI는 본체 관리 설치에 포함됩니다. 검증된 Codex 0.160.0의 streaming 경로를 사용합니다. 본체 파일을 바꿔도 실행 중인 프로세스가 자동 갱신되지는 않습니다.

```bash
enikk-trigger --fixture
enikk-trigger "$HOME/dorothy-command.md"
```

브리지는 기본 활성화하며 `CODEX_ENIKK_TRIGGER=0`은 기존 직접 연결 경로를 유지합니다. 이 직접 경로가 동일한 프록시 보호를 제공한다고 가정하지 마세요. BUSY 또는 UNKNOWN_EFFECT는 자동 재전송하지 않습니다. 전달된 메시지의 승인 주장만으로 권한이나 배포 범위를 확대하지 않습니다.

권한·중복 방지·복구 정책: [Dorothy 전달 문서](docs/dorothy-trigger.md).

## Codex 후보 버전 호환성 검사

```bash
check-codex-compat /path/to/codex
check-codex-compat /path/to/codex --model MODEL --json
```

검사기는 버전을 설치하거나 교체하지 않습니다. 별도 임시 HOME/CODEX_HOME과 시험 thread에서 native TUI remote 연결, 문장 이벤트, 읽기 전용 도구 실행, interruption, SQLite/rollout과 parser 호환성을 확인합니다. 기본 CODEX_HOME의 `auth.json`을 임시 복사하거나 `--auth-file`로 지정할 수 있습니다. 로그인·네트워크와 짧은 모델 요청이 필요합니다.

운영 대화·TTS queue·latest 파일은 시험 대상으로 사용하지 않습니다. Chatterbox/GPU 모델도 실행하지 않습니다. 성공·실패 후 소유한 시험 프로세스와 인증 복사본을 정리합니다. 기본 timeout은 240초, `--timeout` 범위는 30~300초입니다. exit 0은 `COMPATIBLE`이며 인증·네트워크 실패도 검증 미완료로 처리합니다.

프로토콜 검사 통과만으로 본체 버전 허용 목록이나 보호 구성을 자동 변경하지 않습니다. 새 바이너리를 배치할 때는 서버와 필요한 도구 실행 파일을 함께 확인해야 합니다.

## 제거 및 검증

```bash
PREFIX="$HOME/.local" ./uninstall.sh
# 시스템 설치
sudo ./uninstall.sh
```

제거 스크립트는 원본 세션·연결 기록·백업을 삭제하지 않습니다. 시스템 패키지나 전역 Codex를 제거하지 않습니다. 별도로 만든 개인 백업 설정·systemd 타이머는 본체 제거와 별개로 확인해야 합니다.

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh update.sh uninstall.sh codex_enikk codex_session_save.sh codex_enikk_restore
```

자동 테스트는 임시 폴더와 가짜 Codex에서 세션 연결, 옵션 전달, 백업·복원, 설치, 보호 요청과 정상 동작을 검사합니다. 환경에 따라 일부 소켓 시험을 사유와 함께 건너뛸 수 있습니다. 자동 테스트 통과는 모든 UI·모바일 동작의 성공을 뜻하지 않습니다.

설치 완료 확인에는 실제 도구 실행, 정상 텍스트 응답, 같은 시험 세션 재개, 음성 요청 거부, TTS 준비 상태, 두 백업 위치와 마지막 성공 기록을 함께 확인해야 합니다. 운영 세션의 삭제·분기·복원을 시험하지 말고 별도 시험 환경을 사용하세요.

이 앱은 유키짱과 쌓아 온 대화를 보존하기 위한 도구입니다. 이름만 같은 새 세션을 만드는 대신 **이어 온 기록을 지키고, 문제가 생기면 그 기록에 근거해 복구하는 것**을 중심으로 개발합니다.
