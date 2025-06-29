"""
Response models for the API
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class ErrorResponse(BaseModel):
    """Standard error response model"""

    error: str = Field(description="Error type or category")
    details: Optional[str] = Field(None, description="Detailed error message")
    error_code: Optional[str] = Field(None, description="Specific error code")
    timestamp: datetime = Field(
        default_factory=datetime.now, description="Error timestamp"
    )


class VideoCreationResponse(BaseModel):
    """Response model for successful video creation"""

    success: bool = Field(True, description="Whether the operation was successful")
    video_id: str = Field(description="Unique identifier for the created video")
    download_url: str = Field(description="URL to download the created video")
    file_size: Optional[int] = Field(
        None, description="Size of the created video file in bytes"
    )
    duration: Optional[float] = Field(
        None, description="Duration of the video in seconds"
    )
    processing_time: Optional[float] = Field(
        None, description="Time taken to process the video"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )


class CutResult(BaseModel):
    """Result for a single cut in batch processing"""

    id: str = Field(description="Cut identifier")
    status: str = Field(description="Processing status (success/error)")
    video_path: Optional[str] = Field(None, description="Path to the processed video")
    error: Optional[str] = Field(None, description="Error message if processing failed")
    processing_time: Optional[float] = Field(
        None, description="Time taken to process this cut"
    )


class BatchVideoResponse(BaseModel):
    """Response model for batch video creation"""

    success: bool = Field(description="Whether the overall operation was successful")
    final_video_url: Optional[str] = Field(
        None, description="URL to download the final concatenated video"
    )
    total_cuts: int = Field(description="Total number of cuts processed")
    successful_cuts: int = Field(description="Number of successfully processed cuts")
    failed_cuts: int = Field(description="Number of failed cuts")
    cut_results: List[CutResult] = Field(description="Detailed results for each cut")
    total_processing_time: Optional[float] = Field(
        None, description="Total processing time"
    )
    created_at: datetime = Field(
        default_factory=datetime.now, description="Creation timestamp"
    )


class HealthResponse(BaseModel):
    """Health check response model"""

    status: str = Field(description="Service health status")
    timestamp: datetime = Field(description="Health check timestamp")
    uptime: float = Field(description="Service uptime in seconds")
    memory_usage: Dict[str, Any] = Field(description="Memory usage statistics")
    disk_usage: Dict[str, Any] = Field(description="Disk usage statistics")
    cpu_usage: float = Field(description="CPU usage percentage")
    active_processes: int = Field(description="Number of active processes")


class UploadResponse(BaseModel):
    """Response model for file uploads"""

    success: bool = Field(True, description="Whether the upload was successful")
    filename: str = Field(description="Name of the uploaded file")
    file_size: int = Field(description="Size of the uploaded file in bytes")
    upload_id: str = Field(description="Unique identifier for the upload")
    message: str = Field(description="Success message")
    uploaded_at: datetime = Field(
        default_factory=datetime.now, description="Upload timestamp"
    )
