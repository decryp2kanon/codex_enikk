# 작성자: 에닉(유키짱)
"""Dynamic hash grammar, adjacent anchors and preserved machine boundaries."""
import unittest
from test_education_2_7 import tn
from test_education_9 import notify


class HashReadingTests(unittest.TestCase):
    def test_independent_readings(self):
        cases = [
            ('commit 5f61d98a', '커밋 파이브 에프 식스 원 디 나인 에이트로 시작하는 해시고 총길이 팔 글자'),
            ('hash deadbeef12', '해시 디 이 에이 디 비 이 이로 시작하는 해시고 총길이 십 글자'),
            ('release a1b2c3d4e5', '릴리스 에이 원 비 투 씨 쓰리 디로 시작하는 해시고 총길이 십 글자'),
            ('commit hash 4acb675fbe30', '커밋 해시 포 에이 씨 비 식스 세븐 파이브로 시작하는 해시고 총길이 십이 글자'),
            ('0123456789abcdef0123456789abcdef', '제로 원 투 쓰리 포 파이브 식스로 시작하는 해시고 총길이 삼십이 글자'),
            ('4acb675fbe30fe1f99e0e4c1a6b4ea45ba62d29f', '포 에이 씨 비 식스 세븐 파이브로 시작하는 해시고 총길이 사십 글자'),
            ('ABCDEFabcdef1234567890'*3, '에이 비 씨 디 이 에프 에이로 시작하는 해시고 총길이 육십육 글자'),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                self.assertEqual(tn.normalize(raw), expected)

    def test_unseen_lengths_and_case(self):
        lengths = [(8,'팔'),(10,'십'),(12,'십이'),(16,'십육'),(20,'이십'),
                   (31,'삼십일'),(32,'삼십이'),(40,'사십'),(64,'육십사'),(77,'칠십칠')]
        for size, reading in lengths:
            value = ('aBcD091e'*10)[:size]
            expected = '에이 비 씨 디 제로 나인 원으로 시작하는 해시고 총길이 '+reading+' 글자'
            with self.subTest(size=size):
                self.assertEqual(tn.normalize('hash '+value), '해시 '+expected)
                self.assertEqual(tn.normalize(value), expected if size >= 32 else value)

    def test_anchor_scope(self):
        for anchor in ('hash','commit','SHA','SHA1','SHA-1','SHA256','SHA-256',
                       'digest','checksum','release','revision','rev','COMMIT',
                       'commit hash','release hash','SHA hash','checksum hash'):
            self.assertIn('총길이 십 글자', tn.normalize(anchor+' deadbeef12'))
        for raw in ('release candidate is ready and cafe1234 is selected',
                    'commit completed and deadbeef is a project name',
                    'commit\ndeadbeef12','hash\rdeadbeef12','myhash deadbeef12',
                    'hash=deadbeef12','hash: deadbeef12'):
            with self.subTest(raw=raw):
                self.assertNotIn('로 시작하는 해시',tn.normalize(raw))
        self.assertIn('총길이 십 글자!', tn.normalize('hash deadbeef12!'))

    def test_machine_boundaries(self):
        value = '4acb675fbe30fe1f99e0e4c1a6b4ea45ba62d29f'
        for raw in ('deadbeef','cafe1234','abcdef12',
                    '9'*64,'ff0000','abcdef','v4.10.12','192.168.0.1','::1',
                    '01234567-89ab-cdef-0123-456789abcdef'):
            self.assertEqual(tn.normalize(raw),raw)
        self.assertEqual(tn.normalize('12345678'),'천이백삼십사만오천육백칠십팔')
        self.assertEqual(tn.normalize('20261007'),'이천이십육만천칠')
        for template in ('https://example.com/{}','{}@example.com','/tmp/{}/file',
                         'file-{}.dat','--hash={}','`{}`','```\n{}\n```',
                         'HASH={}','{{"hash": "{}"}}','#{0}','prefix_{0}',
                         '{0}_id','prefix-{0}','{0}-suffix','{0}Z','Z{0}'):
            raw=template.format(value)
            with self.subTest(raw=raw):
                self.assertEqual(tn.normalize(raw),raw)

    def test_notify_preserves_hash_code_before_normalization(self):
        value='4acb675fbe30fe1f99e0e4c1a6b4ea45ba62d29f'
        for raw in ('`'+value+'`','`commit '+value+'`','`hash deadbeef12`'):
            cleaned=notify.clean_text(raw)
            self.assertEqual(cleaned,raw)
            self.assertEqual(tn.normalize(cleaned),raw)
        self.assertEqual(notify.clean_text('`wallet`'),'wallet')
        self.assertEqual(notify.clean_text('```\n'+value+'\n```'),'')

# EOF
