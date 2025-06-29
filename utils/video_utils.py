from moviepy import (
    VideoFileClip,
    ImageClip,
    CompositeVideoClip,
    vfx,
    ColorClip,
    concatenate_videoclips,
)
import cv2
from typing import List, Optional, Dict, Any
import numpy as np


def create_raw_video_clip_from_images(
    images: List[np.ndarray], total_audio_duration_sec: float, fps: int = 24
) -> Any:
    """
    Create a raw video clip from a list of numpy images, each image displayed for duration_per_image.
    Args:
        images: list of numpy arrays (H, W, 3) in BGR (OpenCV)
        total_audio_duration_sec: float, total duration in seconds
        fps: int, frames per second
    Returns:
        VideoClip object
    """
    n = len(images)
    if n == 0:
        raise ValueError("No images provided")

    duration_per_image = total_audio_duration_sec / n

    # Process images to ensure valid dimensions for H.264
    processed_images = []
    for i, img in enumerate(images):
        # Convert from BGR (OpenCV) to RGB (MoviePy)
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Ensure dimensions are divisible by 2 for H.264 compatibility
        h, w = rgb_img.shape[:2]
        if h % 2 != 0:
            rgb_img = rgb_img[:-1, :, :]  # Remove bottom row
        if w % 2 != 0:
            rgb_img = rgb_img[:, :-1, :]  # Remove right column

        processed_images.append(rgb_img)

    clips = [
        ImageClip(img).with_duration(duration_per_image).with_fps(fps)
        for img in processed_images
    ]
    video = concatenate_videoclips(clips, method="compose")
    return video


def merge_audio_with_video_clip(video_clip: Any, audio_clip: Any) -> Any:
    """
    Merge a MoviePy audio clip into a MoviePy video clip.
    Args:
        video_clip: MoviePy VideoClip object (không có audio hoặc audio cũ)
        audio_clip: MoviePy AudioClip object (AudioFileClip, CompositeAudioClip, ...)
    Returns:
        VideoClip object đã gắn audio
    """
    if video_clip is None or audio_clip is None:
        raise ValueError("Both video_clip and audio_clip must be provided")
    # Gắn audio vào video (MoviePy >=2.2 dùng with_audio)
    video_with_audio = video_clip.with_audio(audio_clip)
    return video_with_audio


def export_final_video_clip(
    video_clip: Any,
    output_path: str,
    fps: int = 24,
    codec: str = "libx264",
    audio_codec: str = "aac",
    bitrate: Optional[str] = None,
    audio_bitrate: Optional[str] = None,
    preset: str = "medium",
    threads: Optional[int] = None,
    logger: Optional[str] = "bar",
    write_logfile: bool = False,
) -> None:
    """
    Export the final MoviePy video clip (with audio) to an MP4 file.
    Args:
        video_clip: MoviePy VideoClip object (đã gắn audio)
        output_path: str, đường dẫn file đầu ra (ví dụ: 'output.mp4')
        fps: int, frames per second (nên khớp với fps khi tạo video)
        codec: str, video codec (mặc định: 'libx264')
        audio_codec: str, audio codec (mặc định: 'aac')
        bitrate: str, video bitrate (ví dụ: '2000k', '5M'). None = auto
        audio_bitrate: str, audio bitrate (ví dụ: '128k', '320k'). None = auto
        preset: str, encoding preset for speed/quality tradeoff ('ultrafast', 'fast', 'medium', 'slow', 'veryslow')
        threads: int, số threads sử dụng. None = auto detect
        logger: str, loại progress logger ('bar', None, hoặc function)
        write_logfile: bool, có ghi log file hay không
    Returns:
        None
    Raises:
        ValueError: nếu input không hợp lệ
        RuntimeError: nếu export thất bại
        OSError: nếu có vấn đề về file/directory
    """
    import os
    import multiprocessing

    # Validate inputs
    if video_clip is None:
        raise ValueError("video_clip must be provided")

    if not output_path or not isinstance(output_path, str):
        raise ValueError("output_path must be a non-empty string")

    # Validate and create output directory if needed
    output_dir = os.path.dirname(os.path.abspath(output_path))
    if output_dir and not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            raise OSError(f"Cannot create output directory {output_dir}: {e}")

    # Auto-detect threads if not specified
    if threads is None:
        threads = min(multiprocessing.cpu_count(), 8)  # Cap at 8 to avoid memory issues

    # Build ffmpeg parameters for better compatibility
    ffmpeg_params = []
    if bitrate:
        ffmpeg_params.extend(["-b:v", bitrate])
    if audio_bitrate:
        ffmpeg_params.extend(["-b:a", audio_bitrate])
    if preset and codec == "libx264":
        ffmpeg_params.extend(["-preset", preset])

    # Add compatibility parameters for Windows Media Player
    ffmpeg_params.extend(
        [
            "-pix_fmt",
            "yuv420p",  # Pixel format compatible with most players
            "-movflags",
            "+faststart",  # Move metadata to beginning of file
            "-f",
            "mp4",  # Force MP4 container format
            # Removed strict baseline profile to allow more flexibility
            "-profile:v",
            "main",  # H.264 main profile instead of baseline
            "-level",
            "4.0",  # H.264 level 4.0 for better compatibility
            # Force video dimensions to be divisible by 2
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",  # Ensure even dimensions
        ]
    )

    try:
        video_clip.write_videofile(
            output_path,
            fps=fps,
            codec=codec,
            audio_codec=audio_codec,
            threads=threads,
            ffmpeg_params=ffmpeg_params,
            logger=logger,
            write_logfile=write_logfile,
            temp_audiofile="temp-audio.m4a",  # Use specific temp audio format
            remove_temp=True,  # Clean up temp files
        )

        # Validate the created file
        if not os.path.exists(output_path):
            raise RuntimeError("Output file was not created")

        # Check if file has reasonable size (not empty or too small)
        file_size = os.path.getsize(output_path)
        if file_size < 1024:  # Less than 1KB is suspicious
            raise RuntimeError(
                f"Output file is too small ({file_size} bytes), possibly corrupted"
            )

    except FileNotFoundError as e:
        raise OSError(f"FFmpeg not found or output path invalid: {e}")
    except PermissionError as e:
        raise OSError(f"Permission denied writing to {output_path}: {e}")
    except Exception as e:
        # Clean up partial file if export failed
        if os.path.exists(output_path):
            try:
                os.remove(output_path)
            except OSError:
                pass  # Best effort cleanup
        raise RuntimeError(f"Export video failed: {e}")


