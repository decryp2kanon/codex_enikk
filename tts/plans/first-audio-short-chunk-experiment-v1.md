작성자: Enikk(에닉)

# 첫 음성 극단적 단축 실험 계획서 v1

## 1. 목적과 현재 상태

현재의 자연스러운 음성과 빠른 응답을 복구 기준으로 보존한다. 첫 생성 청크를 과감하게 줄여 실제 첫 음성이 얼마나 빨라지는지 확인하고, 부자연스러운 경우 첫 청크 길이를 단계적으로 늘린다.

현재 확인한 main: `a41e3232fc852d0346033aebb2c70d8487e22ca1`
현재 active TTS release: `b9b120d6ebeb129c`

이 값은 계획서 작성 시 확인한 값이다. 실제 실행 시작 시 HEAD, origin/main, active release, working tree, TTS 상태를 다시 확인하며, 시작 직전 production을 최우선 복구점으로 사용한다.

기존 한국어 고정 문장 20회 측정에서는 오디오 출력 신호 시작 기준 median이 2.782초에서 2.102초로 약 0.680초, 24.4% 감소했다. 이는 해당 문장의 결과이며 모든 문장에 적용되는 개선율이 아니다. 해시 입력 median은 거의 같았다. 물리적 스피커 발음 시작 시점은 미측정이었다.

사용자는 현재 음성의 자연스러움과 음량에 문제가 없다고 확인했다. 간헐적 클릭/팝은 아직 원인이 미확정이다. 이번 실험은 클릭 제거 작업과 섞지 않는다.

## 2. 성공 기준

1. 현재 production 대비 첫 음성이 재현 가능하게 빨라진다.
2. 첫 소리 뒤에 다음 청크를 기다리는 긴 공백이 생기지 않는다.
3. 단어 누락·중복·말끝 잘림이 없다.
4. 음량, 음색, 발음, 클릭/팝이 악화되지 않는다.
5. 해시·UUID·숫자·단위·경로와 기존 교육 규칙을 유지한다.

첫 소리만 빨라지고 이후 멈추는 후보는 채택하지 않는다. 아주 짧은 첫 음절을 잘라 지표만 개선하지 않는다. 한 단어만 발화하는 후보는 공격적 청취 실험으로만 허용하며, 최종 채택에는 자연스러운 이어짐 확인이 필요하다.

## 3. 허용 범위와 금지 사항

작업은 `/home/ak/git/codex_enikk` 하나에서 수행한다. 별도 worktree나 별도 repository 복사본을 만들지 않는다. 진단 WAV와 측정 자료는 기존 사용자 상태 디렉터리에 보존할 수 있다.

수정 범위는 첫 생성 청크의 분할 정책으로 제한한다. 기존 나머지 청크 정책은 가능한 한 그대로 유지하며, 첫 청크의 나머지 텍스트를 중복 없이 다음 청크에 전달한다.

Enikk/Codex core, enikk.py, codex app-server, codex resume, trigger_service를 종료하거나 재시작하지 않는다. kill/pkill 명령을 사용하지 않는다. 필요할 때 TTS 서비스만 stop/update/start한다.

모델, reference voice, 샘플링 설정, playback tempo, guard/retry, sequence-gap reconcile, long-tail 경고 후 재생 정책, 170ms 후미 잡음 감쇠는 변경하지 않는다. 음량 보정이나 fade/crossfade를 동시에 추가하지 않는다.

전체 문장 exact override, 특정 교육 행 하드코딩, 단어 중간 절단, 숫자·단위·해시 설명·UUID·경로의 의미 단위 중간 절단을 금지한다. 보호된 코드/URL/path 경계를 우회하지 않는다.

## 4. 시간과 후보 제한

전체 wall-clock은 최대 3시간이다. 상태 확인, 계측, 수정, 테스트, TTS 적용, 청취 대기, benchmark, rollback 시간을 포함한다.

첫 30분 안에 현행 첫 청크 길이, 실제 생성/재생 흐름, 계측 가능 지점을 확인하지 못하면 INCONCLUSIVE로 종료한다.

코드 후보는 최대 3개다. 효과 없는 후보가 2개 연속 나오면 중단한다. 청취 대기는 후보 유지 승인으로 간주하지 않는다. 시간 만료 시 신규 작업을 시작하지 않고 복구·상태 확인·결과 보고만 마무리한다. 복구에 필요한 시간은 별도로 확보한다.

