# codex_enikk

**2.1.7 · Linux · Python 3.10+ · MIT**

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
실행 잠금은 에닉만 보유하며 자식에게 상속하지 않습니다. 지원되는 버전은 전용
app-server에 native TUI를 연결하며, streaming을 사용하지 못하면 `--no-daemon`으로 실행합니다.
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

실행 시 `~/.codex/AGENTS.md`의 짧은 관리 블록에 Enikk의 이름과 유래를 기록합니다.
Codex가 지원하는 전역 지침 로딩을 사용하므로 새 세션과 모델 변경 후에도 적용되며,
transcript에 identity를 복제하거나 별도의 LLM 호출을 하지 않습니다. 기존 전역 지침은 보존합니다.

## 백업과 복구

전용 저장 위치: **`/var/tmp/codex_enikk-사용자UID/`**

- 백업은 `backups/`, 10 MB 분할 대화문은 `transcripts/`, Dorothy 전달용 파일은
  `latest/`에 저장합니다. 현재 작업 폴더와 Git 저장소 안에는 만들지 않습니다.
- 시작 전과 정상 종료 시 `backups/`에 날짜별 `.tar.gz`를 생성합니다. 자동 삭제하지 않습니다.
- `$CODEX_HOME`(기본 `~/.codex`)의 `sessions/`, `archived_sessions/` 아래 JSONL,
  `history.jsonl`, `session_index.jsonl`, `enikk-continuity.json`을 저장합니다.
- Codex 0.158.0의 `state_5.sqlite`와 `thread_history_1.sqlite`도 있으면 포함합니다.
  Python SQLite backup API로 committed WAL까지 snapshot을 만들며, 실행 중 DB 본체를 단순 복사하지 않습니다.
  스레드 이름·분기 이력·대화 및 DB 내부 attachment metadata를 보존합니다.
  로그·queue·모델/cache·goals/memories DB·외부 첨부 파일·프로젝트 파일은 포함하지 않습니다.
- format 2 manifest에 CLI 버전, 원본 CODEX_HOME, 포함 파일, SHA-256 및 snapshot 시간을 기록합니다.
  복원 전에 archive 전체와 SQLite 무결성·rollout 참조를 검증합니다.
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

Codex와 앱을 종료한 뒤 **빈 CODEX_HOME**에 복구하세요:

```bash
CODEX_HOME="$HOME/codex-recovered" codex_enikk_restore /path/to/backup.tar.gz
# 이 CODEX_HOME에서 로그인/설정을 별도로 준비한 뒤 실행:
CODEX_HOME="$HOME/codex-recovered" codex_enikk
```

SQLite가 포함된 백업은 기존 SQLite/WAL 또는 겹치는 대화 파일이 있으면 쓰기 전에 거부합니다.
DB를 덮어쓰거나 row를 병합하지 않습니다. 복원한 DB의 `threads.rollout_path`는 새 CODEX_HOME으로
변경하므로 이전 원본 rollout에 쓰지 않습니다. 작업 폴더와 외부 프로젝트/첨부 파일 경로까지 이전하지는 않습니다.
기존 JSONL-only 백업은 계속 지원하며, 종전처럼 누락 파일만 복구하고 기존 파일은 유지합니다.
단, 0.158.0에서 JSONL-only 복원은 직접 대화를 재구성해도 스레드 이름이나 분기 이전 이력을
완전히 보존하지 못할 수 있습니다. 현재 구현은 JSONL과 두 SQLite를 함께 보관합니다.
별도 복구는 로그인·설정이나 기존 데이터베이스 병합을 제공하지 않습니다.
이전 1.0.0 백업에는 연결 기록이 없습니다. 해당 백업 복구 후 처음 실행하면 최초 연결 규칙이 적용됩니다.

실행 중 snapshot은 각 DB 내부에서 일관되지만 여러 DB와 JSONL 전체가 한 트랜잭션은 아닙니다.
정확한 동일 시점의 전체 백업이 필요하면 **모든 Codex 쓰기 작업을 종료한 상태에서 백업**하세요.
rollout 누락 또는 DB의 기록 위치가 JSONL 크기를 넘어가면 백업을 실패 처리하고 재시도를 요구합니다.
복원은 항상 Codex 종료 상태에서 수행합니다. 생성 파일을 기존 archive 위에 덮어쓰지 않습니다.

