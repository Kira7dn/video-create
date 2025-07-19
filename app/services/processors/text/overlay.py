import os
import logging
from app.config.settings import settings

logger = logging.getLogger(__name__)


class TextOverlayProcessor:
    """Handles text overlay drawtext filter generation with fade-in/fade-out"""

    @staticmethod
    def _escape_text_for_ffmpeg(text: str) -> str:
        """Properly escape text for FFmpeg drawtext filter"""
        if not text:
            return ""

        # FFmpeg drawtext needs specific escaping
        escaped = text
        # First escape backslashes
        escaped = escaped.replace("\\", "\\\\")
        # Then escape single quotes
        escaped = escaped.replace(
            "'", "'\"'\"'"
        )  # Break out of quotes to insert literal quote
        # Escape colons (used for parameter separation)
        escaped = escaped.replace(":", "\\:")
        # Escape special characters that could break parsing
        escaped = escaped.replace("%", "\\%")
        escaped = escaped.replace("{", "\\{")
        escaped = escaped.replace("}", "\\}")

        return escaped

    @staticmethod
    def build_drawtext_filter(text_over, total_duration, delay=0.0):
        """Build drawtext filter without unsupported alpha parameter"""
        if not text_over.get("text"):
            return None

        # Safely escape text
        safe_text = TextOverlayProcessor._escape_text_for_ffmpeg(text_over["text"])

        # Calculate timing
        text_start = float(text_over.get("start_time", 0)) + delay
        text_duration = text_over.get("duration")
        text_end = text_over.get("end")

        if text_end is None:
            if text_duration is not None:
                text_end = text_start + float(text_duration)
            else:
                text_end = min(text_start + 5, total_duration)
        else:
            text_end = float(text_end)

        # Handle font
        font_file = text_over.get("font_file", settings.text_default_font_file)
        if not os.path.exists(font_file) and not font_file.startswith("/"):
            font_file = os.path.join(os.getcwd(), font_file)
            if not os.path.exists(font_file):
                logger.warning(
                    "Font file not found: %s, using system default", font_file
                )
                font_file = "Arial"

        # Build drawtext parameters with minimal approach - NO ALPHA parameter
        params = []

        # Font parameter
        if os.path.exists(font_file):
            params.append(f"fontfile={font_file}")
        else:
            params.append(f"font={font_file}")

        # Text parameter - single quotes around text only
        params.append(f"text='{safe_text}'")

        # Style parameters
        params.append(
            f"fontcolor={text_over.get('font_color', settings.text_default_font_color)}"
        )
        params.append(
            f"fontsize={text_over.get('font_size', settings.text_default_font_size)}"
        )
        params.append(f"x={text_over.get('x', settings.text_default_position_x)}")
        params.append(f"y={text_over.get('y', settings.text_default_position_y)}")

        # Timing parameters - format numbers to avoid decimal issues
        start_formatted = f"{text_start:.3f}".rstrip("0").rstrip(".")
        end_formatted = f"{text_end:.3f}".rstrip("0").rstrip(".")
        params.append(
            f"enable=between(t\\,{start_formatted}\\,{end_formatted})"
        )  # Escape commas, no quotes

        # Box parameters if needed
        if text_over.get("box"):
            params.append("box=1")
            params.append(f"boxcolor={text_over.get('box_color', 'black@0.5')}")
            params.append(f"boxborderw={text_over.get('box_border_width', 10)}")

        # Join parameters with colons
        return "drawtext=" + ":".join(params)

    @staticmethod
    def build_multiple_drawtext_filters(text_overs, total_duration):
        """Build multiple drawtext filters as separate filter components"""
        if not text_overs:
            return []

        filters = []
        for text_over in text_overs:
            filter_str = TextOverlayProcessor.build_drawtext_filter(
                text_over, total_duration
            )
            if filter_str:
                filters.append(filter_str)

        return filters
