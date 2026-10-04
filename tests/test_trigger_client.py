import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from trigger_client import main, EXIT
from trigger_service import inbox_bytes, bind_local


class ClientTests(unittest.TestCase):
    def test_all_status_exit_codes(self):
        for status, code in EXIT.items():
            output = io.StringIO()
            with patch('trigger_client.submit', return_value={'status': status}), contextlib.redirect_stdout(output):
                self.assertEqual(main([]), code)
            self.assertEqual(json.loads(output.getvalue())['status'], status)

    def test_path_cannot_override_trusted_inbox(self):
        with patch('trigger_client.submit') as request, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['/tmp/arbitrary']), EXIT['INVALID_PATH'])
            request.assert_not_called()

    def test_file_replaced_during_read_is_rejected(self):
        import os
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'command'; path.write_text('original\n\nEOF\n'); path.chmod(0o600)
            original_read = os.read
            changed = False
            def replace_during_read(fd, size):
                nonlocal changed
                if not changed:
                    changed = True
                    replacement = path.with_suffix('.new'); replacement.write_text('changed\n\nEOF\n')
                    replacement.replace(path)
                return original_read(fd, size)
            with patch('trigger_service.os.read', side_effect=replace_during_read), self.assertRaises(ValueError):
                inbox_bytes(path)

    def test_stale_path_regular_file_not_removed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'socket'; path.write_text('keep')
            with self.assertRaises(ValueError): bind_local(path)
            self.assertEqual(path.read_text(), 'keep')
