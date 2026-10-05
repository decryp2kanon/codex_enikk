# satoshi.md 교육 중간 종료 / Full Apply 보고서 — 2026-10-06

## 종료 범위

- 사용자의 지시에 따라 satoshi.md 12파트 교육은 **여기서 중단**했다.
- Part 4 진행 중 turn은 중단되어 `FAILED_EXPLICITLY` 상태다.
- Part 5~12 queued task는 모두 `CANCELLED` 처리했다.
- 이후 Part는 자동으로 진행되지 않는다.

## 현재 반영 상태

- Runtime code revision used for the final production restart: `a22c39016a9e1f818a43e3a5a0e9e8f77d7b10d8`
- `main == origin/main` at restart time.
- Production update command completed successfully:
  `PREFIX=/home/ak/.local CODEX_ENIKK_INSTALL_TTS=0 bash update.sh`
- Rollback snapshot: `/home/ak/.local/lib/codex_enikk/previous-FNCsf4Eg`

## Production restart verification

- Previous wrapper PID: `3608480`
- New wrapper PID: `3624520`
- New TTS run: `run-0wb080f4`
- Ready event: `tts_mode=streaming reason=ready monotonic_ns=584202562697426`
- `CODEX_ENIKK_TTS_UPSTREAM=0`: confirmed.
- NeMo/nemo_adapter/enikk-nemo-tn standalone process: 0 actual processes observed.
- New wrapper owns Codex app-server, streaming TTS helper and trigger service children normally.

## Source / production parity

The following source and installed production files matched byte-for-byte at final verification:

- `trigger_service.py`
  - SHA-256 `45b12c6da44797dcaac65d016917bd49a311bfe63db9ba44d795b3a4d860b9bc`
- `satoshi_training_supervisor.py`
  - SHA-256 `40d8836708d726f9457916d682741048a2185e825f59564d2a575cbcd6099535`
- `tts/yuki-text-normalization-overrides.py`
  - SHA-256 `0aac81ba2b0c47e27efad080020997fae7af7eef8f41a96e768fec55886fc72a`

## 교육 결과 보존

- Part 2에서 반영된 `branch과` 문맥 교정은 production custom normalization에 포함되어 있다.
- Part 2/3의 기존 production-verified marker는 이후 더 엄격한 졸업 기준을 적용하기 위해
  `*.superseded-old-gate`로 보존했다.
- 숫자/단위 낭독은 아직 100% 졸업 기준을 충족하지 못한 것으로 판단했다.
- 따라서 Part 2/3을 최종 교육 완료로 간주하지 않고, 다음 재개 시 숫자/단위/기술어/문맥까지 검증하는 새 졸업 기준으로 다시 진행해야 한다.

## Queue 종료 상태

- Part 3 task: `COMPLETED` 기록 보존
- Part 4 task: `FAILED_EXPLICITLY` 기록 보존
- Part 5~12 task: 모두 `CANCELLED`
- 활성 satoshi 교육 supervisor systemd unit: 없음

## 기존 파일 보존

Primary checkout의 기존 untracked benchmark 보고서 4개는 삭제하거나 commit하지 않았다.

- `tts/benchmark-haruhi-fixed-upstream0-custom-20261005.md`
- `tts/benchmark-haruhi-upstream0-custom-20261005.md`
- `tts/benchmark-tech300-upstream0-custom-20261005.md`
- `tts/benchmark-upstream0-custom-20261005.md`

## 종료 상태

**FULL APPLY COMPLETE / TRAINING PAUSED**

현재 production은 위 runtime code가 반영된 상태로 실행 중이며, satoshi 교육 자동 진행은 중단되어 있다.
