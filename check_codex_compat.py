#!/usr/bin/env python3
"""Isolated Codex/Enikk interface smoke test. Never starts a TTS worker."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pty
import re
import select
import shutil
import signal
import socket
import sqlite3
import struct
import subprocess
import sys
import tempfile
import termios
import threading
import time
import fcntl

ROOT = Path(__file__).resolve().parent
CLI_OPTIONS = ('--remote', '--no-daemon', '--dangerously-bypass-approvals-and-sandbox', '--no-alt-screen')
FIELDS = {
    'state_5.sqlite': {'threads': {'id', 'rollout_path'}},
    'thread_history_1.sqlite': {
        'thread_items': {'thread_id', 'rollout_ordinal', 'item_type', 'item_json'},
        'thread_history_projection_state': {'thread_id', 'next_rollout_byte_offset'}},
}


class Failure(Exception):
    def __init__(self, expected, observed):
        self.expected, self.observed = expected, observed
        super().__init__(f'expected {expected}; observed {observed}')


def require(condition, expected, observed):
    if not condition:
        raise Failure(expected, observed)


def validate_binary(value):
    p = Path(value).expanduser().resolve()
    require(p.is_file() and os.access(p, os.X_OK), 'executable candidate file', str(p))
    return p


def parse_version(text):
    match = re.fullmatch(r'codex-cli (\d+\.\d+\.\d+(?:[-+][\w.-]+)?)', text.strip())
    require(match is not None, 'codex-cli VERSION', text.strip())
    return match[1]


def validate_cli(text):
    missing = [x for x in CLI_OPTIONS if x not in text]
    require(not missing, list(CLI_OPTIONS), {'missing': missing})


def schema_fields(connection, tables):
    observed = {}
    for table, fields in tables.items():
        columns = {r[1] for r in connection.execute(f'PRAGMA table_info("{table}")')}
        observed[table] = sorted(columns)
        require(fields <= columns, {table: sorted(fields)}, {table: sorted(columns)})
    return observed


def validate_stream(events, jobs):
    delta = next((i for i,e in enumerate(events) if e.get('method') == 'item/agentMessage/delta'), None)
    completed = next((i for i,e in enumerate(events) if e.get('method') == 'item/completed'
                      and e.get('params', {}).get('item', {}).get('type') == 'agentMessage'), None)
    require(delta is not None and completed is not None and delta < completed,
            'agent delta before agent item completion', {'delta':delta, 'completion':completed})
    require(jobs and jobs[0][0] < completed, 'first sentence submitted before item completion',
            {'first_sentence':jobs[0][0] if jobs else None, 'completion':completed})
    require(any(e.get('method') == 'turn/completed' and e['params']['turn']['status'] == 'completed' for e in events),
            'completed turn', 'missing successful completion')


def fingerprint(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else hashlib.sha256(stream.read()).hexdigest()


class Checks:
    def __init__(self):
        self.checks = []
        self.current = None

    def check(self, name, action):
        self.current = name
        start = time.monotonic()
        try:
            detail = action()
        except Exception as exc:
            self.checks.append(dict(name=name, status='FAIL', seconds=time.monotonic()-start,
                                   expected=getattr(exc,'expected','successful bounded check'),
                                   observed=getattr(exc,'observed',f'{type(exc).__name__}: {exc}')))
            raise
        self.checks.append(dict(name=name, status='PASS', seconds=time.monotonic()-start, detail=detail))
        return detail


class Client:
    def __init__(self, endpoint):
        import websocket
        raw = socket.socket(socket.AF_UNIX)
        raw.settimeout(10)
        try:
            raw.connect(str(endpoint))
            self.ws = websocket.create_connection('ws://localhost/', socket=raw, timeout=10)
        except BaseException:
            raw.close()
            raise
        self.serial = 0
        self.events = []
        try:
            self.call('initialize', {'clientInfo':{'name':'enikk_compat', 'version':'1'}})
            self.ws.send(json.dumps({'method':'initialized'}))
        except BaseException:
            self.ws.close()
            raise

    def receive(self, timeout=30):
        self.ws.settimeout(timeout)
        e = json.loads(self.ws.recv())
        if 'method' in e:
            self.events.append(e)
            if 'id' in e:
                # Never auto-approve arbitrary model-generated commands.
                self.ws.send(json.dumps({'id':e['id'], 'result':{'decision':'decline'}}))
        return e

    def call(self, method, params):
        self.serial += 1
        self.ws.send(json.dumps({'id':self.serial,'method':method,'params':params}))
        end = time.monotonic()+30
        while time.monotonic() < end:
            e = self.receive(max(.01,end-time.monotonic()))
            if e.get('id') == self.serial and 'method' not in e:
                require('result' in e, method+' result', e.get('error'))
                return e['result']
        raise TimeoutError(method)

    def finish_turn(self, turn=None, timeout=75):
        for e in reversed(self.events):
            if turn is not None and e.get('method') == 'turn/completed' and e['params']['turn']['id'] == turn:
                return e['params']['turn']
        end = time.monotonic()+timeout
        while time.monotonic() < end:
            e = self.receive(max(.01,end-time.monotonic()))
            if e.get('method') == 'turn/completed' and (turn is None or e['params']['turn']['id'] == turn):
                return e['params']['turn']
        raise TimeoutError('turn completion')


def smoke(binary, root, environment, model, checks):
    from latest import recent_bytes, atomic_write
    from persistence import snapshots, validate_rollouts
    endpoint = root/'server.sock'
    home = root/'codex-home'
    processes = []
    client = None
    master = None
    drain = None
    stop = threading.Event()
    log = (root/'server.log').open('wb')
    def run(args, timeout=15):
        p = subprocess.run([str(binary), *args], env=environment, cwd=root,
                           stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=timeout)
        require(p.returncode == 0, 'command exit 0', {'args':args,'exit':p.returncode,'stderr':p.stderr[-1000:]})
        return p.stdout
    try:
        checks.check('CLI', lambda: validate_cli(run(['resume','--help'])))
        def start():
            p = subprocess.Popen([str(binary),'-c','notify=[]','-c','check_for_update_on_startup=false',
                                  'app-server','--listen','unix://'+str(endpoint)],env=environment,cwd=root,
                                  stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
            processes.append(p)
            end=time.monotonic()+20
            while not endpoint.exists() and p.poll() is None and time.monotonic()<end:time.sleep(.03)
            require(endpoint.exists() and p.poll() is None,'private Unix socket ready',p.poll())
            return {'pid':p.pid,'socket':str(endpoint)}
        checks.check('app-server', start)
        client = checks.check('websocket', lambda: Client(endpoint))
        checks.checks[-1]['detail'] = 'Unix socket + WebSocket initialize/initialized'
        params={'cwd':str(root),'approvalPolicy':'never','sandbox':'read-only',
                'developerInstructions':'This is a compatibility smoke test. Follow the short user requests exactly. Only run pwd when explicitly requested; otherwise do not use tools.'}
        if model:params['model']=model
        created=checks.check('thread',lambda:client.call('thread/start',params))
        tid=created['thread']['id'];checks.checks[-1]['detail']={'id':tid}
        # An empty thread has no rollout yet in 0.158.0. Persist a tiny completed
        # turn before testing the wrapper's existing-thread resume contract.
        def seed():
            result=client.call('turn/start',{'threadId':tid,'effort':'low','input':[{'type':'text','text':'준비 완료라고만 답해.'}]})
            result=client.finish_turn(result['turn']['id'])
            require(result['status']=='completed','persisted seed turn',result['status'])
            return result['status']
        checks.check('thread persistence seed',seed)
        resumed=checks.check('resume',lambda:client.call('thread/resume',{'threadId':tid}))
        require(resumed['thread']['id']==tid,tid,resumed['thread']['id']);checks.checks[-1]['detail']={'id':tid}
        client.events.clear()
        spec=importlib.util.spec_from_file_location('compat_stream',ROOT/'tts/yuki-codex-stream.py')
        stream=importlib.util.module_from_spec(spec);spec.loader.exec_module(stream)
        jobs=[]
        accumulator=stream.Accumulator(root/'sentences',tid,lambda job:jobs.append((len(client.events)-1,job)))
        prompt='도구 없이 다음 세 문장을 그대로 출력해. 오늘은 조용한 산책을 시작합니다. 나무 사이로 부드러운 바람이 불어옵니다. 마지막까지 차분하게 이야기를 이어갑니다.'
        master,slave=pty.openpty()
        fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',40,120,0,0))
        try:
            native=subprocess.Popen([str(binary),'-c','check_for_update_on_startup=false','resume',tid,
                                     '--remote','unix://'+str(endpoint),'--no-alt-screen',prompt],
                                    env=environment|{'TERM':'xterm-256color'},cwd=root,
                                    stdin=slave,stdout=slave,stderr=slave,start_new_session=True)
            processes.append(native)
        finally:os.close(slave)
        def consume_terminal():
            while not stop.is_set():
                try:
                    if not select.select([master],[],[],.1)[0]:continue
                    b=os.read(master,65536)
                    if not b:return
                    for query,answer in [(b'\x1b[6n',b'\x1b[1;1R'),(b'\x1b]11;?',b'\x1b]11;rgb:0000/0000/0000\x1b\\'),(b'\x1b]10;?',b'\x1b]10;rgb:ffff/ffff/ffff\x1b\\')]:
                        if query in b:os.write(master,answer)
                except OSError:return
        drain=threading.Thread(target=consume_terminal,daemon=True);drain.start()
        def native_stream():
            end=time.monotonic()+90
            while time.monotonic()<end:
                require(native.poll() is None,'native TUI alive',native.poll())
                e=client.receive(max(.01,end-time.monotonic()));accumulator.event(e)
                if e.get('method')=='turn/completed':break
            else:raise TimeoutError('native TUI streaming')
            validate_stream(client.events,jobs)
            return {'sentences':len(jobs),'native_alive':native.poll() is None,'incremental_before_completion':True}
        checks.check('remote/delta/sentence/completion',native_stream)
        def tool():
            begin=len(client.events)
            result=client.call('turn/start',{'threadId':tid,'input':[{'type':'text','text':'Run pwd exactly once using the shell tool, then reply done.'}]})
            result=client.finish_turn(result['turn']['id'])
            commands=[e['params']['item'] for e in client.events[begin:] if e.get('method')=='item/completed' and e.get('params',{}).get('item',{}).get('type')=='commandExecution']
            require(result['status']=='completed' and commands,'completed commandExecution event',result['status'])
            require(any(c.get('exitCode')==0 for c in commands),'successful harmless tool command',[(c.get('status'),c.get('exitCode')) for c in commands])
            return {'events':len(commands),'success':True}
        checks.check('tool',tool)
        def interrupt():
            result=client.call('turn/start',{'threadId':tid,'input':[{'type':'text','text':'Write a long explanation of trees in 100 sentences. Do not use tools.'}]})
            turn=result['turn']['id']
            # turn/start can acknowledge a queued turn before it is interruptible.
            # Wait for actual generation, not a sleep or an assumed state.
            end=time.monotonic()+45
            while time.monotonic()<end:
                e=client.receive(max(.01,end-time.monotonic()))
                if e.get('method')=='item/agentMessage/delta' and e.get('params',{}).get('turnId')==turn:
                    break
            else:raise TimeoutError('interruptible generation')
            client.call('turn/interrupt',{'threadId':tid,'turnId':turn})
            already=[e['params']['turn'] for e in client.events if e.get('method')=='turn/completed' and e['params']['turn']['id']==turn]
            result=already[-1] if already else client.finish_turn(turn,20)
            require(result['status']=='interrupted','interrupted turn',result['status'])
            return result['status']
        checks.check('interruption',interrupt)
        def persistence():
            observed={}
            for db,tables in FIELDS.items():
                path=home/db;require(path.is_file(),db,'missing')
                with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True) as c:
                    observed[db]=schema_fields(c,tables)
                    if db=='state_5.sqlite':
                        row=c.execute('SELECT rollout_path FROM threads WHERE id=?',(tid,)).fetchone()
                        require(row and Path(row[0]).is_relative_to(home) and Path(row[0]).is_file(),'isolated rollout path',row)
            directory=root/'snapshots';directory.mkdir()
            snapshots(home,directory)
            sizes={'codex/'+str(p.relative_to(home)):p.stat().st_size for p in (home/'sessions').rglob('*.jsonl')}
            validate_rollouts(directory,home,sizes)
            return observed
        checks.check('persistence/SQLite',persistence)
        def latest():
            with sqlite3.connect((home/'thread_history_1.sqlite').as_uri()+'?mode=ro',uri=True) as c:data=recent_bytes(c,tid)
            require(b'[USER]' in data and b'[ENIKK]' in data,'USER and ENIKK text',len(data))
            require('오늘은 조용한 산책을 시작합니다.' in data.decode(),'completed assistant text','not found')
            atomic_write(root/'codex-latest.txt',data)
            return {'bytes':len(data),'isolated_output':True}
        checks.check('latest parser',latest)
        def approval():
            out=root/'schema';run(['app-server','generate-json-schema','--out',str(out)],20)
            requests=json.loads((out/'ServerRequest.json').read_text())
            require('item/commandExecution/requestApproval' in json.dumps(requests),'command approval request method','missing')
            response=json.loads((out/'CommandExecutionRequestApprovalResponse.json').read_text())
            require('decision' in response.get('required',[]) and 'accept' in json.dumps(response) and 'decline' in json.dumps(response),'approval decision response schema','missing')
            return {'level':'protocol-only','reason':'Harmless pwd requires no approval; no risky/escalated command is fabricated.'}
        checks.check('approval',approval)
        return tid
    finally:
        if client:client.ws.close()
        stop.set()
        for p in reversed(processes):
            try:os.killpg(p.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        for p in processes:
            try:p.wait(3)
            except subprocess.TimeoutExpired:
                try:os.killpg(p.pid,signal.SIGKILL)
                except ProcessLookupError:pass
                p.wait(3)
        if drain:drain.join(1)
        if master is not None:os.close(master)
        log.close()


def execute(args):
    from enikk import owned_processes, process_table, SUPPORTED_CODEX_VERSIONS
    started=time.monotonic();checks=Checks();report={'binary':str(args.binary),'version':None,'checks':checks.checks,'failure_reason':None}
    root=None;binary=None;before=None;previous=signal.getsignal(signal.SIGALRM)
    children_before=set(process_table())
    stable_entry=shutil.which('codex')
    stable=Path(stable_entry).resolve() if stable_entry else None
    stable_hash=fingerprint(stable) if stable and stable.is_file() else None
    report['stable_binary']=str(stable) if stable else None
    def expired(*_):raise TimeoutError('checker total runtime limit')
    signal.signal(signal.SIGALRM,expired);signal.alarm(args.timeout)
    try:
        binary=checks.check('binary',lambda:validate_binary(args.binary));checks.checks[-1]['detail']=str(binary)
        before=fingerprint(binary)
        report['binary_sha256']=before
        with owned_processes(), tempfile.TemporaryDirectory(prefix='enikk-compat-') as directory:
            root=Path(directory);home=root/'codex-home';home.mkdir();(root/'home').mkdir()
            report['temporary_CODEX_HOME']=str(home);report['temporary_socket']=str(root/'server.sock')
            environment={k:v for k,v in os.environ.items() if not k.startswith(('CODEX_','XDG_'))}
            environment.update(CODEX_HOME=str(home),HOME=str(root/'home'),XDG_CACHE_HOME=str(root/'cache'),XDG_CONFIG_HOME=str(root/'config'),XDG_STATE_HOME=str(root/'state'))
            auth=Path(args.auth_file).expanduser() if args.auth_file else Path(os.environ.get('CODEX_HOME',Path.home()/'.codex'))/'auth.json'
            if auth.is_file():
                shutil.copyfile(auth,home/'auth.json');(home/'auth.json').chmod(0o600)
            def version():
                p=subprocess.run([str(binary),'--version'],env=environment,cwd=root,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=5)
                require(p.returncode==0,'version exit 0',p.returncode)
                return parse_version(p.stdout)
            report['version']=checks.check('version',version)
            if stable:
                stable_version=subprocess.run([str(stable),'--version'],env=environment,cwd=root,
                                              stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=5)
                report['stable_version']=stable_version.stdout.strip()
            smoke(binary,root,environment,args.model,checks)
            pins=SUPPORTED_CODEX_VERSIONS
            checks.check('wrapper version gate',lambda:require(report['version'] in pins,{'allowed_versions':sorted(pins)},report['version']))
    except (Exception,KeyboardInterrupt,SystemExit) as exc:
        report['failure_reason']=f'{type(exc).__name__}: {exc}'
        if not checks.checks or checks.checks[-1]['status']!='FAIL':
            checks.checks.append({'name':checks.current or 'checker','status':'FAIL','expected':'successful isolated execution','observed':report['failure_reason'],'seconds':0})
    finally:
        signal.alarm(0);signal.signal(signal.SIGALRM,previous)
        remaining=[pid for pid,(parent,_) in process_table().items() if parent==os.getpid() and pid not in children_before]
        clean=(root is None or not root.exists()) and not remaining
        checks.checks.append(dict(name='shutdown/cleanup',status='PASS' if clean else 'FAIL',seconds=0,detail={'temporary_removed':root is None or not root.exists(),'remaining_children':remaining}))
        unchanged=(binary is not None and binary.is_file() and before==fingerprint(binary)
                   and Path(args.binary).expanduser().resolve()==binary)
        stable_unchanged=(stable is None or (stable.is_file() and fingerprint(stable)==stable_hash
                                            and Path(stable_entry).resolve()==stable))
        report['stable_unchanged']=stable_unchanged
        unchanged=unchanged and stable_unchanged
        checks.checks.append(dict(name='binary unchanged/failure isolation',status='PASS' if unchanged else 'FAIL',seconds=0,detail=unchanged))
    report['result']='COMPATIBLE' if all(c['status']=='PASS' for c in checks.checks) else 'INCOMPATIBLE'
    report['runtime_seconds']=time.monotonic()-started
    report['slowest_check']=max(checks.checks,key=lambda c:c['seconds'])['name']
    return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary',help='explicit candidate binary path; never installs or updates it')
    parser.add_argument('--model',help='optional model available to this account')
    parser.add_argument('--auth-file',help='read-only login source; only this credential file is copied into the temporary home')
    parser.add_argument('--timeout',type=int,default=240,help='overall timeout, 30–300 seconds (default 240)')
    parser.add_argument('--json',action='store_true')
    args=parser.parse_args(argv)
    parser.error('timeout must be between 30 and 300') if not 30<=args.timeout<=300 else None
    result=execute(args)
    if args.json:print(json.dumps(result,ensure_ascii=False,indent=2))
    else:
        for c in result['checks']:print(c['status'],c['name'],'' if c['status']=='PASS' else json.dumps(c,ensure_ascii=False))
        print('RESULT:',result['result']);print(f"runtime={result['runtime_seconds']:.3f}s slowest={result['slowest_check']}")
    return 0 if result['result']=='COMPATIBLE' else 1


if __name__=='__main__':
    raise SystemExit(main())