## 5. 공격적 후보 설계

길이는 정규화된 발화 텍스트 기준이며, 아래 값은 절대 절단 위치가 아닌 탐색 목표다. 기존 parser가 찾은 안전한 단어/구절 경계를 우선한다. 안전한 경계가 없으면 기존 분할 정책을 유지한다.

| 후보 | 탐색 목표 | 진행 조건 |
|---|---|---|
| 1: 공격적 | 약 6~10글자, 완전한 1~2단어 또는 짧은 구절 | 첫 단어 누락 없이 발화 가능한 경계가 있을 때 |
| 2: 완화 | 약 10~14글자, 2~3단어 또는 짧은 구절 | 후보 1의 호흡·음량·중간 공백 문제가 확인될 때 |
| 3: 보수적 | 약 14~18글자, 자연스러운 구절 | 후보 2도 문제가 있거나 개선이 불충분할 때 |

문장을 외워 분할하지 않는다. 일반적인 단어·구절 경계로 처리한다. 한국어 조사의 부착과 기술 표현의 구조를 보존한다. 첫 청크가 짧아져 생성된 음성이 무음이거나 실패하면 실패로 기록하며, guard를 완화하지 않는다.

후보 1이 속도와 청취 검증을 모두 통과하면 후보 2·3은 만들지 않는다. 후보 간 여러 정책을 동시에 변경하지 않는다. 짧은 청크로 인해 추가 청크 수가 늘어난 사실을 결과에 기록한다.

## 6. 실행 전 기록

- HEAD 및 origin/main, working tree 상태
- active release와 rollback release
- engine/normalizer 파일 hash 및 source/install parity
- TTS PID, service generation, run generation
- ready, model_ready, playback_available, last_error
- Enikk/Codex core PID와 시작 시각
- output device/sink, sink volume, playback stream volume
- reference 및 tempo 설정
- GPU/model warm 상태, queue 상태

관련 없는 미커밋 파일을 수정하거나 stage하지 않는다. 시작 직전 release를 삭제하지 않는다.

## 7. 입력과 비교 조건

고정 짧은 입력은 최소 다음 세 종류로 분리한다.

1. 한국어: `현재 시스템 상태는 정상이며 다음 작업을 계속 진행합니다.`
2. 해시 포함: `commit 4acb675fbe30fe1f99e0e4c1a6b4ea45ba62d29f completed`
3. 실제 길고 복합적인 문장: 실행 전 미학습 혼합 문장 1개를 확정하고 A/B에서 동일하게 사용한다.

장문은 `/home/ak/tts-text-for-bench.md`를 사용한다. 파일 hash를 기록하며 실험 중 입력을 바꾸지 않는다. 공격적 첫 분할이 실제 적용되는 장문 입력도 별도로 1개 확보한다. 기존 장문의 첫 청크가 변경되지 않는다면 그 결과는 일반 회귀 확인으로만 해석한다.

동일 reference, 모델/샘플링, tempo, GPU, audio device, 제출 경로, idle window, timer, recording 조건을 유지한다. chunking은 이번 후보 변수이므로 변경을 허용하지만 정확한 전후 분할 목록을 기록한다.

서비스 재시작 후 warmup은 입력별 1회 이상 동일하게 수행하고 측정에서 분리한다. queue empty와 unrelated playback 부재를 확인한다. idle window는 2초로 고정하고 실제 추가 대기를 함께 기록한다.

## 8. First Audio 계측

정의는 최초 source 제출부터 첫 실제 재생 시작까지다. queue, 전처리, 생성, retry, 첫 청크 실패 후 다음 청크까지의 대기를 모두 포함한다.

실제 장치 시작을 신뢰성 있게 측정하지 못하면 그 지점은 UNMEASURED로 기록한다. 출력 sink monitor 신호 시작은 backend onset estimate라고 명시한다. paplay 실행 시각이나 generate_end를 실제 첫 재생 시작이라고 부르지 않는다.

monitor는 제출 전에 연결하고 다른 소리의 개입을 확인한다. 신호 감지 threshold와 녹음 gain은 A/B에서 동일하게 유지한다. 음량이 달라지면 threshold 통과 시점의 영향도 확인한다.

