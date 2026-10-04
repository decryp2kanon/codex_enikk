import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import enikk


class LifecycleTests(unittest.TestCase):
    def test_disabled_has_no_process_or_endpoint(self):
        with patch.dict(os.environ, {'CODEX_ENIKK_TRIGGER': '0'}), patch('enikk.subprocess.Popen') as launch:
            with enikk.submission_proxy('unix:///old', 'same-thread', Path('/python')) as endpoint:
                self.assertEqual(endpoint, 'unix:///old')
            launch.assert_not_called()

    def test_wrapper_owns_proxy_and_shutdown_on_body_error(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Mock(); process.poll.return_value = None
            def launch(args, **kwargs):
                self.assertIn('same-thread', args)
                self.assertTrue(kwargs['start_new_session'])
                Path(args[args.index('--ready')+1]).write_text('{}')
                return process
            version = subprocess.CompletedProcess([], 0, 'codex-cli 0.160.0\n', '')
            with patch.dict(os.environ, {'CODEX_ENIKK_TRIGGER': '1'}), patch('enikk.Path.home', return_value=Path(temp)), patch('enikk.subprocess.run', return_value=version), patch('enikk.subprocess.Popen', side_effect=launch):
                with self.assertRaisesRegex(RuntimeError, 'native failure'):
                    with enikk.submission_proxy('unix:///upstream', 'same-thread', Path('/python')) as endpoint:
                        self.assertTrue(endpoint.startswith('unix:///tmp/enikk-arbiter-'))
                        raise RuntimeError('native failure')
            process.terminate.assert_called_once(); process.wait.assert_called_once()

    def test_initialization_failure_no_direct_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            process = Mock(); process.poll.return_value = 1
            version = subprocess.CompletedProcess([], 0, 'codex-cli 0.160.0\n', '')
            with patch.dict(os.environ, {'CODEX_ENIKK_TRIGGER': '1'}), patch('enikk.Path.home', return_value=Path(temp)), patch('enikk.subprocess.run', return_value=version), patch('enikk.subprocess.Popen', return_value=process):
                with self.assertRaisesRegex(RuntimeError, 'failed to initialize'):
                    with enikk.submission_proxy('unix:///upstream', 'same-thread', Path('/python')):
                        self.fail('must not yield direct endpoint')

    def test_unverified_version_rejected(self):
        version = subprocess.CompletedProcess([], 0, 'codex-cli 0.158.0\n', '')
        with patch.dict(os.environ, {'CODEX_ENIKK_TRIGGER': '1'}), patch('enikk.subprocess.run', return_value=version), patch('enikk.subprocess.Popen') as launch:
            with self.assertRaises(RuntimeError):
                with enikk.submission_proxy('unix:///upstream', 'same-thread', Path('/python')): pass
            launch.assert_not_called()
