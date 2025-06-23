from moviepy.video.VideoClip import ImageClip
from moviepy.video.compositing.CompositeVideoClip import concatenate_videoclips
from moviepy.video.io.VideoFileClip import VideoFileClip
import cv2
from moviepy import vfx as fx


def create_raw_video_clip_from_images(images, total_audio_duration_sec, fps=24):
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


def merge_audio_with_video_clip(video_clip, audio_clip):
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
    video_clip, output_path, fps=24, codec="libx264", audio_codec="aac"
):
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


def concatenate_videos(video_paths, transition_type=None, transition_duration=1.0):
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
    from moviepy.video.fx.FadeIn import FadeIn
    from moviepy.video.fx.FadeOut import FadeOut
    from moviepy.video.VideoClip import ColorClip
    from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip

    clips = []
    for path in video_paths:
        try:
            clip = VideoFileClip(path)
            clips.append(clip)
        except Exception as e:
            raise RuntimeError(f"Failed to load video {path}: {e}")
    if not clips:
        raise RuntimeError("No valid video clips to concatenate.")
    if transition_type == "crossfade":
        final_clip = concatenate_videoclips(
            clips, method="compose", padding=-transition_duration
        )
    elif transition_type == "fade":
        for i, clip in enumerate(clips):
            if i > 0:
                clips[i] = FadeIn(transition_duration).copy().apply(clip)
            if i < len(clips) - 1:
                clips[i] = FadeOut(transition_duration).copy().apply(clips[i])
        final_clip = concatenate_videoclips(clips, method="compose")
    elif transition_type == "fadeblack":
        # Fade out to black, insert black clip, fade in from black
        new_clips = []
        for i, clip in enumerate(clips):
            c = (
                FadeOut(transition_duration).copy().apply(clip)
                if i < len(clips) - 1
                else clip
            )
            new_clips.append(c)
            if i < len(clips) - 1:
                black = ColorClip(
                    size=clip.size, color=(0, 0, 0), duration=transition_duration
                )
                black = FadeIn(transition_duration).copy().apply(black)
                new_clips.append(black)
        final_clip = concatenate_videoclips(new_clips, method="compose")
    elif transition_type == "slideleft":
        # Slide left: clip sau trượt từ phải sang
        def slide_left(clip, duration):
            w, h = clip.size
            return clip.with_start(0).with_position(
                lambda t: (w * (1 - t / duration), 0) if t < duration else (0, 0)
            )

        new_clips = [clips[0]]
        for i in range(1, len(clips)):
            slide = slide_left(clips[i], transition_duration)
            new_clips.append(slide)
        final_clip = CompositeVideoClip(new_clips).with_duration(
            sum([c.duration for c in clips])
        )
    elif transition_type == "slideright":
        # Slide right: clip sau trượt từ trái sang
        def slide_right(clip, duration):
            w, h = clip.size
            return clip.with_start(0).with_position(
                lambda t: (-w * (1 - t / duration), 0) if t < duration else (0, 0)
            )

        new_clips = [clips[0]]
        for i in range(1, len(clips)):
            slide = slide_right(clips[i], transition_duration)
            new_clips.append(slide)
        final_clip = CompositeVideoClip(new_clips).with_duration(
            sum([c.duration for c in clips])
        )
    else:
        final_clip = concatenate_videoclips(clips, method="compose")
    return final_clip


def concatenate_videos_with_sequence(
    video_paths, transitions=None, default_duration=1.0
):
    """
    Ghép nhiều video với sequence hiệu ứng chuyển cảnh khác nhau giữa từng cặp clip.
    Args:
        video_paths: list[str] - danh sách đường dẫn video
        transitions: list[dict] - mỗi dict gồm {"type": <transition_type>, "duration": <float>} cho từng cặp (len = len(video_paths)-1)
        default_duration: float - thời lượng mặc định nếu không chỉ định
    Returns:
        MoviePy VideoClip đã nối
    """
    from moviepy.video.fx.FadeIn import FadeIn
    from moviepy.video.fx.FadeOut import FadeOut
    from moviepy.video.VideoClip import ColorClip
    from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip
    from moviepy.video.compositing.CompositeVideoClip import concatenate_videoclips

    clips = []
    for path in video_paths:
        try:
            clip = VideoFileClip(path)
            clips.append(clip)
        except Exception as e:
            raise RuntimeError(f"Failed to load video {path}: {e}")
    if not clips:
        raise RuntimeError("No valid video clips to concatenate.")
    if not transitions or len(transitions) != len(clips) - 1:
        # fallback: dùng cut nối thẳng
        return concatenate_videoclips(clips, method="compose")
    out_clips = [clips[0]]
    for i in range(1, len(clips)):
        trans = transitions[i - 1] or {}
        ttype = trans.get("type", None)
        tdur = trans.get("duration", default_duration)
        if ttype == "crossfade":
            # Crossfade: nối 2 clip với padding âm
            prev = out_clips.pop()
            merged = concatenate_videoclips(
                [prev, clips[i]], method="compose", padding=-tdur
            )
            out_clips.append(merged)
        elif ttype == "fade":
            prev = out_clips.pop()
            prev = FadeOut(tdur).copy().apply(prev)
            curr = FadeIn(tdur).copy().apply(clips[i])
            merged = concatenate_videoclips([prev, curr], method="compose")
            out_clips.append(merged)
        elif ttype == "fadeblack":
            prev = out_clips.pop()
            prev = FadeOut(tdur).copy().apply(prev)
            black = ColorClip(size=clips[i].size, color=(0, 0, 0), duration=tdur)
            black = FadeIn(tdur).copy().apply(black)
            curr = FadeIn(tdur).copy().apply(clips[i])
            merged = concatenate_videoclips([prev, black, curr], method="compose")
            out_clips.append(merged)
        elif ttype == "slideleft":

            def slide_left(clip, duration):
                w, h = clip.size
                return clip.with_start(0).with_position(
                    lambda t: (w * (1 - t / duration), 0) if t < duration else (0, 0)
                )

            prev = out_clips.pop()
            slide = slide_left(clips[i], tdur)
            merged = CompositeVideoClip([prev, slide]).with_duration(
                prev.duration + clips[i].duration
            )
            out_clips.append(merged)
        elif ttype == "slideright":

            def slide_right(clip, duration):
                w, h = clip.size
                return clip.with_start(0).with_position(
                    lambda t: (-w * (1 - t / duration), 0) if t < duration else (0, 0)
                )

            prev = out_clips.pop()
            slide = slide_right(clips[i], tdur)
            merged = CompositeVideoClip([prev, slide]).with_duration(
                prev.duration + clips[i].duration
            )
            out_clips.append(merged)
        else:
            # cut nối thẳng
            out_clips.append(clips[i])
    # Nếu có nhiều merged clip, nối lại lần cuối
    if len(out_clips) > 1:
        return concatenate_videoclips(out_clips, method="compose")
    return out_clips[0]
