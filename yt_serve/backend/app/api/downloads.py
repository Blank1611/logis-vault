"""
Download management API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from typing import List, Optional
from pydantic import BaseModel
from enum import Enum
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.database import get_db
from app.repositories import JobRepository, PlaylistRepository, TrackRepository
from app.services.job_manager import job_manager
from app.services.ytdlp_service import DownloadService
from app.api.websocket import manager as ws_manager
from app.core.config import settings

router = APIRouter()

class JobStatus(str, Enum):
    """Job status enum"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobType(str, Enum):
    """Job type enum"""
    DOWNLOAD = "download"
    EXTRACT = "extract"
    BOTH = "both"

class JobResponse(BaseModel):
    """Job response model"""
    id: int
    playlist_id: int
    job_type: str
    status: str
    progress: float
    total_items: int
    completed_items: int
    failed_items: int
    
    # Separate download progress
    download_status: Optional[str]
    download_total: int
    download_completed: int
    download_failed: int
    download_batch_info: Optional[str]
    
    # Separate extraction progress
    extract_status: Optional[str]
    extract_total: int
    extract_completed: int
    extract_failed: int
    
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    error: Optional[str]

    # In-flight active video stream telemetry
    current_video_title: Optional[str] = None
    current_video_id: Optional[str] = None
    current_video_bytes_downloaded: Optional[int] = None
    current_video_bytes_total: Optional[int] = None
    current_video_speed: Optional[float] = None
    current_video_eta: Optional[int] = None

    class Config:
        from_attributes = True

class JobCreate(BaseModel):
    """Job creation model"""
    playlist_id: int
    job_type: JobType
    target_format: Optional[str] = None

class LogEntry(BaseModel):
    """Log entry model"""
    message: str

def get_download_service() -> DownloadService:
    """Get download service instance"""
    return DownloadService(settings.BASE_DOWNLOAD_PATH, {
        "audio_extract_mode": settings.AUDIO_EXTRACT_MODE,
        "max_extraction_workers": settings.MAX_CONCURRENT_EXTRACTIONS,
        "batch_size": settings.BATCH_SIZE,
        "use_browser_cookies": settings.USE_BROWSER_COOKIES,
        "browser_name": settings.BROWSER_NAME,
        "cookies_file": settings.COOKIES_FILE,
    })

