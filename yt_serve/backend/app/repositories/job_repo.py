"""
Job Data Access Repository
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import Job, get_db_context


class JobRepository:
    """Centralized repository for all Job state and stream progress tracking"""

    @staticmethod
    def get_by_id(job_id: int, db: Optional[Session] = None) -> Optional[Job]:
        """Fetch job by integer ID"""
        with get_db_context(db) as session:
            return session.query(Job).filter(Job.id == job_id).first()

    @staticmethod
    def get_active_jobs(db: Optional[Session] = None) -> List[Job]:
        """Fetch all currently running or pending jobs"""
        with get_db_context(db) as session:
            return session.query(Job).filter(
                Job.status.in_(["pending", "running", "in_progress"])
            ).all()

    @staticmethod
    def create(
        playlist_id: int,
        job_type: str,
        total_items: int = 0,
        db: Optional[Session] = None
    ) -> Job:
        """Create a new job record"""
        with get_db_context(db) as session:
            job = Job(
                playlist_id=playlist_id,
                job_type=job_type,
                status="pending",
                total_items=total_items,
                completed_items=0,
                failed_items=0,
                download_status="pending",
                download_total=total_items,
                download_completed=0,
                download_failed=0,
                extract_status="pending",
                extract_total=total_items,
                extract_completed=0,
                extract_failed=0,
                created_at=datetime.utcnow()
            )
            session.add(job)
            session.flush()
            session.refresh(job)
            return job

    @staticmethod
    def update_status(
        job_id: int,
        status: str,
        completed_items: Optional[int] = None,
        failed_items: Optional[int] = None,
        error: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Optional[Job]:
        """Update job lifecycle status and counts"""
        with get_db_context(db) as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                return None
            job.status = status
            if completed_items is not None:
                job.completed_items = completed_items
            if failed_items is not None:
                job.failed_items = failed_items
            if error is not None:
                job.error = error
            if status in ("completed", "failed", "cancelled"):
                job.completed_at = datetime.utcnow()
            return job

    @staticmethod
    def update_stream_progress(
        job_id: int,
        title: Optional[str] = None,
        video_id: Optional[str] = None,
        bytes_downloaded: Optional[int] = None,
        bytes_total: Optional[int] = None,
        speed: Optional[float] = None,
        eta: Optional[int] = None,
        db: Optional[Session] = None
    ) -> Optional[Job]:
        """Update in-flight byte stream metrics for reconnect recovery"""
        with get_db_context(db) as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                return None
            if title is not None:
                job.current_video_title = title
            if video_id is not None:
                job.current_video_id = video_id
            if bytes_downloaded is not None:
                job.current_video_bytes_downloaded = bytes_downloaded
            if bytes_total is not None:
                job.current_video_bytes_total = bytes_total
            if speed is not None:
                job.current_video_speed = speed
            if eta is not None:
                job.current_video_eta = eta
            return job
