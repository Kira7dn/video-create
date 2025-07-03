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
import subprocess
import tempfile
import os


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
    """Helper function to load video clips from paths with proper error handling."""
    clips = []
    try:
        for path in video_paths:
            try:
                clip = VideoFileClip(path)
                clips.append(clip)
            except Exception as e:
                # Clean up already loaded clips on error
                for loaded_clip in clips:
                    try:
                        loaded_clip.close()
                    except:
                        pass
                raise RuntimeError(f"Failed to load video {path}: {e}")

        if not clips:
            raise RuntimeError("No valid video clips to concatenate.")
        return clips
    except Exception as e:
        # Ensure cleanup on any error
        for clip in clips:
            try:
                clip.close()
            except:
                pass
        raise


def concatenate_videos_with_sequence(
    video_paths: List[str],
    transitions: Optional[List[Dict[str, Any]]] = None,
    default_duration: float = 1.0,
) -> Any:
    """
    Ghép nhiều video với sequence hiệu ứng chuyển cảnh khác nhau giữa từng cặp clip.
    Phiên bản này được tối ưu hóa để tránh xử lý lặp lại và sử dụng phương pháp phù hợp (composition hoặc concatenation).
    Cải thiện memory management để tránh crash Docker.
    """
    import gc

    clips = _load_video_clips(video_paths)
    if not clips:
        return None

    try:
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
                        clip.with_start(start_time).with_effects(
                            [vfx.CrossFadeIn(tdur)]
                        )
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

            final_clip = CompositeVideoClip(composition_clips)

            # Force garbage collection after creating composite clip
            gc.collect()

            return final_clip

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

            final_clip = concatenate_videoclips(final_clips, method="chain")

            # Force garbage collection after concatenation
            gc.collect()

            return final_clip

    except Exception as e:
        # Clean up clips on error to prevent memory leak
        for clip in clips:
            try:
                clip.close()
            except:
                pass
        raise RuntimeError(f"Failed to concatenate videos: {e}")
    finally:
        # Force garbage collection to help with memory management
        gc.collect()


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