@router.get("/jobs", response_model=List[JobResponse])
@router.get("/jobs/", response_model=List[JobResponse])
async def list_jobs(
    status: Optional[str] = None,
    playlist_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    jobs = JobRepository.get_all(playlist_id=playlist_id, status=status, db=db)
    
    result = []
    for job in jobs:
        result.append(JobResponse(
            id=job.id,
            playlist_id=job.playlist_id,
            job_type=job.job_type,
            status=job.status,
            progress=job.progress,
            total_items=job.total_items,
            completed_items=job.completed_items,
            failed_items=job.failed_items,
            download_status=job.download_status,
            download_total=job.download_total,
            download_completed=job.download_completed,
            download_failed=job.download_failed,
            download_batch_info=job.download_batch_info,
            extract_status=job.extract_status,
            extract_total=job.extract_total,
            extract_completed=job.extract_completed,
            extract_failed=job.extract_failed,
            created_at=job.created_at.isoformat(),
            started_at=job.started_at.isoformat() if job.started_at else None,
            completed_at=job.completed_at.isoformat() if job.completed_at else None,
            error=job.error,
            current_video_title=job.current_video_title,
            current_video_id=job.current_video_id,
            current_video_bytes_downloaded=job.current_video_bytes_downloaded,
            current_video_bytes_total=job.current_video_bytes_total,
            current_video_speed=job.current_video_speed,
            current_video_eta=job.current_video_eta
        ))
    
    return result

@router.post("/jobs", response_model=JobResponse, status_code=201)
@router.post("/jobs/", response_model=JobResponse, status_code=201)
async def create_job(
    job: JobCreate,
    db: Session = Depends(get_db)
):
    """Create a new download/extract job"""
    from app.services.scheduler import is_scheduler_scanning
    if is_scheduler_scanning():
        raise HTTPException(
            status_code=409,
            detail="Daily scheduled metadata scan is currently in progress. Please wait for it to complete."
        )

    # Check if playlist exists
    playlist = PlaylistRepository.get_by_id(job.playlist_id, db=db)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    # Check if there's already a running job for this playlist
    existing_job = JobRepository.get_active_job_for_playlist(job.playlist_id, db=db)
    
    if existing_job:
        raise HTTPException(
            status_code=400,
            detail=f"Job {existing_job.id} is already running for this playlist"
        )
    
    # Create download service
    download_service = get_download_service()
    
    # Create callbacks for WebSocket
    async def log_callback(job_id, message):
        await ws_manager.send_message({
            "type": "log",
            "message": message,
            "timestamp": str(datetime.utcnow())
        }, job_id)
    
    async def progress_callback(job_id, progress, completed, total):
        await ws_manager.send_message({
            "type": "progress",
            "progress": progress,
            "completed": completed,
            "total": total
        }, job_id)
    
    # Create and start job
    job_id = await job_manager.create_download_job(
        db,
        job.playlist_id,
        job.job_type.value,
        download_service,
        log_callback,
        progress_callback,
        target_format=job.target_format
    )
    
    # Return job
    db_job = JobRepository.get_by_id(job_id, db=db)
    
    return JobResponse(
        id=db_job.id,
        playlist_id=db_job.playlist_id,
        job_type=db_job.job_type,
        status=db_job.status,
        progress=db_job.progress,
        total_items=db_job.total_items,
        completed_items=db_job.completed_items,
        failed_items=db_job.failed_items,
        download_status=db_job.download_status,
        download_total=db_job.download_total,
        download_completed=db_job.download_completed,
        download_failed=db_job.download_failed,
        download_batch_info=db_job.download_batch_info,
        extract_status=db_job.extract_status,
        extract_total=db_job.extract_total,
        extract_completed=db_job.extract_completed,
        extract_failed=db_job.extract_failed,
        created_at=db_job.created_at.isoformat(),
        started_at=db_job.started_at.isoformat() if db_job.started_at else None,
        completed_at=db_job.completed_at.isoformat() if db_job.completed_at else None,
        error=db_job.error,
        current_video_title=db_job.current_video_title,
        current_video_id=db_job.current_video_id,
        current_video_bytes_downloaded=db_job.current_video_bytes_downloaded,
        current_video_bytes_total=db_job.current_video_bytes_total,
        current_video_speed=db_job.current_video_speed,
        current_video_eta=db_job.current_video_eta
    )

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    job = JobRepository.get_by_id(job_id, db=db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobResponse(
        id=job.id,
        playlist_id=job.playlist_id,
        job_type=job.job_type,
        status=job.status,
        progress=job.progress,
        total_items=job.total_items,
        completed_items=job.completed_items,
        failed_items=job.failed_items,
        download_status=job.download_status,
        download_total=job.download_total,
        download_completed=job.download_completed,
        download_failed=job.download_failed,
        download_batch_info=job.download_batch_info,
        extract_status=job.extract_status,
        extract_total=job.extract_total,
        extract_completed=job.extract_completed,
        extract_failed=job.extract_failed,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error=job.error,
        current_video_title=job.current_video_title,
        current_video_id=job.current_video_id,
        current_video_bytes_downloaded=job.current_video_bytes_downloaded,
        current_video_bytes_total=job.current_video_bytes_total,
        current_video_speed=job.current_video_speed,
        current_video_eta=job.current_video_eta
    )

@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: int, db: Session = Depends(get_db)):
    """Cancel a running job"""
    job = JobRepository.get_by_id(job_id, db=db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status not in ["pending", "running"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel job with status: {job.status}"
        )
    
    # Cancel the job
    await job_manager.cancel_job(job_id)
    
    return {"message": "Job cancellation requested", "job_id": job_id}

@router.get("/jobs/{job_id}/logs", response_model=List[LogEntry])
async def get_job_logs(
    job_id: int,
    lines: Optional[int] = 100,
    db: Session = Depends(get_db)
):
    """Get job logs from file system"""
    job = JobRepository.get_by_id(job_id, db=db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get logs from file system
    log_lines = job_manager.get_job_logs(job_id, lines)
    
    return [
        LogEntry(message=line.strip())
        for line in log_lines
    ]

@router.get("/jobs/{job_id}/download-log")
async def download_job_log(
    job_id: int,
    db: Session = Depends(get_db)
):
    """Download raw log file for a job"""
    from fastapi.responses import FileResponse
    job = JobRepository.get_by_id(job_id, db=db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    log_file = job_manager._get_log_file_path(job_id)
    if not os.path.isfile(log_file):
        raise HTTPException(status_code=404, detail="Log file does not exist for this job")
        
    return FileResponse(
        path=log_file,
        filename=f"job_{job_id}.log",
        media_type="text/plain"
    )

# ============================================================================
# INTERRUPTED JOBS ENDPOINTS (for UI-based recovery dialog)
# ============================================================================

class InterruptedJobInfo(BaseModel):
    """Information about an interrupted job"""
    id: int
    job_type: str
    playlist_id: int
    playlist_title: str
    created_at: str

class InterruptedJobsResponse(BaseModel):
    """Response containing interrupted jobs"""
    jobs: List[InterruptedJobInfo]
    count: int

class JobRecoveryRequest(BaseModel):
    """Request to handle interrupted jobs"""
    action: str  # 'resume_all', 'cancel_all', or 'individual'
    job_decisions: Optional[dict] = None  # For individual: {job_id: 'resume' or 'cancel'}

class JobRecoveryResponse(BaseModel):
    """Response after handling interrupted jobs"""
    message: str
    processed: int
    resumed: int
    cancelled: int

@router.get("/interrupted-jobs", response_model=InterruptedJobsResponse)
async def get_interrupted_jobs(db: Session = Depends(get_db)):
    """
    Get all interrupted jobs (jobs with 'running' status).
    Called on app initialization to check for jobs that didn't complete.
    """
    interrupted_jobs = JobRepository.get_interrupted(db=db)
    
    jobs_info = []
    for job in interrupted_jobs:
        playlist = PlaylistRepository.get_by_id(job.playlist_id, db=db)
        playlist_title = playlist.title if playlist else "Unknown Playlist"
        jobs_info.append(InterruptedJobInfo(
            id=job.id,
            job_type=job.job_type,
            playlist_id=job.playlist_id,
            playlist_title=playlist_title,
            created_at=job.created_at.isoformat()
        ))
    
    return InterruptedJobsResponse(
        jobs=jobs_info,
        count=len(jobs_info)
    )

@router.post("/handle-interrupted-jobs", response_model=JobRecoveryResponse)
async def handle_interrupted_jobs(
    request: JobRecoveryRequest,
    db: Session = Depends(get_db)
):
    """
    Handle interrupted jobs based on user decision from UI dialog.
    Supports three actions:
    - resume_all: Resume all interrupted jobs
    - cancel_all: Cancel all interrupted jobs
    - individual: Handle each job based on decision map
    """
    interrupted_jobs = JobRepository.get_interrupted(db=db)
    
    if not interrupted_jobs:
        return JobRecoveryResponse(
            message="No interrupted jobs found",
            processed=0,
            resumed=0,
            cancelled=0
        )
    
    from app.services.job_manager import JobManager
    job_manager_svc = JobManager()
    
    resumed_count = 0
    cancelled_count = 0
    
    if request.action == 'resume_all':
        # Resume all interrupted jobs
        for job in interrupted_jobs:
            try:
                JobRepository.update_status(job.id, status='pending', error=None, db=db)
                # Start the job in background using singleton job_manager
                await job_manager.start_job(job.id)
                resumed_count += 1
            except Exception as e:
                JobRepository.update_status(job.id, status='failed', error=f"Failed to resume: {str(e)}", db=db)
    
    elif request.action == 'cancel_all':
        # Cancel all interrupted jobs
        for job in interrupted_jobs:
            JobRepository.update_status(job.id, status='cancelled', error='Cancelled by user during startup', db=db)
            cancelled_count += 1
    
    elif request.action == 'individual' and request.job_decisions:
        # Handle each job individually based on user decisions
        for job in interrupted_jobs:
            decision = request.job_decisions.get(str(job.id))
            
            if decision == 'resume':
                try:
                    JobRepository.update_status(job.id, status='pending', error=None, db=db)
                    await job_manager.start_job(job.id)
                    resumed_count += 1
                except Exception as e:
                    JobRepository.update_status(job.id, status='failed', error=f"Failed to resume: {str(e)}", db=db)
            
            elif decision == 'cancel':
                JobRepository.update_status(job.id, status='cancelled', error='Cancelled by user during startup', db=db)
                cancelled_count += 1
    
    else:
        raise HTTPException(
            status_code=400,
            detail="Invalid action. Must be 'resume_all', 'cancel_all', or 'individual'"
        )
    
    return JobRecoveryResponse(
        message=f"Successfully handled {len(interrupted_jobs)} interrupted job(s)",
        processed=len(interrupted_jobs),
        resumed=resumed_count,
        cancelled=cancelled_count
    )

class IntegrityTestRequest(BaseModel):
    file_path: Optional[str] = None
    playlist_id: Optional[int] = None
    video_id: Optional[str] = None

class IntegrityTestResponse(BaseModel):
    file_path: str
    valid: bool
    has_video: bool
    has_audio: bool
    duration: Optional[float] = None
    error: Optional[str] = None
    details: dict

@router.post("/test-integrity", response_model=IntegrityTestResponse)
async def test_integrity(
    request: IntegrityTestRequest,
    db: Session = Depends(get_db)
):
    """
    Test stream integrity for a specific video file or playlist video.
    Safeguard 2 testing tool using ffprobe.
    """
    from app.core import yt_playlist_audio_tools as tools
    import os
    
    file_to_check = request.file_path
    
    if not file_to_check and request.playlist_id and request.video_id:
        playlist = PlaylistRepository.get_by_id(request.playlist_id, db=db)
        if not playlist:
            raise HTTPException(status_code=404, detail="Playlist not found")
        safe_title = tools._sanitize_title(playlist.title)
        playlist_folder = os.path.join(settings.BASE_DOWNLOAD_PATH, safe_title)
        file_to_check = tools._get_video_file_path(playlist_folder, request.video_id, wait_for_file=False)
        if not file_to_check:
            raise HTTPException(status_code=404, detail=f"No video file found for video ID {request.video_id}")
            
    if not file_to_check or not os.path.isfile(file_to_check):
        raise HTTPException(status_code=400, detail="Invalid file path or file not found")
        
    result = tools._verify_video_stream_integrity(file_to_check)
    
    return IntegrityTestResponse(
        file_path=file_to_check,
        valid=result.get("valid", True),
        has_video=result.get("has_video", False),
        has_audio=result.get("has_audio", False),
        duration=result.get("duration"),
        error=result.get("error"),
        details=result.get("details", {})
    )


# ==============================================================================
# Ad-hoc / Quick Single-Video Download Endpoints
# ==============================================================================

class AdhocProbeRequest(BaseModel):
    url: str


class AdhocDownloadRequest(BaseModel):
    url: str
    video_quality: Optional[str] = "best"
    audio_format: Optional[str] = "copy"
    extract_mode: Optional[str] = "both"  # video_only, audio_only, both
    custom_download_path: Optional[str] = None


@router.post("/adhoc/probe")
async def probe_adhoc_video(req: AdhocProbeRequest):
    """
    Probe single YouTube video URL without downloading.
    Returns title, thumbnail, duration, and available resolution options.
    """
    from app.services.adhoc_service import probe_video_info
    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="YouTube video URL is required")
    res = probe_video_info(req.url.strip())
    if res.get("status") == "error":
        raise HTTPException(status_code=400, detail=res.get("message", "Failed to probe video"))
    return res


@router.post("/adhoc/start")
async def start_adhoc_download(
    req: AdhocDownloadRequest,
    db: Session = Depends(get_db)
):
    """
    Start asynchronous ad-hoc single video download and optional audio extraction.
    Creates a background Job tracked in the shared Job queue and managed by JobManager.
    """
    from app.repositories import JobRepository

    if not req.url or not req.url.strip():
        raise HTTPException(status_code=400, detail="YouTube video URL is required")

    job = JobRepository.create(
        playlist_id=0,
        job_type=f"adhoc_{req.extract_mode}",
        total_items=1,
        db=db
    )

    # Launch via JobManager to enforce concurrency semaphore and per-job log writing
    await job_manager.start_adhoc_job(
        job_id=job.id,
        url=req.url.strip(),
        video_quality=req.video_quality or "best",
        audio_format=req.audio_format or "copy",
        extract_mode=req.extract_mode or "both",
        custom_download_path=req.custom_download_path
    )

    return {
        "status": "started",
        "job_id": job.id,
        "job_type": job.job_type,
        "message": "Ad-hoc download enqueued successfully."
    }


@router.get("/adhoc/{job_id}/download")
async def download_adhoc_file(job_id: int, db: Session = Depends(get_db)):
    """
    Direct browser download of completed ad-hoc media (audio or video).
    """
    import os
    job = JobRepository.get_by_id(job_id, db=db)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="Job is not completed yet")
    
    file_to_send = None
    if job.current_video_id:
        track = TrackRepository.get_by_video_id(job.current_video_id, db=db)
        if track:
            if "audio" in (job.job_type or "") and track.primary_audio_filepath and os.path.isfile(track.primary_audio_filepath):
                file_to_send = track.primary_audio_filepath
            elif track.primary_filepath and os.path.isfile(track.primary_filepath):
                file_to_send = track.primary_filepath
            elif track.primary_audio_filepath and os.path.isfile(track.primary_audio_filepath):
                file_to_send = track.primary_audio_filepath

    if not file_to_send and job.current_video_title:
        candidate = os.path.join(settings.get_adhoc_download_path(), job.current_video_title)
        if os.path.isfile(candidate):
            file_to_send = candidate

    if not file_to_send:
        adhoc_dir = settings.get_adhoc_download_path()
        info_json = os.path.join(adhoc_dir, "adhoc_info.json")
        if os.path.isfile(info_json):
            try:
                import json
                with open(info_json, "r", encoding="utf-8") as f:
                    entries = json.load(f)
                    for item in entries:
                        if item.get("id") == job.current_video_id:
                            if "audio" in (job.job_type or "") and item.get("audio_filepath") and os.path.isfile(item["audio_filepath"]):
                                file_to_send = item["audio_filepath"]
                            elif item.get("filepath") and os.path.isfile(item["filepath"]):
                                file_to_send = item["filepath"]
                            elif item.get("audio_filepath") and os.path.isfile(item["audio_filepath"]):
                                file_to_send = item["audio_filepath"]
                            break
            except Exception:
                pass

    if not file_to_send or not os.path.isfile(file_to_send):
        raise HTTPException(status_code=404, detail="Downloaded media file not found on server")

    filename = os.path.basename(file_to_send)
    return FileResponse(
        path=file_to_send,
        filename=filename,
        media_type="application/octet-stream"
    )


