"""
Startup Recovery Engine for yt_serve:
Reconciles system state after container boot, server restarts, or abrupt power loss.
"""
import os
import time
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.database import Job, Playlist
from app.repositories import JobRepository, PlaylistRepository

logger = logging.getLogger(__name__)

class RecoveryService:
    @staticmethod
    def recover_interrupted_jobs(db: Session) -> List[Job]:
        """
        Inspects and flags download/extract jobs interrupted by container shutdown/crash.
        Jobs left in 'running' state are flagged for the UI recovery dialog.
        """
        logger.info("[RECOVERY] Checking for interrupted jobs...")
        try:
            interrupted_jobs = JobRepository.get_interrupted(db=db)
            if interrupted_jobs:
                logger.warning(f"[RECOVERY] Found {len(interrupted_jobs)} interrupted job(s):")
                playlists_map = {p.id: p for p in PlaylistRepository.get_all(db=db)}
                for job in interrupted_jobs:
                    playlist = playlists_map.get(job.playlist_id)
                    title = playlist.title if playlist else f"Playlist #{job.playlist_id}"
                    logger.warning(f"  - Job #{job.id}: {job.job_type} for '{title}' (started {job.created_at})")
                logger.info("[RECOVERY] Interrupted jobs will be presented to the user via the UI recovery dialog.")
            else:
                logger.info("[RECOVERY] No interrupted jobs found.")
            return interrupted_jobs
        except Exception as e:
            logger.error(f"[RECOVERY] Error inspecting interrupted jobs: {e}")
            return []

    @staticmethod
    def recover_git_metadata(base_path: str) -> bool:
        """
        Inspects local Git repository for stale locks (.git/index.lock) or uncommitted
        playlist metadata left on disk from a prior crash/restart, and commits them cleanly.
        """
        if not getattr(settings, "ENABLE_GIT_METADATA_SYNC", False):
            return False

        logger.info("[RECOVERY] Checking Git repository for uncommitted metadata or stale locks...")
        try:
            from app.utils.git_sync import reconcile_uncommitted_metadata
            reconciled = reconcile_uncommitted_metadata(base_path)
            if reconciled:
                logger.info("[RECOVERY] ✓ Git repository state reconciled successfully.")
            else:
                logger.info("[RECOVERY] Git repository is clean.")
            return reconciled
        except Exception as e:
            logger.error(f"[RECOVERY] Git metadata recovery error: {e}")
            return False

    @staticmethod
    def cleanup_temp_artifacts(temp_path: Optional[str]) -> int:
        """
        Safely sweeps temporary download directory for abandoned .part or .ytdl files older than 1 hour.
        """
        if not temp_path or not os.path.isdir(temp_path):
            return 0

        logger.info(f"[RECOVERY] Checking temporary download directory: {temp_path}")
        removed_count = 0
        now = time.time()
        try:
            for root, _, files in os.walk(temp_path):
                for f in files:
                    if f.endswith((".part", ".ytdl", ".temp")):
                        full_path = os.path.join(root, f)
                        try:
                            # Only remove if file has not been modified for at least 1 hour (3600s)
                            if (now - os.path.getmtime(full_path)) > 3600:
                                os.remove(full_path)
                                removed_count += 1
                                logger.info(f"[RECOVERY] Removed abandoned temp file: {f}")
                        except Exception as file_err:
                            logger.warning(f"[RECOVERY] Could not remove temp file {full_path}: {file_err}")
            if removed_count > 0:
                logger.info(f"[RECOVERY] Cleaned up {removed_count} abandoned temp artifact(s).")
            else:
                logger.info("[RECOVERY] No abandoned temp artifacts found.")
        except Exception as e:
            logger.warning(f"[RECOVERY] Temp cleanup scan encountered an issue: {e}")
        return removed_count

    @classmethod
    async def run_startup_recovery(cls, db: Session):
        """
        Orchestrates all recovery phases sequentially before normal application operations begin.
        """
        logger.info("=" * 60)
        logger.info("[STARTUP RECOVERY] Initializing crash recovery engine...")
        logger.info("=" * 60)

        # 1. Inspect interrupted jobs
        cls.recover_interrupted_jobs(db)

        # 2. Reconcile Git repository locks and uncommitted metadata
        cls.recover_git_metadata(settings.BASE_DOWNLOAD_PATH)

        # 3. Clean up abandoned temporary download fragments from crash
        cls.cleanup_temp_artifacts(settings.TEMP_DOWNLOAD_PATH)

        # 4. Safely purge phantom database records (e.g., test_custom, _adhoc_downloads) without touching disk files
        cls.cleanup_phantom_playlists(db)

        logger.info("=" * 60)
        logger.info("[STARTUP RECOVERY] Recovery checks completed.")
        logger.info("=" * 60)

    @classmethod
    def cleanup_phantom_playlists(cls, db: Session) -> int:
        """
        Safely purges phantom database entries (e.g. from empty directories or adhoc download folders)
        where valid playlist metadata was never generated.
        GUARANTEE: Purely removes database rows; NEVER deletes or touches physical files/folders on disk.
        """
        purged_count = 0
        try:
            excluded = settings.get_excluded_directories()
            candidates = PlaylistRepository.get_phantom_candidates(
                excluded_dirs=excluded,
                base_download_path=settings.BASE_DOWNLOAD_PATH,
                db=db
            )

            for pl in candidates:
                logger.info(f"[RECOVERY] Safely purging phantom database playlist #{pl.id} '{pl.title}' ({pl.url}) - files on disk are preserved.")
                PlaylistRepository.delete(pl.id, db=db)
                purged_count += 1

            if purged_count > 0:
                logger.info(f"[RECOVERY] ✓ Safely purged {purged_count} phantom playlist record(s) from database.")
        except Exception as e:
            logger.warning(f"[RECOVERY] Note during phantom playlist cleanup: {e}")
            db.rollback()
        return purged_count
