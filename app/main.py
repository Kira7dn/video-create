"""
Professional Video Creation API - Production Ready Implementation
"""

import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config.settings import settings
from app.core.exceptions import (
    VideoCreationError,
    FileValidationError,
    VideoProcessingError,
    validation_exception_handler,
    http_exception_handler,
    video_processing_exception_handler,
    file_validation_exception_handler,
    general_exception_handler,
)
from app.core.middleware import (
    RateLimitMiddleware,
    RequestLoggingMiddleware,
)
from app.api.v1.router import router as api_v1_router

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format=settings.log_format,
    datefmt=settings.log_date_format,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management"""
    logger.info("Starting Video Creation API...")
    logger.info(f"Debug mode: {settings.debug}")
    yield
    logger.info("Shutting down Video Creation API...")


def create_application() -> FastAPI:
    """Create and configure FastAPI application"""

    app = FastAPI(
        title=settings.api_title,
        description=settings.api_description,
        version=settings.api_version,
        debug=settings.debug,
        lifespan=lifespan,
    )

    # Add CORS middleware
    # app.add_middleware(
    #     CORSMiddleware,
    #     allow_origins=settings.cors_origins,
    #     allow_credentials=settings.cors_allow_credentials,
    #     allow_methods=settings.cors_allow_methods,
    #     allow_headers=settings.cors_allow_headers,
    # )

    # Add custom middleware
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        calls=settings.max_concurrent_requests,
        period=60,
    )

    # Add exception handlers
    # app.add_exception_handler(RequestValidationError, validation_exception_handler)
    # app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    # app.add_exception_handler(VideoProcessingError, video_processing_exception_handler)
    # app.add_exception_handler(FileValidationError, file_validation_exception_handler)
    # app.add_exception_handler(Exception, general_exception_handler)

    # Include API routers
    app.include_router(api_v1_router)

    return app


# Create application instance
app = create_application()


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
