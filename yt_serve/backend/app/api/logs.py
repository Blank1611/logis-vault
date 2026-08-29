"""
Log API endpoints for retrieving in-memory buffered logs and server log files.
"""

import os
from typing import Optional, List, Dict, Any
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse

from app.core.logging_engine import get_recent_logs, clear_ring_buffer

router = APIRouter()


@router.get("/recent", response_model=List[Dict[str, Any]])
async def get_recent_log_entries(
    limit: int = Query(200, ge=1, le=1000, description="Max entries to return"),
    level: Optional[str] = Query(None, description="Minimum log level: DEBUG, INFO, WARN, ERROR"),
    source: Optional[str] = Query(None, description="Filter by source component"),
    job_id: Optional[int] = Query(None, description="Filter by job ID"),
    search: Optional[str] = Query(None, description="Search query text")
):
    """
    Fetch recent structured logs from the in-memory circular buffer (<1ms latency).
    """
    return get_recent_logs(
        limit=limit,
        min_level=level,
        source=source,
        job_id=job_id,
        search=search
    )


@router.delete("/clear")
async def clear_recent_logs():
    """
    Clear the in-memory circular log buffer.
    """
    clear_ring_buffer()
    return {"status": "success", "message": "In-memory logs cleared"}


@router.get("/file")
async def get_server_log_file():
    """
    Download the main rotating server log file (yt_manager.log).
    """
    backend_dir = Path(__file__).parent.parent.parent
    log_file = backend_dir / "logs" / "yt_manager.log"

    if not log_file.exists():
        raise HTTPException(status_code=404, detail="Log file not found")

    return FileResponse(
        str(log_file),
        media_type="text/plain",
        filename="yt_manager.log"
    )
