"""General UUID spoken structure, character names, and protected literals."""
import unittest
from test_education_2_7 import tn
from test_education_9 import notify


class UUIDReadingTests(unittest.TestCase):
    def test_user_reading(self):
        raw = '123e4567-e89b-12d3-a456-426614174000'
        expected = ('원 투 쓰리 이 포 파이브 식스 세븐, 대시, 이 에이트 나인 비, '
                    '대시, 원 투 디 쓰리, 대시, 에이 포 파이브 식스, 대시, '
                    '포 투 식스 식스 원 포 원 세븐 포 제로 제로 제로')
        self.assertEqual(tn.normalize('UUID '+raw), '유유아이디 '+expected)
        self.assertEqual(tn.normalize(raw.upper()), expected)
        self.assertEqual(tn.normalize(raw+'를 확인합니다.'), expected+'를 확인합니다.')

    def test_unseen_values_retain_every_group(self):
        for raw in ('00000000-0000-0000-0000-000000000000',
                    'fedcba98-7654-3210-abcd-ef0123456789',
                    'AbCd0123-4567-89aB-cDeF-9876543210ab'):
            reading = tn.normalize(raw)
            self.assertEqual(reading.count('대시'), 4)
            self.assertNotIn('총길이', reading)
            self.assertNotIn('시작하는 해시', reading)
            spoken_groups = reading.split(', 대시, ')
            self.assertEqual([len(group.split()) for group in spoken_groups], [8,4,4,4,12])

    def test_invalid_shapes_and_machine_boundaries(self):
        value = '123e4567-e89b-12d3-a456-426614174000'
        for raw in ('123e456-e89b-12d3-a456-426614174000',
                    '123g4567-e89b-12d3-a456-426614174000',
                    '123e4567-e89b-12d3-a456-42661417400',
                    '/tmp/'+value, 'https://example.com/'+value,
                    'file-'+value+'.txt', value+'@example.com',
                    'id_'+value, '--uuid='+value, 'UUID='+value,
                    '{"uuid":"'+value+'"}', '`'+value+'`'):
            self.assertEqual(tn.normalize(raw), raw)
        self.assertEqual(tn.normalize(notify.clean_text('`'+value+'`')), '`'+value+'`')
