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
from fastapi.responses import FileResponse, StreamingResponse
from starlette.background import BackgroundTask

from app.models.requests import VideoRequest, BatchVideoRequest
from app.models.responses import (
    VideoCreationResponse,
    BatchVideoResponse,
    ErrorResponse,
    UploadResponse,
    CutResult,
)
from app.services.video_service_v2 import video_service_v2
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
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Create a video from uploaded JSON configuration

    - **file**: JSON file containing video configuration
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
        output_path = await video_service_v2.create_video_from_json(json_data)

        # Get file information
        file_size = (
            os.path.getsize(output_path) if os.path.exists(output_path) else None
        )
        processing_time = time.time() - start_time

        # Schedule cleanup in background
        background_tasks.add_task(
            video_service_v2.cleanup_temp_directory, os.path.dirname(output_path)
        )

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
    batch_uuid = uuid.uuid4().hex
    temp_dir = f"tmp_batch_{batch_uuid}"

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

        # Process batch video creation, truyền batch_uuid vào để dùng cho tên file output
        output_path, cut_results = await video_service_v2.process_batch_video_creation(
            json_data, tmp_dir=temp_dir, batch_uuid=batch_uuid
        )

        # Calculate statistics
        total_cuts = len(cut_results)
        successful_cuts = sum(
            1 for result in cut_results if result["status"] == "success"
        )
        failed_cuts = total_cuts - successful_cuts
        processing_time = time.time() - start_time

        # Schedule cleanup in background
        background_tasks.add_task(video_service_v2.cleanup_temp_directory, temp_dir)

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
            detail={"error": "Unexpected error", "details": str(e)},
        )


@router.get("/download/{filename}")
async def download_video(filename: str):
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
    # Extract UUID from filename pattern: final_batch_video_{uuid}.mp4 or final_video_{uuid}.mp4
    if filename.startswith("final_batch_video_"):
        uuid_part = filename.replace("final_batch_video_", "").replace(".mp4", "")
        possible_paths = [
            os.path.join(f"tmp_batch_{uuid_part}", filename),
            filename,  # Direct path
        ]
    elif filename.startswith("final_video_"):
        uuid_part = filename.replace("final_video_", "").replace(".mp4", "")
        possible_paths = [
            os.path.join(f"tmp_create_{uuid_part}", filename),
            filename,  # Direct path
        ]
    else:
        # Fallback to old logic for other filename patterns
        possible_paths = [
            os.path.join(
                f"tmp_create_{filename.split('_')[2].split('.')[0]}", filename
            ),
            os.path.join(f"tmp_batch_{filename.split('_')[2].split('.')[0]}", filename),
            filename,  # Direct path
        ]

    logger.info(f"[DOWNLOAD] Looking for file: {filename}")
    logger.info(f"[DOWNLOAD] Possible paths: {possible_paths}")

    file_path = None
    temp_dir = None
    for path in possible_paths:
        logger.info(
            f"[DOWNLOAD] Checking path: {path} - exists: {os.path.exists(path)}"
        )
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

    # Cleanup callback: xóa file output và temp directory sau khi response đã gửi xong
    def cleanup():
        import time
        import gc
        import platform

        # Wait longer on Windows to ensure file handles are fully released
        wait_time = 5.0 if platform.system() == "Windows" else 2.0
        time.sleep(wait_time)
        gc.collect()

        # Additional wait and force garbage collection for Windows
        if platform.system() == "Windows":
            time.sleep(2.0)
            gc.collect()

        # Cleanup output file in root directory with retry
        if file_path and os.path.exists(file_path) and not os.path.dirname(file_path):
            # Only cleanup files in root directory (final_video_*.mp4)
            cleanup_attempts = 5  # More attempts for Windows
            for attempt in range(cleanup_attempts):
                try:
                    # Force close any potential file handles before removal
                    gc.collect()
                    os.remove(file_path)
                    logger.info(f"🗑️ Cleaned up output file: {file_path}")
                    break
                except PermissionError as e:
                    if attempt < cleanup_attempts - 1:
                        wait_retry = 5.0 if platform.system() == "Windows" else 3.0
                        logger.warning(
                            f"⚠️ Output file cleanup attempt {attempt + 1} failed, retrying in {wait_retry}s: {e}"
                        )
                        time.sleep(wait_retry)
                        gc.collect()  # Force garbage collection before retry
                    else:
                        logger.warning(
                            f"❌ Failed to cleanup output file {file_path} after {cleanup_attempts} attempts: {e}"
                        )
                except Exception as e:
                    logger.warning(f"⚠️ Failed to cleanup output file {file_path}: {e}")
                    break

        # Cleanup temp directory if exists
        if temp_dir and temp_dir != ".":
            logger.info(f"📋 Cleanup after download for: {temp_dir}")
            video_service_v2.cleanup_temp_directory(temp_dir)

    def generate_file():
        """Generator to read file and ensure it's properly closed"""
        try:
            with open(file_path, "rb") as f:
                while True:
                    data = f.read(8192)  # Read in 8KB chunks
                    if not data:
                        break
                    yield data
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise

    response = StreamingResponse(
        generate_file(),
        media_type="video/mp4",
        background=BackgroundTask(cleanup),
    )
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
