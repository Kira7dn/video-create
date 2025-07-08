import os
from app.config.settings import settings
import logging

logger = logging.getLogger(__name__)

class TextOverlayProcessor:
    """Handles text overlay drawtext filter generation with fade-in/fade-out"""
    @staticmethod
    def build_drawtext_filter(text_over, total_duration):
        if not text_over.get("text"):
            return None
        safe_text = text_over['text']
        text_start = text_over.get('start', text_over.get('start_time', 0))
        text_duration = text_over.get('duration')
        text_end = text_over.get('end')
        if text_end is None:
            if text_duration is not None:
                text_end = float(text_start) + float(text_duration)
            else:
                text_end = min(5, total_duration)
        fade_in = float(text_over.get('fade_in', settings.text_default_fade_in))
        fade_out = float(text_over.get('fade_out', settings.text_default_fade_out))
        visible_duration = float(text_end) - float(text_start)
        fade_in = min(fade_in, visible_duration/2)
        fade_out = min(fade_out, visible_duration/2)
        alpha_expr = (
            f"if(lt(t,{text_start}),0,"
            f"if(lt(t,{text_start+fade_in}), (t-{text_start})/{fade_in},"
            f"if(lt(t,{text_end-fade_out}), 1,"
            f"if(lt(t,{text_end}), ({text_end}-t)/{fade_out},0)"
            f")))"
        )
        font_file = text_over.get('font_file', settings.text_default_font_file)
        if not os.path.exists(font_file) and not font_file.startswith('/'):
            font_file = os.path.join(os.getcwd(), font_file)
            if not os.path.exists(font_file):
                logger.warning(f"Font file not found: {font_file}, using system default")
                font_file = "Arial"
        drawtext_args = [
            f"fontfile={font_file}" if os.path.exists(font_file) else f"font={font_file}",
            f"text={safe_text}",
            f"fontcolor={text_over.get('font_color', settings.text_default_font_color)}",
            f"fontsize={text_over.get('font_size', settings.text_default_font_size)}",
            f"x={text_over.get('x', settings.text_default_position_x)}",
            f"y={text_over.get('y', settings.text_default_position_y)}",
            f"enable='between(t,{text_start},{text_end})'",
            f"alpha='{alpha_expr}'"
        ]
        if text_over.get('box'):
            drawtext_args.append("box=1")
            drawtext_args.append(f"boxcolor={text_over.get('box_color', 'black@0.5')}")
            drawtext_args.append(f"boxborderw={text_over.get('box_border_width', 10)}")
        return "drawtext=" + ":".join(drawtext_args)
