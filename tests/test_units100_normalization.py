import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'tts/yuki-text-normalization.py'
spec = importlib.util.spec_from_file_location('units100_tn', SOURCE)
tn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tn)

# Literal expected strings from the immutable education A table.
EXPECTED = [
    ('100 kb/s', '백 킬로비트 퍼 세컨드'),
    ('1000 ms', '천 밀리세컨드'),
    ('225 block/s', '이백이십오 블록 퍼 세컨드'),
    ('50 MB/s', '오십 메가바이트 퍼 세컨드'),
    ('1.5 GB/s', '일 쩜 오 기가바이트 퍼 세컨드'),
    ('250 Mbps', '이백오십 메가비트 퍼 세컨드'),
    ('1 Gbps', '일 기가비트 퍼 세컨드'),
    ('32 kB', '삼십이 킬로바이트'),
    ('64 KB', '육십사 킬로바이트'),
    ('128 MB', '백이십팔 메가바이트'),
    ('8 GB', '팔 기가바이트'),
    ('16 GiB', '십육 기비바이트'),
    ('500 µs', '오백 마이크로세컨드'),
    ('2 s', '이 초'),
    ('30 sec', '삼십 세컨드'),
    ('5 min', '오 분'),
    ('2 h', '이 시간'),
    ('24 hr', '이십사 아워'),
    ('60 Hz', '육십 헤르츠'),
    ('144 Hz', '백사십사 헤르츠'),
    ('3.2 GHz', '삼 쩜 이 기가헤르츠'),
    ('450 MHz', '사백오십 메가헤르츠'),
    ('25 kHz', '이십오 킬로헤르츠'),
    ('48 kHz', '사십팔 킬로헤르츠'),
    ('96 kHz', '구십육 킬로헤르츠'),
    ('220 V', '이백이십 볼트'),
    ('12 V', '십이 볼트'),
    ('5 A', '오 암페어'),
    ('750 W', '칠백오십 와트'),
    ('65 W', '육십오 와트'),
    ('85 °C', '팔십오 도씨'),
    ('37 °C', '삼십칠 도씨'),
    ('10%', '십 퍼센트'),
    ('99.9%', '구십구 쩜 구 퍼센트'),
    ('0.1%', '영 쩜 일 퍼센트'),
    ('250 tx/s', '이백오십 티엑스 퍼 세컨드'),
    ('1200 tx/min', '천이백 티엑스 퍼 분'),
    ('32 peer/s', '삼십이 피어 퍼 세컨드'),
    ('8 peer/min', '팔 피어 퍼 분'),
    ('15 node/s', '십오 노드 퍼 세컨드'),
    ('120 req/s', '백이십 알이큐 퍼 세컨드'),
    ('500 request/s', '오백 리퀘스트 퍼 세컨드'),
    ('300 msg/s', '삼백 메시지 퍼 세컨드'),
    ('90 packet/s', '구십 패킷 퍼 세컨드'),
    ('75 event/s', '칠십오 이벤트 퍼 세컨드'),
    ('42 job/s', '사십이 잡 퍼 세컨드'),
    ('18 task/s', '십팔 태스크 퍼 세컨드'),
    ('7 thread/s', '칠 스레드 퍼 세컨드'),
    ('4 process/s', '사 프로세스 퍼 세컨드'),
    ('60 frame/s', '육십 프레임 퍼 세컨드'),
    ('30 fps', '삼십 에프피에스'),
    ('120 fps', '백이십 에프피에스'),
    ('2 block/min', '이 블록 퍼 분'),
    ('6 block/h', '육 블록 퍼 시간'),
    ('144 block/day', '백사십사 블록 퍼 데이'),
    ('250 hash/s', '이백오십 해시 퍼 세컨드'),
    ('1 kH/s', '일 킬로해시 퍼 세컨드'),
    ('5 MH/s', '오 메가해시 퍼 세컨드'),
    ('2 GH/s', '이 기가해시 퍼 세컨드'),
    ('120 TH/s', '백이십 테라해시 퍼 세컨드'),
    ('250 byte/s', '이백오십 바이트 퍼 세컨드'),
    ('4 kB/s', '사 킬로바이트 퍼 세컨드'),
    ('20 MB/min', '이십 메가바이트 퍼 분'),
    ('1 GB/min', '일 기가바이트 퍼 분'),
    ('50 GB/day', '오십 기가바이트 퍼 데이'),
    ('2 TB/day', '이 테라바이트 퍼 데이'),
    ('15 IOPS', '십오 아이옵스'),
    ('500 IOPS', '오백 아이옵스'),
    ('5000 IOPS', '오천 아이옵스'),
    ('2 ms/op', '이 밀리세컨드 퍼 오퍼레이션'),
    ('10 op/s', '십 오퍼레이션 퍼 세컨드'),
    ('200 call/s', '이백 콜 퍼 세컨드'),
    ('80 query/s', '팔십 쿼리 퍼 세컨드'),
    ('25 write/s', '이십오 라이트 퍼 세컨드'),
    ('40 read/s', '사십 리드 퍼 세컨드'),
    ('64 connection/s', '육십사 커넥션 퍼 세컨드'),
    ('12 session/s', '십이 세션 퍼 세컨드'),
    ('3 retry/s', '삼 리트라이 퍼 세컨드'),
    ('5 error/min', '오 에러 퍼 분'),
    ('1 fail/h', '일 페일 퍼 시간'),
    ('10 km/h', '십 킬로미터 퍼 아워'),
    ('100 km/h', '백 킬로미터 퍼 아워'),
    ('5 m/s', '오 미터 퍼 세컨드'),
    ('9.8 m/s²', '구 쩜 팔 미터 퍼 세컨드 제곱'),
    ('1.2 MB', '일 쩜 이 메가바이트'),
    ('2.4 GB', '이 쩜 사 기가바이트'),
    ('0.5 ms', '영 쩜 오 밀리세컨드'),
    ('12.5 ms', '십이 쩜 오 밀리세컨드'),
    ('250 ns', '이백오십 나노세컨드'),
    ('100 µs', '백 마이크로세컨드'),
    ('3 core', '삼 코어'),
    ('8 core', '팔 코어'),
    ('16 core', '십육 코어'),
    ('32 thread', '삼십이 스레드'),
    ('4096 byte', '사천구십육 바이트'),
    ('65536 byte', '육만오천오백삼십육 바이트'),
    ('2048 bit', '이천사십팔 비트'),
    ('256 bit', '이백오십육 비트'),
    ('64 bit', '육십사 비트'),
    ('32 bit', '삼십이 비트'),
]


