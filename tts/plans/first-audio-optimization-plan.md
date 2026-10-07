# TTS First Audio 최적화 계획서

작성자: Enikk(에닉)

## 1. 목적과 실행 승인

사용자가 실제 첫 음성을 듣기까지 기다리는 시간을 줄인다.

진행 순서:

**변경 전 측정·기록 → 한 가지 수정 → 변경 후 동일 조건 측정 → 비교 → 통과한 변경만 최종 반영**

이 문서는 계획서다. 작성만으로 benchmark, 코드 수정, TTS 재시작, commit 또는 push를 시작하지 않는다. 사용자가 실행을 지시한 뒤 작업을 시작한다.

첫 음성 지연이 최우선이다. 음질, 말끝, 내용 누락·중복, 중간 공백이 나빠지면 속도가 빨라도 채택하지 않는다.

## 2. 작업 범위

작업 repository는 `/home/ak/git/codex_enikk` 하나만 사용한다. 별도 worktree나 복제 작업 폴더는 만들지 않는다.

다음 후보를 계측 결과에 따라 우선순위를 정해 하나씩 시험한다.

1. 생성 준비 재사용: 매 요청마다 반복되는 reference 처리, 초기화, 할당 등이 실제로 있는지 확인하고 안전하게 재사용한다.
2. 첫 청크 크기 조정: 자연스러운 문장·절 경계에서 앞부분을 먼저 생성·재생할 수 있는지 확인한다.
3. 일반 문장 정규화 경로 단순화: 코드·JSON 등의 보호가 필요 없는 문장은 불필요한 검사를 줄인다.

후보는 제안이지 확정된 병목 해결책이 아니다. 이미 캐시되는 작업을 다시 캐시하거나 효과 없는 미세 최적화를 하지 않는다. 최대 3개 후보만 시험한다.

## 3. 보존 조건

- Enikk/Codex core, enikk.py, codex app-server/resume, trigger_service를 종료·재시작하지 않는다.
- kill, pkill, kill -9를 사용하지 않는다. 필요한 서비스 전환은 TTS 관리 명령만 사용한다.
- 기존 숫자·단위·기술어·해시·UUID·경로·기호·기능어 규칙을 보존한다.
- 전체 입력 문자열 exact override와 교육 행 전용 하드코딩을 추가하지 않는다.
- 기존 long-tail 경고 후 재생 정책과 170ms 후미 잡음 감쇠를 유지한다.
- retry/guard를 약화하거나 실패를 숨겨 수치를 개선하지 않는다.
- model, reference voice, 샘플링 설정, 재생 속도와 음성 정체성을 변경하지 않는다.
- sequence-gap reconcile을 변경하지 않는다.
- 사용자의 기존 미커밋 변경과 작업 외 보고서는 보존한다.

## 4. 시작 상태와 복구점

실행 시 현재 상태를 다시 확인한다. 과거 대화의 commit/release를 현재 상태로 가정하지 않는다.

기록 항목:

- 시작 시각과 종료 제한 시각
- main, origin/main, working tree 상태
- active TTS release와 source/install 일치 여부
- TTS service 및 engine PID, service generation
- ready, model_ready, playback_available, last_error
- Enikk/Codex core PID와 시작 시각
- engine, normalizer, override 파일 hash
- model/reference/tempo 설정, GPU 상태
- queue 상태와 진행 중인 재생

작업 시작 직전 정상 production release를 최우선 복구점으로 보존한다. 후보 검증이 끝나기 전 삭제하지 않는다. 복구 명령의 실제 지원 여부를 먼저 확인한다.

시작 상태가 비정상이면 benchmark나 최적화를 진행하지 않고 상태와 원인을 보고한다. 사용자 작업을 강제로 중단하거나 queue를 임의로 비우지 않는다.

## 5. 먼저 측정 기준 확정

First Audio의 목표 정의:

**첫 source 제출 → 첫 실제 음성 출력 시작**

전처리, 정규화, queue, 생성, retry, long-tail, playback 준비 시간을 모두 포함한다. 첫 청크가 실패해서 다음 청크가 재생된 경우 그 대기시간도 포함한다.

현재 재생 관찰 도구는 TTS의 PulseAudio 재생 스트림에서 신호를 관찰할 수 있지만, 물리적인 스피커 출력 시작을 직접 측정한 것은 아니다. 스트림 생성 후 관찰 도구가 붙으면 첫 신호를 놓칠 수도 있다.

