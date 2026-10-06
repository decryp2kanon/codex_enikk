import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / 'tts/yuki-text-normalization.py'
UPSTREAM = ROOT / 'tts/upstream/selected_korean_dictionary.py'


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


tn = load_module(WRAPPER, 'tn_upstream_test')
rules = load_module(UPSTREAM, 'selected_korean_dictionary_test')


class UpstreamDictionaryTests(unittest.TestCase):
    def test_nine_exact_prose_tokens(self):
        expected = {
            'AI': '에이아이', 'CEO': '씨이오', 'PC': '피씨',
            'CCTV': '씨씨티비', 'SNS': '에스엔에스', 'KOREA': '코리아',
            'IDOL': '아이돌', 'IT': '아이티', 'IQ': '아이큐',
        }
        for source, spoken in expected.items():
            with self.subTest(source=source):
                self.assertEqual(rules.apply(f'{source} 테스트'), f'{spoken} 테스트')

    def test_identifier_and_literal_boundaries_are_preserved(self):
        samples = [
            'AI_model', 'xAI', 'AI42', '42AI', 'AI/path', '/AI',
            'AI.wav', 'report_AI.txt', 'userAI@example.com',
            'https://example.com/AI?mode=PC', 'A+B=AI', 'AI==5',
            'AI+PC', 'PC-code', 'prefix.CCTV',
        ]
        for sample in samples:
            with self.subTest(sample=sample):
                self.assertEqual(rules.apply(sample), sample)

    def test_prose_punctuation_and_case(self):
        self.assertEqual(rules.apply('(AI), CEO! pc and ai'), '(에이아이), 씨이오! pc and ai')

    def test_disabled_layer_is_identity(self):
        disabled = tn._orchestrator.Service(tn.overrides, upstream_dir=ROOT / 'missing-upstreams')
        with patch.dict(os.environ, {'CODEX_ENIKK_TTS_UPSTREAM': '0'}):
            disabled.initialize()
            self.assertEqual(disabled.normalize('AI CEO'), 'AI CEO')
            self.assertIsNone(disabled.process)
        disabled.close()

    def test_environment_switch_disables_layer(self):
        with patch.dict(os.environ, {'CODEX_ENIKK_TTS_UPSTREAM': '0'}):
            disabled = tn.Client()
            self.assertEqual(disabled.normalize('AI CEO and Yuki'),
                             'AI CEO and 유키')
        disabled.close()

    def test_missing_module_is_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            disabled = tn._orchestrator.Service(tn.overrides, upstream_dir=Path(temp))
            with patch.dict(os.environ, {'CODEX_ENIKK_TTS_UPSTREAM': '0'}):
                self.assertEqual(disabled.normalize('AI CEO'), 'AI CEO')
                self.assertIsNone(disabled.process)
            disabled.close()

    def test_manifest_has_all_stable_rule_ids(self):
        manifest = json.loads((ROOT / 'tts/upstream/manifest.json').read_text())
        self.assertEqual([item['id'] for item in manifest['rules']],
                         [f'UDK-{number:03d}' for number in range(1, 10)])
        self.assertEqual(set(manifest['tests']), {
            'tests/test_upstream_normalization.py', 'tests/test_text_normalization.py'})

    def test_service_has_one_explicit_runtime_connection(self):
        source = WRAPPER.read_text()
        orchestrator = (ROOT / 'tts/upstream/orchestrator.py').read_text()
        self.assertEqual(source.count('_orchestrator.Service'), 1)
        self.assertIn('_service = Client()', source)
        self.assertIn('CODEX_ENIKK_TTS_UPSTREAM', orchestrator)
        self.assertIn('self.custom.normalize_with_exceptions(text, upstream_adapter.normalize)', orchestrator)


if __name__ == '__main__':
    unittest.main()