| 환경변수 | 기본값 |
| --- | --- |
| `CODEX_HOME` | `~/.codex` |
| `CODEX_ENIKK_DATA_DIR` | `/var/tmp/codex_enikk-사용자UID` |

저장 위치는 절대 경로이며 Git 저장소 밖이어야 합니다. 해당 폴더 권한을 700으로 변경합니다.
`CODEX_HOME`을 바꾸면 별도의 연결 기록을 사용합니다.

대화 연속성은 **같은 세션과 기록 유지**를 뜻합니다. 모델의 문맥 압축이나 모든 과거 내용의 완전한 기억까지
보장할 수는 없습니다. 프로젝트 파일·시스템 전체·실행 중 프로세스는 백업하지 않습니다.
강제 종료·전원 차단 시 마지막 백업 이후 내용은 백업에 없을 수 있습니다.
다른 프로그램이 동시에 쓰는 JSONL의 마지막 미완성 줄은 그대로 보존하고 텍스트 변환에서는 건너뜁니다.
`auth.json`과 설정·키 파일은 포함하지 않지만 대화에 입력한 비밀정보는 기록에 포함될 수 있으므로 공개하지 마세요.

## Dorothy 전달용 최신 대화

`/var/tmp/codex_enikk-사용자UID/latest/codex-latest-YYMMDD-HHMMSS.txt`를 실행마다 하나씩 만들고, 현재 연결된 세션에서
약 2초마다 같은 파일을 갱신합니다. 파일명은 최초 저장 시각(시스템 현지 시간)입니다.
이전 실행의 파일은 보존합니다.
사용자·Codex 진행·최종 메시지만 로컬 JSONL에서 읽습니다. TTY, resume 및 전체 10MB archive는 변경하지 않습니다.

UTF-8 기준 200,000바이트는 목표 크기입니다. 오래된 메시지를 완전한 단위로 제거하고
최신 메시지와 최신 최종 답변을 우선 보존합니다. 이 필수 메시지들이 목표 크기를 넘으면
자르지 않고 온전히 보존합니다. 요약이나 LLM 호출, Dorothy API 호출은 없습니다.
필요할 때 이 TXT를 사용자가 직접 Dorothy에게 업로드합니다.

## 선택적 로컬 TTS

`codex_enikk`는 설치된 TTS 의존성을 찾으면 CODEX 진행 메시지와 최종 메시지를 확정된
유키짱 음성으로 읽습니다. 사용자 입력, reasoning, 도구 출력과 로그는 읽지 않습니다.
Chatterbox 모델과 SUPER-CLEAN C2 conditioning은 worker 시작 시 한 번 준비하고 재사용합니다.
음성 설정과 설치 요구사항은 [`tts/README.md`](tts/README.md)에 있습니다.

TTS 의존성이 없거나 TTS가 실패해도 Codex TUI, 세션 연속성, 백업과 transcript는 계속
동작합니다. Chatterbox 모델, WAV, 세션 파일과 인증 정보는 저장소나 관리 설치에 포함하지 않습니다.

신규 Ubuntu 설치는 `python3-venv`, `alsa-utils`, `libsndfile1`과 전용 venv를 준비하고
`chatterbox-tts==0.1.7`을 설치합니다. CUDA가 있으면 GPU를, 없으면 CPU를 사용합니다.
`CODEX_ENIKK_TTS=0`은 실행 시 TTS를 끄고,
`CODEX_ENIKK_INSTALL_TTS=0`은 설치·업데이트 중 선택 구성 준비를 건너뜁니다. 제거 시
관리 설치 파일만 제거하며 사용자 venv, reference와 모델 cache는 보존합니다.

### TTS 사용법

Ubuntu 22.04 이상에서 일반적인 전역 설치는 다음과 같습니다. 설치 프로그램이 필요한
Ubuntu 패키지와 전용 Python 환경을 준비합니다.

```bash
git clone https://github.com/decryp2kanon/codex_enikk.git
cd codex_enikk
sudo ./install.sh
cd /path/to/existing-project
codex_enikk
```

