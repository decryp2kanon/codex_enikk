작성자: 에닉(유키짱)

# TTS 교육 전·후·현재 production A/B/C 벤치마크 — 2026-10-06

## 목적과 범위

A/B 비교 보고서에 사용된 기술 문서의 동일한 production TTS benchmark를 다시 수행해 C를 기록했다. benchmark만 수행했으며 코드, 설치본, 설정, branch, commit은 변경하지 않았다. 본문을 별도 재생성·수정하지 않고 입력 파일의 실제 production 전처리와 문장 경계 처리 후 순서대로 제출했다. 전처리된 전체 텍스트는 9,380자이며, 입력 구간 178개가 TTS에 한 번씩 전달됐다.

## 입력과 실행 조건

- 입력: `/home/ak/tts-text-for-bench.md`
- 원본: 9,393자, 175개 줄, SHA-256 `14825803bf1de37162d2c3544151cf99c6ac12d1da13408a4697f353637ee8dd` — 명령서에 적힌 SHA와 일치
- 내용 범위: Bitcoin·Git/GitHub·Linux 기술 용어 각 100개, 총 300개 용어를 포함한 파일 전체
- Core commit: `a26223203bc12851e60d8c834965069f8d47e38c`; `main`과 `origin/main` 동일
- 현재 production 선택 release: `a492cdc27ea17847`; benchmark를 처리한 상주 service/engine은 시작 당시 실행 중이던 `b37bd7a1ad4e1f59` 경로
- 두 release의 Chatterbox engine SHA-256은 동일(`4784bf5fd6ea57da05b65a23490773761aafd6c887845eae99daca4a9ae5df9a`), normalization override SHA-256도 동일(`c5c064283888e1a1fc161bafec4cfe17a1a0498b962196e906281aa7d4aa13cb`). 선택 release와 실행 중 release의 `tts_control.py`만 달랐다.
- TTS service PID `3825938`, generation `65a64a83c6cd40d5a186d6fc127d9756`; engine PID `3910666`, run `b6ac5bee38dd44b58e3f6adcf1886d24`
- Model path: Chatterbox C2. Reference: `/home/ak/Apps/chatterbox-yuki/yuki_super-clean.wav`. Playback: 1.25× tempo.
- GPU: NVIDIA GeForce GTX 1080
- benchmark 제출 시작: 2026-10-06 16:02:33.672 KST (monotonic `610007.769256` s)
- 첫 benchmark playback: 16:02:36.959 KST (monotonic `610010.959075` s)
- 마지막 benchmark playback 완료: 16:19:53 KST, monotonic `611047.689521` s
- 제출 시작부터 마지막 완료까지: 1,039.920 s. 첫 playback부터 마지막 완료까지: 1,036.730 s.
- 원문 전체를 정상 순서로 처리했다. 제출 구간 178개가 전처리 후 전체 9,380자를 끊김·중복 없이 덮었고, playback 순서 역전은 없었다. 코드/설정 update, TTS service 재시작, Core/Enikk 재시작은 없었다.

## A/B/C 결과

A와 B 수치는 기존 `benchmark-education-ab-20261006.md`에서 가져왔다. 해당 보고서의 generation·RTF 집계 세부 정의가 기록돼 있지 않아, C의 생성 비용 지표는 측정 방식을 함께 표시했다. Chatterbox는 확률적이므로 단일 실행 차이를 교육 변경의 인과 효과로 단정할 수 없다.

| 지표 | A: 교육 전 | B: 교육 후 | C: 현재 production | C−A | C−B |
|---|---:|---:|---:|---:|---:|
| 완료 output parts | 306 | 306 | 280 | −26 (−8.50%) | −26 (−8.50%) |
| PLAYED output parts | 299 | 304 | 271 | −28 | −33 |
| FAILED_EXPLICITLY output parts | 7 | 2 | 9 | +2 (+28.6%) | +7 (+350%) |
| 성공률 | 97.71% | 99.35% | 96.79% (271/280) | −0.93%p | −2.56%p |
| Retry / 추가 생성 시도 | 70 | 65 | 88 | +18 (+25.7%) | +23 (+35.4%) |
| internal_long_tail 거부 | 96 | 77 | 119 | +23 (+24.0%) | +42 (+54.5%) |
| Recovery split | 19 | 10 | 22 | +3 (+15.8%) | +12 (+120%) |
| Recovery accepted | 12 | 8 | 13 | +1 (+8.3%) | +5 (+62.5%) |
| Generation median | 2.517 s | 2.545 s | 2.528 s/output part* | +0.011 s | −0.017 s |
| RTF median | 0.739 | 0.749 | 0.754/output part* | +0.015 | +0.005 |
| Gap median | 0.011 s | 0.008 s | 0.009 s | −15.4% | +16.4% |
| Gap p95 | 4.124 s | 2.771 s | 6.832 s | +65.7% | +146.6% |
| Gap max | 15.031 s | 9.005 s | 12.234 s | −18.6% | +35.8% |
| Gap mean | 0.568 s | 0.401 s | 0.926 s | +63.0% | +131.0% |
| >5 s gap | 12 | 6 | 19 | +7 | +13 |
| First playback → last completion | 1,019.038 s | 987.745 s | 1,036.730 s | +1.74% | +4.96% |

