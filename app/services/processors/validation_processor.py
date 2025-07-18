"""
Validation processor for video creation requests
"""

import logging
from typing import Dict, List, Any, Optional

from app.services.processors.base_processor import (
    Validator,
    ValidationResult,
    ProcessingStage,
    MetricsCollector,
)

logger = logging.getLogger(__name__)


class VideoRequestValidator(Validator):
    """Validates video creation requests"""

    def __init__(self, metrics_collector: Optional[MetricsCollector] = None):
        super().__init__(metrics_collector)
        self.required_segment_fields = ["id"]
        self.optional_segment_fields = [
            "image",
            "video",
            "voice_over",
            "background_music",
            "text_overlay",
            "transition_in",
            "transition_out",
            "duration",
        ]
        self.supported_asset_types = [
            "image",
            "video",
            "voice_over",
            "background_music",
        ]
        self.supported_transition_types = ["fade", "fadeblack", "fadewhite", "cut"]

    def validate(self, data: Dict[str, Any]) -> ValidationResult:
        """Validate video creation request data"""
        result = ValidationResult()
        metric = self._start_processing(ProcessingStage.VALIDATION)

        try:
            # Basic structure validation
            self._validate_basic_structure(data, result)

            if result.is_valid:
                # Validate segments
                segments = data.get("segments", [])
                self._validate_segments(segments, result)

                # Validate global settings
                self._validate_global_settings(data, result)

                # Validate transitions
                if "transitions" in data:
                    self._validate_transitions(data["transitions"], result)

            return result

        except (ValueError, KeyError, TypeError) as e:
            # Catch specific exceptions that might occur during validation
            error_msg = f"Validation error: {str(e)}"
            result.add_error(error_msg)
            return result

        except Exception as e:  # noqa: BLE001
            # Catch any other unexpected errors
            error_msg = f"Unexpected error during validation: {str(e)}"
            raise RuntimeError(error_msg) from e

        finally:
            # Always end the processing metric
            self._end_processing(
                metric,
                success=result.is_valid,
                error_message="; ".join(result.errors) if result.errors else None,
                items_processed=len(data.get("segments", [])),
            )

    def _validate_basic_structure(self, data: Dict[str, Any], result: ValidationResult):
        """Validate basic request structure"""
        if not isinstance(data, dict):
            result.add_error("Request data must be a dictionary")
            return

        if "segments" not in data:
            result.add_error("Missing required 'segments' field")
            return

        segments = data["segments"]
        if not isinstance(segments, list):
            result.add_error("'segments' must be a list")
            return

        if not segments:
            result.add_error("'segments' cannot be empty")
            return

    def _validate_segments(self, segments: List[Dict], result: ValidationResult):
        """Validate segment structure and content"""
        for i, segment in enumerate(segments):
            if not isinstance(segment, dict):
                result.add_error(f"Segment {i} must be a dictionary")
                continue

            # Check required fields
            for field in self.required_segment_fields:
                if field not in segment:
                    result.add_error(f"Segment {i} missing required field '{field}'")

            # Validate segment ID
            if "id" in segment:
                if not isinstance(segment["id"], (str, int)):
                    result.add_error(f"Segment {i} 'id' must be a string or integer")

            # Validate assets
            self._validate_segment_assets(segment, i, result)

            # Validate text overlay
            if "text_overlay" in segment:
                self._validate_text_overlay(segment["text_overlay"], i, result)

            # Validate transitions
            if "transition_in" in segment:
                self._validate_transition(
                    segment["transition_in"], f"segment {i} transition_in", result
                )

            if "transition_out" in segment:
                self._validate_transition(
                    segment["transition_out"], f"segment {i} transition_out", result
                )

    def _validate_segment_assets(
        self, segment: Dict, segment_index: int, result: ValidationResult
    ):
        """Validate assets in a segment"""
        has_media = False

        for asset_type in self.supported_asset_types:
            if asset_type in segment:
                asset = segment[asset_type]
                if not isinstance(asset, dict):
                    result.add_error(
                        f"Segment {segment_index} '{asset_type}' must be a dictionary"
                    )
                    continue

                # Check for URL or local_path
                if "url" not in asset and "local_path" not in asset:
                    result.add_error(
                        f"Segment {segment_index} '{asset_type}' must have 'url' or 'local_path'"
                    )

                # Mark that we have media content
                if asset_type in ["image", "video"]:
                    has_media = True

        # Each segment must have at least one media asset (image or video)
        if not has_media:
            result.add_error(
                f"Segment {segment_index} must have at least one media asset (image or video)"
            )

    def _validate_text_overlay(
        self, text_overlay: Any, segment_index: int, result: ValidationResult
    ):
        """Validate text overlay configuration"""
        if isinstance(text_overlay, dict):
            # Single text overlay
            text_overlays = [text_overlay]
        elif isinstance(text_overlay, list):
            # Multiple text overlays
            text_overlays = text_overlay
        else:
            result.add_error(
                f"Segment {segment_index} 'text_overlay' must be a dict or list"
            )
            return

        for i, overlay in enumerate(text_overlays):
            if not isinstance(overlay, dict):
                result.add_error(
                    f"Segment {segment_index} text_overlay {i} must be a dictionary"
                )
                continue

            if "text" not in overlay:
                result.add_error(
                    f"Segment {segment_index} text_overlay {i} missing required 'text' field"
                )

            # Validate timing
            if "start_time" in overlay:
                if (
                    not isinstance(overlay["start_time"], (int, float))
                    or overlay["start_time"] < 0
                ):
                    result.add_error(
                        f"Segment {segment_index} text_overlay {i}"
                        " 'start_time' must be non-negative number"
                    )

            if "end_time" in overlay:
                if (
                    not isinstance(overlay["end_time"], (int, float))
                    or overlay["end_time"] < 0
                ):
                    result.add_error(
                        f"Segment {segment_index} text_overlay {i}"
                        " 'end_time' must be non-negative number"
                    )

            # Validate start_time < end_time
            if "start_time" in overlay and "end_time" in overlay:
                if overlay["start_time"] >= overlay["end_time"]:
                    result.add_error(
                        f"Segment {segment_index} text_overlay"
                        "{i} 'start_time' must be less than 'end_time'"
                    )

    def _validate_transition(
        self, transition: Dict, location: str, result: ValidationResult
    ):
        """Validate transition configuration"""
        if not isinstance(transition, dict):
            result.add_error(f"{location} must be a dictionary")
            return

        if "type" in transition:
            if transition["type"] not in self.supported_transition_types:
                result.add_error(
                    f"{location} type '{transition['type']}' not supported. "
                    f"Supported types: {', '.join(self.supported_transition_types)}"
                )

        if "duration" in transition:
            if (
                not isinstance(transition["duration"], (int, float))
                or transition["duration"] <= 0
            ):
                result.add_error(f"{location} 'duration' must be a positive number")

    def _validate_global_settings(self, data: Dict[str, Any], result: ValidationResult):
        """Validate global settings"""
        if "background_music" in data:
            bg_music = data["background_music"]
            if not isinstance(bg_music, dict):
                result.add_error("Global 'background_music' must be a dictionary")
            elif "url" not in bg_music and "local_path" not in bg_music:
                result.add_error(
                    "Global 'background_music' must have 'url' or 'local_path'"
                )

        if "output_settings" in data:
            output_settings = data["output_settings"]
            if not isinstance(output_settings, dict):
                result.add_error("'output_settings' must be a dictionary")
            else:
                # Validate specific output settings
                if "fps" in output_settings:
                    if (
                        not isinstance(output_settings["fps"], int)
                        or output_settings["fps"] <= 0
                    ):
                        result.add_error(
                            "'output_settings.fps' must be a positive integer"
                        )

                if "resolution" in output_settings:
                    resolution = output_settings["resolution"]
                    if not isinstance(resolution, str) or "," not in resolution:
                        result.add_error(
                            "'output_settings.resolution' must be a string in format 'width,height'"
                        )

    def _validate_transitions(self, transitions: List[Dict], result: ValidationResult):
        """Validate global transitions list"""
        if not isinstance(transitions, list):
            result.add_error("'transitions' must be a list")
            return

        for i, transition in enumerate(transitions):
            if not isinstance(transition, dict):
                result.add_error(f"Transition {i} must be a dictionary")
                continue

            # Validate transition configuration
            self._validate_transition(transition, f"transition {i}", result)

            # Validate segment references
            if "from_segment" in transition:
                if not isinstance(transition["from_segment"], (str, int)):
                    result.add_error(
                        f"Transition {i} 'from_segment' must be a string or integer"
                    )

            if "to_segment" in transition:
                if not isinstance(transition["to_segment"], (str, int)):
                    result.add_error(
                        f"Transition {i} 'to_segment' must be a string or integer"
                    )


# Export the main validator
def create_video_request_validator(
    metrics_collector: Optional[MetricsCollector] = None,
) -> VideoRequestValidator:
    """Factory function to create video request validator"""
    return VideoRequestValidator(metrics_collector)
