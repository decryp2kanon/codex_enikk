import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import enikk

class BackupMirrorTests(unittest.TestCase):
    def test_verified_mirror_and_existing_file_preserved(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / 'backup.tar.gz'
            source.write_bytes(b'preserved conversation' * 100)
            target = root / 'secondary'
            settings = {'secondary': str(target), 'secondary_mount': str(root)}
            with patch.object(enikk, 'backup_settings', return_value=settings), patch.object(Path, 'is_mount', return_value=True):
                enikk.mirror_backup(source)
                self.assertEqual((target / source.name).read_bytes(), source.read_bytes())
                source.write_bytes(b'changed')
                with self.assertRaises(FileExistsError):
                    enikk.mirror_backup(source)
                self.assertEqual((target / source.name).read_bytes(), b'preserved conversation' * 100)
                self.assertEqual(list(target.glob('.incomplete-*')), [])

    def test_unmounted_disk_is_rejected_without_writing(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            target = root / 'secondary'
            with patch.object(enikk, 'backup_settings', return_value={'secondary': str(target), 'secondary_mount': str(root)}), patch.object(Path, 'is_mount', return_value=False):
                with self.assertRaises(OSError):
                    enikk.mirror_backup(root / 'backup.tar.gz')
            self.assertFalse(target.exists())