별도 TTS 명령을 실행할 필요는 없습니다. `codex_enikk`를 실행하면 TTS worker가 함께
시작되고, 화면에 완성되어 표시된 CODEX 진행 메시지와 최종 답변을 순서대로 읽습니다.
Chatterbox 모델은 최초 실행 때 정상 사용자 cache로 자동 다운로드되고 persistent worker가
한 번 로드한 뒤 재사용합니다. bundled `yuki_super-clean.wav`도 자동 설치되고 실제로 열어
검증합니다. 기존 reference와 venv는 업데이트 때 덮어쓰거나 삭제하지 않습니다.
다른 승인된 reference를 명시적으로 설치하려면
`CODEX_ENIKK_CHATTERBOX_REFERENCE_SOURCE=/path/reference.wav`를 설치 명령에 지정합니다.

한국어 문장 안의 주요 영문 기술어는 TTS 내부에서 한국식 발음으로 바꾸고 계속 한국어로
합성합니다. 화면에 표시되는 원문은 변경하지 않습니다. 각 chunk는 완성되는 즉시 재생
queue에 들어가므로 뒤쪽 문장 전체의 합성을 기다리지 않습니다.

단일 줄바꿈은 같은 대화 흐름으로 이어 읽고, 빈 줄은 짧은 문단 호흡으로 처리합니다.
모델이 만든 앞뒤 silence도 정리하여 chunk 경계에서 긴 공백이 누적되지 않게 합니다.
화면 텍스트는 바꾸지 않으며 이 처리는 음성 합성 내부에만 적용됩니다.

관리자 권한 없이 사용자 경로에 설치하려면 OS 패키지만 먼저 준비합니다.

```bash
sudo apt-get update
sudo apt-get install alsa-utils
PREFIX="$HOME/.local" ./install.sh
export PATH="$HOME/.local/bin:$PATH"
codex_enikk
```

한 번만 음성을 끄거나, TTS 구성 없이 설치·업데이트하려면 다음 환경변수를 사용합니다.

```bash
CODEX_ENIKK_TTS=0 codex_enikk
sudo env CODEX_ENIKK_INSTALL_TTS=0 ./install.sh
sudo env CODEX_ENIKK_INSTALL_TTS=0 bash ./update.sh
```

설치 후 TTS 구성만 다시 준비하려면 설치 경로의 setup script를 실행합니다.

```bash
# 기본 전역 설치
sudo /usr/local/lib/codex_enikk/tts/setup-tts.sh

# 사용자 PREFIX 설치
"$HOME/.local/lib/codex_enikk/tts/setup-tts.sh"
```

업데이트는 새로 받은 source 폴더에서 실행하고, 실행 중인 `codex_enikk`를 종료한 뒤 다시
시작합니다.

```bash
git pull --ff-only
sudo bash ./update.sh
codex_enikk
```

문제가 있으면 다음 항목으로 설치 상태를 확인할 수 있습니다. TTS가 실패해도 Codex의
세션 연속성, 백업, transcript와 TUI는 계속 동작합니다.

```bash
$HOME/Apps/chatterbox-yuki/.venv/bin/python -c 'import chatterbox, torch; print(torch.cuda.is_available())'
command -v aplay
tail -n 50 "$HOME/.local/state/codex_enikk/tts/notify.log"
```

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

### 문장 단위 streaming TTS

Codex 0.158.0에서는 app-server streaming이 기본입니다. wrapper가 native TUI,
private server, helper를 관리합니다. `CODEX_ENIKK_STREAMING_TTS=0`, 미지원
Codex 버전 또는 초기화 실패 시 기존 `--no-daemon`과 완료 메시지 TTS를 사용합니다.
명확한 한국어 문장 종료는 다음 delta나 final을 기다리지 않고 독립 job으로
즉시 전달합니다. 소수·도메인·경로처럼 불확실한 점은 lookahead 보호를 유지합니다.
시작 시 모델 준비를 확인한 뒤 TUI를 열며, streaming 또는 fallback 상태와 이유를
표시합니다. 실행마다 TTS queue를 분리하므로 종료·재시작 후 이전 대사는 자동 재생하지 않습니다.
내부 long-tail 이중 실패에는 제한된 절 분할 복구를 적용합니다. 파일 경로는
화면 원문을 보존하고 TTS에서만 파일명·확장자 중심 한국어 설명으로 변환합니다.
내부 anomaly는 재생 전에 차단하며, 제한된 복구 후 정상 재생되면 성공으로
계산합니다. 최종 실패·누락·중복·순서 오류는 성공으로 계산하지 않습니다.
실패 내용은 보존되며, 자동 무한 재시도는 하지 않습니다. 상세 정책은
[tts/README.md](tts/README.md)를 참고하세요.