측정 전에 다음을 확인한다.

- source 제출과 재생 관찰 timestamp가 비교 가능한 시간 기준인지
- 관찰 도구가 첫 신호 이전에 준비됐는지
- 다른 앱의 음성이 섞이지 않고 TTS 출력만 식별되는지
- 녹음 실패와 무음을 구분할 수 있는지
- subprocess 실행 시각과 음성 신호 시작 시각이 구분되는지

물리적 출력 측정이 가능하면 그 결과를 사용한다. 신뢰 가능한 backend 신호만 측정할 수 있으면 지표를 `backend audio onset`으로 명시하고 물리적 First Audio로 부르지 않는다. 부착 이후의 상한 추정치만 얻으면 진단용으로만 사용한다.

핵심 시작 지연을 신뢰성 있게 비교할 수 없으면 **INCONCLUSIVE**로 종료한다. 대체 지표를 실제 사용자 체감 지연 개선으로 과장하지 않는다. 측정 방식 변경이 필요하면 변경된 방식으로 baseline을 다시 확정한 뒤 A/B를 시작한다.

## 6. 시간·시도 제한

- 전체 작업은 시작부터 최대 3시간이다. 분석, benchmark, 코드 수정, 테스트, 후보 적용, 복구와 보고 시간을 포함한다.
- 첫 30분 이내에 신뢰 가능한 측정 경로와 가장 큰 지연 구간을 좁히지 못하면 INCONCLUSIVE로 중단한다.
- 코드 최적화 후보는 최대 3개다.
- 효과 없는 후보가 2개 연속이면 중단한다.
- 최종 검증과 복구 시간을 확보하지 못하면 새 후보를 시작하지 않는다.
- 시간 한도에 도달하면 새 실험을 중단한다. 후보가 불안정하거나 미검증 상태로 production에 남아 있으면 복구와 상태 확인까지 마친 뒤 종료한다.

한도 안에 필요한 측정 수를 채우지 못하면 표본을 임의로 줄여 PASS시키지 않는다.

## 7. 고정 입력과 공통 조건

입력은 수정 전에 파일로 저장하고 hash를 기록한다.

### 짧은 한국어

현재 시스템 상태는 정상이며 다음 작업을 계속 진행합니다.

### 해시 포함 기술 문장

commit 4acb675fbe30fe1f99e0e4c1a6b4ea45ba62d29f completed

### 장문

`/home/ak/tts-text-for-bench.md`

장문 파일이 없으면 임의로 다른 파일을 대신 사용하지 않는다. 실행 전 고정 장문을 준비하고 A/B 모두 같은 원문을 사용한다.

공통 조건:

- model warm, service ready, model_ready=true
- queue empty, 다른 재생 없음
- 동일 GPU, reference, tempo, audio backend/device
- 동일 원문, 제출 경로, 측정 도구와 로그 설정
- 동일 warmup 및 playback 완료 후 idle window
- 첫 청크 후보를 제외하면 동일 chunking

warmup은 측정 표본과 구분해 저장한다. 정해진 warmup 횟수와 idle window는 A 측정 전에 고정한다. chunking을 변경하는 후보는 그 차이를 명시하고 입력 내용은 바꾸지 않는다.

## 8. 변경 전 A 측정·기록

코드 수정 전에 시작 production에서 baseline을 저장한다.

- 짧은 한국어: 정확히 20회
- 해시 포함 문장: 정확히 20회
- 장문: 정확히 2회 완주

각 입력 결과를 별도로 집계한다. 서로 다른 문장의 latency를 한 median으로 섞지 않는다.

run별 기록:

- run ID, 제출 시각, 측정 조건
- 관찰 시작 준비 여부와 측정 지표 이름
- 첫 음성 시작 지연 또는 재생 실패
- retry/long-tail/recovery split 횟수와 이유
- 첫 청크 성공 여부, 첫 playback source
- queue wait, 생성 시간, 재생 준비 시간
- 관찰 도구 오류와 raw 로그

가능한 실제 처리 단계별 시간을 기록한다. 확인 불가능한 단계는 미측정으로 표시한다. 구간을 추측해서 합산하지 않는다.

통계:

