"""Real Unix/WebSocket protocol fixtures, without Codex/model/user data."""
import json
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from trigger_client import submit, main as client_main, EXIT
from trigger_service import Service, Session, bind_local, native_client, trigger_client
from trigger_transport import accept_websocket, connect


def eventually(predicate, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate(): return
        time.sleep(.01)
    raise AssertionError('condition timeout')


class FakeServer:
    def __init__(self, path):
        self.listener = bind_local(path)
        self.connections = []
        self.events = []
        self.lock = threading.RLock()
        self.stop = threading.Event()
        self.hold = threading.Event(); self.hold.set()
        self.submitted = threading.Event()
        self.active = None
        self.count = 0
        self.steered = 0
        threading.Thread(target=self.accept, daemon=True).start()

    def accept(self):
        while not self.stop.is_set():
            try: sock, _ = self.listener.accept()
            except socket.timeout: continue
            except OSError: return
            threading.Thread(target=self.handle, args=(sock,), daemon=True).start()

    def broadcast(self, event):
        for connection in list(self.connections):
            try: connection.send(json.dumps(event))
            except OSError: pass

    def complete(self):
        turn = self.active; self.active = None
        self.broadcast({'method': 'turn/completed', 'params': {'threadId': 'thread', 'turn': {'id': turn, 'status': 'completed'}}})

    def handle(self, sock):
        connection = None
        try:
            connection = accept_websocket(sock); self.connections.append(connection)
            while not self.stop.is_set():
                event = json.loads(connection.recv()); self.events.append(event)
                method = event.get('method')
                result = {}
                if method in ('thread/resume', 'thread/read'):
                    result = {'thread': {'id': 'thread', 'status': {'type': 'idle' if self.active is None else 'active'}}}
                elif method == 'turn/start':
                    with self.lock:
                        if self.active:
                            self.steered += 1
                        else:
                            self.count += 1; self.active = 'turn-' + str(self.count)
                    self.submitted.set(); self.hold.wait(3)
                    result = {'turn': {'id': self.active}}
                    self.broadcast({'method': 'turn/started', 'params': {'threadId': 'thread', 'turn': {'id': self.active}}})
                elif method == 'turn/interrupt':
                    self.complete()
                if 'id' in event and method:
                    connection.send(json.dumps({'id': event['id'], 'result': result}))
        except (EOFError, OSError, ValueError): pass
        finally:
            if connection: connection.close()
            else: sock.close()

    def close(self):
        self.stop.set(); self.hold.set(); self.listener.close()
        for connection in self.connections: connection.close()


class IpcTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='arb-'); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.inbox = self.root / 'inbox'; self.inbox.write_text('harmless\n\nEOF\n'); self.inbox.chmod(0o600)
        self.server = FakeServer(self.root / 'up.sock'); self.addCleanup(self.server.close)
        self.service = Service(str(self.root / 'up.sock'), 'thread', self.root / 'state', self.inbox)
        self.service.initialize(); self.addCleanup(self.close_service)
        self.service.start_dispatcher()
        self.proxy = bind_local(self.root / 'proxy.sock'); self.addCleanup(self.proxy.close)
        self.trigger = bind_local(self.root / 'trigger.sock'); self.addCleanup(self.trigger.close)
        self.stop = threading.Event(); self.addCleanup(self.stop.set)
        for listener, handler in ((self.proxy, native_client), (self.trigger, trigger_client)):
            threading.Thread(target=self.accept, args=(listener, handler), daemon=True).start()
        self.native = connect(self.root / 'proxy.sock'); self.native.settimeout(3); self.addCleanup(self.native.close)
        self.native.send(json.dumps({'id': 1, 'method': 'initialize', 'params': {}}))
        self.response(1)
        self.native.send(json.dumps({'method': 'initialized'}))
        self.native.send(json.dumps({'id': 2, 'method': 'thread/resume', 'params': {'threadId': 'thread'}}))
        self.response(2)

    def close_service(self):
        self.service.stopped.set(); self.service.queue_wakeup.set()
        for session in list(self.service.sessions): session.close()

    def accept(self, listener, handler):
        while not self.stop.is_set():
            try: sock, _ = listener.accept()
            except socket.timeout: continue
            except OSError: return
            threading.Thread(target=handler, args=(self.service, sock), daemon=True).start()

    def response(self, identity):
        while True:
            event = json.loads(self.native.recv())
            if event.get('id') == identity and 'method' not in event: return event

    def native_submit(self, identity=3):
        self.native.send(json.dumps({'id': identity, 'method': 'turn/start', 'params': {'threadId': 'thread', 'input': [{'type': 'text', 'text': 'native'}]}}))

    def test_native_then_dorothy_reserved_race(self):
        self.server.hold.clear(); self.native_submit()
        self.assertTrue(self.server.submitted.wait(3))
        self.assertEqual(submit(self.root / 'trigger.sock')['status'], 'QUEUED')
        self.server.hold.set(); self.response(3)
        self.assertEqual(self.server.count, 1); self.assertEqual(self.server.steered, 0)

    def test_dorothy_then_native_reserved_race_and_completion(self):
        self.server.hold.clear(); results = []
        thread = threading.Thread(target=lambda: results.append(submit(self.root / 'trigger.sock'))); thread.start()
        self.assertTrue(self.server.submitted.wait(3))
        self.native_submit(); self.assertIn('error', self.response(3))
        self.server.hold.set(); thread.join(3); self.assertFalse(thread.is_alive())
        self.assertEqual(results[0]['status'], 'ACCEPTED')
        self.assertEqual(submit(self.root / 'trigger.sock')['status'], 'DUPLICATE')
        self.server.complete(); eventually(lambda: self.service.arbiter.state == 'IDLE')
        self.native_submit(4); self.assertIn('result', self.response(4))
        self.assertEqual(self.server.count, 2); self.assertEqual(self.server.steered, 0)

    def test_approval_tool_event_and_native_interrupt(self):
        self.native_submit(); self.response(3)
        approval = {'id': 'approval', 'method': 'item/commandExecution/requestApproval', 'params': {'threadId': 'thread'}}
        self.server.broadcast(approval)
        while True:
            event = json.loads(self.native.recv())
            if event.get('id') == 'approval': break
        self.assertEqual(event, approval)
        response = {'id': 'approval', 'result': {'decision': 'decline'}}
        self.native.send(json.dumps(response))
        eventually(lambda: response in self.server.events)
        self.native.send(json.dumps({'id': 9, 'method': 'turn/interrupt', 'params': {'threadId': 'thread', 'turnId': self.server.active}}))
        self.assertIn('result', self.response(9))
        eventually(lambda: self.service.arbiter.state == 'IDLE')

    def test_socket_permissions_and_missing_server(self):
        self.assertEqual((self.root / 'trigger.sock').stat().st_mode & 0o777, 0o600)
        self.assertEqual(submit(self.root / 'absent')['status'], 'NO_RUNNING_ENIKK')

    def test_stale_socket_and_live_socket_protection(self):
        path = self.root / 'stale'
        stale = bind_local(path); stale.close()
        replacement = bind_local(path)
        try:
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError): bind_local(path)
        finally: replacement.close()

    def test_symlink_endpoint_rejected(self):
        alias = self.root / 'alias'; alias.symlink_to(self.root / 'trigger.sock')
        self.assertEqual(submit(alias)['status'], 'SECURITY_ERROR')

    def test_restart_unknown_effect_never_reissues(self):
        task = self.service.tasks / ('a' * 64); task.mkdir()
        import hashlib
        data = b'unchanged\n\nEOF\n'; (task / 'command.md').write_bytes(data)
        digest = hashlib.sha256(data).hexdigest()
        (task / 'state.json').write_text(json.dumps({'task_id': 'a'*64, 'sha256': digest, 'status': 'UNKNOWN_EFFECT'}))
        (task / 'command-state.json').write_text(json.dumps({'task_id': 'a'*64, 'command_sha256': digest, 'instructions': []}))
        (task / 'instructions').mkdir()
        restarted = Service(str(self.root / 'up.sock'), 'thread', self.service.root, self.inbox)
        try:
            restarted.initialize()
            self.assertEqual(restarted.arbiter.state, 'UNKNOWN')
            self.assertEqual(restarted.trigger({'action': 'trigger'}, os.getuid())['status'], 'QUEUED')
            self.assertEqual(self.server.count, 0)
        finally:
            restarted.stopped.set()
            for session in list(restarted.sessions): session.close()

    def temporary_client(self):
        client = connect(self.root / 'proxy.sock'); client.settimeout(3)
        client.send(json.dumps({'id': 101, 'method': 'initialize', 'params': {}}))
        while json.loads(client.recv()).get('id') != 101:
            pass
        return client

    def test_temporary_disconnect_preserves_idle_and_next_submission(self):
        client = self.temporary_client()
        natives = [s for s in self.service.sessions if s is not self.service.observer]
        client.close()
        eventually(lambda: any(not s.alive for s in natives))
        self.assertEqual(self.service.arbiter.state, 'IDLE')
        self.native_submit(); self.assertIn('result', self.response(3))

    def test_interrupt_then_temporary_disconnect_allows_new_delegate(self):
        first = submit(self.root / 'trigger.sock')
        self.assertEqual(first['status'], 'ACCEPTED')
        client = self.temporary_client()
        natives = [s for s in self.service.sessions if s is not self.service.observer]
        client.send(json.dumps({'id': 102, 'method': 'turn/interrupt',
                                'params': {'threadId': 'thread', 'turnId': self.server.active}}))
        while json.loads(client.recv()).get('id') != 102:
            pass
        eventually(lambda: self.service.arbiter.state == 'IDLE')
        client.close()
        eventually(lambda: any(not s.alive for s in natives))
        self.inbox.write_text('second command\n\nEOF\n')
        self.assertEqual(submit(self.root / 'trigger.sock')['status'], 'ACCEPTED')
        self.assertEqual(self.server.count, 2)
        self.assertEqual(self.server.steered, 0)

    def test_idle_client_disconnect_does_not_poison_active_delegate(self):
        self.assertEqual(submit(self.root / 'trigger.sock')['status'], 'ACCEPTED')
        client = self.temporary_client()
        natives = [s for s in self.service.sessions if s is not self.service.observer]
        client.close()
        eventually(lambda: any(not s.alive for s in natives))
        self.assertEqual(self.service.arbiter.state, 'DOROTHY_ACTIVE')
        self.inbox.write_text('new command\n\nEOF\n')
        self.assertEqual(submit(self.root / 'trigger.sock')['status'], 'QUEUED')
        self.server.complete()
        eventually(lambda: self.server.count == 2)
        self.assertEqual(submit(self.root / 'trigger.sock')['status'], 'DUPLICATE')
        self.assertEqual(self.server.steered, 0)

    def test_unresolved_native_send_disconnect_remains_unknown(self):
        from unittest.mock import Mock
        session = Mock(); session.pending = {}
        self.service.native_request(session, {'id': 55, 'method': 'turn/start',
                                             'params': {'threadId': 'thread'}})
        self.service.transport_lost(session)
        self.assertEqual(self.service.arbiter.state, 'UNKNOWN')

    def test_fifo_snapshot_and_no_steering(self):
        self.native_submit(); self.response(3)
        ids = []
        for text in ('first queued', 'second queued', 'third queued'):
            self.inbox.write_text(text + '\n\nEOF\n')
            reply = submit(self.root / 'trigger.sock')
            self.assertEqual(reply['status'], 'QUEUED')
            ids.append(reply['task_id'])
        self.assertEqual(submit(self.root / 'trigger.sock')['status'], 'DUPLICATE')
        self.inbox.write_text('overwritten inbox\n\nEOF\n')
        for index, task_id in enumerate(ids, 2):
            self.server.complete()
            eventually(lambda: self.server.count == index)
            path = self.service.tasks / task_id / 'state.json'
            eventually(lambda: json.loads(path.read_text())['status'] == 'ACCEPTED')
        self.server.complete(); eventually(lambda: self.service.arbiter.state == 'IDLE')
        messages = [e['params']['input'][0]['text'] for e in self.server.events if e.get('method') == 'turn/start'][1:]
        self.assertEqual([x.split('===== 명령서 원문 =====\n')[1] for x in messages],
                         [x + '\n\nEOF\n' for x in ('first queued', 'second queued', 'third queued')])
        self.assertEqual(self.server.count, 4); self.assertEqual(self.server.steered, 0)

    def test_cancel_queued_never_runs_or_cancels_active(self):
        self.native_submit(); self.response(3)
        reply = submit(self.root / 'trigger.sock')
        task_id = reply['task_id']
        self.assertEqual(submit(self.root / 'trigger.sock', cancel=task_id)['status'], 'CANCELLED')
        self.assertEqual(submit(self.root / 'trigger.sock')['delivery_status'], 'CANCELLED')
        self.server.complete(); eventually(lambda: self.service.arbiter.state == 'IDLE')
        self.assertEqual(self.server.count, 1)

    def test_known_completion_after_unknown_drains_queue(self):
        self.assertEqual(submit(self.root / 'trigger.sock')['status'], 'ACCEPTED')
        self.service.arbiter.lost()
        self.inbox.write_text('next\n\nEOF\n')
        self.assertEqual(submit(self.root / 'trigger.sock')['status'], 'QUEUED')
        self.server.complete()
        eventually(lambda: self.server.count == 2)
        self.assertEqual(self.server.steered, 0)

    def test_transport_only_unknown_reconciles_and_drains(self):
        self.service.arbiter.lost()
        self.assertEqual(submit(self.root / 'trigger.sock')['status'], 'QUEUED')
        eventually(lambda: self.server.count == 1)
        self.assertEqual(self.server.steered, 0)

    def test_restart_retains_and_dispatches_unsent_queue(self):
        self.native_submit(); self.response(3)
        reply = submit(self.root / 'trigger.sock'); self.assertEqual(reply['status'], 'QUEUED')
        self.close_service()
        self.server.complete()
        restarted = Service(str(self.root / 'up.sock'), 'thread', self.service.root, self.inbox)
        try:
            restarted.initialize(); restarted.start_dispatcher()
            eventually(lambda: self.server.count == 2)
            path = restarted.tasks / reply['task_id'] / 'state.json'
            eventually(lambda: json.loads(path.read_text())['status'] == 'ACCEPTED')
            self.assertEqual(self.server.steered, 0)
        finally:
            restarted.stopped.set(); restarted.queue_wakeup.set()
            for session in list(restarted.sessions): session.close()

    def test_disconnect_fails_closed(self):
        self.server.close()
        eventually(lambda: self.service.arbiter.state == 'UNKNOWN')
        self.assertEqual(submit(self.root / 'trigger.sock')['status'], 'QUEUED')
        self.assertEqual(self.server.count, 0)
