#!/usr/bin/env python3
import sys
import tarfile
from enikk import restore

if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] in ('-h', '--help'):
        print('사용법: codex_enikk_restore BACKUP.tar.gz\n기존 파일을 덮어쓰지 않고 누락된 세션만 복구합니다. Codex 종료 후 실행하세요.')
        sys.exit(0 if len(sys.argv) == 2 else 2)
    try:
        restore(sys.argv[1])
    except (OSError, ValueError, tarfile.TarError) as exc:
        print(f'복구 실패: {exc}', file=sys.stderr)
        sys.exit(1)
