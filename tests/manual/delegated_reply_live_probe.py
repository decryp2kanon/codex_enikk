"""Disposable live model roundtrip. Never resumes or restarts the real thread."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from trigger_transport import connect
from trigger_service import Service

parser=argparse.ArgumentParser()
parser.add_argument('--codex',required=True)
parser.add_argument('--auth',required=True)
a=parser.parse_args()
root=Path(tempfile.mkdtemp(prefix='enikk-delegated-reply-live-')); root.chmod(0o700)
print('Evidence directory:',root,flush=True)
home=root/'home'; ch=home/'.codex'; ch.mkdir(parents=True,mode=0o700)
shutil.copyfile(a.auth,ch/'auth.json'); (ch/'auth.json').chmod(0o600)
(ch/'config.toml').write_text('model="gpt-6.1-sol"\nmodel_reasoning_effort="low"\napproval_policy="never"\nsandbox_mode="read-only"\ncheck_for_update_on_startup=false\n')
env=os.environ | {'HOME':str(home),'CODEX_HOME':str(ch),'XDG_STATE_HOME':str(root/'state'),'XDG_CONFIG_HOME':str(root/'config')}
sock=root/'server.sock'; log=(root/'server.log').open('wb')
proc=subprocess.Popen([a.codex,'app-server','--listen','unix://'+str(sock)],env=env,cwd=root,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
seed=service=None
try:
    deadline=time.monotonic()+25
    while not sock.exists() and proc.poll() is None and time.monotonic()<deadline:time.sleep(.1)
    assert sock.exists(),'server not ready'
    seed=connect(str(sock)); seed.settimeout(90)
    def call(identity,method,params):
        seed.send(json.dumps({'id':identity,'method':method,'params':params}))
        while True:
            result=json.loads(seed.recv())
            if result.get('id')==identity:
                assert 'error' not in result,result.get('error')
                return result['result']
    call(1,'initialize',{'clientInfo':{'name':'delegated_reply_fixture','version':'1'},'capabilities':{'experimentalApi':True}})
    seed.send(json.dumps({'method':'initialized'}))
    tid=call(2,'thread/start',{'cwd':str(root),'approvalPolicy':'never','sandbox':'read-only'})['thread']['id']
    call(3,'turn/start',{'threadId':tid,'input':[{'type':'text','text':'Isolated fixture seed. Reply only READY. Do not use tools.'}]})
    while True:
        event=json.loads(seed.recv())
        if event.get('method')=='turn/completed':
            assert event['params']['turn']['status']=='completed'
            break
    seed.close(); seed=None
    inbox=root/'inbox'; inbox.write_text('Isolated one-turn roundtrip fixture. Reply only DELEGATED_RETURN_ORCHID_927. Do not use tools.\nEOF\n'); inbox.chmod(0o600)
    shared=root/'messages.md'; shared.write_text('preserved fixture history\n'); lock=root/'messages.md.lock'; lock.touch(); inode=lock.stat().st_ino
    with patch.dict(os.environ,{'ENIKK_TTS_SOCKET':str(root/'no-voice.sock')}),patch('delegated_reply.shared_log',return_value=shared):
        service=Service(str(sock),tid,root/'proxy',inbox); service.initialize()
        accepted=service.trigger({'action':'trigger'},os.getuid()); assert accepted['status']=='ACCEPTED',accepted
        task=service.tasks/accepted['task_id']; deadline=time.monotonic()+140
        while time.monotonic()<deadline:
            if (task/'reply-delivery.json').exists(): break
            time.sleep(.1)
        else:raise AssertionError('reply timeout')
        delivery=json.loads((task/'reply-delivery.json').read_text())
        assert delivery['status']=='PUBLISHED',delivery
        assert 'DELEGATED_RETURN_ORCHID_927' in shared.read_text()
        assert shared.read_text().startswith('preserved fixture history\n')
        assert lock.stat().st_ino==inode
        assert service.thread_id==tid and service.arbiter.state=='IDLE'
        before=shared.read_bytes()
        from delegated_reply import publish
        assert publish(task,tid,accepted['turn_id'],shared)=='ALREADY_PUBLISHED'
        assert shared.read_bytes()==before
        result=dict(status='PASS',thread_id=tid,task_id=accepted['task_id'],turn_id=accepted['turn_id'],delivery=delivery,lock_inode_preserved=True,duplicate_prevented=True)
        (root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print('PASS: real delegated model reply -> durable task snapshot -> shared append -> readback; retry unchanged')
        print('Evidence:',root/'result.json')
finally:
    if seed:seed.close()
    if service:
        service.stopped.set();service.queue_wakeup.set()
        for session in list(service.sessions):session.close()
    if proc.poll() is None:
        proc.terminate()
        try:proc.wait(timeout=10)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
    log.close()
