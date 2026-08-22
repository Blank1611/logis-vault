"""
Job manager for background download/extract tasks
"""
import asyncio
import os
from typing import Dict, Optional, Callable
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import Job, Playlist
from app.services.ytdlp_service import DownloadService
from app.core.config import settings

class JobManager:
    """Manages background jobs"""
    
    def __init__(self):
        self.active_jobs: Dict[int, asyncio.Task] = {}
        self.cancel_flags: Dict[int, bool] = {}
        self.download_services: Dict[int, DownloadService] = {}  # Track services for cancellation
        
        # Video extraction queue system (pub-sub)
        self.extraction_queues: Dict[int, asyncio.Queue] = {}  # job_id -> queue of video paths
        
        # Ensure logs directory exists
        self.logs_dir = os.path.join(settings.BASE_DOWNLOAD_PATH, "logs")
        os.makedirs(self.logs_dir, exist_ok=True)
        
        # Concurrency semaphore for video downloads
        self._download_semaphore: Optional[asyncio.Semaphore] = None
    
    def _get_download_semaphore(self) -> asyncio.Semaphore:
        """Get or initialize the global download concurrency semaphore"""
        if self._download_semaphore is None:
            max_concurrent = max(1, getattr(settings, "MAX_CONCURRENT_DOWNLOADS", 1))
            self._download_semaphore = asyncio.Semaphore(max_concurrent)
        return self._download_semaphore

    
    def _get_log_file_path(self, job_id: int) -> str:
        """Get log file path for a job"""
        return os.path.join(self.logs_dir, f"job_{job_id}.log")
    
    def _cleanup_old_logs(self, max_days: int = 30, max_files: int = 100):
        """Clean up old job log files to prevent infinite disk accumulation"""
        try:
            if not os.path.isdir(self.logs_dir):
                return
            now = time.time()
            log_files = []
            for fname in os.listdir(self.logs_dir):
                if fname.startswith("job_") and fname.endswith(".log"):
                    fpath = os.path.join(self.logs_dir, fname)
                    if os.path.isfile(fpath):
                        mtime = os.path.getmtime(fpath)
                        log_files.append((fpath, mtime))
            
            # Sort newest to oldest
            log_files.sort(key=lambda x: x[1], reverse=True)
            
            # Delete files older than max_days or exceeding max_files
            for idx, (fpath, mtime) in enumerate(log_files):
                age_days = (now - mtime) / 86400
                if age_days > max_days or idx >= max_files:
                    try:
                        os.remove(fpath)
                    except OSError:
                        pass
        except Exception as e:
            print(f"Warning during log cleanup: {e}")

    def _write_log(self, job_id: int, message: str, level: Optional[str] = None):
        """Write structured log message to file"""
        log_file = self._get_log_file_path(job_id)
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        
        # Infer level if not provided
        if not level:
            msg_lower = message.lower()
            if "⚠️" in message or "warn" in msg_lower:
                level = "WARN"
            elif "✗" in message or "error" in msg_lower or "failed" in msg_lower:
                level = "ERROR"
            elif "✓" in message or "completed" in msg_lower or "success" in msg_lower or "verified" in msg_lower:
                level = "SUCCESS"
            else:
                level = "INFO"
                
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")
    
    async def create_download_job(
        self,
        db: Session,
        playlist_id: int,
        job_type: str,
        download_service: DownloadService,
        log_callback: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None
    ) -> int:
        """
        Create and start a download job
        
        Args:
            db: Database session
            playlist_id: Playlist ID
            job_type: "download", "extract", or "both"
            download_service: Download service instance
            log_callback: Async function(job_id, message) for logs
            progress_callback: Async function(job_id, progress, completed, total) for progress
        
        Returns:
            Job ID
        """
        # Get playlist
        playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
        if not playlist:
            raise ValueError(f"Playlist {playlist_id} not found")
        
        # Periodic log cleanup
        self._cleanup_old_logs()
        
        # Create job with initialized status fields
        job = Job(
            playlist_id=playlist_id,
            job_type=job_type,
            status="pending",
            download_status="pending" if job_type in ["download", "both"] else None,
            extract_status="pending" if job_type in ["extract", "both"] else None,
            download_total=0,
            download_completed=0,
            extract_total=0,
            extract_completed=0
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        
        # Start job task
        task = asyncio.create_task(
            self._run_job(
                job.id,
                playlist,
                job_type,
                download_service,
                log_callback,
                progress_callback
            )
        )
        self.active_jobs[job.id] = task
        self.cancel_flags[job.id] = False
        self.download_services[job.id] = download_service  # Store for cancellation
        
        return job.id

    async def start_job(self, job_id: int) -> int:
        """
        Start or resume an existing job by ID
        """
        from app.models.database import SessionLocal
        from app.api.websocket import manager as ws_manager
        
        db = SessionLocal()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if not job:
                raise ValueError(f"Job {job_id} not found")
            
            playlist = db.query(Playlist).filter(Playlist.id == job.playlist_id).first()
            if not playlist:
                raise ValueError(f"Playlist {job.playlist_id} not found for job {job_id}")
            
            download_service = DownloadService(settings.BASE_DOWNLOAD_PATH, {
                "audio_extract_mode": settings.AUDIO_EXTRACT_MODE,
                "max_extraction_workers": settings.MAX_CONCURRENT_EXTRACTIONS,
                "batch_size": settings.BATCH_SIZE,
                "use_browser_cookies": settings.USE_BROWSER_COOKIES,
                "browser_name": settings.BROWSER_NAME,
                "cookies_file": settings.COOKIES_FILE,
            })
            
            async def log_callback(j_id, message):
                await ws_manager.send_message({
                    "type": "log",
                    "message": message,
                    "timestamp": str(datetime.utcnow())
                }, j_id)
            
            async def progress_callback(j_id, progress, completed, total):
                await ws_manager.send_message({
                    "type": "progress",
                    "progress": progress,
                    "completed": completed,
                    "total": total
                }, j_id)
            
            task = asyncio.create_task(
                self._run_job(
                    job.id,
                    playlist,
                    job.job_type,
                    download_service,
                    log_callback,
                    progress_callback
                )
            )
            self.active_jobs[job.id] = task
            self.cancel_flags[job.id] = False
            self.download_services[job.id] = download_service
            return job.id
        finally:
            db.close()

    
    async def _run_job(
        self,
        job_id: int,
        playlist: Playlist,
        job_type: str,
        download_service: DownloadService,
        log_callback: Optional[Callable],
        progress_callback: Optional[Callable]
    ):
        """Run a job with separate download and extraction progress"""
        from app.models.database import SessionLocal
        db = SessionLocal()
        
        try:
            # Query playlist once from this session and reuse it
            playlist_obj = db.query(Playlist).filter(Playlist.id == playlist.id).first()
            if not playlist_obj:
                raise Exception(f"Playlist {playlist.id} not found")
            
            # Update job status
            job = db.query(Job).filter(Job.id == job_id).first()
            job.status = "running"
            job.started_at = datetime.utcnow()
            db.commit()
            
            # Log start
            if log_callback:
                await log_callback(job_id, f"Starting {job_type} for playlist: {playlist.title}")
            
            # Create download progress wrapper
            async def download_progress_wrapper(total, current, batch_info=None):
                if self.cancel_flags.get(job_id):
                    raise asyncio.CancelledError("Job cancelled")
                
                # Update job download progress
                job = db.query(Job).filter(Job.id == job_id).first()
                job.download_total = total
                job.download_completed = current
                job.download_batch_info = batch_info
                job.download_status = "running"
                db.commit()
                
                # Callback
                if progress_callback:
                    await progress_callback(job_id, None, current, total)
            
            # Create extraction progress wrapper
            async def extract_progress_wrapper(total, current):
                if self.cancel_flags.get(job_id):
                    raise asyncio.CancelledError("Job cancelled")
                
                # Update job extraction progress
                job = db.query(Job).filter(Job.id == job_id).first()
                job.extract_total = total
                job.extract_completed = current
                job.extract_status = "running"
                db.commit()
                
                # Callback
                if progress_callback:
                    await progress_callback(job_id, None, current, total)
            
            # Create log wrapper
            async def log_wrapper(message):
                # Write to file
                self._write_log(job_id, message)
                
                # Send to WebSocket
                if log_callback:
                    await log_callback(job_id, message)
            
            # Execute job based on type
            if job_type == "download":
                # Download only
                job.download_status = "pending"
                db.commit()
                
                await log_wrapper("Waiting for download slot in queue...")
                async with self._get_download_semaphore():
                    job.download_status = "running"
                    db.commit()
                    await log_wrapper("Starting download...")
                    
                    failed_ids = await download_service.download_playlist(
                        playlist.url,
                        set(playlist.excluded_ids or []),
                        progress_callback=download_progress_wrapper,
                        log_callback=log_wrapper
                    )
                
                # Update playlist
                playlist.last_download = datetime.utcnow()
                
                # Add failed IDs to exclusions
                if failed_ids:
                    existing = set(playlist.excluded_ids or [])
                    playlist.excluded_ids = list(existing.union(failed_ids))
                
                job.download_status = "completed"
                job.download_failed = len(failed_ids)
                db.commit()
                
                await log_wrapper(f"Download completed. Failed: {len(failed_ids)}")
            
            elif job_type == "extract":
                # Extract only
                job.extract_status = "pending"
                db.commit()
                
                await log_wrapper("Starting audio extraction...")
                
                await download_service.extract_audio(
                    playlist.title,
                    progress_callback=extract_progress_wrapper,
                    log_callback=log_wrapper
                )
                
                # Update playlist
                playlist.last_extract = datetime.utcnow()
                job.extract_status = "completed"
                db.commit()
                
                await log_wrapper("Audio extraction completed")
            
            elif job_type == "both":
                # Download and extract in parallel
                job.download_status = "pending"
                job.extract_status = "pending"
                db.commit()
                
                await log_wrapper("Starting download and extraction...")
                
                # CREATE EXTRACTION QUEUE FIRST - Must happen before download starts
                # This prevents race condition where download publishes to queue before it exists
                self.extraction_queues[job_id] = asyncio.Queue()
                await log_wrapper("Extraction queue created")
                
                # Start download task
                download_task = asyncio.create_task(
                    self._run_download_phase(
                        job_id, playlist_obj, download_service,
                        download_progress_wrapper, log_wrapper, db
                    )
                )
                
                # Start extraction task (will wait for videos to be available)
                extract_task = asyncio.create_task(
                    self._run_extraction_phase(
                        job_id, playlist_obj, download_service,
                        extract_progress_wrapper, log_wrapper, db
                    )
                )
                
                # Wait for both to complete
                await asyncio.gather(download_task, extract_task)
            
            # Final stats refresh after job completion
            await log_wrapper("Refreshing final stats...")
            try:
                # Refresh stats on the same playlist object
                local_count, available_count, unavailable_count = await download_service.get_playlist_stats(
                    playlist_obj.title,
                    playlist_obj.url,
                    playlist_obj.excluded_ids or []
                )
                
                playlist_obj.local_count = local_count
                playlist_obj.playlist_count = available_count
                playlist_obj.unavailable_count = unavailable_count
                db.commit()
                
                await log_wrapper(f"Final stats: {local_count} local, {available_count} available, {unavailable_count} unavailable")
                await log_wrapper(f"Database updated for playlist ID {playlist_obj.id}")
                
                # Broadcast playlist update event via WebSocket
                from app.api.websocket import broadcast_event
                await broadcast_event("playlist_updated", {
                    "playlist_id": playlist_obj.id,
                    "local_count": local_count,
                    "playlist_count": available_count,
                    "unavailable_count": unavailable_count
                })
            except Exception as e:
                await log_wrapper(f"Error refreshing final stats: {str(e)}")
                import traceback
                await log_wrapper(f"Traceback: {traceback.format_exc()}")
            
            # Update job status
            job = db.query(Job).filter(Job.id == job_id).first()
            job.status = "completed"
            job.completed_at = datetime.utcnow()
            db.commit()
            
            await log_wrapper("Job completed successfully")
            
        except asyncio.CancelledError:
            # Job was cancelled
            job = db.query(Job).filter(Job.id == job_id).first()
            job.status = "cancelled"
            job.completed_at = datetime.utcnow()
            db.commit()
            
            if log_callback:
                await log_callback(job_id, "Job cancelled by user")
        
        except Exception as e:
            # Job failed
            job = db.query(Job).filter(Job.id == job_id).first()
            job.status = "failed"
            job.error = str(e)
            job.completed_at = datetime.utcnow()
            db.commit()
            
            if log_callback:
                await log_callback(job_id, f"Job failed: {str(e)}")
        
        finally:
            # Cleanup
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]
            if job_id in self.cancel_flags:
                del self.cancel_flags[job_id]
            if job_id in self.download_services:
                del self.download_services[job_id]
            
            db.close()
    
    async def _run_download_phase(
        self,
        job_id: int,
        playlist: Playlist,
        download_service: DownloadService,
        progress_callback: Callable,
        log_callback: Callable,
        db
    ):
        """Run download phase and publish downloaded videos to extraction queue"""
        try:
            # Create callback to publish downloaded videos to extraction queue
            async def video_downloaded_callback(video_path: str):
                """Called when a video is successfully downloaded"""
                if job_id in self.extraction_queues:
                    await self.extraction_queues[job_id].put(video_path)
                    await log_callback(f"Video queued for extraction: {os.path.basename(video_path)}")
            
            await log_callback("Waiting for download slot in queue...")
            async with self._get_download_semaphore():
                job = db.query(Job).filter(Job.id == job_id).first()
                if job:
                    job.download_status = "running"
                    db.commit()
                
                await log_callback("Starting download phase...")
                
                failed_ids = await download_service.download_playlist(
                    playlist.url,
                    set(playlist.excluded_ids or []),
                    progress_callback=progress_callback,
                    log_callback=log_callback,
                    video_downloaded_callback=video_downloaded_callback
                )
            
            # Signal that download is complete (send None as sentinel)
            if job_id in self.extraction_queues:
                await self.extraction_queues[job_id].put(None)
            
            # Update playlist metadata (playlist object is already from this session)
            playlist.last_download = datetime.utcnow()
            
            # Add failed IDs to exclusions
            if failed_ids:
                existing = set(playlist.excluded_ids or [])
                playlist.excluded_ids = list(existing.union(failed_ids))
            
            # Refresh playlist stats
            await log_callback("Refreshing playlist stats...")
            try:
                local_count, available_count, unavailable_count = await download_service.get_playlist_stats(
                    playlist.title,
                    playlist.url,
                    playlist.excluded_ids or []
                )
                playlist.local_count = local_count
                playlist.playlist_count = available_count
                playlist.unavailable_count = unavailable_count
                await log_callback(f"Stats updated: {local_count} local, {available_count} available, {unavailable_count} unavailable")
            except Exception as e:
                await log_callback(f"Warning: Could not refresh stats: {str(e)}")
            
            job.download_status = "completed"
            job.download_failed = len(failed_ids)
            db.commit()
            
            await log_callback(f"Download phase completed. Failed: {len(failed_ids)}")
            
        except Exception as e:
            job = db.query(Job).filter(Job.id == job_id).first()
            job.download_status = "failed"
            db.commit()
            
            # Signal extraction to stop
            if job_id in self.extraction_queues:
                await self.extraction_queues[job_id].put(None)
            
            await log_callback(f"Download phase failed: {str(e)}")
            raise
    
    async def _run_extraction_phase(
        self,
        job_id: int,
        playlist: Playlist,
        download_service: DownloadService,
        progress_callback: Callable,
        log_callback: Callable,
        db
    ):
        """Run extraction phase using queue-based pub-sub system with thread pool"""
        from concurrent.futures import ThreadPoolExecutor
        from app.core import yt_playlist_audio_tools as tools
        
        try:
            # Create extraction queue for this job if it doesn't exist
            # (It may already exist if this is part of a "both" job type)
            if job_id not in self.extraction_queues:
                self.extraction_queues[job_id] = asyncio.Queue()
            
            job = db.query(Job).filter(Job.id == job_id).first()
            job.extract_status = "running"
            db.commit()
            
            await log_callback("Starting extraction phase (queue-based)...")
            
            # Get playlist folder - use same path construction as standalone extract
            safe_title = tools._sanitize_title(playlist.title)
            playlist_folder = os.path.join(download_service.base_path, safe_title)
            audio_folder = os.path.join(playlist_folder, safe_title)  # Match extract_audio_for_existing_playlist
            os.makedirs(audio_folder, exist_ok=True)
            
            # Find ffmpeg
            ffmpeg_path = tools._find_ffmpeg()
            if not ffmpeg_path:
                raise RuntimeError("FFmpeg not found")
            
            # Track extraction results
            extracted_videos = set()
            failed_videos = set()
            total_videos = 0
            
            # Create thread pool for parallel extraction
            max_workers = min(tools.MAX_EXTRACTION_WORKERS, 4)
            executor = ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="ExtractionThread"
            )
            
            await log_callback(f"Extraction thread pool ready with {max_workers} workers")
            
            # Active extraction tasks
            active_tasks = set()
            download_complete = False
            
            try:
                while not download_complete or active_tasks:
                    # Process completed tasks first
                    done_tasks = [task for task in active_tasks if task.done()]
                    for task in done_tasks:
                        active_tasks.remove(task)
                        try:
                            result = task.result()
                            vid_path = result.get("video")
                            
                            if result["status"] == "success" or result["status"] == "skipped":
                                extracted_videos.add(vid_path)
                                await log_callback(f"✓ Extracted: {os.path.basename(vid_path)}")
                            else:
                                failed_videos.add(vid_path)
                                await log_callback(f"✗ Failed: {os.path.basename(vid_path)}")
                            
                            # Update progress
                            completed = len(extracted_videos)
                            job = db.query(Job).filter(Job.id == job_id).first()
                            job.extract_total = total_videos
                            job.extract_completed = completed
                            job.extract_failed = len(failed_videos)
                            db.commit()
                            
                            if progress_callback:
                                await progress_callback(total_videos, completed)
                                
                        except Exception as e:
                            await log_callback(f"Error processing extraction result: {str(e)}")
                    
                    # If download not complete, try to get more videos from queue
                    if not download_complete:
                        try:
                            # Non-blocking queue check
                            video_path = self.extraction_queues[job_id].get_nowait()
                            
                            # None is sentinel value indicating download is complete
                            if video_path is None:
                                download_complete = True
                                await log_callback("Download complete signal received, waiting for remaining extractions...")
                                continue
                            
                            # Check if audio already exists
                            base_name = os.path.splitext(os.path.basename(video_path))[0]
                            audio_path = os.path.join(audio_folder, base_name + ".mp3")
                            
                            if os.path.exists(audio_path):
                                await log_callback(f"Skipping (audio exists): {os.path.basename(video_path)}")
                                extracted_videos.add(video_path)
                                continue
                            
                            # Increment total count
                            total_videos += 1
                            
                            # Submit extraction task to thread pool
                            loop = asyncio.get_event_loop()
                            future = loop.run_in_executor(
                                executor,
                                tools._extract_single_audio,
                                video_path,
                                audio_folder,
                                ffmpeg_path,
                                len(extracted_videos) + len(active_tasks) + 1,
                                total_videos
                            )
                            active_tasks.add(future)
                            
                            await log_callback(f"Queued for extraction ({len(active_tasks)} active): {os.path.basename(video_path)}")
                            
                        except asyncio.QueueEmpty:
                            # No videos in queue, wait a bit before checking again
                            if active_tasks:
                                # If we have active tasks, wait for at least one to complete
                                done, pending = await asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED)
                                # Don't process results here, let the main loop handle them
                            else:
                                # No active tasks and no videos in queue, wait briefly
                                await asyncio.sleep(0.1)
                    else:
                        # Download complete, just wait for remaining extractions
                        if active_tasks:
                            done, pending = await asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED)
                        else:
                            break
                
                # Wait for all remaining extraction tasks to complete
                if active_tasks:
                    await log_callback(f"Waiting for {len(active_tasks)} remaining extraction(s)...")
                    results = await asyncio.gather(*active_tasks, return_exceptions=True)
                    
                    for result in results:
                        if isinstance(result, Exception):
                            await log_callback(f"Extraction error: {str(result)}")
                            continue
                        
                        vid_path = result.get("video")
                        if result["status"] == "success" or result["status"] == "skipped":
                            extracted_videos.add(vid_path)
                        else:
                            failed_videos.add(vid_path)
                    
                    # Final progress update
                    job = db.query(Job).filter(Job.id == job_id).first()
                    job.extract_total = total_videos
                    job.extract_completed = len(extracted_videos)
                    job.extract_failed = len(failed_videos)
                    db.commit()
                    
                    if progress_callback:
                        await progress_callback(total_videos, len(extracted_videos))
                
                await log_callback(f"Extraction complete: {len(extracted_videos)} extracted, {len(failed_videos)} failed")
                
            finally:
                # Cleanup thread pool
                executor.shutdown(wait=False)
            
            # Update playlist (playlist object is already from this session)
            playlist.last_extract = datetime.utcnow()
            
            job.extract_status = "completed"
            db.commit()
            
            await log_callback("Extraction phase completed")
            
        except Exception as e:
            job = db.query(Job).filter(Job.id == job_id).first()
            job.extract_status = "failed"
            db.commit()
            await log_callback(f"Extraction phase failed: {str(e)}")
            raise
        
        finally:
            # Cleanup queue
            if job_id in self.extraction_queues:
                del self.extraction_queues[job_id]
    
    async def cancel_job(self, job_id: int):
        """Cancel a running job"""
        if job_id in self.cancel_flags:
            self.cancel_flags[job_id] = True
        
        # Cancel the download service's current job
        if job_id in self.download_services:
            self.download_services[job_id].cancel_current_job()
        
        if job_id in self.active_jobs:
            task = self.active_jobs[job_id]
            task.cancel()
    
    def get_active_jobs(self) -> list:
        """Get list of active job IDs"""
        return list(self.active_jobs.keys())
    
    def get_job_logs(self, job_id: int, lines: Optional[int] = None) -> list:
        """
        Get job logs from file
        
        Args:
            job_id: Job ID
            lines: Number of lines to return (from end), None for all
        """
        log_file = self._get_log_file_path(job_id)
        if not os.path.exists(log_file):
            return []
            
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
        
        if lines is not None:
            return all_lines[-lines:]
        
        return all_lines

    async def shutdown(self):
        """Cancel all running jobs gracefully during server/container shutdown"""
        print("[JobManager] Shutting down, cancelling active jobs...")
        from app.models.database import SessionLocal
        db = SessionLocal()
        try:
            for job_id in list(self.active_jobs.keys()):
                print(f"[JobManager] Cancelling active job #{job_id}")
                self.cancel_flags[job_id] = True
                if job_id in self.download_services:
                    self.download_services[job_id].cancel_current_job()
                task = self.active_jobs.get(job_id)
                if task and not task.done():
                    task.cancel()
                
                job = db.query(Job).filter(Job.id == job_id).first()
                if job and job.status == 'running':
                    job.error = 'Interrupted by server shutdown'
                    db.commit()
        except Exception as e:
            print(f"[JobManager] Error during shutdown: {e}")
        finally:
            db.close()

# Global job manager instance
job_manager = JobManager()

