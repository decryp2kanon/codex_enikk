"""CPU-only delivery tests: load stdlib engine definitions without ML imports."""
import ast
import fcntl
import json
import logging
import os
from pathlib import Path
import queue
import re
import subprocess
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / 'tts/yuki-chatterbox-engine.py'


def definitions():
    tree = ast.parse(SOURCE.read_text())
    names = {'DeliveryJob', 'playback', 'run', 'GenerationWarnings',
             'sentences', 'speech_chunks', 'segment_drop_reason'}
    tree.body = [node for node in tree.body if getattr(node, 'name', None) in names]
    scope = dict(Path=Path, os=os, tempfile=tempfile, json=json, threading=threading,
                 time=time, subprocess=types.SimpleNamespace(run=Mock(), DEVNULL=subprocess.DEVNULL),
                 queue=queue, logging=logging, fcntl=fcntl, re=re, log=Mock())
    exec(compile(tree, str(SOURCE), 'exec'), scope)
    return scope


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scope = definitions()

    def job(self, parts=('first', 'second')):
        path = self.root / 'job'
        item = dict(id='test', text=' '.join(parts), queued_ns=time.monotonic_ns())
        path.write_text(json.dumps(item))
        return self.scope['DeliveryJob'](path, item, list(parts))

    def test_partial_ack_survives_restart(self):
        job = self.job()
        job.finish(0, 'played')
        self.assertTrue(job.path.exists())
        resumed = self.scope['DeliveryJob'](job.path, json.loads(job.path.read_text()), [])
        self.assertEqual(resumed.parts, ['first', 'second'])
        self.assertEqual(resumed.terminal, {'0': 'PLAYED'})
        resumed.finish(1, 'played')
        self.assertFalse(job.path.exists())
        self.assertTrue(resumed.complete)

    def test_failed_atomic_write_preserves_pending_job(self):
        job = self.job()
        with patch.object(os, 'replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                job.finish(0, 'played')
        self.assertEqual(json.loads(job.path.read_text())['delivery']['terminal'], {})
        self.assertFalse(job.complete)

    def test_terminal_record_before_cleanup_does_not_replay(self):
        job = self.job()
        job.item['delivery']['terminal'] = {'0': 'PLAYED', '1': 'PLAYED'}
        job.path.write_text(json.dumps(job.item))
        resumed = self.scope['DeliveryJob'](job.path, json.loads(job.path.read_text()), [])
        self.assertTrue(resumed.complete)
        self.assertFalse(job.path.exists())

    def test_playback_errors_do_not_kill_consumer(self):
        for error in (subprocess.CalledProcessError(1, 'aplay'), OSError('device'), RuntimeError('unexpected')):
            with self.subTest(error=type(error).__name__):
                job = self.job()
                self.scope['subprocess'].run = Mock(side_effect=[error, None])
                ready = queue.Queue()
                for number in range(2):
                    wav = self.root / f'{number}.wav'; wav.write_bytes(b'test')
                    ready.put((job, number, str(wav), time.monotonic_ns(), time.monotonic(), .01))
                thread = threading.Thread(target=self.scope['playback'], args=(ready,), daemon=True)
                thread.start()
                deadline = time.monotonic() + 2
                while ready.unfinished_tasks and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertEqual(ready.unfinished_tasks, 0)
                self.assertTrue(thread.is_alive())
                self.assertEqual(job.terminal, {'0': 'FAILED_EXPLICITLY', '1': 'PLAYED'})
                self.assertFalse(job.path.exists())
                failed = json.loads((self.root / '.failed-job').read_text())
                self.assertEqual(failed['delivery']['terminal']['0'], 'FAILED_EXPLICITLY')
                self.assertIn('0', failed['delivery']['failures'])
                ready.put(None); thread.join(2)
                self.assertFalse(thread.is_alive())

    def test_run_prefetch_claim_and_delivery_order(self):
        self.exercise_run()

    def test_generation_failure_is_retained_after_two_attempts(self):
        self.exercise_run(fail=True)

    def exercise_run(self, fail=False):
        jobs = self.root / 'jobs'; jobs.mkdir()
        source = jobs / 'job'
        source.write_text(json.dumps(dict(id='normal', text='a|b|c|d|e|f|g|h', queued_ns=time.monotonic_ns())))
        reference = self.root / 'ref'; reference.touch()
        entered = threading.Event(); release = threading.Event(); stop = threading.Event()
        generated = []; played = []; scanned = threading.Event(); queues = []
        class StopRun(Exception):
            pass
        def sleep(_):
            scanned.set()
            if stop.wait(.005):
                raise StopRun()
        def synth(text, **kwargs):
            generated.append(text)
            if fail and text == "d":
                raise RuntimeError("injected generation failure")
            return types.SimpleNamespace(cpu=lambda: text)
        def play(args, **kwargs):
            text = Path(args[-1]).read_text()
            if not played:
                entered.set()
                if not release.wait(2):
                    raise RuntimeError('test timed out')
            played.append(text)
        def make_queue():
            result = queue.Queue(); queues.append(result); return result
        model = types.SimpleNamespace(sr=24000, generate=synth, prepare_conditionals=Mock())
        self.scope.update(STATE=self.root, JOBS=jobs, REFERENCE=reference,
            torch=types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False, empty_cache=Mock())),
            ChatterboxMultilingualTTS=types.SimpleNamespace(from_pretrained=lambda **kw:model),
            conditioning_state=lambda m:'test', speech_chunks=lambda text:text.split('|'),
            korean_pronunciation=lambda text:text,
            trim_edge_silence=lambda wav,sr:(wav,0,0),
            suspicious_audio=lambda wav,sr,text:(False,'',.01),
            torchaudio=types.SimpleNamespace(save=lambda path,wav,sr:Path(path).write_text(wav)),
            queue=types.SimpleNamespace(Queue=make_queue),
            time=types.SimpleNamespace(monotonic=time.monotonic, monotonic_ns=time.monotonic_ns, sleep=sleep))
        self.scope['subprocess'].run = play
        errors = []
        def worker():
            try:self.scope['run']()
            except StopRun:pass
            except Exception as exc:errors.append(exc)
        thread = threading.Thread(target=worker, daemon=True); thread.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assertTrue(scanned.wait(2))
            time.sleep(.04)  # several scans while first WAV is still playing
            self.assertEqual(generated, list('abcddefgh') if fail else list('abcdefgh'))  # prefetch + no duplicate claims
            self.assertTrue(source.exists())
            self.assertEqual(json.loads(source.read_text())['delivery']['terminal'], {'3': 'FAILED_EXPLICITLY'} if fail else {})
            release.set()
            deadline=time.monotonic()+2
            while source.exists() and time.monotonic()<deadline:time.sleep(.005)
            self.assertFalse(source.exists())
            self.assertEqual(played, list('abcefgh') if fail else list('abcdefgh'))
            if fail:
                saved = json.loads((jobs / '.failed-job').read_text())
                self.assertEqual(saved['delivery']['parts'][3], 'd')
                self.assertIn('injected generation failure', saved['delivery']['failures']['3'])
                self.assertEqual(len(saved['delivery']['terminal']), 8)
            self.assertFalse(errors)
        finally:
            release.set();stop.set();thread.join(2)
            if queues:queues[0].put(None)


if __name__ == '__main__':
    unittest.main()
