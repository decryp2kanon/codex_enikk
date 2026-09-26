# codex_enikk

**2.0.0 · Linux · Python 3.10+ · MIT**

하나의 대화를 계속 이어가는 앱입니다. 처음 연결한 세션을 고정하고 매번 같은 ID로 재개합니다.
새 대화 생성, 포크, 세션 선택, 세션 전환 기능은 없습니다.

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
기존 명령은 덮어쓰지 않습니다. 업데이트 시 기존 설치를 제거한 뒤 재설치하세요.

## 하나의 대화

첫 실행은 유효한 `CODEX_THREAD_ID`가 있으면 해당 대화, 없으면 현재 작업 폴더의
가장 최근 기존 대화를 연결합니다. 그 ID는 `$CODEX_HOME/enikk-continuity.json`에 저장됩니다.
이후 작업 폴더가 바뀌거나 다른 프로그램에서 새 세션을 만들더라도 연결된 ID를 유지합니다.
연결 기록은 직접 지우거나 편집하지 마세요. 기록까지 없애면 최초 연결로 처리됩니다.

```bash
codex_enikk             # 연결된 하나의 대화
codex_enikk --resume    # 호환 옵션: 같은 대화 재개, 선택 화면 없음
codex_enikk --help
codex_enikk --version
```

한 줄씩 입력하고 Enter를 누르면 응답합니다. Ctrl+D로 종료합니다.
`--new`, `--fork`, `fork`, `--resume ID`, 임의의 추가 CLI 옵션은 거부합니다.
`/fork`, `/new`, `/resume`을 포함한 슬래시 명령도 Codex로 전달하지 않습니다.
Codex 기본 TUI를 열지 않으므로 앱 안에 포크·세션 선택 화면이 없습니다.
같은 Codex 데이터 경로에서 이 앱을 동시에 두 번 실행할 수 없습니다.

연결된 세션 파일이 없거나 손상된 연결 기록, 재개 실패, 다른 세션 ID 응답이 발생하면 중단합니다.
다른 세션이나 새 대화로 자동 전환하지 않습니다. 원본이 유실되면 백업을 복구하세요.

내부적으로 [OpenAI 공식 비대화형 실행 방식](https://developers.openai.com/codex/noninteractive/)의
`codex exec resume SESSION_ID --json --skip-git-repo-check -`를 사용합니다.
세션 ID와 응답 완료 이벤트를 확인합니다. 입력은 표준입력으로 전달하며 셸 명령으로 실행하지 않습니다.
Codex 자체를 수정하지 않으며, 앱 밖에서 직접 실행한 Codex의 기능까지 차단하지는 않습니다.

이 입력 화면은 단일 행 텍스트만 지원합니다. 기본 TUI의 이미지 첨부·슬래시 명령·대화형 승인 화면은 없습니다.
권한을 자동 해제하지 않으며 Codex의 비대화형 실행 권한 설정을 따릅니다.
승인이 필요한 작업은 거부되거나 실패할 수 있습니다.

## 백업과 복구

기본 백업 위치: **`~/git/codex-enikk-session-backups/`**

- 시작 전, 응답 완료 후, 정상 종료 시 날짜별 `.tar.gz`를 생성합니다. 자동 삭제하지 않습니다.
- `$CODEX_HOME`(기본 `~/.codex`)의 `sessions/`, `archived_sessions/` 아래 JSONL,
  `history.jsonl`, `session_index.jsonl`, `enikk-continuity.json`을 저장합니다.
- 연결된 세션의 사용자·어시스턴트 텍스트를 약 2초마다 `transcripts/`에 저장합니다.
- 폴더 권한은 700, 아카이브·대화문·연결 기록은 600입니다.
- 시작 백업이 실패하면 대화를 시작하지 않습니다. 종료 저장 실패도 오류로 알립니다.

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

테스트는 임시 폴더와 가짜 Codex를 사용합니다. 고정 세션, 분기 차단, 동시 실행 방지, 백업·복구,
사용자 설치 및 `DESTDIR`를 이용한 전역 설치 구조·제거를 검사합니다.
실제 로그인·서버 응답은 자동 테스트 범위에 포함되지 않습니다.
