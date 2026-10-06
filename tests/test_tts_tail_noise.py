"""CPU waveform and fail-open coverage for experimental tail attenuation."""
import ast
from pathlib import Path
import time
import types
import unittest
from unittest.mock import Mock
import torch


def helpers():
    path = Path(__file__).resolve().parents[1] / 'tts/yuki-chatterbox-engine.py'
    tree = ast.parse(path.read_text())
    tree.body = [n for n in tree.body if getattr(n, 'name', None) in
                 {'soften_detached_tail', 'optional_tail_softening'}]
    scope = {'torch': torch, 'time': time}
    exec(compile(tree, str(path), 'exec'), scope)
    return scope


class TailNoiseTests(unittest.TestCase):
    def setUp(self):
        self.scope = helpers()
        self.sr = 24000

    def wave(self, gap=.4, noise_duration=.15, noise_level=.02):
        # Same waveform prefix in every fixture; suffix represents isolated noise.
        wave = torch.zeros((1, 48000))
        wave[:, :24000] = .1
        start = int(self.sr * (1 + gap))
        wave[:, start:start + int(self.sr * noise_duration)] = noise_level
        return wave

    def test_detached_tail_reduced_without_retiming_or_prefix_change(self):
        wave = self.wave()
        result, record = self.scope['soften_detached_tail'](wave, self.sr, .9)
        self.assertEqual(record['attenuation_db'], 60)
        self.assertEqual(result.shape, wave.shape)
        self.assertTrue(torch.equal(result[:, :int(self.sr * .95)], wave[:, :int(self.sr * .95)]))
        self.assertTrue(torch.equal(wave[:, :24000], torch.full((1,24000), .1)))
        self.assertAlmostEqual(result[0, int(self.sr * 1.4)].item(), .00002, places=7)

    def test_noop_without_final_text_hint(self):
        wave = self.wave()
        for hint in (None, -1., 4.):
            result, _ = self.scope['soften_detached_tail'](wave, self.sr, hint)
            self.assertIs(result, wave)

    def test_normal_final_word_before_completion_hint_preserved(self):
        wave = self.wave(noise_level=.08)
        result, _ = self.scope['soften_detached_tail'](wave, self.sr, 1.5)
        self.assertIs(result, wave)

    def test_ambiguous_strong_or_extended_resumption_preserved(self):
        for wave in (self.wave(gap=.02), self.wave(noise_level=.1),
                     torch.zeros((1,48000))):
            result, _ = self.scope['soften_detached_tail'](wave, self.sr, .9)
            self.assertIs(result, wave)

    def test_stronger_setting_accepts_short_gap_and_longer_weak_tail(self):
        for wave in (self.wave(gap=.1), self.wave(noise_duration=.6)):
            result, record = self.scope['soften_detached_tail'](wave, self.sr, .9)
            self.assertIsNot(result, wave)
            self.assertEqual(record['attenuation_db'], 60)

    def test_normal_generation_does_not_run_detector(self):
        detector = Mock(side_effect=AssertionError('not called'))
        self.scope['soften_detached_tail'] = detector
        wave = self.wave()
        result = self.scope['optional_tail_softening'](wave, self.sr, None,
                   types.SimpleNamespace(signals=set()), 0., Mock())
        self.assertIs(result, wave)
        detector.assert_not_called()

    def test_gap_overlapping_completion_hint_uses_listening_advance(self):
        wave = self.wave()
        result, record = self.scope['soften_detached_tail'](wave, self.sr, 1.2)
        self.assertIsNot(result, wave)
        self.assertAlmostEqual(record['start_seconds'], 1.15)
        self.assertTrue(torch.equal(result[:, :27600], wave[:, :27600]))
        self.assertAlmostEqual(result[0, 33600].item(), .00002, places=7)

    def test_detector_error_keeps_original_and_never_raises(self):
        self.scope['soften_detached_tail'] = Mock(side_effect=RuntimeError('diagnostic failure'))
        wave = self.wave()
        result = self.scope['optional_tail_softening'](wave, self.sr, None,
                   types.SimpleNamespace(signals={'long_tail'}), 0., Mock())
        self.assertIs(result, wave)


if __name__ == '__main__':
    unittest.main()
