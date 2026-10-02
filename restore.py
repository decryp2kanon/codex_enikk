#!/usr/bin/env python3
import sys
import tarfile
import sqlite3
from enikk import restore

if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] in ('-h', '--help'):
        print('사용법: codex_enikk_restore BACKUP.tar.gz\nCodex 종료 후 실행하세요. SQLite 백업은 빈 CODEX_HOME에 복구합니다. 기존 DB 덮어쓰기/병합은 지원하지 않습니다. Legacy JSONL 백업은 누락된 파일만 복구합니다.')
        sys.exit(0 if len(sys.argv) == 2 else 2)
    try:
        restore(sys.argv[1])
    except (OSError, ValueError, tarfile.TarError, sqlite3.Error, EOFError) as exc:
        print(f'복구 실패: {exc}', file=sys.stderr)
        sys.exit(1)
