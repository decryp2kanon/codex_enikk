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



class NormalizationTests(unittest.TestCase):
    def test_only_proper_names(self):
        self.assertEqual(tn.overrides.proper_names('Yuki Enikk Sugarchain Python CUDA YukiXYZ'),
                         '유키 에닉 슈가체인 Python CUDA YukiXYZ')

    def test_custom_client_has_no_external_process(self):
        c = tn.Client()
        c.initialize()
        self.assertIsNone(c.process)
        self.assertEqual(c.normalize('Yuki 8 GB'), '유키 팔 기가바이트')
        c.close()

    def test_core_environment_not_used(self):
        text = SOURCE.read_text()
        self.assertNotIn('chatterbox-yuki/.venv', text)
        self.assertNotIn('apply_phonology', text)

    def test_no_duplicate_path_normalization(self):
        engine = SOURCE.with_name('yuki-chatterbox-engine.py').read_text()
        self.assertNotIn('KOREAN_TECH', engine)
        self.assertNotIn('normalize_numbers', engine)
        self.assertIn('normalized_text = korean_pronunciation(spoken_text)', engine)
        self.assertIn('originals = speech_chunks(normalized_text,', engine)


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
            match = tn.overrides.NUMBER_UNIT.search(text)
            self.assertTrue(match is None or match.group('unit') not in tn.overrides.KNOWN_UNITS)
            self.assertEqual(tn.normalize(text), text)
        self.assertEqual(tn.overrides.NUMBER_UNIT.fullmatch('-8GB').group('number'), '-8')


class CustomOnlyArchitectureTests(unittest.TestCase):
    def test_custom_module_is_independent_of_optional_normalizers(self):
        import ast
        tree = ast.parse(Path(tn.overrides.__file__).read_text())
        imports = [node for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))]
        modules = {alias.name for node in imports if isinstance(node, ast.Import)
                   for alias in node.names}
        modules.update(node.module for node in imports if isinstance(node, ast.ImportFrom))
        # JSON span recognition is standard-library parsing, not an optional
        # language normalizer or a production network/runtime dependency.
        self.assertEqual(modules, {'re', 'functools', 'json'})
        self.assertEqual([(node.module, [alias.name for alias in node.names])
                          for node in imports if isinstance(node, ast.ImportFrom)],
                         [('functools', ['lru_cache'])])
        wrapper = SOURCE.read_text()
        self.assertNotIn('HEARD_ERRORS =', wrapper)
        self.assertNotIn('KNOWN_UNITS =', wrapper)

    def test_install_and_update_preserve_only_custom_normalization(self):
        for name in ['tts_release.py']:
            script = (SOURCE.parents[1] / name).read_text()
            self.assertIn('yuki-text-normalization.py', script)
            self.assertIn('yuki-text-normalization-overrides.py', script)

    def test_setup_has_no_optional_normalizer_setup(self):
        setup = (SOURCE.parent / 'setup-tts.sh').read_text()


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
