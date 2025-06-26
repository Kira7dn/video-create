"""
Professional Video Creation API - Production Ready Implementation
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field
from typing import Optional
import os
import uuid
import shutil
import logging
import json
import asyncio
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


# Custom Exception Classes
class VideoProcessingError(Exception):
    """Custom exception for video processing errors"""

    def __init__(self, message: str, video_id: str = None):
        self.message = message
        self.video_id = video_id
        super().__init__(self.message)


class FileValidationError(Exception):
    """Custom exception for file validation errors"""

    def __init__(self, message: str, filename: str = None):
        self.message = message
        self.filename = filename
        super().__init__(self.message)


# Pydantic Models
class ErrorResponse(BaseModel):
    error: str
    details: Optional[str] = None
    error_code: Optional[str] = None


class VideoRequest(BaseModel):
    transitions: Optional[str] = None


# Helper function for executor
def run_video_creation(input_data: list, transitions: str = None) -> str:
    """Helper function to run video creation in executor"""
    from create_video import create_video_from_json

    return asyncio.run(create_video_from_json(input_data, transitions))


# Service Layer
class VideoService:
    def __init__(self, max_file_size: int = 100 * 1024 * 1024):  # 100MB
        self.max_file_size = max_file_size
        self.logger = logging.getLogger(__name__)
        self.executor = ThreadPoolExecutor(
            max_workers=2
        )  # Limit concurrent video processing

    async def validate_upload(self, file: UploadFile) -> None:
        """Validate uploaded file with enhanced checks"""
        if not file.filename:
            raise FileValidationError("No filename provided", file.filename)

        # Check file extension
        allowed_extensions = [".json"]
        if not any(file.filename.endswith(ext) for ext in allowed_extensions):
            raise FileValidationError(
                f"Invalid file format. Allowed: {', '.join(allowed_extensions)}",
                file.filename,
            )

        # Read file content to check size
        content = await file.read()
        await file.seek(0)  # Reset file pointer

        if len(content) > self.max_file_size:
            raise FileValidationError(
                f"File too large. Max size: {self.max_file_size} bytes", file.filename
            )

    async def create_video(
        self, input_json: UploadFile, transitions: Optional[str] = None
    ) -> tuple[str, str]:
        """Create video using optimized async function"""
        try:
            await self.validate_upload(input_json)
        except FileValidationError as e:
            raise HTTPException(
                status_code=400,
                detail={"error": "File validation failed", "details": str(e)},
            )

        video_id = uuid.uuid4().hex
        tmp_dir = f"tmp_create_{video_id}"
        os.makedirs(tmp_dir, exist_ok=True)

        try:
            # Save uploaded file
            json_path = os.path.join(tmp_dir, input_json.filename)
            with open(json_path, "wb") as f:
                shutil.copyfileobj(input_json.file, f)

            # Load and parse JSON
            with open(json_path, "r", encoding="utf-8") as f:
                input_data = json.load(f)

            if not isinstance(input_data, list):
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "Invalid input format",
                        "details": "Input must be an array of objects",
                    },
                )

            if len(input_data) == 0:
                raise HTTPException(
                    status_code=400,
                    detail={
                        "error": "Empty input",
                        "details": "Input array cannot be empty",
                    },
                )

            # Use the existing video creation function (simpler approach)
            output_path = os.path.join(tmp_dir, "output_create.mp4")
            await self._process_video_batch(input_data, output_path, tmp_dir)

            if not os.path.exists(output_path):
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": "Video creation failed",
                        "details": "Output file not generated",
                    },
                )

            return output_path, video_id

        except Exception as e:
            self.logger.error(f"Video creation failed for {video_id}: {e}")
            # Cleanup on error
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)

            if isinstance(e, HTTPException):
                raise e

            raise HTTPException(
                status_code=500,
                detail={"error": "Internal server error", "details": str(e)},
            )

    async def _process_video_batch(
        self, input_data: list, output_path: str, tmp_dir: str
    ):
        """Process video batch using existing create_video functions"""
        # Import here to avoid circular imports
        from create_video import process_single_cut
        from utils.validation_utils import (
            batch_download_urls,
            replace_url_with_local_path,
        )
        from utils.video_utils import concatenate_videos_with_sequence

        temp_files = []
        url_to_local = {}

        try:
            # Download URLs if needed
            url_list = []
            for data in input_data:
                for img in data["images"]:
                    if img.get("is_url"):
                        url_list.append(img["path"])
                for key in ["voice_over", "background_music"]:
                    if data.get(f"{key}_is_url"):
                        url_list.append(data[key])

            if url_list:
                local_paths, download_errors = batch_download_urls(url_list, tmp_dir)
                for url, local in zip(url_list, local_paths):
                    if local:
                        url_to_local[url] = local
                        temp_files.append(local)

                if download_errors:
                    raise RuntimeError(f"Download errors: {download_errors}")

                # Replace URLs with local paths
                input_data = [
                    replace_url_with_local_path(data, url_to_local)
                    for data in input_data
                ]

            # Process each cut
            temp_video_paths = []
            for idx, data in enumerate(input_data):
                cut_id = data.get("id") or f"cut{idx+1}"
                video_path = process_single_cut(data, tmp_dir, cut_id)
                temp_video_paths.append(video_path)
                temp_files.append(video_path)

            # Concatenate videos
            if not temp_video_paths:
                raise RuntimeError("No video cuts to concatenate")

            transitions = [
                obj.get("transition") for obj in input_data if "transition" in obj
            ]

            final_clip = concatenate_videos_with_sequence(
                temp_video_paths, transitions=transitions
            )
            final_clip.write_videofile(
                output_path, codec="libx264", audio_codec="aac", logger=None
            )
            final_clip.close()

            # Cleanup temp video cuts
            for video_path in temp_video_paths:
                if os.path.exists(video_path):
                    os.remove(video_path)

        finally:
            # Cleanup downloaded files
            for f in temp_files:
                if os.path.exists(f):
                    try:
                        os.remove(f)
                    except:
                        pass


# Dependency
def get_video_service() -> VideoService:
    return VideoService()


# Global video service instance
video_service_instance = VideoService()


# Lifespan events
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logging.info("Starting Video Creation API...")
    yield
    # Shutdown
    logging.info("Shutting down Video Creation API...")
    # Cleanup executor
    video_service_instance.executor.shutdown(wait=True)


# FastAPI App
app = FastAPI(
    title="Video Creation API",
    description="Professional video creation service with batch processing",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Middleware
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["http://localhost:3000", "http://localhost:8080"],
#     allow_credentials=True,
#     allow_methods=["GET", "POST"],
#     allow_headers=["*"],
# )


# Utility function
def cleanup_tmp_dir(tmp_dir: str):
    """Cleanup temporary directory"""
    try:
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
            logging.info(f"Cleaned up temporary directory: {tmp_dir}")
    except Exception as e:
        logging.error(f"Failed to cleanup {tmp_dir}: {e}")


# Routes
@app.post(
    "/api/create-video",
    responses={
        200: {
            "description": "Video file created successfully",
            "content": {"video/mp4": {}},
        },
        400: {"model": ErrorResponse, "description": "Invalid input"},
        413: {"model": ErrorResponse, "description": "File too large"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def create_video_api(
    background_tasks: BackgroundTasks,
    input_json: UploadFile = File(
        ..., description="JSON file containing video configuration"
    ),
    video_service: VideoService = Depends(lambda: video_service_instance),
    transitions: Optional[str] = None,
):
    """
    Create a video from JSON configuration

    - **input_json**: JSON file with video configuration (array of video cuts)
    - **transitions**: Optional transitions configuration

    Returns a video file (MP4) as response
    """
    output_path, video_id = await video_service.create_video(input_json, transitions)

    # Get file size for headers
    file_size = os.path.getsize(output_path) if os.path.exists(output_path) else None

    # Schedule cleanup
    background_tasks.add_task(cleanup_tmp_dir, os.path.dirname(output_path))

    # Return file response with proper headers
    headers = {
        "X-Video-ID": video_id,
        "Content-Disposition": f"attachment; filename=video_{video_id}.mp4",
    }
    if file_size:
        headers["Content-Length"] = str(file_size)

    return FileResponse(
        output_path,
        media_type="video/mp4",
        filename=f"video_{video_id}.mp4",
        headers=headers,
    )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "video-creation-api", "version": "1.0.0"}


@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {"message": "Video Creation API", "docs": "/docs", "health": "/health"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
