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
    def get_active_job_for_playlist(playlist_id: int, db: Optional[Session] = None) -> Optional[Job]:
        """Fetch active (pending or running) job for a specific playlist"""
        with get_db_context(db) as session:
            return session.query(Job).filter(
                Job.playlist_id == playlist_id,
                Job.status.in_(["pending", "running", "in_progress"])
            ).first()

    @staticmethod
    def get_all(
        playlist_id: Optional[int] = None,
        status: Optional[str] = None,
        limit: Optional[int] = None,
        db: Optional[Session] = None
    ) -> List[Job]:
        """Fetch jobs with optional playlist and status filters, newest first"""
        with get_db_context(db) as session:
            query = session.query(Job)
            if playlist_id is not None:
                query = query.filter(Job.playlist_id == playlist_id)
            if status is not None:
                query = query.filter(Job.status == status)
            query = query.order_by(Job.created_at.desc())
            if limit:
                query = query.limit(limit)
            return query.all()

    @staticmethod
    def get_interrupted(db: Optional[Session] = None) -> List[Job]:
        """Fetch interrupted (running) jobs needing startup recovery"""
        with get_db_context(db) as session:
            return session.query(Job).filter(Job.status == "running").all()

    @staticmethod
    def create(
        playlist_id: int,
        job_type: str,
        total_items: int = 0,
        db: Optional[Session] = None
    ) -> Job:
        """Create a new job record with durable commit"""
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
            session.commit()
            session.refresh(job)
            return job

    @staticmethod
    def update_status(
        job_id: int,
        status: Optional[str] = None,
        download_status: Optional[str] = None,
        extract_status: Optional[str] = None,
        completed_items: Optional[int] = None,
        failed_items: Optional[int] = None,
        error: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Optional[Job]:
        """Update job lifecycle status, counts, and commit"""
        with get_db_context(db) as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                return None
            if status is not None:
                job.status = status
                if status == "running" and not job.started_at:
                    job.started_at = datetime.utcnow()
                if status in ("completed", "failed", "cancelled"):
                    job.completed_at = datetime.utcnow()
            if download_status is not None:
                job.download_status = download_status
            if extract_status is not None:
                job.extract_status = extract_status
            if completed_items is not None:
                job.completed_items = completed_items
            if failed_items is not None:
                job.failed_items = failed_items
            if error is not None:
                job.error = error
            session.commit()
            session.refresh(job)
            return job

    @staticmethod
    def update_progress(
        job_id: int,
        download_total: Optional[int] = None,
        download_completed: Optional[int] = None,
        download_failed: Optional[int] = None,
        download_status: Optional[str] = None,
        download_batch_info: Optional[str] = None,
        extract_total: Optional[int] = None,
        extract_completed: Optional[int] = None,
        extract_failed: Optional[int] = None,
        extract_status: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Optional[Job]:
        """Update download/extract phase progress numbers and status"""
        with get_db_context(db) as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                return None
            if download_total is not None:
                job.download_total = download_total
            if download_completed is not None:
                job.download_completed = download_completed
            if download_failed is not None:
                job.download_failed = download_failed
            if download_status is not None:
                job.download_status = download_status
            if download_batch_info is not None:
                job.download_batch_info = download_batch_info
            if extract_total is not None:
                job.extract_total = extract_total
            if extract_completed is not None:
                job.extract_completed = extract_completed
            if extract_failed is not None:
                job.extract_failed = extract_failed
            if extract_status is not None:
                job.extract_status = extract_status
            session.commit()
            session.refresh(job)
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
        """Update in-flight byte stream metrics with commit for live polling and reconnect recovery"""
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
            session.commit()
            session.refresh(job)
            return job

    @staticmethod
    def count_active(db: Optional[Session] = None) -> int:
        """Count currently running or pending jobs"""
        with get_db_context(db) as session:
            return session.query(Job).filter(
                Job.status.in_(["pending", "running", "in_progress"])
            ).count()

    @staticmethod
    def count_jobs(
        playlist_id: Optional[int] = None,
        status: Optional[str] = None,
        db: Optional[Session] = None
    ) -> int:
        """Count jobs matching optional playlist or status filters"""
        with get_db_context(db) as session:
            query = session.query(Job)
            if playlist_id is not None:
                query = query.filter(Job.playlist_id == playlist_id)
            if status is not None:
                query = query.filter(Job.status == status)
            return query.count()

    @staticmethod
    def get_stats_by_type_and_status(db: Optional[Session] = None) -> List[Any]:
        """Get job counts grouped by job_type and status for metrics"""
        from sqlalchemy import func
        with get_db_context(db) as session:
            return session.query(
                Job.job_type, Job.status, func.count(Job.id)
            ).group_by(Job.job_type, Job.status).all()

    @staticmethod
    def delete(job_id: int, db: Optional[Session] = None) -> bool:
        """Delete a job record by ID"""
        with get_db_context(db) as session:
            job = session.query(Job).filter(Job.id == job_id).first()
            if not job:
                return False
            session.delete(job)
            session.commit()
            return True

