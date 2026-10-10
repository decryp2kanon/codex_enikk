"""Explicit opt-in live probe: private CODEX_HOME, disposable thread, no production restart."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from trigger_transport import connect
from trigger_service import Service, bind_local, native_client

parser = argparse.ArgumentParser()
parser.add_argument('--codex', required=True)
parser.add_argument('--auth', required=True)
args = parser.parse_args()
root = Path(tempfile.mkdtemp(prefix='enikk-guard-live-'))
root.chmod(0o700)
home = root/'home'; home.mkdir(mode=0o700)
ch = home/'.codex'; ch.mkdir(mode=0o700)
shutil.copyfile(args.auth, ch/'auth.json'); (ch/'auth.json').chmod(0o600)
(ch/'config.toml').write_text('model = "gpt-6.1-sol"\nmodel_reasoning_effort = "low"\napproval_policy = "never"\nsandbox_mode = "read-only"\ncheck_for_update_on_startup = false\n')
env = os.environ | {'HOME': str(home), 'CODEX_HOME': str(ch), 'XDG_STATE_HOME': str(root/'state'), 'XDG_CONFIG_HOME': str(root/'config')}
identity = 0

def call(ws, method, params):
    global identity
    identity += 1; key = identity
    ws.send(json.dumps({'id': key, 'method': method, 'params': params}))
    while True:
        event = json.loads(ws.recv())
        if event.get('id') == key:
            return event

def initialize(ws):
    result = call(ws, 'initialize', {'clientInfo': {'name': 'enikk_guard_live_fixture', 'version': '1'}, 'capabilities': {'experimentalApi': True}})
    assert 'error' not in result, 'initialize failed'
    ws.send(json.dumps({'method': 'initialized'}))

def turn(ws, tid, prompt):
    result = call(ws, 'turn/start', {'threadId': tid, 'input': [{'type': 'text', 'text': prompt}]})
    assert 'error' not in result, 'normal turn rejected'
    text = []
    while True:
        event = json.loads(ws.recv()); params = event.get('params') or {}
        if event.get('method') == 'item/completed':
            item = params.get('item') or {}
            if item.get('type') == 'agentMessage': text.append(item.get('text',''))
        if event.get('method') == 'turn/completed':
            assert params['turn']['status'] == 'completed', 'live model turn failed'
            return '\n'.join(text)

try:
    tid = None
    for stage in (1, 2):
        sock = root/f'app-{stage}.sock'
        log = (root/f'app-{stage}.log').open('wb')
        process = subprocess.Popen([args.codex, 'app-server', '--listen', 'unix://'+str(sock)], env=env, cwd=root, stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        service = listener = ws = None
        try:
            deadline = time.monotonic()+25
            while not sock.exists() and process.poll() is None and time.monotonic()<deadline: time.sleep(.1)
            assert sock.exists(), 'isolated app-server unavailable'
            if tid is None:
                seed = connect(str(sock)); seed.settimeout(120); initialize(seed)
                result = call(seed,'thread/start',{'cwd':str(root),'approvalPolicy':'never','sandbox':'read-only'})
                assert 'error' not in result, 'disposable thread creation failed'
                tid = result['result']['thread']['id']
                seeded = turn(seed,tid,'This is an isolated fixture. Reply only READY and do not use tools.')
                assert 'READY' in seeded, 'seed turn failed'
                seed.close()
            service = Service(str(sock),tid,root/f'proxy-{stage}',root/'inbox')
            service.initialize()
            endpoint = root/f'native-{stage}.sock'; listener=bind_local(endpoint)
            def accept():
                while not service.stopped.is_set():
                    try: client,_=listener.accept()
                    except TimeoutError: continue
                    except OSError: break
                    threading.Thread(target=native_client,args=(service,client),daemon=True).start()
            threading.Thread(target=accept,daemon=True).start()
            ws=connect(str(endpoint));ws.settimeout(150);initialize(ws)
            resumed=call(ws,'thread/resume',{'threadId':tid})
            assert resumed.get('result',{}).get('thread',{}).get('id')==tid, 'resume changed thread'
            if stage==1:
                for mode in ('plan','default'):
                    changed=call(ws,'thread/settings/update',{'threadId':tid,'model':'gpt-6.1-sol','effort':'low','collaborationMode':{'mode':mode,'settings':{'model':'gpt-6.1-sol','reasoning_effort':'low','developer_instructions':None}}})
                    assert 'error' not in changed, 'normal model/plan update rejected'
                for method,params in [('memory/reset',{}),('config/value/write',{'keyPath':'personality','value':'none','mergeStrategy':'replace'}),('thread/delete',{'threadId':tid})]:
                    denied=call(ws,method,params);assert denied.get('error',{}).get('code')==-32010, 'guard did not reject'
                reply=turn(ws,tid,'This is an isolated continuity test. Remember the token GUARD_ORCHID_927. Reply only GUARD_LIVE_OK. Do not use any tools.')
                assert 'GUARD_LIVE_OK' in reply, 'unexpected initial model response'
                print('LIVE stage 1: denied requests, same-thread model response PASS',flush=True)
            else:
                reply=turn(ws,tid,'What was the test token I asked you to remember? Reply only that token, and do not use tools.')
                assert 'GUARD_ORCHID_927' in reply, 'resume did not preserve test context'
                print('LIVE stage 2: isolated server restart, same ID and recalled token PASS',flush=True)
        finally:
            if ws: ws.close()
            if service:
                service.stopped.set(); service.queue_wakeup.set(); service.voice.close()
                for session in list(service.sessions): session.close()
            if listener: listener.close()
            process.terminate()
            try: process.wait(8)
            except subprocess.TimeoutExpired: process.kill();process.wait()
            log.close()
    (root/'result.json').write_text(json.dumps({'status':'PASS','thread_id':tid,'stages':2}))
    print('LIVE PASS; evidence '+str(root),flush=True)
finally:
    (ch/'auth.json').unlink(missing_ok=True)
