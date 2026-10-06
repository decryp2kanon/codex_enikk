"""Mixed Korean prose quantities and protected technical literal boundaries."""
import unittest
from test_education_2_7 import tn


class MixedProseTests(unittest.TestCase):
    def test_middle_dot_lists_are_lexical_prose_not_machine_paths(self):
        self.assertEqual(tn.normalize('코드 블록·명령어·URL·경로 보호는 유지한다.'),
                         '코드 블록·명령어·유알엘·경로 보호는 유지한다.')
        self.assertEqual(tn.normalize('response_item·tool_call·tool_result'),
                         '리스폰스 아이템·툴 콜·툴 리절트')
        for raw in ('`URL·UUID`', '/tmp/URL·UUID', 'https://example.com/URL·UUID',
                    'URL·UUID.txt', 'x=URL·UUID'):
            self.assertEqual(tn.normalize(raw), raw)

    def test_url_uuid_names_without_changing_machine_boundaries(self):
        self.assertEqual(tn.normalize('URL과 UUID는'), '유알엘과 유유아이디는')
        for raw in ('https://example.com/4acb675fbe30',
                    '`URL UUID`', 'UUID_id'):
            self.assertEqual(tn.normalize(raw), raw)

    def test_numeric_ratios_and_protected_boundaries(self):
        self.assertEqual(tn.normalize('987/1,000이며'), '천 분의 구백팔십칠이며')
        self.assertEqual(tn.normalize('123/2,000이면'), '이천 분의 백이십삼이면')
        for raw in ('/tmp/987/1,000', '`987/1,000`', 'https://example.com/987/1,000',
                    'count=987/1,000', '987/0'):
            self.assertEqual(tn.normalize(raw), raw)

    def test_counts_and_rates(self):
        cases = {
            '1,000개 중 987개': '천 개 중 구백팔십칠 개',
            '2,451/s에서 3,200/s로': '이천사백오십일 퍼 세컨드에서 삼천이백 퍼 세컨드로',
            '1,234개 중 876개': '천이백삼십사 개 중 팔백칠십육 개',
        }
        for raw, expected in cases.items():
            self.assertEqual(tn.normalize(raw), expected)

    def test_ranges_with_counters_units_and_markdown_escape(self):
        cases = {
            r'0\~2회': '영에서 이 회', '2~5초': '이에서 오 초',
            '10~20개의': '십에서 이십 개의',
            '4GB~16GB': '사 기가바이트에서 십육 기가바이트',
            '100ms~500ms': '백 밀리세컨드에서 오백 밀리세컨드',
            '10~20%': '십에서 이십 퍼센트',
            '3,000~4,000개': '삼천에서 사천 개',
            r'2\~5초입니다.': '이에서 오 초입니다.',
            r'3\~7회였습니다.': '삼에서 칠 회였습니다.',
            r'2,451/s\~3,200/s이고': '이천사백오십일 퍼 세컨드에서 삼천이백 퍼 세컨드이고',
            r'&#32;1\.8\~2.5초면': '일 쩜 팔에서 이 쩜 오 초면',
            r'10\~20%라면': '십에서 이십 퍼센트라면',
            r'9\.5\~12.5%일': '구 쩜 오에서 십이 쩜 오 퍼센트일',
        }
        for raw, expected in cases.items():
            self.assertEqual(tn.normalize(raw), expected)

    def test_sha_algorithm_labels_and_boundaries(self):
        for raw, expected in (('SHA-256', '에스 에이치 에이 이백오십육'),
                              ('SHA512', '에스 에이치 에이 오백십이'),
                              ('SHA-384에도', '에스 에이치 에이 삼백팔십사에도'),
                              ('sha-384를', '에스 에이치 에이 삼백팔십사를')):
            self.assertEqual(tn.normalize(raw), expected)
        for raw in ('`SHA-256`', '/tmp/SHA-256', 'https://example.com/SHA-256',
                    'SHA-256_id', '--SHA-256'):
            self.assertEqual(tn.normalize(raw), raw)

    def test_registered_lexical_words_with_common_endings(self):
        self.assertEqual(tn.normalize('completed이며 ready이면'),
                         '컴플리티드이며 레디이면')
        for raw in ('`completed이며`', 'completed이며_id', '/tmp/completed이며',
                    'https://example.com/completed이며', '--completed이며'):
            self.assertEqual(tn.normalize(raw), raw)

    def test_registered_words_with_productive_korean_verb_endings(self):
        for ending in ('하며', '하고', '하면', '하는', '합니다', '했으며', '해서'):
            self.assertEqual(tn.normalize('merge'+ending), '머지'+ending)
        for raw in ('`merge하며`', 'merge하며_id', '/tmp/merge하며',
                    '--merge하며', 'https://example.com/merge하며', 'unknown하며'):
            self.assertEqual(tn.normalize(raw), raw)

    def test_pr_and_issue_references_only_in_adjacent_context(self):
        self.assertEqual(tn.normalize(r'PR \#225에서'), 'PR 이백이십오 번에서')
        self.assertEqual(tn.normalize('issue #317을'), '이슈 삼백십칠 번을')
        for raw in ('color #225', '/tmp/#225', '`PR #225`',
                    'https://example.com/#225', 'PR completed #225'):
            self.assertEqual(tn.normalize(raw), raw if raw != 'PR completed #225'
                             else 'PR 컴플리티드 #225')

    def test_entities_only_at_prose_token_start(self):
        self.assertEqual(tn.normalize('&#32;commit abc1234'),
                         tn.normalize('commit abc1234'))
        for raw in ('https://example.com/?a=&#32;', '`&#32;commit abc1234`',
                    '/tmp/100ms~500ms', 'file-987개.dat', 'id_0~2회',
                    'v1.2.3', '--timeout=100ms~500ms', 'x=10~20%'):
            self.assertEqual(tn.normalize(raw), raw)
