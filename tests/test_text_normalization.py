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
        self.assertEqual(tn.overrides.proper_names('Yuki Enikk Sugarchain Python CUDA YukiXYZ'),
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
        for text, expected in {'-5': '마이너스 오', 'Python 3.10': '파이썬 삼점일영',
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

class ExceptionBoundaryTests(unittest.TestCase):
    def test_thousands_groups_only(self):
        pattern = tn.overrides.GROUPED_INTEGER
        convert = lambda t: pattern.sub(lambda m:m.group().replace(',', ''), t)
        self.assertEqual(convert('1,024개와 45,000원, 1,234,567.89'), '1024개와 45000원, 1234567.89')
        self.assertEqual(convert('1,024, 다음 숫자는 2,048이다.'), '1024, 다음 숫자는 2048이다.')
        for text in ['1,24', '1,024,56', '1234,567', 'ABC1,024', '안녕, 반가워', '3.1,024', '0,024', '01,024']:
            self.assertEqual(convert(text), text)

    def test_no_general_korean_rewriting(self):
        class Identity:
            def normalize(self, text):return text
        text = '일반 일반적인 일반은 일요일 반 열은 월별 월요일 정상'
        self.assertEqual(tn.overrides.normalize_with_exceptions(text, Identity().normalize), text)

    def test_only_digit_bearing_file_identifiers_are_protected(self):
        self.assertIsNone(tn.overrides.KNOWN_PROTECTED.search('test.wav'))
        self.assertIsNotNone(tn.overrides.KNOWN_PROTECTED.fullmatch('report_v31.1.md'))
        self.assertIsNotNone(tn.overrides.KNOWN_PROTECTED.fullmatch('test.mp3'))

    def test_heard_terms_do_not_change_words_identifiers_or_addresses(self):
        for text in ['Pythonic', 'MyPython', 'CPU2', 'CPU_core', 'xGPU', 'TTS_ENGINE',
                     'APIs', 'VRAM_cache', 'Python.py', 'report', 'API-user',
                     'https://example.com/?name=CPU', 'x+API@example.com']:
            self.assertEqual(tn.overrides.heard_error_readings(text), text)
        self.assertEqual(tn.overrides.heard_error_readings('Python. CPU의 GPU와 VRAM은 TTS API를'),
                         '파이썬. 씨피유의 지피유와 브이램은 티티에스 에이피아이를')

    def test_markers_cannot_collide_with_input(self):
        class Identity:
            def normalize(self, text):return text
        text = '\ue000 일반 \ue001 .mp3'
        self.assertEqual(tn.overrides.normalize_with_exceptions(text, Identity().normalize), text)

    def test_lost_or_duplicate_protection_fails_closed(self):
        class Dropping:
            def normalize(self, text):return ''
        class Duplicating:
            def normalize(self, text):return text + text
        for bad in [Dropping(), Duplicating()]:
            with self.assertRaisesRegex(RuntimeError, 'lost or duplicated'):
                tn.overrides.normalize_with_exceptions('일반', bad.normalize)

    def test_byte_units_are_case_sensitive_and_identifiers_not_units(self):
        for text in ['8Gb', '8gb', 'test8GB', 'test_8GB', '8GBPS', 'test-8GB', '3-8GB']:
            self.assertIsNone(tn.overrides.NUMBER_UNIT.search(text))
        self.assertEqual(tn.overrides.NUMBER_UNIT.fullmatch('-8GB').group('number'), '-8')


@unittest.skipUnless((Path.home() / 'Apps/enikk-nemo-tn/.venv/bin/python').is_file(), 'isolated NeMo unavailable')
class KnownErrorIntegrationTests(unittest.TestCase):
    def test_single_hour_duration_uses_native_numeral(self):
        self.assertEqual(self.client.normalize('1시간 제한'), '한 시간 제한')
        self.assertEqual(self.client.normalize('1시간 안에 확인합니다.'), '한 시간 안에 확인합니다.')

    @classmethod
    def setUpClass(cls):
        cls.client = tn.Client()
        cls.client.initialize()

    @classmethod
    def tearDownClass(cls):
        cls.client.close()

    def test_general_korean_exactly_preserved(self):
        for text in ['일반 한국어 문장입니다. 일반적인 대화를 확인합니다.',
                     '일반은 일반적인 개념이며 일요일과 월요일을 확인한다.',
                     '열은 정상이고 일반적으로 문제없다.']:
            self.assertEqual(self.client.normalize(text), text)

    def test_comma_grouping(self):
        result = self.client.normalize('파일은 1,024개이고 가격은 45,000원입니다.')
        self.assertIn('천이십사', result)
        self.assertIn('사만오천', result)
        self.assertNotIn(',', result)

    def test_known_measure_errors_and_negative_values(self):
        for text, expected in {'8GB': '팔 기가바이트', '512MB': '오백십이 메가바이트',
                               '2TB': '이 테라바이트', '44.1kHz':'사십사점일 킬로헤르츠',
                               '192kbps':'백구십이 킬로비트 퍼 초', '-5GB':'마이너스 오 기가바이트'}.items():
            self.assertEqual(self.client.normalize(text), expected)

    def test_only_user_confirmed_english_errors(self):
        self.assertEqual(self.client.normalize('GPU VRAM CPU TTS API'),
                         '지피유 브이램 씨피유 티티에스 에이피아이')
        text = 'Linux Ubuntu GitHub Codex OpenAI'
        self.assertEqual(self.client.normalize(text), text)

    def test_python_and_speed_unit_readings(self):
        self.assertEqual(self.client.normalize('Python 3.10'), '파이썬 삼점일영')
        self.assertEqual(self.client.normalize('120km/h'), '백이십 킬로미터 퍼 아워')
        self.assertEqual(self.client.normalize('km/h'), '킬로미터 퍼 아워')

    def test_version_fraction_digits_and_extensions(self):
        self.assertEqual(self.client.normalize('Python 3.10'), '파이썬 삼점일영')
        self.assertEqual(self.client.normalize('test.wav와 .mp3 파일을 확인한다.'),
                         'test.wav와 .mp3 파일을 확인한다.')

    def test_known_filename_uses_path_layer_before_public_tn(self):
        from test_tts_delivery import definitions
        source = 'report_v31.1.md 파일도 확인합니다.'
        spoken, records = definitions()['normalize_paths'](source)
        self.assertEqual(self.client.normalize(spoken),
                         '리포트 버전 삼십일 점 일 마크다운 파일도 확인합니다.')
        self.assertEqual(records[0]['original'], 'report_v31.1.md')
        self.assertEqual(self.client.normalize('report_v31.1.md'), 'report_v31.1.md')

    def test_public_working_rules_unchanged(self):
        for text, expected in {'31.1':'삼십일점일', '2.8초':'이점팔 초',
                               '1.25배':'일점이오 배', '99.9%':'구십구점구 퍼센트',
                               '2026년 10월 4일':'이천이십육년 시월 사일',
                               '23:30':'이십삼시 삼십분', '12시 12분':'열두시 십이분'}.items():
            self.assertEqual(self.client.normalize(text), expected)

    def test_long_input_has_no_sentinel_or_content_loss(self):
        text = ('일반 한국어 문장입니다. 파일은 1,024개이고 오디오 설정은 44.1kHz입니다. ' * 24)
        result = self.client.normalize(text)
        self.assertEqual(result.count('일반 한국어 문장입니다.'), 24)
        self.assertEqual(result.count('천이십사'), 24)
        self.assertEqual(result.count('킬로헤르츠'), 24)
        self.assertFalse(any('\ue000' <= c <= '\uf8ff' for c in result))


class LayerSeparationTests(unittest.TestCase):
    def test_public_tn_callback_sees_protected_text_once(self):
        public = Mock()
        public.normalize.side_effect = lambda text: text
        value = tn.overrides.normalize_with_exceptions('일반 Python', public.normalize)
        self.assertEqual(value, '일반 파이썬')
        public.normalize.assert_called_once()
        self.assertNotIn('일반', public.normalize.call_args.args[0])
        self.assertIn('파이썬', public.normalize.call_args.args[0])

    def test_custom_module_is_independent_of_nvidia_and_gpu(self):
        import ast
        tree = ast.parse(Path(tn.overrides.__file__).read_text())
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        self.assertEqual(len(imports), 1)
        self.assertIsInstance(imports[0], ast.Import)
        self.assertEqual([alias.name for alias in imports[0].names], ['re'])
        wrapper = SOURCE.read_text()
        self.assertIn('from nemo_text_processing.text_normalization.normalize import Normalizer', wrapper)
        self.assertNotIn('HEARD_ERRORS =', wrapper)
        self.assertNotIn('KNOWN_UNITS =', wrapper)

    def test_install_and_update_preserve_custom_module(self):
        for name in ['install.sh', 'update.sh']:
            self.assertIn('yuki-text-normalization-overrides.py',
                          (SOURCE.parents[1] / name).read_text())


class SingleHourDurationTests(unittest.TestCase):
    def test_duration_is_protected_before_public_tn(self):
        public = Mock(side_effect=lambda text: text)
        self.assertEqual(tn.overrides.normalize_with_exceptions('1시간 제한, 1시간 안에 확인', public),
                         '한 시간 제한, 한 시간 안에 확인')
        public.assert_called_once()
        self.assertNotIn('1시간', public.call_args.args[0])

    def test_no_other_values_identifiers_ordinals_or_paths(self):
        for text in ['11시간', '31시간', '0.1시간', '1.1시간', '-1시간', '+1시간',
                     '0~1시간', 'test_1시간', '제1시간', '1시간.txt', '/tmp/1시간.wav',
                     '한 시간', '24시간', '12시 12분']:
            self.assertIsNone(tn.overrides.SINGLE_HOUR.search(text), text)
