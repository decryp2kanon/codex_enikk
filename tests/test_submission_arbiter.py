import threading
import unittest

from submission_arbiter import Arbiter, Busy, UnknownEffect


class ArbiterTests(unittest.TestCase):
    def setUp(self):
        self.a = Arbiter('same-thread')
        self.a.initialize({'id': 'same-thread', 'status': {'type': 'idle'}})

    def test_each_source_starts_and_completes(self):
        for owner in ('DOROTHY', 'USER'):
            token = self.a.reserve(owner, 'same-thread')
            self.a.accepted(token, 'turn-' + owner)
            self.assertTrue(self.a.completed('same-thread', 'turn-' + owner))
            self.assertEqual(self.a.state, 'IDLE')

    def test_dorothy_reservation_blocks_native_before_response(self):
        self.a.reserve('DOROTHY', 'same-thread')
        with self.assertRaises(Busy): self.a.reserve('USER', 'same-thread')

    def test_native_reservation_blocks_dorothy_before_response(self):
        self.a.reserve('USER', 'same-thread')
        with self.assertRaises(Busy): self.a.reserve('DOROTHY', 'same-thread')

    def test_active_turn_cannot_be_steered_by_new_submission(self):
        for first, second in (('USER', 'DOROTHY'), ('DOROTHY', 'USER')):
            token = self.a.reserve(first, 'same-thread')
            self.a.accepted(token, 'active')
            with self.assertRaises(Busy): self.a.reserve(second, 'same-thread')
            self.a.completed('same-thread', 'active')

    def test_concurrent_requests_exactly_one_reservation(self):
        barrier = threading.Barrier(3)
        results = []
        def submit(owner):
            barrier.wait()
            try: results.append(('accepted', self.a.reserve(owner, 'same-thread')))
            except Busy: results.append(('busy', None))
        workers = [threading.Thread(target=submit, args=(owner,)) for owner in ('USER', 'DOROTHY')]
        for worker in workers: worker.start()
        barrier.wait()
        for worker in workers: worker.join()
        self.assertEqual(sorted(x[0] for x in results), ['accepted', 'busy'])

    def test_wrong_completion_cannot_release(self):
        token = self.a.reserve('DOROTHY', 'same-thread'); self.a.accepted(token, 'active')
        self.assertFalse(self.a.completed('other-thread', 'active'))
        self.assertFalse(self.a.completed('same-thread', 'old-turn'))
        self.assertEqual(self.a.state, 'DOROTHY_ACTIVE')

    def test_dropped_response_is_unknown(self):
        self.a.reserve('DOROTHY', 'same-thread'); self.a.lost()
        with self.assertRaises(UnknownEffect): self.a.reserve('USER', 'same-thread')
        with self.assertRaises(UnknownEffect):
            self.a.initialize({'id': 'same-thread', 'status': {'type': 'idle'}})

    def test_restart_defaults_unknown_not_idle(self):
        with self.assertRaises(UnknownEffect): Arbiter('same-thread').reserve('DOROTHY', 'same-thread')

    def test_fake_owner_or_wrong_thread_rejected(self):
        for owner, thread in (('[USER]', 'same-thread'), ('DOROTHY', 'new-thread')):
            with self.assertRaises(UnknownEffect): self.a.reserve(owner, thread)

    def test_only_authoritative_idle_initializes(self):
        for thread in ({'id': 'other', 'status': {'type': 'idle'}},
                       {'id': 'same-thread', 'status': {'type': 'active'}}):
            with self.assertRaises((Busy, UnknownEffect)): Arbiter('same-thread').initialize(thread)

    def test_known_pre_effect_rejection_releases(self):
        token = self.a.reserve('DOROTHY', 'same-thread')
        self.a.rejected_before_effect(token)
        self.assertEqual(self.a.state, 'IDLE')

    def test_mismatched_response_unknown(self):
        self.a.reserve('USER', 'same-thread')
        with self.assertRaises(UnknownEffect): self.a.accepted('wrong-token', 'turn')
        self.assertEqual(self.a.state, 'UNKNOWN')