- 표본 수, raw values, min, median, p95, max
- >2초, >3초, >5초, >10초 횟수
- retry, long-tail, 생성·재생 실패
- 측정 분산과 조건 재현성

p95는 nearest-rank 방식으로 고정하고, 20회 표본에서 tail 추정이 제한적임을 보고한다.

불리한 run을 삭제·교체하지 않는다. 실패 run을 성공 run으로 채우지 않는다. 첫 재생이 아예 없으면 latency는 관측되지 않은 실패로 남기고 임의의 초 값을 넣지 않는다. 실패가 있으면 성공 run median만으로 PASS하지 않는다.

## 9. 한 가지 수정과 후보 B 적용

baseline 분석에서 확인한 병목 하나를 선택한다. 변경 이유와 예상 효과를 먼저 기록한다.

최소 수정 후 관련 테스트를 수행한다. 테스트가 실패하면 후보를 적용하지 않는다.

테스트 통과 후 실제 음성을 측정하려면 후보를 TTS에 **임시 적용**해야 한다. 이 단계는 최종 채택이 아니며 아직 commit/push하지 않는다.

```bash
enikk_tts stop
enikk_tts update /home/ak/git/codex_enikk
enikk_tts start
enikk_tts status
```

candidate release와 source/install 일치 여부를 기록한다. ready, model_ready, playback_available을 확인하고 queue가 비었을 때 측정한다. core는 유지한다.

후보끼리 변경을 누적해 효과를 혼동하지 않는다. 각 후보는 동일한 시작 baseline에 대해 비교한다. 채택 후보를 조합하려면 조합본도 별도의 최종 검증을 통과해야 하며 3개 후보 한도 안에서 진행한다.

## 10. 변경 후 B 측정

A와 동일한 입력·조건·측정 수로 측정한다.

- 짧은 한국어: 정확히 20회
- 해시 포함 문장: 정확히 20회
- 장문: 정확히 2회 완주

각 run raw 결과와 실패를 모두 보존한다. GPU 부하나 관찰 조건이 달라져 비교가 불가능하면 INCONCLUSIVE로 판정한다. 유리한 결과가 나올 때까지 재측정하지 않는다.

## 11. 첫 음성 비교와 채택 기준

변화율:

`(B median - A median) / A median × 100`

이번 목표는 속도 개선이므로 단지 5% 미만 느려졌다는 이유로 채택하지 않는다.

### CLEAR IMPROVEMENT

다음을 모두 만족해야 한다.

- 두 짧은 입력 중 최소 하나에서 median이 5% 이상 및 0.10초 이상 감소한다.
- 다른 입력의 median/p95가 신뢰 가능한 기준으로 악화되지 않는다.
- 개선폭이 측정 잡음과 구분된다. paired 측정이 아니라면 독립 표본 비교를 사용하며, 선택한 분석 방법을 보고한다.
- 가능하면 bootstrap 95% 구간으로 median 변화가 개선 방향인지 확인한다. 작은 표본의 불확실성을 숨기지 않는다.
- p95, retry/long-tail, 실패, 음질과 중간 gap의 품질 조건을 만족한다.

### REGRESSION

- 어느 짧은 입력에서든 median이 5% 이상 느려지면 채택하지 않는다.
- p95 악화, 실패 증가 또는 품질 회귀가 명백하면 채택하지 않는다.
- 작은 median 악화라도 다른 입력의 큰 개선과 임의로 상쇄해 PASS시키지 않는다.

### INCONCLUSIVE / NO MATERIAL IMPROVEMENT

측정이 불안정하거나 개선이 잡음과 구분되지 않으면 INCONCLUSIVE다. 안정적이지만 개선폭이 채택 기준에 못 미치면 효과 없음으로 기록한다. 두 경우 모두 후보를 최종 반영하지 않는다.

2초는 도전 목표이며 달성 보장 조건이 아니다. 확실한 개선을 기준으로 판단한다.

## 12. 중간 gap과 내용 보호

gap 정의:

**이전 청크 실제 재생 종료 → 다음 청크 실제 재생 시작**

첫 제출부터 첫 재생까지와 마지막 재생 이후는 제외한다. 시작·종료가 backend 추정이라면 gap도 같은 한계를 명시한다.

장문 run별 기록:

- 청크 수와 gap sample 수, raw gap values
- median, p95, max
- >1초, >2초, >5초 횟수와 비율
- retry, long-tail, recovery split, playback failure
- source 순서와 누락·중복 여부

