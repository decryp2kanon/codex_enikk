import json
import socket
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from trigger_service import Service, ContinuityBlocked, BLOCKED_CONTINUITY_METHODS, check_continuity_request, native_client
from trigger_transport import connect

TID='11111111-1111-4111-8111-111111111111'
class ContinuityGuardTests(unittest.TestCase):
    def test_denials_leave_every_reservation_state_intact(self):
        with tempfile.TemporaryDirectory() as d:
            s=Service('unused',TID,Path(d)/'private',Path(d)/'inbox')
            for state,owner in [('IDLE',None),('USER_ACTIVE','USER'),('DOROTHY_ACTIVE','DOROTHY'),('UNKNOWN',None)]:
                s.arbiter.state,s.arbiter.owner=state,owner
                s.arbiter.token='reserved-token';s.arbiter.turn='current-turn'
                for method in BLOCKED_CONTINUITY_METHODS:
                    with self.subTest(state=state,method=method):
                        with self.assertRaises(ContinuityBlocked):s.native_request(Mock(),{'id':1,'method':method,'params':{'threadId':TID}})
                        self.assertEqual((s.arbiter.state,s.arbiter.owner,s.arbiter.token,s.arbiter.turn),(state,owner,'reserved-token','current-turn'))
    def test_normal_resume_and_controls_are_allowed(self):
        for method,params in [('thread/resume',{'threadId':TID,'history':None,'path':None}),('turn/start',{'threadId':TID}),('turn/interrupt',{'threadId':TID}),('thread/compact/start',{'threadId':TID}),('thread/backgroundTerminals/clean',{'threadId':TID}),('config/value/write',{'keyPath':'model','value':'fixture'}),('config/value/write',{'keyPath':'approval_policy','value':'on-request'})]:
            check_continuity_request({'method':method,'params':params},TID)
    def test_resume_rejects_other_id_or_replacement_history(self):
        for p in [{'threadId':'other'},{'threadId':TID,'history':[]},{'threadId':TID,'path':'/elsewhere'}]:
            with self.assertRaises(ContinuityBlocked):check_continuity_request({'method':'thread/resume','params':p},TID)
    def test_real_proxy_keeps_connection_after_denial(self):
        with tempfile.TemporaryDirectory() as d:
            s=Service('unused',TID,Path(d)/'private',Path(d)/'inbox')
            s.arbiter.initialize({'id':TID,'status':{'type':'idle'}})
            endpoint=str(Path(d)/'mock.sock');listener=socket.socket(socket.AF_UNIX);listener.bind(endpoint);listener.listen()
            sent=[]
            class FakeSession:
                def __init__(self,service,downstream):self.downstream=downstream;self.pending={}
                def send(self,event):
                    sent.append(event)
                    self.downstream.send(json.dumps({'id':event['id'],'result':{'ok':True}}))
                def close(self):self.downstream.close()
            def run():
                conn,_=listener.accept()
                native_client(s,conn)
            with patch('trigger_service.Session',FakeSession):
                t=threading.Thread(target=run,daemon=True);t.start();ws=connect(endpoint);ws.settimeout(2)
                try:
                    for method in sorted(BLOCKED_CONTINUITY_METHODS):
                        ws.send(json.dumps({'id':1,'method':method,'params':{'threadId':TID}}))
                        denied=json.loads(ws.recv())
                        self.assertEqual(denied['error']['code'],-32601 if method=='thread/revert' else -32010)
                        self.assertIn('ENIKK_CONTINUITY_BLOCKED',denied['error']['message'])
                        self.assertEqual(s.arbiter.state,'IDLE');self.assertEqual(sent,[])
                    ws.send(json.dumps({'id':3,'method':'thread/resume','params':{'threadId':'other'}}))
                    self.assertEqual(json.loads(ws.recv())['error']['code'],-32010)
                    self.assertEqual(sent,[])
                    ws.send(json.dumps({'id':2,'method':'thread/read','params':{'threadId':TID}}))
                    self.assertTrue(json.loads(ws.recv())['result']['ok'])
                    self.assertEqual(len(sent),1)
                finally:ws.close();s.stopped.set();listener.close();t.join(2)
