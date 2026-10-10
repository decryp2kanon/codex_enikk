"""Isolated opt-in server probe; never resumes a production thread."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from trigger_transport import connect

parser = argparse.ArgumentParser()
parser.add_argument('--codex', required=True)
parser.add_argument('--auth', required=True)
args = parser.parse_args()
root = Path(tempfile.mkdtemp(prefix='enikk-voice-guard-live-'))
root.chmod(0o700)
home = root / 'home'
home.mkdir(mode=0o700)
shutil.copyfile(args.auth, home / 'auth.json')
(home / 'auth.json').chmod(0o600)
(home / 'config.toml').write_text('model = "gpt-6.1-sol"\nmodel_reasoning_effort = "low"\napproval_policy = "never"\nsandbox_mode = "read-only"\ncheck_for_update_on_startup = false\n')
env = os.environ | {'CODEX_HOME': str(home), 'CODEX_ENIKK_DISABLE_REALTIME': '1',
                    'XDG_STATE_HOME': str(root / 'state'), 'XDG_CONFIG_HOME': str(root / 'config')}
message = '나 유키짱의 대화 맥락과 기억 연속성을 보호하려고 실시간 음성대화를 막아뒀어. 텍스트로 이야기해 줘.'
identity = 0
result = {'root': str(root), 'status': 'STARTED'}

def call(ws, method, params):
    global identity
    identity += 1
    key = identity
    ws.send(json.dumps({'id': key, 'method': method, 'params': params}))
    while True:
        event = json.loads(ws.recv())
        if event.get('id') == key:
            return event

def initialize(ws):
    response = call(ws, 'initialize', {'clientInfo': {'name': 'voice_guard_fixture', 'version': '1'},
                                     'capabilities': {'experimentalApi': True}})
    assert 'error' not in response, response
    ws.send(json.dumps({'method': 'initialized'}))

def turn(ws, tid, prompt):
    response = call(ws, 'turn/start', {'threadId': tid, 'input': [{'type': 'text', 'text': prompt}]})
    assert 'error' not in response, response
    text = []
    while True:
        event = json.loads(ws.recv())
        params = event.get('params') or {}
        if event.get('method') == 'item/completed':
            item = params.get('item') or {}
            if item.get('type') == 'agentMessage':
                text.append(item.get('text', ''))
        if event.get('method') == 'turn/completed':
            assert params['turn']['status'] == 'completed', params
            return '\n'.join(text)

try:
    tid = None
    for stage in (1, 2):
        endpoint = root / f'server-{stage}.sock'
        with (root / f'server-{stage}.log').open('wb') as log:
            process = subprocess.Popen([args.codex, 'app-server', '--listen', 'unix://' + str(endpoint)],
                                       env=env, cwd=root, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=log, start_new_session=True)
            ws = None
            try:
                deadline = time.monotonic() + 30
                while not endpoint.exists() and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(.05)
                assert endpoint.exists(), 'isolated server failed to start'
                ws = connect(endpoint)
                ws.settimeout(150)
                initialize(ws)
                if stage == 1:
                    response = call(ws, 'thread/start', {'cwd': str(root), 'approvalPolicy': 'never', 'sandbox': 'read-only'})
                    tid = response['result']['thread']['id']
                else:
                    response = call(ws, 'thread/resume', {'threadId': tid})
                    assert response['result']['thread']['id'] == tid, response
                for transport in (None, {'type': 'webrtc', 'sdp': 'test'},
                                  {'type': 'existingCall', 'callId': 'test'}):
                    response = call(ws, 'thread/realtime/start', {'threadId': tid, 'outputModality': 'audio', 'transport': transport})
                    assert response.get('error') == {'code': -32600, 'message': message}, response
                if stage == 1:
                    reply = turn(ws, tid, 'Isolated fixture. Remember token VOICE_GUARD_ORCHID_927. Reply only VOICE_GUARD_ORCHID_927. Do not use tools.')
                else:
                    reply = turn(ws, tid, 'Reply only with the token from our previous message. Do not use tools.')
                assert 'VOICE_GUARD_ORCHID_927' in reply, reply
                result[f'stage_{stage}'] = {'thread_id': tid, 'voice_rejected': 3, 'text_response': reply}
            finally:
                if ws is not None:
                    ws.close()
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
    result['status'] = 'PASS'
except BaseException as error:
    result['status'] = 'FAIL'
    result['error'] = str(error)
    raise
finally:
    (root / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False))
