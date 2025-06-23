import os
from utils.audio_utils import (
    load_audio_file,
    adjust_volume,
    mix_audio,
    manage_audio_duration,
)


def test_audio_pipeline_integration():
    voice_path = "source/voice/voice2.mp3"
    music_path = "source/bgm/bg1.mp3"
    assert os.path.exists(voice_path), f"Voice file not found: {voice_path}"
    assert os.path.exists(music_path), f"Music file not found: {music_path}"

    # 1. Load audio
    voice = load_audio_file(voice_path)
    music = load_audio_file(music_path)

    # 2. Điều chỉnh âm lượng nhạc nền (giảm 10dB)
    music_quiet = adjust_volume(music, -10)

    # 3. Mix voice lên nhạc nền
    mixed = mix_audio(
        voice, music_quiet, bgm_gain_when_voice=0
    )  # đã giảm trước nên gain overlay = 0

    # 4. Đảm bảo nhạc nền đủ dài (nếu cần)
    final_audio = manage_audio_duration(mixed, len(voice))

    # 5. Kiểm tra kết quả
    assert (
        abs(len(final_audio) - len(voice)) < 10
    ), "Final audio duration mismatch with voice-over"
    assert (
        final_audio.dBFS > music.dBFS
    ), "Final audio should be louder than background music alone"
    # Có thể export thử nếu muốn nghe thử:
    final_audio.export("test_output_mix.mp3", format="mp3")
