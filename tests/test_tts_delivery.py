"""CPU-only delivery tests: load stdlib engine definitions without ML imports."""
import ast
import fcntl
import json
import importlib.util
import logging
import os
from pathlib import Path
import queue
import re
import subprocess
import tempfile
import threading
import time
import types
import unittest
from contextlib import nullcontext
from unittest.mock import Mock, patch

SOURCE = Path(__file__).resolve().parents[1] / 'tts/yuki-chatterbox-engine.py'

_override_spec = importlib.util.spec_from_file_location(
    'delivery_overrides', SOURCE.with_name('yuki-text-normalization-overrides.py'))
overrides = importlib.util.module_from_spec(_override_spec)
_override_spec.loader.exec_module(overrides)


def definitions():
    tree = ast.parse(SOURCE.read_text())
    names = {'DeliveryJob', 'playback', 'play_audio', 'run', 'GenerationWarnings', 'retire_alignment_hooks',
             'soften_detached_tail', 'optional_tail_softening',
             'sentences', 'speech_chunks', 'segment_drop_reason', 'recovery_clauses', 'recover_generation',
             'normalize_paths', 'korean_pronunciation',
             'owner_alive', 'discard_stale_job'}
    constants = set()
    assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id in constants for target in node.targets)]
    tree.body = [node for node in tree.body if getattr(node, 'name', None) in names]
    tree.body = assignments + tree.body
    scope = dict(tn=types.SimpleNamespace(overrides=overrides, initialize=Mock(), normalize=Mock(side_effect=lambda text:text)), Path=Path, os=os, tempfile=tempfile, json=json, threading=threading,
                 time=time, subprocess=types.SimpleNamespace(run=Mock(), DEVNULL=subprocess.DEVNULL),
                 queue=queue, logging=logging, fcntl=fcntl, re=re, log=Mock(), STATE=Path('/unused'),
                 notify=types.SimpleNamespace(epoch_valid=lambda *args: True, epoch_lock=lambda *args: nullcontext()))
    exec(compile(tree, str(SOURCE), 'exec'), scope)
    scope['real_play_audio'] = scope['play_audio']
    # Existing delivery tests inject a synchronous CPU playback operation.
    def simulated_audio(job, path):
        scope['subprocess'].run(['/usr/bin/aplay', '-q', path], check=True)
        return 'played'
    scope['play_audio'] = simulated_audio
    return scope


