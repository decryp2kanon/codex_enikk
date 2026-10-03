import importlib.util
import json
import os
import re
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('stream', ROOT/'tts/yuki-codex-stream.py')
stream = importlib.util.module_from_spec(spec); spec.loader.exec_module(stream)

class StreamingTests(unittest.TestCase):
    def ready_status(self, count=0, ready=True, active=True):
        jobs = self.root / 'jobs'
        jobs.mkdir(exist_ok=True)
        for i in range(count):
            (jobs / str(i)).write_text(json.dumps({'text': '문장이야.', 'run_id': 'current'}))
        with patch.object(stream.notify, 'STATE', self.root), \
             patch.object(stream.notify, 'engine_ready', return_value=ready), \
             patch.object(stream.notify, 'run_active', return_value=active), \
             patch.object(stream.time, 'monotonic_ns', return_value=17900000000), \
             patch.dict(os.environ, {'CODEX_ENIKK_STARTUP_NS': '1000000000', 'CODEX_ENIKK_TTS_RUN_ID': 'current'}):
            stream.report_engine_ready()
        path = self.root / 'runtime.log'
        return path.read_text() if path.exists() else ''

    def test_ready_status_once(self):
        self.assertEqual(len(self.ready_status().splitlines()), 1)

    def test_ready_status_elapsed(self):
        self.assertIn('Yuki TTS ready (16.9s)', self.ready_status())

    def test_ready_status_no_pending(self):
        self.assertNotIn('queued', self.ready_status())

    def test_ready_status_singular(self):
        self.assertEqual(self.ready_status(1), 'Yuki TTS ready (16.9s) — 1 queued sentence\n')

    def test_ready_status_plural(self):
        self.assertEqual(self.ready_status(3), 'Yuki TTS ready (16.9s) — 3 queued sentences\n')

    def test_ready_status_repeated_signal(self):
        first = self.ready_status()
        self.assertEqual(self.ready_status(), first)

    def test_ready_status_failure_or_cancelled(self):
        self.assertEqual(self.ready_status(ready=False), '')
        self.assertEqual(self.ready_status(active=False), '')

    def test_ready_status_excludes_old_and_terminal(self):
        jobs = self.root / 'jobs'; jobs.mkdir()
        (jobs / 'old').write_text(json.dumps({'text': '옛 문장.', 'run_id': 'old'}))
        (jobs / '.played-hidden').write_text(json.dumps({'text': '완료.', 'run_id': 'current'}))
        (jobs / 'done').write_text(json.dumps({'text': '완료.', 'run_id': 'current',
            'delivery': {'parts': ['완료.'], 'terminal': {'0': 'PLAYED'}}}))
        (jobs / 'partial').write_text(json.dumps({'text': '아직 남아 있어.', 'run_id': 'current',
            'delivery': {'parts': ['앞.', '뒤.'], 'terminal': {'0': 'PLAYED'}}}))
        self.assertIn('1 queued sentence\n', self.ready_status())

    def test_connect_avoids_duplicate_utf8_validation(self):
        import sys
        from unittest.mock import Mock
        websocket=Mock()
        with patch.dict(sys.modules, {'websocket':websocket}), patch.object(stream.socket,'socket') as socket:
            result=stream.connect('/private/socket')
        socket.return_value.connect.assert_called_once_with('/private/socket')
        self.assertTrue(websocket.create_connection.call_args.kwargs['skip_utf8_validation'])
        self.assertEqual(result,websocket.create_connection.return_value)

    def test_initial_history_uses_turn_manifest_not_item_files(self):
        history={'turns':[{'id': 'old', 'status':'completed', 'items':[
            {'id':str(i), 'type':'agentMessage', 'phase':'final_answer', 'text':'이전 대화야.'}
            for i in range(1000)]}]}
        self.a.snapshot(history, initial=True)
        self.assertEqual(self.a.baseline, {'old'})
        self.assertEqual(list(self.root.glob('*.json')), [])
        stream.atomic_json(self.root/'.baseline', {'ignored_turns':['old']})
        restarted=stream.Accumulator(self.root,'thread',self.jobs.append)
        restarted.snapshot(history, reconnecting=True)
        self.assertEqual(self.jobs, [])

    def test_model_not_ready_does_not_delay_subscription(self):
        import sys
        from unittest.mock import Mock
        for failure in (None, OSError('fixture unavailable')):
            with self.subTest(failure=failure), patch.object(stream.notify,'STATE',self.root), \
                 patch.object(stream.notify,'ensure_engine',side_effect=failure), \
                 patch.object(stream.notify,'engine_ready',return_value=False), \
                 patch.object(stream.threading,'Thread'), patch.object(stream.signal,'signal'), \
                 patch.object(stream,'observe') as observe, \
                 patch.object(sys,'argv',['stream','--socket','/unused','--thread','thread','--ready','/unused-ready']):
                stream.main()
                observe.assert_called_once()
                publisher=observe.call_args.kwargs['submit']
                self.assertFalse(publisher.start_engine)
                self.assertTrue(observe.call_args.kwargs['stop'].is_set())

    def test_pre_ready_jobs_preserve_order_and_idempotency(self):
        publisher=stream.Publisher(self.root/'runtime',start_engine=False)
        self.a.submit=publisher
        with patch.object(stream.notify,'engine_ready',return_value=False), patch.object(stream.notify,'ensure_engine') as spawn:
            self.delta('첫 번째 문장이야. 두 번째 문장이야. 세 번째 문장이야.')
            self.complete('첫 번째 문장이야. 두 번째 문장이야. 세 번째 문장이야.')
            self.a.recover()
            spawn.assert_not_called()
        jobs=[json.loads(p.read_text()) for p in sorted(publisher.jobs.iterdir()) if not p.name.startswith('.')]
        self.assertEqual([j['text'] for j in jobs],['첫 번째 문장이야.','두 번째 문장이야.','세 번째 문장이야.'])
        with patch.object(stream.notify,'run_active',return_value=False):
            self.delta(' 종료 후 문장이야.')
        self.assertEqual(len(list(publisher.jobs.iterdir())),3)

    def test_model_readiness_failure_is_logged_without_stopping_observer(self):
        import threading
        stop=threading.Event()
        with patch.object(stream.notify,'engine_ready',return_value=False), patch.object(stream.notify,'run_active',return_value=True), \
             patch.object(stream.time,'monotonic',side_effect=[0,61]), patch.object(stream.notify,'log_status') as log:
            stream.monitor_engine(stop)
        self.assertFalse(stop.is_set())
        self.assertIn('TTS_READY_FAILED',log.call_args.args[0])

    def test_model_ready_monitor_emits_ready_without_requeue(self):
        import threading
        stop=threading.Event()
        with patch.object(stream.notify,'engine_ready',return_value=True), patch.object(stream.notify,'run_active',return_value=True), \
             patch.object(stream.notify,'log_status') as log:
            stream.monitor_engine(stop)
        self.assertIn('TTS_READY monotonic_ns=',log.call_args.args[0])
        self.assertFalse(stop.is_set())

    def setUp(self):
        environment = patch.dict(os.environ)
        environment.start(); self.addCleanup(environment.stop)
        for key in list(os.environ):
            if key.startswith('CODEX_ENIKK_TTS_') or key == 'CODEX_ENIKK_STARTUP_NS':
                os.environ.pop(key)
        logger = patch.object(stream.notify, 'log_status')
        logger.start(); self.addCleanup(logger.stop)
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.jobs = []
        state_patch = patch.object(stream.notify, 'STATE', self.root)
        state_patch.start(); self.addCleanup(state_patch.stop)
        self.a = stream.Accumulator(self.root, 'thread', self.jobs.append)
        self.event('item/started', item=dict(type='agentMessage', id='item', phase='final_answer'))

    def event(self, method, **params):
        self.a.event(dict(method=method, params=dict(threadId='thread', turnId='turn', **params)))

    def delta(self, text):
        self.event('item/agentMessage/delta', itemId='item', delta=text)

    def test_mirror_tracks_thread_switch_but_never_deltas(self):
        with patch.object(stream.notify, 'STATE', self.root):
            stream.mirror_selection(dict(method='thread/started', params={'thread': {'id': 'B'}}))
            path = self.root / 'mirror-thread.json'
            self.assertEqual(json.loads(path.read_text())['thread'], 'B')
            before = path.stat().st_mtime_ns
            stream.mirror_selection(dict(method='item/agentMessage/delta', params={'threadId': 'A'}))
            self.assertEqual(path.stat().st_mtime_ns, before)
            stream.mirror_selection(dict(method='turn/started', params={'threadId': 'C'}))
            self.assertEqual(json.loads(path.read_text())['thread'], 'C')

    def test_five_second_sentence_isolation(self):
        timestamps = []
        traces = []
        self.a.log = traces.append
        publisher = stream.Publisher(self.root / 'runtime', start_engine=False)
        logger = patch.object(stream.notify, 'log_status')
        logger.start(); self.addCleanup(logger.stop)
        def publish(job):
            publisher(job)
            self.assertTrue((publisher.jobs / job['filename']).is_file())
            self.jobs.append(job)
            timestamps.append(time.monotonic())
        self.a.submit = publish
        complete = time.monotonic()
        self.delta('첫 번째 문장이 완성됐어.')
        self.assertEqual(len(self.jobs), 1)
        self.assertLess(timestamps[0] - complete, .5)
        time.sleep(5)
        second = time.monotonic()
        self.assertLess(timestamps[0], second)
        self.delta('두 번째 문장이 이제 도착했어.')
        self.assertEqual(len(self.jobs), 2)
        time.sleep(5)
        self.delta('세 번째 문장이 마지막이야.')
        self.assertEqual(len(self.jobs), 3)
        flush = int(re.search(r'flush_ns=(\d+)', next(line for line in traces if 'SENTENCE_FLUSH' in line))[1]) / 1e9
        self.assertLess(flush, second)
        print(f'sentence isolation complete={complete:.6f} flush={flush:.6f} job_created={timestamps[0]:.6f} second_arrival={second:.6f}')

    def test_ambiguous_terminal_period_requires_lookahead(self):
        for token in ('31.', 'v0.', 'test.', 'example.', '/tmp/한국.', 'https://example.com/한국.'):
            self.assertEqual(list(stream.boundaries(token)), [])

    def complete(self, text):
        self.event('item/completed', item=dict(type='agentMessage',id='item',text=text,phase='final_answer'))
        self.event('turn/completed', turn=dict(id='turn',status='completed',items=[]))

    def test_partial_and_final_duplicate(self):
        self.delta('설치 상태를 '); self.assertEqual(self.jobs, [])
        self.delta('확인하고 있어. 다음 ')
        self.assertEqual([j['text'] for j in self.jobs], ['설치 상태를 확인하고 있어.'])
        self.complete('설치 상태를 확인하고 있어. 다음 문장')
        self.complete('설치 상태를 확인하고 있어. 다음 문장')
        self.assertEqual([j['text'] for j in self.jobs], ['설치 상태를 확인하고 있어.', '다음 문장'])

    def test_decimal_version_domain_ip_and_code(self):
        text='31.1 및 3.2GB, v0.1.7 test.py example.com 127.0.0.1을 확인해. 다음이야.'
        for c in text: self.delta(c)
        self.complete(text)
        self.assertEqual([j['text'] for j in self.jobs], [text[:text.index(' 다음')], '다음이야.'])

    def test_path_stream_keeps_visible_source_and_final_is_not_duplicated(self):
        from test_tts_delivery import definitions
        engine = definitions()
        text = '현재 /home/ak/git/codex_enikk/tts/yuki-chatterbox-engine.py 파일을 확인할게. 숫자는 31.1이야.'
        for character in text:
            self.delta(character)
        self.complete(text)
        self.complete(text)
        self.assertEqual(len(self.jobs), 2)
        self.assertEqual(' '.join(job['text'] for job in self.jobs), text)
        normalized, paths = engine['normalize_paths'](self.jobs[0]['text'])
        self.assertEqual(normalized, '현재 유키 채터박스 엔진 파이썬 파일 경로를 확인할게.')
        self.assertEqual(len(paths), 1)
        self.assertEqual(' '.join(engine['speech_chunks'](normalized)), normalized)

    def test_markdown_and_code_not_spoken(self):
        text='첫 문장이야.\n```python\nprint("숨긴 코드.")\n```\n[설명](https://example.com/a.b)을 확인해. 끝.'
        for c in text:self.delta(c)
        self.complete(text)
        combined=' '.join(j['text'] for j in self.jobs)
        self.assertNotIn('print',combined);self.assertNotIn('https',combined)
        self.assertIn('설명을 확인해.',combined)

    def test_interruption_does_not_flush_fragment(self):
        self.delta('완성 문장이야. 미완성')
        self.event('turn/completed', turn=dict(id='turn',status='interrupted',items=[]))
        self.assertEqual([j['text'] for j in self.jobs], ['완성 문장이야.'])

    def test_interrupted_completed_item_does_not_read_tail(self):
        self.delta('완성 문장이야. 미완성')
        self.event('item/completed', item=dict(type='agentMessage', id='item', text='완성 문장이야. 미완성', phase='final_answer'))
        self.event('turn/completed', turn=dict(id='turn', status='interrupted', items=[]))
        self.assertEqual([j['text'] for j in self.jobs], ['완성 문장이야.'])

    def test_snapshot_resume_no_repeat(self):
        self.delta('첫 문장이야. 둘째')
        b=stream.Accumulator(self.root,'thread',self.jobs.append)
        b.snapshot(dict(turns=[dict(id='turn',status='inProgress',items=[dict(type='agentMessage',id='item',phase='final_answer',text='첫 문장이야. 둘째 문장이야. 셋째')])]))
        self.assertEqual([j['text'] for j in self.jobs],['첫 문장이야.','둘째 문장이야.'])
        b.snapshot(dict(turns=[dict(id='turn',status='completed',items=[dict(type='agentMessage',id='item',phase='final_answer',text='첫 문장이야. 둘째 문장이야. 셋째')])]))
        self.assertEqual(len(self.jobs),3)

    def test_reconnect_without_active_item_does_not_splice_delta(self):
        self.delta('첫 문장이야. 베')
        b = stream.Accumulator(self.root, 'thread', self.jobs.append)
        b.snapshot(dict(turns=[dict(id='turn', status='inProgress', items=[])]), reconnecting=True)
        b.event(dict(method='item/agentMessage/delta', params=dict(threadId='thread', turnId='turn', itemId='item', delta='을 스치며 지나간다. ')))
        self.assertEqual([j['text'] for j in self.jobs], ['첫 문장이야.'])
        full = '첫 문장이야. 베타는 바람을 스치며 지나간다. 마지막 문장이야.'
        b.event(dict(method='item/completed', params=dict(threadId='thread', turnId='turn', item=dict(type='agentMessage', id='item', phase='final_answer', text=full))))
        b.event(dict(method='turn/completed', params=dict(threadId='thread', turn=dict(id='turn',status='completed',items=[]))))
        self.assertEqual(' '.join(j['text'] for j in self.jobs), full)
        self.assertEqual(len({j['id'] for j in self.jobs}), 3)

    def test_reconnect_missing_completed_item_requests_snapshot(self):
        self.delta('첫 문장이야. 다음')
        self.a.snapshot(dict(turns=[dict(id='turn',status='inProgress',items=[])]), reconnecting=True)
        with self.assertRaises(ConnectionError):
            self.event('turn/completed', turn=dict(id='turn',status='completed',items=[]))
        full = '첫 문장이야. 다음 문장이야.'
        self.a.snapshot(dict(turns=[dict(id='turn',status='completed',items=[dict(type='agentMessage',id='item',phase='final_answer',text=full)])]), reconnecting=True)
        self.assertEqual(' '.join(j['text'] for j in self.jobs), full)

    def test_changed_consumed_prefix_fails_closed(self):
        self.delta('첫 문장이야. 다음')
        with self.assertRaises(ValueError): self.complete('다른 문장이야. 다음')
        self.assertEqual(len(self.jobs),1)
        self.assertIn('conflict',json.loads(self.a.path('turn','item').read_text()))

    def test_12_sentences_accounting_and_other_thread(self):
        sentences=[f'{word} 단어와 함께 현재 상태를 확인하고 있어.' for word in ['알파','베타','감마','델타']*3]
        text=' '.join(sentences)
        for c in text:self.delta(c)
        self.complete(text)
        self.a.event(dict(method='item/agentMessage/delta',params=dict(threadId='other',turnId='turn',itemId='item',delta='읽으면 안 돼. ')))
        self.assertEqual([j['text'] for j in self.jobs],sentences)
        self.assertEqual(len({j['id'] for j in self.jobs}),12)

    def test_outbox_crash_recovery_and_delivery_receipt(self):
        jobsdir=self.root/'state'
        publisher=stream.Publisher(jobsdir,start_engine=False)
        old=stream.notify.log_status;stream.notify.log_status=lambda _:None
        self.addCleanup(setattr,stream.notify,'log_status',old)
        self.delta('전달할 첫 문장이야. 다음')
        job=self.jobs[0];publisher(job)
        path=publisher.jobs/job['filename']
        path.rename(path.with_name('.played-'+path.name))
        recovered=stream.Accumulator(self.root,'thread',publisher)
        recovered.recover()
        self.assertFalse(path.exists())

    def test_previous_run_outbox_is_never_published(self):
        import os
        publisher = stream.Publisher(self.root / 'new-run', start_engine=False)
        with patch.object(stream.notify, 'log_status'), patch.dict(os.environ, {'CODEX_ENIKK_TTS_RUN_ID':'A'}):
            self.delta('이전 실행 문장은 다시 읽지 않아.')
        self.assertEqual(self.jobs[0]['run_id'], 'A')
        with patch.object(stream.notify, 'log_status'), patch.dict(os.environ, {'CODEX_ENIKK_TTS_RUN_ID':'B'}):
            publisher(self.jobs[0])
        self.assertEqual(list(publisher.jobs.iterdir()), [])

    def test_previous_run_active_turn_cannot_resume_speaking(self):
        self.a.snapshot({'turns':[{'id':'turn','status':'inProgress','items':[]}]}, initial=True)
        self.delta('지난 실행에서 생성하던 문장이 뒤늦게 도착했어.')
        self.complete('지난 실행에서 생성하던 문장이 뒤늦게 도착했어.')
        self.assertEqual(self.jobs, [])
        self.a.snapshot({'turns':[{'id':'turn','status':'completed','items':[
            {'id':'item','type':'agentMessage','phase':'final_answer','text':'지난 문장이야.'}]}]}, reconnecting=True)
        self.assertEqual(self.jobs, [])

    def test_readiness_requires_live_matching_worker_and_run(self):
        import os
        born = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]
        path = self.root / 'model-ready.json'
        with patch.object(stream.notify, 'STATE', self.root), patch.dict(os.environ, {'CODEX_ENIKK_TTS_RUN_ID':'B'}):
            self.assertFalse(stream.notify.engine_ready())
            for run, birth, expected in [('A', born, False), ('B', '0', False), ('B', born, True)]:
                path.write_text(json.dumps({'pid':os.getpid(), 'born':birth, 'run_id':run}))
                self.assertEqual(stream.notify.engine_ready(), expected)

    def test_stream_recovery_delivery_receipt_and_final_duplicate(self):
        from test_tts_delivery import definitions
        scope = definitions()
        publisher = stream.Publisher(self.root / 'delivery', start_engine=False)
        self.a.submit = publisher
        text = '가벼운 바람이 나뭇잎을 스치며 조용히 지나간다.'
        self.delta(text + ' ')
        self.complete(text)
        paths = [p for p in publisher.jobs.iterdir() if not p.name.startswith('.')]
        self.assertEqual(len(paths), 1)
        item = json.loads(paths[0].read_text())
        job = scope['DeliveryJob'](paths[0], item, [text])
        recovered, reason = scope['recover_generation'](
            text, lambda t,n,d,c: (None, 'internal_long_tail') if d == 0 else (t, None),
            lambda: None, ' '.join, lambda _: None)
        self.assertEqual(recovered.split(), text.split())
        job.finish(0, 'played')
        self.a.recover()
        self.complete(text)
        self.assertEqual(len(list(publisher.jobs.glob('.played-*'))), 1)
        self.assertEqual([p for p in publisher.jobs.iterdir() if not p.name.startswith('.')], [])

    def test_graceful_shutdown_reconciles_last_sentence(self):
        import threading
        import types
        from unittest.mock import patch
        import sys
        publisher = stream.Publisher(self.root / 'delivery', start_engine=False)
        self.a.submit = publisher
        self.delta('첫 문장이야. 마지막')
        stream.atomic_json(self.root / '.baseline', {'initialized':True})
        stop = threading.Event()
        full = '첫 문장이야. 마지막 문장이야.'
        class Socket:
            def __init__(self): self.request = None; self.closed = False
            def send(self, data): self.request = json.loads(data).get('id')
            def settimeout(self, timeout): pass
            def close(self): self.closed = True
            def recv(self):
                request = self.request; self.request = None
                if request == 1: return json.dumps({'id':1,'result':{}})
                if request == 2: return json.dumps({'id':2,'result':{'thread':{'turns':[{'id':'turn','status':'inProgress','items':[]}]}}})
                if request == 3: return json.dumps({'id':3,'result':{'thread':{'turns':[{'id':'turn','status':'completed','items':[{'id':'item','type':'agentMessage','phase':'final_answer','text':full}]}]}}})
                stop.set()
                return json.dumps({'method':'item/agentMessage/delta','params':{'threadId':'thread','turnId':'turn','itemId':'item','delta':' 문장이야.'}})
        socket = Socket()
        with patch.object(stream,'connect',return_value=socket), patch.object(stream.notify,'log_status'), patch.dict(sys.modules, {'websocket':types.SimpleNamespace(WebSocketTimeoutException=TimeoutError)}):
            stream.observe('unused','thread',self.root,submit=publisher,stop=stop)
        jobs = [json.loads(p.read_text()) for p in sorted(publisher.jobs.iterdir()) if not p.name.startswith('.')]
        self.assertEqual([j['text'] for j in jobs], ['첫 문장이야.', '마지막 문장이야.'])
        self.assertTrue(socket.closed)

if __name__=='__main__':unittest.main()
