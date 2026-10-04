import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / 'tts/yuki-text-normalization.py'
spec = importlib.util.spec_from_file_location('tn_test', SOURCE)
tn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tn)


class NormalizationTests(unittest.TestCase):
    def test_only_proper_names(self):
        self.assertEqual(tn.proper_names('Yuki Enikk Sugarchain Python CUDA YukiXYZ'),
                         '유키 에닉 슈가체인 Python CUDA YukiXYZ')

    def test_missing_environment_fails_closed(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ, CODEX_ENIKK_TN_HOME=d):
            c = tn.Client()
            with self.assertRaisesRegex(RuntimeError, 'environment missing'):
                c.initialize()
            self.assertIsNone(c.process)

    def test_failed_child_never_claims_ready(self):
        c = tn.Client()
        c.process = Mock()
        c.process.poll.return_value = 1
        with self.assertRaisesRegex(RuntimeError, 'died'):
            c.initialize()
        c.process = None

    def test_timeout_is_bounded(self):
        c = tn.Client()
        c.process = Mock()
        with patch.object(tn.select, 'select', return_value=([], [], [])):
            with self.assertRaises(TimeoutError):
                c._receive(0.01)
        c.process = None

    def test_protocol_error_is_explicit(self):
        c = tn.Client()
        c.buffer = b'{"error":"bad input"}\n'
        with self.assertRaisesRegex(RuntimeError, 'bad input'):
            c._receive(1)

    def test_core_environment_not_used(self):
        text = SOURCE.read_text()
        self.assertNotIn('chatterbox-yuki/.venv', text)
        self.assertNotIn('apply_phonology', text)

    def test_no_duplicate_path_normalization(self):
        engine = SOURCE.with_name('yuki-chatterbox-engine.py').read_text()
        self.assertNotIn('KOREAN_TECH', engine)
        self.assertNotIn('normalize_numbers', engine)
        self.assertIn('normalized_text = korean_pronunciation(spoken_text)', engine)
        self.assertIn('originals = speech_chunks(normalized_text)', engine)


@unittest.skipUnless((Path.home() / 'Apps/enikk-nemo-tn/.venv/bin/python').is_file(), 'optional isolated NeMo fixture')
class InstalledGrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = tn.Client()
        cls.client.initialize()

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_actual_public_rules(self):
        for text, expected in {'-5': '마이너스 오', 'Python 3.10': 'Python 삼점일영',
                               '2026년 10월 4일': '이천이십육년 시월 사일'}.items():
            self.assertEqual(self.client.normalize(text), expected)

    def test_reuse_and_no_gpu(self):
        p = self.client.process
        self.client.normalize('12시 12분')
        self.client.normalize('0')
        self.assertIs(self.client.process, p)
        self.assertIsNone(p.poll())

    def test_raw_english_and_named_exceptions(self):
        self.assertEqual(self.client.normalize('OpenAI Codex'), 'OpenAI Codex')
        self.assertEqual(self.client.normalize('Yuki Enikk Sugarchain'), '유키 에닉 슈가체인')

    def test_whitespace(self):
        self.assertEqual(self.client.normalize(' \n '), ' \n ')

class WorkerNormalizationFailureTests(unittest.TestCase):
    def test_failure_has_terminal_receipt_without_generation(self):
        from test_tts_delivery import definitions
        import types
        import queue
        scope = definitions()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            jobs = root / 'jobs'; jobs.mkdir()
            (jobs / 'input').write_text(json.dumps({'id': 'n', 'text': '안녕.', 'run_id': 'fixture'}))
            ref = root / 'ref'; ref.touch()
            model = types.SimpleNamespace(prepare_conditionals=Mock(), generate=Mock())
            ready = queue.Queue()
            class Finished(Exception):
                pass
            scope.update(STATE=root, JOBS=jobs, REFERENCE=ref, watch_owner=Mock(),
                torch=types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda:False)),
                ChatterboxMultilingualTTS=types.SimpleNamespace(from_pretrained=lambda **kw:model),
                conditioning_state=lambda m:'fixture',
                queue=types.SimpleNamespace(Queue=lambda:ready),
                time=types.SimpleNamespace(monotonic=lambda:0, monotonic_ns=lambda:0,
                    sleep=Mock(side_effect=Finished)),
                korean_pronunciation=Mock(side_effect=TimeoutError('normalization timeout')))
            try:
                with patch.dict(os.environ, CODEX_ENIKK_TTS_MODEL_LOCK=str(root / 'model.lock'), CODEX_ENIKK_TTS_OWNER='', CODEX_ENIKK_TTS_RUN_ID='fixture'):
                    with self.assertRaises(Finished):
                        scope['run']()
                receipt = json.loads((jobs / '.failed-input').read_text())
                self.assertEqual(receipt['delivery']['terminal'], {'0':'FAILED_EXPLICITLY'})
                self.assertIn('normalization timeout', receipt['delivery']['failures']['0'])
                model.generate.assert_not_called()
            finally:
                ready.put(None)
