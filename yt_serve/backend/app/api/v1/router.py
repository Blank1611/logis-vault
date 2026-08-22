"""
API v1 Router - Aggregates all v1 endpoints
"""
from fastapi import APIRouter

from app.api.v1.endpoints import playlists, downloads, config, websocket, metrics

router = APIRouter()

# Include all endpoint routers
router.include_router(playlists.router, prefix="/playlists", tags=["playlists"])
router.include_router(downloads.router, prefix="/downloads", tags=["downloads"])
router.include_router(config.router, prefix="/config", tags=["config"])
router.include_router(websocket.router, prefix="/ws", tags=["websocket"])
router.include_router(metrics.router, tags=["metrics"])