기본 보호 기준:

- median gap 증가 ≤ 0.05초
- p95 gap 증가 ≤ 0.10초
- 동일 청크 수일 때 >1초 횟수 증가 < 2개
- >2초 증가가 있으면 원인 확인 전 채택 금지
- >5초 gap와 playback failure 증가 금지

chunk 수가 달라지면 횟수만 직접 비교하지 않는다. 비율, 총 대기시간, 같은 문장 경계와 실제 청취 결과를 함께 비교한다. 재현성이 부족하면 INCONCLUSIVE로 남긴다.

## 13. 음질과 회귀 검증

A/B WAV와 해당 원문을 함께 보존한다. 동일 문장으로 비교한다.

- 음색과 발음 유지
- 말끝 잘림, 잡음·clipping 악화 없음
- 단어/문장 누락·중복 없음
- 부자연스러운 청크 절단 없음
- 170ms 후미 감쇠와 long-tail 재생 정책 유지

파형 검사만으로 자연스러운 음질을 확정하지 않는다. 청취 판단이 필요한데 확인하지 못했으면 최종 채택을 보류하고 비교 파일을 제시한다.

관련 회귀:

- 기존 교육 1~11, 해시·UUID·혼합 문장
- 코드/JSON/URL/path/version/identifier 보호
- delivery, stream, epoch, independent voice
- sequence-gap, retry, long-tail, tail-noise
- queue lifecycle 및 playback
- Python syntax와 git diff --check

실제 Enikk/Codex core를 재시작하는 테스트는 실행하지 않는다.

## 14. 실패·불확실성 시 복구

REGRESSION, INCONCLUSIVE, 효과 없음 또는 품질 확인 실패면 후보를 채택하지 않는다. 다음 후보를 준비하는 동안도 시작 정상 release를 유지한다.

복구 순서:

```bash
enikk_tts stop
enikk_tts rollback <작업 시작 직전 정상 release>
enikk_tts start
enikk_tts status
```

실제 CLI가 지원하는 동작을 사전에 확인해 사용한다. 복구 후 active release, ready, model_ready, playback_available, last_error를 기록한다. core는 건드리지 않는다.

실패 변경은 commit/push하지 않는다. 사용자의 기존 변경을 되돌리지 않고 이번 후보의 변경만 분리해 복원한다. 실패 증거와 WAV는 보존한다.

## 15. 통과한 후보 최종 반영

첫 음성, gap, 음질, 회귀 검증을 모두 통과한 후보만 반영한다. 실행 시 사용자가 승인한 Git/배포 범위에 따른다. 승인되지 않은 확대 작업은 하지 않는다.

순서:

1. 최종 diff와 검증 결과 정리
2. git diff --check
3. 승인된 변경만 commit
4. origin/main push와 main 일치 확인
5. 검증 candidate와 최종 commit의 파일 일치 확인
6. 필요한 경우 최종 main으로 TTS update/start
7. active release, ready/model_ready/playback_available 확인
8. core PID와 시작 시각이 동일한지 확인

파일이 달라진 최종 release를 검증 candidate와 같다고 가정하지 않는다. 재배포 시 source/install 일치와 정상 재생 smoke를 확인한다.

## 16. 기록과 최종 보고

보고서와 raw 결과를 repository의 `tts/reports/` 또는 사용자 상태 폴더에 저장한다. 파일명에는 실행 날짜와 시도를 포함한다.

보고 내용:

- 시작/종료 시각, 누적 시간, 후보 수
- 시작 commit/release와 복구점
- 실제 측정 지표와 측정 한계
- 가장 큰 지연 구간과 근거
- 입력별 A/B raw values, median/p95/max와 변화율
- retry/long-tail/실패 비교
- 장문 gap과 누락·중복 결과
- 후보별 수정 내용, 채택·복원 여부
- 음질 비교 파일과 청취 확인 결과
- 회귀 및 정규화 비용 변화
- CLEAR IMPROVEMENT / REGRESSION / INCONCLUSIVE / 효과 없음
- commit/push 여부, 최종 release와 service 상태
- Enikk/Codex core 종료·재시작 없음

핵심 원칙: **먼저 기록하고, 한 가지를 바꾸고, 같은 조건으로 비교하고, 실제 첫 음성이 확실히 좋아졌을 때만 반영한다.**
