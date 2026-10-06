"""Read-only PulseAudio observations of TTS-owned playback streams.

No service, device routing, volume or synthesis settings are changed. A monitor
attached after stream creation gives an observed upper bound, not physical
speaker onset. Silence, connection errors and unrelated streams stay distinct.
"""
import array
import json
import os
import select
import subprocess
import threading
import time


def descendant(pid, owner, read=None):
    """Only monitor paplay descendants of the requested TTS service."""
    if read is None:
        def read(value):
            with open('/proc/' + str(value) + '/stat') as stream:
                return int(stream.read().rsplit(')', 1)[1].split()[1])
    for _ in range(32):
        if pid == owner:
            return True
        if pid <= 1:
            return False
        try:
            pid = read(pid)
        except (OSError, ValueError, IndexError):
            return False
    return False


def signal_block(data, rate=48000, channels=2, threshold=.001, end=None):
    """Use both channels; keep partial frames in the caller, never discard."""
    samples = array.array('f')
    samples.frombytes(data)
    hits = [i // channels for i, value in enumerate(samples) if abs(value) > threshold]
    if not hits:
        return None, max(map(abs, samples), default=0)
    frames = len(samples) // channels
    end = time.monotonic() if end is None else end
    return end - (frames - hits[0]) / rate, max(map(abs, samples))


class Recorder:
    def __init__(self, server, sink, stream):
        self.stream = stream
        self.sink = sink
        self.started = time.monotonic()
        self.ready = threading.Event()
        self.stop = threading.Event()
        self.blocks = 0
        self.bytes = 0
        self.first_signal = None
        self.peak = 0
        self.reader_error = None
        self.requested_latency_ms = 20
        self.process = subprocess.Popen([
            'parec', '--server=' + server, '--device=' + sink['monitor_source'],
            '--monitor-stream=' + str(stream['index']), '--raw',
            '--format=float32le', '--rate=48000', '--channels=2',
            '--latency-msec=20', '--process-time-msec=10',
            '--client-name=Enikk read-only benchmark'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.thread = threading.Thread(target=self.receive, daemon=True)
        self.thread.start()

    def receive(self):
        pending = b''
        try:
            while not self.stop.is_set():
                if not select.select([self.process.stdout], [], [], .1)[0]:
                    if self.process.poll() is not None:
                        break
                    continue
                data = os.read(self.process.stdout.fileno(), 4096)
                if not data:
                    break
                pending += data
                complete = len(pending) // 8 * 8
                if not complete:
                    continue
                block, pending = pending[:complete], pending[complete:]
                self.blocks += 1
                self.bytes += len(block)
                onset, peak = signal_block(block)
                self.peak = max(self.peak, peak)
                if onset is not None and self.first_signal is None:
                    self.first_signal = onset
                self.ready.set()
        except Exception as exc:
            self.reader_error = type(exc).__name__ + ': ' + str(exc)

    def close(self):
        natural_exit = self.process.poll()
        self.stop.set()
        if natural_exit is None:
            # This is our own capture child, never an Enikk/Codex process.
            self.process.terminate()
        self.thread.join(timeout=1)
        self.process.wait(timeout=3)
        self.stderr = self.process.stderr.read().decode(errors='replace')
        self.natural_exit = natural_exit

    def result(self):
        return {'stream_index': self.stream['index'], 'stream_pid': self.stream['properties']['application.process.id'],
                'sink_index': self.sink['index'], 'sink_name': self.sink['name'],
                'monitor_source': self.sink['monitor_source'], 'attach_requested': self.started,
                'connected': self.ready.is_set(), 'blocks': self.blocks, 'bytes': self.bytes,
                'first_observed_signal': self.first_signal, 'peak': self.peak,
                'reader_error': self.reader_error, 'capture_stderr': getattr(self, 'stderr', ''),
                'natural_capture_exit': getattr(self, 'natural_exit', None),
                'requested_capture_latency_ms': self.requested_latency_ms,
                'playback_buffer_latency_usec': self.stream.get('buffer_latency_usec'),
                'sink_latency_usec': self.stream.get('sink_latency_usec'),
                'measurement': 'TTS-owned sink-input signal observed after monitor attachment; upper-bound estimate, physical onset unmeasured'}


class PlaybackObserver:
    def __init__(self, owner_pid, server=None):
        self.owner_pid = owner_pid
        self.server = server or 'unix:/run/user/' + str(os.getuid()) + '/pulse/native'
        self.stop = threading.Event()
        self.records = {}
        self.errors = []
        self.sinks = {s['index']: s for s in self.query('sinks')}
        env = {**os.environ, 'LC_ALL': 'C'}
        self.subscription = subprocess.Popen(['pactl', '--server=' + self.server, 'subscribe'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        self.thread = threading.Thread(target=self.observe, daemon=True)
        self.thread.start()

    def query(self, name):
        return json.loads(subprocess.check_output(
            ['pactl', '--server=' + self.server, '--format=json', 'list', name],
            text=True, timeout=3))

    def observe(self):
        pending = b''
        try:
            while not self.stop.is_set():
                if not select.select([self.subscription.stdout], [], [], .1)[0]:
                    if self.subscription.poll() is not None:
                        self.errors.append('PulseAudio subscription exited')
                        break
                    continue
                data = os.read(self.subscription.stdout.fileno(), 65536)
                if not data:
                    if not self.stop.is_set():
                        self.errors.append('PulseAudio subscription closed')
                    break
                pending += data
                lines = pending.split(b'\n')
                pending = lines.pop()
                if not any(b'on sink-input' in line and b"'remove'" not in line for line in lines):
                    continue
                for stream in self.query('sink-inputs'):
                    props = stream.get('properties', {})
                    binary = props.get('application.process.binary', '')
                    # paplay is a pacat symlink; PulseAudio reports the binary
                    # executable, not necessarily argv[0]. Ownership remains
                    # mandatory so another application's pacat is excluded.
                    if binary.rsplit('/', 1)[-1] not in ('paplay', 'pacat') or stream['index'] in self.records:
                        continue
                    if not descendant(int(props.get('application.process.id', '0')), self.owner_pid):
                        continue
                    sink = self.sinks.get(stream['sink'])
                    if sink is None:
                        self.errors.append('Unknown actual playback sink: ' + str(stream['sink']))
                        continue
                    self.records[stream['index']] = Recorder(self.server, sink, stream)
        except Exception as exc:
            self.errors.append(type(exc).__name__ + ': ' + str(exc))

    def close(self):
        self.stop.set()
        self.subscription.terminate()
        self.thread.join(timeout=4)
        self.subscription.wait(timeout=3)
        for recorder in list(self.records.values()):
            recorder.close()

    def results(self, submitted, ended):
        return [r.result() for r in list(self.records.values()) if submitted <= r.started <= ended]
