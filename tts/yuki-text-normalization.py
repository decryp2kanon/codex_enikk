#!/usr/bin/env python3
"""Persistent CPU NeMo Korean TN; never imports or changes the GPU environment."""
import atexit
import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import threading
import time

# User-defined names, not a general pronunciation dictionary.
NAMES = {'Yuki': '유키', 'Enikk': '에닉', 'Sugarchain': '슈가체인'}


def proper_names(text):
    return re.sub(r'(?<![A-Za-z])(?:Yuki|Enikk|Sugarchain)(?![A-Za-z])',
                  lambda m: NAMES[m.group()], text, flags=0)


# Reproduced NeMo errors and USER-confirmed unit readings. Case matters: GB != Gb.
# Other numeric/SI rules, ordinary Korean and mathematical operators stay upstream.
GROUPED_INTEGER = re.compile(r'(?<![A-Za-z0-9_.,])[1-9]\d{0,2}(?:,\d{3})+(?!\d|,\d)')
KNOWN_UNITS = {'GB': '기가바이트', 'MB': '메가바이트', 'TB': '테라바이트',
               'kHz': '킬로헤르츠', 'kbps': '킬로비트 퍼 초', 'km/h': '킬로미터 퍼 아워'}
NUMBER_UNIT = re.compile(r'(?<![A-Za-z0-9_.,+-])(?P<number>-?\d+(?:\.\d+)?)'
                        r'(?P<unit>GB|MB|TB|kHz|kbps|km/h)(?![A-Za-z0-9_])')
# Relative filename tokens and the known digit-bearing extension remain identifiers.
# Absolute filesystem paths have already gone through the separate path-description layer.
KNOWN_PROTECTED = re.compile(
    r'(?<![\w])일반(?![\w])'
    r'|(?<![\w/])(?=[A-Za-z0-9_.-]*\d)[A-Za-z0-9][A-Za-z0-9_.-]*\.(?:py|md|sh|json|txt|wav|mp3|log|toml|yaml|yml|cpp|rs|js|ts)(?![A-Za-z0-9_.])'
    r'|(?<![\w.])\.mp3(?![A-Za-z0-9_])')


# Explicit USER listening failures only; not a general English or letter dictionary.
HEARD_ERRORS = {'Python': '파이썬', 'CPU': '씨피유', 'TTS': '티티에스',
                'API': '에이피아이', 'GPU': '지피유', 'VRAM': '브이램',
                'km/h': '킬로미터 퍼 아워'}
HEARD_TOKEN = re.compile(r'(?<![A-Za-z0-9_./@-])(?:Python|CPU|TTS|API|GPU|VRAM|km/h)'
                         r'(?![A-Za-z0-9_/@-]|\.[A-Za-z0-9_])')


def heard_error_readings(text):
    def replace(match):
        # Do not reinterpret tokens inside URL/email literals as prose words.
        left = re.search(r'\S*$', text[:match.start()]).group()
        right = re.match(r'\S*', text[match.end():]).group()
        token = left + match.group() + right
        if '://' in token or '@' in token:
            return match.group()
        return HEARD_ERRORS[match.group()]
    return HEARD_TOKEN.sub(replace, text)


def normalize_with_exceptions(text, normalizer):
    """Protect reproduced errors, run public TN, restore only our own exact spans.

    Each transformed span is normalized once. Opaque markers never reach the GPU.
    The private-use markers are chosen outside the input and checked for loss or
    duplication rather than repairing arbitrary words in the final output.
    """
    if not text.strip():
        return text
    text = proper_names(text)
    protected = {}
    available = (chr(i) for i in range(0xE000, 0xF900) if chr(i) not in text)

    def protect(value):
        token = next(available, None)
        if token is None:
            raise ValueError('too many protected normalization spans')
        protected[token] = value
        return token

    text = KNOWN_PROTECTED.sub(lambda match: protect(match.group()), text)
    # Strip commas only from syntactically valid thousands groups, not prose commas.
    text = GROUPED_INTEGER.sub(lambda match: match.group().replace(',', ''), text)

    def unit(match):
        number = normalizer.normalize(match.group('number'))
        if not number.strip():
            raise RuntimeError('empty normalized number')
        return protect(number + ' ' + KNOWN_UNITS[match.group('unit')])

    text = NUMBER_UNIT.sub(unit, text)
    text = heard_error_readings(text)
    result = normalizer.normalize(text)
    for token, value in protected.items():
        if result.count(token) != 1:
            raise RuntimeError('protected normalization span lost or duplicated')
        result = result.replace(token, value)
    return result


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
            self.process = subprocess.Popen([str(python), str(Path(__file__).resolve()), '--serve'],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, close_fds=True, bufsize=0)
            os.set_blocking(self.process.stdin.fileno(), False)
            try:
                if self._receive(15).get('ready') is not True:
                    raise RuntimeError('invalid NeMo readiness')
            except BaseException:
                self.close()
                raise

    def normalize(self, text):
        self.initialize()
        if len(text.encode('utf-8')) > 1024 * 1024:
            raise ValueError('normalization request too large')
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
                    # Never force-kill or silently start a replacement process.
                    self.process = process
            if process.stdout and process.poll() is not None:
                process.stdout.close()


_client = Client()
initialize = _client.initialize
normalize = _client.normalize


def serve():
    from nemo_text_processing.text_normalization.normalize import Normalizer
    home = Path(os.environ.get('CODEX_ENIKK_TN_HOME', Path.home() / 'Apps/enikk-nemo-tn'))
    cache = home / 'cache'
    normalizer = Normalizer(input_case='cased', lang='ko', cache_dir=str(cache), overwrite_cache=False)
    print(json.dumps({'ready': True}), flush=True)
    for line in sys.stdin:
        try:
            text = json.loads(line)['text']
            # Public NeMo TN with bounded, reproduced-error protection; no Korean G2P.
            result = normalize_with_exceptions(text, normalizer)
            print(json.dumps({'text': result}, ensure_ascii=False), flush=True)
        except Exception as error:
            print(json.dumps({'error': type(error).__name__ + ': ' + str(error)}), flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--serve']:
        serve()
    else:
        initialize()
        _client.close()
