"""Core-owned app-server lifecycle. No voice runtime dependencies."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

@contextmanager
def app_server():
    executable = 'codex'
    environment = os.environ.copy()
    guard_manifest = Path(__file__).resolve().parent / 'voice-guard.json'
    if guard_manifest.exists():
        manifest = json.loads(guard_manifest.read_text(encoding='utf-8'))
        binary = Path(__file__).resolve().parent / 'bin' / 'codex-voice-guard'
        if binary.is_symlink() or not binary.is_file():
            raise RuntimeError('Voice guard binary missing; existing thread preserved')
        checksum = hashlib.sha256()
        with binary.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                checksum.update(chunk)
        digest = checksum.hexdigest()
        if digest != manifest['sha256']:
            raise RuntimeError('Voice guard binary changed; existing thread preserved')
        executable = str(binary)
        environment['CODEX_ENIKK_DISABLE_REALTIME'] = '1'
    with tempfile.TemporaryDirectory(prefix='enikk-core-') as directory:
        root = Path(directory)
        endpoint = root / 'server.sock'
        with (root / 'server.log').open('wb') as log:
            process = subprocess.Popen([executable, '-c', 'approval_policy="never"',
                '-c', 'sandbox_mode="danger-full-access"', '-c', 'notify=[]',
                'app-server', '--listen', 'unix://' + str(endpoint)],
                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                close_fds=True, start_new_session=True, env=environment)
            try:
                deadline = time.monotonic() + 30
                while not endpoint.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(.05)
                if process.poll() is not None or not endpoint.exists():
                    raise RuntimeError('Core app-server unavailable; existing thread preserved')
                yield 'unix://' + str(endpoint)
            finally:
                if process.poll() is None:
                    process.terminate()
                    try: process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
