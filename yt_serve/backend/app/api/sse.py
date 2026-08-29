"""
Server-Sent Events (SSE) streaming endpoint for live job progress and telemetry.
Runs over standard HTTP/2 and supports native EventSource reconnection.
"""

import asyncio
import json
from datetime import datetime
from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.models.database import get_db, Job
from app.services.job_manager import job_manager

router = APIRouter()


async def job_event_generator(request: Request, job_id: int, db: Session) -> AsyncGenerator[str, None]:
    """
    Yields Server-Sent Events for a specific job:
    - Periodic in-flight byte progress and speeds
    - Job completion/failure/cancellation terminal states
    - Keep-alive heartbeat ping every 15s
    """
    last_log_count = 0
    last_ping_time = asyncio.get_event_loop().time()

    # Initial state push
    initial_job = db.query(Job).filter(Job.id == job_id).first()
    if not initial_job:
        yield f"event: error\ndata: {json.dumps({'error': f'Job {job_id} not found'})}\n\n"
        return

    progress_payload = {
        "job_id": initial_job.id,
        "status": initial_job.status,
        "download_status": initial_job.download_status,
        "download_completed": initial_job.download_completed,
        "download_total": initial_job.download_total,
        "extract_status": initial_job.extract_status,
        "extract_completed": initial_job.extract_completed,
        "extract_total": initial_job.extract_total,
        "current_video_title": initial_job.current_video_title,
        "current_video_id": initial_job.current_video_id,
        "bytes_downloaded": initial_job.current_video_bytes_downloaded or 0,
        "bytes_total": initial_job.current_video_bytes_total or 0,
        "speed": initial_job.current_video_speed or 0.0,
        "eta": initial_job.current_video_eta or 0,
    }
    yield f"event: progress\ndata: {json.dumps(progress_payload)}\n\n"

    try:
        while True:
            # Check if client disconnected
            if await request.is_disconnected():
                break

            # Poll latest job status
            db.expire_all()
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                break

            # Send telemetry progress tick
            progress_payload = {
                "job_id": job.id,
                "status": job.status,
                "download_status": job.download_status,
                "download_completed": job.download_completed,
                "download_total": job.download_total,
                "extract_status": job.extract_status,
                "extract_completed": job.extract_completed,
                "extract_total": job.extract_total,
                "current_video_title": job.current_video_title,
                "current_video_id": job.current_video_id,
                "bytes_downloaded": job.current_video_bytes_downloaded or 0,
                "bytes_total": job.current_video_bytes_total or 0,
                "speed": job.current_video_speed or 0.0,
                "eta": job.current_video_eta or 0,
            }
            yield f"event: progress\ndata: {json.dumps(progress_payload)}\n\n"

            # Check new logs
            logs = job_manager.get_job_logs(job_id)
            if len(logs) > last_log_count:
                new_logs = logs[last_log_count:]
                last_log_count = len(logs)
                for line in new_logs:
                    log_data = {
                        "job_id": job_id,
                        "message": line.strip(),
                        "timestamp": datetime.utcnow().isoformat()
                    }
                    yield f"event: log\ndata: {json.dumps(log_data)}\n\n"

            # Keep-alive heartbeat
            now = asyncio.get_event_loop().time()
            if now - last_ping_time >= 15.0:
                last_ping_time = now
                yield f": ping {datetime.utcnow().isoformat()}\n\n"

            # If job reached terminal state and logs drained, send terminal event and end
            if job.status in ["completed", "failed", "cancelled"]:
                terminal_data = {
                    "job_id": job_id,
                    "status": job.status,
                    "error": job.error
                }
                yield f"event: completed\ndata: {json.dumps(terminal_data)}\n\n"
                break

            await asyncio.sleep(0.3)

    except asyncio.CancelledError:
        pass


@router.get("/downloads/jobs/{job_id}/stream")
async def stream_job_events(job_id: int, request: Request, db: Session = Depends(get_db)):
    """
    Stream live dual-tier progress telemetry and logs for a job via Server-Sent Events (SSE).
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return StreamingResponse(
        job_event_generator(request, job_id, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )
