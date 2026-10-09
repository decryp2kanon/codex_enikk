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

    def test_read_only_stdin_still_disables_mouse(self):
        master, slave = pty.openpty()
        try:
            with open(os.ttyname(slave), 'r') as stream, patch.object(sys, 'stdin', stream):
                with enikk.terminal_restore():
                    tty.setraw(slave)
            import select
            self.assertTrue(select.select([master], [], [], 1)[0])
            data = os.read(master, 4096)
            self.assertIn(b'\x1b[?1003l', data)
            self.assertIn(b'\x1b[?1016l', data)
        finally:
            os.close(master)
            os.close(slave)

    def test_queued_mouse_input_is_not_returned_to_shell(self):
        master, slave = pty.openpty()
        try:
            with os.fdopen(os.dup(slave), 'r') as stream, patch.object(sys, 'stdin', stream):
                with enikk.terminal_restore():
                    tty.setraw(slave)
                    os.write(master, b'\x1b[<35;46;54M\n')
                    import select
                    self.assertTrue(select.select([slave], [], [], 1)[0])
                self.assertFalse(select.select([slave], [], [], 0)[0])
        finally:
            os.close(master)
            os.close(slave)

    def test_failed_attribute_restore_does_not_skip_mouse_reset(self):
        master, slave = pty.openpty()
        try:
            with os.fdopen(os.dup(slave), 'r') as stream, patch.object(sys, 'stdin', stream):
                with patch.object(termios, 'tcsetattr', side_effect=OSError('test')):
                    with enikk.terminal_restore():
                        pass
                # Verify normal output separately from kernel attributes.
            self.assertIn(b'\x1b[?1003l', os.read(master, 4096))
        finally:
            os.close(master)
            os.close(slave)