class PathTests(unittest.TestCase):
    def setUp(self):
        self.scope = definitions()

    def normalize(self, text):
        return self.scope['normalize_paths'](text)[0]

    def test_versioned_registered_filename_has_structural_description(self):
        source = 'report_v31.1.md 파일도 확인합니다.'
        result, records = self.scope['normalize_paths'](source)
        self.assertEqual(result, '리포트 버전 삼십일 점 일 마크다운 파일도 확인합니다.')
        self.assertEqual(records[0]['original'], 'report_v31.1.md')
        self.assertEqual(source[slice(*records[0]['span'])], records[0]['replaced_text'])
        self.assertEqual(self.normalize('/tmp/report_v31.1.md'),
                         '리포트 버전 삼십일 점 일 마크다운 파일 경로')
        self.assertEqual(self.normalize('report_v31.2.md'),
                         '리포트 버전 삼십일 점 이 마크다운 파일')
        for text in ['report is ready', 'other-report_v31.1.md',
                     'https://example.com/?file=report_v31.1.md', 'x@report_v31.1.md']:
            self.assertEqual(self.scope['normalize_paths'](text), (text, []))

    def test_known_relative_file_preserves_consonant_noun_particles(self):
        for particle in ['을', '은', '이', '으로', '도']:
            source = 'report_v31.1.md 파일' + particle + ' 확인합니다.'
            self.assertEqual(self.normalize(source),
                             '리포트 버전 삼십일 점 일 마크다운 파일' + particle + ' 확인합니다.')
        self.assertEqual(self.normalize('/tmp/report_v31.1.md 파일을 확인합니다.'),
                         '리포트 버전 삼십일 점 일 마크다운 파일 경로를 확인합니다.')

    def test_known_filename_attached_particles_only(self):
        for particle, wanted in {'를':'을', '는':'은', '가':'이', '와':'과', '로':'로', '에서':'에서'}.items():
            source = 'report_v31.1.md' + particle + ' 확인합니다.'
            result, records = self.scope['normalize_paths'](source)
            self.assertEqual(result, '리포트 버전 삼십일 점 일 마크다운 파일' + wanted + ' 확인합니다.')
            self.assertEqual(source[slice(*records[0]['span'])], records[0]['replaced_text'])
        self.assertEqual(self.normalize('report_v31.1.md가이드 확인합니다.'),
                         '리포트 버전 삼십일 점 일 마크다운 파일가이드 확인합니다.')

    def test_unrelated_path_particle_behavior_is_unchanged(self):
        self.assertEqual(self.normalize('/tmp/test.md 파일도 확인합니다.'),
                         '테스트 마크다운 파일 경로 파일도 확인합니다.')

    def test_required_paths(self):
        for path, expected in {
            '/home/ak/git/codex_enikk/tts/yuki-chatterbox-engine.py': '유키 채터박스 엔진 파이썬 파일 경로',
            '/home/ak/git/codex_enikk/enikk.py': '에닉 파이썬 파일 경로',
            '/home/ak/git/codex_enikk/README.md': '리드미 마크다운 파일 경로',
            '/home/ak/git/codex_enikk/install.sh': '인스톨 셸 스크립트 경로',
            '/tmp/test-output.wav': '테스트 아웃풋 웨이브 오디오 파일 경로',
            '/tmp/enikk-recovery-id3zb9we/approval-marker.txt': '승인 표시 텍스트 파일 경로',
        }.items():
            with self.subTest(path=path):
                result, records = self.scope['normalize_paths'](path)
                self.assertEqual(result, expected)
                self.assertEqual(records[0]['original'], path)

    def test_non_paths_are_unchanged(self):
        for text in ('https://example.com/test.py', 'https://example.com/home/ak/test.py',
                     '31.1', '3.2GB', '파일 경로를 확인할게.', '초/분', 'C2'):
            self.assertEqual(self.scope['normalize_paths'](text), (text, []))

    def test_markdown_punctuation_and_grammar(self):
        expected = '테스트 파이썬 파일 경로'
        self.assertEqual(self.normalize('`/home/ak/test.py`.'), expected + '.')
        self.assertEqual(self.normalize('(/home/ak/test.py)'), '(' + expected + ')')
        self.assertEqual(self.normalize('/home/ak/test.py를 확인해.'), expected + '를 확인해.')
        self.assertEqual(self.normalize('현재 `/home/ak/test.py` 파일을 확인할게.'), '현재 ' + expected + '를 확인할게.')
        self.assertEqual(self.normalize('/home/ak/test.py 파일에서 확인해.'), expected + '에서 확인해.')
        self.assertEqual(self.normalize('/home/ak/test.py 경로에서 확인해.'), expected + '에서 확인해.')
        prose = '테스트 파이썬 파일 경로 파일을 확인해.'
        self.assertEqual(self.normalize('/tmp/test.py. ' + prose), expected + '. ' + prose)

    def test_relative_paths_machine_names_and_extensions(self):
        for prefix in ('~/', './', '../', '/etc/'):
            self.assertEqual(self.normalize(prefix + 'README.md'), '리드미 마크다운 파일 경로')
        self.assertEqual(self.normalize('/tmp/' + 'a3' * 32 + '.py'), '파이썬 파일 경로')
        for extension, label in {'json': '제이슨 파일', 'yaml': '야믈 설정 파일', 'cpp': '씨 플러스 플러스 소스 파일',
                                  'toml': '톰엘 설정 파일', 'rs': '러스트 소스 파일', 'unknown': '파일'}.items():
            self.assertEqual(self.normalize('/tmp/test.' + extension), '테스트 ' + label + ' 경로')

    def test_long_path_before_scheduler_and_existing_numbers(self):
        raw = '승인을 받아 /tmp/' + 'directory/' * 30 + 'approval-marker.txt 파일에 ok를 기록했습니다.'
        normalized = self.normalize(raw)
        self.assertEqual(normalized, '승인을 받아 승인 표시 텍스트 파일 경로에 ok를 기록했습니다.')
        chunks = self.scope['speech_chunks'](normalized)
        self.assertEqual(' '.join(chunks).split(), normalized.split())
        self.assertNotIn('/tmp/', ' '.join(chunks))
        text = 'SUPER-CLEAN C2는 버전 31.1에서 3.2GB를 사용해.'
        self.scope['korean_pronunciation'](text)
        self.scope['tn'].normalize.assert_called_once_with(text)

    def test_only_explicit_path_spans_change(self):
        source = '알파 `/home/ak/test.py` 파일을 확인하고, 베타 /tmp/output.wav를 확인해. 감마 31.1 델타.'
        result, records = self.scope['normalize_paths'](source)
        reconstructed = source
        for record in reversed(records):
            start, end = record['span']
            self.assertEqual(source[start:end], record['replaced_text'])
            reconstructed = reconstructed[:start] + record['spoken'] + reconstructed[end:]
        self.assertEqual(result, reconstructed)
        self.assertEqual(len(records), 2)
        self.assertIn('감마 31.1 델타.', result)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.scope = definitions()
        self.calls = []
        self.reset = Mock()
        self.trace = Mock()
        self.text = "가벼운 바람이 나뭇잎을 스치며 조용히 지나간다."

    def generate(self, text, number, depth, clause):
        self.calls.append((text, number, depth, clause))
        return (None, "internal_long_tail") if depth == 0 else (text, None)

    def recover(self, attempt=None):
        return self.scope['recover_generation'](self.text, attempt or self.generate,
                                                self.reset, " ".join, self.trace)

    def test_double_failure_recovers_once_with_exact_token_order(self):
        recovered, reason = self.recover()
        self.assertEqual(recovered.split(), self.text.split())
        self.assertIsNone(reason)
        self.assertEqual([call[2] for call in self.calls], [0, 0, 1, 1])
        self.assertEqual(self.reset.call_count, 2)

    def test_no_recursive_split_or_infinite_retry(self):
        def failing(text, number, depth, clause):
            self.calls.append((text, number, depth, clause))
            return None, 'internal_long_tail'
        result, reason = self.recover(failing)
        self.assertIsNone(result)
        self.assertIn('recovery clause=0', reason)
        self.assertEqual(len(self.calls), 4)
        self.assertEqual(max(call[2] for call in self.calls), 1)

    def test_second_clause_failure_never_publishes_partial_recovery(self):
        def failing(text, number, depth, clause):
            self.calls.append((text, number, depth, clause))
            return (text, None) if depth == 1 and clause == 0 else (None, 'internal_long_tail')
        result, reason = self.recover(failing)
        self.assertIsNone(result)
        self.assertIn('clause=1', reason)
        self.assertEqual(len(self.calls), 5)

    def test_attempt_budget_six_and_retry_success(self):
        def failing(text, number, depth, clause):
            self.calls.append((text, number, depth, clause))
            return (text, None) if depth == 1 and number == 2 else (None, 'internal_long_tail')
        result, reason = self.recover(failing)
        self.assertEqual(result.split(), self.text.split())
        self.assertEqual(len(self.calls), 6)
        self.assertIsNone(reason)

    def test_normal_generation_does_not_split(self):
        attempt = Mock(return_value=(self.text, None))
        self.assertEqual(self.recover(attempt), (self.text, None))
        attempt.assert_called_once_with(self.text, 1, 0, 0)
        self.reset.assert_not_called()

    def test_only_long_tail_double_failure_can_split(self):
        for reason in ('waveform: tone', 'internal_alignment_repetition', 'generate: OOM'):
            attempt = Mock(return_value=(None, reason))
            self.assertIsNone(self.recover(attempt)[0])
            self.assertEqual(attempt.call_count, 2)

    def test_split_preserves_numbers_urls_and_punctuation(self):
        for text in (self.text, 'SUPER-CLEAN C2는 버전 31.1에서 3.2GB를 사용해.',
                     'example.com/test.py 파일을 확인하고, 다음 문장을 그대로 읽어.',
                     '한글', '3.2GB', 'https://example.com/a.very.long.filename'):
            parts = self.scope['recovery_clauses'](text)
            if parts:
                self.assertEqual(len(parts), 2)
                self.assertEqual(' '.join(parts).split(), text.split())
            else:
                self.assertLess(len(text.split()), 4)

    def test_recovery_keeps_a_long_filename_whole(self):
        text = '승인을 받아 /tmp/example-long-directory/approval-marker.txt'
        self.assertEqual(self.scope['recovery_clauses'](text), ['승인을 받아', '/tmp/example-long-directory/approval-marker.txt'])
        self.assertEqual(self.scope['recovery_clauses']('/tmp/example-long-directory/approval-marker.txt'), [])

    def test_recovery_keeps_conditional_and_time_clauses_together(self):
        for text, expected in (
            ('문제가 발견되면 원인을 하나씩 분리해서 확인하겠다.',
             ['문제가 발견되면', '원인을 하나씩 분리해서 확인하겠다.']),
            ('원인을 분석한 다음 새로운 방법을 시험하는 과정이라고 생각한다.',
             ['원인을 분석한 다음', '새로운 방법을 시험하는 과정이라고 생각한다.']),
        ):
            parts = self.scope['recovery_clauses'](text)
            self.assertEqual(parts, expected)
            self.assertEqual(' '.join(parts), text)

    def test_recovery_boundary_change_keeps_existing_comma_and_short_fallback(self):
        for text, expected in (
            ('시스템의 상태를 정확하게 이해하고, 변경하기 전에 기준값을',
             ['시스템의 상태를 정확하게 이해하고,', '변경하기 전에 기준값을']),
            ('안녕. 오늘도 필요한 작업을 하나씩 확인해 볼게.',
             ['안녕. 오늘도 필요한', '작업을 하나씩 확인해 볼게.']),
            ('오류가 발생한 건 아니야? 다음 단계로 넘어가도 괜찮을까?',
             ['오류가 발생한 건 아니야?', '다음 단계로 넘어가도 괜찮을까?']),
            ('복구했어. 다음 단계는 사용자의 판단을 기다릴게.',
             ['복구했어. 다음 단계는', '사용자의 판단을 기다릴게.']),
        ):
            self.assertEqual(self.scope['recovery_clauses'](text), expected)

    def test_analyzer_signals_are_separate(self):
        capture = self.scope['GenerationWarnings']()
        def emit(message):
            capture.emit(logging.LogRecord('analyzer', logging.WARNING, '', 0, message, (), None))
        emit('forcing EOS token, long_tail=False, alignment_repetition=False, token_repetition=True')
        self.assertIsNone(capture.reason)
        emit('forcing EOS token, long_tail=tensor(True), alignment_repetition=tensor(False), token_repetition=False')
        self.assertIsNone(capture.reason)
        self.assertEqual(capture.signals, {'token_repetition', 'long_tail', 'forced_eos'})
        emit('forcing EOS token, long_tail=True, alignment_repetition=True, token_repetition=False')
        self.assertEqual(capture.reason, 'internal_alignment_repetition')


