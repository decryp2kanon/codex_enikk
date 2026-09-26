# codex_enikk

**버전 1.0.0 · Linux · Python 3.10+ · MIT**

명령 하나로 마지막 Codex 세션을 이어가고, 시작 전·종료 후 대화를 로컬 백업합니다.
별도의 Python 패키지나 jq가 필요하지 않습니다. OpenAI 공식 제품이 아닌 독립적인 CLI 래퍼입니다.

## 설치

먼저 로그인 가능한 [Codex CLI](https://developers.openai.com/codex/cli/)와 Python 3.10 이상,
Bash, GNU coreutils, Git을 준비하세요. 설치 프로그램은 시스템 패키지나 NVIDIA 드라이버를 변경하지 않습니다.

```bash
git clone https://github.com/decryp2kanon/codex_enikk.git
cd codex_enikk
sudo ./install.sh
codex_enikk --version
```

기본 설치 위치는 `/usr/local/bin` 및 `/usr/local/lib/codex_enikk`입니다.
설치 후에는 일반 사용자로 실행하세요. Codex 자체는 설치하거나 업데이트하지 않습니다.
이미 설치된 프로그램과 같은 이름의 명령이 있으면 덮어쓰지 않고 중단합니다.
업데이트는 기존 설치를 제거한 뒤 다시 설치하세요. 세션과 백업은 유지됩니다.

관리자 권한 없이 설치하려면:

```bash
PREFIX="$HOME/.local" ./install.sh
export PATH="$HOME/.local/bin:$PATH"
```

설치 없이 소스 폴더에서 `./codex_enikk` 또는 `./codex_session_save.sh`로 실행할 수도 있습니다.

## 사용법

항상 작업하던 프로젝트 폴더에서 실행하세요.

```bash
cd /path/to/project
codex_enikk                       # codex resume --last
codex_enikk --resume              # 세션 선택 화면
codex_enikk --resume SESSION_ID   # 특정 세션 재개
codex_session_save.sh             # 호환 명령: 동일하게 마지막 세션 재개
codex_enikk --help
```

`--new`는 지원하지 않고 오류로 종료합니다. 나머지 옵션은 `codex resume`에 전달합니다.
권한 승인·샌드박스 설정은 Codex 자체 설정을 따릅니다. 권한 검사를 자동으로 해제하지 않습니다.
[공식 CLI 문서](https://developers.openai.com/codex/cli/reference/)와 `codex resume --help`를 참고하세요.

`--last`는 Codex가 현재 작업 폴더에 대해 판단한 마지막 세션입니다.
다른 세션을 만들거나 다른 폴더에서 실행하면 원하는 세션과 다를 수 있습니다.
이때 `--resume`으로 선택하거나 `--resume SESSION_ID`로 원래 작업을 이어가세요.
원본 세션이 없다면 재개가 실패할 수 있습니다. 이 프로그램은 새 세션을 대신 만들지 않습니다.

## 백업과 복구

기본 저장 위치는 **`~/git/codex-enikk-session-backups/`** 입니다.

- 실행 전·종료 후 각각 날짜가 붙은 `.tar.gz`를 생성합니다. 백업을 자동 삭제하지 않습니다.
- `$CODEX_HOME`(기본 `~/.codex`)의 `sessions/`, `archived_sessions/` 아래 JSONL,
  `history.jsonl`, `session_index.jsonl`을 저장합니다.
- `auth.json`, 설정 파일, API 키 파일, 작업 프로젝트 파일은 백업 대상이 아닙니다.
  단, 대화 자체에 입력한 비밀정보는 대화 백업에 포함될 수 있으므로 공개하지 마세요.
- 백업 폴더는 700, 아카이브와 대화문은 600 권한을 사용합니다.
- 실행 중 변경된 현재 작업 폴더의 세션을 약 2초마다 `transcripts/`에 읽기 쉬운 텍스트로 저장합니다.
  같은 폴더의 동시 세션은 세션 ID별 파일에 분리됩니다. 다른 폴더 세션도 전체 JSONL 백업에는 포함됩니다.
- 사용자·어시스턴트 텍스트만 대화문에 표시합니다. 도구 실행 기록 등은 원본 JSONL 백업에 남습니다.
- 시작 전 백업 실패 시 Codex를 시작하지 않습니다. 종료 시 저장 실패는 오류로 알려줍니다.
  정상 저장 시 Codex의 종료 코드를 유지합니다.

실수로 새 세션을 열었어도 기존 세션이 남아 있으면 `--resume`으로 돌아갈 수 있습니다.
파일까지 유실된 경우 Codex를 종료한 뒤 복구하세요:

```bash
codex_enikk_restore "$HOME/git/codex-enikk-session-backups/codex-enikk-날짜.tar.gz"
codex_enikk --resume
```

복구 명령은 **누락된 파일만 복구**하며 기존 파일을 덮어쓰거나 합치지 않습니다.
기존 세션 파일이 손상되었다면 별도 폴더에서 백업을 확인할 수 있습니다:

```bash
CODEX_HOME="$HOME/codex-recovered" codex_enikk_restore /path/to/backup.tar.gz
```

별도 경로 복구는 로그인·설정까지 복구하지 않으며, 기존 세션 인덱스/데이터베이스와의 자동 병합도 하지 않습니다.
복구한 세션이 목록에 없으면 해당 세션 ID로 재개하세요.

이것은 대화 기록 백업입니다. 프로젝트 코드, 실행 중 프로세스, 시스템 전체 복원이나
모델의 모든 문맥 유지를 보장하지 않습니다. 원본 파일을 읽는 시점에 다른 Codex가 쓰는 중이면
아카이브에 마지막 미완성 줄이 포함될 수 있습니다. 텍스트 변환에서는 미완성 줄을 건너뜁니다.
강제 종료·전원 차단 시 종료 백업은 실행되지 않습니다. 필요하면 별도로 프로젝트도 백업하세요.

설정 가능한 환경변수:

| 이름 | 기본값 | 역할 |
| --- | --- | --- |
| `CODEX_HOME` | `~/.codex` | Codex 데이터 위치 |
| `CODEX_ENIKK_BACKUP_DIR` | `~/git/codex-enikk-session-backups` | 아카이브 위치 |
| `CODEX_ENIKK_LOG_DIR` | 백업 위치 아래 `transcripts` | 텍스트 대화문 위치 |

지정한 백업·대화문 폴더의 권한을 700으로 설정하므로 전용 폴더를 지정하세요.

## 제거

소스 폴더에서:

```bash
sudo ./uninstall.sh
# 사용자 설치였다면:
PREFIX="$HOME/.local" ./uninstall.sh
```

소스 폴더가 없으면 `sudo /usr/local/lib/codex_enikk/uninstall.sh`를 사용할 수 있습니다.
Codex 자체, 원본 대화, 백업 폴더는 제거하지 않습니다.

## 테스트

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh uninstall.sh codex_enikk codex_session_save.sh codex_enikk_restore
```

테스트는 임시 폴더와 가짜 Codex 실행 파일을 사용합니다. 실제 계정·대화·시스템 설치 경로를 변경하지 않으며
API 호출을 하지 않습니다. `DESTDIR`를 이용한 `/usr/local` 설치와 사용자 경로 설치·제거를 검증합니다.
실제 Codex 서버와의 로그인·대화 응답은 자동 테스트 범위에 포함되지 않습니다.
