"""
Video creation API endpoints
"""

import os
import uuid
import time
import json
import logging
from typing import Optional
from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse

from app.models.requests import VideoRequest, BatchVideoRequest
from app.models.responses import (
    VideoCreationResponse,
    BatchVideoResponse,
    ErrorResponse,
    UploadResponse,
    CutResult,
)
from app.services.video_service import video_service
from app.core.exceptions import VideoCreationError, FileValidationError
from app.config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/video", tags=["video"])


async def validate_upload_file(file: UploadFile) -> None:
    """Validate uploaded file"""
    if not file.filename:
        raise FileValidationError("No filename provided", file.filename or "")

    # Check file extension
    allowed_extensions = settings.allowed_extensions
    if not any(file.filename.endswith(ext) for ext in allowed_extensions):
        raise FileValidationError(
            f"Invalid file format. Allowed: {', '.join(allowed_extensions)}",
            file.filename,
        )

    # Read file content to check size
    content = await file.read()
    await file.seek(0)  # Reset file pointer

    if len(content) > settings.max_file_size:
        raise FileValidationError(
            f"File too large. Max size: {settings.max_file_size} bytes", file.filename
        )


@router.post("/create", response_model=VideoCreationResponse)
async def create_video(
    file: UploadFile = File(...),
    transitions: Optional[str] = None,
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Create a video from uploaded JSON configuration

    - **file**: JSON file containing video configuration
    - **transitions**: Optional transition type between segments
    """
    start_time = time.time()
    video_id = str(uuid.uuid4())

    try:
        # Validate uploaded file
        await validate_upload_file(file)

        # Read and parse JSON content
        content = await file.read()
        try:
            json_data = json.loads(content.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail={"error": "Invalid JSON format", "details": str(e)},
            )

        # Validate JSON structure
        if not isinstance(json_data, list):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid format",
                    "details": "JSON must be an array of segments",
                },
            )

        # Create video using service
        output_path = await video_service.create_video_from_json(json_data, transitions)

        # Get file information
        file_size = (
            os.path.getsize(output_path) if os.path.exists(output_path) else None
        )
        processing_time = time.time() - start_time

        # Schedule cleanup in background
        # background_tasks.add_task(
        #     video_service.cleanup_temp_directory, os.path.dirname(output_path)
        # )

        return VideoCreationResponse(
            success=True,
            video_id=video_id,
            download_url=f"/api/v1/video/download/{os.path.basename(output_path)}",
            file_size=file_size,
            duration=None,  # TODO: Extract video duration
            processing_time=processing_time,
        )

    except FileValidationError as e:
        logger.warning(f"File validation error: {e.message}")
        raise HTTPException(
            status_code=400,
            detail={"error": "File validation failed", "details": e.message},
        )
    except VideoCreationError as e:
        logger.error(f"Video creation error: {e.message}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Video creation failed", "details": e.message},
        )
    except Exception as e:
        logger.error(f"Unexpected error in video creation: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "details": "An unexpected error occurred",
            },
        )


@router.post("/batch", response_model=BatchVideoResponse)
async def create_batch_video(
    file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Create a video from batch of cuts in uploaded JSON file

    - **file**: JSON file containing array of video cuts
    """
    start_time = time.time()
    temp_dir = f"tmp_batch_{uuid.uuid4().hex}"

    try:
        # Validate uploaded file
        await validate_upload_file(file)

        # Read and parse JSON content
        content = await file.read()
        try:
            json_data = json.loads(content.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail={"error": "Invalid JSON format", "details": str(e)},
            )

        # Validate JSON structure
        if not isinstance(json_data, list):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Invalid format",
                    "details": "JSON must be an array of cuts",
                },
            )

        if len(json_data) == 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "Empty input",
                    "details": "JSON array cannot be empty",
                },
            )

        # Process batch video creation
        output_path, cut_results = await video_service.process_batch_video_creation(
            json_data, tmp_dir=temp_dir
        )

        # Calculate statistics
        total_cuts = len(cut_results)
        successful_cuts = sum(
            1 for result in cut_results if result["status"] == "success"
        )
        failed_cuts = total_cuts - successful_cuts
        processing_time = time.time() - start_time

        # Schedule cleanup in background
        background_tasks.add_task(video_service.cleanup_temp_directory, temp_dir)

        return BatchVideoResponse(
            success=successful_cuts > 0,
            final_video_url=(
                f"/api/v1/video/download/{os.path.basename(output_path)}"
                if successful_cuts > 0
                else None
            ),
            total_cuts=total_cuts,
            successful_cuts=successful_cuts,
            failed_cuts=failed_cuts,
            cut_results=[
                CutResult(
                    id=result["id"],
                    status=result["status"],
                    video_path=result["video_path"],
                    error=result["error"],
                    processing_time=None,  # TODO: Track individual cut processing time
                )
                for result in cut_results
            ],
            total_processing_time=processing_time,
        )

    except FileValidationError as e:
        logger.warning(f"File validation error: {e.message}")
        raise HTTPException(
            status_code=400,
            detail={"error": "File validation failed", "details": e.message},
        )
    except VideoCreationError as e:
        logger.error(f"Batch video creation error: {e.message}")
        raise HTTPException(
            status_code=500,
            detail={"error": "Batch video creation failed", "details": e.message},
        )
    except Exception as e:
        logger.error(f"Unexpected error in batch video creation: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "error": "Internal server error",
                "details": "An unexpected error occurred",
            },
        )


@router.get("/download/{filename}")
async def download_video(
    filename: str, background_tasks: BackgroundTasks = BackgroundTasks()
):
    """
    Download a created video file

    - **filename**: Name of the video file to download
    """
    # Security: Basic filename validation
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "Invalid filename",
                "details": "Filename contains invalid characters",
            },
        )

    # Look for file in common temp directories
    possible_paths = [
        os.path.join(f"tmp_create_{filename.split('_')[2].split('.')[0]}", filename),
        os.path.join(f"tmp_batch_{filename.split('_')[2].split('.')[0]}", filename),
        filename,  # Direct path
    ]

    file_path = None
    temp_dir = None
    for path in possible_paths:
        if os.path.exists(path):
            file_path = path
            temp_dir = os.path.dirname(path)
            break

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(
            status_code=404,
            detail={
                "error": "File not found",
                "details": "The requested video file does not exist",
            },
        )

    # Schedule cleanup after download
    if temp_dir:
        logger.info(f"📋 Scheduling cleanup for: {temp_dir}")
        background_tasks.add_task(video_service.cleanup_temp_directory, temp_dir)

    return FileResponse(path=file_path, filename=filename, media_type="video/mp4")
