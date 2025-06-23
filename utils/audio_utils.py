from pydub.generators import Sine
from pydub import AudioSegment
import os
import json


def load_audio_file(path):
    """
    Đọc file audio (mp3, wav, ...), trả về AudioSegment. Raise error nếu không hỗ trợ.
    """
    try:
        audio = AudioSegment.from_file(path)
        return audio
    except Exception as e:
        raise ValueError(f"Unsupported or unreadable audio format for {path}: {e}")


def adjust_volume(audio_segment, gain_db):
    """
    Điều chỉnh âm lượng cho AudioSegment (gain_db có thể âm hoặc dương).
    """
    return audio_segment.apply_gain(gain_db)


def mix_audio(voice_over, background_music, bgm_gain_when_voice=-10):
    """
    Mix voice_over lên background_music, giảm âm lượng nhạc nền khi có lời thoại.
    - voice_over, background_music: AudioSegment
    - bgm_gain_when_voice: dB giảm cho nhạc nền khi overlay
    """
    # Đảm bảo cùng sample rate và channels
    if voice_over.frame_rate != background_music.frame_rate:
        background_music = background_music.set_frame_rate(voice_over.frame_rate)
    if voice_over.channels != background_music.channels:
        background_music = background_music.set_channels(voice_over.channels)
    # Giảm âm lượng nhạc nền
    bgm_lowered = background_music.apply_gain(bgm_gain_when_voice)
    # Overlay voice lên nhạc nền
    mixed = bgm_lowered.overlay(voice_over)
    return mixed


def manage_audio_duration(audio, target_duration_ms):
    """
    Điều chỉnh độ dài audio (cắt hoặc lặp lại cho đủ target_duration_ms).
    """
    if len(audio) > target_duration_ms:
        return audio[:target_duration_ms]
    elif len(audio) < target_duration_ms:
        # Lặp lại cho đủ
        times = target_duration_ms // len(audio) + 1
        extended = audio * times
        return extended[:target_duration_ms]
    else:
        return audio
