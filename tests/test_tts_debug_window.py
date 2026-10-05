import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import enikk

class TTSDebugTests(unittest.TestCase):
    def test_current_run_and_read_only_tail(self):
        with tempfile.TemporaryDirectory(prefix='debug space ') as d:
            with patch.dict(os.environ, {'DISPLAY': ':0'}), patch.object(enikk.shutil, 'which', return_value='/usr/bin/gnome-terminal'), patch.object(enikk.subprocess, 'Popen') as spawn:
                enikk.open_tts_debug_window(d)
            argv = spawn.call_args.args[0]
            self.assertEqual(argv[-2:], [str(Path(d) / 'runtime.log'), str(Path(d) / 'notify.log')])
            self.assertIn('--window', argv)
            self.assertIn('--pid=' + str(os.getpid()), argv)
            self.assertEqual(argv[argv.index('--') + 1], 'tail')
            self.assertTrue((Path(d) / 'runtime.log').exists())

    def test_without_gui_keeps_wrapper_usable(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(enikk.subprocess, 'Popen') as spawn:
            enikk.open_tts_debug_window('/nonexistent')
            spawn.assert_not_called()
