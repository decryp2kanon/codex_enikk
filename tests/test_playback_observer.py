"""CPU-only observer tests; never start services or capture user microphones."""
import array
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('observer',
    Path(__file__).resolve().parents[1] / 'tts/benchmarks/playback_observer.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


class PlaybackObserverTests(unittest.TestCase):
    def test_tts_ownership_and_unrelated_stream(self):
        parents = {7: 5, 5: 3, 3: 1, 9: 1}
        self.assertTrue(observer.descendant(7, 3, parents.__getitem__))
        self.assertFalse(observer.descendant(9, 3, parents.__getitem__))

    def test_parent_exit_is_not_ownership(self):
        def gone(pid):
            raise FileNotFoundError()
        self.assertFalse(observer.descendant(7, 3, gone))

    def test_stereo_signal_does_not_cancel_opposite_channels(self):
        data = array.array('f', [0, 0, 0, 0, .1, -.1, .2, -.2]).tobytes()
        onset, peak = observer.signal_block(data, rate=100, end=10)
        self.assertAlmostEqual(onset, 9.98)
        self.assertAlmostEqual(peak, .2)

    def test_silence_distinct_from_no_received_blocks(self):
        self.assertEqual(observer.signal_block(array.array('f', [0]*20).tobytes(), end=10), (None, 0))
        self.assertEqual(observer.signal_block(b'', end=10), (None, 0))
        # The Recorder separately records bytes/blocks/readiness: empty capture
        # must never be reported as verified silence or a successful onset.

    def test_noise_threshold(self):
        data = array.array('f', [.00001, -.00001]*10).tobytes()
        self.assertIsNone(observer.signal_block(data, end=10)[0])
