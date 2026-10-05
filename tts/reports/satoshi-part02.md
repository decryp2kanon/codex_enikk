# satoshi.md custom-only training — Part 2/12

## 범위와 입력 무결성

- Source: `/home/ak/satoshi.md`; Part 2는 `## 1. 사라진 개발자`를 포함하고 `## 2. 첫 번째 경고` 직전에서 끝난다.
- Source SHA-256: `6734fe26f929fcc5a7b679499a2c6efadaa434027c11dee7a692725810f6d25d` (작업 전후 동일).
- Part: 1,232 Unicode characters, 17 lines; SHA-256 `66940598e729dd2d42d755ce0578bc28a494f74416b6d134479d5e167af29336`.
- 다른 Part의 본문은 음성 입력에 포함하지 않았다.

## 작업 환경

- Feature worktree: `/home/ak/git/codex_enikk-satoshi-part02`.
- Branch: `fix/yuki-satoshi-part02-20261005`; 시작 HEAD `15b0b2d839c998006247bd002dfe79a76c792f51` (당시 최신 `main`).
- Feature implementation commit: `6b909289ec9b40679d42bd6db878b5643b617764`.
- Mode: `CODEX_ENIKK_TTS_UPSTREAM=0`, custom-only; NeMo process count 0.
- Running production worker was kept alive; no restart was performed. Playback path retained its configured 1.25x tempo.
- Existing four untracked benchmark reports in the primary checkout were left untouched.

## 발견 사항과 수정

- Reproduction: prose token `branch과` was normalized to `브랜치과`. Because the confirmed reading is `브랜치`, the coordinating particle in this exact prose context must be `와`.
- Added one narrow custom-token exception for `branch과` immediately before `switch` plus a Korean particle/punctuation boundary. It yields `브랜치와`.
- Negative cases preserve `branch과_switch`, `branch과.py`, `/tmp/branch과`, `feature/branch과`, URL and email literals. No source text, upstream module, engine, segmentation, retry, or playback logic was changed.
- Other English tokens, numbers and units in this Part were not modified: no separate reproducible text-normalization error was established for them.

## 음성 교육 / 재시도 기록

### Initial full Part read (installed pre-fix code)

- The streamed receipt text, after the normal TTS markdown cleanup, exactly matched the Part input: 23 ordered jobs, 1,219 cleaned characters.
- 36 delivery segments: 35 `PLAYED`, 1 `FAILED_EXPLICITLY`; the failed segment was the numeric-list continuation in the debug sentence.
- 55 generation attempts; 31 first-attempt accepted generations; 12 retry attempts; 17 `internal_long_tail` rejections; 4 recovery splits, 3 recovery accepts; one terminal segment failure.
- Generation duration: min 1.381 s, median 2.544 s, p95 4.097 s, max 5.545 s, mean 2.745 s. Audio duration: min 1.220 s, median 3.700 s, p95 6.580 s, max 9.580 s, mean 3.943 s.
- Inter-part `previous_gap`, excluding the first source playback: n=34, min 0.006 s, median 0.015 s, p95 5.839 s, max 18.975 s, mean 1.242 s; >0.5 s: 7, >1 s: 6, >2 s: 5, >5 s: 3. The long gaps aligned with generation/recovery delays; no timing or recovery policy was changed.

### Targeted failed-chunk retry

- The failed source sentence was submitted once more by itself. It completed on its first generation attempt and was `PLAYED` (1/1), with no retry, recovery split, waveform rejection, or final failure.
- Across the initial run plus this targeted retry, the source text has no unspoken segment. The retry was later than the subsequent sentences, so it does not replace the required ordered graduation read.

### Graduation read-through

- **Pending after install/restart.** The current resident worker had already imported the pre-fix installed normalizer; this task did not restart or hot-patch that worker. Dorothy must restart normally after the update, then perform the one ordered Part 2 graduation read with the candidate loaded and verify 0 missing/duplicate/out-of-order or failed segments. Do not use this report as evidence that candidate code has passed that final audio gate.

## Tests and performance

- `test_text_normalization` + `test_tts_delivery`: 95 tests passed after the final candidate change.
- Targeted branch-reading and identifier/path/URL/email boundary tests: 2 passed (also included in the 95-test run).
- `git diff --check`: passed.
- Paired warm CPU normalization microbenchmark on the Part text, 12 ABBA/BAAB measurements per variant with 500 calls each: baseline median 0.29916 s; candidate median 0.27640 s; candidate was 7.608% faster. This is a local microbenchmark, not end-to-end TTS latency.
- Compared with the initial audio, the targeted retry changed that one failed segment from four long-tail rejections/one terminal failure to one accepted generation/one playback. A complete after-change graduation distribution is pending and is not estimated.

## 반영과 남은 확인

- Code/test changes are limited to `tts/yuki-text-normalization-overrides.py` and `tests/test_text_normalization.py`.
- Implementation commit: `6b909289ec9b40679d42bd6db878b5643b617764`; branch report commit merged with it: `53e66c602d29b929d5c5e9f399f0e8165e36df47`.
- Main fast-forward and `origin/main` push succeeded at `53e66c602d29b929d5c5e9f399f0e8165e36df47`.
- `PREFIX=/home/ak/.local CODEX_ENIKK_INSTALL_TTS=0 bash ./update.sh`: exit 0. Source/install SHA-256 matched for overrides (`0aac81ba2b0c47e27efad080020997fae7af7eef8f41a96e768fec55886fc72a`), normalization wrapper (`e4c8eb944a32261a242d51db6fb87285e519aed02199de6419b214eba0dbc835`), upstream orchestrator (`0072de5b23cfe2cdd01880479402df8fe13e0edf48002cac3833e4cfcd782844`), selected dictionary (`a6be2d6e1a36dda51ba7648528484dbf9c9534b2646589693e1dd019a72932fb`), and Chatterbox engine (`53fc54cac8d8f20fe7a1bd84656ada4e76d4acc1c618efa624723e3bcf4f053e`).
- The pre-existing production worker PID `3304971` remained alive on run `run-_icdknfr`; its environment still showed `CODEX_ENIKK_TTS_UPSTREAM=0`. NeMo process count was 0. The worker was not restarted and therefore has not loaded the updated module in memory.
- Status: `PARTIAL_PASS_RESTART_GRADUATION_PENDING`; `RESTART_REQUIRED=true`. Dorothy should restart normally, verify ready/UPSTREAM=0/NeMo=0, perform the one ordered graduation read using the installed candidate, verify 0 failed/missing/duplicate/out-of-order segments, and only then create `part02-production-verified`. No later Part may start before that marker exists.
- Rollback: use a normal `git revert` of the implementation commit if the post-restart graduation reveals an unwanted transformation; no runtime or model setting changed.
- Four primary-checkout benchmark reports remain untouched.
