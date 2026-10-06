import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / 'tts/yuki-text-normalization.py'
spec = importlib.util.spec_from_file_location('tn_test', SOURCE)
tn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tn)


def load_nemo_adapter():
    path = SOURCE.parent / 'upstream/nemo_adapter.py'
    adapter_spec = importlib.util.spec_from_file_location('nemo_adapter_unit_test', path)
    module = importlib.util.module_from_spec(adapter_spec)
    adapter_spec.loader.exec_module(module)
    return module


class NormalizationTests(unittest.TestCase):
    def test_only_proper_names(self):
        self.assertEqual(tn.overrides.proper_names('Yuki Enikk Sugarchain Python CUDA YukiXYZ'),
                         '유키 에닉 슈가체인 Python CUDA YukiXYZ')

    def test_missing_upstream_environment_defaults_custom_only(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(
                os.environ, {'CODEX_ENIKK_TN_HOME': d}, clear=True):
            c = tn.Client()
            c.initialize()
            self.assertIsNone(c.process)
            self.assertEqual(c.normalize('Yuki 8 GB'), '유키 8 GB')

    def test_failed_child_never_claims_ready(self):
        c = load_nemo_adapter().Client()
        c.process = Mock()
        c.process.poll.return_value = 1
        with self.assertRaisesRegex(RuntimeError, 'died'):
            c.initialize()
        c.process = None

    def test_timeout_is_bounded(self):
        adapter = load_nemo_adapter()
        c = adapter.Client()
        c.process = Mock()
        with patch.object(adapter.select, 'select', return_value=([], [], [])):
            with self.assertRaises(TimeoutError):
                c._receive(0.01)
        c.process = None

    def test_protocol_error_is_explicit(self):
        c = load_nemo_adapter().Client()
        c.buffer = b'{"error":"bad input"}\n'
        with self.assertRaisesRegex(RuntimeError, 'bad input'):
            c._receive(1)

    def test_global_upstream_zero_is_custom_only_and_does_not_load_sources(self):
        with tempfile.TemporaryDirectory() as missing:
            service = tn.Client(tn.overrides, upstream_dir=missing)
            with patch.dict(os.environ, {'CODEX_ENIKK_TTS_UPSTREAM': '0',
                                         'CODEX_ENIKK_TN_HOME': str(Path(missing) / 'no-nemo-home')}), \
                    patch.object(tn._orchestrator, '_load_source',
                                 side_effect=AssertionError('upstream source was loaded')), \
                    patch.object(subprocess, 'Popen') as popen:
                service.initialize()
                self.assertEqual(service.normalize('AI CEO and Yuki CPU'),
                                 'AI CEO and 유키 씨피유')
                self.assertEqual(service.normalize('plain text passes through.'), 'plain text passes through.')
                self.assertIsNone(service.process)
                popen.assert_not_called()
            service.close()

    def test_removed_nemo_files_do_not_break_public_custom_only_api(self):
        with tempfile.TemporaryDirectory() as missing, \
                patch.dict(os.environ, {'CODEX_ENIKK_TTS_UPSTREAM': '0',
                                        'CODEX_ENIKK_TN_HOME': str(Path(missing) / 'no-nemo-home')}), \
                patch.object(tn._orchestrator, '_load_source',
                             side_effect=AssertionError('NeMo/dictionary path was touched')), \
                patch.object(subprocess, 'Popen') as popen:
            tn.initialize()
            self.assertEqual(tn.normalize('Yuki CPU and AI'), '유키 씨피유 and AI')
            self.assertIsNone(tn._service.process)
            popen.assert_not_called()

    def test_enabled_order_keeps_dictionary_custom_and_nemo_layers_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'selected_korean_dictionary.py').write_text(
                "def apply(text): return text.replace('AI', '에이아이')\n")
            (root / 'nemo_adapter.py').write_text(
                'def initialize(): pass\ndef normalize(text): return text\ndef close(): pass\n')
            service = tn.Client(tn.overrides, upstream_dir=root)
            with patch.dict(os.environ, {'CODEX_ENIKK_TTS_UPSTREAM': '1'}):
                service.initialize()
                self.assertEqual(service.normalize('AI Yuki'), '에이아이 유키')
            service.close()

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
        cls.upstream_env = patch.dict(os.environ, {'CODEX_ENIKK_TTS_UPSTREAM': '1'})
        cls.upstream_env.start()
        cls.client = tn.Client()
        cls.client.initialize()

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.upstream_env.stop()

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
    def test_weekday_collision_contexts_have_bounded_endings(self):
        pattern = tn.overrides.WEEKDAY_COLLISION_PHRASE
        for text in ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일',
                     '가수 없으면', '수 없었다', '수 없다는', '목 건강보험',
                     '금 가격표', '일 처리기', '일 하나둘', '일수 계산기',
                     '/목 건강', '목 건강.txt', '@금 가격', '수 없다.py']:
            self.assertIsNone(pattern.search(text), text)

    def test_weekday_filename_protection_only_covers_standalone_names(self):
        pattern = tn.overrides.WEEKDAY_INITIAL_FILENAME
        for name in ['월.py', '화.txt', '수.md', '목.json', '금.wav', '토.sh', '일.log']:
            self.assertIsNotNone(pattern.fullmatch(name), name)
            for text in ['prefix_'+name, '/tmp/'+name, name+'@example.com',
                         'https://example.com/'+name, name+'.backup']:
                self.assertIsNone(pattern.search(text), text)

    def test_audited_nouns_exclude_weekdays_and_identifiers(self):
        pattern = tn.overrides.AUDITED_NOUN_PHRASE
        for text in ['수요일 있습니다', '일요일 하나', '가수 있습니다',
                     '할일 하나', '수 있습니다.py', '/수 없다', '@수 있는',
                     '수 있다는', '수 없어요.txt', '일 하나둘', '수 있었어요']:
            self.assertIsNone(pattern.search(text), text)

    def test_literary_weekday_collisions_have_identifier_boundaries(self):
        cases = [
            (tn.overrides.LITERARY_SU_PHRASE,
             ['수 있을지', '수 없는', '수 없이', '수 있었다'],
             ['수요일 있을지', '가수 없는', '/수 없이', '수 있었다.py', '수 있었던']),
            (tn.overrides.SEVERAL_MOVES_AHEAD,
             ['몇 수 앞을'],
             ['몇 수 앞', '아몇 수 앞을', '/몇 수 앞을', '몇 수 앞을.txt']),
            (tn.overrides.ONE_YEAR_DURATION,
             ['일 년', '일 년 동안'],
             ['일 년도', '/일 년', '일 년.txt', '일요일 년']),
        ]
        for pattern, positives, negatives in cases:
            for text in positives:
                self.assertIsNotNone(pattern.search(text), text)
            for text in negatives:
                self.assertIsNone(pattern.search(text), text)

    def test_su_isseo_protection_has_narrow_boundaries(self):
        pattern = tn.overrides.SU_ISSEO_PHRASE
        for text in ['설치할 수 있으므로 중단한다.', '변경이 섞일 수 있어.']:
            self.assertIsNotNone(pattern.search(text), text)
        for text in ['수요일 있어', '가수 있어', '수 있어서', '수 있어요',
                     '수 있어.txt', '/수 있어', '@수 있으므로', '수 있음']:
            self.assertIsNone(pattern.search(text), text)

    def test_branch_reading_only_changes_prose_token(self):
        self.assertEqual(tn.overrides.heard_error_readings('현재 branch 상태와 branch는'),
                         '현재 브랜치 상태와 브랜치는')
        for text in ['branches', 'Branch', 'branch_name', 'mybranch', 'branch.py',
                     '/tmp/branch', 'feature/branch', 'branch-user',
                     'https://example.com/?name=branch', 'branch@example.com']:
            self.assertEqual(tn.overrides.heard_error_readings(text), text)

    def test_branch_coordinating_particle_matches_vowel_reading(self):
        self.assertEqual(
            tn.overrides.heard_error_readings('GitHub에서는 branch과 switch가 바뀌었다.'),
            'GitHub에서는 브랜치와 switch가 바뀌었다.')
        for text in ['branch과_switch', 'branch과.py', '/tmp/branch과 switch',
                     'feature/branch과 switch', 'https://example.com/branch과',
                     'branch과@example.com']:
            self.assertEqual(tn.overrides.heard_error_readings(text), text)

    def test_large_item_count_boundaries(self):
        pattern = tn.overrides.LARGE_ITEM_COUNT
        self.assertIsNotNone(pattern.search('284개를 확인한다.'))
        for text in ['3개', '28개', '17개', '0.284개', '-284개', '+284개', 'A284개',
                     'id_284개', '284개.txt', '/284개', '284개API']:
            self.assertIsNone(pattern.search(text), text)

    def test_su_eopseo_protection_excludes_other_contexts(self):
        pattern = tn.overrides.SU_EOPSEO_PHRASE
        self.assertIsNotNone(pattern.search('원인으로 단정할 수 없어.'))
        for text in ['수요일 없어', '가수 없어', '수 없어도', '수 없어요',
                     '수 없어.txt', '/수 없어', '@수 없어', '수 있도록',
                     'CPU GPU API', '수 초가']:
            self.assertIsNone(pattern.search(text), text)

    def test_few_seconds_protection_has_narrow_boundaries(self):
        pattern = tn.overrides.FEW_SECONDS_SUBJECT
        self.assertIsNotNone(pattern.search('retry 때문에 수 초가 더 걸렸어.'))
        for text in ['수요일 초가', '수 초가량', '가수 초가', '수 초가.txt',
                     '수 초', '수 있도록', '수 없어']:
            self.assertIsNone(pattern.search(text), text)

    def test_su_ittorok_protection_has_narrow_boundaries(self):
        pattern = tn.overrides.SU_ITTOROK_PHRASE
        self.assertIsNotNone(pattern.search('이어받을 수 있도록 상태를 남긴다.'))
        for text in ['수요일', '수 있도록이', '가수 있도록', '수 있도록.txt',
                     '수 초가', '수 없어']:
            self.assertIsNone(pattern.search(text), text)

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
    def test_weekday_collision_audit_preserves_confirmed_meanings(self):
        for text in ['실행할 수 없다.', '실행할 수 없으면 중단합니다.',
                     '실행할 수 있어서 진행합니다.', '실행할 수 있어도 대기합니다.',
                     '실행할 수 없지만 기록합니다.', '수 없습니다.',
                     '목 건강을 확인합니다.', '목 안쪽이 아픕니다.',
                     '금 가격을 확인합니다.', '금 한 돈을 샀습니다.',
                     '일 처리를 확인합니다.', '이 일 하나부터 끝냅니다.',
                     '이 일 두 개를 끝냅니다.', '일수 계산을 확인합니다.',
                     '이번 월 말에 만납니다.', '분노의 화 관리를 확인합니다.',
                     '흙의 토 분류를 확인합니다.', '흙의 토 색상을 확인합니다.',
                     '월.py 화.txt 수.md 목.json 금.wav 토.sh 일.log']:
            with self.subTest(text=text):
                self.assertEqual(self.client.normalize(text), text)
        for weekday in ['월요일', '화요일', '수요일', '목요일', '금요일', '토요일', '일요일']:
            text = weekday + ' 오전에 시작합니다.'
            self.assertEqual(self.client.normalize(text), text)

    def test_audited_nouns_do_not_become_weekdays(self):
        for text in ['확인할 수 있습니다.', '확인할 수 없어요.',
                     '확인할 수 없어서 중단합니다.', '확인할 수 있는 상태입니다.',
                     '확인할 수 있다.', '일 하나를 끝냅니다.']:
            with self.subTest(text=text):
                self.assertEqual(self.client.normalize(text), text)

    def test_confirmed_ability_phrases_are_not_weekdays(self):
        for text in ['변경까지 설치할 수 있으므로 중단할게.', '변경이 섞일 수 있어.']:
            self.assertEqual(self.client.normalize(text), text)

    def test_branch_prose_reading(self):
        self.assertEqual(self.client.normalize('현재 branch 상태를 확인할게.'),
                         '현재 브랜치 상태를 확인할게.')

    def test_large_item_counts_keep_numeric_value(self):
        for text, expected in [('46개', '사십육 개'),
                               ('48개', '사십팔 개'),
                               ('61개', '육십일 개'),
                               ('28개', '스물여덟개'),
                               ('17개', '열일곱개'),
                               ('282개', '이백팔십이 개'),
                               ('284개', '이백팔십사 개'),
                               ('1,024개', '천이십사 개')]:
            self.assertEqual(self.client.normalize(text), expected)

    def test_su_eopseo_is_not_wednesday(self):
        text = '길이나 영문 혼합만 원인으로 단정할 수 없어.'
        self.assertEqual(self.client.normalize(text), text)

    def test_few_seconds_duration_is_not_wednesday(self):
        self.assertEqual(self.client.normalize('retry 때문에 수 초가 더 걸렸어.'),
                         'retry 때문에 수 초가 더 걸렸어.')
        self.assertEqual(self.client.normalize('수요일에는 쉬겠습니다.'),
                         '수요일에는 쉬겠습니다.')

    def test_su_ittorok_is_not_wednesday(self):
        self.assertEqual(self.client.normalize('이어받을 수 있도록 branch 상태를 남길게.'),
                         '이어받을 수 있도록 브랜치 상태를 남길게.')
        self.assertEqual(self.client.normalize('수요일에는 쉬겠습니다.'),
                         '수요일에는 쉬겠습니다.')

    def test_work_noun_is_not_abbreviated_weekday(self):
        self.assertEqual(self.client.normalize('작은 일부터 하나씩 시작하면 돼.'),
                         '작은 일부터 하나씩 시작하면 돼.')
        self.assertEqual(self.client.normalize('일요일에는 쉬겠습니다.'),
                         '일요일에는 쉬겠습니다.')

    def test_literary_dependent_nouns_and_one_year_are_not_weekdays(self):
        for text in [
                '몇 수 앞을 내다보는 노인의 눈빛에는 서두름이 없었다.',
                '끝까지 해낼 수 있을지 걱정됐지만 동료의 격려가 힘이 되었다.',
                '이번에는 놓칠 수 없는 기회라고 생각해 그는 먼 길을 떠났다.',
                '한 번에 할 수 없는 일이라면 작은 단계로 나누어 시작하면 된다.',
                '오늘은 어쩔 수 없이 떠나지만 내일 해가 뜨면 돌아오겠다고 말했다.',
                '몇 차례의 시도 끝에 아이는 제 힘으로 매듭을 묶을 수 있었다.',
                '짧은 목차만으로도 이 책이 어떤 질문을 다루는지 알 수 있었다.',
                '그들은 일 년 동안 모은 기록을 한 권의 책으로 엮었다.']:
            with self.subTest(text=text):
                self.assertEqual(self.client.normalize(text), text)

    def test_single_hour_attached_eman_uses_native_numeral(self):
        self.assertEqual(self.client.normalize('1시간에만 집중하겠습니다.'),
                         '한 시간에만 집중하겠습니다.')

    def test_single_hour_duration_uses_native_numeral(self):
        self.assertEqual(self.client.normalize('1시간 제한'), '한 시간 제한')
        self.assertEqual(self.client.normalize('1시간 안에 확인합니다.'), '한 시간 안에 확인합니다.')

    @classmethod
    def setUpClass(cls):
        cls.upstream_env = patch.dict(os.environ, {'CODEX_ENIKK_TTS_UPSTREAM': '1'})
        cls.upstream_env.start()
        cls.client = tn.Client()
        cls.client.initialize()

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.upstream_env.stop()

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
        orchestrator = (SOURCE.parent / 'upstream/orchestrator.py').read_text()
        adapter = (SOURCE.parent / 'upstream/nemo_adapter.py').read_text()
        self.assertNotIn('nemo_text_processing', wrapper)
        self.assertNotIn('nemo_text_processing', orchestrator)
        self.assertIn('from nemo_text_processing.text_normalization.normalize import Normalizer', adapter)
        self.assertIn("os.environ.get('CODEX_ENIKK_TTS_UPSTREAM', '0') != '0'", orchestrator)
        self.assertNotIn('HEARD_ERRORS =', wrapper)
        self.assertNotIn('KNOWN_UNITS =', wrapper)

    def test_install_and_update_preserve_custom_module(self):
        for name in ['install.sh', 'update.sh']:
            script = (SOURCE.parents[1] / name).read_text()
            self.assertIn('yuki-text-normalization-overrides.py', script)
            self.assertIn('selected_korean_dictionary.py', script)
            self.assertIn('orchestrator.py', script)
            self.assertIn('nemo_adapter.py', script)
            self.assertIn('manifest.json', script)

    def test_custom_only_setup_skips_nemo_preparation(self):
        setup = (SOURCE.parent / 'setup-tts.sh').read_text()
        self.assertIn('CODEX_ENIKK_TTS_UPSTREAM:-0', setup)
        self.assertIn('NeMo upstream disabled; keeping TTS setup custom-only.', setup)
        nemo_setup = (SOURCE.parent / 'setup-nemo-tn.sh').read_text()
        self.assertIn('CODEX_ENIKK_TTS_UPSTREAM=1', nemo_setup)


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


