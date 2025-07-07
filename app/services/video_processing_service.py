"""
Video processing service for creating video clips from segments
"""

import os
import uuid
import logging
import subprocess
import json
from typing import List, Dict, Optional, Any
from app.core.exceptions import VideoCreationError
from app.services.config.video_config import video_config
from app.services.resource_manager import ResourceManager
from utils.subprocess_utils import safe_subprocess_run, SubprocessError
from utils.video_utils import ffmpeg_concat_videos

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

        filter_inputs = [f"-i {voice_over_path}"]
        filter_complex = []
        amix_inputs = []
        idx = 0

        # Voice over: adelay đầu, apad cuối, normalize loudness
        vo_filters = []
        if vo_start_delay > 0:
            delay_ms = int(vo_start_delay * 1000)
            vo_filters.append(f"adelay={delay_ms}|{delay_ms}")
        
        # Sử dụng loudnorm với target âm lượng cao hơn + volume boost
        vo_filters.append("loudnorm=I=-8:TP=-0.5:LRA=5")
        vo_filters.append("volume=2.0")
        
        if vo_end_delay > 0:
            vo_filters.append(f"apad=pad_dur={vo_end_delay}")
        vo_chain = ",".join(vo_filters) if vo_filters else "anull"
        filter_complex.append(f"[{idx}:a]{vo_chain}[vo]")
        amix_inputs.append("[vo]")

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
        
        safe_subprocess_run(ffmpeg_cmd, f"Audio composition for segment {id}", logger)
        
        return out_audio

    def create_segment_clip(self, segment: Dict, temp_dir: str) -> str:
        """Create a video clip from a processed segment (asset object format) using ffmpeg CLI only (always with audio)"""
        try:
            # Validate background image
            image_obj = segment.get("image", {})
            bg_image_path = image_obj.get("local_path")
            
            # Extract transition info for fade preprocessing with support for multiple effect types
            transition_in = segment.get("transition_in", {})
            transition_out = segment.get("transition_out", {})
            
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

            # Build filter chains for transitions with ADDITIVE approach
            video_filters = ["scale=1920:1080", "format=yuv420p"]
            audio_filters = ["volume=1.5"]
            
            # Calculate extended duration for additive fade approach
            fade_in_duration = 0.0
            fade_out_duration = 0.0
            fade_in_type = "fade"
            fade_out_type = "fade"
            
            # Apply transition-in effects (extends at beginning)
            if transition_in.get("type") and transition_in.get("duration", 0) > 0:
                fade_in_duration = float(transition_in["duration"])
                fade_in_type = transition_in.get("type", "fade").lower()
                
                # Check if this transition type can be preprocessed
                if self._is_preprocessing_supported(fade_in_type):
                    self._apply_transition_in_filter(video_filters, audio_filters, fade_in_type, fade_in_duration)
                    logger.debug(f"Applied {fade_in_type} transition-in: {fade_in_duration}s (additive)")
                else:
                    logger.warning(f"Transition-in type '{fade_in_type}' not supported for preprocessing, using basic fade")
                    fade_in_type = "fade"
                    video_filters.append(f"fade=t=in:st=0:d={fade_in_duration}")
                    audio_filters.append(f"afade=t=in:st=0:d={fade_in_duration}")
            
            # Get original audio duration
            original_audio_duration = 0.0
            try:
                probe_cmd = [
                    "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                    "-of", "csv=p=0", audio_path
                ]
                result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
                original_audio_duration = float(result.stdout.strip())
                logger.debug(f"Original audio duration: {original_audio_duration}s")
            except (ValueError, AttributeError, subprocess.CalledProcessError) as e:
                logger.warning(f"Could not get audio duration for segment {segment_id}: {e}")
                original_audio_duration = 4.0  # Fallback
            
            # Apply transition-out effects (extends at end)
            if transition_out.get("type") and transition_out.get("duration", 0) > 0:
                fade_out_duration = float(transition_out["duration"])
                fade_out_type = transition_out.get("type", "fade").lower()
                
                # Check if this transition type can be preprocessed
                if self._is_preprocessing_supported(fade_out_type):
                    # Calculate fade-out start time for additive approach
                    fade_out_start = fade_in_duration + original_audio_duration
                    self._apply_transition_out_filter(video_filters, audio_filters, fade_out_type, fade_out_duration, fade_out_start)
                    logger.debug(f"Applied {fade_out_type} transition-out: {fade_out_duration}s starting at {fade_out_start}s (additive)")
                else:
                    logger.warning(f"Transition-out type '{fade_out_type}' not supported for preprocessing, using basic fade")
                    fade_out_type = "fade"
                    fade_out_start = fade_in_duration + original_audio_duration
                    video_filters.append(f"fade=t=out:st={fade_out_start}:d={fade_out_duration}")
                    audio_filters.append(f"afade=t=out:st={fade_out_start}:d={fade_out_duration}")
            
            # Calculate total extended duration
            total_duration = fade_in_duration + original_audio_duration + fade_out_duration
            logger.info(f"Segment {segment_id} - Original: {original_audio_duration}s, With fades: {total_duration}s")
            
            # Log voice timing for clarity
            voice_over = segment.get("voice_over", {})
            vo_start_delay = float(voice_over.get("start_delay", 0))
            actual_voice_start_time = fade_in_duration + vo_start_delay
            logger.debug(f"Voice timing - Fade-in: {fade_in_duration}s, VO delay: {vo_start_delay}s, "
                        f"Actual voice start: {actual_voice_start_time}s")
            
            # Create extended audio track for additive fades
            extended_audio_path = audio_path
            if fade_in_duration > 0 or fade_out_duration > 0:
                extended_audio_path = os.path.join(temp_dir, f"extended_audio_{segment_id}.wav")
                
                # Build audio extension command
                audio_inputs = []
                audio_filters = []
                
                # Add silence at beginning for fade-in
                if fade_in_duration > 0:
                    audio_inputs.append(f"-f lavfi -t {fade_in_duration} -i anullsrc=channel_layout=stereo:sample_rate=44100")
                
                # Add original audio
                audio_inputs.append(f"-i {audio_path}")
                
                # Add silence at end for fade-out
                if fade_out_duration > 0:
                    audio_inputs.append(f"-f lavfi -t {fade_out_duration} -i anullsrc=channel_layout=stereo:sample_rate=44100")
                
                # Concatenate all audio parts
                if fade_in_duration > 0 and fade_out_duration > 0:
                    filter_str = "[0:a][1:a][2:a]concat=n=3:v=0:a=1[aout]"
                elif fade_in_duration > 0:
                    filter_str = "[0:a][1:a]concat=n=2:v=0:a=1[aout]"
                elif fade_out_duration > 0:
                    filter_str = "[0:a][1:a]concat=n=2:v=0:a=1[aout]"
                else:
                    filter_str = "[0:a]acopy[aout]"
                
                extend_cmd = ["ffmpeg", "-y"]
                for inp in audio_inputs:
                    extend_cmd += inp.split()
                extend_cmd += [
                    "-filter_complex", filter_str,
                    "-map", "[aout]", "-ac", "2", "-ar", "44100", extended_audio_path
                ]
                
                safe_subprocess_run(extend_cmd, f"Create extended audio for segment {segment_id}", logger)
            
            # Prepare ffmpeg command with extended audio for additive fades
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", processed_bg_path,
                "-i", extended_audio_path,
                "-vf", ",".join(video_filters),
                "-af", "volume=1.5",  # Simple volume adjustment for extended audio
                "-t", str(total_duration),
                "-pix_fmt", "yuv420p",
                "-r", str(video_config.default_fps),
                "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k", segment_output_path
            ]

            safe_subprocess_run(ffmpeg_cmd, f"Create segment clip {segment_id}", logger)
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
        total_segments = len(segments)
        for i, segment in enumerate(segments):
            try:
                clip_path = self.create_segment_clip(segment, temp_dir)
                clip_infos.append({"id": segment.get("id", str(i)), "path": clip_path})
                # Log progress every 20% for better performance
                if (i + 1) % max(1, total_segments // 5) == 0 or i == total_segments - 1:
                    logger.info(f"✅ Created segments {i+1}/{total_segments}")
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
        try:
            if not video_segments:
                raise VideoCreationError("No video segments provided for concatenation")
            
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
            logger.info(f"Video concatenation completed: {output_path}")
            
            return output_path
        except Exception as e:
            logger.error(f"Failed to concatenate clips: {e}", exc_info=True)
            raise VideoCreationError(f"Failed to concatenate clips: {e}") from e

    def _is_preprocessing_supported(self, transition_type: str) -> bool:
        """Check if transition type can be preprocessed at segment level"""
        preprocessing_supported = {
            "fade", "fadeblack", "fadewhite",  # Fade family - fully working
            "cut"                              # No-op for cut transitions
        }
        return transition_type.lower() in preprocessing_supported
    
    def _apply_transition_in_filter(self, video_filters: list, audio_filters: list, 
                                   transition_type: str, duration: float) -> None:
        """Apply transition-in filter based on type"""
        if transition_type == "fade":
            video_filters.append(f"fade=t=in:st=0:d={duration}")
            audio_filters.append(f"afade=t=in:st=0:d={duration}")
        elif transition_type == "fadeblack":
            video_filters.append(f"fade=t=in:st=0:d={duration}:c=black")
            audio_filters.append(f"afade=t=in:st=0:d={duration}")
        elif transition_type == "fadewhite":
            video_filters.append(f"fade=t=in:st=0:d={duration}:c=white")
            audio_filters.append(f"afade=t=in:st=0:d={duration}")
        elif transition_type == "cut":
            # Cut transition - no effects needed
            pass
    
    def _apply_transition_out_filter(self, video_filters: list, audio_filters: list,
                                    transition_type: str, duration: float, start_time: float) -> None:
        """Apply transition-out filter based on type"""
        if transition_type == "fade":
            video_filters.append(f"fade=t=out:st={start_time}:d={duration}")
            audio_filters.append(f"afade=t=out:st={start_time}:d={duration}")
        elif transition_type == "fadeblack":
            video_filters.append(f"fade=t=out:st={start_time}:d={duration}:c=black")
            audio_filters.append(f"afade=t=out:st={start_time}:d={duration}")
        elif transition_type == "fadewhite":
            video_filters.append(f"fade=t=out:st={start_time}:d={duration}:c=white")
            audio_filters.append(f"afade=t=out:st={start_time}:d={duration}")
        elif transition_type == "cut":
            # Cut transition - no effects needed
            pass
