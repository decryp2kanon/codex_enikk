"""Bounded experimental first phrases preserve prose and protected sources."""
import unittest
from test_tts_delivery import definitions

class ShortPhraseTests(unittest.TestCase):
    def setUp(self):
        self.split = definitions()['speech_chunks']

    def test_first_phrase_and_all_text_preserved(self):
        for prefix in ['현재 시스템', '현재 서비스', '지금 상태는', '오늘 결과를', '이번 작업은',
                       '먼저 상태를', '다음 요청을', '지금 내용을', '오늘 변경을', '현재 작업은',
                       '이제 결과를', '먼저 내용을', '지금 변경을', '이번 결과는', '오늘 작업은',
                       '다음 작업을', '현재 결과는', '이제 상태를', '먼저 결과를', '이번 변경은']:
            raw=prefix+' 확인하고 다음 요청을 순서대로 진행하겠습니다.'
            with self.subTest(raw=raw):
                parts=self.split(raw, first_target=8, source_text=raw)
                self.assertEqual(parts[0],prefix)
                self.assertEqual(' '.join(parts),raw)
                self.assertGreaterEqual(len(parts[0]),6)
                self.assertLessEqual(len(parts[0]),10)

    def test_raw_machine_and_technical_prefix_are_not_split_early(self):
        spoken='커밋 포 에이 씨 비 식스 세븐 파이브로 시작하는 해시고 총길이 사십 글자'
        for raw in ['commit abcdef1234567890 completed', 'UUID 123e4567-e89b-12d3-a456-426614174000',
                    '100 kb/s 처리량을 확인합니다.', '/tmp/test.py 파일을 확인합니다.',
                    'https://example.com 상태를 확인합니다.', '`commit deadbeef` 결과를 확인합니다.',
                    'SHA-256 abcdef1234567890 verified']:
            self.assertEqual(self.split(spoken,first_target=8,source_text=raw),self.split(spoken))

    def test_no_tiny_greeting_or_split_word_or_short_remainder(self):
        for raw in ['네 다음 작업을 확인합니다.', '좋아 다음 작업을 확인합니다.',
                    '긴단어하나만으로는 안전하게 짧은 첫 구절을 만들 수 없습니다.',
                    '현재 시스템 상태는 정상입니다.']:
            parts=self.split(raw,first_target=8,source_text=raw)
            self.assertEqual(' '.join(parts),raw)
            self.assertNotEqual(parts[0],'네')
            self.assertNotEqual(parts[0],'좋아')

    def test_later_chunks_unchanged(self):
        raw='현재 시스템 상태는 정상이며 다음 작업을 계속 진행합니다. '+'기존 문장과 나머지 요청은 순서대로 보존되어야 합니다. '*3
        original=self.split(raw)
        candidate=self.split(raw,first_target=8,source_text=raw)
        self.assertEqual(' '.join(candidate), ' '.join(original))
        # Only the first preexisting chunk is replaced; later scheduling stays.
        # The original first connective split can yield a different prefix.
        self.assertEqual(candidate[-2:],original[-2:])

    def test_transformed_hash_characters_cannot_complete_short_phrase(self):
        spoken='이 해시는 포 에이 씨 비 식스 세븐 파이브로 시작하는 해시고 총길이 사십 글자'
        raw='이 해시는 4acb675fbe30fe1f99e0e4c1a6b4ea45ba62d29f입니다.'
        self.assertEqual(self.split(spoken,first_target=8,source_text=raw),self.split(spoken))

    def test_longer_candidate_keeps_a_complete_phrase(self):
        raw='현재 시스템 상태는 정상이며 다음 작업을 계속 진행합니다.'
        self.assertEqual(self.split(raw,first_target=12,source_text=raw)[0],'현재 시스템 상태는')
        raw='현재 작업 결과를 먼저 확인하고 다음 요청을 순서대로 진행하겠습니다.'
        self.assertEqual(self.split(raw,first_target=12,source_text=raw)[0],'현재 작업 결과를 먼저')
        for target in (8,12,16):
            parts=self.split(raw,first_target=target,source_text=raw)
            self.assertEqual(' '.join(parts),raw)

    def test_conservative_candidate_reaches_five_word_clause(self):
        raw='현재 작업 결과를 먼저 확인하고 해시와 숫자 및 경로의 처리 상태를 비교한 뒤 다음 요청을 순서대로 진행하겠습니다.'
        parts=self.split(raw,first_target=16,source_text=raw)
        self.assertEqual(parts[0],'현재 작업 결과를 먼저 확인하고')
        self.assertEqual(' '.join(parts),raw)
        raw='현재 시스템 상태는 정상이며 다음 작업을 계속 진행합니다.'
        self.assertEqual(self.split(raw,first_target=16,source_text=raw),self.split(raw))

    def test_reallocation_keeps_first_phrase_and_all_words(self):
        raw='현재 작업 결과를 먼저 확인하고 해시와 숫자 및 경로의 처리 상태를 비교한 뒤 다음 요청을 순서대로 진행하겠습니다.'
        parts=self.split(raw,first_target=16,source_text=raw,remainder_target=25)
        self.assertEqual(list(map(len,parts)),[17,25,20])
        self.assertEqual(' '.join(parts),raw)
        combined=self.split(raw,first_target=16,source_text=raw,remainder_target=55)
        self.assertEqual(list(map(len,combined)),[17,46])
        self.assertEqual(' '.join(combined),raw)

    def test_reallocation_only_changes_eligible_prose(self):
        for raw in ['현재 시스템 상태는 정상이며 다음 작업을 계속 진행합니다.',
                    'commit abcdef1234567890 completed',
                    '/tmp/test.py 파일을 확인하고 다음 요청을 진행합니다.']:
            self.assertEqual(self.split(raw,first_target=16,source_text=raw,remainder_target=25),
                             self.split(raw,first_target=16,source_text=raw))

    def test_reallocation_preserves_tokens_and_bounded_chunks(self):
        raw='현재 작업 결과를 먼저 확인하고 '
        raw += '다음 요청에서 abcdef1234567890 /tmp/test.py 123e4567-e89b-12d3-a456-426614174000 상태를 확인합니다. '*4
        for target in (25,55):
            parts=self.split(raw,first_target=16,source_text=raw,remainder_target=target)
            self.assertEqual(' '.join(parts),' '.join(raw.split()))
            self.assertTrue(all(len(part)<=55 for part in parts))
            self.assertEqual(parts[0],'현재 작업 결과를 먼저 확인하고')
