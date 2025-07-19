"""Audio processing module for handling voice over composition and normalization."""

import logging
import os
import uuid
from typing import Dict, Optional

from app.interfaces import IAudioProcessor
from utils.subprocess_utils import safe_subprocess_run

logger = logging.getLogger(__name__)


class AudioProcessor(IAudioProcessor):
    """Handles audio composition for segments (voice over, delays, normalization)"""

    @staticmethod
    def create_audio_composition(segment: Dict, temp_dir: str) -> Optional[str]:
        """Create audio composition for a segment with voice over, delays, and normalization.

        Args:
            segment: Dictionary containing segment data with voice_over configuration
            temp_dir: Temporary directory path for output files

        Returns:
            Optional[str]: Path to the generated audio file, or None if no voice over
        """
        segment_id = segment.get("id", str(uuid.uuid4()))
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

        vo_filters = []
        if vo_start_delay > 0:
            delay_ms = int(vo_start_delay * 1000)
            vo_filters.append(f"adelay={delay_ms}|{delay_ms}")
        vo_filters.append("loudnorm=I=-8:TP=-0.5:LRA=5")
        vo_filters.append("volume=2.0")
        if vo_end_delay > 0:
            vo_filters.append(f"apad=pad_dur={vo_end_delay}")
        vo_chain = ",".join(vo_filters) if vo_filters else "anull"
        filter_complex.append(f"[{idx}:a]{vo_chain}[vo]")
        amix_inputs.append("[vo]")
        filter_complex.append(
            f"{''.join(amix_inputs)}amix=inputs=1:duration=first[aout]"
        )

        out_audio = os.path.join(temp_dir, f"audio_{segment_id}.wav")
        ffmpeg_cmd = ["ffmpeg", "-y"]
        for inp in filter_inputs:
            ffmpeg_cmd += inp.split()
        ffmpeg_cmd += [
            "-filter_complex",
            ";".join(filter_complex),
            "-map",
            "[aout]",
            "-ac",
            "2",
            "-ar",
            "44100",
            out_audio,
        ]
        safe_subprocess_run(
            ffmpeg_cmd, f"Audio composition for segment {segment_id}", logger
        )
        return out_audio