각 입력의 A/B 측정은 20회씩을 최종 비교 기준으로 한다. 초기 후보 선별은 입력별 5회까지 허용하지만 이를 최종 합격 근거로 쓰지 않는다. 선별·warmup·최종 run을 별도 표기하며 불리한 run을 삭제하거나 교체하지 않는다.

한 baseline을 후보들의 공통 기준으로 사용할 수 있으나 출력 설정이나 부하가 달라졌다면 비교 신뢰도를 재검토한다. 시간 부족을 이유로 표본 수를 줄여 PASS하지 않는다.

재생이 전혀 발생하지 않은 run은 실패 수와 timeout을 기록하며 성공 run 통계에서 조용히 제거하지 않는다. 재생 실패가 있는 후보는 최종 채택하지 않는다.

## 9. 기록할 지표

각 입력별 sample count, raw latency, min/median/p95/max, retry, long-tail 경고, 실패, 첫 청크 길이, 생성 시간, 청크 수를 기록한다.

가능한 경우 전처리, queue wait, generation, 재생 dispatch, backend onset을 분리한다. 계측되지 않은 구간을 추정값으로 채우지 않는다.

목표는 2.102초에서 추가 개선을 찾는 것이지만 현재 재측정 baseline을 실제 기준으로 사용한다. 1초 이하 등 특정 숫자의 달성을 보장하지 않는다.

## 10. 중간 공백 보호

첫 청크 실제 종료부터 둘째 청크 시작까지의 gap을 별도로 기록한다. 이 구간을 장문 전체 median 속에 묻지 않는다.

장문에서는 전체 gap sample 수, median/p95/max, >1초/>2초/>5초 count와 비율, retry/long-tail/recovery split/failure를 기록한다. First Audio 및 마지막 tail은 중간 gap에서 제외한다.

기본 허용 기준은 다음과 같다.

- 첫 청크 뒤 gap median: baseline 대비 +0.05초 이내
- 첫 청크 뒤 gap p95: baseline 대비 +0.10초 이내
- 전체 gap median: +0.05초 이내
- 전체 gap p95: +0.10초 이내
- 새롭게 반복되는 >1초 gap, >2초/>5초 gap 증가가 있으면 채택 보류
- playback failure 증가 금지

청크 수가 바뀌므로 단순 count 외에 발생 비율과 첫 경계 자체를 함께 비교한다. backend frame gap, threshold 기반 audible gap, dispatch 로그 gap을 구분한다. 실제 장치 gap이 미측정이면 명시한다.

## 11. 음질·음량·클릭 검증

원본 A와 후보 B의 첫 문장 및 이어지는 청크 WAV를 보존한다. 비교 파일의 PCM을 임의로 증폭하거나 정규화하여 후보의 음량 문제를 감추지 않는다.

음량은 녹음 전체 RMS 외에 발화 구간 RMS/peak를 함께 기록한다. sink와 stream gain 차이를 먼저 확인한다. clip saturation과 큰 sample discontinuity는 진단 근거일 뿐 청취 품질을 대신하지 않는다.

확인할 항목:

- 짧은 첫 발화가 자연스러운가
- 뒤 청크가 멈춤 없이 이어지는가
- 단어/음절 누락·중복이 없는가
- 첫 청크와 둘째 청크의 음량 차이가 생기지 않는가
- 음색·발음·말끝이 유지되는가
- 기존 간헐적 클릭/팝이 증가하지 않는가

첫 소리의 대기를 귀로 비교하려면 제출 직후부터 녹음하거나 측정된 대기 시간을 무음으로 넣은 비교 파일을 별도로 만든다. 무음을 합성한 경우 실제 연속 녹음이 아니라는 점을 표시한다. 음질 확인용 WAV와 시작 지연 비교용 WAV를 구분한다.

## 12. 테스트

첫 청크 분할의 신규 일반화 입력을 최소 20개 검증한다. 짧은 인사, 한국어 조사, 문장부호, 긴 문장, 영어 기술 문장, 숫자+단위, 해시 설명, UUID, path/URL/code 경계를 포함한다.

