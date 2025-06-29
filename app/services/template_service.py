"""
Video template and preset system for quick video creation
"""

from typing import Dict, Any, List, Optional
import json
import os
import logging

logger = logging.getLogger(__name__)


class VideoTemplateService:
    """Service for managing video templates and presets"""

    def __init__(self, templates_dir: str = "templates"):
        self.templates_dir = templates_dir
        os.makedirs(templates_dir, exist_ok=True)

    def get_social_media_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get predefined social media templates"""
        return {
            "instagram_story": {
                "name": "Instagram Story",
                "description": "Vertical 9:16 format for Instagram Stories",
                "video_config": {"size": (1080, 1920), "fps": 30, "duration": 15},
                "text_style": {
                    "font_size": 48,
                    "color": "white",
                    "stroke_color": "black",
                    "stroke_width": 2,
                    "position": "center",
                },
                "audio_config": {
                    "background_volume": 0.3,
                    "voice_volume": 1.0,
                    "fade_in": 0.5,
                    "fade_out": 0.5,
                },
                "effects": [
                    {
                        "type": "fade",
                        "category": "fade",
                        "params": {"fade_in": 0.5, "fade_out": 0.5},
                    }
                ],
            },
            "youtube_short": {
                "name": "YouTube Short",
                "description": "Vertical format for YouTube Shorts",
                "video_config": {"size": (1080, 1920), "fps": 60, "duration": 60},
                "text_style": {
                    "font_size": 52,
                    "color": "yellow",
                    "stroke_color": "black",
                    "stroke_width": 3,
                    "position": ("center", 200),
                },
                "audio_config": {
                    "background_volume": 0.2,
                    "voice_volume": 1.0,
                    "normalize": True,
                },
                "effects": [
                    {
                        "type": "zoom",
                        "category": "motion",
                        "params": {"zoom_factor": 1.1},
                    }
                ],
            },
            "tiktok": {
                "name": "TikTok Video",
                "description": "Vertical format optimized for TikTok",
                "video_config": {"size": (1080, 1920), "fps": 30, "duration": 30},
                "text_style": {
                    "font_size": 44,
                    "color": "white",
                    "font": "Arial-Bold",
                    "stroke_color": "black",
                    "stroke_width": 2,
                    "position": ("center", 300),
                },
                "audio_config": {
                    "background_volume": 0.4,
                    "voice_volume": 1.0,
                    "crossfade": True,
                },
                "effects": [
                    {
                        "type": "slide_in_left",
                        "category": "motion",
                        "params": {"animation_duration": 0.3},
                    }
                ],
            },
            "facebook_post": {
                "name": "Facebook Post",
                "description": "Square format for Facebook posts",
                "video_config": {"size": (1080, 1080), "fps": 30, "duration": 30},
                "text_style": {
                    "font_size": 36,
                    "color": "white",
                    "position": ("center", 900),
                },
                "audio_config": {"background_volume": 0.25, "voice_volume": 1.0},
            },
            "linkedin_post": {
                "name": "LinkedIn Post",
                "description": "Professional format for LinkedIn",
                "video_config": {"size": (1200, 675), "fps": 30, "duration": 60},
                "text_style": {
                    "font_size": 32,
                    "color": "white",
                    "font": "Arial",
                    "position": ("center", 600),
                },
                "audio_config": {
                    "background_volume": 0.15,
                    "voice_volume": 1.0,
                    "fade_in": 1.0,
                    "fade_out": 1.0,
                },
            },
        }

    def get_content_type_templates(self) -> Dict[str, Dict[str, Any]]:
        """Get templates based on content type"""
        return {
            "news_update": {
                "name": "News Update",
                "description": "Template for news and updates",
                "segments": [
                    {
                        "type": "intro",
                        "duration": 3,
                        "texts": [
                            {
                                "text": "BREAKING NEWS",
                                "animation": "slide_in_left",
                                "style": {"font_size": 48, "color": "red"},
                            }
                        ],
                    },
                    {
                        "type": "content",
                        "duration": 15,
                        "texts": [
                            {
                                "text": "{{content_text}}",
                                "animation": "fade_in",
                                "style": {"font_size": 32, "color": "white"},
                            }
                        ],
                    },
                    {
                        "type": "outro",
                        "duration": 2,
                        "texts": [
                            {
                                "text": "Stay tuned for more updates",
                                "animation": "fade_out",
                                "style": {"font_size": 24, "color": "lightgray"},
                            }
                        ],
                    },
                ],
            },
            "product_showcase": {
                "name": "Product Showcase",
                "description": "Template for product demonstrations",
                "segments": [
                    {
                        "type": "intro",
                        "duration": 2,
                        "texts": [
                            {
                                "text": "NEW PRODUCT",
                                "animation": "zoom_in",
                                "style": {"font_size": 52, "color": "gold"},
                            }
                        ],
                    },
                    {
                        "type": "features",
                        "duration": 20,
                        "texts": [
                            {
                                "text": "{{product_features}}",
                                "animation": "typewriter",
                                "style": {"font_size": 28, "color": "white"},
                            }
                        ],
                    },
                    {
                        "type": "cta",
                        "duration": 3,
                        "texts": [
                            {
                                "text": "GET YOURS TODAY!",
                                "animation": "blink",
                                "style": {"font_size": 44, "color": "lime"},
                            }
                        ],
                    },
                ],
            },
            "tutorial": {
                "name": "Tutorial",
                "description": "Step-by-step tutorial format",
                "segments": [
                    {
                        "type": "title",
                        "duration": 3,
                        "texts": [
                            {
                                "text": "HOW TO: {{tutorial_title}}",
                                "animation": "slide_in_top",
                                "style": {"font_size": 40, "color": "white"},
                            }
                        ],
                    },
                    {
                        "type": "steps",
                        "duration": "variable",
                        "texts": [
                            {
                                "text": "Step {{step_number}}: {{step_description}}",
                                "animation": "fade_in",
                                "style": {"font_size": 32, "color": "cyan"},
                            }
                        ],
                    },
                ],
            },
        }

    def apply_template(
        self, template_name: str, content_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply a template with user content"""
        social_templates = self.get_social_media_templates()
        content_templates = self.get_content_type_templates()

        # Check social media templates first
        if template_name in social_templates:
            template = social_templates[template_name]
            return self._merge_template_with_content(template, content_data)

        # Check content type templates
        if template_name in content_templates:
            template = content_templates[template_name]
            return self._merge_template_with_content(template, content_data)

        raise ValueError(f"Template '{template_name}' not found")

    def _merge_template_with_content(
        self, template: Dict[str, Any], content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Merge template configuration with user content"""
        result = template.copy()

        # Replace placeholders in template
        if "segments" in template:
            for segment in result["segments"]:
                if "texts" in segment:
                    for text_item in segment["texts"]:
                        text_content = text_item.get("text", "")
                        # Replace placeholders with actual content
                        for key, value in content.items():
                            placeholder = f"{{{{{key}}}}}"
                            if placeholder in text_content:
                                text_item["text"] = text_content.replace(
                                    placeholder, str(value)
                                )

        # Merge user-specific configurations
        if "video_config" in content:
            result.setdefault("video_config", {}).update(content["video_config"])

        if "audio_config" in content:
            result.setdefault("audio_config", {}).update(content["audio_config"])

        return result

    def save_custom_template(self, name: str, template_config: Dict[str, Any]) -> bool:
        """Save a custom template to disk"""
        try:
            template_path = os.path.join(self.templates_dir, f"{name}.json")
            with open(template_path, "w", encoding="utf-8") as f:
                json.dump(template_config, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved custom template: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to save template {name}: {e}")
            return False

    def load_custom_template(self, name: str) -> Optional[Dict[str, Any]]:
        """Load a custom template from disk"""
        try:
            template_path = os.path.join(self.templates_dir, f"{name}.json")
            if os.path.exists(template_path):
                with open(template_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"Failed to load template {name}: {e}")
            return None

    def list_available_templates(self) -> Dict[str, List[str]]:
        """List all available templates"""
        social_templates = list(self.get_social_media_templates().keys())
        content_templates = list(self.get_content_type_templates().keys())

        # Load custom templates
        custom_templates = []
        if os.path.exists(self.templates_dir):
            for file in os.listdir(self.templates_dir):
                if file.endswith(".json"):
                    custom_templates.append(file[:-5])  # Remove .json extension

        return {
            "social_media": social_templates,
            "content_type": content_templates,
            "custom": custom_templates,
        }
