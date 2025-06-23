import os
import tempfile
import pytest
from pydub.generators import Sine
from utils.audio_utils import load_audio_file


def make_temp_audio(format="wav", duration_ms=500):
    fd, path = tempfile.mkstemp(suffix=f".{format}")
    os.close(fd)
    audio = Sine(440).to_audio_segment(duration=duration_ms)
    audio.export(path, format=format)
    return path


def test_load_wav():
    path = make_temp_audio("wav")
    audio = load_audio_file(path)
    assert audio.frame_rate > 0
    assert audio.channels > 0
    os.remove(path)


def test_load_mp3():
    path = make_temp_audio("mp3")
    audio = load_audio_file(path)
    assert audio.frame_rate > 0
    assert audio.channels > 0
    os.remove(path)


def test_unsupported_format():
    # Tạo file giả định không phải audio
    fd, path = tempfile.mkstemp(suffix=".txt")
    with os.fdopen(fd, "w") as f:
        f.write("not audio")
    with pytest.raises(ValueError):
        load_audio_file(path)
    os.remove(path)
