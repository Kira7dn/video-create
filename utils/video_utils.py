from typing import List, Optional, Dict, Any
from utils.subprocess_utils import safe_subprocess_run, SubprocessError


class VideoProcessingError(SubprocessError):
    """Custom exception for video processing errors - inherits from SubprocessError"""
    pass

def ffmpeg_concat_videos(
    video_segments: List[Dict[str, str]],
    output_path: str,
    transitions: Optional[list] = None,
    background_music: Optional[dict] = None,
    logger: Optional[Any] = None,
    default_transition_type: str = "fade",
    default_transition_duration: float = 1.0,
    bgm_volume: float = 0.2,
) -> None:
    """
    Concatenate video segments with per-pair transitions, then overlay background music (with start_delay, end_delay) as in input_sample2.json.
    - video_segments: list of dicts with 'id' and 'path'.
    - transitions: list of dicts with 'type', 'duration', 'from_segment', 'to_segment'.
    - background_music: dict with 'url' or 'local_path', 'start_delay', 'end_delay'.
    """
    import tempfile
    import os
    import shutil
    import json
    import re

    def get_duration(path):
        cmd = [
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration", "-of", "json", path
        ]
        try:
            result = safe_subprocess_run(cmd, f"Get duration for {path}", logger)
            info = json.loads(result.stdout)
            return float(info["format"]["duration"])
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            error_msg = f"Failed to parse duration from {path}: {e}"
            if logger:
                logger.error(error_msg)
            raise VideoProcessingError(error_msg) from e

    def get_mean_volume(audio_path):
        cmd = [
            "ffmpeg", "-i", audio_path, "-af", "volumedetect", "-vn", "-sn", "-dn", "-f", "null", "NUL" if os.name == "nt" else "/dev/null"
        ]
        try:
            result = safe_subprocess_run(cmd, f"Get mean volume for {audio_path}", logger)
            match = re.search(r"mean_volume:\s*(-?\d+(\.\d+)?) dB", result.stderr)
            if match:
                return float(match.group(1))
            return None
        except Exception as e:
            if logger:
                logger.warning(f"Failed to get mean volume for {audio_path}: {e}")
            return None

    temp_dir = tempfile.mkdtemp()
    try:
        # 1. Concat segments with transitions
        current = video_segments[0]
        for idx in range(1, len(video_segments)):
            next_seg = video_segments[idx]
            transition = None
            if transitions:
                for t in transitions:
                    if t.get("from_segment") == current["id"] and t.get("to_segment") == next_seg["id"]:
                        transition = t
                        break
            t_type = transition.get("type") if transition and transition.get("type") else default_transition_type
            t_duration = float(transition.get("duration", default_transition_duration)) if transition else default_transition_duration
            dur1 = get_duration(current["path"])
            offset = dur1 - t_duration
            temp_out = os.path.join(temp_dir, f"xfade_{idx}.mp4")
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-i", current["path"],
                "-i", next_seg["path"],
                "-filter_complex",
                f"[0:v][1:v]xfade=transition={t_type}:duration={t_duration}:offset={offset}[v];"
                f"[0:a][1:a]acrossfade=d={t_duration}[a]",
                "-map", "[v]", "-map", "[a]",
                "-c:v", "libx264", "-c:a", "aac", temp_out
            ]
            safe_subprocess_run(ffmpeg_cmd, f"Video transition {idx} ({t_type})", logger)
            current = {"id": next_seg["id"], "path": temp_out}
        shutil.move(current["path"], output_path)
        if logger:
            logger.info(f"Final video with transitions: {output_path}")

        # 2. Overlay background music if provided
        if background_music and background_music.get("local_path"):
            bgm_path = background_music["local_path"]
            start_delay = float(background_music.get("start_delay", 0) or 0)
            video_duration = get_duration(output_path)
            # Auto adjust bgm volume based on mean_volume
            try:
                video_mean_volume = get_mean_volume(output_path)
                music_mean_volume = get_mean_volume(bgm_path)
                if video_mean_volume is not None and music_mean_volume is not None:
                    diff_db = video_mean_volume - music_mean_volume
                    bgm_volume_factor = 10 ** (diff_db / 20)
                    bgm_volume_factor = max(0.1, min(bgm_volume_factor, 0.5))
                    if logger:
                        logger.info(f"🔊 Auto-adjusted bgm volume factor: {bgm_volume_factor:.2f} (video_mean={video_mean_volume}dB, music_mean={music_mean_volume}dB)")
                else:
                    bgm_volume_factor = bgm_volume
                    if logger:
                        logger.warning("⚠️ Could not auto-detect mean_volume, using default bgm volume 0.2")
            except Exception as e:
                bgm_volume_factor = bgm_volume
                if logger:
                    logger.warning(f"⚠️ Error auto-adjusting bgm volume: {e}, using default 0.2")
            # Prepare filter for bgm: delay, trim, volume
            bgm_play_duration = max(0, video_duration - start_delay)
            filter_parts = []
            if start_delay > 0:
                delay_ms = int(start_delay * 1000)
                filter_parts.append(f"adelay={delay_ms}|{delay_ms}")
            filter_parts.append(f"atrim=duration={bgm_play_duration}")
            filter_parts.append(f"volume={bgm_volume_factor}")
            bgm_filter = ",".join(filter_parts)
            # Compose filter_complex for direct mix
            filter_complex = (
                f"[1:a]{bgm_filter}[bgm]; "
                f"[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
            # Use temp file for safe atomic operation - avoid overwriting output_path directly
            temp_final_with_bgm = os.path.join(temp_dir, "final_with_bgm.mp4")
            ffmpeg_mix_cmd = [
                "ffmpeg", "-y",
                "-i", output_path,
                "-i", bgm_path,
                "-filter_complex", filter_complex,
                "-map", "0:v", "-map", "[aout]",
                "-c:v", "copy", "-c:a", "aac", "-shortest", temp_final_with_bgm
            ]
            if logger:
                logger.info(f"Mixing BGM (atomic operation): {' '.join(ffmpeg_mix_cmd)}")
            safe_subprocess_run(ffmpeg_mix_cmd, "Background music mixing", logger)
            # Atomic move - only overwrite output_path when processing is completely successful
            shutil.move(temp_final_with_bgm, output_path)
            if logger:
                logger.info(f"Final video with background music: {output_path}")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
