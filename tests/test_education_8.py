# 작성자: 에닉(유키짱)
"""Function-word policy, unseen prose and machine boundaries."""
import json
import hashlib
import unittest
from pathlib import Path
from test_education_2_7 import tn

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / 'tests/fixtures/education-8.json').read_text())

class FunctionWordsTests(unittest.TestCase):
    def test_fixed_hundred(self):
        self.assertEqual(len(FIXTURE['cases']), 100)
        for raw, expected in FIXTURE['cases']:
            with self.subTest(raw=raw):
                self.assertEqual(tn.normalize(raw), expected)

    def test_source_immutable(self):
        source = Path('/home/ak/git/codex_enikk-education/8_tts-function-words-100.txt')
        if not source.exists():
            self.skipTest('external education corpus unavailable')
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), FIXTURE['_source_sha256'])
        self.assertEqual(source.read_text().splitlines(), [x[0] for x in FIXTURE['cases']])

    def test_thirty_unseen_sentences(self):
        # Explicit compositional anchors, not candidate-registry-generated answers.
        clauses = [
            ('I am here', '아이 앰 here'), ('We are here', '위 아 here'),
            ('You can do it', '유 캔 두 잇'), ('They will be here', '데이 윌 비 here'),
            ('She has it', '쉬 해즈 잇'), ('He had this', '히 해드 디스'),
            ('This is mine', '디스 이즈 마인'), ('That was yours', '댓 워즈 유어스'),
            ('These are ours', '디즈 아 아워스'), ('Those were his', '도즈 워 히즈'),
            ('Who did this', '후 디드 디스'), ('What does she have', '왓 더즈 쉬 해브'),
            ('When will they do it', '웬 윌 데이 두 잇'), ('Where should we be', '웨어 슈드 위 비'),
            ('If you can', '이프 유 캔'), ('Because we must', '비커즈 위 머스트'),
            ('Though he might', '도우 히 마이트'), ('While she could', '와일 쉬 쿠드'),
            ('Before and after', '비포 앤드 애프터'), ('Above or below', '어버브 오어 빌로'),
            ('Among us all', '어몽 어스 올'), ('Between you and me', '비트윈 유 앤드 미'),
            ('Without any', '위드아웃 애니'), ('During every', '듀어링 에브리'),
            ('Both of them', '보스 오브 뎀'), ('Neither of those', '니더 오브 도즈'),
            ('Either this or that', '이더 디스 오어 댓'), ('The node is on', '더 노드 이즈 온'),
            ('A wallet for her', 'A 월렛 포 허'), ('An address from him', '앤 어드레스 프롬 힘'),
        ]
        self.assertEqual(len(clauses), 30)
        for raw, expected in clauses:
            with self.subTest(raw=raw):
                self.assertEqual(tn.normalize(raw + '.'), expected + '.')

    def test_case_and_particles(self):
        for raw, expected in [('The', '더'), ('the', '더'), ('THE', 'THE'),
                              ('I', '아이'), ('i', '아이'), ('A', 'A'),
                              ('a', '어'), ('the는', '더는'), ('You에게', '유에게')]:
            self.assertEqual(tn.normalize(raw), expected)

    def test_all_word_literal_boundaries(self):
        for word, _ in FIXTURE['cases']:
            for template in ['https://example.org/{}', 'https://{}.example.org',
                             '{}@example.org', '/tmp/{}/config.txt', '{}.py',
                             'test_{}', '{}_test', 'test-{}', '--{}',
                             '`{}`', '```\n{}\n```', 'name={}', '{}123']:
                raw = template.format(word)
                with self.subTest(raw=raw):
                    self.assertEqual(tn.normalize(raw), raw)
        for raw in ['v1.5', '192.168.0.1', '`'+'a'*40+'`', '`'+'f'*64+'`', 'another', 'theory',
                    'android', 'island', 'mustard', 'inside']:
            self.assertEqual(tn.normalize(raw), raw)

# EOF
