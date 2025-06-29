"""
Custom exception handlers and error types
"""

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import traceback
from typing import Optional

logger = logging.getLogger(__name__)


class VideoProcessingError(Exception):
    """Custom exception for video processing errors"""

    def __init__(self, message: str, error_code: "Optional[str]" = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class VideoCreationError(VideoProcessingError):
    """Custom exception for video creation errors"""

    def __init__(self, message: str, error_code: Optional[str] = None):
        super().__init__(message, error_code)


class FileValidationError(Exception):
    """Custom exception for file validation errors"""

    def __init__(self, message: str, file_name: Optional[str] = None):
        self.message = message
        self.file_name = file_name
        super().__init__(self.message)


async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors"""
    logger.warning(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "error": "Validation error",
                "details": "Invalid request data",
                "errors": exc.errors(),
            }
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent format"""
    logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}")

    # Ensure detail is in our standard format
    if isinstance(exc.detail, dict):
        detail = exc.detail
    else:
        detail = {"error": "HTTP Error", "details": str(exc.detail)}

    return JSONResponse(status_code=exc.status_code, content={"detail": detail})


async def video_processing_exception_handler(
    request: Request, exc: VideoProcessingError
):
    """Handle video processing errors"""
    logger.error(f"Video processing error: {exc.message}")
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "error": "Video processing failed",
                "details": exc.message,
                "error_code": exc.error_code,
            }
        },
    )


async def file_validation_exception_handler(request: Request, exc: FileValidationError):
    """Handle file validation errors"""
    logger.warning(f"File validation error: {exc.message} (file: {exc.file_name})")
    return JSONResponse(
        status_code=400,
        content={
            "detail": {
                "error": "File validation failed",
                "details": exc.message,
                "file_name": exc.file_name,
            }
        },
    )


async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    logger.error(f"Unexpected error: {type(exc).__name__}: {str(exc)}")
    logger.error(f"Traceback: {traceback.format_exc()}")

    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "error": "Internal server error",
                "details": "An unexpected error occurred",
            }
        },
    )
