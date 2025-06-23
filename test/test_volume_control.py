import os
import tempfile
import pytest
from pydub.generators import Sine
from utils.audio_utils import adjust_volume


def make_temp_audio(format="wav", duration_ms=500):
    fd, path = tempfile.mkstemp(suffix=f".{format}")
    os.close(fd)
    audio = Sine(440).to_audio_segment(duration=duration_ms)
    audio.export(path, format=format)
    return path


def test_increase_volume():
    path = make_temp_audio()
    from pydub import AudioSegment

    audio = AudioSegment.from_file(path)
    louder = adjust_volume(audio, 6)  # tăng 6dB
    assert louder.dBFS > audio.dBFS
    os.remove(path)


def test_decrease_volume():
    path = make_temp_audio()
    from pydub import AudioSegment

    audio = AudioSegment.from_file(path)
    quieter = adjust_volume(audio, -6)  # giảm 6dB
    assert quieter.dBFS < audio.dBFS
    os.remove(path)


def test_zero_gain():
    path = make_temp_audio()
    from pydub import AudioSegment

    audio = AudioSegment.from_file(path)
    same = adjust_volume(audio, 0)
    assert abs(same.dBFS - audio.dBFS) < 0.01
    os.remove(path)
