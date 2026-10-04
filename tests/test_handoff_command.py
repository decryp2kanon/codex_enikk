import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from handoff_command import format_command, main, save_command, validate


class HandoffCommandTests(unittest.TestCase):
    def test_every_kind_and_length(self):
        for kind in ('task', 'additional', 'revision', 'continuation', 'recovery', 'handoff', 'status'):
            for text in (kind, kind + '\n한국어 지시\n' * 1000):
                with self.subTest(kind=kind, length=len(text)):
                    result = format_command(text)
                    validate(result)
                    self.assertEqual(result, text.rstrip('\r\n') + '\n\nEOF\n')

    def test_idempotent_existing_eof(self):
        for text in ('work\n\nEOF\n', 'work\nEOF', 'work\r\n\r\nEOF\r\n'):
            result = format_command(text)
            self.assertEqual(result, 'work\n\nEOF\n')
            self.assertEqual(format_command(result), result)

    def test_body_not_rewritten(self):
        body = 'Keep  spaces  \r\nEOF\r\nMore instructions  '
        self.assertEqual(format_command(body), body + '\n\nEOF\n')

    def test_invalid_or_empty(self):
        for text in ('', 'EOF', 'work\nEOF\n', 'work\n\nEOF \n', 'work\n\nEOF\nMore', 'work\n\nEOF\n\n'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                validate(text)
        for text in ('', '\n', 'EOF', '  '):
            with self.subTest(text=text), self.assertRaises(ValueError):
                format_command(text)

    def test_publish_and_do_not_overwrite_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'command.md'
            save_command(path, 'First')
            with self.assertRaises(FileExistsError):
                save_command(path, 'Second')
            self.assertEqual(path.read_text(), 'First\n\nEOF\n')
            self.assertEqual(list(Path(temp).glob('.command-*')), [])

    def test_explicit_inbox_replace_not_other_files(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'command.md'
            report = Path(temp) / 'enikk-result.md'
            report.write_text('result without EOF')
            save_command(path, 'Old')
            save_command(path, 'New', replace=True)
            self.assertEqual(path.read_text(), 'New\n\nEOF\n')
            self.assertEqual(report.read_text(), 'result without EOF')

    def test_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'original'; target.write_text('unchanged')
            path = Path(temp) / 'link'; path.symlink_to(target)
            for replace in (False, True):
                with self.assertRaises(ValueError):
                    save_command(path, 'new', replace=replace)
            self.assertEqual(target.read_text(), 'unchanged')

    def test_failed_write_preserves_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'command.md'; path.write_text('old')
            with patch('handoff_command.os.replace', side_effect=OSError('failure')):
                with self.assertRaises(OSError):
                    save_command(path, 'new', replace=True)
            self.assertEqual(path.read_text(), 'old')
            self.assertEqual(list(Path(temp).glob('.command-*')), [])

    def test_cli_write_then_readonly_check(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'command.md'
            with patch('sys.stdin', io.StringIO('한 줄 명령')):
                self.assertEqual(main([str(path)]), 0)
            before = path.read_bytes()
            self.assertEqual(main([str(path), '--check']), 0)
            self.assertEqual(path.read_bytes(), before)
            path.write_text('invalid')
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(main([str(path), '--check']), 1)
            self.assertEqual(path.read_text(), 'invalid')