def _load_video_clips(video_paths: List[str]) -> List[Any]:
    """Helper function to load video clips from paths."""
    clips = []
    for path in video_paths:
        try:
            clip = VideoFileClip(path)
            clips.append(clip)
        except Exception as e:
            raise RuntimeError(f"Failed to load video {path}: {e}")
    if not clips:
        raise RuntimeError("No valid video clips to concatenate.")
    return clips


# def _create_crossfade_sequence(clips: List[Any], crossfade_duration: float) -> Any:
#     """Create crossfade sequence using official MoviePy way."""
#     if len(clips) < 2:
#         return clips[0] if clips else None

#     # Use official MoviePy crossfade method
#     result_clips = [clips[0]]

#     for i in range(1, len(clips)):
#         # Set start time to create overlap
#         start_time = sum(clip.duration for clip in clips[:i]) - (
#             crossfade_duration * (i - 1)
#         )
#         crossfade_clip = (
#             clips[i]
#             .with_start(start_time)
#             .with_effects([vfx.CrossFadeIn(crossfade_duration)])
#         )
#         result_clips.append(crossfade_clip)

#     return CompositeVideoClip(result_clips)


# def concatenate_videos(
#     video_paths: List[str],
#     transition_type: Optional[str] = None,
#     transition_duration: float = 1.0,
# ) -> Any:
#     """
#     Nối các video lại với nhau, tuỳ chọn chèn hiệu ứng chuyển cảnh giữa các clip.
#     Args:
#         video_paths: list[str] - danh sách đường dẫn video
#         transition_type: None, "crossfade", "fade", "fadeblack", "slideleft", "slideright" (mặc định: None, nối thẳng)
#         transition_duration: float - thời lượng hiệu ứng chuyển cảnh (giây, mặc định: 1.0)
#     Returns:
#         MoviePy VideoClip đã nối
#     Raises:
#         RuntimeError nếu có video không load được hoặc nối lỗi
#     """
#     clips = _load_video_clips(video_paths)

#     if transition_type == "crossfade":
#         # Use official MoviePy crossfade method
#         return _create_crossfade_sequence(clips, transition_duration)
#     elif transition_type == "fade":
#         # Apply fade effects using modern API
#         faded_clips = []
#         for i, clip in enumerate(clips):
#             current_clip = clip
#             if i > 0:
#                 current_clip = current_clip.with_effects(
#                     [vfx.FadeIn(transition_duration)]
#                 )
#             if i < len(clips) - 1:
#                 current_clip = current_clip.with_effects(
#                     [vfx.FadeOut(transition_duration)]
#                 )
#             faded_clips.append(current_clip)
#         return concatenate_videoclips(faded_clips, method="chain")
#     elif transition_type == "fadeblack":
#         # Fade out to black, insert black clip, fade in from black
#         new_clips = []
#         for i, clip in enumerate(clips):
#             if i < len(clips) - 1:
#                 # Fade out current clip
#                 faded_clip = clip.with_effects([vfx.FadeOut(transition_duration)])
#                 new_clips.append(faded_clip)
#                 # Add black transition
#                 black = ColorClip(
#                     size=clip.size, color=(0, 0, 0), duration=transition_duration
#                 )
#                 new_clips.append(black)
#                 # Next clip will be faded in (handled in next iteration)
#             else:
#                 # Last clip, apply fade in if not first
#                 if i > 0:
#                     clip = clip.with_effects([vfx.FadeIn(transition_duration)])
#                 new_clips.append(clip)
#         return concatenate_videoclips(new_clips, method="chain")
#     else:
#         return concatenate_videoclips(clips, method="chain")


