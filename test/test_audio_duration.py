import os
import tempfile
import pytest
from pydub.generators import Sine
from utils.audio_utils import manage_audio_duration


def make_temp_audio(duration_ms=500):
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    audio = Sine(440).to_audio_segment(duration=duration_ms)
    audio.export(path, format="wav")
    return path


def test_trim_audio():
    path = make_temp_audio(1000)
    from pydub import AudioSegment

    audio = AudioSegment.from_file(path)
    trimmed = manage_audio_duration(audio, 500)
    assert abs(len(trimmed) - 500) < 5
    os.remove(path)


def test_extend_audio():
    path = make_temp_audio(300)
    from pydub import AudioSegment

    audio = AudioSegment.from_file(path)
    extended = manage_audio_duration(audio, 1000)
    assert abs(len(extended) - 1000) < 5
    os.remove(path)


def test_exact_duration():
    path = make_temp_audio(700)
    from pydub import AudioSegment

    audio = AudioSegment.from_file(path)
    same = manage_audio_duration(audio, 700)
    assert abs(len(same) - 700) < 5
    os.remove(path)
