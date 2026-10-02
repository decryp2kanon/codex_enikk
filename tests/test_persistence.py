import hashlib
import io
import json
import os
from pathlib import Path
import sqlite3
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import enikk
from persistence import DATABASES


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='enikk-restore-audit-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.home = self.root / 'source'
        self.home.mkdir()
        self.environment = patch.dict(os.environ, {'CODEX_HOME':str(self.home),
            'CODEX_ENIKK_DATA_DIR':str(self.root/'data')})
        self.environment.start();self.addCleanup(self.environment.stop)
        self.rollout = self.home / 'sessions/rollout.jsonl'
        self.rollout.parent.mkdir()
        self.rollout.write_text('{"fixture":"한국어"}\n')
        self.state = sqlite3.connect(self.home / DATABASES[0])
        self.history = sqlite3.connect(self.home / DATABASES[1])
        self.addCleanup(self.state.close);self.addCleanup(self.history.close)
        for c in [self.state,self.history]:
            c.execute('PRAGMA journal_mode=WAL')
            c.execute('PRAGMA wal_autocheckpoint=0')
        self.state.execute('CREATE TABLE threads(id PRIMARY KEY, rollout_path, name)')
        self.state.execute('INSERT INTO threads VALUES(?,?,?)',('thread',str(self.rollout),'사용자 이름'))
        self.state.execute('CREATE TABLE thread_attachments(id PRIMARY KEY, thread_id, payload)')
        self.state.execute('INSERT INTO thread_attachments VALUES(?,?,?)',('attachment','thread','metadata'))
        self.state.commit()
        self.history.execute('CREATE TABLE thread_history_projection_state(thread_id PRIMARY KEY,next_rollout_byte_offset)')
        self.history.execute('INSERT INTO thread_history_projection_state VALUES(?,?)',('thread',self.rollout.stat().st_size))
        self.history.execute('CREATE TABLE thread_items(thread_id,item_id PRIMARY KEY,item_type,item_json)')
        for i,kind in enumerate(['userMessage','agentMessage','agentMessage']):
            self.history.execute('INSERT INTO thread_items VALUES(?,?,?,?)',('thread',str(i),kind,json.dumps({'text': '한국어 '+str(i)})))
        self.history.commit()

    def backup(self):
        with patch('enikk.subprocess.run') as version:
            version.return_value.returncode=0
            version.return_value.stdout='codex-cli 0.158.0\n'
            return enikk.backup()

    def target(self,name='restored'):
        p=self.root/name;os.environ['CODEX_HOME']=str(p);return p

    def test_wal_snapshot_empty_restore_relocation_and_counts(self):
        self.assertGreater((self.home/(DATABASES[1]+'-wal')).stat().st_size,0)
        # An uncommitted item must not leak into the backup.
        self.history.execute('INSERT INTO thread_items VALUES(?,?,?,?)',('thread','uncommitted','userMessage','{}'))
        archive=self.backup()
        with tarfile.open(archive) as t:
            manifest=json.load(t.extractfile('manifest.json'))
            self.assertEqual(manifest['format_version'],2)
            self.assertEqual(manifest['codex_cli_version'],'codex-cli 0.158.0')
            for name in DATABASES:self.assertIn('codex/'+name,t.getnames())
            self.assertFalse(any(n.endswith(('-wal','-shm')) for n in t.getnames()))
        target=self.target();self.assertEqual(enikk.restore(archive),3)
        with sqlite3.connect(target/DATABASES[0]) as c:
            row=c.execute('SELECT * FROM threads').fetchone()
            self.assertEqual(row,('thread',str(target/'sessions/rollout.jsonl'),'사용자 이름'))
            self.assertTrue(Path(row[1]).is_file())
            self.assertEqual(c.execute('SELECT count(*) FROM thread_attachments').fetchone()[0],1)
        with sqlite3.connect(target/DATABASES[1]) as c:
            self.assertEqual(c.execute('SELECT count(*) FROM thread_items').fetchone()[0],3)
            self.assertEqual(c.execute('PRAGMA quick_check').fetchone()[0],'ok')
        self.assertEqual(self.state.execute('SELECT rollout_path FROM threads').fetchone()[0],str(self.rollout))

    def test_existing_home_refused_without_any_change(self):
        a=self.backup();target=self.target();target.mkdir()
        sentinel=target/DATABASES[0];sentinel.write_bytes(b'existing database')
        with self.assertRaisesRegex(ValueError,'기존 SQLite'):enikk.restore(a)
        self.assertEqual(sentinel.read_bytes(),b'existing database')
        self.assertEqual(list(target.iterdir()),[sentinel])

    def test_orphan_wal_refused(self):
        a=self.backup();target=self.target();target.mkdir()
        (target/(DATABASES[0]+'-wal')).write_bytes(b'existing WAL')
        with self.assertRaisesRegex(ValueError,'기존 SQLite'):enikk.restore(a)
        self.assertFalse((target/'sessions').exists())

    def test_conflicting_existing_rollout_refused(self):
        a=self.backup();target=self.target();p=target/'sessions/rollout.jsonl';p.parent.mkdir(parents=True);p.write_text('other data')
        with self.assertRaisesRegex(ValueError,'기존 대화'):enikk.restore(a)
        self.assertEqual(p.read_text(),'other data');self.assertFalse((target/DATABASES[0]).exists())

    def test_legacy_restore_and_missing_only(self):
        a=self.root/'legacy.tar.gz'
        with tarfile.open(a,'w:gz') as t:
            i=tarfile.TarInfo('codex/sessions/legacy.jsonl');data=b'{}\n';i.size=len(data);t.addfile(i,io.BytesIO(data))
        target=self.target();self.assertEqual(enikk.restore(a),1)
        p=target/'sessions/legacy.jsonl';p.write_text('keep')
        self.assertEqual(enikk.restore(a),0);self.assertEqual(p.read_text(),'keep')

    def test_truncated_archive_no_partial_restore(self):
        a=self.backup();bad=self.root/'truncated.tar.gz';data=a.read_bytes();bad.write_bytes(data[:len(data)//2]);target=self.target()
        with self.assertRaises((tarfile.TarError,EOFError,OSError)):enikk.restore(bad)
        self.assertEqual(list(target.iterdir()),[])

    def test_corrupt_snapshot_rejected_even_with_matching_hash(self):
        a=self.backup();bad=self.root/'corrupt-db.tar.gz'
        with tarfile.open(a) as t:files={m.name:t.extractfile(m).read() for m in t.getmembers()}
        files['codex/'+DATABASES[1]]=b'not a database'
        manifest=json.loads(files['manifest.json']);manifest['sha256']['codex/'+DATABASES[1]]=hashlib.sha256(files['codex/'+DATABASES[1]]).hexdigest();files['manifest.json']=json.dumps(manifest).encode()
        with tarfile.open(bad,'w:gz') as t:
            for name,data in files.items():
                i=tarfile.TarInfo(name);i.size=len(data);t.addfile(i,io.BytesIO(data))
        target=self.target()
        with self.assertRaises((sqlite3.Error,ValueError)):enikk.restore(bad)
        self.assertEqual(list(target.iterdir()),[])

    def test_checksum_mismatch_rejected_before_publish(self):
        a=self.backup();bad=self.root/'wrong-hash.tar.gz'
        with tarfile.open(a) as t:files={m.name:t.extractfile(m).read() for m in t.getmembers()}
        files['codex/sessions/rollout.jsonl']=b'changed\n'
        with tarfile.open(bad,'w:gz') as t:
            for name,data in files.items():
                i=tarfile.TarInfo(name);i.size=len(data);t.addfile(i,io.BytesIO(data))
        target=self.target()
        with self.assertRaisesRegex(ValueError,'손상된'):enikk.restore(bad)
        self.assertEqual(list(target.iterdir()),[])

    def test_snapshot_ahead_of_rollout_fails_backup(self):
        self.history.execute('UPDATE thread_history_projection_state SET next_rollout_byte_offset=999999');self.history.commit()
        with self.assertRaisesRegex(ValueError,'mismatch'):self.backup()
        self.assertEqual(list((self.root/'data/backups').iterdir()),[])

    def test_existing_archive_never_overwritten(self):
        with patch('enikk.datetime') as clock:
            clock.now.return_value.strftime.return_value='same-time'
            a=self.backup();before=a.read_bytes()
            with self.assertRaises(FileExistsError):self.backup()
            self.assertEqual(a.read_bytes(),before)
