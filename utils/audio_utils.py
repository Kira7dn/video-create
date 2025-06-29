import soundfile as sf
import numpy as np
import os
import json
import tempfile
import subprocess


def load_audio_file(path):
    """
    Load audio file using soundfile, returns dict with data, samplerate, duration.
    """
    try:
        data, samplerate = sf.read(path)
        duration_sec = len(data) / samplerate
        return {
            "data": data,
            "samplerate": samplerate,
            "duration_sec": duration_sec,
            "duration_ms": duration_sec * 1000,
        }
    except Exception as e:
        raise ValueError(f"Unsupported or unreadable audio format for {path}: {e}")


def adjust_volume(audio_dict, gain_db):
    """
    Adjust volume for audio data (gain_db can be negative or positive).
    """
    # Convert dB to linear gain
    gain_linear = 10 ** (gain_db / 20)
    adjusted_data = audio_dict["data"] * gain_linear

    return {
        "data": np.clip(adjusted_data, -1.0, 1.0),  # Prevent clipping
        "samplerate": audio_dict["samplerate"],
        "duration_sec": audio_dict["duration_sec"],
        "duration_ms": audio_dict["duration_ms"],
    }


def simple_resample(data, current_sr, target_sr):
    """
    Simple resampling using linear interpolation.
    For production use, consider using librosa.resample for better quality.
    """
    if current_sr == target_sr:
        return data

    ratio = target_sr / current_sr
    new_length = int(len(data) * ratio)

    # Simple linear interpolation
    old_indices = np.linspace(0, len(data) - 1, new_length)
    new_data = np.interp(old_indices, np.arange(len(data)), data)

    return new_data


def mix_audio(voice_over, background_music, bgm_gain_when_voice=-10):
    """
    Mix voice_over onto background_music, reducing BGM volume when voice is present.
    - voice_over, background_music: audio dicts from load_audio_file
    - bgm_gain_when_voice: dB reduction for background music during overlay
    """
    # Ensure same sample rate
    if voice_over["samplerate"] != background_music["samplerate"]:
        # Resample background music to match voice
        target_sr = voice_over["samplerate"]
        current_sr = background_music["samplerate"]

        resampled_data = simple_resample(
            background_music["data"], current_sr, target_sr
        )
        background_music = {
            "data": resampled_data,
            "samplerate": target_sr,
            "duration_sec": len(resampled_data) / target_sr,
            "duration_ms": len(resampled_data) / target_sr * 1000,
        }

    # Ensure same number of channels (convert to mono if needed)
    voice_data = voice_over["data"]
    bgm_data = background_music["data"]

    if voice_data.ndim > 1:
        voice_data = np.mean(voice_data, axis=1)  # Convert to mono
    if bgm_data.ndim > 1:
        bgm_data = np.mean(bgm_data, axis=1)  # Convert to mono

    # Apply gain reduction to background music
    gain_linear = 10 ** (bgm_gain_when_voice / 20)
    bgm_reduced = bgm_data * gain_linear

    # Make arrays same length (pad shorter one with zeros)
    max_len = max(len(voice_data), len(bgm_reduced))
    if len(voice_data) < max_len:
        voice_data = np.pad(voice_data, (0, max_len - len(voice_data)))
    if len(bgm_reduced) < max_len:
        bgm_reduced = np.pad(bgm_reduced, (0, max_len - len(bgm_reduced)))

    # Mix audio (overlay voice over background)
    mixed_data = np.clip(voice_data + bgm_reduced, -1.0, 1.0)

    return {
        "data": mixed_data,
        "samplerate": voice_over["samplerate"],
        "duration_sec": max_len / voice_over["samplerate"],
        "duration_ms": max_len / voice_over["samplerate"] * 1000,
    }


def manage_audio_duration(audio_dict, target_duration_ms):
    """
    Adjust audio duration (trim or loop to reach target_duration_ms).
    """
    current_samples = len(audio_dict["data"])
    current_duration_ms = audio_dict["duration_ms"]
    samplerate = audio_dict["samplerate"]

    target_samples = int((target_duration_ms / 1000) * samplerate)

    if current_samples > target_samples:
        # Trim audio
        trimmed_data = audio_dict["data"][:target_samples]
    else:
        # Loop audio to reach target duration
        repeats_needed = (target_samples // current_samples) + 1
        extended_data = np.tile(audio_dict["data"], repeats_needed)
        trimmed_data = extended_data[:target_samples]

    return {
        "data": trimmed_data,
        "samplerate": samplerate,
        "duration_sec": target_samples / samplerate,
        "duration_ms": target_duration_ms,
    }


def save_audio_to_file(audio_dict, output_path, format="mp3"):
    """
    Save audio dict to file using soundfile.
    For MP3 output, save as WAV first then convert with ffmpeg if needed.
    """
    if format.lower() == "mp3":
        # soundfile doesn't support MP3 directly, use WAV as intermediate
        temp_wav = output_path.replace(".mp3", "_temp.wav")
        sf.write(temp_wav, audio_dict["data"], audio_dict["samplerate"])

        # Convert to MP3 using ffmpeg (if available)
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-i",
                    temp_wav,
                    "-codec:a",
                    "libmp3lame",
                    "-b:a",
                    "192k",
                    output_path,
                    "-y",
                ],
                check=True,
                capture_output=True,
            )
            os.remove(temp_wav)  # Cleanup temp file
        except (subprocess.CalledProcessError, FileNotFoundError):
            # Fallback: rename WAV to requested name
            os.rename(temp_wav, output_path.replace(".mp3", ".wav"))
            return output_path.replace(".mp3", ".wav")
    else:
        # For WAV, FLAC, etc. - direct save
        sf.write(output_path, audio_dict["data"], audio_dict["samplerate"])

    return output_path
