"""
Video processing service for creating video clips from segments
"""

import os
import uuid
import logging
import subprocess
from typing import List, Dict, Optional, Any
from app.core.exceptions import VideoCreationError
from app.services.config.video_config import video_config
from app.services.resource_manager import ResourceManager
from utils.subprocess_utils import safe_subprocess_run, SubprocessError

logger = logging.getLogger(__name__)


class VideoProcessingService:
    """Service for processing video clips from segments"""

    def __init__(self, resource_manager: Optional[ResourceManager] = None):
        self.resource_manager = resource_manager or ResourceManager()

    def _create_audio_composition(
        self, segment: Dict, temp_dir: str
    ) -> Optional[str]:
        """
        Tạo file audio đã trộn từ các asset audio (voice over) bằng ffmpeg filter_complex.
        Trả về đường dẫn file audio tạm, hoặc None nếu không có voice over.
        """
        id = segment.get("id", str(uuid.uuid4()))
        voice_over = segment.get("voice_over", {})
        voice_over_path = voice_over.get("local_path")
        vo_start_delay = float(voice_over.get("start_delay", 0))
        vo_end_delay = float(voice_over.get("end_delay", 0))

        if not voice_over_path:
            return None

        # 🔍 DEBUG: Log độ dài audio input gốc
        try:
            from utils.video_utils import VideoProcessingError
            def get_duration(path):
                import json
                cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path]
                result = safe_subprocess_run(cmd, f"Get duration for {path}", logger)
                info = json.loads(result.stdout)
                return float(info["format"]["duration"])
            
            original_duration = get_duration(voice_over_path)
            logger.info(f"🎵 ORIGINAL audio duration for segment '{id}': {original_duration:.3f}s")
            logger.info(f"🎵 Audio delays - start: {vo_start_delay}s, end: {vo_end_delay}s")
        except Exception as e:
            logger.warning(f"Could not get original audio duration: {e}")
            original_duration = 0

        filter_inputs = [f"-i {voice_over_path}"]
        filter_complex = []
        amix_inputs = []
        idx = 0

        # Voice over: adelay đầu, apad cuối, normalize loudness
        vo_filters = []
        if vo_start_delay > 0:
            delay_ms = int(vo_start_delay * 1000)
            vo_filters.append(f"adelay={delay_ms}|{delay_ms}")
            logger.info(f"🔧 Adding start delay: {delay_ms}ms")
        
        # 🔧 FIXED: Sử dụng loudnorm với target âm lượng cao hơn + volume boost để có âm thanh đủ to
        vo_filters.append("loudnorm=I=-8:TP=-0.5:LRA=5")  # Target rất cao: -8dB để âm thanh to hơn
        vo_filters.append("volume=2.0")  # Boost thêm 6dB (x2) sau khi normalize
        logger.info(f"🔧 Using aggressive loudnorm (I=-8dB) + volume boost (2.0x) for better audio volume")
        
        if vo_end_delay > 0:
            vo_filters.append(f"apad=pad_dur={vo_end_delay}")
            logger.info(f"🔧 Adding end delay: {vo_end_delay}s")
        vo_chain = ",".join(vo_filters) if vo_filters else "anull"
        filter_complex.append(f"[{idx}:a]{vo_chain}[vo]")
        amix_inputs.append("[vo]")

        # 🔧 FIX: Thay duration=longest bằng duration=first để tránh silence thừa
        filter_complex.append(f"{''.join(amix_inputs)}amix=inputs=1:duration=first[aout]")

        # Output file
        out_audio = os.path.join(temp_dir, f"audio_{id}.wav")
        ffmpeg_cmd = ["ffmpeg", "-y"]
        for inp in filter_inputs:
            ffmpeg_cmd += inp.split()
        ffmpeg_cmd += [
            "-filter_complex", ";".join(filter_complex),
            "-map", "[aout]", "-ac", "2", "-ar", "44100", out_audio
        ]
        
        logger.info(f"🔧 Audio filter chain: {';'.join(filter_complex)}")
        safe_subprocess_run(ffmpeg_cmd, f"Audio composition for segment {id}", logger)
        
        # 🔍 DEBUG: Log độ dài audio output sau xử lý
        try:
            def get_duration_local(path):
                import json
                cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path]
                result = safe_subprocess_run(cmd, f"Get duration for {path}", logger)
                info = json.loads(result.stdout)
                return float(info["format"]["duration"])
            
            final_duration = get_duration_local(out_audio)
            duration_diff = final_duration - original_duration
            logger.info(f"🎵 PROCESSED audio duration for segment '{id}': {final_duration:.3f}s")
            logger.info(f"🎵 Duration difference: {duration_diff:+.3f}s")
            if abs(duration_diff) > 0.1:  # Nếu chênh lệch > 100ms
                logger.warning(f"⚠️ Significant duration change detected! Original: {original_duration:.3f}s → Final: {final_duration:.3f}s")
        except Exception as e:
            logger.warning(f"Could not get processed audio duration: {e}")
        
        return out_audio

    def create_segment_clip(self, segment: Dict, temp_dir: str) -> str:
        """Create a video clip from a processed segment (asset object format) using ffmpeg CLI only (always with audio)"""
        try:
            # Validate background image
            image_obj = segment.get("image", {})
            bg_image_path = image_obj.get("local_path")
            if not bg_image_path or not os.path.exists(bg_image_path):
                raise VideoCreationError("Background image not found for segment")

            # Process image with padding for consistent size
            from utils.image_utils import process_image

            processed_image_paths = process_image(
                image_paths=bg_image_path,
                target_size=(1920, 1080),  # Standard HD size
                smart_pad_color=True,  # Enable smart padding color detection
                pad_color_method="average_edge",  # Use average edge method
                auto_enhance=True,  # Enable auto image enhancement
                enhance_brightness=True,  # Auto brightness adjustment
                enhance_contrast=True,  # Auto contrast enhancement
                enhance_saturation=True,  # Auto saturation optimization
                output_dir=temp_dir,
            )

            if not processed_image_paths:
                raise VideoCreationError("Failed to process background image")

            processed_bg_path = processed_image_paths[0]

            # Prepare audio (ffmpeg-based)
            audio_path = self._create_audio_composition(segment, temp_dir)
            if not audio_path:
                raise VideoCreationError("Audio composition failed or missing for segment")

            # Prepare output path
            segment_id = segment.get("id", str(uuid.uuid4()))
            segment_output_path = os.path.join(
                temp_dir, f"temp_segment_{segment_id}.mp4"
            )

            # Prepare ffmpeg command (no need for -t, just use -shortest)
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", processed_bg_path,
                "-i", audio_path,
                "-vf", "scale=1920:1080,format=yuv420p",
                "-af", "volume=1.5",  # 🔧 Tăng thêm 50% âm lượng ở bước cuối
                "-pix_fmt", "yuv420p",
                "-r", str(video_config.default_fps),
                "-shortest",
                "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k", segment_output_path
            ]

            safe_subprocess_run(ffmpeg_cmd, f"Create segment clip {segment_id}", logger)
            logger.info(f"Created segment with ffmpeg: {segment_output_path}")
            return segment_output_path

        except SubprocessError as e:
            # Convert SubprocessError to VideoCreationError for service layer
            raise VideoCreationError(str(e)) from e
        except Exception as e:
            logger.error(f"Failed to create segment clip: {e}", exc_info=True)
            raise VideoCreationError(f"Failed to create segment clip: {e}") from e

    def create_multiple_segment_clips(
        self, segments: List[Dict], temp_dir: str
    ) -> List[Dict[str, str]]:
        """Create multiple segment clips and return list of dicts with id and file path (for transition pipeline)"""
        clip_infos = []
        for i, segment in enumerate(segments):
            try:
                clip_path = self.create_segment_clip(segment, temp_dir)
                clip_infos.append({"id": segment.get("id", str(i)), "path": clip_path})
                logger.info(
                    f"✅ Created segment {i+1}/{len(segments)}: {clip_path}"
                )
            except Exception as e:
                logger.error(f"❌ Failed to create segment {i+1}: {e}")
                raise
        return clip_infos

    def concatenate_clips(
        self, video_segments: List[Dict[str, str]],
        output_path: str,
        temp_dir: str,
        transitions: Optional[list] = None,
        background_music: Optional[dict] = None,
        default_transition_type: str = "fade",
        default_transition_duration: float = 1.0,
    ) -> Any:
        """Concatenate video clips using ffmpeg, supporting per-pair transitions from metadata."""
        from utils.video_utils import ffmpeg_concat_videos
        import psutil
        try:
            if not video_segments:
                raise VideoCreationError("No video segments provided for concatenation")
            memory = psutil.virtual_memory()
            logger.info(
                f"Memory usage before concatenation: {memory.percent:.1f}% ({memory.used // 1024 // 1024} MB used)"
            )
            ffmpeg_concat_videos(
                video_segments=video_segments,
                output_path=output_path,
                temp_dir=temp_dir,
                transitions=transitions,
                background_music=background_music,
                logger=logger,
                default_transition_type=default_transition_type,
                default_transition_duration=default_transition_duration,
            )
            logger.info(f"ffmpeg concat output: {output_path}")
            memory_after = psutil.virtual_memory()
            logger.info(
                f"Memory usage after concatenation: {memory_after.percent:.1f}% ({memory_after.used // 1024 // 1024} MB used)"
            )
            return output_path
        except Exception as e:
            logger.error(f"Failed to concatenate clips: {e}", exc_info=True)
            raise VideoCreationError(f"Failed to concatenate clips: {e}") from e
