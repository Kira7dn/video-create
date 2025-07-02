"""
Video creation API endpoints
"""

import os
import uuid
import time
import json
import logging
import threading
from filelock import FileLock
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

# Global job store and lock for thread safety
JOB_STORE_PATH = os.path.join("data", "job_store.json")
JOB_STORE_LOCK_PATH = os.path.join("data", "job_store.json.lock")


def load_job_store():
    if not os.path.exists(JOB_STORE_PATH):
        return {}
    with FileLock(JOB_STORE_LOCK_PATH, timeout=5):
        with open(JOB_STORE_PATH, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except Exception:
                return {}


def save_job_store(job_store):
    os.makedirs(os.path.dirname(JOB_STORE_PATH), exist_ok=True)
    with FileLock(JOB_STORE_LOCK_PATH, timeout=5):
        with open(JOB_STORE_PATH, "w", encoding="utf-8") as f:
            json.dump(job_store, f)


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


@router.post("/create", response_model=dict)
async def create_video(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """
    Create a video from uploaded JSON configuration (async job)
    Returns: {"job_id": ...}
    """
    job_id = str(uuid.uuid4())
    content = await file.read()
    filename = file.filename
    job_store = load_job_store()
    job_store[job_id] = {"status": "pending", "result": None, "error": None}
    save_job_store(job_store)

    async def process_job(content, filename):
        try:
            # Validate file (filename, extension, size)
            allowed_extensions = settings.allowed_extensions
            if not filename:
                raise FileValidationError("No filename provided", filename or "")
            if not any(filename.endswith(ext) for ext in allowed_extensions):
                raise FileValidationError(
                    f"Invalid file format. Allowed: {', '.join(allowed_extensions)}",
                    filename,
                )
            if len(content) > settings.max_file_size:
                raise FileValidationError(
                    f"File too large. Max size: {settings.max_file_size} bytes",
                    filename,
                )
            # Parse JSON
            json_data = json.loads(content.decode("utf-8"))
            if not isinstance(json_data, list):
                raise ValueError("JSON must be an array of segments")
            output_path = await video_service_v2.create_video_from_json(json_data)
            job_store = load_job_store()
            job_store[job_id]["status"] = "done"
            job_store[job_id]["result"] = output_path
            save_job_store(job_store)
        except Exception as e:
            job_store = load_job_store()
            job_store[job_id]["status"] = "failed"
            job_store[job_id]["error"] = str(e)
            save_job_store(job_store)

    background_tasks.add_task(process_job, content, filename)
    return {"job_id": job_id}


@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    job_store = load_job_store()
    job = job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail={"error": "Job not found"})
    return job


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
    if filename.startswith("final_video_"):
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
            filename,  # Direct path
        ]

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
        wait_time = 2.0
        time.sleep(wait_time)
        gc.collect()

        # Cleanup output file in root directory with retry
        if file_path and os.path.exists(file_path) and not os.path.dirname(file_path):
            # Only cleanup files in root directory (final_video_*.mp4)
            cleanup_attempts = 2  # More attempts for Windows
            for attempt in range(cleanup_attempts):
                try:
                    # Force close any potential file handles before removal
                    gc.collect()
                    os.remove(file_path)
                    logger.info(f"🗑️ Cleaned up output file: {file_path}")
                    break
                except PermissionError as e:
                    if attempt < cleanup_attempts - 1:
                        wait_retry = 3.0
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