def concatenate_videos_with_sequence(
    video_paths: List[str],
    transitions: Optional[List[Dict[str, Any]]] = None,
    default_duration: float = 1.0,
) -> Any:
    """
    Ghép nhiều video với sequence hiệu ứng chuyển cảnh khác nhau giữa từng cặp clip.
    Phiên bản này được tối ưu hóa để tránh xử lý lặp lại và sử dụng phương pháp phù hợp (composition hoặc concatenation).
    """
    clips = _load_video_clips(video_paths)
    if not clips:
        return None

    # If not enough transitions, pad with None
    if transitions is None:
        transitions = []
    if len(transitions) < len(clips) - 1:
        transitions.extend([{}] * (len(clips) - 1 - len(transitions)))

    # If any transition is 'crossfade', the entire sequence must be a CompositeVideoClip
    if any(t and t.get("type") == "crossfade" for t in transitions):
        composition_clips = []
        current_pos = 0.0
        for i, clip in enumerate(clips):
            if i == 0:
                # Handle first clip - check if next transition needs fade out
                if i < len(clips) - 1:
                    next_trans = transitions[i] or {}
                    next_ttype = next_trans.get("type")
                    next_tdur = next_trans.get("duration", default_duration)
                    if next_ttype in ["fade", "fadeblack"]:
                        clip = clip.with_effects([vfx.FadeOut(next_tdur)])

                composition_clips.append(clip.with_start(0))
                current_pos = clip.duration
                continue

            trans = transitions[i - 1] or {}
            ttype = trans.get("type")
            tdur = trans.get("duration", default_duration)

            if ttype == "crossfade":
                start_time = current_pos - tdur
                composition_clips.append(
                    clip.with_start(start_time).with_effects([vfx.CrossFadeIn(tdur)])
                )
                current_pos = start_time + clip.duration
            elif ttype == "fade":
                # Apply fade effects in composition mode
                faded_clip = clip.with_effects([vfx.FadeIn(tdur)])
                composition_clips.append(faded_clip.with_start(current_pos))
                current_pos += clip.duration
            elif ttype == "fadeblack":
                # Apply fade in from black in composition mode
                faded_clip = clip.with_effects([vfx.FadeIn(tdur)])
                # Add black clip before this clip
                black_clip = ColorClip(
                    size=clip.size, color=(0, 0, 0), duration=tdur
                ).with_start(current_pos)
                composition_clips.append(black_clip)
                composition_clips.append(faded_clip.with_start(current_pos + tdur))
                current_pos += clip.duration + tdur
            else:
                # For other transitions or no transition, place sequentially
                composition_clips.append(clip.with_start(current_pos))
                current_pos += clip.duration

        return CompositeVideoClip(composition_clips)

    # If no 'crossfade', we can use the more straightforward concatenation method
    else:
        final_clips = []
        for i, clip in enumerate(clips):
            # Fade-out for the first clip if needed
            if i == 0 and len(clips) > 1:
                next_trans = transitions[0] or {}
                next_ttype = next_trans.get("type")
                next_tdur = next_trans.get("duration", default_duration)
                if next_ttype == "fadeblack":
                    fadeout_duration = min(1.0, clip.duration / 2)
                    clip = clip.with_effects([vfx.FadeOut(fadeout_duration)])
                elif next_ttype == "fade":
                    fadeout_duration = min(next_tdur, clip.duration / 2)
                    if next_tdur > clip.duration / 2:
                        import warnings

                        warnings.warn(
                            f"Fade-out duration ({next_tdur}s) is greater than half of clip duration ({clip.duration}s). Capping to {fadeout_duration}s."
                        )
                    clip = clip.with_effects([vfx.FadeOut(fadeout_duration)])

            # Apply fade-in if the previous transition was 'fade' or 'fadeblack'
            if i > 0:
                prev_trans = transitions[i - 1] or {}
                prev_ttype = prev_trans.get("type")
                prev_tdur = prev_trans.get("duration", default_duration)
                if prev_ttype == "fadeblack":
                    fadein_duration = min(1.0, clip.duration / 2)
                    clip = clip.with_effects([vfx.FadeIn(fadein_duration)])
                elif prev_ttype == "fade":
                    fadein_duration = min(prev_tdur, clip.duration / 2)
                    if prev_tdur > clip.duration / 2:
                        import warnings

                        warnings.warn(
                            f"Fade-in duration ({prev_tdur}s) is greater than half of clip duration ({clip.duration}s). Capping to {fadein_duration}s."
                        )
                    clip = clip.with_effects([vfx.FadeIn(fadein_duration)])

            # Apply fade-out if the next transition is 'fade' or 'fadeblack' (for non-first clips)
            if i > 0 and i < len(clips) - 1:
                next_trans = transitions[i] or {}
                next_ttype = next_trans.get("type")
                next_tdur = next_trans.get("duration", default_duration)
                if next_ttype == "fadeblack":
                    fadeout_duration = min(1.0, clip.duration / 2)
                    clip = clip.with_effects([vfx.FadeOut(fadeout_duration)])
                elif next_ttype == "fade":
                    fadeout_duration = min(next_tdur, clip.duration / 2)
                    if next_tdur > clip.duration / 2:
                        import warnings

                        warnings.warn(
                            f"Fade-out duration ({next_tdur}s) is greater than half of clip duration ({clip.duration}s). Capping to {fadeout_duration}s."
                        )
                    clip = clip.with_effects([vfx.FadeOut(fadeout_duration)])

            final_clips.append(clip)

            # Add a black clip if the next transition is 'fadeblack'
            if i < len(clips) - 1:
                next_trans = transitions[i] or {}
                next_ttype = next_trans.get("type")
                next_tdur = next_trans.get("duration", default_duration)
                if next_ttype == "fadeblack":
                    black_clip = ColorClip(
                        size=clip.size, color=(0, 0, 0), duration=next_tdur
                    )
                    final_clips.append(black_clip)

        return concatenate_videoclips(final_clips, method="chain")


