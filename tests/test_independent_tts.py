import importlib.util
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch, Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import core_runtime
import voice_events
import tts_release

spec = importlib.util.spec_from_file_location('independent_voice', ROOT / 'tts/independent_service.py')
voice = importlib.util.module_from_spec(spec)
spec.loader.exec_module(voice)

def envelope(method, params, sent=200):
    return {'protocol': 1, 'producer': 'producer', 'thread': 'thread',
            'sequence': 1, 'sent_ns': sent, 'event': {'method': method, 'params': params}}

def event(method, item='item', **kw):
    p = {'threadId': 'thread', 'turnId': 'turn'}
    if method == 'item/agentMessage/delta':
        p.update(itemId=item, delta='문장이야.')
    else:
        p['item'] = {'id': item, 'type': 'agentMessage', 'phase': 'final_answer', **kw}
    return envelope(method, p)

class GateTests(unittest.TestCase):
    def test_mid_item_start_skips_remaining_and_snapshot(self):
        gate = voice.Gate(100, 'thread')
        self.assertIsNone(gate.filter(event('item/agentMessage/delta')))
        self.assertIsNone(gate.filter(event('item/completed', text='오래된 답변.')))
        done = envelope('turn/completed', {'threadId': 'thread',
            'turn': {'id':'turn', 'status':'completed', 'items':[{'id':'item','type':'agentMessage','text':'과거.'}]}})
        self.assertEqual(gate.filter(done)['params']['turn']['items'], [])

    def test_ready_boundary_and_new_item(self):
        gate = voice.Gate(100, 'thread')
        old = event('item/started'); old['sent_ns'] = 99
        self.assertIsNone(gate.filter(old))
        self.assertIsNone(gate.filter(event('item/agentMessage/delta')))
        self.assertIsNotNone(gate.filter(event('item/started', 'new')))
        self.assertIsNotNone(gate.filter(event('item/agentMessage/delta', 'new')))
        self.assertIsNone(gate.filter(event('item/started', 'new')))

    def test_new_generation_never_reuses_allowed_items(self):
        first = voice.Gate(100, 'thread')
        first.filter(event('item/started'))
        second = voice.Gate(200, 'thread')
        self.assertIsNone(second.filter(event('item/agentMessage/delta')))

    def test_other_thread_and_oversized_item(self):
        gate = voice.Gate(100, 'thread')
        wrong = event('item/started'); wrong['event']['params']['threadId'] = 'other'
        self.assertIsNone(gate.filter(wrong))
        gate.filter(event('item/started'))
        huge = event('item/agentMessage/delta')
        huge['event']['params']['delta'] = 'a' * (voice.MAX_ITEM_BYTES + 1)
        with self.assertRaises(ValueError): gate.filter(huge)

    def test_invalid_protocol_and_payload(self):
        for value in [{}, [], {'protocol': 2}, {'protocol':1, 'producer':False}, {'protocol':1,'producer':'p','thread':'t','sequence':True,'sent_ns':1}]:
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                voice.valid_message(json.dumps(value))
        self.assertEqual(voice.valid_message(json.dumps(event('item/started')))['thread'], 'thread')

class PublisherTests(unittest.TestCase):
    def test_absent_and_full_receiver_never_wait(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {'ENIKK_TTS_SOCKET':td+'/voice.sock'}):
            p = voice_events.Publisher('thread')
            started = time.monotonic()
            for _ in range(1000): self.assertFalse(p.emit())
            self.assertLess(time.monotonic()-started, 1)
            receiver = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            self.addCleanup(receiver.close); self.addCleanup(p.close)
            receiver.bind(td+'/voice.sock')
            started = time.monotonic()
            results = [p.emit() for _ in range(1000)]
            self.assertTrue(any(results)); self.assertFalse(all(results))
            self.assertLess(time.monotonic()-started, 1)

    def test_event_order_gap_and_large_drop(self):
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ, {'ENIKK_TTS_SOCKET':td+'/voice.sock'}):
            receiver = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            receiver.bind(td+'/voice.sock'); receiver.settimeout(1)
            p = voice_events.Publisher('thread')
            self.addCleanup(receiver.close); self.addCleanup(p.close)
            p.emit(); first = json.loads(receiver.recv(65536))
            p.lock.acquire()
            self.assertFalse(p.emit(event('item/started')['event']))
            p.lock.release()
            p.emit(); second = json.loads(receiver.recv(65536))
            self.assertGreater(second['sequence'],first['sequence']+1)
            huge = event('item/agentMessage/delta')['event']
            huge['params']['delta']='a'*100000
            self.assertFalse(p.emit(huge))
            p.emit(); third=json.loads(receiver.recv(65536))
            self.assertGreater(third['sequence'],second['sequence']+1)

class CoreTests(unittest.TestCase):
    def test_core_start_and_cleanup_without_any_voice_files(self):
        children=[]
        def launch(args, **kw):
            child=Mock(); child.poll.return_value=None
            Path(args[-1].removeprefix('unix://')).touch()
            children.append(child)
            return child
        with patch('core_runtime.subprocess.Popen', side_effect=launch):
            with self.assertRaisesRegex(RuntimeError,'body'):
                with core_runtime.app_server() as endpoint:
                    directory=Path(endpoint.removeprefix('unix://')).parent
                    raise RuntimeError('body')
        self.assertFalse(directory.exists())
        self.assertEqual(len(children),1)
        children[0].terminate.assert_called_once()

    def test_core_start_failure_does_not_start_new_session(self):
        child=Mock(); child.poll.return_value=1
        with patch('core_runtime.subprocess.Popen',return_value=child) as launch:
            with self.assertRaises(RuntimeError):
                with core_runtime.app_server(): pass
        self.assertEqual(launch.call_count,1)
        self.assertIn('app-server',launch.call_args.args[0])
        self.assertNotIn('thread/start',launch.call_args.args[0])

    def test_training_cannot_restart_core(self):
        import satoshi_training_supervisor as training
        with patch('satoshi_training_supervisor.os.kill') as kill:
            with self.assertRaisesRegex(RuntimeError,'core restart is forbidden'): training.restart(os.getpid())
        kill.assert_not_called()

