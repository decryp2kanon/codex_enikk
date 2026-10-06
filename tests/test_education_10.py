# 작성자: 에닉(유키짱)
"""Codex prose labels, productive composition and machine literals."""
import hashlib
import json
from pathlib import Path
import unittest
from test_education_2_7 import tn
ROOT=Path(__file__).resolve().parents[1]
FIXTURE=json.loads((ROOT/'tests/fixtures/education-10.json').read_text())

class CodexTermsTests(unittest.TestCase):
    def test_hundred(self):
        self.assertEqual(len(FIXTURE['cases']),100)
        for raw,expected in FIXTURE['cases']:
            with self.subTest(raw=raw):self.assertEqual(tn.normalize(raw),expected)

    def test_thirty_unseen_sentences(self):
        anchors=[('agent','에이전트'),('assistant','어시스턴트'),('prompt','프롬프트'),
                 ('response','리스폰스'),('reasoning','리즈닝'),('instruction','인스트럭션'),
                 ('developer','디벨로퍼'),('turn','턴'),('session','세션'),('memory','메모리'),
                 ('model','모델'),('runtime','런타임'),('workspace','워크스페이스'),
                 ('timeout','타임아웃'),('interrupt','인터럽트')]
        seen=set()
        for raw,expected in anchors:
            for template in ['새로운 {} 상태를 확인해.','{} 문맥을 다시 점검해.']:
                text=template.format(raw);seen.add(text)
                self.assertEqual(tn.normalize(text),template.format(expected))
        self.assertEqual(len(seen),30)
        self.assertEqual(tn.normalize('The agent is ready.'),'더 에이전트 이즈 레디.')
        self.assertEqual(tn.normalize('Codex can resume the session.'),'코덱스 캔 리줌 더 세션.')

    def test_label_generalization(self):
        for raw,expected in [('tool_item','툴 아이템'),('response_call','리스폰스 콜'),
                             ('response_result','리스폰스 리절트'),('tool_point','툴 포인트'),
                             ('rollback_result','롤백 리절트'),('apply_item','어플라이 아이템')]:
            self.assertEqual(tn.normalize(raw),expected)
            self.assertEqual(tn.normalize('상태 '+raw+' 확인'), '상태 '+expected+' 확인')
        for raw,expected in [('notes','노트스'),('agents','에이전트스'),('models','모델스'),('plugins','플러그인스'),
                             ('tool_calls','툴 콜스'),('Agent','에이전트'),
                             ('Codex는','코덱스는'),('agent에게','에이전트에게'),
                             ('tool_call에서는','툴 콜에서는')]:
            self.assertEqual(tn.normalize(raw),expected)

    def test_boundaries(self):
        for word,_ in FIXTURE['cases']:
            for template in ['https://example.org/{}','{}@example.org','/tmp/{}/config.json',
                             '{}.txt','prefix_{}','{}_id','prefix-{}','--{}','`{}`',
                             '```\n{}\n```','name={}','{}123']:
                raw=template.format(word)
                with self.subTest(raw=raw):self.assertEqual(tn.normalize(raw),raw)
        for raw in ['tool_call_id','get_tool_call','tool_custom','custom_response',
                    'TOOL_CALL','v1.2.3','192.168.0.1','`'+'a'*40+'`','`'+'f'*64+'`']:
            self.assertEqual(tn.normalize(raw),raw)

    def test_source_immutable(self):
        p=Path('/home/ak/git/codex_enikk-education/10_tts-codex-terms-100.txt')
        if not p.exists():self.skipTest('external source absent')
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),FIXTURE['_source_sha256'])
        self.assertEqual(p.read_text().splitlines(),[x[0] for x in FIXTURE['cases']])
# EOF
