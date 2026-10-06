"""Best-effort, bounded, one-way voice events. No TTS imports or acknowledgments."""
import json
import os
from pathlib import Path
import socket
import threading
import time
import uuid
import weakref

PROTOCOL = 1
MAX_MESSAGE = 60 * 1024

def endpoint():
    return Path(os.environ.get('ENIKK_TTS_SOCKET',
        str(Path(os.environ.get('XDG_RUNTIME_DIR', '/run/user/' + str(os.getuid()))) / 'enikk-tts.sock')))

class Publisher:
    def __init__(self, thread):
        self.thread = thread
        self.producer = uuid.uuid4().hex
        self.sequence = 0
        self.socket = None
        self.cleanup = None
        self.lock = threading.Lock()
        self.dropped = 0
        self.pending_gap = 0

    def emit(self, event=None):
        # Never wait on a voice consumer or another publishing thread.
        if not self.lock.acquire(False):
            self.dropped += 1
            self.pending_gap += 1
            return False
        try:
            if event is not None:
                method = event.get('method')
                if method not in ('turn/started', 'turn/completed', 'item/started',
                                  'item/completed', 'item/agentMessage/delta'):
                    return False
                original = event.get('params', {})
                if original.get('threadId') != self.thread:
                    return False
                def item(value):
                    if value.get('type') not in ('agentMessage', 'userMessage'):
                        return None
                    return {k:value[k] for k in ('id','type','phase','text') if k in value}
                params = {k:original[k] for k in ('threadId','turnId','itemId','delta') if k in original}
                if 'item' in original:
                    selected = item(original['item'])
                    if selected is None: return False
                    params['item'] = selected
                if 'turn' in original:
                    turn = original['turn']
                    params['turn'] = {k:turn[k] for k in ('id','status') if k in turn}
                    # Completed items arrived through item/completed; no bulk snapshots.
                    params['turn']['items'] = []
                event = {'method':method, 'params':params}
            self.sequence += 1 + self.pending_gap
            self.pending_gap = 0
            if event is not None:
                params = event['params']
                text = params.get('delta', params.get('item', {}).get('text', ''))
                if not isinstance(text, str) or len(text) > MAX_MESSAGE:
                    self.dropped += 1
                    return False
            message = {'protocol': PROTOCOL, 'producer': self.producer,
                       'sequence': self.sequence, 'thread': self.thread,
                       'sent_ns': time.monotonic_ns(), 'event': event}
            data = json.dumps(message, ensure_ascii=False).encode()
            if len(data) > MAX_MESSAGE:
                self.dropped += 1
                return False
            if self.socket is None:
                self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
                self.socket.setblocking(False)
                self.cleanup = weakref.finalize(self, self.socket.close)
            self.socket.sendto(data, str(endpoint()))
            return True
        except (OSError, ValueError, TypeError, AttributeError):
            self.dropped += 1
            return False
        finally:
            self.lock.release()

    def close(self):
        if self.cleanup: self.cleanup()
