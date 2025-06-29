"""
Health check API endpoints
"""

from fastapi import APIRouter
from app.models.responses import HealthResponse
from app.core.monitoring import health_checker

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint that returns system status and metrics
    """
    health_data = health_checker.get_system_health()

    return HealthResponse(
        status=health_data.status,
        timestamp=health_data.timestamp,
        uptime=health_data.uptime,
        memory_usage=health_data.memory_usage,
        disk_usage=health_data.disk_usage,
        cpu_usage=health_data.cpu_usage,
        active_processes=health_data.active_processes,
    )


@router.get("/")
async def root():
    """
    Root endpoint
    """
    return {"message": "Video Creation API is running", "status": "healthy"}