분할 전후 token sequence가 같고 모든 청크가 순서대로 재생되는지 확인한다. 이는 실제 음성의 누락 없음이나 자연스러움을 보장하지 않으므로 청취 확인도 필요하다.

관련 normalization, delivery/stream/epoch, retry/long-tail, queue lifecycle, sequence-gap 및 첫 청크 테스트를 실행한다. git diff --check를 수행한다. 실제 Enikk/Codex core를 재시작하는 테스트는 금지한다.

## 13. 후보 판정

### CLEAR IMPROVEMENT

현재 baseline 대비 하나 이상의 대상 입력에서 median이 5% 이상이면서 0.10초 이상 감소하고 측정 잡음으로 설명되지 않아야 한다. 다른 입력의 median/p95가 명백히 악화되면 채택하지 않는다.

위 속도 기준과 함께 gap, 기능, 음질, 음량, 안정성 검증을 모두 통과해야 한다. 사용자 청취 확인이 필요하다.

### REGRESSION

반복되는 음질·음량 저하, 말 잘림, 누락/중복, 클릭 증가, gap 기준 초과 또는 First Audio의 명백한 악화가 있으면 후보를 복구한다.

### INCONCLUSIVE

측정 편차, 외부 재생, 출력 gain 변화, 미완료 청취 또는 로그 누락으로 결론을 낼 수 없으면 채택하지 않는다. 유리한 표본을 골라 PASS하지 않는다.

## 14. 적용과 복구

정적/회귀 검증을 통과한 후보만 TTS에 임시 적용한다.

```bash
cd /home/ak/git/codex_enikk &&
enikk_tts stop &&
enikk_tts update /home/ak/git/codex_enikk &&
enikk_tts start &&
enikk_tts status
```

start 직후의 오래된 status를 최종 상태로 판단하지 않는다. 현행 service generation의 ready/model_ready/playback_available와 last_error를 확인한다.

후보가 실패하거나 청취 대기·판정 불가 상태이면 시작 직전 production으로 복구한다. 저장된 후보 자료는 보존하되 불확실한 후보를 production에 남기지 않는다. 다음 완화 후보는 허용 횟수·시간 내에서만 진행한다.

복구는 TTS stop → 실제 보존 release rollback/select → TTS start → readiness 및 active release 확인 순서다. 실제 지원 명령을 먼저 확인하며 실패 시 core를 건드리지 않는다.

## 15. 풀반영

이번 요청은 계획서 작성이며 실행 또는 풀반영 승인이 아니다.

실험 실행 지시 후 검증을 진행하고, 사용자가 채택 후보의 청취를 확인하고 풀반영을 지시한 경우 다음을 수행한다.

1. 변경 범위 및 git diff --check 확인
2. 검증된 파일만 commit
3. main 반영; 이미 main에서 작업 중이면 별도 merge 없음
4. origin/main push 및 일치 확인
5. 최종 main 기준 TTS update/start 및 상태 확인
6. source/install parity, active release, core PID/시작 시각 확인

기존 교육, 해시/UUID 규칙, 170ms 후미 감쇠를 유지한다. 검증 실패 후보를 commit/push/deploy하지 않는다.

## 16. 최종 보고

- 시작 HEAD/release 및 복구점
- 총 작업시간, 후보 수, 중단 조건 발동 여부
- A와 각 후보의 첫 청크/나머지 청크 구조
- 입력별 raw First Audio, median/p95/max와 변화율
- 실제 측정 지점 및 미측정 구간
- 첫 청크 뒤 gap과 장문 gap 비교
- retry/long-tail/failure 및 완전 재생 여부
- 음량/peak/클릭 진단과 사용자 청취 결과
- 테스트 결과
- CLEAR IMPROVEMENT / REGRESSION / INCONCLUSIVE
- 채택·복구 여부 및 최종 서비스 상태
- 풀반영한 경우 commit, push, active release 및 parity
- Enikk/Codex core 종료·재시작 없음

## 핵심 원칙

빠르게 첫 소리만 내는 것이 아니라, 빠르게 시작하고 자연스럽게 이어지는 가장 짧은 첫 청크를 찾는다.
공격적으로 시험하되 자연스러움이 무너지면 길이를 늘린다.
현재 잘 작동하는 버전으로 언제든 돌아갈 수 있도록 보존한다.
