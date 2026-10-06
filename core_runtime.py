"""Core-owned app-server lifecycle. No voice runtime dependencies."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time

@contextmanager
def app_server():
    with tempfile.TemporaryDirectory(prefix='enikk-core-') as directory:
        root = Path(directory)
        endpoint = root / 'server.sock'
        with (root / 'server.log').open('wb') as log:
            process = subprocess.Popen(['codex', '-c', 'approval_policy="never"',
                '-c', 'sandbox_mode="danger-full-access"', '-c', 'notify=[]',
                'app-server', '--listen', 'unix://' + str(endpoint)],
                stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                close_fds=True, start_new_session=True)
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
