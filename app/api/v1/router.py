"""
API v1 router configuration
"""

from fastapi import APIRouter
from app.api.v1.endpoints import video, health

router = APIRouter(prefix="/api/v1")

# Include all endpoint routers
router.include_router(video.router)
router.include_router(health.router)