class SingleHourParticleBoundaryTests(unittest.TestCase):
    def test_only_confirmed_eman_suffix(self):
        for text in ['1시간에만 집중', '1시간에만.', '1시간에만']:
            self.assertEqual(tn.overrides.normalize_with_exceptions(text, lambda t:t),
                             text.replace('1시간', '한 시간'))
        for text in ['11시간에만', '1.1시간에만', '-1시간에만', '+1시간에만',
                     '제1시간에만', 'test_1시간에만', '1시간에만큼',
                     '1시간에만.txt', '/tmp/1시간에만', '1시간에는']:
            self.assertIsNone(tn.overrides.SINGLE_HOUR.search(text), text)


class WorkNounContextTests(unittest.TestCase):
    def test_only_confirmed_phrase_is_protected(self):
        public = Mock(side_effect=lambda t:t)
        self.assertEqual(tn.overrides.normalize_with_exceptions('작은 일부터 하나씩 시작해.', public),
                         '작은 일부터 하나씩 시작해.')
        public.assert_called_once()
        self.assertNotIn('작은 일부터', public.call_args.args[0])
        for text in ['일요일', '월 화 수 목 금 토 일', '작은 일', '작은 일요일부터',
                     '아주작은 일부터', '작은 일부터는', '큰 일부터', '오늘 할 일을']:
            self.assertIsNone(tn.overrides.WORK_NOUN_PHRASE.search(text), text)
