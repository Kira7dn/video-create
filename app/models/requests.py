"""
Request and response models for the API
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class VideoRequest(BaseModel):
    """Request model for video creation"""

    transitions: Optional[str] = Field(
        None, description="Optional transition type for video segments"
    )


class VideoSegment(BaseModel):
    """Model for a single video segment"""

    type: str = Field(description="Type of the video segment")
    duration: float = Field(default=5.0, description="Duration in seconds")
    background_image: Optional[str] = Field(
        None, description="Background image URL or path"
    )
    background_music: Optional[str] = Field(
        None, description="Background music URL or path"
    )
    texts: Optional[List[Dict[str, Any]]] = Field(
        default=[], description="Text overlays"
    )
    tts: Optional[Dict[str, str]] = Field(
        None, description="Text-to-speech configuration"
    )


class VideoCreationRequest(BaseModel):
    """Complete video creation request"""

    segments: List[VideoSegment] = Field(description="List of video segments")
    transitions: Optional[str] = Field(
        None, description="Transition type between segments"
    )
    output_format: str = Field(default="mp4", description="Output video format")


class CutData(BaseModel):
    """Model for a single cut in batch processing"""

    id: Optional[str] = Field(None, description="Unique identifier for the cut")
    images: List[Dict[str, Any]] = Field(description="List of images for the cut")
    voice_over: str = Field(description="Voice over audio file path or URL")
    background_music: str = Field(description="Background music file path or URL")
    voice_over_is_url: bool = Field(
        default=False, description="Whether voice_over is a URL"
    )
    background_music_is_url: bool = Field(
        default=False, description="Whether background_music is a URL"
    )
    transition: Optional[Dict[str, Any]] = Field(
        None, description="Transition configuration"
    )


class BatchVideoRequest(BaseModel):
    """Request model for batch video creation"""

    cuts: List[CutData] = Field(description="List of video cuts to process")
    transitions: Optional[List[Dict[str, Any]]] = Field(
        None, description="Global transitions configuration"
    )
    output_name: Optional[str] = Field(None, description="Custom output filename")
