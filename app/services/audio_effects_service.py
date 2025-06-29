"""
Advanced audio effects and processing service
"""

from moviepy import AudioFileClip, CompositeAudioClip
from moviepy.audio.fx import (
    MultiplyVolume,
    MultiplyStereoVolume,
    AudioNormalize,
    AudioFadeIn,
    AudioFadeOut,
)
import numpy as np
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class AudioEffectsService:
    """Service for advanced audio processing and effects"""

    @staticmethod
    def apply_volume_effects(
        audio: AudioFileClip, config: Dict[str, Any]
    ) -> AudioFileClip:
        """Apply volume-related effects"""
        if "multiply_volume" in config:
            factor = config["multiply_volume"]
            audio = MultiplyVolume(factor=factor).apply(audio)

        if "stereo_volume" in config:
            left = config["stereo_volume"].get("left", 1.0)
            right = config["stereo_volume"].get("right", 1.0)
            audio = MultiplyStereoVolume(left=left, right=right).apply(audio)

        if "normalize" in config and config["normalize"]:
            audio = AudioNormalize().apply(audio)

        return audio

    @staticmethod
    def apply_fade_effects(
        audio: AudioFileClip, fade_in: float = 0, fade_out: float = 0
    ) -> AudioFileClip:
        """Apply audio fade effects"""
        if fade_in > 0:
            audio = AudioFadeIn(fade_in).apply(audio)
        if fade_out > 0:
            audio = AudioFadeOut(fade_out).apply(audio)
        return audio

    @staticmethod
    def create_audio_ducking(
        voice: AudioFileClip,
        background: AudioFileClip,
        duck_factor: float = 0.3,
        threshold: float = -20,
    ) -> CompositeAudioClip:
        """
        Create audio ducking effect: lower background music when voice is present
        """
        # Simple ducking implementation
        # Lower background volume when voice is present
        ducked_bg = MultiplyVolume(factor=duck_factor).apply(background)
        return CompositeAudioClip([voice, ducked_bg])

    @staticmethod
    def create_layered_audio(audio_layers: List[Dict[str, Any]]) -> CompositeAudioClip:
        """
        Create complex layered audio with different effects per layer

        audio_layers format:
        [
            {
                "audio": AudioFileClip,
                "effects": {
                    "volume": 0.8,
                    "fade_in": 1.0,
                    "fade_out": 0.5,
                    "start_time": 0
                }
            }
        ]
        """
        processed_clips = []

        for layer in audio_layers:
            audio_clip = layer["audio"]
            effects = layer.get("effects", {})

            # Apply volume
            if "volume" in effects:
                audio_clip = MultiplyVolume(factor=effects["volume"]).apply(audio_clip)

            # Apply fade effects
            fade_in = effects.get("fade_in", 0)
            fade_out = effects.get("fade_out", 0)
            audio_clip = AudioEffectsService.apply_fade_effects(
                audio_clip, fade_in, fade_out
            )

            # Set start time
            start_time = effects.get("start_time", 0)
            if start_time > 0:
                audio_clip = audio_clip.with_start(start_time)

            processed_clips.append(audio_clip)

        return CompositeAudioClip(processed_clips)

    @staticmethod
    def create_audio_crossfade(
        audio1: AudioFileClip, audio2: AudioFileClip, crossfade_duration: float = 1.0
    ) -> CompositeAudioClip:
        """Create crossfade between two audio clips"""
        # Fade out first audio
        audio1_faded = AudioFadeOut(crossfade_duration).apply(audio1)

        # Fade in second audio and delay it
        start_time = audio1.duration - crossfade_duration
        audio2_faded = (
            AudioFadeIn(crossfade_duration).apply(audio2).with_start(start_time)
        )

        return CompositeAudioClip([audio1_faded, audio2_faded])

    @staticmethod
    def apply_audio_effects_chain(
        audio: AudioFileClip, effects_config: List[Dict[str, Any]]
    ) -> AudioFileClip:
        """Apply a chain of audio effects"""
        for effect in effects_config:
            effect_type = effect.get("type")
            params = effect.get("params", {})

            if effect_type == "volume":
                audio = AudioEffectsService.apply_volume_effects(audio, params)
            elif effect_type == "fade":
                fade_in = params.get("fade_in", 0)
                fade_out = params.get("fade_out", 0)
                audio = AudioEffectsService.apply_fade_effects(audio, fade_in, fade_out)

        return audio