class AnalyzerLifecycleTests(unittest.TestCase):
    def test_retire_only_completed_analyzer_hooks(self):
        scope = definitions()
        def attention_forward_hook(*args):
            pass
        attention_forward_hook.__module__ = 'chatterbox.models.t3.inference.alignment_stream_analyzer'
        framework_hook = Mock()
        hooks = {1: attention_forward_hook, 2: framework_hook, 3: attention_forward_hook}
        model = types.SimpleNamespace(t3=types.SimpleNamespace(tfmr=types.SimpleNamespace(
            layers=[types.SimpleNamespace(self_attn=types.SimpleNamespace(_forward_hooks=hooks))])))
        scope['retire_alignment_hooks'](model)
        self.assertEqual(hooks, {2: framework_hook})
        scope['retire_alignment_hooks'](model)
        self.assertEqual(hooks, {2: framework_hook})

    def test_similar_name_from_other_module_is_preserved(self):
        scope = definitions()
        def attention_forward_hook(*args):
            pass
        hooks = {1: attention_forward_hook}
        model = types.SimpleNamespace(t3=types.SimpleNamespace(tfmr=types.SimpleNamespace(
            layers=[types.SimpleNamespace(self_attn=types.SimpleNamespace(_forward_hooks=hooks))])))
        scope['retire_alignment_hooks'](model)
        self.assertIn(1, hooks)

    def test_missing_analyzer_is_noop(self):
        definitions()['retire_alignment_hooks'](types.SimpleNamespace())

    def test_attempt_retires_hooks_even_on_generation_exception(self):
        scope = definitions()
        tree = ast.parse(SOURCE.read_text())
        run = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'run')
        attempt = next(n for n in ast.walk(run) if isinstance(n, ast.FunctionDef) and n.name == 'attempt')
        model = types.SimpleNamespace(generate=Mock(side_effect=RuntimeError('injected')))
        cleanup = Mock()
        scope.update(model=model, item={}, trace=Mock(), retire_alignment_hooks=cleanup)
        exec(compile(ast.Module(body=[attempt], type_ignores=[]), str(SOURCE), 'exec'), scope)
        self.assertEqual(scope['attempt']('text', 1, 0, 0)[0], None)
        cleanup.assert_called_once_with(model)


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        environment = patch.dict(os.environ)
        environment.start(); self.addCleanup(environment.stop)
        for key in list(os.environ):
            if key.startswith('CODEX_ENIKK_TTS_'):
                os.environ.pop(key)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.scope = definitions()

    def job(self, parts=('first', 'second')):
        path = self.root / 'job'
        item = dict(id='test', text=' '.join(parts), queued_ns=time.monotonic_ns())
        path.write_text(json.dumps(item))
        return self.scope['DeliveryJob'](path, item, list(parts))

    def test_stale_job_never_reaches_generation(self):
        path = self.root / 'pending'; path.write_text('old content')
        with patch.dict(os.environ, {'CODEX_ENIKK_TTS_RUN_ID':'B'}):
            self.assertTrue(self.scope['discard_stale_job'](path, {'id':'old', 'run_id':'A'}))
            self.assertFalse(path.exists())
            self.assertEqual((self.root / '.stale-pending').read_text(), 'old content')
            path.write_text('new content')
            self.assertFalse(self.scope['discard_stale_job'](path, {'id':'new', 'run_id':'B'}))
            self.assertTrue(path.exists())

    def test_owner_identity_rejects_pid_reuse_and_dead_owner(self):
        born = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()[19]
        self.assertTrue(self.scope['owner_alive'](f'{os.getpid()}:{born}'))
        self.assertFalse(self.scope['owner_alive'](f'{os.getpid()}:0'))
        self.assertFalse(self.scope['owner_alive']('999999999:0'))

    def test_partial_ack_survives_restart(self):
        job = self.job()
        job.finish(0, 'played')
        self.assertTrue(job.path.exists())
        resumed = self.scope['DeliveryJob'](job.path, json.loads(job.path.read_text()), [])
        self.assertEqual(resumed.parts, ['first', 'second'])
        self.assertEqual(resumed.terminal, {'0': 'PLAYED'})
        resumed.finish(1, 'played')
        self.assertFalse(job.path.exists())
        self.assertTrue(resumed.complete)

    def test_failed_atomic_write_preserves_pending_job(self):
        job = self.job()
        with patch.object(os, 'replace', side_effect=OSError('disk failure')):
            with self.assertRaises(OSError):
                job.finish(0, 'played')
        self.assertEqual(json.loads(job.path.read_text())['delivery']['terminal'], {})
        self.assertFalse(job.complete)

    def test_terminal_record_before_cleanup_does_not_replay(self):
        job = self.job()
        job.item['delivery']['terminal'] = {'0': 'PLAYED', '1': 'PLAYED'}
        job.path.write_text(json.dumps(job.item))
        resumed = self.scope['DeliveryJob'](job.path, json.loads(job.path.read_text()), [])
        self.assertTrue(resumed.complete)
        self.assertFalse(job.path.exists())

    def test_playback_errors_do_not_kill_consumer(self):
        for error in (subprocess.CalledProcessError(1, 'aplay'), OSError('device'), RuntimeError('unexpected')):
            with self.subTest(error=type(error).__name__):
                job = self.job()
                self.scope['subprocess'].run = Mock(side_effect=[error, None])
                ready = queue.Queue()
                for number in range(2):
                    wav = self.root / f'{number}.wav'; wav.write_bytes(b'test')
                    ready.put((job, number, str(wav), time.monotonic_ns(), time.monotonic(), .01))
                thread = threading.Thread(target=self.scope['playback'], args=(ready,), daemon=True)
                thread.start()
                deadline = time.monotonic() + 2
                while ready.unfinished_tasks and time.monotonic() < deadline:
                    time.sleep(.005)
                self.assertEqual(ready.unfinished_tasks, 0)
                self.assertTrue(thread.is_alive())
                self.assertEqual(job.terminal, {'0': 'FAILED_EXPLICITLY', '1': 'PLAYED'})
                self.assertFalse(job.path.exists())
                failed = json.loads((self.root / '.failed-job').read_text())
                self.assertEqual(failed['delivery']['terminal']['0'], 'FAILED_EXPLICITLY')
                self.assertIn('0', failed['delivery']['failures'])
                ready.put(None); thread.join(2)
                self.assertFalse(thread.is_alive())

    def test_run_prefetch_claim_and_delivery_order(self):
        self.exercise_run()

    def test_generation_failure_is_retained_after_two_attempts(self):
        self.exercise_run(fail=True)

    def exercise_run(self, fail=False):
        jobs = self.root / 'jobs'; jobs.mkdir()
        source = jobs / 'job'
        source.write_text(json.dumps(dict(id='normal', text='a|b|c|d|e|f|g|h', queued_ns=time.monotonic_ns())))
        reference = self.root / 'ref'; reference.touch()
        entered = threading.Event(); release = threading.Event(); stop = threading.Event()
        generated = []; played = []; scanned = threading.Event(); queues = []
        class StopRun(Exception):
            pass
        def sleep(_):
            scanned.set()
            if stop.wait(.005):
                raise StopRun()
        def synth(text, **kwargs):
            generated.append(text)
            if fail and text == "d":
                raise RuntimeError("injected generation failure")
            return types.SimpleNamespace(cpu=lambda: types.SimpleNamespace(text=text, shape=(1, 240)))
        def play(args, **kwargs):
            text = Path(args[-1]).read_text()
            if not played:
                entered.set()
                if not release.wait(2):
                    raise RuntimeError('test timed out')
            played.append(text)
        def make_queue():
            result = queue.Queue(); queues.append(result); return result
        model = types.SimpleNamespace(sr=24000, generate=synth, prepare_conditionals=Mock())
        self.scope.update(STATE=self.root, JOBS=jobs, REFERENCE=reference,
            torch=types.SimpleNamespace(cuda=types.SimpleNamespace(is_available=lambda: False, empty_cache=Mock())),
            ChatterboxMultilingualTTS=types.SimpleNamespace(from_pretrained=lambda **kw:model),
            conditioning_state=lambda m:'test', speech_chunks=lambda text, **kwargs:text.split('|'),
            korean_pronunciation=lambda text:text,
            trim_edge_silence=lambda wav,sr:(wav,0,0),
            suspicious_audio=lambda wav,sr,text:(False,'',.01),
            torchaudio=types.SimpleNamespace(save=lambda path,wav,sr:Path(path).write_text(wav.text)),
            queue=types.SimpleNamespace(Queue=make_queue),
            time=types.SimpleNamespace(monotonic=time.monotonic, monotonic_ns=time.monotonic_ns, sleep=sleep))
        self.scope['subprocess'].run = play
        errors = []
        def worker():
            try:self.scope['run']()
            except StopRun:pass
            except Exception as exc:errors.append(exc)
        thread = threading.Thread(target=worker, daemon=True); thread.start()
        try:
            self.assertTrue(entered.wait(2))
            self.assertTrue(scanned.wait(2))
            time.sleep(.04)  # several scans while first WAV is still playing
            self.assertEqual(generated, list('abcddefgh') if fail else list('abcdefgh'))  # prefetch + no duplicate claims
            self.assertTrue(source.exists())
            self.assertEqual(json.loads(source.read_text())['delivery']['terminal'], {'3': 'FAILED_EXPLICITLY'} if fail else {})
            release.set()
            deadline=time.monotonic()+2
            while source.exists() and time.monotonic()<deadline:time.sleep(.005)
            self.assertFalse(source.exists())
            self.assertEqual(played, list('abcefgh') if fail else list('abcdefgh'))
            if fail:
                saved = json.loads((jobs / '.failed-job').read_text())
                self.assertEqual(saved['delivery']['parts'][3], 'd')
                self.assertIn('injected generation failure', saved['delivery']['failures']['3'])
                self.assertEqual(len(saved['delivery']['terminal']), 8)
            self.assertFalse(errors)
        finally:
            release.set();stop.set();thread.join(2)
            if queues:queues[0].put(None)


if __name__ == '__main__':
    unittest.main()