def ffmpeg_concat_videos(
    video_paths: List[str],
    output_path: str,
    reencode: bool = False,
    logger: Optional[Any] = None,
) -> None:
    """
    Concatenate multiple video files using ffmpeg command-line concat for memory efficiency.
    Args:
        video_paths: List of input video file paths (must be same codec, resolution, fps)
        output_path: Output file path (should end with .mp4)
        reencode: If True, re-encode instead of stream copy (slower, but allows different codecs)
        logger: Optional logger for debug/info
    Raises:
        RuntimeError if ffmpeg fails
    """
    import psutil
    import time
    
    filelist_path = None  # Initialize to avoid unbound variable in finally block
    
    try:
        if logger:
            logger.info(f"🎬 Starting ffmpeg concat: {len(video_paths)} videos")
            logger.info(f"📁 Output path: {output_path}")
            
        if not video_paths or len(video_paths) < 2:
            raise ValueError("Need at least two videos to concatenate")
        if not output_path.lower().endswith(".mp4"):
            output_path += ".mp4"

        # Log process info before concat
        if logger:
            try:
                process = psutil.Process()
                logger.info(f"🔍 Process info before concat:")
                logger.info(f"   PID: {process.pid}")
                logger.info(f"   Memory: {process.memory_info().rss // 1024 // 1024} MB")
                logger.info(f"   Open files: {len(process.open_files())}")
            except Exception as e:
                logger.warning(f"Could not get process info: {e}")

        # Validate and log input files
        total_input_size = 0
        for i, path in enumerate(video_paths):
            if not os.path.exists(path):
                raise FileNotFoundError(f"Input video {i} not found: {path}")
            size = os.path.getsize(path)
            total_input_size += size
            if logger:
                logger.info(f"📹 Input {i}: {os.path.basename(path)} ({size//1024} KB)")

        if logger:
            logger.info(f"📊 Total input size: {total_input_size//1024//1024} MB")

        # Check disk space
        try:
            import shutil
            free_space = shutil.disk_usage(os.path.dirname(output_path)).free
            required_space = total_input_size * 2  # Buffer for output file
            if logger:
                logger.info(f"💾 Free disk space: {free_space//1024//1024} MB")
                logger.info(f"💾 Required space: {required_space//1024//1024} MB")
            if free_space < required_space:
                raise RuntimeError(f"Insufficient disk space: {free_space//1024//1024}MB available, {required_space//1024//1024}MB required")
        except Exception as e:
            if logger:
                logger.warning(f"Could not check disk space: {e}")

        # Create a temporary file list for ffmpeg
        if logger:
            logger.info(f"📝 Creating ffmpeg file list...")
        filelist_path = None
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for path in video_paths:
                f.write(f"file '{os.path.abspath(path)}'\n")
            filelist_path = f.name

        if logger:
            logger.info(f"📝 File list created: {filelist_path}")

        ffmpeg_cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-f", "concat",
            "-safe", "0",
            "-i", filelist_path,
        ]
        if reencode:
            ffmpeg_cmd += ["-c:v", "libx264", "-c:a", "aac"]
            if logger:
                logger.info(f"🔧 Using re-encode mode")
        else:
            ffmpeg_cmd += ["-c", "copy"]
            if logger:
                logger.info(f"🔧 Using stream copy mode")
        ffmpeg_cmd.append(output_path)

        if logger:
            logger.info(f"🔧 FFmpeg command: {' '.join(ffmpeg_cmd)}")
            logger.info(f"⏰ Starting ffmpeg execution...")

        start_time = time.time()
        
        try:
            result = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
                timeout=600  # 10 minutes timeout
            )
            
            execution_time = time.time() - start_time
            
            if logger:
                logger.info(f"✅ FFmpeg concat completed in {execution_time:.2f}s")
                if os.path.exists(output_path):
                    output_size = os.path.getsize(output_path)
                    logger.info(f"📤 Output file size: {output_size//1024//1024} MB")
                else:
                    logger.error(f"❌ Output file not created: {output_path}")
                    
                if result.stdout.strip():
                    logger.info(f"📜 FFmpeg stdout: {result.stdout.strip()}")
                if result.stderr.strip():
                    logger.info(f"📜 FFmpeg stderr: {result.stderr.strip()}")
                    
        except subprocess.TimeoutExpired:
            if logger:
                logger.error("❌ FFmpeg concat timeout (>10 minutes)")
            raise RuntimeError("FFmpeg concat timeout")
        except subprocess.CalledProcessError as e:
            if logger:
                logger.error(f"❌ FFmpeg failed with code {e.returncode}")
                logger.error(f"❌ FFmpeg stderr: {e.stderr}")
                logger.error(f"❌ FFmpeg stdout: {e.stdout}")
            raise RuntimeError(f"FFmpeg concat failed: {e.stderr}")

        # Log process info after concat
        if logger:
            try:
                process = psutil.Process()
                logger.info(f"🔍 Process info after concat:")
                logger.info(f"   Memory: {process.memory_info().rss // 1024 // 1024} MB")
                logger.info(f"   Open files: {len(process.open_files())}")
            except Exception as e:
                logger.warning(f"Could not get process info after concat: {e}")

    except Exception as e:
        if logger:
            logger.error(f"💥 Exception in ffmpeg_concat_videos: {e}")
            logger.error(f"💥 Exception type: {type(e).__name__}")
            try:
                process = psutil.Process()
                logger.error(f"💥 Process memory at crash: {process.memory_info().rss // 1024 // 1024} MB")
            except:
                pass
        raise
    finally:
        try:
            if filelist_path and os.path.exists(filelist_path):
                os.remove(filelist_path)
                if logger:
                    logger.info(f"🗑️ Cleaned up file list: {filelist_path}")
        except Exception as e:
            if logger:
                logger.warning(f"Failed to cleanup file list: {e}")