## 최근 대화 복사

실행 중인 에닉 대화는 `~/codex-latest.txt`에 `[USER]` / `[ENIKK]` 일반 텍스트로 자동 갱신됩니다. 최대 200,000바이트이며 오래된 메시지부터 제거합니다. 단일 메시지가 제한보다 크면 UTF-8 경계를 지켜 최신 부분만 남깁니다. 영구 백업이 아닌 현재 대화의 편의용 미러입니다. `gedit ~/codex-latest.txt`에서 열고 새로 불러와 복사할 수 있습니다.

대화 DB는 별도 백그라운드 작업에서 읽기 전용으로 확인하며 보통 1초 이내에 반영합니다. 현재 스레드를 재개하면 이전 텍스트도 복원되지만 이전 실행의 TTS는 재생하지 않습니다. Streaming 모드의 새 스레드 생성/첫 입력도 자동 추적합니다. TTS 비활성화 또는 legacy 모드에서는 wrapper가 시작한 스레드를 표시합니다. 원본 Codex 기록과 기존 백업 파일은 변경하지 않습니다.

## Codex 업데이트 전 호환성 검사

Codex를 교체하기 전에 명시적인 binary를 검사할 수 있습니다. 검사기는 버전을 설치하거나 업데이트하지 않습니다.

```bash
check-codex-compat /path/to/codex
# 계정에서 사용할 모델을 지정하거나 JSON 결과를 받으려면:
check-codex-compat /path/to/codex --model gpt-6-astra --json
```

`/tmp/enikk-compat-*` 안에 별도 HOME/CODEX_HOME·thread·socket을 만들고 실제 native TUI remote 연결,
문장 delta/완료, 읽기 전용 `pwd` tool, interruption, SQLite/rollout, 현재 latest parser와 snapshot 호환성을 검사합니다.
승인 흐름은 안전한 명령에 강제 승인을 요구하지 않고 candidate가 제공하는 request/decision schema 수준으로 확인합니다.
로그인 정보는 기본 CODEX_HOME의 `auth.json`만 읽어서 임시 홈으로 복사합니다. `--auth-file /path/auth.json`으로
명시할 수도 있습니다. 실제 대화·설정·TTS queue·latest 파일은 사용하지 않습니다. 짧은 모델 요청이 발생하므로
로그인과 네트워크가 필요합니다. Chatterbox나 GPU 모델은 실행하지 않습니다.

기존 TTS venv의 `websocket-client`를 사용하며 별도 dependency를 설치하지 않습니다. venv가 없으면 system Python을
사용하고 WebSocket dependency 부재를 실패로 보고합니다. 성공/실패 모두 process와 임시 데이터·인증 복사본을 정리합니다.
전체 timeout 기본값은 240초이며 `--timeout 30..300`으로 제한할 수 있습니다. exit 0은 `COMPATIBLE`, 그 외는 실패입니다.
FAIL 결과에는 위치와 expected/observed가 포함됩니다. 인증·네트워크 실패 역시 검증 미완료이므로 통과시키지 않습니다.

현재 wrapper는 Codex 0.158.0에 명시적으로 고정되어 있습니다. 다른 candidate가 protocol 검사를 통과해도
`wrapper version gate`에서 이를 알리고 `INCOMPATIBLE`로 판정합니다. 검사기가 pin을 자동 변경하지 않습니다.
새 버전 허용은 검증 결과를 검토한 뒤 별도 변경으로 진행합니다. 26초 수준의 TTS warmup 최적화는 이 검사의 범위가 아닙니다.
