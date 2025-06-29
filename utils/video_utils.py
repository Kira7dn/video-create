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
    # Chuyển từng ảnh từ BGR (OpenCV) sang RGB (MoviePy)
    rgb_images = [cv2.cvtColor(img, cv2.COLOR_BGR2RGB) for img in images]
    clips = [
        ImageClip(img).with_duration(duration_per_image).with_fps(fps)
        for img in rgb_images
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
) -> None:
    """
    Export the final MoviePy video clip (with audio) to an MP4 file.
    Args:
        video_clip: MoviePy VideoClip object (đã gắn audio)
        output_path: str, đường dẫn file đầu ra (ví dụ: 'output.mp4')
        fps: int, frames per second (nên khớp với fps khi tạo video)
        codec: str, video codec (mặc định: 'libx264')
        audio_codec: str, audio codec (mặc định: 'aac')
    Returns:
        None
    Raises:
        Exception nếu export thất bại
    """
    if video_clip is None:
        raise ValueError("video_clip must be provided")
    try:
        video_clip.write_videofile(
            output_path,
            fps=fps,
            codec=codec,
            audio_codec=audio_codec,
            threads=4,  # Tăng tốc export nếu máy hỗ trợ
        )
    except Exception as e:
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


def _create_crossfade_sequence(clips: List[Any], crossfade_duration: float) -> Any:
    """Create crossfade sequence using official MoviePy way."""
    if len(clips) < 2:
        return clips[0] if clips else None

    # Use official MoviePy crossfade method
    result_clips = [clips[0]]

    for i in range(1, len(clips)):
        # Set start time to create overlap
        start_time = sum(clip.duration for clip in clips[:i]) - (
            crossfade_duration * (i - 1)
        )
        crossfade_clip = (
            clips[i]
            .with_start(start_time)
            .with_effects([vfx.CrossFadeIn(crossfade_duration)])
        )
        result_clips.append(crossfade_clip)

    return CompositeVideoClip(result_clips)


def concatenate_videos(
    video_paths: List[str],
    transition_type: Optional[str] = None,
    transition_duration: float = 1.0,
) -> Any:
    """
    Nối các video lại với nhau, tuỳ chọn chèn hiệu ứng chuyển cảnh giữa các clip.
    Args:
        video_paths: list[str] - danh sách đường dẫn video
        transition_type: None, "crossfade", "fade", "fadeblack", "slideleft", "slideright" (mặc định: None, nối thẳng)
        transition_duration: float - thời lượng hiệu ứng chuyển cảnh (giây, mặc định: 1.0)
    Returns:
        MoviePy VideoClip đã nối
    Raises:
        RuntimeError nếu có video không load được hoặc nối lỗi
    """
    clips = _load_video_clips(video_paths)

    if transition_type == "crossfade":
        # Use official MoviePy crossfade method
        return _create_crossfade_sequence(clips, transition_duration)
    elif transition_type == "fade":
        # Apply fade effects using modern API
        faded_clips = []
        for i, clip in enumerate(clips):
            current_clip = clip
            if i > 0:
                current_clip = current_clip.with_effects(
                    [vfx.FadeIn(transition_duration)]
                )
            if i < len(clips) - 1:
                current_clip = current_clip.with_effects(
                    [vfx.FadeOut(transition_duration)]
                )
            faded_clips.append(current_clip)
        return concatenate_videoclips(faded_clips, method="chain")
    elif transition_type == "fadeblack":
        # Fade out to black, insert black clip, fade in from black
        new_clips = []
        for i, clip in enumerate(clips):
            if i < len(clips) - 1:
                # Fade out current clip
                faded_clip = clip.with_effects([vfx.FadeOut(transition_duration)])
                new_clips.append(faded_clip)
                # Add black transition
                black = ColorClip(
                    size=clip.size, color=(0, 0, 0), duration=transition_duration
                )
                new_clips.append(black)
                # Next clip will be faded in (handled in next iteration)
            else:
                # Last clip, apply fade in if not first
                if i > 0:
                    clip = clip.with_effects([vfx.FadeIn(transition_duration)])
                new_clips.append(clip)
        return concatenate_videoclips(new_clips, method="chain")
    else:
        return concatenate_videoclips(clips, method="chain")


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
            else:
                # For other transitions in composition mode, we just place them sequentially.
                composition_clips.append(clip.with_start(current_pos))
                current_pos += clip.duration

        return CompositeVideoClip(composition_clips)

    # If no 'crossfade', we can use the more straightforward concatenation method
    else:
        final_clips = []
        for i, clip in enumerate(clips):
            # Apply fade-in if the previous transition was 'fade' or 'fadeblack'
            if i > 0:
                prev_trans = transitions[i - 1] or {}
                prev_ttype = prev_trans.get("type")
                prev_tdur = prev_trans.get("duration", default_duration)
                if prev_ttype in ["fade", "fadeblack"]:
                    clip = clip.with_effects([vfx.FadeIn(prev_tdur)])

            # Apply fade-out if the next transition is 'fade'
            if i < len(clips) - 1:
                next_trans = transitions[i] or {}
                next_ttype = next_trans.get("type")
                next_tdur = next_trans.get("duration", default_duration)
                if next_ttype == "fade":
                    clip = clip.with_effects([vfx.FadeOut(next_tdur)])

            final_clips.append(clip)

            # Add a black clip if the next transition is 'fadeblack'
            if i < len(clips) - 1:
                next_trans = transitions[i] or {}
                next_ttype = next_trans.get("type")
                next_tdur = next_trans.get("duration", default_duration)
                if next_ttype == "fadeblack":
                    final_clips[-1] = final_clips[-1].with_effects(
                        [vfx.FadeOut(next_tdur)]
                    )
                    black_clip = ColorClip(
                        size=clip.size, color=(0, 0, 0), duration=next_tdur
                    )
                    final_clips.append(black_clip)

        return concatenate_videoclips(final_clips, method="chain")
