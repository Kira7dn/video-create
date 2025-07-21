import logging

from app.services.processors.core.base_processor import AsyncProcessor

logger = logging.getLogger(__name__)


class VideoProcessor(AsyncProcessor):
    """Handles transition filter logic for video and audio"""

    @staticmethod
    def is_preprocessing_supported(transition_type: str) -> bool:
        preprocessing_supported = {
            "fade",
            "fadeblack",
            "fadewhite",  # Fade family - fully working
            "cut",  # No-op for cut transitions
        }
        return transition_type.lower() in preprocessing_supported

    @staticmethod
    def apply_transition_in_filter(
        video_filters: list, audio_filters: list, transition_type: str, duration: float
    ) -> None:
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
            pass

    @staticmethod
    def apply_transition_out_filter(
        video_filters: list,
        audio_filters: list,
        transition_type: str,
        duration: float,
        start_time: float,
    ) -> None:
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
            pass
