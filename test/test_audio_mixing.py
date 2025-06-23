import os
import tempfile
import pytest
from pydub.generators import Sine
from utils.audio_utils import mix_audio


def make_temp_audio(freq=440, format="wav", duration_ms=1000, gain_db=0):
    fd, path = tempfile.mkstemp(suffix=f".{format}")
    os.close(fd)
    audio = Sine(freq).to_audio_segment(duration=duration_ms).apply_gain(gain_db)
    audio.export(path, format=format)
    return path


def test_mix_basic():
    voice_path = make_temp_audio(660, duration_ms=500, gain_db=0)
    music_path = make_temp_audio(220, duration_ms=1000, gain_db=-10)
    from pydub import AudioSegment

    voice = AudioSegment.from_file(voice_path)
    music = AudioSegment.from_file(music_path)
    mixed = mix_audio(voice, music, bgm_gain_when_voice=-8)
    # Mixed length phải bằng nhạc nền (vì overlay)
    assert abs(len(mixed) - len(music)) < 5
    # Mixed phải có biên độ lớn hơn nhạc nền gốc (do overlay thêm voice)
    assert mixed.dBFS > music.dBFS
    os.remove(voice_path)
    os.remove(music_path)


def test_mix_sample_rate_and_channels():
    # Tạo voice mono, music stereo, sample rate khác nhau
    voice_path = make_temp_audio(440, duration_ms=500)
    music_path = make_temp_audio(220, duration_ms=1000)
    from pydub import AudioSegment

    voice = AudioSegment.from_file(voice_path).set_channels(1).set_frame_rate(22050)
    music = AudioSegment.from_file(music_path).set_channels(2).set_frame_rate(44100)
    mixed = mix_audio(voice, music)
    assert mixed.frame_rate == voice.frame_rate
    assert mixed.channels == voice.channels
    os.remove(voice_path)
    os.remove(music_path)
