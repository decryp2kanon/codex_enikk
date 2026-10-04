"""CPU-only user submit barrier and playback race coverage."""
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import types
import unittest
from unittest.mock import Mock, patch
from test_tts_stream import stream
from test_tts_delivery import definitions


class EpochTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for context in [patch.object(stream.notify, 'STATE', self.root),
                        patch.object(stream.notify, 'log_status'),
                        patch.dict(os.environ, {'CODEX_ENIKK_TTS_RUN_ID': 'run'})]:
            context.start(); self.addCleanup(context.stop)
        self.notify = stream.notify
        self.scope = definitions(); self.scope.update(STATE=self.root, notify=self.notify)
        self.publisher = stream.Publisher(self.root, start_engine=False)

    def process_api(self, playback_spawn, converter=None):
        if converter is None:
            converter = Mock(returncode=0)
            converter.poll.return_value = 0
        def spawn(args, **kwargs):
            if args[0] == '/usr/bin/ffmpeg':
                return converter
            return playback_spawn(args, **kwargs)
        return types.SimpleNamespace(Popen=spawn, DEVNULL=subprocess.DEVNULL,
                                     TimeoutExpired=subprocess.TimeoutExpired,
                                     CalledProcessError=subprocess.CalledProcessError)

    def advance(self, name, ordinal):
        return self.notify.advance_epoch('thread', name, name, ordinal)

    def job(self, epoch, number=0):
        return dict(id=f'{epoch}{number}', epoch=epoch, run_id='run', text='자연스러운 문장이야.',
                    filename=f'{epoch}{number}', queued_ns=time.monotonic_ns(),
                    source={'thread':'thread','turn':epoch})

    def test_pending_A_dropped_and_B_published(self):
        self.advance('A', 1)
        for i in range(3): self.publisher(self.job('A', i))
        self.advance('B', 2); self.publisher(self.job('B'))
        files=list((self.root/'jobs').iterdir())
        live=[json.loads(p.read_text())['id'] for p in files if self.notify.epoch_valid(json.loads(p.read_text()))]
        self.assertEqual(live,['B0'])
        for p in files:
            d=json.loads(p.read_text())
            if d['epoch']=='A': self.assertTrue(self.scope['discard_stale_job'](p,d))

    def test_late_generation_discard_and_no_retry(self):
        self.advance('A',1); job=self.job('A'); reset=Mock(); calls=[]
        def attempt(*args): calls.append(args);self.advance('B',2);return 'old WAV',None
        result,reason=self.scope['recover_generation']('문장이야.',attempt,reset,Mock(),Mock(),
                                                      valid=lambda:self.notify.epoch_valid(job))
        self.assertIsNone(result);self.assertEqual(reason,'STALE');self.assertEqual(len(calls),1);reset.assert_not_called()

    def test_retry_cancelled_during_reset(self):
        self.advance('A',1);job=self.job('A');attempt=Mock(return_value=(None,'internal_long_tail'))
        result,_=self.scope['recover_generation']('문장이야.',attempt,lambda:self.advance('B',2),Mock(),Mock(),
                                                  valid=lambda:self.notify.epoch_valid(job))
        self.assertIsNone(result);self.assertEqual(attempt.call_count,1)

    def test_split_remaining_clause_cancelled(self):
        self.advance('A',1);job=self.job('A');calls=[]
        def attempt(text,number,depth,clause):
            calls.append((depth,clause))
            if depth==1:self.advance('B',2);return 'old',None
            return None,'internal_long_tail'
        self.scope['recovery_clauses']=lambda text:['첫 번째 절','두 번째 절']
        result,_=self.scope['recover_generation']('원래 문장이야.',attempt,lambda:None,Mock(),Mock(),
                                                  valid=lambda:self.notify.epoch_valid(job))
        self.assertIsNone(result);self.assertEqual(calls,[(0,0),(0,0),(1,0)])

    def test_pre_ready_five_old_jobs_never_play(self):
        self.advance('A',1)
        old=[self.job('A',i) for i in range(5)]
        for j in old:self.publisher(j)
        self.advance('B',2)
        self.assertFalse(any(self.notify.epoch_valid(j) for j in old))
        for j in old:self.publisher(j)
        self.assertEqual(len(list((self.root/'jobs').glob('A*'))),5)

    def test_ready_count_only_active_generation(self):
        self.advance('A',1)
        for i in range(5):self.publisher(self.job('A',i))
        self.advance('B',2);self.publisher(self.job('B'))
        with patch.object(self.notify,'engine_ready',return_value=True),patch.object(self.notify,'run_active',return_value=True),patch.dict(os.environ,{'CODEX_ENIKK_STARTUP_NS':str(time.monotonic_ns())}):
            stream.report_engine_ready()
        self.assertIn('1 queued sentence\n',(self.root/'runtime.log').read_text())

    def test_duplicate_and_reordered_events_idempotent(self):
        self.advance('B',20)
        self.assertFalse(self.advance('A',10));self.assertFalse(self.advance('B',20))
        self.assertEqual(self.notify.current_epoch()['epoch'],'B')
        self.advance('C',30);self.assertFalse(self.advance('B',None))
        self.assertTrue(self.notify.epoch_valid(self.job('C')))

    def test_typing_event_does_not_interrupt(self):
        self.advance('A',1);a=stream.Accumulator(self.root/'streams','thread',Mock())
        a.event({'method':'typing','params':{'threadId':'thread','turnId':'B'}})
        self.assertTrue(self.notify.epoch_valid(self.job('A')))

    def test_reordered_event_after_delayed_persistence(self):
        self.advance('B', None)
        with patch.object(self.notify, 'user_ordinal', return_value=20):
            self.assertFalse(self.advance('A', 10))
        self.assertEqual(self.notify.current_epoch()['epoch'], 'B')

    def test_user_event_stamps_new_sentence_and_blocks_late_old(self):
        a=stream.Accumulator(self.root/'streams','thread',self.publisher)
        def event(method,turn,**kwargs):a.event({'method':method,'params':dict(threadId='thread',turnId=turn,**kwargs)})
        with patch.object(self.notify,'user_ordinal',side_effect=[1,2]):
            event('item/started','A',item={'type':'userMessage','id':'A'})
            event('item/started','A',item={'type':'agentMessage','id':'agentA','phase':'final_answer'})
            event('item/started','B',item={'type':'userMessage','id':'B'})
        event('item/agentMessage/delta','A',itemId='agentA',delta='늦게 나온 옛 문장이야.')
        event('item/started','B',item={'type':'agentMessage','id':'agentB','phase':'final_answer'})
        event('item/agentMessage/delta','B',itemId='agentB',delta='새 문장이야.')
        jobs=[json.loads(p.read_text()) for p in (self.root/'jobs').iterdir()]
        self.assertEqual([j['text'] for j in jobs],['새 문장이야.'])

    def test_publication_rechecks_barrier_under_lock(self):
        with patch.object(self.notify,'epoch_valid',side_effect=[True,False]):self.publisher(self.job('A'))
        self.assertEqual(list((self.root/'jobs').iterdir()),[])

    def test_playback_rechecks_before_process_start(self):
        item=self.job('A');job=self.scope['DeliveryJob'](self.root/'job',item,['한 문장'])
        wav=self.root/'test.wav';wav.touch();q=queue.Queue();q.put((job,0,str(wav),time.monotonic_ns(),time.monotonic(),1));q.put(None)
        self.scope['play_audio']=self.scope['real_play_audio'];process=Mock();self.scope['subprocess']=self.process_api(process)
        with patch.object(self.notify,'epoch_valid',side_effect=[True,False]):self.scope['playback'](q)
        process.assert_not_called();self.assertEqual(job.terminal,{'0':'STALE'})

    def test_playing_child_stops_within_500ms_without_worker_kill(self):
        self.advance('A',1);entered=threading.Event();children=[]
        def spawn(*args,**kwargs):
            child=subprocess.Popen(['/bin/sleep','10']);children.append(child);entered.set();return child
        self.scope['subprocess']=self.process_api(spawn)
        result=[];thread=threading.Thread(target=lambda:result.append(self.scope['real_play_audio'](types.SimpleNamespace(item=self.job('A')),'unused')))
        thread.start();self.assertTrue(entered.wait(1));start=time.monotonic();self.advance('B',2);thread.join(1)
        self.assertFalse(thread.is_alive());self.assertLess(time.monotonic()-start,.5);self.assertEqual(result,['stale']);self.assertIsNotNone(children[0].poll())

    def test_pulse_playback_defaults_and_success(self):
        self.advance('A',1)
        child=Mock(returncode=0, args=['/usr/bin/paplay','test.wav']);child.poll.return_value=0
        spawn=Mock(return_value=child)
        self.scope['subprocess']=self.process_api(spawn)
        with patch.dict(os.environ,{},clear=True):
            self.assertEqual(self.scope['real_play_audio'](types.SimpleNamespace(item=self.job('A')),'test.wav'),'played')
        args,kwargs=spawn.call_args
        self.assertEqual(args[0][0], '/usr/bin/paplay')
        self.assertNotEqual(args[0][1], 'test.wav')
        self.assertFalse(Path(args[0][1]).exists())
        self.assertEqual(kwargs['env']['XDG_RUNTIME_DIR'],f'/run/user/{os.getuid()}')
        self.assertEqual(kwargs['env']['PULSE_SERVER'],f'unix:/run/user/{os.getuid()}/pulse/native')

    def test_pulse_playback_preserves_explicit_environment(self):
        self.advance('A',1)
        child=Mock(returncode=0);child.poll.return_value=0
        spawn=Mock(return_value=child)
        self.scope['subprocess']=self.process_api(spawn)
        with patch.dict(os.environ,{'XDG_RUNTIME_DIR':'/custom/runtime','PULSE_SERVER':'unix:/custom/pulse'}):
            self.scope['real_play_audio'](types.SimpleNamespace(item=self.job('A')),'test.wav')
        self.assertEqual(spawn.call_args.kwargs['env']['XDG_RUNTIME_DIR'],'/custom/runtime')
        self.assertEqual(spawn.call_args.kwargs['env']['PULSE_SERVER'],'unix:/custom/pulse')

    def test_pulse_nonzero_failure_does_not_kill_playback_loop(self):
        self.advance('A',1)
        children=[Mock(returncode=1,args=['/usr/bin/paplay','bad.wav']),Mock(returncode=0,args=['/usr/bin/paplay','good.wav'])]
        for child in children:child.poll.return_value=child.returncode
        spawn=Mock(side_effect=children)
        self.scope['subprocess']=self.process_api(spawn)
        self.scope['play_audio']=self.scope['real_play_audio']
        job=self.scope['DeliveryJob'](self.root/'job',self.job('A'),['첫 문장','다음 문장'])
        q=queue.Queue()
        for i in range(2):
            wav=self.root/f'{i}.wav';wav.touch()
            q.put((job,i,str(wav),time.monotonic_ns(),time.monotonic(),1))
        q.put(None);self.scope['playback'](q)
        self.assertEqual(spawn.call_count,2)
        self.assertEqual(job.terminal,{'0':'FAILED_EXPLICITLY','1':'PLAYED'})

    def test_tempo_conversion_cancelled_before_playback(self):
        self.advance('A', 1)
        entered = threading.Event()
        playback_spawn = Mock()
        children = []
        def spawn(args, **kwargs):
            self.assertEqual(args[0], '/usr/bin/ffmpeg')
            self.assertIn('atempo=1.25', args)
            self.assertIn('-nostdin', args)
            child = subprocess.Popen(['/bin/sleep', '10'])
            children.append((child, args[-1])); entered.set()
            return child
        self.scope['subprocess'] = types.SimpleNamespace(
            Popen=spawn, DEVNULL=subprocess.DEVNULL,
            TimeoutExpired=subprocess.TimeoutExpired, CalledProcessError=subprocess.CalledProcessError)
        result = []
        thread = threading.Thread(target=lambda: result.append(self.scope['real_play_audio'](
            types.SimpleNamespace(item=self.job('A')), 'original.wav')))
        thread.start(); self.assertTrue(entered.wait(1))
        start = time.monotonic(); self.advance('B', 2); thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertLess(time.monotonic() - start, .5)
        self.assertEqual(result, ['stale'])
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0][0].poll())
        self.assertFalse(Path(children[0][1]).exists())

    def test_tempo_failure_preserves_original_and_cleans_temporary(self):
        self.advance('A', 1)
        original = self.root / 'original.wav'; original.write_bytes(b'original')
        converter = Mock(returncode=1, args=['/usr/bin/ffmpeg'])
        converter.poll.return_value = 1
        spawn = Mock()
        self.scope['subprocess'] = self.process_api(spawn, converter)
        with self.assertRaises(subprocess.CalledProcessError):
            self.scope['real_play_audio'](types.SimpleNamespace(item=self.job('A')), str(original))
        spawn.assert_not_called()
        self.assertEqual(original.read_bytes(), b'original')
