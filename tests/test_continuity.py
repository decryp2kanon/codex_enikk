import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from continuity import Continuity


class ContinuityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / 'home'
        self.path = self.home / 'sessions' / 'original.jsonl'
        self.path.parent.mkdir(parents=True)
        self.pin = self.home / 'enikk-continuity.json'
        self.pin.write_text(json.dumps({'session_id': 'original'}))
        self.path.write_bytes(self.record('session_meta', {'id': 'original'}))
        self.guard = Continuity(self.home, Path(self.temp.name) / 'evidence')

    def record(self, kind, payload):
        return (json.dumps({'type': kind, 'payload': payload}, ensure_ascii=False) + '\n').encode()

    def append(self, value):
        with self.path.open('ab') as out:
            out.write(value)

    def checkpoint(self):
        return self.guard.inspect('original', self.path, save=True)

    def test_append_preserves_exact_original_and_search_provenance(self):
        self.checkpoint()
        self.append(self.record('response_item', {'type': 'message', 'role': 'user',
                    'content': [{'type': 'input_text', 'text': '너 별명은 유키짱'}]}))
        self.checkpoint()
        self.assertEqual(self.guard.journal.read_bytes(), self.path.read_bytes())
        result = list(self.guard.search('유키짱', True))
        self.assertEqual(result[0]['text'], '너 별명은 유키짱')
        self.assertEqual(result[0]['session_id'], 'original')
        self.assertGreater(result[0]['byte_offset'], 0)

    def test_missing_or_changed_pin_never_rebinds(self):
        self.checkpoint()
        self.pin.unlink()
        with self.assertRaisesRegex(ValueError, 'pin missing'):
            self.guard.require_binding()
        self.pin.write_text(json.dumps({'session_id': 'other'}))
        with self.assertRaisesRegex(ValueError, 'thread changed'):
            self.guard.require_binding()

    def test_truncated_or_rewritten_source_preserves_evidence(self):
        self.checkpoint()
        proof = self.guard.journal.read_bytes()
        self.path.write_bytes(b'')
        with self.assertRaisesRegex(ValueError, 'truncated'):
            self.checkpoint()
        self.assertEqual(self.guard.journal.read_bytes(), proof)
        self.path.write_bytes(proof.replace(b'original', b'modified'))
        with self.assertRaises(ValueError):
            self.checkpoint()
        self.assertEqual(self.guard.journal.read_bytes(), proof)

    def test_invalid_utf8_and_json_do_not_advance_checkpoint(self):
        self.checkpoint()
        proof = self.guard.state.read_bytes()
        original = self.path.read_bytes()
        for bad in (b'\xff\n', b'{broken}\n'):
            self.path.write_bytes(original + bad)
            with self.assertRaisesRegex(ValueError, 'Corrupt rollout'):
                self.checkpoint()
            self.assertEqual(self.guard.state.read_bytes(), proof)

    def test_partial_live_write_excluded_but_resume_rejected(self):
        self.checkpoint()
        self.append(b'{incomplete')
        with self.assertRaisesRegex(ValueError, 'Incomplete rollout'):
            self.checkpoint()
        result = self.guard.inspect('original', self.path, save=True, allow_partial=True)
        self.assertTrue(result['partial_tail'])
        self.assertNotIn(b'incomplete', self.guard.journal.read_bytes())

    def test_crash_after_journal_fsync_before_state_publish(self):
        self.checkpoint()
        self.append(self.record('compacted', {}))
        with patch('continuity.atomic_json', side_effect=OSError('power loss')):
            with self.assertRaises(OSError):
                self.checkpoint()
        # Old committed prefix remains valid; next checkpoint recovers appended tail.
        self.checkpoint()
        self.assertEqual(self.guard.journal.read_bytes(), self.path.read_bytes())
        self.assertEqual(self.guard.load()['compactions'], 1)

    def test_initial_publish_crash_fails_closed_without_deleting_journal(self):
        with patch('continuity.atomic_json', side_effect=OSError('power loss')):
            with self.assertRaises(OSError):
                self.checkpoint()
        evidence = self.guard.journal.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Orphan'):
            self.checkpoint()
        self.assertEqual(self.guard.journal.read_bytes(), evidence)

    def test_read_only_inspection_creates_no_evidence(self):
        result = self.guard.inspect('original', self.path)
        self.assertFalse(result['checkpoint_present'])
        self.assertFalse(self.guard.root.exists())

    def test_evidence_damage_prevents_source_replacing_it(self):
        self.checkpoint()
        self.guard.journal.write_bytes(b'damage')
        with self.assertRaisesRegex(ValueError, 'journal truncated'):
            self.checkpoint()
        self.assertEqual(self.guard.journal.read_bytes(), b'damage')

    def test_direct_user_search_excludes_relay_and_assistant(self):
        for role, text in [('user', '[USER · 도로시 경유] 유키짱'),
                           ('assistant', '유키짱'), ('user', '내가 정한 유키짱')]:
            self.append(self.record('response_item', {'type': 'message', 'role': role,
                        'content': [{'type': 'input_text', 'text': text}]}))
        self.checkpoint()
        self.assertEqual([r['text'] for r in self.guard.search('유키짱', True)], ['내가 정한 유키짱'])

    def test_wrong_database_reference_and_projection_rejected(self):
        import sqlite3
        state = sqlite3.connect(self.home / 'state_5.sqlite')
        state.execute('CREATE TABLE threads (id TEXT, rollout_path TEXT)')
        state.execute('INSERT INTO threads VALUES (?, ?)', ('original', '/wrong'))
        state.commit()
        with self.assertRaisesRegex(ValueError, 'rollout mismatch'):
            self.checkpoint()
        state.execute('UPDATE threads SET rollout_path=?', (str(self.path),))
        state.commit()
        state.close()
        history = sqlite3.connect(self.home / 'thread_history_1.sqlite')
        history.execute('CREATE TABLE thread_history_projection_state (thread_id TEXT, next_rollout_byte_offset INTEGER)')
        history.execute('INSERT INTO thread_history_projection_state VALUES (?, ?)', ('original', 999999))
        history.commit()
        history.close()
        with self.assertRaisesRegex(ValueError, 'projection exceeds'):
            self.checkpoint()