class ReleaseTests(unittest.TestCase):
    def test_atomic_update_failure_hash_check_and_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)/'voice'
            first=tts_release.stage(ROOT,base)
            tts_release.select(base,first)
            self.assertEqual((base/'active').resolve(),first)
            with patch('tts_release.shutil.copyfile',side_effect=OSError('disk failed')):
                with self.assertRaises(OSError): tts_release.stage(ROOT,base)
            self.assertEqual((base/'active').resolve(),first)
            self.assertFalse(list((base/'releases').glob('.stage-*')))
            (first/'PROTOCOL').write_text('99')
            with self.assertRaisesRegex(ValueError,'hash mismatch'):tts_release.select(base,first)

    def test_release_uses_fixed_resolved_path(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)/'voice'
            release=tts_release.stage(ROOT,base)
            tts_release.select(base,release)
            source=(base/'active/independent_service.py').resolve()
            self.assertEqual(source.parent,release)
            self.assertNotIn('codex_enikk',str(release))

    def test_install_update_touch_no_core_files(self):
        with tempfile.TemporaryDirectory() as td:
            prefix=Path(td)/'prefix'; runtime=Path(td)/'runtime';runtime.mkdir()
            core=prefix/'lib/codex_enikk'; core.mkdir(parents=True)
            sentinel=core/'enikk.py';sentinel.write_text('core-sentinel')
            env=os.environ|{'PREFIX':str(prefix),'ENIKK_TTS_INSTALL_SERVICE':'0','XDG_RUNTIME_DIR':str(runtime)}
            result=subprocess.run(['bash',str(ROOT/'install-tts.sh')],env=env,capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(sentinel.read_text(),'core-sentinel')
            self.assertEqual(list(core.iterdir()),[sentinel])
            fakebin=Path(td)/'bin';fakebin.mkdir()
            systemctl=fakebin/'systemctl'
            systemctl.write_text('#!/bin/sh\nprintf "MainPID=0\\nActiveState=inactive\\nSubState=dead\\n"\n')
            systemctl.chmod(0o755)
            checked=subprocess.run([str(prefix/'bin/enikk_tts'),'status'],
                env=env|{'PATH':str(fakebin)+os.pathsep+os.environ['PATH']},capture_output=True,text=True)
            self.assertEqual(checked.returncode,0,checked.stderr)
            active=(prefix/'lib/enikk_tts/active').resolve()
            self.assertFalse((active/'__pycache__').exists())
            tts_release.verify(active)

    def test_voice_status_has_no_start_side_effect(self):
        import runpy
        cli=runpy.run_path(str(ROOT/'enikk_tts'))
        with tempfile.TemporaryDirectory() as td, patch.dict(os.environ,{'ENIKK_TTS_STATE':td}), \
             patch.object(sys,'argv',['enikk_tts','status']), \
             patch('subprocess.run',return_value=subprocess.CompletedProcess([],0,'ActiveState=inactive\n','')) as run:
            self.assertEqual(cli['main'](),0)
            self.assertEqual(list(Path(td).iterdir()),[])
            self.assertEqual(run.call_count,1)
            self.assertEqual(run.call_args.args[0][2],'show')

    def test_killed_active_switch_keeps_previous_release_and_rollback(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)/'voice'
            first=tts_release.stage(ROOT,base);tts_release.select(base,first)
            source=Path(td)/'source';(source/'tts').mkdir(parents=True)
            import shutil
            for name in tts_release.FILES: shutil.copyfile(ROOT/'tts'/name,source/'tts'/name)
            for name in tts_release.ROOT_FILES: shutil.copyfile(ROOT/name,source/name)
            (source/'VERSION').write_text('different-test-version')
            second=tts_release.stage(source,base)
            marker=Path(td)/'switch-ready'
            script=("import sys,time,os;from pathlib import Path;sys.path.insert(0,"+repr(str(ROOT))+")\n"
                "import tts_release\n"
                "def pause(a,b):\n    Path("+repr(str(marker))+").touch()\n    time.sleep(30)\n"
                "tts_release.os.replace=pause\n"
                "tts_release.select(Path("+repr(str(base))+"),Path("+repr(str(second))+"))\n")
            child=subprocess.Popen([sys.executable,'-B','-c',script],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            try:
                end=time.monotonic()+5
                while not marker.exists() and child.poll() is None and time.monotonic()<end:time.sleep(.02)
                self.assertTrue(marker.exists())
            finally:
                if child.poll() is None:child.kill()
                child.wait()
            self.assertEqual((base/'active').resolve(),first)
            tts_release.verify(first)
            tts_release.select(base,second)
            self.assertEqual((base/'active').resolve(),second)
            tts_release.select(base,first)
            self.assertEqual((base/'active').resolve(),first)
