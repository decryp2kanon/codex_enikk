#!/usr/bin/env python3
"""Optional persistent CPU NeMo TN source adapter; safe to remove when disabled."""
import atexit
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import threading
import time


class Client:
    def __init__(self):
        self.process = None
        self.lock = threading.Lock()
        self.buffer = b''
        atexit.register(self.close)

    def _receive(self, timeout):
        deadline = time.monotonic() + timeout
        while b'\n' not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.process.stdout], [], [], remaining)[0]:
                raise TimeoutError('NeMo CPU normalization timed out')
            data = os.read(self.process.stdout.fileno(), 65536)
            if not data:
                raise RuntimeError('NeMo CPU normalizer exited')
            self.buffer += data
            if len(self.buffer) > 8 * 1024 * 1024:
                raise RuntimeError('NeMo response exceeds limit')
        line, self.buffer = self.buffer.split(b'\n', 1)
        response = json.loads(line)
        if 'error' in response:
            raise RuntimeError(response['error'])
        return response

    def initialize(self):
        with self.lock:
            if self.process is not None:
                if self.process.poll() is not None:
                    raise RuntimeError('NeMo normalizer died; no legacy fallback')
                return
            home = Path(os.environ.get('CODEX_ENIKK_TN_HOME', Path.home() / 'Apps/enikk-nemo-tn'))
            python = home / '.venv/bin/python'
            if not python.is_file():
                raise RuntimeError('NeMo CPU environment missing; run tts/setup-nemo-tn.sh')
            self.process = subprocess.Popen(
                [str(python), str(Path(__file__).resolve()), '--serve'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                close_fds=True, bufsize=0)
            os.set_blocking(self.process.stdin.fileno(), False)
            try:
                if self._receive(15).get('ready') is not True:
                    raise RuntimeError('invalid NeMo readiness')
            except BaseException:
                self.close()
                raise

    def normalize(self, text):
        self.initialize()
        with self.lock:
            try:
                payload = (json.dumps({'text': text}, ensure_ascii=False) + '\n').encode()
                deadline = time.monotonic() + 5
                while payload:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not select.select([], [self.process.stdin], [], remaining)[1]:
                        raise TimeoutError('NeMo request write timed out')
                    try:
                        payload = payload[os.write(self.process.stdin.fileno(), payload):]
                    except BlockingIOError:
                        continue
                result = self._receive(5)['text']
                if text.strip() and not result.strip():
                    raise RuntimeError('normalization returned empty text')
                return result
            except BaseException:
                self.close()
                raise

    def close(self):
        process, self.process = self.process, None
        self.buffer = b''
        if process is not None:
            if process.stdin:
                process.stdin.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    self.process = process
            if process.stdout and process.poll() is not None:
                process.stdout.close()


_client = Client()
initialize = _client.initialize
normalize = _client.normalize
close = _client.close


def serve():
    # NeMo is imported only in this enabled, isolated CPU child process.
    from nemo_text_processing.text_normalization.normalize import Normalizer
    home = Path(os.environ.get('CODEX_ENIKK_TN_HOME', Path.home() / 'Apps/enikk-nemo-tn'))
    normalizer = Normalizer(input_case='cased', lang='ko',
                            cache_dir=str(home / 'cache'), overwrite_cache=False)
    print(json.dumps({'ready': True}), flush=True)
    for line in sys.stdin:
        try:
            text = json.loads(line)['text']
            print(json.dumps({'text': normalizer.normalize(text)}, ensure_ascii=False), flush=True)
        except Exception as error:
            print(json.dumps({'error': type(error).__name__ + ': ' + str(error)}), flush=True)


if __name__ == '__main__' and sys.argv[1:] == ['--serve']:
    serve()
