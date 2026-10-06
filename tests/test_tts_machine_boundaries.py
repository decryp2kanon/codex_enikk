"""End-to-end clean_text -> path -> prose protection, not just raw tokens."""
import unittest
from test_education_2_7 import tn
from test_education_9 import notify


def spoken(raw):
    cleaned = notify.clean_text(raw)
    paths = tn.overrides.normalize_paths(cleaned)[0]
    return tn.normalize(paths)


class MachineBoundaryTests(unittest.TestCase):
    def test_space_bearing_assignments_and_commands(self):
        values = ('commit deadbeef12', 'URL UUID', '/tmp/report_v12.6.md',
                  '10ms~20ms completed이며', 'foo__bar **wallet**',
                  '987/1,000 model_ready=true')
        for value in values:
            for raw in ('DATA="'+value+'"', "DATA='"+value+"'", '`git '+value+'`'):
                with self.subTest(raw=raw):
                    self.assertEqual(spoken('확인 '+raw+' 유지.'), '확인 '+raw+' 유지.')

    def test_json_whitespace_nested_and_markdown_values(self):
        for raw in ('{ "op": ">=", "value": "commit deadbeef12" }',
                    '{"outer": {"path": "/tmp/report_v12.6.md", "text": "**wallet**"}}',
                    '[ {"word": "URL UUID"}, "10ms~20ms" ]',
                    '{"value": "<span>completed</span>"}',
                    '{"word": "completed이며", "bad": 10ms}',
                    '{"unfinished": "commit deadbeef12'):
            with self.subTest(raw=raw):
                self.assertEqual(spoken('확인 '+raw), '확인 '+raw)

    def test_literal_spaces_escape_and_addresses_survive_cleanup(self):
        for raw in ('DATA="a  b\\\" URL"', '`printf "a  b"`',
                    'https://example.com/**wallet**?id=foo__bar',
                    '/tmp/foo__bar/report_v12.6.md', 'x+URL@example.com',
                    'foo__wallet__bar'):
            with self.subTest(raw=raw):
                self.assertEqual(notify.clean_text(raw), raw)

    def test_fences_hidden_and_inline_display_word_compatibility(self):
        for fence in ('```', '~~~'):
            for closed in (True, False):
                raw = fence+'text\n# commit deadbeef12\n/tmp/report_v12.6.md\n'
                if closed:
                    raw += fence
                self.assertEqual(notify.clean_text(raw), '')
                self.assertEqual(tn.normalize(raw), raw)
        self.assertEqual(spoken('`wallet`'), '월렛')
        self.assertIn('총길이 팔 글자', spoken('commit `abc12345`'))
        self.assertEqual(notify.clean_text('[설명 문서](https://example.com/a.b)를 확인.'),
                         '설명 문서를 확인.')

    def test_machine_path_records_are_not_prose(self):
        for raw in ('`cat /tmp/report_v12.6.md`', '{"path": "/tmp/report_v12.6.md"}',
                    'DATA="/tmp/report_v12.6.md and URL"',
                    '```sh\ncat /tmp/report_v12.6.md\n```'):
            self.assertEqual(tn.overrides.normalize_paths(raw), (raw, []))

    def test_general_versioned_filenames_and_original_offsets(self):
        cases = {
            'report_v72.8.md': '리포트 버전 칠십이 점 팔 마크다운 파일',
            'summary_v7.2.8.json': '서머리 버전 칠 점 이 점 팔 제이슨 파일',
            'release_v12.6.txt': '릴리스 버전 십이 점 육 텍스트 파일',
            'wallet_v3.0.cpp': '월렛 버전 삼 점 영 씨 플러스 플러스 소스 파일',
            'report_v01.02.md': '리포트 버전 영 일 점 영 이 마크다운 파일',
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                result, records = tn.overrides.normalize_paths(raw+'를 확인.')
                self.assertEqual(result, expected+'을 확인.')
                self.assertEqual(raw+'를', records[0]['replaced_text'])
                self.assertEqual((raw+'를 확인.')[slice(*records[0]['span'])], records[0]['replaced_text'])
        for raw in ('unknown_v12.6.md', 'x@report_v72.8.md',
                    'https://example.com/report_v72.8.md', '--report_v72.8.md',
                    'x=report_v72.8.md', 'report_v12.6.md_id'):
            self.assertEqual(tn.overrides.normalize_paths(raw), (raw, []))
