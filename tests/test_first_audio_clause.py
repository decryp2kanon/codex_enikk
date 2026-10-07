"""First-clause splitting must preserve content and avoid tiny fragments."""
import unittest
from test_tts_delivery import definitions


class FirstClauseTests(unittest.TestCase):
    def setUp(self):
        self.split = definitions()['speech_chunks']

    def test_complete_connective_clause_and_remainder(self):
        inputs = [
            '현재 시스템 상태는 정상이며 다음 작업을 계속 진행합니다.',
            '현재 서비스 상태는 정상이며 다음 요청을 순서대로 처리합니다.',
            '지금 저장소 상태는 정상이며 변경 내용을 함께 확인합니다.',
        ]
        for raw in inputs:
            with self.subTest(raw=raw):
                parts = self.split(raw)
                self.assertGreaterEqual(len(parts), 2)
                self.assertTrue(parts[0].endswith('정상이며'))
                self.assertEqual(' '.join(parts), raw)
                self.assertGreaterEqual(len(parts[0]), 14)

    def test_no_arbitrary_split_or_tiny_leading_clause(self):
        for raw in ['네, 다음 작업을 계속 진행하며 결과를 확인합니다.',
                    '작업을 계속 진행합니다.',
                    'This is an ordinary sentence without a Korean connective.',
                    'commit abcdef1234567890 completed']:
            parts = self.split(raw)
            self.assertEqual(' '.join(parts), raw)
            self.assertFalse(parts[0] == '네,')

    def test_only_first_chunk_is_eligible(self):
        raw = '앞에서 설명한 내용을 먼저 확인합니다. 현재 시스템 상태는 정상이며 다음 작업을 계속 진행합니다.'
        parts = self.split(raw)
        self.assertEqual(' '.join(parts), raw)
        self.assertNotIn('현재 시스템 상태는 정상이며', parts)
