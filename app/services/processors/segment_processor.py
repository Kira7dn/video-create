import os
import uuid
import subprocess
from typing import Dict, Optional
from app.core.exceptions import VideoCreationError
from app.config.settings import settings
from app.services.processors.audio_processor import AudioProcessor
from app.services.processors.text_overlay_processor import TextOverlayProcessor
from app.services.processors.transition_processor import TransitionProcessor
from utils.subprocess_utils import safe_subprocess_run, SubprocessError
import logging

logger = logging.getLogger(__name__)

class SegmentProcessor:
    """Handles creation of a single video segment clip from a segment dict"""
    @staticmethod
    def create_segment_clip(segment: Dict, temp_dir: str) -> str:
        image_obj = segment.get("image", {})
        video_obj = segment.get("video", {})
        bg_image_path = image_obj.get("local_path")
        video_path = video_obj.get("local_path")
        
        transition_in = segment.get("transition_in", {})
        transition_out = segment.get("transition_out", {})
        segment_id = segment.get("id", str(uuid.uuid4()))
        voice_over = segment.get("voice_over", {})
        segment_output_path = os.path.join(temp_dir, f"temp_segment_{segment_id}.mp4")

        if video_path and os.path.exists(video_path):
            input_type = "video"
            input_path = video_path
            try:
                probe_cmd = [
                    "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                    "-of", "csv=p=0", video_path
                ]
                result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
                original_duration = float(result.stdout.strip())
            except Exception as e:
                logger.warning(f"Could not get video duration for segment {segment_id}: {e}")
                original_duration = 4.0
            audio_input_path = video_path
        else:
            input_type = "image"
            if not bg_image_path or not os.path.exists(bg_image_path):
                raise VideoCreationError("Background image not found for segment")
            from utils.image_utils import process_image
            processed_image_paths = process_image(
                image_paths=bg_image_path,
                target_size=(1920, 1080),
                smart_pad_color=True,
                pad_color_method="average_edge",
                auto_enhance=True,
                enhance_brightness=True,
                enhance_contrast=True,
                enhance_saturation=True,
                output_dir=temp_dir,
            )
            if not processed_image_paths:
                raise VideoCreationError("Failed to process background image")
            input_path = processed_image_paths[0]
            audio_path = AudioProcessor.create_audio_composition(segment, temp_dir)
            if not audio_path:
                raise VideoCreationError("Audio composition failed or missing for segment")
            try:
                probe_cmd = [
                    "ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                    "-of", "csv=p=0", audio_path
                ]
                result = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
                original_duration = float(result.stdout.strip())
            except Exception as e:
                logger.warning(f"Could not get audio duration for segment {segment_id}: {e}")
                original_duration = 4.0
            fade_in_duration = float(transition_in.get("duration", 0) or 0)
            fade_out_duration = float(transition_out.get("duration", 0) or 0)
            extended_audio_path = audio_path
            if fade_in_duration > 0 or fade_out_duration > 0:
                extended_audio_path = os.path.join(temp_dir, f"extended_audio_{segment_id}.wav")
                audio_inputs = []
                if fade_in_duration > 0:
                    audio_inputs.append(f"-f lavfi -t {fade_in_duration} -i anullsrc=channel_layout=stereo:sample_rate=44100")
                audio_inputs.append(f"-i {audio_path}")
                if fade_out_duration > 0:
                    audio_inputs.append(f"-f lavfi -t {fade_out_duration} -i anullsrc=channel_layout=stereo:sample_rate=44100")
                if fade_in_duration > 0 and fade_out_duration > 0:
                    filter_str = "[0:a][1:a][2:a]concat=n=3:v=0:a=1[aout]"
                elif fade_in_duration > 0 or fade_out_duration > 0:
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
            audio_input_path = extended_audio_path

        video_filters = ["scale=1920:1080", "format=yuv420p"]
        audio_filters = ["volume=1.5"]
        fade_in_duration = float(transition_in.get("duration", 0) or 0)
        fade_out_duration = float(transition_out.get("duration", 0) or 0)
        fade_in_type = transition_in.get("type", "fade").lower() if transition_in.get("type") else "fade"
        fade_out_type = transition_out.get("type", "fade").lower() if transition_out.get("type") else "fade"
        if fade_in_duration > 0:
            if TransitionProcessor.is_preprocessing_supported(fade_in_type):
                TransitionProcessor.apply_transition_in_filter(video_filters, audio_filters, fade_in_type, fade_in_duration)
                logger.debug(f"Applied {fade_in_type} transition-in: {fade_in_duration}s ({'overlay' if input_type == 'video' else 'additive'})")
            else:
                logger.warning(f"Transition-in type '{fade_in_type}' not supported for preprocessing, using basic fade")
                fade_in_type = "fade"
                video_filters.append(f"fade=t=in:st=0:d={fade_in_duration}")
                audio_filters.append(f"afade=t=in:st=0:d={fade_in_duration}")
        if fade_out_duration > 0:
            fade_out_start = max(0, original_duration - fade_out_duration) if input_type == "video" else fade_in_duration + original_duration
            if TransitionProcessor.is_preprocessing_supported(fade_out_type):
                TransitionProcessor.apply_transition_out_filter(video_filters, audio_filters, fade_out_type, fade_out_duration, fade_out_start)
                logger.debug(f"Applied {fade_out_type} transition-out: {fade_out_duration}s starting at {fade_out_start}s ({'overlay' if input_type == 'video' else 'additive'})")
            else:
                logger.warning(f"Transition-out type '{fade_out_type}' not supported for preprocessing, using basic fade")
                fade_out_type = "fade"
                video_filters.append(f"fade=t=out:st={fade_out_start}:d={fade_out_duration}")
                audio_filters.append(f"afade=t=out:st={fade_out_start}:d={fade_out_duration}")
        
        # Calculate total duration
        total_duration = original_duration if input_type == "video" else fade_in_duration + original_duration + fade_out_duration
        # Calculate delay
        delay = fade_in_duration + voice_over.get("start_delay", 0)
        # Handle text overlays - build them separately to avoid conflicts
        text_overs = segment.get("text_over")
        if text_overs:
            if not isinstance(text_overs, list):
                raise VideoCreationError("text_over must be an array of objects")
            
            # Add text filters directly to video filters
            for text_over in text_overs:
                drawtext_filter = TextOverlayProcessor.build_drawtext_filter(text_over, total_duration, delay)
                if drawtext_filter:
                    video_filters.append(drawtext_filter)
        
        # Build FFmpeg command based on input type
        if input_type == "video":
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-i", input_path,
                "-vf", ",".join(video_filters),
                "-af", ",".join(audio_filters),
                "-t", str(total_duration),
                "-map", "1:v", "-map", "0:a",
                "-pix_fmt", "yuv420p",
                "-r", str(settings.video_default_fps),
                "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k", segment_output_path
            ]
        else:
            ffmpeg_cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", input_path,
                "-i", audio_input_path,
                "-vf", ",".join(video_filters),
                "-af", ",".join(audio_filters),
                "-t", str(total_duration),
                "-pix_fmt", "yuv420p",
                "-r", str(settings.video_default_fps),
                "-c:v", "libx264", "-c:a", "aac", "-b:a", "192k", segment_output_path
            ]
        safe_subprocess_run(ffmpeg_cmd, f"Create segment clip {segment_id}", logger)
        return segment_output_path
