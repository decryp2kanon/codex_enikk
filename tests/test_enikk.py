import io
import json
import os
import shutil
import socket
import signal
import time
import uuid
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import call, patch
from contextlib import nullcontext

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import enikk


def can_bind_abstract_socket():
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
            probe.bind('\0codex_enikk.test.probe.' + uuid.uuid4().hex)
        return True
    except PermissionError:
        return False


SOCKET_BIND_AVAILABLE = can_bind_abstract_socket()


class EnikkTests(unittest.TestCase):
    def test_supported_codex_versions(self):
        self.assertTrue(enikk.supported_codex_version('codex-cli 0.158.0\n'))
        self.assertTrue(enikk.supported_codex_version('codex-cli 0.160.0\n'))
        self.assertFalse(enikk.supported_codex_version('codex-cli 0.161.0'))
        self.assertFalse(enikk.supported_codex_version('codex-cli 0.160.0-beta'))

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / 'home'
        self.home.mkdir()
        self.data = self.home / '.codex'
        self.enikk_data = self.base / 'enikk-data'
        self.sessions = self.data / 'sessions'
        self.sessions.mkdir(parents=True)
        self.env = os.environ.copy()
        for key in list(self.env):
            if key.startswith('CODEX_ENIKK_TTS_'):
                self.env.pop(key)
        self.env['CODEX_ENIKK_INSTALL_TTS'] = '0'
        self.env.update(HOME=str(self.home), CODEX_HOME=str(self.data),
                        CODEX_ENIKK_DATA_DIR=str(self.enikk_data))
        self.env.pop('CODEX_THREAD_ID', None)
        self.env.update(ARG_CAPTURE=str(self.base / 'args.json'), FAKE_STATUS='0')
        # Do not contend with the user's currently running app during tests.
        self.app_root = self.base / 'app'
        self.app_root.mkdir()
        namespace = '\0codex_enikk.test.' + uuid.uuid4().hex + '.'
        source = (ROOT / 'enikk.py').read_text().replace(
            "INSTANCE_SOCKET_PREFIX = '\\0codex_enikk.instance.'",
            'INSTANCE_SOCKET_PREFIX = ' + repr(namespace))
        if not SOCKET_BIND_AVAILABLE:
            # Only the temporary test copy bypasses the unavailable socket bind.
            # The real source keeps the production singleton; flock is still tested.
            source = source.replace('guard.bind(INSTANCE_SOCKET_PREFIX + str(os.getuid()))', 'pass')
        (self.app_root / 'enikk.py').write_text(source)
        (self.app_root / 'core_runtime.py').write_text('from contextlib import nullcontext\ndef app_server(): return nullcontext(None)\n')
        core_patch = patch.object(enikk, 'app_server', side_effect=lambda: nullcontext(None))
        core_patch.start(); self.addCleanup(core_patch.stop)
        shutil.copy2(ROOT / 'latest.py', self.app_root / 'latest.py')
        shutil.copy2(ROOT / 'persistence.py', self.app_root / 'persistence.py')
        shutil.copy2(ROOT / 'continuity.py', self.app_root / 'continuity.py')
        shutil.copy2(ROOT / 'codex_enikk', self.app_root / 'codex_enikk')
        self.namespace_patch = patch.object(enikk, 'INSTANCE_SOCKET_PREFIX', namespace)
        self.namespace_patch.start()
        self.addCleanup(self.namespace_patch.stop)
        self.patcher = patch.dict(os.environ, self.env, clear=True)
        self.patcher.start()
        latest_patch = patch.object(enikk, "LATEST_TRANSCRIPT_FILE", None)
        latest_patch.start()
        self.addCleanup(latest_patch.stop)
        self.addCleanup(self.patcher.stop)

    def write_session(self, path=None, cwd=None):
        path = path or self.sessions / 'rollout-example.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [
            {'type': 'session_meta', 'payload': {'id': 'example-session', 'cwd': str(cwd or self.base)}},
            {'type': 'event_msg', 'payload': {'type': 'user_message', 'message': '계속 해줘'}},
            {'type': 'event_msg', 'payload': {'type': 'agent_message', 'message': '\x1b[31m작업 완료\x1b[0m'}},
            {'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'duplicate fallback'}]}},
            {'type': 'response_item', 'payload': {'type': 'function_call', 'arguments': 'not transcript'}},
        ]
        path.write_text('\n'.join(json.dumps(x) for x in data) + '\n', encoding='utf-8')
        return path

    def run_cli(self, *args, status=0, prompt="hello\n", seed=True):
        if seed and not list(self.sessions.glob("*.jsonl")):
            self.write_session()
        fakebin = self.base / 'bin'
        fakebin.mkdir(exist_ok=True)
        fake = fakebin / 'codex'
        fake.write_text('''#!/usr/bin/env python3
import os, sys, json
from pathlib import Path
Path(os.environ["ARG_CAPTURE"]).write_text(json.dumps(sys.argv[1:]))
print("NATIVE_TUI_READY", flush=True)
prompt = sys.stdin.read()
p = Path(os.environ["CODEX_HOME"]) / "sessions" / "rollout-example.jsonl"
with p.open("a") as out:
    out.write(json.dumps({"type": "event_msg", "payload": {"type": "user_message", "message": prompt}}) + "\\n")
print("native reply")
sys.exit(int(os.environ["FAKE_STATUS"]))
''')
        fake.chmod(0o755)
        env = self.env | {'PATH': str(fakebin) + os.pathsep + os.environ['PATH'],
                          'FAKE_STATUS': str(status)}
        return subprocess.run([str(self.app_root / 'codex_enikk'), *args], cwd=self.base, env=env, input=prompt, capture_output=True, text=True)

    def test_default_resume_backup_and_log(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.base / 'args.json').read_text()), ['resume', 'example-session', '--dangerously-bypass-approvals-and-sandbox', '--no-daemon', '-c', 'notify=[]'])
        self.assertEqual(len(list((self.enikk_data / 'backups').glob('*.tar.gz'))), 2)
        self.assertIn('hello', (self.enikk_data / 'transcripts/codex-session-example-session-part-000001.txt').read_text())
        self.assertFalse((self.data / 'AGENTS.md').exists())

    def test_guarded_restart_missing_pin_or_modified_source_never_launches(self):
        self.assertEqual(self.run_cli().returncode, 0)
        capture = self.base / 'args.json'
        capture.unlink()
        pin = self.data / 'enikk-continuity.json'
        saved_pin = pin.read_bytes()
        pin.unlink()
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(capture.exists())
        self.assertFalse(pin.exists())
        pin.write_bytes(saved_pin)
        with (self.sessions / 'rollout-example.jsonl').open('ab') as out:
            out.write(b'corrupt\n')
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertFalse(capture.exists())

    def test_live_integrity_failure_stops_native_child_and_preserves_journal(self):
        self.assertEqual(self.run_cli().returncode, 0)
        source = self.app_root / 'enikk.py'
        source.write_text(source.read_text().replace('time.monotonic() + 60', 'time.monotonic() + .1').replace('stop.wait(2)', 'stop.wait(.05)'))
        journal = next((self.enikk_data / 'continuity').glob('*/original.jsonl'))
        original = journal.read_bytes()
        fake = self.base / 'bin/codex'
        fake.write_text("#!/usr/bin/env python3\nimport os,time\nfrom pathlib import Path\np=Path(os.environ['CODEX_HOME'])/'sessions/rollout-example.jsonl'\nwith p.open('ab') as out: out.write(b'broken\\n')\ntime.sleep(30)\n")
        env = self.env | {'PATH': str(self.base / 'bin') + os.pathsep + os.environ['PATH']}
        result = subprocess.run([str(self.app_root / 'codex_enikk')], cwd=self.base,
                                env=env, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('연속성 검사 실패', result.stderr)
        self.assertEqual(journal.read_bytes(), original)

    def test_guard_cli_audit_and_search_do_not_launch_or_rewrite_instructions(self):
        (self.data / 'AGENTS.md').write_text('# Existing user instructions\n')
        self.assertEqual(self.run_cli(prompt='유키짱').returncode, 0)
        capture = self.base / 'args.json'
        capture.unlink()
        instructions = (self.data / 'AGENTS.md').read_bytes()
        result = self.run_cli('--continuity-check')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['checkpoint_present'])
        result = self.run_cli('--history-search', '유키짱', '--direct-user-only')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(capture.exists())
        self.assertEqual((self.data / 'AGENTS.md').read_bytes(), instructions)

    def test_startup_preserves_global_instructions_without_adding_identity(self):
        agents = self.data / 'AGENTS.md'
        agents.write_text('# Existing\nKeep this.\n')
        original = agents.read_bytes()
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(agents.read_bytes(), original)

    def test_resume_alias_and_exit_code(self):
        result = self.run_cli('--resume', status=7)
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(json.loads((self.base / 'args.json').read_text()), ['resume', 'example-session', '--dangerously-bypass-approvals-and-sandbox', '--no-daemon', '-c', 'notify=[]'])

    def test_native_options_forwarded(self):
        args = ('--resume', '--yolo', '-m', 'chosen-model', '-i', '/tmp/photo with spaces.png', '--no-alt-screen')
        result = self.run_cli(*args)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.base / 'args.json').read_text()),
                         ['resume', 'example-session', '--dangerously-bypass-approvals-and-sandbox', '--no-daemon', '-c', 'notify=[]',
                          '-m', 'chosen-model', '-i', '/tmp/photo with spaces.png', '--no-alt-screen'])

    def test_yolo_aliases_do_not_duplicate_flag_or_rewrite_literal_prompt(self):
        flag = '--dangerously-bypass-approvals-and-sandbox'
        result = self.run_cli('--yolo', flag, '--', '--yolo')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.base / 'args.json').read_text()),
                         ['resume', 'example-session', flag, '--no-daemon', '-c', 'notify=[]', '--', '--yolo'])

    def test_no_session_does_not_create_one(self):
        result = self.run_cli(seed=False)
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.base / 'args.json').exists())

    def test_slash_commands_and_multiline_input_reach_codex(self):
        prompt = '/model\n/new\n/resume\nmultiline text\n'
        result = self.run_cli(prompt=prompt)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(prompt, (self.enikk_data / 'transcripts/codex-session-example-session-part-000001.txt').read_text())
        self.assertIn('native reply', result.stdout)
        self.assertNotIn('나 >', result.stdout)

    def test_first_launch_finds_latest_session_outside_cwd(self):
        older = self.write_session(self.sessions / 'old.jsonl', cwd=self.base / 'old-project')
        newer = self.write_session(self.sessions / 'new.jsonl', cwd=self.base / 'new-project')
        newer.write_text(newer.read_text().replace('example-session', 'latest-session'))
        os.utime(older, ns=(100, 100))
        os.utime(newer, ns=(200, 200))
        with patch('pathlib.Path.cwd', return_value=self.base / 'empty-folder'):
            self.assertEqual(enikk.pinned_session(), 'latest-session')

    def test_current_project_precedes_global_latest(self):
        local = self.write_session(cwd=self.base)
        other = self.write_session(self.sessions / 'other.jsonl', cwd=self.base / 'other')
        other.write_text(other.read_text().replace('example-session', 'other-session'))
        os.utime(local, ns=(100, 100))
        os.utime(other, ns=(200, 200))
        with patch('pathlib.Path.cwd', return_value=self.base):
            self.assertEqual(enikk.pinned_session(), 'example-session')

    def test_pin_survives_newer_session_and_cwd_change(self):
        self.write_session()
        with patch('pathlib.Path.cwd', return_value=self.base):
            self.assertEqual(enikk.pinned_session(), 'example-session')
        newer = self.write_session(self.sessions / 'newer.jsonl', cwd=self.base)
        newer.write_text(newer.read_text().replace('example-session', 'other-id'))
        with patch('pathlib.Path.cwd', return_value=self.base / 'elsewhere'):
            self.assertEqual(enikk.pinned_session(), 'example-session')
        (self.sessions / 'rollout-example.jsonl').unlink()
        with self.assertRaises(ValueError):
            enikk.pinned_session()

    def test_process_lock_prevents_parallel_conversations(self):
        import fcntl
        with (self.data / 'enikk-continuity.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.run_cli()
            self.assertEqual(result.returncode, 1)
            self.assertFalse((self.base / 'args.json').exists())

    @unittest.skipUnless(SOCKET_BIND_AVAILABLE, 'sandbox denies abstract socket bind')
    def test_single_instance_blocks_different_home_and_codex_home(self):
        with enikk.single_instance():
            other = self.base / 'other-home'
            other.mkdir()
            self.env['HOME'] = str(other)
            self.env['CODEX_HOME'] = str(other / '.codex')
            result = self.run_cli()
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn('이미 실행 중', result.stderr)
            self.assertFalse((other / '.codex').exists())
            self.assertFalse((self.base / 'args.json').exists())
        # The same command succeeds after the first instance releases its lock.
        self.env['HOME'] = str(self.home)
        self.env['CODEX_HOME'] = str(self.data)
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(SOCKET_BIND_AVAILABLE, 'sandbox denies abstract socket bind')
    def test_two_running_apps_block_second_and_allow_after_exit(self):
        import time
        self.run_cli(prompt='')  # Prepare fake executable and an existing session.
        env = self.env | {'PATH': str(self.base / 'bin') + os.pathsep + os.environ['PATH']}
        with tempfile.TemporaryFile(mode='w+') as output:
            first = subprocess.Popen([str(self.app_root / 'codex_enikk')], cwd=self.base, env=env,
                                     stdin=subprocess.PIPE, stdout=output, stderr=output, text=True)
            try:
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    output.seek(0)
                    if 'NATIVE_TUI_READY' in output.read():
                        break
                    if first.poll() is not None:
                        self.fail('First app exited before opening its input prompt')
                    time.sleep(0.02)
                else:
                    self.fail('First app did not reach its input prompt')
                second = self.run_cli()
                self.assertEqual(second.returncode, 1, second.stderr)
                self.assertIn('이미 실행 중', second.stderr)
                self.assertIsNone(first.poll())
            finally:
                first.communicate(input='', timeout=5)
            self.assertEqual(first.returncode, 0)
        self.assertEqual(self.run_cli().returncode, 0)

    @unittest.skipUnless(SOCKET_BIND_AVAILABLE, 'sandbox denies abstract socket bind')
    def test_child_does_not_hold_instance_lock_after_parent_guard_closes(self):
        with enikk.single_instance() as guard:
            child = subprocess.Popen([sys.executable, '-c', 'import sys; sys.stdin.read()'],
                                     stdin=subprocess.PIPE, close_fds=True)
        try:
            with enikk.single_instance():
                pass
        finally:
            child.communicate(input=b'', timeout=5)
        with enikk.single_instance():
            pass

    def test_native_child_inherits_terminal_streams(self):
        python = self.home / 'Apps/chatterbox-yuki/.venv/bin/python'
        python.parent.mkdir(parents=True)
        python.touch()
        with patch.dict(os.environ, {'CODEX_ENIKK_STREAMING_TTS': '0'}), patch('enikk.shutil.which', return_value='/usr/bin/aplay'), patch('enikk.subprocess.Popen') as launch:
            launch.return_value.wait.return_value = 0
            self.assertEqual(enikk.conversation('example-session', 42, ['-i', 'picture.png']), 0)
            launch.assert_called_once_with(
                ['codex', 'resume', 'example-session', '--dangerously-bypass-approvals-and-sandbox',
                 '--no-daemon', '-c', 'notify=[]', '-i', 'picture.png'], close_fds=True)

    def test_pty_is_passed_to_native_codex(self):
        self.run_cli(prompt='')
        fake = self.base / 'bin/codex'
        fake.write_text('''#!/usr/bin/env python3
import json, os
from pathlib import Path
Path(os.environ['ARG_CAPTURE']).write_text(json.dumps([os.isatty(fd) for fd in (0, 1, 2)]))
print('native terminal')
''')
        master, slave = os.openpty()
        try:
            env = self.env | {'PATH': str(self.base / 'bin') + os.pathsep + os.environ['PATH']}
            child = subprocess.Popen([str(self.app_root / 'codex_enikk')], cwd=self.base,
                                     env=env, stdin=slave, stdout=slave, stderr=slave)
            try:
                self.assertEqual(child.wait(timeout=5), 0)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait()
            self.assertEqual(json.loads((self.base / 'args.json').read_text()), [True, True, True])
        finally:
            os.close(master)
            os.close(slave)

    # Voice lifecycle tests moved to test_independent_tts; core must never own it.
    def test_core_has_no_voice_lifecycle(self):
        self.assertFalse(hasattr(enikk, 'tts_run'))
        self.assertFalse(hasattr(enikk, 'streaming_tts'))

    def test_ctrl_c_is_left_to_native_child(self):
        with patch('enikk.subprocess.Popen') as launch:
            launch.return_value.wait.side_effect = [KeyboardInterrupt(), 0, 0]
            self.assertEqual(enikk.conversation('example-session', 42), 0)
            launch.return_value.terminate.assert_not_called()

    def test_exit_and_signals_cleanup_detached_children(self):
        for mode in ('normal', 'term', 'hup'):
            with self.subTest(mode=mode):
                self.run_cli(prompt='')
                marker = self.base / ('child-' + mode)
                fake = self.base / 'bin/codex'
                fake.write_text("""#!/usr/bin/env python3
import os, signal, time
from pathlib import Path
marker = Path(os.environ['CHILD_MARKER'])
if os.fork() == 0:
    os.setsid()
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    marker.write_text(str(os.getpid()))
    while True: time.sleep(1)
while not marker.exists(): time.sleep(0.01)
if os.environ['EXIT_MODE'] == 'normal': raise SystemExit(0)
while True: time.sleep(1)
""")
                env = self.env | {'PATH': str(self.base / 'bin') + os.pathsep + os.environ['PATH'],
                                  'CHILD_MARKER': str(marker), 'EXIT_MODE': mode}
                unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
                app = subprocess.Popen([str(self.app_root / 'codex_enikk')], env=env,
                                       cwd=self.base, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                try:
                    deadline = time.monotonic() + 5
                    while not marker.exists() and time.monotonic() < deadline:
                        time.sleep(0.02)
                    self.assertTrue(marker.exists())
                    pid = int(marker.read_text())
                    if mode != 'normal':
                        app.send_signal(signal.SIGTERM if mode == 'term' else signal.SIGHUP)
                    _, err = app.communicate(timeout=10)
                    self.assertEqual(app.returncode, {'normal': 0, 'term': 143, 'hup': 129}[mode], err)
                    self.assertFalse(Path('/proc/' + str(pid)).exists(), 'Detached child survived')
                    self.assertIsNone(unrelated.poll(), 'Unrelated process was terminated')
                    self.assertEqual(self.run_cli().returncode, 0, 'Instance lock not released')
                finally:
                    if app.poll() is None:
                        app.kill()
                        app.wait()
                    unrelated.terminate()
                    unrelated.wait()

    def test_pin_is_backed_up_and_restored(self):
        self.write_session()
        with patch('pathlib.Path.cwd', return_value=self.base):
            enikk.pinned_session()
        target = enikk.backup()
        state = self.data / 'enikk-continuity.json'
        state.unlink()
        enikk.restore(target)
        self.assertEqual(enikk.pinned_session(), 'example-session')
        self.assertEqual(state.stat().st_mode & 0o777, 0o600)

    def test_backup_failure_prevents_launch(self):
        self.enikk_data.mkdir()
        (self.enikk_data / 'backups').write_text('not a directory')
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.base / 'args.json').exists())

    def test_transcript_failure_still_backs_up_session(self):
        self.enikk_data.mkdir()
        (self.enikk_data / 'transcripts').write_text('not a directory')
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(list((self.enikk_data / 'backups').glob('*.tar.gz'))), 2)
        self.assertTrue((self.sessions / 'rollout-example.jsonl').exists())

    def test_archive_contents_permissions_and_exact_bytes(self):
        session = self.write_session()
        with session.open('ab') as out:
            out.write(b'{"partial":')
        (self.data / 'auth.json').write_text('SECRET')
        (self.data / 'config.toml').write_text('SECRET')
        (self.data / 'history.jsonl').write_text('{"history": true}\n')
        archived = self.data / 'archived_sessions/old.jsonl'
        archived.parent.mkdir()
        archived.write_text('{}\n')
        target = enikk.backup()
        self.assertEqual(target.stat().st_mode & 0o777, 0o600)
        self.assertEqual(target.parent.stat().st_mode & 0o777, 0o700)
        with tarfile.open(target) as archive:
            self.assertEqual(set(archive.getnames()), {'manifest.json', 'codex/sessions/rollout-example.jsonl', 'codex/history.jsonl', 'codex/archived_sessions/old.jsonl'})
            self.assertEqual(archive.extractfile('codex/sessions/rollout-example.jsonl').read(), session.read_bytes())

    def test_restore_missing_and_preserve_existing(self):
        session = self.write_session()
        original = session.read_bytes()
        target = enikk.backup()
        session.unlink()
        self.assertEqual(enikk.restore(target), 1)
        self.assertEqual(session.read_bytes(), original)
        session.write_text('newer content')
        self.assertEqual(enikk.restore(target), 0)
        self.assertEqual(session.read_text(), 'newer content')

    def test_reject_malicious_archive_before_writing(self):
        target = self.base / 'evil.tar.gz'
        with tarfile.open(target, 'w:gz') as archive:
            for name in ['codex/sessions/good.jsonl', 'codex/../../escape.jsonl']:
                entry = tarfile.TarInfo(name)
                entry.size = 3
                archive.addfile(entry, io.BytesIO(b'{}\n'))
        with self.assertRaises(ValueError):
            enikk.restore(target)
        self.assertFalse((self.sessions / 'good.jsonl').exists())

    def test_transcript_filters_and_partial_json(self):
        session = self.write_session()
        with session.open('a') as out:
            out.write('{"partial":')
        text = enikk.transcript(session)
        self.assertIn('계속 해줘', text)
        self.assertIn('작업 완료', text)
        self.assertNotIn('\x1b', text)
        self.assertNotIn('duplicate', text)
        self.assertNotIn('not transcript', text)

    def test_completed_item_and_response_fallback(self):
        session = self.sessions / 'formats.jsonl'
        session.write_text(json.dumps({'type': 'event_msg', 'payload': {'type': 'item_completed', 'item': {'type': 'AgentMessage', 'content': [{'type': 'Text', 'text': 'done'}]}}}))
        self.assertIn('done', enikk.transcript(session))
        session.write_text(json.dumps({'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'fallback'}]}}))
        self.assertIn('fallback', enikk.transcript(session))

    def test_transcript_parts_respect_real_10mb_limit(self):
        text = 'a' * enikk.TRANSCRIPT_PART_BYTES + '한글🙂' * 10
        output = self.base / 'parts'
        parts = enikk.write_transcript_parts(output, 'test', text)
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0].stat().st_size, 10_000_000)
        self.assertTrue(all(p.stat().st_size <= 10_000_000 for p in parts))
        self.assertEqual(''.join(p.read_text() for p in parts), text)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in parts))

    def test_transcript_parts_preserve_unicode_and_completed_parts(self):
        output = self.base / 'parts'
        text = '가나다🙂abc\n' * 12
        parts = enikk.write_transcript_parts(output, 'test', text, limit=31)
        self.assertGreater(len(parts), 2)
        self.assertTrue(all(p.stat().st_size <= 31 for p in parts))
        self.assertEqual(''.join(p.read_text() for p in parts), text)
        original = parts[0].stat()
        parts = enikk.write_transcript_parts(output, 'test', text + '추가 대화🙂', limit=31)
        self.assertEqual(parts[0].stat().st_mtime_ns, original.st_mtime_ns)
        self.assertEqual(parts[0].stat().st_ino, original.st_ino)
        self.assertEqual(''.join(p.read_text() for p in parts), text + '추가 대화🙂')

    def test_transcript_restart_partial_line_and_legacy_preservation(self):
        session = self.write_session()
        output = self.base / 'logs'
        output.mkdir()
        legacy = output / 'codex-session-example-session.txt'
        legacy.write_text('legacy conversation')
        baseline = {}
        enikk.export_changed(baseline, self.base, output, 'example-session')
        part = output / 'codex-session-example-session-part-000001.txt'
        original = part.stat().st_mtime_ns
        enikk.export_changed({}, self.base, output, 'example-session')
        self.assertEqual(part.stat().st_mtime_ns, original)
        event = json.dumps({'type': 'event_msg', 'payload': {'type': 'agent_message', 'message': 'new answer'}})
        with session.open('a') as out:
            out.write(event[:-1])
        enikk.export_changed(baseline, self.base, output, 'example-session')
        self.assertNotIn('new answer', part.read_text())
        with session.open('a') as out:
            out.write('}\n')
        enikk.export_changed(baseline, self.base, output, 'example-session')
        self.assertIn('new answer', part.read_text())
        self.assertEqual(legacy.read_text(), 'legacy conversation')

    def test_shortened_source_archives_surplus_parts(self):
        output = self.base / 'parts'
        previous = enikk.write_transcript_parts(output, 'test', 'x' * 100, limit=31)
        old_tail = previous[-1].read_bytes()
        parts = enikk.write_transcript_parts(output, 'test', 'short', limit=31)
        self.assertEqual(len(list(output.glob('*.txt'))), 1)
        self.assertEqual(parts[0].read_text(), 'short')
        self.assertEqual(next(output.glob('superseded-*/' + previous[-1].name)).read_bytes(), old_tail)

    def test_live_saver_once_exports_existing_session(self):
        self.write_session()
        result = subprocess.run([sys.executable, str(ROOT / 'save_transcript.py'),
                                 '--session', 'example-session', '--once'],
                                env=self.env, cwd=self.base, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('계속 해줘', (self.enikk_data / 'transcripts/codex-session-example-session-part-000001.txt').read_text())

    def test_latest_keeps_whole_messages_and_latest_final(self):
        path = self.write_session()
        def append(kind, body, phase=None):
            item = {'type': kind, 'content': [{'type': 'Text', 'text': body}]}
            if phase:
                item['phase'] = phase
            with path.open('a') as out:
                out.write(json.dumps({'type': 'event_msg', 'payload': {'type': 'item_completed', 'item': item}}) + '\n')
        result = '중요한 결과🙂'
        append('AgentMessage', result, 'final_answer')
        append('AgentMessage', '오래된진행' * 100, 'commentary')
        append('AgentMessage', '숨긴추론', 'analysis')
        append('UserMessage', '최신 질문')
        output = enikk.write_latest_transcript(path, target=100)
        data = output.read_text()
        self.assertIn(result, data)
        self.assertIn('최신 질문', data)
        self.assertNotIn('오래된진행', data)
        self.assertNotIn('숨긴추론', data)
        self.assertLessEqual(output.stat().st_size, 100)
        huge = '한글🙂' * 30_000
        append('AgentMessage', huge, 'final_answer')
        enikk.write_latest_transcript(path)
        self.assertGreater(output.stat().st_size, 200_000)
        self.assertEqual(output.read_text(), '[CODEX 최종]\n' + huge + '\n\n')
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_latest_is_separate_and_does_not_change_archive(self):
        session = self.write_session()
        original = session.read_bytes()
        output = self.base / 'logs'
        enikk.export_changed({}, self.base, output, 'example-session')
        parts = sorted(output.glob('*.txt'))
        self.assertEqual(''.join(p.read_text() for p in parts), enikk.transcript(session))
        latest = next((self.enikk_data / 'latest').glob('codex-latest-*.txt'))
        self.assertIn('작업 완료', latest.read_text())
        self.assertEqual(session.read_bytes(), original)
        mtime = latest.stat().st_mtime_ns
        enikk.write_latest_transcript(session)
        self.assertEqual(latest.stat().st_mtime_ns, mtime)
        other = self.write_session(self.sessions / 'other.jsonl')
        other.write_text(other.read_text().replace('example-session', 'other-session').replace('작업 완료', '다른 대화'))
        enikk.export_changed({}, self.base, output, 'example-session')
        self.assertNotIn('다른 대화', latest.read_text())

    def test_latest_filename_per_run_and_directory_permissions(self):
        session = self.write_session()
        directory = self.enikk_data / 'latest'
        first = enikk.write_latest_transcript(session)
        self.assertRegex(first.name, r'^codex-latest-\d{6}-\d{6}\.txt$')
        self.assertEqual(enikk.write_latest_transcript(session), first)
        with patch.object(enikk, 'LATEST_TRANSCRIPT_FILE', None):
            second = enikk.write_latest_transcript(session)
        self.assertNotEqual(first, second)
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual(directory.stat().st_mode & 0o777, 0o700)

    def test_storage_is_independent_of_cwd_and_rejects_git_repositories(self):
        session = self.write_session()
        repository = self.base / 'project'
        (repository / '.git').mkdir(parents=True)
        with patch('pathlib.Path.cwd', return_value=repository):
            enikk.write_latest_transcript(session)
            enikk.export_changed({}, repository, enikk.transcript_dir(), 'example-session')
        self.assertFalse(list(repository.glob('codex-*.txt')))
        self.assertTrue(list((self.enikk_data / 'latest').glob('codex-latest-*.txt')))
        self.assertTrue(list((self.enikk_data / 'transcripts').glob('codex-session-*.txt')))
        with self.assertRaises(ValueError):
            enikk.write_transcript_parts(repository / 'exports', 'test', 'text')

    def test_exports_only_matching_cwd(self):
        self.write_session(cwd=self.base / 'other-project')
        output = self.base / 'logs'
        enikk.export_changed({}, self.base, output)
        self.assertFalse(output.exists())
        self.write_session(cwd=self.base)
        enikk.export_changed({}, self.base, output)
        self.assertTrue((output / 'codex-session-example-session-part-000001.txt').exists())

    def test_backup_symlink_rejected(self):
        private = self.base / 'secret.jsonl'
        private.write_text('secret')
        (self.sessions / 'link.jsonl').symlink_to(private)
        with self.assertRaises(OSError):
            enikk.backup()
        self.assertEqual(list((self.enikk_data / 'backups').iterdir()), [])

    def test_install_uninstall_global_stage_and_user_prefix(self):
        for staged in (True, False):
            with self.subTest(staged=staged):
                env = self.env | ({'DESTDIR': str(self.base / 'stage'), 'PREFIX': '/usr/local'} if staged else {'DESTDIR': '', 'PREFIX': str(self.base / 'user-prefix')})
                prefix = Path(env['DESTDIR'] + env['PREFIX'])
                result = subprocess.run([str(ROOT / 'install.sh')], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                compat_help = subprocess.run([str(prefix / 'bin/check-codex-compat'), '--help'], env=env, capture_output=True, text=True)
                self.assertEqual(compat_help.returncode, 0, compat_help.stderr)
                self.assertFalse((prefix / 'lib/codex_enikk/tts').exists())
                self.assertEqual((prefix / 'lib/codex_enikk/core_runtime.py').read_bytes(), (ROOT / 'core_runtime.py').read_bytes())
                for name in ('codex_enikk', 'codex_session_save.sh'):
                    result = subprocess.run([str(prefix / 'bin' / name), '--version'], env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), f'codex_enikk {enikk.VERSION}')
                result = subprocess.run([str(prefix / 'bin/codex_enikk_restore'), '--help'], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                # A command replaced by the user must survive uninstall.
                command = prefix / 'bin/codex_enikk_restore'
                command.unlink()
                command.write_text('user replacement')
                sentinel = self.data / 'history.jsonl'
                sentinel.write_text('retain me')
                for _ in range(2):
                    result = subprocess.run([str(ROOT / 'uninstall.sh')], env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse((prefix / 'lib/codex_enikk').exists())
                self.assertFalse((prefix / 'bin/codex_enikk').is_symlink())
                self.assertEqual(command.read_text(), 'user replacement')
                self.assertEqual(sentinel.read_text(), 'retain me')

    def test_update_preserves_previous_version_and_sessions(self):
        prefix = self.base / 'installed'
        env = self.env | {'PREFIX': str(prefix), 'DESTDIR': ''}
        result = subprocess.run([str(ROOT / 'install.sh')], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        lib = prefix / 'lib/codex_enikk'
        (lib / 'enikk.py').write_text('print("old version")\n')
        (lib / 'VERSION').write_text('2.0.2\n')
        voice = prefix / 'lib/enikk_tts/releases/sentinel'
        voice.mkdir(parents=True); (voice / 'engine.py').write_text('voice unchanged')
        session = self.write_session()
        original = session.read_bytes()
        result = subprocess.run(['bash', str(ROOT / 'update.sh')], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f'codex_enikk {enikk.VERSION}', result.stdout)
        previous = list(lib.glob('previous-*'))
        self.assertEqual(len(previous), 1)
        self.assertEqual((previous[0] / 'enikk.py').read_text(), 'print("old version")\n')
        self.assertEqual((lib / 'enikk.py').read_bytes(), (ROOT / 'enikk.py').read_bytes())
        self.assertEqual(session.read_bytes(), original)
        self.assertEqual((voice / 'engine.py').read_text(), 'voice unchanged')
        for name in ('handoff_command.py', 'submission_arbiter.py', 'trigger_transport.py',
                     'trigger_service.py', 'trigger_client.py', 'enikk-trigger'):
            self.assertEqual((lib / name).read_bytes(), (ROOT / name).read_bytes())
        self.assertEqual((prefix / 'bin/enikk-trigger').resolve(), lib / 'enikk-trigger')
        trigger_help = subprocess.run([str(prefix / 'bin/enikk-trigger'), '--help'], env=env,
                                      capture_output=True, text=True)
        self.assertEqual(trigger_help.returncode, 0, trigger_help.stderr)
        self.assertFalse((lib / 'tts').exists())
        (lib / '.installed-by-codex-enikk').write_text('unmanaged')
        result = subprocess.run(['bash', str(ROOT / 'update.sh')], env=env, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(list(lib.glob('previous-*'))), 1)

    def test_stream_dependency_is_pinned_in_existing_venv(self):
        setup = (ROOT / 'tts/setup-tts.sh').read_text()
        self.assertIn('m.version("websocket-client") == "1.9.0"', setup)
        self.assertIn('pip install \'websocket-client==1.9.0\'', setup)
        self.assertIn('elif [[ ! -f "$reference" ]]', setup)
        self.assertNotIn('rm -rf', setup)
        self.assertIn('pulseaudio-utils', setup)
        self.assertIn('command -v paplay', setup)

    def test_install_collision_preserves_existing(self):
        prefix = self.base / 'prefix'
        (prefix / 'bin').mkdir(parents=True)
        existing = prefix / 'bin/codex_enikk'
        existing.write_text('original')
        result = subprocess.run([str(ROOT / 'install.sh')], env=self.env | {'PREFIX': str(prefix), 'DESTDIR': ''}, capture_output=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(existing.read_text(), 'original')
        self.assertFalse((prefix / 'lib/codex_enikk').exists())


if __name__ == '__main__':
    unittest.main()