def export_video_with_quality_preset(
    video_clip: Any,
    output_path: str,
    quality: str = "medium",
    fps: int = 24,
) -> None:
    """
    Export video với các quality preset thông dụng để dễ sử dụng.
    Args:
        video_clip: MoviePy VideoClip object
        output_path: str, đường dẫn file đầu ra
        quality: str, quality preset ("low", "medium", "high", "ultra")
        fps: int, frames per second
    """
    quality_settings = {
        "low": {
            "bitrate": "1000k",
            "audio_bitrate": "128k",
            "preset": "fast",
            "codec": "libx264",
            "audio_codec": "aac",
        },
        "medium": {
            "bitrate": "2500k",
            "audio_bitrate": "192k",
            "preset": "medium",
            "codec": "libx264",
            "audio_codec": "aac",
        },
        "high": {
            "bitrate": "5000k",
            "audio_bitrate": "256k",
            "preset": "medium",  # Changed from slow for better compatibility
            "codec": "libx264",
            "audio_codec": "aac",
        },
        "ultra": {
            "bitrate": "8000k",
            "audio_bitrate": "320k",
            "preset": "medium",  # Changed from veryslow for better compatibility
            "codec": "libx264",
            "audio_codec": "aac",
        },
    }

    if quality not in quality_settings:
        raise ValueError(f"Quality must be one of: {list(quality_settings.keys())}")

    settings = quality_settings[quality]

    export_final_video_clip(
        video_clip=video_clip,
        output_path=output_path,
        fps=fps,
        codec=settings["codec"],
        audio_codec=settings["audio_codec"],
        bitrate=settings["bitrate"],
        audio_bitrate=settings["audio_bitrate"],
        preset=settings["preset"],
    )


def export_video_for_windows_media_player(
    video_clip: Any,
    output_path: str,
    fps: int = 24,
    quality: str = "medium",
) -> None:
    """
    Export video với compatibility tối ưu cho Windows Media Player và các player phổ biến.
    Args:
        video_clip: MoviePy VideoClip object
        output_path: str, đường dẫn file đầu ra
        fps: int, frames per second
        quality: str, quality level ("low", "medium", "high")
    """
    # Ensure output path has .mp4 extension
    if not output_path.lower().endswith(".mp4"):
        output_path = output_path.rsplit(".", 1)[0] + ".mp4"

    quality_bitrates = {"low": "1500k", "medium": "3000k", "high": "6000k"}

    audio_bitrates = {"low": "128k", "medium": "192k", "high": "256k"}

    bitrate = quality_bitrates.get(quality, "3000k")
    audio_bitrate = audio_bitrates.get(quality, "192k")

    export_final_video_clip(
        video_clip=video_clip,
        output_path=output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        bitrate=bitrate,
        audio_bitrate=audio_bitrate,
        preset="medium",  # Balance of speed and compatibility
        logger="bar",
        write_logfile=False,
    )
