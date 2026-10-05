"""Minimal local trigger client. Authority/source/body are not accepted inputs."""
import argparse
import json
import os
from pathlib import Path
import socket
import stat
import sys

from trigger_transport import peer_uid

EXIT = {'ACCEPTED': 0, 'BUSY': 2, 'DUPLICATE': 3, 'INVALID_EOF': 4,
        'QUEUED': 0, 'QUEUE_FULL': 2, 'CANCELLED': 0, 'NOT_FOUND': 9, 'NO_RUNNING_ENIKK': 5, 'INVALID_PATH': 6, 'SECURITY_ERROR': 7, 'UNKNOWN_EFFECT': 8}


def submit(endpoint, fixture=False, cancel=None):
    sock = socket.socket(socket.AF_UNIX); sock.settimeout(20)
    sent = False
    try:
        st = endpoint.lstat()
        parent = endpoint.parent.lstat()
        if (not stat.S_ISSOCK(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077 or
                not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.getuid() or parent.st_mode & 0o077):
            return {'status': 'SECURITY_ERROR'}
        sock.connect(str(endpoint))
        if peer_uid(sock) != os.getuid(): return {'status': 'SECURITY_ERROR'}
        sent = True  # a failed send may still have had an effect
        request = {'action': 'cancel', 'task_id': cancel} if cancel is not None else {'action': 'fixture' if fixture else 'trigger'}
        sock.sendall(json.dumps(request).encode() + b'\n')
        raw = bytearray()
        while not raw.endswith(b'\n'):
            part = sock.recv(1)
            if not part or len(raw) > 4096: return {'status': 'UNKNOWN_EFFECT'}
            raw.extend(part)
        value = json.loads(raw)
        if not isinstance(value, dict) or value.get('status') not in EXIT: return {'status': 'UNKNOWN_EFFECT'}
        return value
    except (FileNotFoundError, ConnectionRefusedError):
        return {'status': 'UNKNOWN_EFFECT' if sent else 'NO_RUNNING_ENIKK'}
    except (OSError, ValueError):
        return {'status': 'UNKNOWN_EFFECT' if sent else 'SECURITY_ERROR'}
    finally:
        sock.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path', nargs='?')
    parser.add_argument('--fixture', action='store_true', help='only the built-in harmless status command; never reads the real inbox')
    parser.add_argument('--cancel', metavar='TASK_ID', help='cancel a queued command; never interrupts active work')
    args = parser.parse_args(argv)
    trusted = Path.home() / 'dorothy-command.md'
    if (args.cancel and (args.path or args.fixture)) or (args.path is not None and (args.fixture or args.path != str(trusted))):
        result = {'status': 'INVALID_PATH'}
    else:
        result = submit(Path.home() / '.local/state/codex_enikk/trigger/trigger.sock', args.fixture, cancel=args.cancel) if args.cancel else submit(Path.home() / '.local/state/codex_enikk/trigger/trigger.sock', args.fixture)
    print(json.dumps(result, ensure_ascii=False))
    return EXIT[result['status']]


if __name__ == '__main__': sys.exit(main())
