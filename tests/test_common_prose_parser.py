"""Deterministic grammar matrix with expected readings independent of parser.

This checks families of values/units/endings, not just USER failure examples.
Holdout numbers and combinations are separate from the development matrix.
"""
import random
import unittest
from test_education_2_7 import tn


VALUES = (
    ('0', '영'), ('2', '이'), ('7', '칠'), ('12', '십이'),
    ('25', '이십오'), ('40', '사십'), ('72', '칠십이'), ('99', '구십구'),
    ('100', '백'), ('225', '이백이십오'), ('500', '오백'), ('750', '칠백오십'),
    ('1,000', '천'), ('3,200', '삼천이백'), ('1.8', '일 쩜 팔'), ('9.5', '구 쩜 오'),
)
UNITS = (
    ('ms', '밀리세컨드'), ('GB', '기가바이트'), ('MB/s', '메가바이트 퍼 세컨드'),
    ('kb/s', '킬로비트 퍼 세컨드'), ('kB', '킬로바이트'), ('Hz', '헤르츠'),
    ('GHz', '기가헤르츠'), ('%', '퍼센트'), ('/s', '퍼 세컨드'), ('개', '개'),
)
ENDINGS = ('', '에서', '이며', '이면')
HOLDOUT_VALUES = (
    ('37', '삼십칠'), ('83', '팔십삼'), ('146', '백사십육'),
    ('684', '육백팔십사'), ('2,730', '이천칠백삼십'),
    ('6,508', '육천오백팔'), ('3.75', '삼 쩜 칠 오'), ('21.6', '이십일 쩜 육'),
)
LEXICAL = (('completed', '컴플리티드'), ('ready', '레디'),
           ('merge', '머지'), ('URL', '유알엘'), ('UUID', '유유아이디'),
           ('tool_result', '툴 리절트'))
HEX_NAMES = dict(zip('0123456789abcdef',
    ('제로', '원', '투', '쓰리', '포', '파이브', '식스', '세븐', '에이트', '나인',
     '에이', '비', '씨', '디', '이', '에프')))


def development_cases():
    for value, spoken in VALUES:
        for unit, unit_spoken in UNITS:
            for ending in ENDINGS:
                yield '값 ' + value + unit + ending + '.', '값 ' + spoken + ' ' + unit_spoken + ending + '.'
    for word, spoken in LEXICAL:
        for ending in ('은', '는', '을', '를', '에서', '이며', '이면', '입니다'):
            yield '상태 ' + word + ending + '.', '상태 ' + spoken + ending + '.'
    for value, spoken in VALUES:
        for unit, unit_spoken in UNITS[:8]:
            yield '값 ' + value + ' ' + unit + '이며.', '값 ' + spoken + ' ' + unit_spoken + '이며.'


def holdout_cases():
    # Freeze a deterministic unseen set; expectations use hand-written readings.
    rng = random.Random(20261007)
    combinations = [(a, b, unit, ending) for a in HOLDOUT_VALUES
                    for b in HOLDOUT_VALUES if a != b
                    for unit in UNITS[:8] for ending in ('에도', '입니다', '라면')]
    rng.shuffle(combinations)
    for (left, left_spoken), (right, right_spoken), (unit, unit_spoken), ending in combinations[:100]:
        raw = '값 ' + left + unit + '~' + right + unit + ending + '.'
        expected = '값 ' + left_spoken + ' ' + unit_spoken + '에서 ' + right_spoken + ' ' + unit_spoken + ending + '.'
        yield raw, expected


class CommonProseParserTests(unittest.TestCase):
    def test_development_matrix(self):
        cases = list(development_cases())
        self.assertGreaterEqual(len(cases), 600)
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(tn.normalize(raw), expected)

    def test_holdout_matrix(self):
        cases = list(holdout_cases())
        self.assertEqual(len(cases), 100)
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(tn.normalize(raw), expected)

    def test_machine_containers_and_maximal_boundaries(self):
        values = ('7ms', '1,000개', '10~20%', 'completed이며', 'URL',
                  'deadbeef12345678', '123e4567-e89b-12d3-a456-426614174000')
        templates = ('`{v}`', '/tmp/{v}', 'https://example.com/{v}',
                     '--value={v}', 'value={v}', 'id_{v}', 'file-{v}.dat',
                     '{{"literal": "{v}", "nested": {{"value": "commit deadbeef"}}}}')
        for value in values:
            for template in templates:
                raw = '확인 ' + template.format(v=value) + ' 유지.'
                with self.subTest(raw=raw):
                    self.assertEqual(tn.normalize(raw), raw)

    def test_context_and_unknown_suffix_do_not_leak(self):
        for raw in ('commit 완료 deadbeef12', 'commit\ndeadbeef12',
                    'ready임의꼬리', '10ms임의꼬리', 'merge임의꼬리',
                    'hash deadbeef12_id', 'PR 완료 #789',
                    '확인 {"operator": ">=", "text": "URL UUID"} 유지.'):
            with self.subTest(raw=raw):
                expected = raw
                if raw.startswith('commit'):
                    expected = raw.replace('commit', '커밋', 1)
                elif raw.startswith('hash '):
                    expected = raw.replace('hash', '해시', 1)
                self.assertEqual(tn.normalize(raw), expected)

    def test_fenced_heading_and_duration_stay_opaque(self):
        for raw in ('```text\n# commit deadbeef12\n1시간\n```',
                    '{"duration": "1시간", "text": "URL UUID"}',
                    '`1시간 commit deadbeef12`'):
            self.assertEqual(tn.normalize(raw), raw)

    def test_unseen_hash_and_uuid_compositions(self):
        rng = random.Random(711036)
        length_readings = {7: '칠', 8: '팔', 10: '십', 16: '십육', 31: '삼십일',
                           32: '삼십이', 40: '사십', 64: '육십사'}
        for length, length_spoken in length_readings.items():
            value = 'a' + ''.join(rng.choice('0123456789abcdef') for _ in range(length-1))
            prefix = value[:7]
            particle = '으로' if prefix[-1] in '17' else '로'
            expected = '커밋 ' + ' '.join(HEX_NAMES[c] for c in prefix) + particle + ' 시작하는 해시고 총길이 ' + length_spoken + ' 글자이며'
            self.assertEqual(tn.normalize('commit ' + value + '이며'), expected)
        for _ in range(20):
            groups = [''.join(rng.choice('0123456789abcdef') for _ in range(n)) for n in (8,4,4,4,12)]
            raw = '-'.join(groups)
            expected = ', 대시, '.join(' '.join(HEX_NAMES[c] for c in group) for group in groups)
            self.assertEqual(tn.normalize('값 ' + raw + '이며'), '값 ' + expected + '이며')
