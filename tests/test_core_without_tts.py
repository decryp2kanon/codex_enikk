"""Installed core, real Unix RPC, fake Codex executable, no TTS installation."""
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
import uuid

ROOT=Path(__file__).resolve().parents[1]
FAKE_CODEX = r'''#!/usr/bin/python3
import json,os,signal,sys,time
from pathlib import Path
sys.path.insert(0,os.environ['FIXTURE_CORE'])
sys.path.insert(0,os.environ['FIXTURE_TESTS'])
from test_trigger_ipc import FakeServer
from trigger_transport import connect
if '--version' in sys.argv:
    print('codex-cli 0.160.0')
elif 'app-server' in sys.argv:
    endpoint=sys.argv[sys.argv.index('--listen')+1].removeprefix('unix://')
    server=FakeServer(Path(endpoint))
    stopped=False
    def stop(*_):
        global stopped
        stopped=True
    signal.signal(signal.SIGTERM,stop)
    while not stopped:time.sleep(.02)
    server.close()
else:
    assert signal.getsignal(signal.SIGTSTP) == signal.SIG_IGN
    os.kill(os.getpid(), signal.SIGTSTP)
    assert sys.argv[1:3]==['resume','thread'],sys.argv
    endpoint=sys.argv[sys.argv.index('--remote')+1].removeprefix('unix://')
    ws=connect(endpoint);ws.settimeout(3)
    def call(identity,method,params):
        ws.send(json.dumps(dict(id=identity,method=method,params=params)))
        while True:
            event=json.loads(ws.recv())
            if event.get('id')==identity:
                assert 'error' not in event,event
                return event['result']
    call(1,'initialize',{'clientInfo':{'name':'fixture','version':'1'}})
    ws.send(json.dumps({'method':'initialized'}))
    result=call(2,'thread/resume',{'threadId':'thread'})
    assert result['thread']['id']=='thread'
    result=call(3,'turn/start',{'threadId':'thread','input':[{'type':'text','text':'fixture text'}]})
    call(4,'turn/interrupt',{'threadId':'thread','turnId':result['turn']['id']})
    Path(os.environ['FIXTURE_RESULT']).write_text(json.dumps({'thread':'thread','text_submission':'ok','interrupt':'ok'}))
    ws.close()
'''

class InstalledCoreTests(unittest.TestCase):
    def test_installed_core_text_trigger_mirror_without_tts_or_audio_python(self):
        with tempfile.TemporaryDirectory(prefix='core-no-tts-') as td:
            root=Path(td);home=root/'home';home.mkdir()
            prefix=root/'prefix'
            env=os.environ|{'HOME':str(home),'PREFIX':str(prefix),'DESTDIR':'',
                'XDG_STATE_HOME':str(root/'state'),'CODEX_HOME':str(home/'.codex'),
                'CODEX_ENIKK_DATA_DIR':str(root/'evidence'),
                'CODEX_ENIKK_CHATTERBOX_HOME':str(root/'missing-audio')}
            result=subprocess.run(['bash',str(ROOT/'install.sh')],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            lib=prefix/'lib/codex_enikk'
            self.assertFalse((lib/'tts').exists())
            self.assertFalse((root/'missing-audio').exists())
            p=lib/'enikk.py'
            p.write_text(p.read_text().replace("INSTANCE_SOCKET_PREFIX = '\\0codex_enikk.instance.'",
                "INSTANCE_SOCKET_PREFIX = "+repr('\0core-no-tts-'+uuid.uuid4().hex)))
            sessions=home/'.codex/sessions';sessions.mkdir(parents=True)
            (sessions/'rollout.jsonl').write_text(json.dumps({'type':'session_meta','payload':{'id':'thread','cwd':str(home)}})+'\n')
            with sqlite3.connect(home/'.codex/state_5.sqlite') as db:
                db.execute('CREATE TABLE threads (id TEXT,rollout_path TEXT)')
                db.execute('INSERT INTO threads VALUES (?,?)',('thread',str(sessions/'rollout.jsonl')))
            with sqlite3.connect(home/'.codex/thread_history_1.sqlite') as db:
                db.execute('CREATE TABLE thread_history_projection_state (thread_id TEXT,next_rollout_byte_offset INTEGER)')
                db.execute('INSERT INTO thread_history_projection_state VALUES (?,?)',('thread',0))
                db.execute('CREATE TABLE thread_items (thread_id TEXT,item_type TEXT,rollout_ordinal INTEGER,item_json TEXT)')
                db.execute('INSERT INTO thread_items VALUES (?,?,?,?)',('thread','agentMessage',1,
                    json.dumps({'type':'agentMessage','phase':'final_answer','text':'mirror without voice'})))
            fakebin=root/'bin';fakebin.mkdir()
            codex=fakebin/'codex';codex.write_text(FAKE_CODEX);codex.chmod(0o755)
            # No paplay, venv, model, reference or external tools in this PATH.
            for name in ('python3','bash','dirname','readlink'):
                (fakebin/name).symlink_to('/usr/bin/'+name)
            env.update(PATH=str(fakebin),FIXTURE_CORE=str(lib),FIXTURE_TESTS=str(ROOT/'tests'),
                FIXTURE_RESULT=str(root/'result.json'),ENIKK_TTS_SOCKET=str(root/'missing-voice.sock'))
            completed=subprocess.run([str(prefix/'bin/codex_enikk')],env=env,cwd=home,
                input='',capture_output=True,text=True,timeout=20)
            self.assertEqual(completed.returncode,0,completed.stderr)
            self.assertEqual(json.loads((root/'result.json').read_text())['text_submission'],'ok')
            selection=json.loads((root/'state/codex_enikk/core/mirror-thread.json').read_text())
            self.assertEqual(selection['thread'],'thread')
            self.assertFalse((root/'state/enikk_tts').exists())
            self.assertIn('mirror without voice',(home/'codex-latest.txt').read_text())
            self.assertTrue(list((root/'evidence').rglob('checkpoint.json')))
