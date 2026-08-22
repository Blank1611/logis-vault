"""
Download management API endpoints
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
from enum import Enum
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.database import get_db, Job, Playlist
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
    
    class Config:
        from_attributes = True

class JobCreate(BaseModel):
    """Job creation model"""
    playlist_id: int
    job_type: JobType

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
async def list_jobs(
    status: Optional[str] = None,
    playlist_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get all jobs with optional filters"""
    query = db.query(Job)
    
    if status:
        query = query.filter(Job.status == status)
    if playlist_id:
        query = query.filter(Job.playlist_id == playlist_id)
    
    jobs = query.order_by(Job.created_at.desc()).all()
    
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
            error=job.error
        ))
    
    return result

@router.post("/jobs", response_model=JobResponse, status_code=201)
async def create_job(
    job: JobCreate,
    db: Session = Depends(get_db)
):
    """Create a new download/extract job"""
    # Check if playlist exists
    playlist = db.query(Playlist).filter(Playlist.id == job.playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    # Check if there's already a running job for this playlist
    existing_job = db.query(Job).filter(
        Job.playlist_id == job.playlist_id,
        Job.status.in_(["pending", "running"])
    ).first()
    
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
        progress_callback
    )
    
    # Return job
    db_job = db.query(Job).filter(Job.id == job_id).first()
    
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
        error=db_job.error
    )

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    """Get job by ID"""
    job = db.query(Job).filter(Job.id == job_id).first()
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
        error=job.error
    )

@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: int, db: Session = Depends(get_db)):
    """Cancel a running job"""
    job = db.query(Job).filter(Job.id == job_id).first()
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
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get logs from file system
    log_lines = job_manager.get_job_logs(job_id, lines)
    
    return [
        LogEntry(message=line.strip())
        for line in log_lines
    ]

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
    interrupted_jobs = db.query(Job).filter(Job.status == 'running').all()
    
    jobs_info = []
    for job in interrupted_jobs:
        #playlist = db.query(Playlist).filter(Playlist.id == job.playlist_id).first()
        playlist = db.query(Playlist).filter(Playlist.id == job.playlist_id).first()
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
    interrupted_jobs = db.query(Job).filter(Job.status == 'running').all()
    
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
                job.status = 'pending'
                job.error_message = None
                db.commit()
                
                # Start the job in background
                await job_manager_svc.start_job(job.id)
                resumed_count += 1
            except Exception as e:
                job.status = 'failed'
                job.error_message = f"Failed to resume: {str(e)}"
                db.commit()
    
    elif request.action == 'cancel_all':
        # Cancel all interrupted jobs
        for job in interrupted_jobs:
            job.status = 'cancelled'
            job.error_message = 'Cancelled by user during startup'
            cancelled_count += 1
        db.commit()
    
    elif request.action == 'individual' and request.job_decisions:
        # Handle each job individually based on user decisions
        for job in interrupted_jobs:
            decision = request.job_decisions.get(str(job.id))
            
            if decision == 'resume':
                try:
                    job.status = 'pending'
                    job.error_message = None
                    db.commit()
                    await job_manager_svc.start_job(job.id)
                    resumed_count += 1
                except Exception as e:
                    job.status = 'failed'
                    job.error_message = f"Failed to resume: {str(e)}"
                    db.commit()
            
            elif decision == 'cancel':
                job.status = 'cancelled'
                job.error_message = 'Cancelled by user during startup'
                cancelled_count += 1
        
        db.commit()
    
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
