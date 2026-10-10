import json
import os
import unittest
from unittest.mock import patch
from test_trigger_ipc import IpcTests, eventually


class DelegatedIpcTests(unittest.TestCase):
    setUp = IpcTests.setUp
    close_service = IpcTests.close_service
    accept = IpcTests.accept
    response = IpcTests.response

    def item(self, turn, text, thread='thread', session=None, phase='final_answer', identity='item'):
        event={'method':'item/completed','params':{'threadId':thread,'turnId':turn,
                'item':{'type':'agentMessage','phase':phase,'id':identity,'text':text}}}
        self.service.received(session or self.service.observer,event)

    def test_observer_only_bound_delegated_turn(self):
        result=self.service.trigger({'action':'trigger'},os.getuid())
        self.assertEqual(result['status'],'ACCEPTED')
        task=self.service.tasks/result['task_id']; turn=result['turn_id']
        log=self.root/'messages.md'; log.write_text('history\n'); (self.root/'messages.md.lock').touch()
        self.item('foreign','wrong-turn'); self.item(turn,'wrong-thread',thread='foreign')
        self.item(turn,'wrong-source',session=object())
        self.item(turn,'progress',phase='commentary')
        self.item(turn,'final answer')
        with patch('delegated_reply.shared_log',return_value=log):
            self.server.complete()
            eventually(lambda: (task/'reply-delivery.json').exists())
        self.assertEqual(json.loads((task/'state.json').read_text())['status'],'COMPLETED')
        text=log.read_text()
        self.assertIn('final answer',text)
        for excluded in ['wrong-turn','wrong-thread','wrong-source','progress']: self.assertNotIn(excluded,text)
        self.assertEqual(self.service.thread_id,'thread')
        self.assertEqual(self.service.arbiter.state,'IDLE')

    def test_user_turn_does_not_capture(self):
        token=self.service.arbiter.reserve('USER','thread')
        self.service.arbiter.accepted(token,'native')
        self.item('native','ordinary user reply')
        self.assertEqual(list(self.service.tasks.glob('*/reply.json')),[])

    def test_capture_failure_does_not_break_turn_or_publish_partial(self):
        result=self.service.trigger({'action':'trigger'},os.getuid()); task=self.service.tasks/result['task_id']; turn=result['turn_id']
        self.item(turn,'first'); self.item(turn,'conflicting')
        self.assertTrue((task/'reply-error.json').exists())
        self.server.complete()
        eventually(lambda:(task/'reply-delivery.json').exists())
        self.assertEqual(json.loads((task/'reply-delivery.json').read_text())['status'],'CAPTURE_FAILED')
        self.assertEqual(self.service.arbiter.state,'IDLE')
