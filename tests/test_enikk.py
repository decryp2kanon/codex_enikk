import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import enikk


class EnikkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.home = self.base / 'home'
        self.home.mkdir()
        self.data = self.home / '.codex'
        self.sessions = self.data / 'sessions'
        self.sessions.mkdir(parents=True)
        self.env = os.environ.copy()
        self.env.update(HOME=str(self.home), CODEX_HOME=str(self.data),
                        CODEX_ENIKK_BACKUP_DIR=str(self.base / 'backups'),
                        CODEX_ENIKK_LOG_DIR=str(self.base / 'logs'))
        self.env.pop('CODEX_THREAD_ID', None)
        self.patcher = patch.dict(os.environ, self.env, clear=True)
        self.patcher.start()
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

    def run_cli(self, *args, status=0, prompt="hello\n", seed=True, wrong_thread=False, incomplete=False):
        if seed and not list(self.sessions.glob("*.jsonl")):
            self.write_session()
        fakebin = self.base / 'bin'
        fakebin.mkdir(exist_ok=True)
        fake = fakebin / 'codex'
        fake.write_text('#!/usr/bin/env python3\nimport os,sys,json\nfrom pathlib import Path\n'
                        'Path(os.environ["ARG_CAPTURE"]).write_text(json.dumps(sys.argv[1:]))\n'
                        'prompt=sys.stdin.read()\n'
                        'p=Path(os.environ["CODEX_HOME"])/"sessions"/"rollout-example.jsonl"\n'
                        'with p.open("a") as out: out.write(json.dumps({"type":"event_msg","payload":{"type":"user_message","message":prompt}})+"\\n")\n'
                        'print(json.dumps({"type":"thread.started","thread_id":("wrong-id" if os.environ["WRONG_THREAD"] == "1" else sys.argv[3])}))\n'
                        'print(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":"reply"}}))\n'
                        'if os.environ["INCOMPLETE"] != "1": print(json.dumps({"type":"turn.completed"}))\n'
                        'sys.exit(int(os.environ["FAKE_STATUS"]))\n')
        fake.chmod(0o755)
        env = self.env | {'PATH': str(fakebin) + os.pathsep + os.environ['PATH'],
                          'ARG_CAPTURE': str(self.base / 'args.json'), 'FAKE_STATUS': str(status), 'WRONG_THREAD': str(int(wrong_thread)), 'INCOMPLETE': str(int(incomplete))}
        return subprocess.run([str(ROOT / 'codex_enikk'), *args], cwd=self.base, env=env, input=prompt, capture_output=True, text=True)

    def test_default_resume_backup_and_log(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.base / 'args.json').read_text()), ['exec', 'resume', 'example-session', '--json', '--skip-git-repo-check', '-'])
        self.assertEqual(len(list((self.base / 'backups').glob('*.tar.gz'))), 3)
        self.assertIn('hello', (self.base / 'logs/codex-session-example-session.txt').read_text())

    def test_resume_alias_and_exit_code(self):
        result = self.run_cli('--resume', status=7)
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual(json.loads((self.base / 'args.json').read_text()), ['exec', 'resume', 'example-session', '--json', '--skip-git-repo-check', '-'])

    def test_session_switching_options_rejected(self):
        for args in [('--fork',), ('fork',), ('--resume', 'different-id'), ('--last',), ('--ephemeral',), ('--', '--fork')]:
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertFalse((self.base / 'args.json').exists())

    def test_no_session_does_not_create_one(self):
        result = self.run_cli(seed=False)
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.base / 'args.json').exists())

    def test_slash_commands_never_reach_codex(self):
        result = self.run_cli(prompt='/fork\n/new\n/resume\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.base / 'args.json').exists())

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

    def test_wrong_thread_or_incomplete_turn_stops(self):
        for settings in ({'wrong_thread': True}, {'incomplete': True}):
            result = self.run_cli(**settings)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertEqual(json.loads((self.data / 'enikk-continuity.json').read_text())['session_id'], 'example-session')

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

    def test_new_rejected_without_launch(self):
        result = self.run_cli('--new')
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.base / 'args.json').exists())
        self.assertFalse((self.base / 'backups').exists())

    def test_backup_failure_prevents_launch(self):
        (self.base / 'backups').write_text('not a directory')
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.base / 'args.json').exists())

    def test_transcript_failure_still_backs_up_session(self):
        (self.base / 'logs').write_text('not a directory')
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(list((self.base / 'backups').glob('*.tar.gz'))), 3)
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
        session.write_text(json.dumps({'type': 'event_msg', 'payload': {'type': 'item_completed', 'item': {'type': 'AgentMessage', 'content': [{'type': 'text', 'text': 'done'}]}}}))
        self.assertIn('done', enikk.transcript(session))
        session.write_text(json.dumps({'type': 'response_item', 'payload': {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'fallback'}]}}))
        self.assertIn('fallback', enikk.transcript(session))

    def test_exports_only_matching_cwd(self):
        self.write_session(cwd=self.base / 'other-project')
        output = self.base / 'logs'
        enikk.export_changed({}, self.base, output)
        self.assertFalse(output.exists())
        self.write_session(cwd=self.base)
        enikk.export_changed({}, self.base, output)
        self.assertTrue((output / 'codex-session-example-session.txt').exists())

    def test_backup_symlink_rejected(self):
        private = self.base / 'secret.jsonl'
        private.write_text('secret')
        (self.sessions / 'link.jsonl').symlink_to(private)
        with self.assertRaises(OSError):
            enikk.backup()
        self.assertEqual(list((self.base / 'backups').iterdir()), [])

    def test_install_uninstall_global_stage_and_user_prefix(self):
        for staged in (True, False):
            with self.subTest(staged=staged):
                env = self.env | ({'DESTDIR': str(self.base / 'stage'), 'PREFIX': '/usr/local'} if staged else {'DESTDIR': '', 'PREFIX': str(self.base / 'user-prefix')})
                prefix = Path(env['DESTDIR'] + env['PREFIX'])
                result = subprocess.run([str(ROOT / 'install.sh')], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                for name in ('codex_enikk', 'codex_session_save.sh'):
                    result = subprocess.run([str(prefix / 'bin' / name), '--version'], env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout.strip(), 'codex_enikk 2.0.0')
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
