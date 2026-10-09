import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from trigger_service import Service, Session
from submission_arbiter import UnknownEffect

class StartupTimeoutTests(unittest.TestCase):
    def test_resume_uses_long_budget_and_keeps_original_id(self):
        with tempfile.TemporaryDirectory() as d:
            observer = Mock()
            observer.call.side_effect = [{}, {'thread': {'id': 'test-only-thread', 'status': {'type': 'idle'}}}]
            service = Service('unused', 'test-only-thread', Path(d)/'private', Path(d)/'inbox')
            with patch('trigger_service.Session', return_value=observer):
                service.initialize()
            self.assertEqual(observer.call.call_args_list[0].kwargs, {})
            observer.call.assert_called_with('thread/resume', {'threadId': 'test-only-thread'}, timeout=120)
            self.assertEqual(service.arbiter.state, 'IDLE')

    def test_resume_still_rejects_wrong_identity(self):
        with tempfile.TemporaryDirectory() as d:
            observer = Mock()
            observer.call.side_effect = [{}, {'thread': {'id': 'wrong-thread', 'status': {'type': 'idle'}}}]
            service = Service('unused', 'test-only-thread', Path(d)/'private', Path(d)/'inbox')
            with patch('trigger_service.Session', return_value=observer):
                with self.assertRaisesRegex(UnknownEffect, 'identity mismatch'):
                    service.initialize()

    def test_rpc_timeout_is_scoped_and_reports_method(self):
        for method, kwargs, budget in [('turn/start', {}, 15), ('thread/resume', {'timeout':120}, 120)]:
            session = Session.__new__(Session)
            session.counter = 0
            session.waiters, session.pending = {}, {}
            session.send = Mock()
            event = Mock()
            event.wait.return_value = False
            with patch('trigger_service.threading.Event', return_value=event):
                with self.assertRaisesRegex(UnknownEffect, method):
                    session.call(method, {}, **kwargs)
            event.wait.assert_called_once_with(budget)
            session.send.assert_called_once()
