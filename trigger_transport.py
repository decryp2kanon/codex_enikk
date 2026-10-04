"""Bounded local WebSocket transport; no TCP listener or terminal access."""
import base64
import hashlib
import json
import os
import socket
import struct
import threading

MAX_MESSAGE = 16 * 1024 * 1024


def peer_uid(sock):
    return struct.unpack('3i', sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]


def exact(sock, size):
    result = bytearray()
    while len(result) < size:
        part = sock.recv(size - len(result))
        if not part:
            raise EOFError('connection closed')
        result.extend(part)
    return bytes(result)


def accept_websocket(sock):
    if peer_uid(sock) != os.getuid():
        raise ValueError('wrong peer user')
    header = bytearray()
    while not header.endswith(b'\r\n\r\n'):
        if len(header) >= 16384:
            raise ValueError('oversized handshake')
        header.extend(exact(sock, 1))
    lines = bytes(header).decode('ascii').split('\r\n')
    # Codex 0.160 native remote client uses /rpc; the helper uses /.
    if lines[0] not in ('GET / HTTP/1.1', 'GET /rpc HTTP/1.1'):
        raise ValueError('unsupported handshake')
    headers = {}
    for line in lines[1:]:
        if not line:
            continue
        key, value = line.split(':', 1)
        key = key.lower()
        if key in headers:
            raise ValueError('duplicate header')
        headers[key] = value.strip()
    key = headers.get('sec-websocket-key', '')
    if (headers.get('upgrade', '').lower() != 'websocket' or
            'upgrade' not in headers.get('connection', '').lower().split(', ') or
            headers.get('sec-websocket-version') != '13' or
            len(base64.b64decode(key, validate=True)) != 16):
        raise ValueError('invalid websocket handshake')
    # No extensions selected: compressed/RSV frames must be rejected.
    accept = base64.b64encode(hashlib.sha1((key + '258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
    sock.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: ' + accept + b'\r\n\r\n')
    return Downstream(sock)


class Downstream:
    def __init__(self, sock):
        self.sock = sock
        self.lock = threading.Lock()

    def send(self, text, opcode=1):
        data = text.encode('utf-8') if isinstance(text, str) else text
        size = len(data)
        head = bytes([128 | opcode])
        if size < 126:
            head += bytes([size])
        elif size < 65536:
            head += b'\x7e' + struct.pack('!H', size)
        else:
            head += b'\x7f' + struct.pack('!Q', size)
        with self.lock:
            self.sock.sendall(head + data)

    def recv(self):
        parts = bytearray()
        fragmented = False
        while True:
            a, b = exact(self.sock, 2)
            final, opcode = bool(a & 128), a & 15
            if a & 112 or not b & 128:
                raise ValueError('unsupported flags or unmasked client frame')
            size = b & 127
            if size == 126:
                size = struct.unpack('!H', exact(self.sock, 2))[0]
                if size < 126: raise ValueError('noncanonical frame length')
            elif size == 127:
                size = struct.unpack('!Q', exact(self.sock, 8))[0]
                if size < 65536: raise ValueError('noncanonical frame length')
            if size > MAX_MESSAGE or len(parts) + size > MAX_MESSAGE:
                raise ValueError('oversized message')
            if opcode >= 8 and (not final or size > 125):
                raise ValueError('invalid control frame')
            mask = exact(self.sock, 4)
            payload = exact(self.sock, size)
            data = bytes(c ^ mask[i % 4] for i, c in enumerate(payload))
            if opcode == 8:
                self.send(data, 8)
                raise EOFError('peer closed')
            if opcode == 9:
                self.send(data, 10)
                continue
            if opcode == 10:
                continue
            if opcode == 1 and not fragmented:
                fragmented = True
            elif opcode != 0 or not fragmented:
                raise ValueError('invalid text/continuation frame')
            parts.extend(data)
            if final:
                return parts.decode('utf-8')

    def close(self):
        try: self.sock.shutdown(socket.SHUT_RDWR)
        except OSError: pass
        self.sock.close()


def connect(path):
    import websocket
    sock = socket.socket(socket.AF_UNIX)
    sock.settimeout(10)
    try:
        sock.connect(str(path))
        if peer_uid(sock) != os.getuid():
            raise ValueError('wrong upstream peer')
        ws = websocket.create_connection('ws://localhost/', socket=sock, timeout=10)
        ws.settimeout(None)
        return ws
    except BaseException:
        sock.close()
        raise


def rpc_object(text):
    value = json.loads(text)
    if not isinstance(value, dict):
        raise ValueError('JSON-RPC object required')
    if 'method' in value and not isinstance(value['method'], str):
        raise ValueError('invalid method')
    if 'id' in value and (isinstance(value['id'], bool) or not isinstance(value['id'], (str, int))):
        raise ValueError('invalid id')
    return value
