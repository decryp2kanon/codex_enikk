# 작성자: 에닉(유키짱)
"""Reviewed symbol policies and independent unseen context anchors."""
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from test_education_2_7 import tn
ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((ROOT / 'tests/fixtures/education-9.json').read_text())
spec = importlib.util.spec_from_file_location('symbol_notify', ROOT/'tts/yuki-codex-notify.py')
notify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(notify)

class SymbolTests(unittest.TestCase):
    def test_hundred(self):
        self.assertEqual(len(FIXTURE['cases']),100)
        for raw,expected in FIXTURE['cases']:
            with self.subTest(raw=raw):
                self.assertEqual(tn.normalize(raw),expected)
                self.assertEqual(notify.clean_text(raw),expected)

    def test_thirty_unseen_contexts(self):
        cases=[('#######','해시 칠 개'),('*****','별표 오 개'),('_____','밑줄 오 개'),
               ('!!!!','느낌표 사 개'),('????','물음표 사 개'),('@@@@','골뱅이 사 개'),
               ('$$$$','달러 사 개'),('%%%%','퍼센트 사 개'),('^^^^','캐럿 사 개'),
               ('~~~~','물결 사 개'),('||||','파이프 사 개'),('&&&&','앰퍼샌드 사 개'),
               ('++++','플러스 사 개'),('----','마이너스 사 개'),('====','등호 사 개'),
               ('/\\','슬래시 백슬래시'),('\\/','백슬래시 슬래시'),
               ('+?','플러스 물음표'),(':-','콜론 마이너스'),('!?','느낌표 물음표'),
               ('==!=','동등 비교 비동등 비교'),('-><-','오른쪽 화살표 왼쪽 화살표'),
               ('<->=>','양방향 화살표 오른쪽 이중선 화살표'),
               ('&&||','논리 앤드 논리 오어'),('>=<=','크거나 같다 작거나 같다'),
               ('()[]','소괄호 쌍 대괄호 쌍'),('{}()','중괄호 쌍 소괄호 쌍'),
               ('::;','이중 콜론 세미콜론'),('?.??','옵셔널 체이닝 널 병합 연산자'),
               ('[]{}','대괄호 쌍 중괄호 쌍')]
        self.assertEqual(len(cases),30)
        for raw,expected in cases:
            self.assertEqual(tn.normalize('기호 '+raw+' 확인'), '기호 '+expected+' 확인')

    def test_markdown_context(self):
        for level,name in enumerate(['일','이','삼','사','오','육'],1):
            raw='#'*level+' wallet'
            self.assertEqual(tn.normalize(raw), name+' 단계 제목 월렛')
            self.assertEqual(notify.clean_text(raw),name+' 단계 제목 wallet')
        for raw,expected in [('**wallet**','굵게 wallet 강조 끝'),
                             ('*wallet*','기울임 wallet 강조 끝'),
                             ('~~wallet~~','취소선 wallet 강조 끝'),
                             ('***wallet***','굵게 기울임 wallet 강조 끝'),
                             ('__wallet__','굵게 wallet 강조 끝'),
                             ('_wallet_','기울임 wallet 강조 끝'),
                             ('<!-- hello -->','에이치티엠엘 주석 hello 주석 끝'),
                             ('<span>hello</span>','여는 태그 span hello 닫는 태그 span')]:
            self.assertEqual(notify.clean_text(raw),expected)
        for fence in ['```','~~~']:
            for raw in [fence+'python\nsecret\n'+fence,fence+'python\nsecret']:
                self.assertEqual(notify.clean_text(raw),'')

    def test_literals(self):
        for raw in ['https://example.org/a?x=1&y=2','foo@example.org','/tmp/the/file.md',
                    'v1.2.3','192.168.0.1','`'+'f'*40+'`','`'+'a'*64+'`','foo_bar','foo-bar',
                    '--the','--output=file.txt','`a == b`','```\na == b\n```',
                    'a == b','value >= limit','name=value','foo::bar','x->y']:
            self.assertEqual(tn.normalize(raw),raw)
        for raw in ['`**wallet**`', '`<span>`', '`<!-- note -->`', '/tmp/**wallet**','https://example.org/**wallet**','foo__wallet__bar']:
            self.assertEqual(tn.overrides.markdown_spoken(raw),raw)

    def test_source(self):
        source=Path.home() / 'git' / 'codex_enikk-education' / '9_tts-github-symbols-100.txt'
        if not source.exists():self.skipTest('external source absent')
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),FIXTURE['_source_sha256'])
        self.assertEqual(source.read_text().splitlines(),[raw for raw,_ in FIXTURE['cases']])
# EOF
