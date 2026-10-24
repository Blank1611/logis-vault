"""
Download service - wraps existing yt_playlist_audio_tools.py logic for playlist operations
"""
import sys
import os
from pathlib import Path
from typing import Set, Callable, Optional
import asyncio
from datetime import datetime

# Import download tools from backend core
try:
    from app.core import yt_playlist_audio_tools as tools
    from app.core.cancellation import CancellationToken
except ImportError as e:
    print(f"Warning: Could not import yt_playlist_audio_tools or cancellation: {e}")
    tools = None
    CancellationToken = None

class DownloadService:
    """Service for downloading playlists using existing logic"""
    
    def __init__(self, base_path: str, config: dict):
        """Initialize download service"""
        self.base_path = base_path
        self.config = config
        self.cancel_token: Optional[CancellationToken] = None
        self.current_runstate = None
        
        # Configure tools module if available
        if tools:
            tools.BASE_DOWNLOAD_PATH = base_path
            tools.AUDIO_EXTRACT_MODE = config.get("audio_extract_mode", "copy")
            tools.MAX_EXTRACTION_WORKERS = config.get("max_extraction_workers", 4)
            tools.BATCH_SIZE = config.get("batch_size", 200)
            tools.USE_BROWSER_COOKIES = config.get("use_browser_cookies", False)
            tools.BROWSER_NAME = config.get("browser_name", "chrome")
            tools.COOKIES_FILE = config.get("cookies_file")
    
    def cancel_current_job(self):
        """Cancel the currently running job"""
        if self.cancel_token:
            self.cancel_token.cancel()
        if self.current_runstate:
            self.current_runstate.cancelled = True
    
    async def download_playlist(
        self,
        url: str,
        excluded_ids: Set[str],
        progress_callback: Optional[Callable] = None,
        log_callback: Optional[Callable] = None,
        video_downloaded_callback: Optional[Callable] = None,
        cancel_token: Optional[CancellationToken] = None,
        inflight_progress_callback: Optional[Callable] = None
    ) -> Set[str]:
        """
        Download playlist with progress and log callbacks
        
        Args:
            url: Playlist URL
            excluded_ids: Set of video IDs to exclude
            progress_callback: Async function(total, current, batch_info=None) for progress updates
            log_callback: Async function(message) for log messages
            video_downloaded_callback: Async function(video_path) called when a video is downloaded
            cancel_token: Optional thread-safe CancellationToken for cooperative cancellation
            inflight_progress_callback: Async function(vid, title, bytes_done, bytes_total, speed, eta) for in-flight byte telemetry
        
        Returns:
            Set of failed video IDs
        """
        if not tools:
            raise RuntimeError("yt_playlist_audio_tools not available")
        
        # Set up cancellation token and runstate
        self.cancel_token = cancel_token
        from types import SimpleNamespace
        runstate = SimpleNamespace(cancelled=False)
        self.current_runstate = runstate
        tools.GLOBAL_RUNSTATE = runstate
        if cancel_token:
            cancel_token.register(lambda: setattr(runstate, "cancelled", True))
        
        # Set up callbacks for existing tools
        main_loop = asyncio.get_event_loop()
        
        if progress_callback:
            def sync_progress(total, current, batch_info=None):
                try:
                    asyncio.run_coroutine_threadsafe(
                        progress_callback(total, current, batch_info),
                        main_loop
                    )
                except Exception as e:
                    print(f"Progress callback error: {e}")
            
            tools.GLOBAL_DOWNLOAD_PROGRESS_CALLBACK = sync_progress

        if inflight_progress_callback:
            def sync_inflight(vid: str, title: str, bytes_done: int, bytes_total: int, speed: float, eta: int):
                try:
                    asyncio.run_coroutine_threadsafe(
                        inflight_progress_callback(vid, title, bytes_done, bytes_total, speed, eta),
                        main_loop
                    )
                except Exception as e:
                    pass
            
            tools.GLOBAL_INFLIGHT_PROGRESS_CALLBACK = sync_inflight
        
        if video_downloaded_callback:
            def sync_video_downloaded(video_path: str):
                try:
                    asyncio.run_coroutine_threadsafe(
                        video_downloaded_callback(video_path),
                        main_loop
                    )
                except Exception as e:
                    print(f"Video downloaded callback error: {e}")
            
            tools.GLOBAL_VIDEO_DOWNLOADED_CALLBACK = sync_video_downloaded
        
        if log_callback:
            def sync_log(message: str):
                try:
                    asyncio.run_coroutine_threadsafe(
                        log_callback(message),
                        main_loop
                    )
                except Exception as e:
                    print(f"Log callback error: {e}")
            
            tools.GLOBAL_LOG_CALLBACK = sync_log
        
        # Run download in dedicated thread pool to avoid blocking
        from concurrent.futures import ThreadPoolExecutor
        
        download_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="DownloadThread"
        )
        
        loop = asyncio.get_event_loop()
        try:
            failed_ids = await loop.run_in_executor(
                download_executor,
                tools.download_playlist_with_video_and_audio,
                url,
                False,  # as_mp3 = False (extraction will be done separately in parallel)
                excluded_ids,
                cancel_token
            )
            return failed_ids
        finally:
            download_executor.shutdown(wait=False)
            tools.GLOBAL_DOWNLOAD_PROGRESS_CALLBACK = None
            tools.GLOBAL_INFLIGHT_PROGRESS_CALLBACK = None
            tools.GLOBAL_VIDEO_DOWNLOADED_CALLBACK = None
            tools.GLOBAL_LOG_CALLBACK = None
            tools.GLOBAL_VIDEO_DOWNLOADED_CALLBACK = None
            tools.GLOBAL_LOG_CALLBACK = None
    
    async def extract_audio(
        self,
        playlist_title: str,
        progress_callback: Optional[Callable] = None,
        log_callback: Optional[Callable] = None,
        extract_mode: Optional[str] = None
    ):
        """
        Extract audio from existing videos
        
        Args:
            playlist_title: Playlist title
            progress_callback: Async function(total, current) for progress updates
            log_callback: Async function(message) for log messages
            extract_mode: Audio extraction mode override (copy, opus, mp3_best, etc.)
        """
        if not tools:
            raise RuntimeError("yt_playlist_audio_tools not available")
        
        # Set up callbacks
        main_loop = asyncio.get_event_loop()
        
        if progress_callback:
            def sync_progress(total, current, batch_info=None):
                try:
                    # Use call_soon_threadsafe to schedule the callback in the main loop
                    # Note: extraction doesn't use batch_info, so we ignore it
                    asyncio.run_coroutine_threadsafe(
                        progress_callback(total, current),
                        main_loop
                    )
                except Exception as e:
                    print(f"Progress callback error: {e}")
            
            # Set extraction-specific callback
            tools.GLOBAL_EXTRACT_PROGRESS_CALLBACK = sync_progress
        
        if log_callback:
            def sync_log(message: str):
                try:
                    asyncio.run_coroutine_threadsafe(
                        log_callback(message),
                        main_loop
                    )
                except Exception as e:
                    print(f"Log callback error: {e}")
            
            tools.GLOBAL_LOG_CALLBACK = sync_log
        
        # Run extraction in thread pool
        loop = asyncio.get_event_loop()
        try:
            await loop.run_in_executor(
                None,
                lambda: tools.extract_audio_for_existing_playlist(playlist_title, extract_mode=extract_mode)
            )
        finally:
            # Clean up callbacks to prevent interference with other operations
            tools.GLOBAL_EXTRACT_PROGRESS_CALLBACK = None
            tools.GLOBAL_LOG_CALLBACK = None
    

    
    async def get_playlist_info(self, url: str) -> dict:
        """Get playlist information"""
        if not tools:
            raise RuntimeError("yt_playlist_audio_tools not available")
        
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(
            None,
            tools._get_playlist_info,
            url,
            False  # force_refresh
        )
        
        return info
    
    def resolve_playlist_folder(self, title: str) -> str:
        """
        Resolve the playlist directory on disk.
        Matches exact sanitized title first; if not found, scans directory entries
        case-insensitively to prevent duplicate ghost folders on Linux ext4 filesystems.
        """
        if not tools:
            safe_title = "".join(c for c in title if c not in r'\/:*?"<>|').strip() or "playlist"
        else:
            safe_title = tools._sanitize_title(title)

        direct_path = os.path.join(self.base_path, safe_title)
        if os.path.isdir(direct_path):
            return direct_path

        # Case-insensitive check against existing directories on disk
        try:
            if os.path.isdir(self.base_path):
                safe_title_lower = safe_title.lower()
                raw_title_lower = title.strip().lower()
                for entry in os.listdir(self.base_path):
                    entry_path = os.path.join(self.base_path, entry)
                    if not os.path.isdir(entry_path) or entry.startswith('.'):
                        continue
                    entry_lower = entry.lower()
                    if entry_lower == safe_title_lower or entry_lower == raw_title_lower:
                        return entry_path
        except Exception:
            pass

        return direct_path

    async def get_playlist_stats(
        self,
        title: str,
        url: str,
        excluded_ids: list,
        source: str = "ondemand",
        force_refresh: Optional[bool] = None
    ) -> tuple:
        """Get playlist statistics with 3-tier refresh policy"""
        if not tools:
            raise RuntimeError("yt_playlist_audio_tools not available")
        
        # 3-Tier refresh policy:
        # Tier 1 & 3: Manual user refreshes and onboarding always force fresh online fetch
        # Tier 2: Routine startup restarts respect ctime freshness check
        if force_refresh is None:
            if source in ("manual", "refresh", "onboarding"):
                force_refresh = True
            else:
                force_refresh = False

        playlist_folder = self.resolve_playlist_folder(title)
        
        # Count local videos
        local_count = 0
        if os.path.isdir(playlist_folder):
            video_exts = ("*.mp4", "*.mkv", "*.webm", "*.m4v")
            import glob
            files = []
            for pat in video_exts:
                files.extend(glob.glob(os.path.join(playlist_folder, pat)))
            local_count = len(files)
        
        # Get playlist entries
        loop = asyncio.get_event_loop()
        entries = await loop.run_in_executor(
            None,
            tools._get_playlist_entries,
            url,
            playlist_folder,
            force_refresh,
            source
        )
        
        # Count available and unavailable
        # Don't pass excluded_set to is_entry_unavailable - we want to count them separately
        excluded_set = set(excluded_ids or [])
        available_count = 0
        unavailable_count = 0
        
        for e in entries:
            vid = e.get("id")
            
            # Check if video is in excluded list
            if vid and vid in excluded_set:
                unavailable_count += 1  # Excluded videos are shown as unavailable
            # Check if video is actually unavailable (private, deleted, etc.)
            elif tools.is_entry_unavailable(e, None):  # Pass None to not check excluded_ids
                unavailable_count += 1
            else:
                available_count += 1
        
        return local_count, available_count, unavailable_count
