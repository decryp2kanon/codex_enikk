#!/usr/bin/env python3
"""Save an already running conversation without restarting its Codex TUI."""
import argparse
from pathlib import Path
import signal
import threading

import enikk


def main():
    parser = argparse.ArgumentParser(description='진행 중인 대화를 10MB TXT 파일로 실시간 저장')
    parser.add_argument('--session', required=True, help='저장할 기존 세션 ID')
    parser.add_argument('--output', type=Path, default=enikk.transcript_dir())
    parser.add_argument('--once', action='store_true', help='한 번 저장하고 종료')
    args = parser.parse_args()
    if not any(meta.get('id') == args.session for _, meta in enikk.session_metadata()):
        parser.error('해당 세션을 찾지 못했습니다.')
    stopped = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())
    baseline = {}
    output = enikk.validate_storage_dir(args.output)
    enikk.export_changed(baseline, Path.cwd(), output, args.session)
    print(f'TXT 실시간 저장: {output} (파일당 최대 10,000,000바이트)', flush=True)
    if not args.once:
        while not stopped.wait(2):
            enikk.export_changed(baseline, Path.cwd(), output, args.session)
        enikk.export_changed(baseline, Path.cwd(), output, args.session)


if __name__ == '__main__':
    main()
