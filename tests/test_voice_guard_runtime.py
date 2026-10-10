import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core_runtime


class VoiceGuardRuntimeTests(unittest.TestCase):
    def test_verified_guard_binary_is_used_and_voice_switch_is_set(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'bin/codex-voice-guard'
            binary.parent.mkdir()
            binary.write_bytes(b'fixture')
            (root / 'voice-guard.json').write_text(json.dumps({
                'sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
            }))
            process = Mock()
            process.poll.return_value = None

            def start(command, **kwargs):
                Path(command[command.index('--listen') + 1].removeprefix('unix://')).touch()
                self.assertEqual(command[0], str(binary))
                self.assertEqual(kwargs['env']['CODEX_ENIKK_DISABLE_REALTIME'], '1')
                return process

            with patch.object(core_runtime, '__file__', str(root / 'core_runtime.py')):
                with patch.object(core_runtime.subprocess, 'Popen', side_effect=start):
                    with core_runtime.app_server() as endpoint:
                        self.assertTrue(endpoint.startswith('unix://'))
            process.terminate.assert_called_once()

    def test_changed_guard_never_falls_back_to_unprotected_server(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'bin/codex-voice-guard'
            binary.parent.mkdir()
            binary.write_bytes(b'changed')
            (root / 'voice-guard.json').write_text(json.dumps({'sha256': 'wrong'}))
            with patch.object(core_runtime, '__file__', str(root / 'core_runtime.py')):
                with patch.object(core_runtime.subprocess, 'Popen') as start:
                    with self.assertRaisesRegex(RuntimeError, 'Voice guard binary changed'):
                        with core_runtime.app_server():
                            self.fail('unprotected server started')
                    start.assert_not_called()


if __name__ == '__main__':
    unittest.main()
