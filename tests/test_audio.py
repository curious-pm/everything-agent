import numpy as np

from everything_agent.audio.barge_in import BargeInDetector
from everything_agent.audio.dsp import Resampler, float_to_pcm16, to_mono


def test_resampling_is_continuous_across_chunks():
    whole = np.sin(np.linspace(0, 40 * np.pi, 24000)).astype(np.float32)
    one = Resampler(24000, 16000).process(whole)
    pieces = Resampler(24000, 16000)
    chunked = np.concatenate([pieces.process(c) for c in np.array_split(whole, 37)])
    assert abs(len(one) - 16000) <= 1
    assert np.allclose(one[: len(chunked)], chunked[: len(one)], atol=1e-5)


def test_pcm16_clips_and_packs_little_endian():
    pcm = float_to_pcm16(np.array([0.0, 1.0, -1.0, 2.0], dtype=np.float32))
    assert np.frombuffer(pcm, "<i2").tolist() == [0, 32767, -32767, 32767]


def test_to_mono_takes_the_first_channel_of_either_layout():
    stereo = np.array([[1, 2], [3, 4], [5, 6]], dtype=np.float32)
    assert to_mono(stereo).tolist() == [1, 3, 5]
    assert to_mono(stereo.T).tolist() == [1, 3, 5]


def test_barge_in_ducks_then_stops_on_a_sustained_voice():
    detector = BargeInDetector(threshold=0.1)
    stages = [detector.observe(0.3, t / 100) for t in range(0, 60, 2)]
    assert stages[0] == "none"
    assert "duck" in stages
    assert stages.count("stop") == 1


def test_barge_in_ignores_a_short_echo():
    detector = BargeInDetector(threshold=0.1)
    stages = [detector.observe(0.3, t / 100) for t in range(0, 10, 2)]
    stages += [detector.observe(0.0, 0.1 + t / 100) for t in range(0, 60, 2)]
    assert "stop" not in stages
    assert stages[-1] == "none"
