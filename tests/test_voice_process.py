"""Process-level tests use fake audio only; production Codex/GPU are untouched."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from voice_events import Publisher

FAKE_ENGINE = """import json,os,time,signal
from pathlib import Path
state=Path(os.environ['CODEX_ENIKK_TTS_STATE'])
owner=os.environ['CODEX_ENIKK_TTS_OWNER']
time.sleep(.15)
born=Path('/proc/self/stat').read_text().rsplit(')',1)[1].split()[19]
(state/'model-ready.json').write_text(json.dumps(dict(pid=os.getpid(),born=born,run_id=os.environ['CODEX_ENIKK_TTS_RUN_ID'])))
while True:
    pid,start=owner.split(':')
    try:
        fields=Path('/proc/'+pid+'/stat').read_text().rsplit(')',1)[1].split()
        if fields[19]!=start or fields[0]=='Z':break
    except OSError:break
    if (state/'cancelled').exists():break
    time.sleep(.02)
"""

def wait(predicate, timeout=8):
    end=time.monotonic()+timeout
    while time.monotonic()<end:
        result=predicate()
        if result:return result
        time.sleep(.03)
    raise AssertionError('process test timed out')

class ProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='voice-test-')
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.code=self.root/'code';self.code.mkdir()
        for name in ('independent_service.py','yuki-codex-stream.py','yuki-codex-notify.py'):
            shutil.copyfile(ROOT/'tts'/name,self.code/name)
        (self.code/'yuki-chatterbox-engine.py').write_text(FAKE_ENGINE)
        (self.code/'VERSION').write_text('test')
        self.bin=self.root/'bin';self.bin.mkdir()
        for name in ('paplay','pactl'):
            p=self.bin/name;p.write_text('#!/bin/sh\nexit 0\n');p.chmod(0o755)
        python=self.root/'audio/.venv/bin/python';python.parent.mkdir(parents=True);python.symlink_to(sys.executable)
        self.env=os.environ|{'ENIKK_TTS_STATE':str(self.root/'state'),
            'ENIKK_TTS_SOCKET':str(self.root/'voice.sock'),
            'CODEX_ENIKK_CHATTERBOX_HOME':str(self.root/'audio'),
            'CODEX_HOME':str(self.root/'no-codex'),
            'PATH':str(self.bin)+os.pathsep+os.environ['PATH']}
        self.patch=patch.dict(os.environ,self.env);self.patch.start();self.addCleanup(self.patch.stop)
        self.publisher=Publisher('thread');self.addCleanup(self.publisher.close)
        self.stop=threading.Event();self.addCleanup(self.stop.set)
        self.heartbeat=threading.Thread(target=self.beat,daemon=True);self.heartbeat.start()
        self.process=None;self.addCleanup(self.shutdown)
        self.log=(self.root/'service.log').open('ab');self.addCleanup(self.log.close)

    def beat(self):
        while not self.stop.wait(.1):self.publisher.emit()

    def status(self):
        try:return json.loads((self.root/'state/status.json').read_text())
        except (OSError,ValueError):return {}

    def start(self):
        self.process=subprocess.Popen([sys.executable,'-B',str(self.code/'independent_service.py')],
            env=self.env,stdin=subprocess.DEVNULL,stdout=self.log,stderr=self.log,start_new_session=True)
        return wait(lambda:self.status() if self.status().get('pid')==self.process.pid and self.status().get('state')=='ready' else False)

    def shutdown(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        self.stop.set()
        self.heartbeat.join(2)

    def send(self,method,item='item',**kw):
        p={'threadId':'thread','turnId':'turn'}
        if method=='item/agentMessage/delta':p.update(itemId=item,delta=kw.get('text','새로운 문장이야.'))
        elif method=='turn/completed':p['turn']={'id':'turn','status':'completed','items':[]}
        else:p['item']={'id':item,'type':'agentMessage','phase':'final_answer',**kw}
        self.publisher.emit({'method':method,'params':p})

    def jobs(self,state):
        return [p for p in (Path(state['run'])/'jobs').glob('*') if not p.name.startswith('.')]

    def test_stop_restart_mid_item_and_new_sentence(self):
        baseline=os.getpid()
        state=self.start()
        self.send('item/agentMessage/delta')
        self.send('item/completed',text='이전 답변.')
        time.sleep(.2)
        self.assertFalse(self.jobs(state))
        self.send('item/started','new')
        self.send('item/agentMessage/delta','new')
        jobs=wait(lambda:self.jobs(state))
        self.assertEqual(len(jobs),1)
        self.assertEqual(json.loads(jobs[0].read_text())['text'],'새로운 문장이야.')
        self.process.terminate();self.process.wait(8)
        self.assertTrue((Path(state['run'])/'cancelled').exists())
        self.assertEqual(os.getpid(),baseline)
        new=self.start()
        self.assertNotEqual(state['generation'],new['generation'])
        self.assertFalse(self.jobs(new))
        self.send('item/agentMessage/delta','new')
        time.sleep(.2)
        self.assertFalse(self.jobs(new))
        self.send('item/started','next')
        self.send('item/agentMessage/delta','next')
        self.assertTrue(wait(lambda:self.jobs(new)))

    def test_disconnect_cancels_voice_without_exiting_service(self):
        state=self.start()
        self.stop.set();self.heartbeat.join(2)
        wait(lambda:self.status().get('state')=='waiting_for_core',timeout=8)
        self.assertIsNone(self.process.poll())
        self.assertTrue((Path(state['run'])/'cancelled').exists())

    def test_crashed_receiver_cannot_block_producer(self):
        state=self.start()
        self.process.kill();self.process.wait(5)
        start=time.monotonic()
        for _ in range(2000):self.publisher.emit()
        self.assertLess(time.monotonic()-start,1)
        pid=json.loads((Path(state['run'])/'model-ready.json').read_text())['pid']
        def gone():
            p=Path('/proc')/str(pid)/'stat'
            if not p.exists():return True
            return p.read_text().rsplit(')',1)[1].split()[0]=='Z'
        wait(gone)
        new=self.start()
        self.assertNotEqual(state['generation'],new['generation'])

    def test_queue_full_is_explicit_skip(self):
        state=self.start()
        jobs=Path(state['run'])/'jobs';jobs.mkdir(exist_ok=True)
        for n in range(128):(jobs/str(n)).write_text('{}')
        self.send('item/started')
        self.send('item/agentMessage/delta')
        log=Path(state['run'])/'notify.log'
        wait(lambda:'SKIPPED reason=voice_queue_full' in log.read_text())
        self.assertEqual(len(self.jobs(state)),128)
        self.assertIsNone(self.process.poll())
