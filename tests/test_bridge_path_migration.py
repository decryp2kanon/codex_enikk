"""Migration preserves inbox contents/inode and refuses ambiguous destinations."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from trigger_service import migrate_command_inbox


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.patch = patch('pathlib.Path.home', return_value=self.home)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.legacy = self.home / 'dorothy-command.md'
        self.new = self.home / '.local/state/codex_enikk/bridge/dorothy-command.md'

    def command(self):
        self.legacy.write_text('User-approved test command.\nEOF\n')
        self.legacy.chmod(0o600)

    def test_migration_preserves_bytes_inode_and_repeated_startup(self):
        self.command()
        data, inode = self.legacy.read_bytes(), self.legacy.stat().st_ino
        self.assertEqual(migrate_command_inbox(), self.new)
        self.assertFalse(self.legacy.exists())
        self.assertEqual(self.new.read_bytes(), data)
        self.assertEqual(self.new.stat().st_ino, inode)
        self.assertEqual(migrate_command_inbox(), self.new)

    def test_conflict_does_not_overwrite_or_remove(self):
        self.command()
        self.new.parent.mkdir(parents=True, mode=0o700)
        self.new.write_text('Existing destination')
        with self.assertRaises(ValueError):
            migrate_command_inbox()
        self.assertTrue(self.legacy.exists())
        self.assertEqual(self.new.read_text(), 'Existing destination')

    def test_incomplete_command_is_preserved_without_blocking_startup(self):
        self.legacy.write_text('Missing EOF')
        self.legacy.chmod(0o600)
        self.assertEqual(migrate_command_inbox(), self.new)
        self.assertFalse(self.legacy.exists())
        self.assertEqual(self.new.read_text(), 'Missing EOF')
        from trigger_service import inbox_bytes
        with self.assertRaisesRegex(ValueError, 'INVALID_EOF'):
            inbox_bytes(self.new)

    def test_symlink_inbox_is_not_moved(self):
        actual = self.home / 'actual'
        actual.write_text('Command\nEOF\n')
        self.legacy.symlink_to(actual)
        with self.assertRaises(OSError):
            migrate_command_inbox()
        self.assertTrue(self.legacy.is_symlink())
        self.assertFalse(self.new.exists())
