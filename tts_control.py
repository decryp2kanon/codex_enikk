#!/usr/bin/env python3
"""Control only the independently supervised voice service."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys

UNIT = 'enikk-tts.service'

def main():
    os.environ.setdefault('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid()))
    os.environ.setdefault('DBUS_SESSION_BUS_ADDRESS', 'unix:path=' + os.environ['XDG_RUNTIME_DIR'] + '/bus')
    command = sys.argv[1] if len(sys.argv) > 1 else 'status'
    if command in ('update', 'rollback'):
        from tts_release import main as release
        return release(sys.argv[1:])
    if command not in ('start', 'stop', 'restart', 'status'):
        print('enikk_tts start|stop|restart|status|update SOURCE|rollback RELEASE')
        return 2
    if command == 'status':
        state = Path(os.environ.get('ENIKK_TTS_STATE',
            str(Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'enikk_tts')))
        result = subprocess.run(['systemctl', '--user', 'show', UNIT,
            '--property=ActiveState,SubState,MainPID'], capture_output=True, text=True)
        print(result.stdout.strip())
        try:
            value = json.loads((state / 'status.json').read_text())
            active = 'ActiveState=active' in result.stdout
            if not active or 'MainPID=' + str(value.get('pid')) + '\n' not in result.stdout + '\n':
                value.update(state='stopped', model_ready=False, playback_available=False)
            print(json.dumps(value, ensure_ascii=False, indent=2))
        except FileNotFoundError:
            print('voice service has not run')
        return result.returncode
    root = Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid())))
    with (root / 'enikk-tts-control.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return subprocess.run(['systemctl', '--user', command, UNIT]).returncode

if __name__ == '__main__':
    sys.exit(main())
