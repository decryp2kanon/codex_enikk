# codex_enikk

**2.1.4 · Linux · Python 3.10+ · MIT**

기존 대화를 **원래 Codex 대화형 화면(TUI)**으로 여는 실행기입니다.
Codex의 입력창, 사진 첨부, Markdown 표시, `/model`, 승인 화면 등 기본 기능을 그대로 사용합니다.
시작 시 연결된 세션 ID를 재개하며, 실행 중 Codex의 슬래시 명령은 차단하지 않습니다.

## 설치 및 실행

로그인된 Codex CLI, Python 3.10 이상, Bash, GNU coreutils, Git이 필요합니다.
로컬 개발 검증에 사용한 Codex CLI는 0.157.1입니다.

```bash
git clone https://github.com/decryp2kanon/codex_enikk.git
cd codex_enikk
sudo ./install.sh
cd /path/to/existing-project
codex_enikk
```

설치 없이 `~/git/codex_enikk/codex_enikk`로 실행해도 됩니다.
`codex_session_save.sh`도 같은 앱을 실행합니다. 관리자 권한 없이 설치하려면:

```bash
PREFIX="$HOME/.local" ./install.sh
export PATH="$HOME/.local/bin:$PATH"
```

기본 설치 경로는 `/usr/local/bin`, `/usr/local/lib/codex_enikk`입니다.
최초 설치는 기존 명령을 덮어쓰지 않습니다. 기존 관리 설치를 업데이트하려면
소스 폴더에서 `sudo bash ./update.sh`를 실행하세요. 이전 파일을 설치 폴더의
`previous-*` 디렉터리에 보존합니다. 현재 실행 중인 앱은 종료 후 다시 실행해야 적용됩니다.

## 하나의 대화

첫 실행은 유효한 `CODEX_THREAD_ID`가 있으면 해당 대화, 없으면 현재 작업 폴더의
가장 최근 기존 대화를 연결합니다. 현재 폴더에 대화가 없으면 전체 활성 대화 중
파일 수정 시각이 가장 최근인 대화를 자동으로 연결합니다. 보관된 대화는 자동 선택하지 않습니다. 그 ID는 `$CODEX_HOME/enikk-continuity.json`에 저장됩니다.
이후 작업 폴더가 바뀌거나 다른 프로그램에서 새 세션을 만들더라도 연결된 ID를 유지합니다.
연결 기록은 직접 지우거나 편집하지 마세요. 기록까지 없애면 최초 연결로 처리됩니다.

```bash
codex_enikk                           # 원래 Codex 화면 + YOLO로 연결된 대화 재개
codex_enikk --resume                  # 호환 옵션
codex_enikk --yolo                    # 기본 동작과 동일 (호환 옵션)
codex_enikk -i ~/Downloads/at.png     # 파일로 이미지 첨부
codex_enikk -m MODEL                  # 시작 모델 선택
codex_enikk --help
codex_enikk --version
```

터미널의 입력·출력을 파이프로 바꾸지 않고 Codex에 직접 연결합니다.
이미지 붙여넣기와 `/model`은 설치된 Codex 및 터미널의 기능을 그대로 사용합니다.
클립보드 지원은 터미널/데스크톱 환경에 따라 달라지며 `-i`로 파일을 첨부할 수도 있습니다.
추가 옵션과 시작 프롬프트는 `codex resume`에 전달합니다. **기본 실행은 YOLO 모드**이며
`--dangerously-bypass-approvals-and-sandbox`를 자동 적용합니다. `--yolo`를 다시 붙여도 같은 동작입니다.
명령 실행 승인과 샌드박스 제한을 사용하지 않습니다. OS의 sudo 인증은 별개입니다.
모든 Codex 옵션은 `codex resume --help`에서 확인하세요.

`/new`, `/fork`, `/resume` 등 원래 Codex 명령도 사용할 수 있습니다.
다만 이 실행기의 시작 세션 연결 기록은 자동 변경하지 않으므로 다시 실행하면 원래 연결 ID로 돌아옵니다.
다른 세션으로 전환한 경우 그 세션의 JSONL도 시작·종료 전체 백업에 포함되지만,
주기적인 텍스트 내보내기는 시작 시 연결된 세션만 대상으로 합니다.