\* C generation median은 재생된 output part별로 해당 part에 든 모든 generation 시도(재시도·recovery 포함)를 합산했다. C RTF도 이 총 생성 비용을 playback audio duration으로 나눴다. A/B 보고서는 이 집계법을 밝히지 않아 generation/RTF 행은 참고 비교이며 완전히 동일한 집계라고 보장할 수 없다.

## C 상세 지표

| 항목 | C 측정값 |
|---|---:|
| 제출한 source 구간 / terminal receipt | 178 / 178 |
| source job 결과 | 169 PLAYED, 9 FAILED_EXPLICITLY |
| output parts 결과 | 271 PLAYED, 9 FAILED_EXPLICITLY, 총 280 |
| 성공률 | 271/280 = 96.79%; source job 기준 169/178 = 94.94% |
| Missing / duplicate / out-of-order | 0 / 0 / 0 |
| Generation attempts | 404회: 첫 시도 316, 추가 시도 88 |
| 첫 시도에서 정상 생성 | 228 output part |
| Generation attempt duration | min 1.304 s, median 2.441 s, p95 3.425 s, max 4.016 s, mean 2.515 s |
| 재생된 output part별 총 생성 비용 | median 2.528 s, p95 7.273 s, max 14.605 s, mean 3.413 s |
| 재생된 output part별 비용 RTF | median 0.754, p95 2.180, max 5.224, mean 0.999 |
| 생성 시도에서 성공으로 끝난 generate_end | 285회 |
| internal_long_tail 거부 | 119회 |
| Recovery split / accepted | 22 / 13 |
| Waveform rejection / OOM / exception | 0 / 0 / 0 |
| 재생된 audio duration 합계 | 934.660 s |
| 성공한 생성 시도들의 후보 audio 합계 | 984.080 s (일부는 최종 delivery로 재생되지 않음) |
| 1.25× 청취 예상 시간 | 747.728 s |
| First-to-last wall time − 1.25× 청취 예상 시간 | 289.002 s |
| Inter-chunk gap 수 | 270 |
| Gap min / median / mean / p95 / max | 0.005 / 0.009 / 0.926 / 6.832 / 12.234 s |
| Gap >0.5 / >1 / >2 / >5 s | 61 / 50 / 39 / 19 |

## 해석과 integrity

C는 178개 source 구간과 280개 최종 output part를 모두 receipt로 정산했다. source 범위는 전처리된 본문 전체를 연속으로 덮었고, 재생 순서 역전·중복·누락은 없었다. 9개 output part는 `FAILED_EXPLICITLY`였고, 119회의 `internal_long_tail` 거부와 22회의 recovery split이 기록됐다. 이 benchmark에서는 실패 항목을 재제출하지 않았다.

성공률은 A와 B보다 낮았고, B 대비 gap p95와 retry·long-tail 거부가 증가했다. output part 수가 306에서 280으로 달라졌으므로 분모 변화와 모델의 stochastic variation을 고려해야 한다. 이 결과만으로 교육 전후 코드가 성능 저하의 원인이라고 결론낼 수는 없다. C 결과는 재생/재시도 변동을 포함한 현재 production의 단일 측정값이다.

Benchmark 전후 Core git은 `a26223203bc12851e60d8c834965069f8d47e38c`였고, benchmark 중 코드·production 설정 변경이나 restart는 수행하지 않았다. Resident TTS service/engine PID 및 service generation도 benchmark 도중 유지됐다. A/B 보고서가 있던 시점의 TTS digest/config snapshot은 없어 과거 시점과의 byte-for-byte 변경 여부는 증명할 수 없다. 이번 측정에서 확인된 running/selected release 간 차이와 동일한 engine·normalizer hash는 위 조건에 기록했다.

## 결론

현재 production C는 280 output parts 중 271개 재생, 9개 최종 실패였다(96.79%). A/B 기록보다 성공률은 낮고 gap p95와 long-tail 거부는 높았다. benchmark만 수행했으며 자동 수정·재시도·rollback은 하지 않았다.

EOF
