"""
Video creation API endpoints
"""

import os
import uuid
import json
import logging
from filelock import FileLock
from fastapi import APIRouter, File, UploadFile, HTTPException, BackgroundTasks
from app.services.video_service import video_service
from app.core.exceptions import FileValidationError
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
            if not isinstance(json_data, dict) or "segments" not in json_data:
                raise ValueError("Invalid JSON format: 'segments' key is required")
            result = await video_service.create_video_from_json(json_data)
            job_store = load_job_store()
            job_store[job_id]["status"] = "done"
            job_store[job_id]["result"] = result["s3_url"]  # Use S3 URL instead of local path
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