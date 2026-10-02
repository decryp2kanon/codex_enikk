import json
import os
from pathlib import Path
import sqlite3
import tempfile
import time
import unittest

from latest import LIMIT, Mirror, atomic_write, recent_bytes


class LatestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.db = self.root / 'history.sqlite'
        self.out = self.root / 'latest.txt'
        self.c = sqlite3.connect(self.db)
        self.addCleanup(self.c.close)
        self.c.execute('CREATE TABLE thread_items(thread_id, rollout_ordinal, item_type, item_json)')
        self.c.execute('CREATE INDEX paging ON thread_items(thread_id,rollout_ordinal)')
        self.index = 0

    def add(self, kind, text, thread='A', phase=None):
        item = dict(type=kind, text=text, phase=phase)
        if kind == 'userMessage':
            item['content'] = [dict(type='text', text=text), dict(type='image', url='SECRET')]
        self.index += 1
        self.c.execute('INSERT INTO thread_items VALUES(?,?,?,?)',
                       (thread, self.index, kind, json.dumps(item)))
        self.c.commit()

    def test_visible_order_and_internal_exclusion(self):
        self.add('userMessage', '안녕?')
        self.add('agentMessage', '안녕! 에닉이야.', phase='commentary')
        self.add('agentMessage', '조금 더 확인할게.', phase='commentary')
        for kind in ('reasoning', 'commandExecution', 'fileChange', 'contextCompaction'):
            self.add(kind, 'SECRET')
        self.add('agentMessage', 'SECRET', phase='analysis')
        self.add('agentMessage', '완료했어.', phase='final_answer')
        self.assertEqual(recent_bytes(self.c, 'A').decode(),
                         '[USER]\n안녕?\n\n[ENIKK]\n안녕! 에닉이야.\n\n'
                         '[ENIKK]\n조금 더 확인할게.\n\n[ENIKK]\n완료했어.\n\n')

    def test_rolling_whole_blocks(self):
        for i in range(80):
            self.add('agentMessage', f'{i:03d} ' + '한글 테스트 ' * 400)
        data = recent_bytes(self.c, 'A')
        self.assertLessEqual(len(data), LIMIT)
        self.assertNotIn('000 ', data.decode())
        self.assertIn('079 ', data.decode())
        self.assertTrue(data.startswith(b'[ENIKK]\n'))
        self.assertTrue(data.endswith(b'\n\n'))
        self.assertNotIn('\ufffd', data.decode('utf-8'))
        # Every retained block is complete, not just valid UTF-8.
        for body in data.decode().split('[ENIKK]\n')[1:]:
            self.assertEqual(len(body.split('한글 테스트 ')) - 1, 400)

    def test_single_huge_korean_message(self):
        self.add('userMessage', '가나다라마' * 100000 + '마지막')
        data = recent_bytes(self.c, 'A')
        self.assertLessEqual(len(data), LIMIT)
        self.assertIn('older content truncated', data.decode())
        self.assertTrue(data.decode().endswith('마지막\n\n'))
        self.assertNotIn('\ufffd', data.decode())

    def test_huge_older_block_does_not_displace_latest(self):
        self.add('userMessage', '가' * LIMIT)
        self.add('agentMessage', '최신')
        self.assertEqual(recent_bytes(self.c, 'A'), '[ENIKK]\n최신\n\n'.encode())

    def test_thread_selection_and_resume(self):
        self.add('userMessage', '대화 A')
        self.add('agentMessage', '대화 B', thread='B')
        selection = self.root / 'selection.json'
        def wait_for(text):
            end = time.monotonic() + 3
            while time.monotonic() < end:
                if self.out.exists() and text in self.out.read_text():
                    return
                time.sleep(.02)
            self.fail('mirror did not refresh')
        with Mirror(self.db, 'A', self.out, selection):
            wait_for('대화 A')
            atomic_write(selection, b'{"thread":"B"}')
            wait_for('대화 B')
            self.assertNotIn('대화 A', self.out.read_text())
            self.add('agentMessage', '새 답변', thread='B')
            wait_for('새 답변')
        selection.unlink()
        with Mirror(self.db, 'A', self.out):
            wait_for('대화 A')
            self.assertNotIn('대화 B', self.out.read_text())
        self.assertEqual(self.out.stat().st_uid, os.getuid())
        self.assertEqual(self.out.stat().st_mode & 0o777, 0o600)
        self.assertFalse(list(self.root.glob('.codex-latest-*')))

    def test_atomic_no_unneeded_rewrite_and_symlink_refused(self):
        atomic_write(self.out, b'text')
        first = self.out.stat().st_mtime_ns
        atomic_write(self.out, b'text')
        self.assertEqual(first, self.out.stat().st_mtime_ns)
        link = self.root / 'link'
        link.symlink_to(self.out)
        with self.assertRaises(OSError):
            atomic_write(link, b'bad')
        self.assertEqual(self.out.read_bytes(), b'text')

    def test_read_only_connection(self):
        self.add('userMessage', '안녕')
        c = sqlite3.connect(self.db.as_uri() + '?mode=ro', uri=True)
        try:
            self.assertIn('안녕', recent_bytes(c, 'A').decode())
            with self.assertRaises(sqlite3.OperationalError):
                c.execute('DELETE FROM thread_items')
        finally:
            c.close()