class Units100NormalizationTests(unittest.TestCase):
    def test_all_education_cases_exactly_match(self):
        self.assertEqual(len(EXPECTED), 100)
        for raw, expected in EXPECTED:
            with self.subTest(raw=raw):
                self.assertEqual(tn.normalize(raw), expected)

    def test_unit_case_and_token_boundaries(self):
        for text in (
            'foo8GB', 'test_8GB', 'v1.5', 'file12.5ms.txt',
            '/path/8GB/test', 'abc123', '192.168.0.1',
            'https://example.com/8GB', 'user8GB@example.com',
            '--limit=8GB', 'TEST-8GB', 'commit8GBsha',
            'foo_12.5ms_bar', '8GB.txt', '192.168.0.1:8080',
        ):
            with self.subTest(text=text):
                self.assertEqual(tn.normalize(text), text)
                self.assertIsNone(tn.overrides.NUMBER_UNIT.search(text))

    def test_compact_and_spaced_prose_units(self):
        self.assertEqual(tn.normalize('8 GB and 250Mbps'),
                         '팔 기가바이트 앤드 이백오십 메가비트 퍼 세컨드')
        self.assertEqual(tn.normalize('10 km/h, 5 m/s'),
                         '십 킬로미터 퍼 아워, 오 미터 퍼 세컨드')
        self.assertEqual(tn.normalize('1,234 widgets'), '1234 widgets')

    def test_general_unit_rules_and_case_sensitive_boundaries(self):
        generalized = {
            '100 kb/s': '백 킬로비트 퍼 세컨드',
            '1000 ms': '천 밀리세컨드',
            '225 block/s': '이백이십오 블록 퍼 세컨드',
            '2 s': '이 초',
            '144 Hz': '백사십사 헤르츠',
            '1.5 GB/s': '일 쩜 오 기가바이트 퍼 세컨드',
        }
        for raw, expected in generalized.items():
            with self.subTest(raw=raw):
                self.assertEqual(tn.normalize(raw), expected)

        # No exact-literal exceptions: unsupported spellings stay unchanged,
        # while supported case-sensitive units use the general registry.
        self.assertEqual(tn.normalize('225 blocks/s'), '225 blocks/s')
        self.assertEqual(tn.normalize('50 mb/s'), '50 mb/s')
        self.assertEqual(tn.normalize('50 MB/s'), '오십 메가바이트 퍼 세컨드')
        for literal in ('x100 kb/s', '100 kb/s_v2', 'v225 block/s',
                        'id50 mb/s', 'file100 kb/s.txt'):
            with self.subTest(literal=literal):
                self.assertEqual(tn.normalize(literal), literal)


if __name__ == '__main__':
    unittest.main()
