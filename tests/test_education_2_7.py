# 작성자: 에닉(유키짱)
"""Fixed reading policy, unseen inputs, and machine-literal boundaries."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('education_tn', ROOT / 'tts/yuki-text-normalization.py')
tn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tn)
FIXTURES = json.loads((ROOT / 'tests/fixtures/education-2-7.json').read_text())


class EducationTests(unittest.TestCase):
    def test_six_fixed_corpora(self):
        for corpus in range(2, 8):
            cases = FIXTURES[str(corpus)]
            self.assertEqual(len(cases), 100)
            for raw, expected in cases:
                with self.subTest(corpus=corpus, raw=raw):
                    spoken = raw
                    if corpus == 7:
                        spoken, records = tn.overrides.normalize_paths(raw)
                        self.assertEqual(len(records), 1)
                        self.assertEqual(records[0]['original'], raw)
                        start, end = records[0]['span']
                        self.assertEqual(raw[start:end], records[0]['replaced_text'])
                    self.assertEqual(tn.normalize(spoken), expected)

    def test_twenty_unseen_plain_and_grouped_numbers(self):
        anchors = [
            ('42', '사십이'), ('-73', '마이너스 칠십삼'), ('+88', '플러스 팔십팔'),
            ('1234', '천이백삼십사'), ('5678', '오천육백칠십팔'),
            ('12345', '일만이천삼백사십오'), ('67890', '육만칠천팔백구십'),
            ('123456', '십이만삼천사백오십육'), ('654321', '육십오만사천삼백이십일'),
            ('7654321', '칠백육십오만사천삼백이십일'),
            ('100000000000000000', '십경'), ('100000000000000000000', '일해'),
            ('10000000000000000000000000', '십자'),
            ('42.031', '사십이 쩜 영 삼 일'), ('-73.007', '마이너스 칠십삼 쩜 영 영 칠'),
            ('+88.042', '플러스 팔십팔 쩜 영 사 이'),
            ('1234.56', '천이백삼십사 쩜 오 육'),
            ('5678.091', '오천육백칠십팔 쩜 영 구 일'),
            ('12345.006', '일만이천삼백사십오 쩜 영 영 육'),
            ('67890.0002', '육만칠천팔백구십 쩜 영 영 영 이'),
        ]
        for raw, expected in anchors:
            with self.subTest(raw=raw):
                self.assertEqual(tn.normalize(raw), expected)
        # Twenty distinct valid grouped forms, including signs and decimals.
        grouped = [
            ('1,234', '천이백삼십사'), ('-5,678', '마이너스 오천육백칠십팔'),
            ('+12,345', '플러스 일만이천삼백사십오'), ('67,890', '육만칠천팔백구십'),
            ('123,456', '십이만삼천사백오십육'), ('654,321', '육십오만사천삼백이십일'),
            ('7,654,321', '칠백육십오만사천삼백이십일'),
            ('100,000,000,000,000,000', '십경'),
            ('100,000,000,000,000,000,000', '일해'),
            ('10,000,000,000,000,000,000,000,000', '십자'),
            ('1,234.56', '천이백삼십사 쩜 오 육'),
            ('-5,678.091', '마이너스 오천육백칠십팔 쩜 영 구 일'),
            ('+12,345.006', '플러스 일만이천삼백사십오 쩜 영 영 육'),
            ('67,890.0002', '육만칠천팔백구십 쩜 영 영 영 이'),
            ('123,456.008', '십이만삼천사백오십육 쩜 영 영 팔'),
            ('654,321.0003', '육십오만사천삼백이십일 쩜 영 영 영 삼'),
            ('7,654,321.007', '칠백육십오만사천삼백이십일 쩜 영 영 칠'),
            ('-123,456.5', '마이너스 십이만삼천사백오십육 쩜 오'),
            ('+654,321.04', '플러스 육십오만사천삼백이십일 쩜 영 사'),
            ('-7,654,321.003', '마이너스 칠백육십오만사천삼백이십일 쩜 영 영 삼'),
        ]
        for raw, expected in grouped:
            with self.subTest(grouped=raw):
                self.assertEqual(tn.normalize(raw), expected)

    def test_twenty_unseen_prose_inputs_per_lexical_domain(self):
        # Independent literal word anchors in contexts absent from training.
        domains = [
            [('wallet', '월렛'), ('node', '노드'), ('peer', '피어'), ('key', '키'),
             ('transaction', '트랜잭션'), ('hash', '해시'), ('chain', '체인'),
             ('script', '스크립트'), ('address', '어드레스'), ('mempool', '멤풀')],
            [('git', '깃'), ('clone', '클론'), ('merge', '머지'), ('rebase', '리베이스'),
             ('checkout', '체크아웃'), ('commit', '커밋'), ('push', '푸시'),
             ('fetch', '페치'), ('review', '리뷰'), ('worktree', '워크트리')],
            [('ls', '엘에스'), ('cd', '씨디'), ('pwd', '피더블유디'), ('cp', '씨피'),
             ('mv', '엠브이'), ('rm', '알엠'), ('grep', '그렙'), ('find', '파인드'),
             ('systemctl', '시스템씨티엘'), ('bash', '배시')],
        ]
        for domain in domains:
            for raw, expected in domain:
                for template in ('오늘 {} 내용을 확인해.', '{} 작업을 다시 살펴봐.'):
                    with self.subTest(raw=raw, template=template):
                        self.assertEqual(tn.normalize(template.format(raw)), template.format(expected))
        plurals = [('wallets', '월렛스'), ('nodes', '노드스'), ('mempools', '멤풀스'),
                   ('pubkeys', '퍼브키스'), ('branches', '브랜치스'), ('patches', '패치스')]
        for raw, expected in plurals:
            self.assertEqual(tn.normalize(raw), expected)
        # Unknown compounds remain identifiers, rather than becoming a new dictionary.
        self.assertEqual(tn.normalize('wallet-cache branch-name'), 'wallet-cache branch-name')
        for raw, expected in [('wallet은', '월렛은'), ('node를', '노드를'),
                              ('commit에서', '커밋에서'), ('git에서는', '깃에서는'),
                              ('systemctl로', '시스템씨티엘로'), ('HEAD는', '헤드는')]:
            self.assertEqual(tn.normalize(raw), expected)
        for raw in ['wallet은.txt', 'commit에서_id', '`HEAD는`', 'wallet그래프']:
            self.assertEqual(tn.normalize(raw), raw)

    def test_twenty_unseen_project_path_combinations(self):
        prefixes = [('/tmp/sugarchain/', '루트 디렉터리 아래 티엠피 아래 슈가체인'),
                    ('~/.bitcoin/', '홈 디렉터리 아래 숨김 비트코인'),
                    ('../bitcoin/', '상위 디렉터리 아래 비트코인'),
                    ('../../sugarchain/', '상위 디렉터리 아래 상위 디렉터리 아래 슈가체인')]
        endings = [('wallet_v2.7.json', '월렛 버전 이 쩜 칠 제이슨 파일'),
                   ('node_v4.9.py', '노드 버전 사 쩜 구 파이썬 파일'),
                   ('README.md', '리드미 마크다운 파일'), ('cache.dat', '캐시 데이터 파일'),
                   ('../config.conf', '상위 디렉터리 아래 컨피그 설정 파일')]
        for prefix, prefix_read in prefixes:
            for tail, tail_read in endings:
                raw = prefix + tail
                expected = prefix_read + ' 아래 ' + tail_read + ' 경로'
                with self.subTest(path=raw):
                    spoken, records = tn.overrides.normalize_paths(raw)
                    self.assertEqual(tn.normalize(spoken), expected)
                    self.assertEqual(records[0]['original'], raw)
        self.assertNotEqual(tn.overrides.normalize_paths('../bitcoin/wallet')[0],
                            tn.overrides.normalize_paths('../../bitcoin/wallet')[0])
        for name, reading in [('Enikk', '에닉'), ('Yuki', '유키')]:
            self.assertEqual(tn.overrides.normalize_paths('~/bitcoin/' + name + '.py')[0],
                             '홈 디렉터리 아래 비트코인 아래 ' + reading + ' 파이썬 파일 경로')
        self.assertIn('버전 이 쩜 영 영 칠',
                      tn.overrides.normalize_paths('~/bitcoin/wallet_v2.007.json')[0])

    def test_boundary_literals(self):
        fixed = ['v1.5', '192.168.0.1', '--limit=1234', '007', '1,23', '01,234',
                 'wallet.txt', 'node_v3.py', '/path/1234/test', '/tmp/wallet',
                 'https://example.com/?amount=1234', 'wallet@example.com',
                 'wallet_name', 'prefix-wallet', 'feature/wallet', 'wallet(node)',
                 'wallet=main', 'PATH', 'WALLET', '1'*40, '9'*64,
                 '`'+'1234567890abcdef'*4+'`', '`branch Python 123`',
                 '```bash\ngit log --oneline\n```', '`wallet', 'v2.3.4.json']
        for raw in fixed:
            with self.subTest(raw=raw):
                self.assertEqual(tn.normalize(raw), raw)
        for word in ['wallet', 'git', 'merge', 'node', 'bash', 'ls', 'scriptSig']:
            for template in ['{0}_id', 'prefix_{0}', '{0}.txt', '/tmp/{0}',
                             'https://example.com/{0}', '{0}@example.com',
                             '--{0}=main', '`{0}`', '{0}(x)', '{0}2']:
                raw = template.format(word)
                self.assertEqual(tn.normalize(raw), raw)
        for raw in ['https://example.com/?path=/home/test-user/git/sugarchain/src',
                    'https://example.com/?path=~/.bitcoin/blocks',
                    'user@example.com/home/test-user/git/sugarchain/src']:
            self.assertEqual(tn.overrides.normalize_paths(raw), (raw, []))

    def test_bounds_and_path_machine_identifier(self):
        with self.assertRaises(ValueError):
            tn.overrides.korean_cardinal(10**32)
        self.assertEqual(tn.normalize('1' * 33), '1' * 33)
        self.assertEqual(tn.normalize('1' * 33 + ' GB'), '1' * 33 + ' GB')
        self.assertEqual(tn.normalize('용량 ' + '1' * 33 + ' GB'), '용량 ' + '1' * 33 + ' GB')
        version = '~/bitcoin/wallet_v' + '1' * 33 + '.json'
        self.assertIn('버전 식별자', tn.overrides.normalize_paths(version)[0])
        raw = '~/bitcoin/' + 'a3'*32 + '.dat'
        spoken, records = tn.overrides.normalize_paths(raw)
        self.assertIn('식별자 데이터 파일', spoken)
        self.assertNotIn('a3', spoken)
        self.assertEqual(records[0]['original'], raw)
        self.assertLessEqual(tn.overrides.path_component.cache_info().maxsize, 256)

    def test_custom_only_shortcut_preserves_existing_identity_semantics(self):
        for text in ['일반', '수 있지만', '할 수 있어', '수 없으면', '작은 일부터',
                     '수 초가 걸린다.', '한 시간', '1시간 제한', '12시 12분',
                     '완전히 한국어인 긴 문장을 그대로 읽으며 숫자나 기술어를 추가하지 않는다.',
                     '루트 디렉터리 아래 슈가체인 아래 월렛 디렉터리 경로',
                     '`Python branch` wallet', '1234', '8 GB', 'Yuki Enikk']:
            self.assertEqual(tn.normalize(text),
                             tn.overrides.normalize_with_exceptions(text, lambda value: value))

    def test_injected_custom_module_keeps_callback_contract(self):
        class LegacyCustom:
            def normalize_with_exceptions(self, text, callback):
                return callback(text) + ' 사용자 규칙'
        self.assertEqual(tn.Client(custom=LegacyCustom()).normalize('문장'), '문장 사용자 규칙')

    def test_proper_names_respect_literal_boundaries(self):
        self.assertEqual(tn.normalize('Yuki Enikk Sugarchain.'), '유키 에닉 슈가체인.')
        for name in ['Yuki', 'Enikk', 'Sugarchain']:
            for template in ['https://{0}.example.com/{0}', '{0}@example.com',
                             'prefix_{0}', '{0}2', '{0}.py', '/tmp/{0}',
                             '--name={0}', '`{0}`', 'func({0})']:
                raw = template.format(name)
                self.assertEqual(tn.normalize(raw), raw)


if __name__ == '__main__':
    unittest.main()
# EOF
