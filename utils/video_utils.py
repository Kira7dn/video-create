from typing import List, Optional, Dict, Any
import os

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


def ffmpeg_concat_videos(
    video_paths: List[str],
    output_path: str,
    background_music: Optional[dict] = None,
    reencode: bool = False,
    logger: Optional[Any] = None,
) -> None:
    """
    Concatenate multiple video files using ffmpeg with optimized subprocess approach.
    Simplified logic: concat videos + optional background music overlay.
    Now auto-adjusts background music volume to not overpower video audio.
    """
    import time
    import tempfile
    import subprocess
    import os
    import re

    def get_mean_volume(audio_path):
        cmd = [
            "ffmpeg", "-i", audio_path, "-af", "volumedetect", "-vn", "-sn", "-dn", "-f", "null", "NUL" if os.name == "nt" else "/dev/null"
        ]
        result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        match = re.search(r"mean_volume:\s*(-?\d+(\.\d+)?) dB", result.stderr)
        if match:
            return float(match.group(1))
        return None

    filelist_path = None
    ffmpeg_cmd = []  # Initialize command list
    try:
        if logger:
            logger.info(f"🎬 Starting optimized ffmpeg concat: {len(video_paths)} videos")
            logger.info(f"📁 Output path: {output_path}")
        # Input validation
        if not video_paths or len(video_paths) < 1:
            raise ValueError("Need at least one video to process")
        if not output_path.lower().endswith(".mp4"):
            output_path += ".mp4"
        # Validate all input files exist
        for i, path in enumerate(video_paths):
            if not os.path.exists(path):
                raise FileNotFoundError(f"Input video {i} not found: {path}")
        # Create temporary file list for ffmpeg concat
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            for path in video_paths:
                f.write(f"file '{os.path.abspath(path)}'\n")
            filelist_path = f.name
        if logger:
            logger.info(f"📝 Created temp file list: {filelist_path}")
        # Build base ffmpeg command
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", filelist_path
        ]
        # Handle background music if provided
        background_music_path = None
        bgm_volume_factor = 0.2  # Default fallback
        if background_music and background_music.get("local_path"):
            local_path = background_music.get("local_path")
            if not local_path or not isinstance(local_path, str):
                raise ValueError("background_music['local_path'] must be a non-empty string")
            background_music_path = os.path.abspath(local_path)
            if not os.path.exists(background_music_path):
                raise FileNotFoundError(f"Background music file not found: {background_music_path}")
            ffmpeg_cmd += ["-i", background_music_path]
            if logger:
                logger.info(f"🎵 Adding background music: {background_music_path}")
            # --- Auto volume adjustment logic ---
            try:
                # Get mean_volume of video audio (first video)
                video_audio_path = os.path.abspath(video_paths[0])
                video_mean_volume = get_mean_volume(video_audio_path)
                music_mean_volume = get_mean_volume(background_music_path)
                if video_mean_volume is not None and music_mean_volume is not None:
                    diff_db = video_mean_volume - music_mean_volume
                    bgm_volume_factor = 10 ** (diff_db / 20)
                    # Clamp to 0.1 - 0.5 for safety
                    bgm_volume_factor = max(0.1, min(bgm_volume_factor, 0.5))
                    if logger:
                        logger.info(f"🔊 Auto-adjusted bgm volume factor: {bgm_volume_factor:.2f} (video_mean={video_mean_volume}dB, music_mean={music_mean_volume}dB)")
                else:
                    if logger:
                        logger.warning("⚠️ Could not auto-detect mean_volume, using default bgm volume 0.2")
            except Exception as e:
                if logger:
                    logger.warning(f"⚠️ Error auto-adjusting bgm volume: {e}, using default 0.2")
        # Configure encoding and filters
        if background_music_path:
            start_delay = float(background_music.get("start_delay", 0) or 0) if background_music else 0
            if start_delay > 0:
                delay_ms = int(start_delay * 1000)
                bgm_filter = f"[1:a]aloop=loop=-1:size=2e+09,adelay={delay_ms}|{delay_ms},volume={bgm_volume_factor}[bgm]"
            else:
                bgm_filter = f"[1:a]aloop=loop=-1:size=2e+09,volume={bgm_volume_factor}[bgm]"
            filter_complex = f"{bgm_filter};[0:a][bgm]amix=inputs=2:duration=first[aout]"
            ffmpeg_cmd += [
                "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac",
                "-filter_complex", filter_complex,
                "-map", "0:v", "-map", "[aout]",
                "-shortest"
            ]
            if logger:
                logger.info(f"🔧 Background music overlay mode (start_delay: {start_delay}s, bgm_volume: {bgm_volume_factor})")
        elif reencode:
            ffmpeg_cmd += [
                "-c:v", "libx264", "-preset", "ultrafast",
                "-c:a", "aac"
            ]
            if logger:
                logger.info("🔧 Re-encode mode (no background music)")
        else:
            ffmpeg_cmd += ["-c", "copy"]
            if logger:
                logger.info("🔧 Stream copy mode (fastest)")
        ffmpeg_cmd.append(output_path)
        if logger:
            logger.info(f"🔧 FFmpeg command: {' '.join(ffmpeg_cmd)}")
            logger.info("⏰ Starting ffmpeg execution...")
        start_time = time.time()
        result = subprocess.run(
            ffmpeg_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
            timeout=300
        )
        execution_time = time.time() - start_time
        if logger:
            logger.info(f"✅ FFmpeg completed successfully in {execution_time:.2f}s")
            logger.info(f"📋 FFmpeg return code: {result.returncode}")
            if result.stdout and result.stdout.strip():
                logger.debug(f"📄 FFmpeg stdout: {result.stdout.strip()}")
            if result.stderr and result.stderr.strip():
                logger.debug(f"📄 FFmpeg stderr: {result.stderr.strip()}")
            if os.path.exists(output_path):
                output_size = os.path.getsize(output_path)
                logger.info(f"📤 Output file: {output_path} ({output_size//1024//1024} MB)")
            else:
                logger.warning(f"⚠️ Output file not found after completion: {output_path}")
                logger.error(f"❌ Expected output: {output_path}")
                logger.error(f"❌ Working directory: {os.getcwd()}")
                if result.stderr:
                    logger.error(f"❌ FFmpeg stderr: {result.stderr}")
    except subprocess.TimeoutExpired as e:
        error_msg = f"FFmpeg timeout (>5 minutes): {' '.join(ffmpeg_cmd)}"
        if logger:
            logger.error(f"❌ {error_msg}")
        raise RuntimeError(error_msg)
    except subprocess.CalledProcessError as e:
        error_msg = f"FFmpeg failed (code {e.returncode}): {e.stderr}"
        if logger:
            logger.error(f"❌ {error_msg}")
            logger.error(f"❌ Command: {' '.join(ffmpeg_cmd)}")
        raise RuntimeError(error_msg)
    except Exception as e:
        if logger:
            logger.error(f"💥 Unexpected error in ffmpeg_concat_videos: {e}")
        raise
    finally:
        if filelist_path and os.path.exists(filelist_path):
            try:
                os.remove(filelist_path)
                if logger:
                    logger.info(f"🗑️ Cleaned up temp file: {filelist_path}")
            except Exception as cleanup_error:
                if logger:
                    logger.warning(f"⚠️ Failed to cleanup {filelist_path}: {cleanup_error}")
