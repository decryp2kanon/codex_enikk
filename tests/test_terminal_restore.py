import os
import pty
import sys
import termios
import tty
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import enikk

class TerminalRestoreTests(unittest.TestCase):
    def check_restore(self, error=False):
        master, slave = pty.openpty()
        try:
            original = termios.tcgetattr(slave)
            with os.fdopen(os.dup(slave), 'r') as stream, patch.object(sys, 'stdin', stream):
                try:
                    with enikk.terminal_restore() as restore:
                        tty.setraw(slave)
                        self.assertNotEqual(termios.tcgetattr(slave), original)
                        if error:
                            raise KeyboardInterrupt()
                        restore()
                        self.assertEqual(termios.tcgetattr(slave), original)
                except KeyboardInterrupt:
                    pass
            self.assertEqual(termios.tcgetattr(slave), original)
            data = os.read(master, 4096)
            self.assertIn(b'\x1b[?1006l', data)
            self.assertIn(b'\x1b[?2004l', data)
            self.assertIn(b'\x1b[?25h\r\x1b[J', data)
            self.assertLess(data.index(b'\x1b[?1049l'), data.index(b'\r\x1b[J'))
            self.assertEqual(data.count(b'\x1b[?1006l'), 1)
        finally:
            os.close(master)
            os.close(slave)

    def test_normal_exit_restores_before_cleanup(self):
        self.check_restore()

    def test_keyboard_interrupt_restores_terminal(self):
        self.check_restore(error=True)

    def test_non_terminal_does_not_emit_escapes(self):
        import io
        with patch.object(sys, 'stdin', io.StringIO('')), patch.object(os, 'write') as write:
            with enikk.terminal_restore() as restore:
                restore()
            write.assert_not_called()
