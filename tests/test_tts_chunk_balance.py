"""Offline scheduler checks; no model load or audio playback."""
import unittest
from test_tts_delivery import definitions


class BalancedTailTests(unittest.TestCase):
    def setUp(self):
        self.chunks = definitions()['speech_chunks']

    def assert_tokens(self, text, chunks):
        self.assertEqual(text.split(), [word for chunk in chunks for word in chunk.split()])

    def test_clause_boundary_balances_long_merged_tail(self):
        text = '새로운 작업의 진행 상태를 확인하고, 남은 검증 결과를 차분하게 살펴봅니다.'
        chunks = self.chunks(text)
        self.assertEqual(chunks, ['새로운 작업의 진행 상태를 확인하고,', '남은 검증 결과를 차분하게 살펴봅니다.'])
        self.assert_tokens(text, chunks)

    def test_korean_connective_boundary(self):
        text = '현재 작업의 자세한 진행 상태를 확인했지만 남아 있는 검증 결과도 함께 확인합니다.'
        chunks = self.chunks(text)
        self.assertEqual(chunks, ['현재 작업의 자세한 진행 상태를 확인했지만', '남아 있는 검증 결과도 함께 확인합니다.'])
        self.assert_tokens(text, chunks)

    def test_no_feasible_pair_keeps_short_tail_joined(self):
        text = '슈퍼 클린 C2는 버전 31.1에서 3.2GB를 사용합니다.'
        self.assertEqual(self.chunks(text), [text])

    def test_short_complete_sentence_unchanged(self):
        text = '오늘도 작은 일을 차근차근 마무리해 봅니다.'
        self.assertEqual(self.chunks(text), [text])

    def test_earlier_complete_chunk_unchanged(self):
        prefix = '오늘은 작업을 시작하기 전에 필요한 내용을 확인합니다.'
        tail = '새로운 작업의 진행 상태를 확인하고, 남은 검증 결과를 차분하게 살펴봅니다.'
        chunks = self.chunks(prefix + ' ' + tail)
        self.assertEqual(chunks[:-2], self.chunks(prefix))
        self.assert_tokens(prefix + ' ' + tail, chunks)

    def test_numbers_and_technical_tokens_remain_whole(self):
        text = '현재 C2 버전 31.1의 메모리는 3.2GB이며 진행률 100%를 기록하고 자세한 결과를 확인합니다.'
        chunks = self.chunks(text)
        self.assert_tokens(text, chunks)
        for token in ('C2', '31.1의', '3.2GB이며', '100%를'):
            self.assertEqual(sum(token in chunk.split() for chunk in chunks), 1)

    def test_deterministic_corpus_preserves_order_and_bounds(self):
        # Vary token lengths and positions around target/minimum boundaries.
        for count in range(1, 60):
            words = [('가나다라마바사'[:1 + (i % 7)]) for i in range(count)]
            text = ' '.join(words) + '.'
            chunks = self.chunks(text)
            self.assert_tokens(text, chunks)
            self.assertTrue(all(len(chunk) <= 55 for chunk in chunks))
            if len(chunks) > 1:
                self.assertTrue(all(len(chunk) >= 20 for chunk in chunks))

    def test_oversized_unbroken_token_is_not_cut_by_rebalance(self):
        token = 'https://example.com/' + 'a' * 45
        text = '먼저 확인할 주소는 ' + token + ' 입니다.'
        self.assert_tokens(text, self.chunks(text))


if __name__ == '__main__':
    unittest.main()
