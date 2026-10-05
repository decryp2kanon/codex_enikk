"""Shared reservation for native and delegated submissions (no network effects)."""
import threading
import uuid


class Busy(Exception):
    pass


class UnknownEffect(Exception):
    pass


class Arbiter:
    def __init__(self, thread_id):
        self.thread_id = thread_id
        self.lock = threading.RLock()
        self.state = 'UNKNOWN'
        self.owner = self.token = self.turn = None

    def initialize(self, thread):
        with self.lock:
            if thread.get('id') != self.thread_id:
                raise UnknownEffect('thread identity mismatch')
            status = thread.get('status', {}).get('type')
            if status != 'idle':
                raise Busy('thread not authoritatively idle')
            if self.token is not None:
                raise UnknownEffect('unresolved reservation')
            self.state = 'IDLE'

    def reserve(self, owner, thread_id):
        with self.lock:
            if owner not in ('USER', 'DOROTHY') or thread_id != self.thread_id:
                raise UnknownEffect('invalid submission identity')
            if self.state == 'UNKNOWN':
                raise UnknownEffect('unreconciled transport state')
            if self.state != 'IDLE':
                raise Busy(self.state)
            self.owner, self.token = owner, uuid.uuid4().hex
            self.turn = None
            self.state = owner + '_RESERVED'
            return self.token

    def accepted(self, token, turn_id):
        with self.lock:
            if self.owner not in ('USER', 'DOROTHY') or token != self.token or not turn_id:
                self.state = 'UNKNOWN'
                raise UnknownEffect('response reservation mismatch')
            if self.turn is not None and self.turn != turn_id:
                self.state = 'UNKNOWN'
                raise UnknownEffect('turn identity mismatch')
            self.turn = turn_id
            self.state = self.owner + '_ACTIVE'

    def completed(self, thread_id, turn_id):
        with self.lock:
            if (self.state.endswith('_ACTIVE') or self.state == 'UNKNOWN') and self.turn is not None and thread_id == self.thread_id and turn_id == self.turn:
                self.state = 'IDLE'
                self.owner = self.token = self.turn = None
                return True
            return False

    def lost(self):
        with self.lock:
            self.state = 'UNKNOWN'

    def rejected_before_effect(self, token):
        with self.lock:
            if token != self.token or not self.state.endswith('_RESERVED'):
                self.lost()
                raise UnknownEffect('cannot clear reservation')
            self.owner = self.token = self.turn = None
            self.state = 'IDLE'
