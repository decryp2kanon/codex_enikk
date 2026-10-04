import json
import os
from pathlib import Path
import socket
import struct
import tempfile
import threading
import unittest
from unittest.mock import patch

from submission_arbiter import Busy, UnknownEffect
from trigger_service import Service, FIXTURE, inbox_bytes, native_client, Session
from trigger_transport import Downstream, rpc_object, accept_websocket


class FakeObserver:
    def __init__(self, service):
        self.service = service
        self.pending = {}
        self.calls = []

    def call(self, method, params, token=None):
        self.calls.append((method, params))
        self.service.arbiter.accepted(token, 'delegated-turn')
        return {'turn': {'id': 'delegated-turn'}}


class TriggerProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inbox = self.root / 'inbox.md'; self.inbox.write_text('harmless\n\nEOF\n')
        self.inbox.chmod(0o600)
        self.service = Service('unused', 'thread', self.root / 'private', self.inbox)
        self.service.arbiter.initialize({'id': 'thread', 'status': {'type': 'idle'}})
        self.service.observer = FakeObserver(self.service)

    def request(self): return self.service.trigger({'action': 'trigger'}, os.getuid())

    def test_valid_snapshot_and_sequential_dedup(self):
        result = self.request(); self.assertEqual(result['status'], 'ACCEPTED')
        task = self.service.tasks / result['task_id']
        self.assertEqual((task / 'command.md').read_bytes(), self.inbox.read_bytes())
        self.assertEqual((task / 'command.md').stat().st_mode & 0o222, 0)
        self.assertTrue((task / 'instructions').is_dir())
        self.assertEqual(self.request()['status'], 'DUPLICATE')
        self.assertEqual(len(self.service.observer.calls), 1)
        self.assertEqual(self.service.observer.calls[0][1]['threadId'], 'thread')

    def test_invalid_eof(self):
        self.inbox.write_text('do something')
        self.assertEqual(self.request()['status'], 'INVALID_EOF')
        self.assertEqual(self.service.observer.calls, [])

    def test_concurrent_dedup(self):
        results = []
        threads = [threading.Thread(target=lambda: results.append(self.request()['status'])) for _ in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()
        self.assertEqual(results.count('ACCEPTED'), 1)
        self.assertEqual(results.count('DUPLICATE'), 7)
        self.assertEqual(len(self.service.observer.calls), 1)

    def test_native_reserved_then_dorothy_busy(self):
        session = FakeObserver(self.service)
        self.service.native_request(session, {'id': 3, 'method': 'turn/start', 'params': {'threadId': 'thread'}})
        self.assertEqual(self.request()['status'], 'BUSY')
        self.assertFalse(list(self.service.tasks.iterdir()))

    def test_dorothy_active_native_busy_no_steer(self):
        self.request()
        for method in ('turn/start', 'turn/steer', 'review/start', 'thread/shellCommand'):
            with self.subTest(method=method), self.assertRaises(Busy):
                self.service.native_request(FakeObserver(self.service), {'id': 3, 'method': method, 'params': {'threadId': 'thread'}})

    def test_native_own_steer_preserved(self):
        token = self.service.arbiter.reserve('USER', 'thread')
        self.service.arbiter.accepted(token, 'native')
        self.service.native_request(FakeObserver(self.service), {'id': 3, 'method': 'turn/steer', 'params': {'threadId': 'thread', 'expectedTurnId': 'native'}})
        self.assertEqual(self.request()['status'], 'BUSY')

    def test_turn_completion_records_terminal(self):
        result = self.request()
        event = {'method': 'turn/completed', 'params': {'threadId': 'thread', 'turn': {'id': 'delegated-turn', 'status': 'completed'}}}
        self.service.received(self.service.observer, event)
        self.assertEqual(self.service.arbiter.state, 'IDLE')
        state = json.loads((self.service.tasks / result['task_id'] / 'state.json').read_text())
        self.assertEqual(state['status'], 'COMPLETED')

    def test_approval_response_and_cancel_passthrough(self):
        self.request()
        session = FakeObserver(self.service)
        messages = [{'id': 'approval', 'result': {'decision': 'accept'}},
                    {'id': 4, 'method': 'turn/interrupt', 'params': {'threadId': 'thread', 'turnId': 'delegated-turn'}}]
        for message in messages:
            before = json.dumps(message)
            self.service.native_request(session, message)
            self.assertEqual(json.dumps(message), before)

    def test_server_approval_id_cannot_consume_client_request(self):
        session = FakeObserver(self.service)
        token = self.service.arbiter.reserve('USER', 'thread'); session.pending[1] = token
        self.service.received(session, {'id': 1, 'method': 'item/commandExecution/requestApproval', 'params': {'threadId': 'thread'}})
        self.assertEqual(session.pending[1], token)

    def test_null_rpc_result_does_not_break_passthrough(self):
        self.service.received(FakeObserver(self.service), {'id': 90, 'result': None})
        self.assertEqual(self.service.arbiter.state, 'IDLE')

    def test_completion_before_request_response(self):
        observer = self.service.observer
        token = self.service.arbiter.reserve('USER', 'thread'); observer.pending[7] = token
        self.service.received(observer, {'method': 'turn/started', 'params': {'threadId': 'thread', 'turn': {'id': 'fast'}}})
        self.service.received(observer, {'method': 'turn/completed', 'params': {'threadId': 'thread', 'turn': {'id': 'fast', 'status': 'completed'}}})
        self.service.received(observer, {'id': 7, 'result': {'turn': {'id': 'fast'}}})
        self.assertEqual(self.service.arbiter.state, 'IDLE')

    def test_dropped_response_durable_unknown(self):
        with patch.object(self.service.observer, 'call', side_effect=TimeoutError):
            result = self.request()
        self.assertEqual(result['status'], 'UNKNOWN_EFFECT')
        self.assertEqual(self.request()['status'], 'UNKNOWN_EFFECT')
        self.assertEqual(self.service.arbiter.state, 'UNKNOWN')

    def test_corrupt_snapshot_fails_closed(self):
        result = self.request(); p = self.service.tasks / result['task_id'] / 'command.md'
        p.chmod(0o600); p.write_text('corrupt')
        self.assertEqual(self.request()['status'], 'UNKNOWN_EFFECT')

    def test_fake_authority_and_path_rejected(self):
        for request in ({'action': 'trigger', 'source': 'USER'}, {'action': 'trigger', 'approval': True},
                        {'action': 'trigger', 'path': '/tmp/other'}, {'action': '[USER]'}):
            self.assertEqual(self.service.trigger(request, os.getuid())['status'], 'INVALID_PATH')
        self.assertEqual(self.service.trigger({'action': 'trigger'}, os.getuid()+1)['status'], 'SECURITY_ERROR')
        self.assertFalse(self.service.observer.calls)

    def test_symlink_and_mutable_other_user_write_rejected(self):
        other = self.root / 'other'; other.write_text('x\n\nEOF\n')
        self.inbox.unlink(); self.inbox.symlink_to(other)
        self.assertEqual(self.request()['status'], 'SECURITY_ERROR')
        self.inbox.unlink(); self.inbox.write_text('x\n\nEOF\n'); self.inbox.chmod(0o666)
        self.assertEqual(self.request()['status'], 'SECURITY_ERROR')

    def test_fixture_never_reads_real_inbox(self):
        with patch('trigger_service.inbox_bytes', side_effect=AssertionError('inbox read')):
            result = self.service.trigger({'action': 'fixture'}, os.getuid())
        self.assertEqual(result['status'], 'ACCEPTED')
        self.assertEqual((self.service.tasks / result['task_id'] / 'command.md').read_text(), FIXTURE)

    def test_protocol_objects_reject_malformed(self):
        for text in ('[]', 'null', '{', '{"id":true}', '{"method":1}'):
            with self.subTest(text=text), self.assertRaises(ValueError): rpc_object(text)


class FrameTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b = socket.socketpair()
        self.addCleanup(self.a.close); self.addCleanup(self.b.close)
        self.reader = Downstream(self.a)

    def frame(self, data, opcode=1, final=True):
        data = data.encode(); key = b'abcd'
        return bytes([(128 if final else 0) | opcode, 128 | len(data)]) + key + bytes(x ^ key[i%4] for i, x in enumerate(data))

    def test_fragmented_utf8_and_control(self):
        self.b.sendall(self.frame('한글', final=False) + self.frame('ping', opcode=9) + self.frame(' 완료', opcode=0))
        self.assertEqual(self.reader.recv(), '한글 완료')
        self.assertEqual(self.b.recv(99), b'\x8a\x04ping')

    def test_invalid_mask_and_opcode(self):
        self.b.sendall(b'\x81\x00')
        with self.assertRaises(ValueError): self.reader.recv()

    def test_binary_frame_rejected(self):
        self.b.sendall(self.frame('bad', opcode=2))
        with self.assertRaises(ValueError): self.reader.recv()

    def test_oversized_frame_rejected_before_read(self):
        self.b.sendall(b'\x81\xff'+struct.pack('!Q', 20*1024*1024))
        with self.assertRaises(ValueError): self.reader.recv()


class HandshakeTests(unittest.TestCase):
    def handshake(self, path):
        a,b=socket.socketpair()
        self.addCleanup(a.close);self.addCleanup(b.close)
        b.sendall((f'GET {path} HTTP/1.1\r\nHost: localhost\r\n'
                   'Connection: Upgrade\r\nUpgrade: websocket\r\n'
                   'Sec-WebSocket-Version: 13\r\n'
                   'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n\r\n').encode())
        downstream=accept_websocket(a)
        self.assertIsInstance(downstream,Downstream)
        self.assertTrue(b.recv(4096).startswith(b'HTTP/1.1 101 '))

    def test_native_0160_rpc_path(self): self.handshake('/rpc')
    def test_helper_root_path(self): self.handshake('/')
    def test_other_paths_fail_closed(self):
        for path in ('/other','/rpc?bypass=1','//rpc'):
            with self.subTest(path=path), self.assertRaises(ValueError): self.handshake(path)