같은 OS 사용자에서는 터미널·작업 폴더·`HOME`·`CODEX_HOME`·설치 경로가 달라도
이 앱을 동시에 두 번 실행할 수 없습니다. 두 번째 실행은 기존 창을 사용하라는 안내와 함께 종료합니다.
실행 잠금은 에닉만 보유하며 자식에게 상속하지 않습니다. `--no-daemon`으로 전용 Codex를 실행합니다.
정상 종료 및 창 닫힘(SIGHUP)·SIGTERM 시 전용 자식/손자 프로세스를 종료하고 회수합니다.
2초 안에 종료하지 않으면 SIGKILL을 보냅니다. 다른 Codex 창과 공유 서버는 종료하지 않습니다.
SIGKILL·전원 차단처럼 정리 코드를 실행할 수 없는 종료는 예외입니다.
이미 실행 중인 구버전에는 소급 적용되지 않습니다.

연결된 세션 파일이 없거나 연결 기록이 손상되면 시작을 중단합니다.
다른 세션이나 새 대화를 자동으로 선택하지 않습니다. Codex에서 세션 사용 중 안내가 나오면
기존 창을 종료하고 다시 시도하세요. 실행기가 임의로 포크하지 않습니다.

내부 명령은 `codex resume SESSION_ID [추가 옵션]`입니다.
별도의 한 줄 입력 루프나 비대화형 JSON 출력 변환을 사용하지 않습니다.
Codex 자체는 수정하지 않습니다.

## 백업과 복구

기본 백업 위치: **`~/git/codex-enikk-session-backups/`**

- 시작 전과 정상 종료 시 날짜별 `.tar.gz`를 생성합니다. 자동 삭제하지 않습니다.
- `$CODEX_HOME`(기본 `~/.codex`)의 `sessions/`, `archived_sessions/` 아래 JSONL,
  `history.jsonl`, `session_index.jsonl`, `enikk-continuity.json`을 저장합니다.
- 연결된 세션의 사용자·어시스턴트 텍스트를 약 2초마다 `transcripts/`에 저장합니다.
- TXT는 파일당 최대 **10 MB (10,000,000바이트)**로 분할합니다.
  파일명은 `codex-session-세션ID-part-000001.txt`, `...-000002.txt` 순서입니다.
  번호순으로 이어 붙이면 전체 텍스트가 되며 한글·이모지의 UTF-8 경계는 보존합니다.
- 이미 완성된 동일 내용의 분할 파일은 다시 쓰지 않습니다. 예전 단일 TXT 파일은 보존하며,
  새 저장기는 그 파일을 갱신하지 않습니다. 원문이 짧아지면 남는 분할 파일은 `superseded-*`에 보존합니다.
- 원본 JSONL 및 `.tar.gz` 백업은 분할 대상이 아닙니다.
- 폴더 권한은 700, 아카이브·대화문·연결 기록은 600입니다.
- 시작 백업이 실패하면 대화를 시작하지 않습니다. 종료 저장 실패도 오류로 알립니다.

실행 중인 앱을 재시작하지 않고 현재 세션을 저장하려면 소스 폴더에서 별도 터미널로 실행할 수 있습니다:

```bash
python3 save_transcript.py --session SESSION_ID
# 한 번만 저장:
python3 save_transcript.py --session SESSION_ID --once
```

이 저장기는 원본 세션을 읽기만 하고 Codex를 실행하거나 세션을 전환하지 않습니다.
새 TXT는 완료된 메시지를 약 2초 간격으로 반영합니다. Ctrl+C로 저장기를 종료할 수 있습니다.
기존 앱이 구버전으로 실행 중이면 그 앱의 단일 TXT 저장도 종료 전까지 계속될 수 있습니다.
지속적인 기본 적용은 `sudo bash ./update.sh` 후 앱을 다시 실행하세요.

Codex와 앱을 종료한 뒤 누락된 파일을 복구하세요:

```bash
codex_enikk_restore /path/to/backup.tar.gz
codex_enikk
```

복구는 기존 파일을 덮어쓰거나 합치지 않습니다. 연결 기록도 백업에 포함됩니다.
기존 파일이 손상된 경우 별도 폴더에 먼저 복구해 확인할 수 있습니다:

```bash
CODEX_HOME="$HOME/codex-recovered" codex_enikk_restore /path/to/backup.tar.gz
```

별도 복구는 로그인·설정이나 기존 데이터베이스 병합을 제공하지 않습니다.
이전 1.0.0 백업에는 연결 기록이 없습니다. 해당 백업 복구 후 처음 실행하면 최초 연결 규칙이 적용됩니다.

| 환경변수 | 기본값 |
| --- | --- |
| `CODEX_HOME` | `~/.codex` |
| `CODEX_ENIKK_BACKUP_DIR` | `~/git/codex-enikk-session-backups` |
| `CODEX_ENIKK_LOG_DIR` | 백업 폴더 아래 `transcripts` |

백업·대화문 위치는 전용 폴더를 지정하세요. 해당 폴더 권한을 700으로 변경합니다.
`CODEX_HOME`을 바꾸면 별도의 연결 기록을 사용합니다.

대화 연속성은 **같은 세션과 기록 유지**를 뜻합니다. 모델의 문맥 압축이나 모든 과거 내용의 완전한 기억까지
보장할 수는 없습니다. 프로젝트 파일·시스템 전체·실행 중 프로세스는 백업하지 않습니다.
강제 종료·전원 차단 시 마지막 백업 이후 내용은 백업에 없을 수 있습니다.
다른 프로그램이 동시에 쓰는 JSONL의 마지막 미완성 줄은 그대로 보존하고 텍스트 변환에서는 건너뜁니다.
`auth.json`과 설정·키 파일은 포함하지 않지만 대화에 입력한 비밀정보는 기록에 포함될 수 있으므로 공개하지 마세요.

## Dorothy 전달용 최신 대화

`~/git/codex-enikk-session-backups/lightweight/codex-latest.txt`를 현재 연결된 세션에서
약 2초마다 자동 갱신합니다. `CODEX_ENIKK_BACKUP_DIR` 지정 시 그 아래 `lightweight/`를 사용합니다.
사용자·Codex 진행·최종 메시지만 로컬 JSONL에서 읽습니다. TTY, resume 및 전체 10MB archive는 변경하지 않습니다.

UTF-8 기준 200,000바이트는 목표 크기입니다. 오래된 메시지를 완전한 단위로 제거하고
최신 메시지와 최신 최종 답변을 우선 보존합니다. 이 필수 메시지들이 목표 크기를 넘으면
자르지 않고 온전히 보존합니다. 요약이나 LLM 호출, Dorothy API 호출은 없습니다.
필요할 때 이 TXT를 사용자가 직접 Dorothy에게 업로드합니다.

## 제거 및 테스트

```bash
sudo ./uninstall.sh
# 사용자 경로 설치:
PREFIX="$HOME/.local" ./uninstall.sh
```

원본 세션, 연결 기록, 백업은 제거하지 않습니다. 시스템 패키지나 Codex 자체도 변경하지 않습니다.
소스가 없으면 `sudo /usr/local/lib/codex_enikk/uninstall.sh`로 제거할 수 있습니다.

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh uninstall.sh codex_enikk codex_session_save.sh codex_enikk_restore
```

테스트는 임시 폴더와 가짜 Codex를 사용합니다. 고정 시작 세션, 네이티브 터미널 연결,
이미지·모델·YOLO 옵션 전달, 동시 실행 방지, 백업·복구,
사용자 설치 및 `DESTDIR`를 이용한 전역 설치 구조·제거를 검사합니다.
실제 로그인·서버 응답 및 데스크톱 클립보드는 자동 테스트 범위에 포함되지 않습니다.
샌드박스에서 추상 소켓 bind가 금지되면 관련 테스트 3개는 사유를 표시하고 건너뜁니다.
