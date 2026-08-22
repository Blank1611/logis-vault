#!/usr/bin/env python3
"""
yt_playlist_audio_tools.py

Shared tools for:
1) Downloading playlists with best video + audio and extracting MP3s.
2) Extracting MP3s later from already-downloaded playlist videos.

This version adds:
- GLOBAL_PROGRESS_CALLBACK: for GUI progress bar
- GLOBAL_RUNSTATE: for GUI cancel flag
- FAILED_VIDEO_IDS: IDs that failed (unavailable) in last run
- is_entry_unavailable(excluded_ids=...): uses per-playlist excluded_ids
"""

import os
import json
import time
import random
import shutil
import glob
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

from yt_dlp import YoutubeDL
from yt_dlp.utils import ExtractorError

# ====== CONFIGURATION SYSTEM ======
# This module can work in two modes:
# 1. Backend mode: Uses Pydantic settings from app.core.config (yt_serve)
# 2. Standalone mode: Uses config.json (Tkinter version)

try:
    from app.core.config import settings
    _USE_BACKEND_SETTINGS = True
except ImportError:
    # Fallback for standalone usage (Tkinter version)
    _USE_BACKEND_SETTINGS = False
    settings = None

def _load_config(config_path: str = "config.json") -> dict:
    """Load configuration from JSON file (fallback for standalone mode)."""
    if not os.path.isfile(config_path):
        return {}
    
    with open(config_path, "r") as f:
        return json.load(f)


# Load config only if backend settings not available
CONFIG = {} if _USE_BACKEND_SETTINGS else _load_config()

# ====== USER CONFIG (DEFAULTS, CAN BE OVERRIDDEN BY GUI) ======

if _USE_BACKEND_SETTINGS and settings:
    # Backend mode: Use Pydantic settings from .env
    BASE_DOWNLOAD_PATH = settings.BASE_DOWNLOAD_PATH
    USE_BROWSER_COOKIES = settings.USE_BROWSER_COOKIES
    BROWSER_NAME = settings.BROWSER_NAME
    COOKIES_FILE = settings.COOKIES_FILE
    AUDIO_EXTRACT_MODE = settings.AUDIO_EXTRACT_MODE
    MAX_EXTRACTION_WORKERS = settings.MAX_CONCURRENT_EXTRACTIONS
    # BATCH_SIZE is loaded dynamically - see _get_batch_size()
    BATCH_DELAY = 300  # Default for backend
else:
    # Standalone mode: Use config.json
    BASE_DOWNLOAD_PATH = CONFIG.get("base_download_path")
    USE_BROWSER_COOKIES = CONFIG.get("use_browser_cookies", False)
    BROWSER_NAME = CONFIG.get("browser_name", "chrome")
    COOKIES_FILE = CONFIG.get("cookies_file")
    AUDIO_EXTRACT_MODE = CONFIG.get("audio_extract_mode", "mp3_best")
    MAX_EXTRACTION_WORKERS = CONFIG.get("max_extraction_workers", 4)
    # BATCH_SIZE is loaded dynamically - see _get_batch_size()
    BATCH_DELAY = CONFIG.get("batch_delay", 300)


def _get_batch_size() -> int:
    """Get current batch size from settings (dynamically loaded)."""
    if _USE_BACKEND_SETTINGS:
        # Create new Settings instance to reload from .env file
        from app.core.config import Settings
        fresh_settings = Settings()
        return fresh_settings.BATCH_SIZE
    else:
        # Reload config.json for standalone mode
        config = _load_config()
        return config.get("batch_size", 200)

USER_AGENT = "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36"
CONCURRENT_FRAGMENTS = 4

# ====== FEATURE FLAGS ======
# ENABLE_OLD_FORMAT_AUTO_RENAME: Controls old format video detection and renaming
# 
# When True:  Will search for videos by title (old format) and automatically rename them to include video ID
#             This is useful for migrating from old naming scheme but can be slow and error-prone
#             due to complex title matching
#
# When False: Only searches for video ID in filename (faster and more reliable)
#             Recommended for new installations or after migration is complete
#
# Default: False (ID-only matching for better performance and reliability)
ENABLE_OLD_FORMAT_AUTO_RENAME = False

# ====== GLOBALS ======

SKIPPED_VIDEOS_ARCHIVE: List[Dict] = []
SKIPPED_AUDIO_EXISTING: List[Dict] = []
EXTRACTED_AUDIO: List[Dict] = []

GLOBAL_PROGRESS_CALLBACK = None  # set by GUI (legacy, for backward compatibility)
GLOBAL_DOWNLOAD_PROGRESS_CALLBACK = None  # separate callback for download progress
GLOBAL_EXTRACT_PROGRESS_CALLBACK = None   # separate callback for extraction progress
GLOBAL_VIDEO_DOWNLOADED_CALLBACK = None   # callback when a video is successfully downloaded
GLOBAL_LOG_CALLBACK = None       # callback for log messages
GLOBAL_RUNSTATE = None           # SimpleNamespace(cancelled=bool) set by GUI

FAILED_VIDEO_IDS: Set[str] = set()  # IDs that failed in last download run
PLAYLIST_INFO_CACHE: Dict[str, dict] = {} # Cache for playlist info extracted via yt-dlp.extract_info()

# NEW global to let hooks know which playlist we're processing
GLOBAL_CURRENT_PLAYLIST_URL: Optional[str] = None


def _log(message: str):
    """Log a message - sends to callback if available, otherwise prints"""
    if GLOBAL_LOG_CALLBACK is not None:
        try:
            GLOBAL_LOG_CALLBACK(message)
        except Exception as e:
            print(f"Log callback error: {e}")
            print(message)  # Fallback to print
    else:
        print(message)


# ====== CUSTOM ARCHIVE LOGIC ======

def _load_custom_archive(archive_file: str) -> Set[str]:
    """Load video IDs from our custom archive file."""
    if not os.path.isfile(archive_file):
        return set()
    
    ids = set()
    with open(archive_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                # Extract ID from "youtube <id>" format or just "<id>"
                parts = line.split()
                vid_id = parts[-1] if parts else line
                ids.add(vid_id)
    return ids

def _save_custom_archive(archive_file: str, video_ids: Set[str]):
    """Save video IDs to our custom archive file."""
    os.makedirs(os.path.dirname(archive_file), exist_ok=True)
    with open(archive_file, "w", encoding="utf-8") as f:
        f.write("# Custom archive - video IDs successfully downloaded\n")
        for vid_id in sorted(video_ids):
            f.write(f"youtube {vid_id}\n")

def _add_to_custom_archive(archive_file: str, video_id: str):
    """Add a single video ID to the archive file."""
    with open(archive_file, "a", encoding="utf-8") as f:
        f.write(f"youtube {video_id}\n")

def _sanitize_filename(title: str) -> str:
    """Sanitize title for filename (same logic as yt-dlp uses)."""
    # Remove invalid filename characters
    invalid_chars = r'\/:*?"<>|'
    sanitized = "".join(c for c in title if c not in invalid_chars)
    return sanitized.strip()


def _get_effective_title(entry: dict) -> str:
    """
    Get effective title for a video entry, using channel name as fallback for empty titles.
    This matches the yt-dlp output template logic: %(title|channel|Unknown)s
    """
    title = entry.get("title", "").strip()
    
    # Check if title is empty or just whitespace/special characters
    if not title or title in ["​", "", " "] or len(title.strip()) == 0:
        # Use channel name as fallback
        channel = entry.get("channel", "").strip()
        if channel:
            return channel
        else:
            return "Unknown"
    
    return title


def _find_video_by_title_and_rename(playlist_folder: str, video_id: str, video_title: str) -> bool:
    """
    Find video file by title (old format without ID) and rename to new format with ID.
    Returns True if file was found and renamed, False otherwise.
    """
    if not video_title:
        return False
    
    video_exts = (".mp4", ".mkv", ".webm", ".m4v")
    
    # Sanitize title (yt-dlp does this when creating filenames)
    sanitized_title = _sanitize_filename(video_title)
    
    # Try to find file with just the title (old format)
    for ext in video_exts:
        # Try exact sanitized title match
        old_path = os.path.join(playlist_folder, f"{sanitized_title}{ext}")
        if os.path.exists(old_path):
            # Rename to new format: title [video_id].ext
            new_filename = f"{sanitized_title} [{video_id}]{ext}"
            new_path = os.path.join(playlist_folder, new_filename)
            
            try:
                os.rename(old_path, new_path)
                print(f"  ✓ Renamed old format: {os.path.basename(old_path)} → {os.path.basename(new_path)}")
                return True
            except Exception as e:
                print(f"  ⚠️  Could not rename {os.path.basename(old_path)}: {e}")
                return False
        
        # Also try original title (in case it wasn't sanitized)
        old_path = os.path.join(playlist_folder, f"{video_title}{ext}")
        if os.path.exists(old_path):
            new_filename = f"{video_title} [{video_id}]{ext}"
            new_path = os.path.join(playlist_folder, new_filename)
            
            try:
                os.rename(old_path, new_path)
                print(f"  ✓ Renamed old format: {os.path.basename(old_path)} → {os.path.basename(new_path)}")
                return True
            except Exception as e:
                print(f"  ⚠️  Could not rename {os.path.basename(old_path)}: {e}")
                return False
    
    # If exact match not found, try fuzzy search (title might have variations)
    sanitized_lower = sanitized_title.lower()
    
    for pattern in [f"*.{ext.lstrip('.')}" for ext in video_exts]:
        files = glob.glob(os.path.join(playlist_folder, pattern))
        for file_path in files:
            filename = os.path.basename(file_path)
            # Skip files that already have video ID
            if f"[{video_id}]" in filename or f"_{video_id}." in filename:
                continue
            
            # Check if filename matches video title (case-insensitive, partial match)
            name_without_ext = os.path.splitext(filename)[0]
            name_lower = name_without_ext.lower()
            
            # Match if either:
            # 1. Sanitized title is in filename
            # 2. Filename is in sanitized title (for truncated names)
            # 3. High similarity (at least 80% of shorter string matches)
            if (sanitized_lower in name_lower or 
                name_lower in sanitized_lower or
                (len(name_lower) > 10 and sanitized_lower[:min(len(sanitized_lower), len(name_lower))] == name_lower[:min(len(sanitized_lower), len(name_lower))])):
                
                # Found potential match - rename it
                ext = os.path.splitext(filename)[1]
                new_filename = f"{name_without_ext} [{video_id}]{ext}"
                new_path = os.path.join(playlist_folder, new_filename)
                
                try:
                    os.rename(file_path, new_path)
                    print(f"  ✓ Renamed old format: {filename} → {new_filename}")
                    return True
                except Exception as e:
                    print(f"  ⚠️  Could not rename {filename}: {e}")
                    return False
    
    return False


def _get_video_file_path(playlist_folder: str, video_id: str, wait_for_file: bool = False) -> Optional[str]:
    """
    Get the full path to a video file with the given ID.
    Returns None if not found.
    
    If wait_for_file is True, will wait up to 5 seconds for the file to appear
    (useful right after download completion to handle file system delays).
    """
    video_exts = (".mp4", ".mkv", ".webm", ".m4v")
    
    max_attempts = 10 if wait_for_file else 1
    wait_interval = 0.5  # seconds
    
    for attempt in range(max_attempts):
        # Use os.listdir() instead of glob to catch files starting with .. or other special names
        try:
            all_files = os.listdir(playlist_folder)
        except Exception as e:
            _log(f"[ERROR] Could not list directory {playlist_folder}: {e}")
            return None
        
        for filename in all_files:
            # Skip directories
            full_path = os.path.join(playlist_folder, filename)
            if not os.path.isfile(full_path):
                continue
            
            # Check if it's a video file
            if not any(filename.lower().endswith(ext) for ext in video_exts):
                continue
            
            # Check if video ID is in filename (format: [video_id] or _video_id.)
            pattern1 = f"[{video_id}]"
            pattern2 = f"_{video_id}."
            
            if pattern1 in filename or pattern2 in filename:
                return full_path
            
            # Debug specific video
            if video_id == "87XbYi98DTg" and video_id in filename:
                _log(f"[DEBUG] Found file with video ID but pattern didn't match:")
                _log(f"[DEBUG]   File: {filename}")
                _log(f"[DEBUG]   Pattern1 '{pattern1}' in filename: {pattern1 in filename}")
                _log(f"[DEBUG]   Pattern2 '{pattern2}' in filename: {pattern2 in filename}")
                _log(f"[DEBUG]   Filename repr: {repr(filename)}")
                _log(f"[DEBUG]   Pattern1 repr: {repr(pattern1)}")
        
        # If not found and we should wait, sleep and try again
        if wait_for_file and attempt < max_attempts - 1:
            time.sleep(wait_interval)
        else:
            break
    
    # Debug: If not found after all attempts, log what we found
    _log(f"[DEBUG] Video file not found for ID: {video_id}")
    _log(f"[DEBUG] Playlist folder: {playlist_folder}")
    _log(f"[DEBUG] Looking for patterns: [{video_id}] or _{video_id}.")
    
    # Use os.listdir() to get all files (including those starting with ..)
    try:
        all_filenames = os.listdir(playlist_folder)
        video_exts_tuple = (".mp4", ".mkv", ".webm", ".m4v")
        all_files = [
            os.path.join(playlist_folder, f) 
            for f in all_filenames 
            if os.path.isfile(os.path.join(playlist_folder, f)) 
            and any(f.lower().endswith(ext) for ext in video_exts_tuple)
        ]
    except Exception as e:
        _log(f"[ERROR] Could not list directory: {e}")
        all_files = []
    
    _log(f"[DEBUG] Found {len(all_files)} video files in folder")
    
    # Check if there are files starting with ..
    dotdot_files = [f for f in all_files if os.path.basename(f).startswith("..")]
    if dotdot_files:
        _log(f"[DEBUG] Found {len(dotdot_files)} files starting with '..'")
        for f in dotdot_files[:3]:  # Show first 3
            _log(f"[DEBUG]   - {os.path.basename(f)}")
    
    # List files that contain the video ID (even partially)
    matching_files = []
    for f in all_files:
        basename = os.path.basename(f)
        # Check both case-sensitive and case-insensitive
        if video_id in basename or video_id.lower() in basename.lower():
            matching_files.append(f)
    
    if matching_files:
        _log(f"[DEBUG] Files containing video ID '{video_id}':")
        for f in matching_files:
            basename = os.path.basename(f)
            _log(f"[DEBUG]   - {basename}")
            # Show why it didn't match
            if f"[{video_id}]" not in basename and f"_{video_id}." not in basename:
                _log(f"[DEBUG]     ^ Does not match pattern [{video_id}] or _{video_id}.")
    else:
        _log(f"[DEBUG] No files found containing video ID '{video_id}'")
        # Show a sample of recent files for comparison
        if all_files:
            _log(f"[DEBUG] Sample of files in folder (first 3):")
            for f in all_files[:3]:
                _log(f"[DEBUG]   - {os.path.basename(f)}")
    
    # Check for .part files (incomplete downloads)
    part_files = glob.glob(os.path.join(playlist_folder, "*.part"))
    if part_files:
        _log(f"[DEBUG] Found {len(part_files)} .part files (incomplete downloads)")
        for pf in part_files:
            pf_basename = os.path.basename(pf)
            if video_id in pf:
                _log(f"[DEBUG]   ⚠️  MATCHES THIS VIDEO: {pf_basename}")
            else:
                _log(f"[DEBUG]   - {pf_basename} (different video)")
    
    return None


def _video_exists_on_disk(playlist_folder: str, video_id: str, video_title: str = None) -> bool:
    """
    Check if a video file with the given ID exists on disk.
    
    If ENABLE_OLD_FORMAT_AUTO_RENAME is True and video_title is provided,
    will also search for old format (title only) and automatically rename to new format.
    """
    # Check if file exists using helper function (searches for ID in filename)
    if _get_video_file_path(playlist_folder, video_id):
        return True
    
    # Optional: If feature flag enabled and title provided, try to find and rename old format
    if ENABLE_OLD_FORMAT_AUTO_RENAME and video_title:
        if _find_video_by_title_and_rename(playlist_folder, video_id, video_title):
            return True
    
    return False

def _should_download_video(archive_file: str, playlist_folder: str, video_id: str, video_title: str = None) -> bool:
    """
    Determine if a video should be downloaded based on:
    a. ID does not exist in archive.txt, OR
    b. ID exists in archive but file not actually on disk
    
    Note: Old format detection (title-only filenames) is controlled by ENABLE_OLD_FORMAT_AUTO_RENAME flag.
    When enabled, will search for and rename old format files to new format (title + ID).
    """
    archived_ids = _load_custom_archive(archive_file)
    
    # Case a: Not in archive at all
    if video_id not in archived_ids:
        return True
    
    # Case b: In archive but file missing on disk
    # Checks for video ID in filename (and optionally old format if flag enabled)
    file_path = _get_video_file_path(playlist_folder, video_id)
    if not file_path:
        # Try old format detection if enabled
        if ENABLE_OLD_FORMAT_AUTO_RENAME and video_title:
            if _find_video_by_title_and_rename(playlist_folder, video_id, video_title):
                return False  # File found and renamed, don't download
        
        # Log detailed info about why file wasn't found
        _log(f"  ⚠️  Video {video_id} in archive but missing on disk - will re-download")
        _log(f"      Archive file: {archive_file}")
        _log(f"      Playlist folder: {playlist_folder}")
        
        # List all video files to help debug
        video_exts = ("*.mp4", "*.mkv", "*.webm", "*.m4v")
        all_files = []
        for pattern in video_exts:
            all_files.extend(glob.glob(os.path.join(playlist_folder, pattern)))
        
        # Check if any file contains this video ID
        matching = [f for f in all_files if video_id in os.path.basename(f)]
        if matching:
            _log(f"      Found {len(matching)} file(s) with video ID in name:")
            for f in matching:
                _log(f"        - {os.path.basename(f)}")
            _log(f"      These files don't match expected pattern: [video_id] or _video_id.")
        else:
            _log(f"      No files found containing video ID {video_id}")
            _log(f"      Total video files in folder: {len(all_files)}")
        
        return True
    
    return False


# ====== BATCH PROGRESS TRACKING ======

def _get_batch_progress_file(playlist_folder: str) -> str:
    """Get the path to the batch progress file."""
    return os.path.join(playlist_folder, "batch_progress.json")


def _load_batch_progress(playlist_folder: str) -> dict:
    """Load batch progress from file."""
    progress_file = _get_batch_progress_file(playlist_folder)
    if not os.path.exists(progress_file):
        return {
            "total_videos": 0,
            "downloaded_count": 0,
            "pending_video_ids": [],
            "last_batch_date": None,
            "batch_size": _get_batch_size(),
            "completed": False
        }
    
    try:
        with open(progress_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Warning: Could not load batch progress: {e}")
        return {
            "total_videos": 0,
            "downloaded_count": 0,
            "pending_video_ids": [],
            "last_batch_date": None,
            "batch_size": _get_batch_size(),
            "completed": False
        }


def _save_batch_progress(playlist_folder: str, progress: dict) -> None:
    """Save batch progress to file."""
    progress_file = _get_batch_progress_file(playlist_folder)
    try:
        with open(progress_file, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Warning: Could not save batch progress: {e}")


def _archive_completed_batch_progress(playlist_folder: str) -> None:
    """Archive completed batch progress file with creation datetime."""
    progress_file = _get_batch_progress_file(playlist_folder)
    
    if not os.path.exists(progress_file):
        return
    
    try:
        # Get file creation time
        creation_time = os.path.getctime(progress_file)
        date_str = datetime.fromtimestamp(creation_time).strftime("%Y%m%d_%H%M%S")
        
        # Create archived filename
        archived_name = f"batch_progress_{date_str}.json"
        archived_path = os.path.join(playlist_folder, archived_name)
        
        # Rename the file
        os.rename(progress_file, archived_path)
        print(f"  ✓ Archived batch progress as: {archived_name}")
    except Exception as e:
        print(f"  Warning: Could not archive batch progress: {e}")


def _initialize_batch_progress(playlist_folder: str, video_ids: list) -> dict:
    """Initialize batch progress for a new download session."""
    progress = {
        "total_videos": len(video_ids),
        "downloaded_count": 0,
        "pending_video_ids": video_ids,
        "last_batch_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "batch_size": _get_batch_size(),
        "completed": False
    }
    _save_batch_progress(playlist_folder, progress)
    return progress


def _update_batch_progress(playlist_folder: str, downloaded_ids: list) -> dict:
    """Update batch progress after downloading videos."""
    progress = _load_batch_progress(playlist_folder)
    
    # Remove downloaded IDs from pending list
    pending = [vid for vid in progress["pending_video_ids"] if vid not in downloaded_ids]
    
    progress["pending_video_ids"] = pending
    progress["downloaded_count"] = progress["total_videos"] - len(pending)
    progress["last_batch_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    progress["completed"] = len(pending) == 0
    
    _save_batch_progress(playlist_folder, progress)
    return progress


def _remove_from_batch_progress(playlist_folder: str, video_id: str) -> None:
    """Remove a single video ID from batch progress (for incremental updates)."""
    progress = _load_batch_progress(playlist_folder)
    
    if video_id in progress["pending_video_ids"]:
        progress["pending_video_ids"].remove(video_id)
        progress["downloaded_count"] = progress["total_videos"] - len(progress["pending_video_ids"])
        progress["last_batch_date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        progress["completed"] = len(progress["pending_video_ids"]) == 0
        _save_batch_progress(playlist_folder, progress)

# ====== HELPERS ======

def _find_ffmpeg_windows() -> Optional[str]:
    possible_names = ['ffmpeg.exe', 'ffmpeg']
    for name in possible_names:
        path = shutil.which(name)
        if path:
            return path

    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"%LOCALAPPDATA%\Programs\ffmpeg\bin\ffmpeg.exe",
    ]
    for path_template in common_paths:
        path = os.path.expandvars(path_template)
        if os.path.exists(path):
            return path

    return None


def _sanitize_title(title: str) -> str:
    safe_title = "".join(c for c in title if c not in r'\/:*?"<>|').strip()
    return safe_title or "playlist"

def _get_playlist_info(url: str, force_refresh: bool = False) -> dict:
    """Return the full info dict for a playlist/url, caching the result.

    If force_refresh is True, re-run extract_info and update cache.
    """
    if not force_refresh and url in PLAYLIST_INFO_CACHE:
        return PLAYLIST_INFO_CACHE[url]

    ydl_opts_info = {
        "quiet": True,
        "skip_download": True,
        "extract_flat": "in_playlist",
        "js_runtimes": {
        'node': {} 
    },
        # "js_runtimes": {"node": "C:\Program Files\nodejs\node.exe"}
    }
    if USE_BROWSER_COOKIES and _check_browser_cookies_available():
        ydl_opts_info["cookies_from_browser"] = (BROWSER_NAME,)
    elif COOKIES_FILE and os.path.isfile(COOKIES_FILE):
        # yt-dlp Python API expects "cookiefile" for a cookies.txt path
        ydl_opts_info["cookiefile"] = COOKIES_FILE
    if USER_AGENT:
        ydl_opts_info["user_agent"] = USER_AGENT

    try:
        with YoutubeDL(ydl_opts_info) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception as e:
        # don't overwrite existing cached info on transient failures
        if url in PLAYLIST_INFO_CACHE and not force_refresh:
            return PLAYLIST_INFO_CACHE[url]
        raise

    PLAYLIST_INFO_CACHE[url] = info or {}
    return PLAYLIST_INFO_CACHE[url]

def _get_playlist_info_title(url: str) -> str:
    info = _get_playlist_info(url)
    return info.get("title") or "playlist"


def _is_playlist_info_fresh(playlist_folder: str) -> bool:
    """
    Check if playlist_info.json was created today (same date as current date).
    Returns True if file exists and was created today, False otherwise.
    """
    snapshot_dir = os.path.join(playlist_folder, "playlist_info_snapshot")
    info_path = os.path.join(snapshot_dir, "playlist_info.json")
    
    if not os.path.exists(info_path):
        return False
    
    try:
        # Get file creation time
        creation_time = os.path.getctime(info_path)
        creation_date = datetime.fromtimestamp(creation_time).date()
        today_date = datetime.now().date()
        
        # Check if created today
        return creation_date == today_date
    except Exception:
        return False


def _load_cached_playlist_info(playlist_folder: str) -> Optional[dict]:
    """
    Load playlist info from cached playlist_info.json file.
    Returns None if file doesn't exist or can't be loaded.
    """
    snapshot_dir = os.path.join(playlist_folder, "playlist_info_snapshot")
    info_path = os.path.join(snapshot_dir, "playlist_info.json")
    
    if not os.path.exists(info_path):
        return None
    
    try:
        with open(info_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  Warning: Could not load cached playlist_info.json: {e}")
        return None


def _save_playlist_info_with_versioning(playlist_folder: str, info: dict):
    """
    Save playlist_info.json to the playlist_info_snapshot subdirectory.
    If file already exists, rename old file with creation date before saving new one.
    """
    # Create snapshot subdirectory
    snapshot_dir = os.path.join(playlist_folder, "playlist_info_snapshot")
    os.makedirs(snapshot_dir, exist_ok=True)
    
    info_path = os.path.join(snapshot_dir, "playlist_info.json")
    
    # If file exists, rename it with its creation date
    if os.path.isfile(info_path):
        try:
            # Get file creation time
            creation_time = os.path.getctime(info_path)
            date_str = datetime.fromtimestamp(creation_time).strftime("%Y%m%d_%H%M%S")
            
            # Rename old file in same directory
            old_name = os.path.join(snapshot_dir, f"playlist_info_{date_str}.json")
            os.rename(info_path, old_name)
            print(f"  Archived old playlist_info.json as: {os.path.basename(old_name)}")
        except Exception as e:
            print(f"  Warning: Could not archive old playlist_info.json: {e}")
    
    # Save new file
    with open(info_path, "w", encoding="utf-8") as f:
        json.dump(info, f, ensure_ascii=False, indent=2)
    
    print(f"  Saved playlist_info.json to: playlist_info_snapshot/")

def _get_playlist_entries(url: str, playlist_folder: str, force_refresh: bool = False) -> List[dict]:
    """
    Return playlist entries (list of entry dicts), using cache when possible.
    
    If force_refresh is False and playlist_info.json was created today,
    loads from cache instead of calling yt-dlp API.
    """
    # Check if we can use cached info (created today)
    if not force_refresh and _is_playlist_info_fresh(playlist_folder):
        cached_info = _load_cached_playlist_info(playlist_folder)
        if cached_info:
            print(f"  ✓ Using cached playlist info (created today)")
            # Also update in-memory cache
            PLAYLIST_INFO_CACHE[url] = cached_info
            return cached_info.get("entries") or []
    
    # Fetch fresh info from yt-dlp API
    info = _get_playlist_info(url, force_refresh=force_refresh)
    playlist_entries = info.get("entries") or []
    _save_playlist_info_with_versioning(playlist_folder, info)
    return playlist_entries

def _check_browser_cookies_available(browser_name: str = BROWSER_NAME) -> bool:
    """
    Return True if browser cookies for YouTube can be loaded (requires browser_cookie3).
    If browser_cookie3 is not installed or no youtube cookies found, returns False.
    """
    try:
        import browser_cookie3
    except Exception as e:
        # browser_cookie3 not installed or import failed
        print(f"[WARN] browser_cookie3 not available: {e}")
        return False

    try:
        loader = getattr(browser_cookie3, browser_name.lower(), None)
        if not callable(loader):
            # unsupported browser
            return False
        cj = loader()
        # cj is a CookieJar; check for any cookie that mentions youtube
        for cookie in cj:
            domain = getattr(cookie, "domain", "") or ""
            if "youtube" in domain.lower() or "google" in domain.lower():
                return True
        return False
    except Exception as e:
        print(f"[WARN] Failed to inspect browser cookies: {e}")
        return False

def _build_playlist_paths(title: str, create_folders: bool = True) -> Tuple[str, str, str]:
    """
    Build paths for playlist folder, archive file, and audio folder.
    If create_folders is True, creates the folders immediately including playlist_info_snapshot.
    """
    safe_title = _sanitize_title(title)
    playlist_folder = os.path.join(BASE_DOWNLOAD_PATH, safe_title)
    archive_file = os.path.join(playlist_folder, "archive.txt")
    audio_folder = os.path.join(playlist_folder, safe_title)
    snapshot_folder = os.path.join(playlist_folder, "playlist_info_snapshot")

    if create_folders:
        os.makedirs(playlist_folder, exist_ok=True)
        os.makedirs(audio_folder, exist_ok=True)
        os.makedirs(snapshot_folder, exist_ok=True)

    return playlist_folder, archive_file, audio_folder


def _base_speed_opts() -> dict:
    return {
        "concurrent_fragment_downloads": max(1, CONCURRENT_FRAGMENTS // 2),  # Reduce concurrent fragments to avoid 403s
        "continuedl": True,
        "retries": 10,  # Increase retries for transient errors
        "fragment_retries": 10,  # Increase fragment retries
        "retry_sleep_functions": {
            "http": lambda n: min(4 ** n, 60),  # Exponential backoff for HTTP errors
            "fragment": lambda n: min(2 ** n, 30),  # Exponential backoff for fragments
        },
        "noprogress": False,
        "sleep_interval": 1,  # Add delay between downloads
        "max_sleep_interval": 5,  # Maximum sleep interval
        "sleep_interval_subtitles": 0,
        'verbose': True,
        # Add specific handling for 403 errors
        "extractor_retries": 3,
        "file_access_retries": 3,
        "js_runtimes": {'node':{}}
        # Add JavaScript runtime support for YouTube's new requirements
        # "extractor_args": {
        #     "youtube": {
        #         "js_runtimes": ['node:C:\Program Files\nodejs\node.EXE']  # Use Node.js for JavaScript execution
        #     }
        # }
    }


# ====== UNAVAILABLE ENTRY DETECTION ======

def is_entry_unavailable(e: dict, excluded_ids: Set[str] | None = None) -> bool:
    """Heuristic to detect unavailable videos for playlist statistics."""
    if e is None:
        return True

    vid = e.get("id")
    if excluded_ids and vid in excluded_ids:
        return True
    if vid in FAILED_VIDEO_IDS:
        return True

    title_e = (e.get("title") or "").lower()
    desc_e = (e.get("description") or "").lower()
    err_e = (e.get("error") or e.get("error_text") or "").lower()
    text = " ".join([title_e, desc_e, err_e])

    patterns = [
        "private video",
        "deleted video",
        "video unavailable",
        "this video is not available",
        "has been removed by the uploader",
        "no longer available due to a copyright claim",
        "this content isn",  # "isn't available" variants
    ]
    for ph in patterns:
        if ph in text:
            return True

    availability = (e.get("availability") or "").lower()
    if availability and availability != "public":
        return True

    return False


# ====== YT-DLP HOOKS ======

def _load_gui_config() -> dict:
    cfg_path = os.path.join(os.path.dirname(__file__), "yt_playlist_gui_config.json")
    if not os.path.isfile(cfg_path):
        return {}
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Could not read GUI config: {e}")
        return {}

def _save_gui_config(cfg: dict) -> None:
    cfg_path = os.path.join(os.path.dirname(__file__), "yt_playlist_gui_config.json")
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[WARN] Could not save GUI config: {e}")

def _is_permanent_error(error_message: str) -> bool:
    """
    Determine if an error is permanent (should exclude video) or transient (should retry).
    
    Permanent errors: Video unavailable, private, deleted, copyright
    Transient errors: Network issues, file system errors, temporary failures
    """
    error_lower = error_message.lower()
    
    # Permanent errors - should exclude
    permanent_patterns = [
        "video unavailable",
        "private video",
        "deleted video",
        "has been removed",
        "copyright",
        "not available",
        "this video is not available",
        "this video has been removed",
        "account associated with this video has been terminated",
        "video is no longer available",
        "members-only content",
        "join this channel",
        "age-restricted",
    ]
    
    # Transient errors - should retry
    transient_patterns = [
        "no such file or directory",
        "errno 2",
        "connection reset",
        "connection refused",
        "timeout",
        "network",
        "temporary failure",
        "unable to download",
        "http error 5",  # 500-599 server errors
        "http error 429",  # Rate limit
        "fragment",
        "part-frag",
        ".part",
    ]
    
    # Check for transient errors first (higher priority)
    for pattern in transient_patterns:
        if pattern in error_lower:
            return False  # Transient - should retry
    
    # Check for permanent errors
    for pattern in permanent_patterns:
        if pattern in error_lower:
            return True  # Permanent - should exclude
    
    # Default: treat as transient (safer to retry)
    return False


def _add_excluded_id_to_gui_config(playlist_url: str, vid: str, error_message: str = "") -> None:
    """
    Append vid to the playlist's excluded_ids in the GUI config (if not present).
    Only adds if error is permanent, not transient.
    """
    if not playlist_url or not vid:
        return
    
    # Check if error is permanent
    if error_message and not _is_permanent_error(error_message):
        print(f"[INFO] Transient error for {vid} - will retry in next session")
        return
    
    cfg = _load_gui_config()
    playlists = cfg.get("playlists") or []
    updated = False
    for p in playlists:
        if p.get("url") == playlist_url:
            excluded = p.get("excluded_ids") or []
            if vid not in excluded:
                excluded.append(vid)
                p["excluded_ids"] = excluded
                p["unavailable_count"] = int(p.get("unavailable_count", 0)) + 1
                updated = True
                print(f"[INFO] Permanently excluded {vid} from future downloads")
            break
    if updated:
        _save_gui_config(cfg)

def _progress_hook_custom(d):
    """
    Track download progress and errors.
    Note: With custom archive logic, we don't rely on this for skipped videos,
    but we still use it to catch errors reported by yt-dlp's hook system.
    """
    global FAILED_VIDEO_IDS, GLOBAL_CURRENT_PLAYLIST_URL

    status = d.get("status")
    info = d.get("info_dict") or {}
    if info.get("_type") == "playlist":
        return

    vid = info.get("id")

    if status == "error":
        err = d.get("error")
        msg = str(err)
        if vid:
            print(f"[WARN] Download failed (hook) for {vid}: {msg}")
            # Classify error and persist to GUI config if permanent
            # Only add to FAILED_VIDEO_IDS if it's a permanent error
            try:
                if GLOBAL_CURRENT_PLAYLIST_URL:
                    _add_excluded_id_to_gui_config(GLOBAL_CURRENT_PLAYLIST_URL, vid, msg)
                    # Only add to FAILED_VIDEO_IDS if it was actually excluded (permanent error)
                    if _is_permanent_error(msg):
                        FAILED_VIDEO_IDS.add(vid)
            except Exception as e:
                print(f"[WARN] Could not persist failed id {vid}: {e}")


def _slow_down_hook(d):
    if d.get("status") == "finished":
        if GLOBAL_RUNSTATE is not None and getattr(GLOBAL_RUNSTATE, "cancelled", False):
            print("Cancellation flag set. Skipping further delays.")
            return
        pause = random.uniform(3, 8)
        print(f"Pausing {pause:.1f}s to avoid hammering YouTube...")
        time.sleep(pause)


# ====== MODE 2: DOWNLOAD + EXTRACT ======

# def download_playlist_with_video_and_audio(url: str, as_mp3: bool = True) -> Set[str]:
#     """
#     MODE 2:
#       - Downloads bestvideo+bestaudio/best for a playlist/single video.
#       - Uses download_archive to only get new videos.
#       - If as_mp3 is True, extracts MP3 into audio subfolder.
#     Returns:
#       FAILED_VIDEO_IDS: set of failed/unavailable IDs for this run.
#     """
#     global SKIPPED_VIDEOS_ARCHIVE, FAILED_VIDEO_IDS
#     SKIPPED_VIDEOS_ARCHIVE = []
#     FAILED_VIDEO_IDS = set()

#     print("Fetching playlist information...")
#     try:
#         title = _get_playlist_info_title(url)
#     except Exception as e:
#         print(f"Could not fetch playlist info ({e}), using generic name.")
#         title = "playlist"

#     playlist_folder, archive_file, audio_folder = _build_playlist_paths(title)

#     print(f"\nBase path      : {BASE_DOWNLOAD_PATH}")
#     print(f"Playlist title : {title}")
#     print(f"Playlist folder: {playlist_folder}")
#     print(f"Archive file   : {archive_file}")
#     print(f"Audio folder   : {audio_folder}")

#     common_opts = {
#         "outtmpl": os.path.join(playlist_folder, "%(title)s.%(ext)s"),
#         "ignoreerrors": True,
#         "download_archive": archive_file,
#         "quiet": False,
#         "no_warnings": True,
#         "progress_hooks": [_progress_hook_archive, _slow_down_hook],
#     }

#     if USE_BROWSER_COOKIES:
#         common_opts["cookies_from_browser"] = (BROWSER_NAME,)
#     else:
#         if COOKIES_FILE and os.path.isfile(COOKIES_FILE):
#             common_opts["cookies"] = COOKIES_FILE

#     if USER_AGENT:
#         common_opts["user_agent"] = USER_AGENT
#     common_opts.update(_base_speed_opts())

#     ydl_opts = {
#         "format": "bestvideo+bestaudio/best",
#         "merge_output_format": "mp4",
#     }
#     ydl_opts.update(common_opts)

#     # First try to enumerate playlist entries (uses cached _get_playlist_entries)
#     entries = []
#     try:
#         entries = _get_playlist_entries(url, playlist_folder)
#     except Exception as e:
#         # _get_playlist_entries may raise on transient failures; fall back to direct download below
#         print(f"Warning: failed to enumerate playlist entries ({e}), will fall back to downloading the playlist URL.")

#     video_urls: List[str] = []
#     if entries:
#         print(f"Found {len(entries)} entries; filtering unavailable/private items...")
#         for e in entries:
#             if not e:
#                 continue
#             # skip entries detected as unavailable/private by heuristic
#             if is_entry_unavailable(e):
#                 vid = e.get("id") or e.get("url") or "unknown"
#                 print(f"  Skipping unavailable/private: {e.get('title') or vid} [{vid}]")
#                 # mark in FAILED_VIDEO_IDS so stats reflect it
#                 if e.get("id"):
#                     FAILED_VIDEO_IDS.add(e.get("id"))
#                 continue

#             # build full watch URL where necessary
#             vid = e.get("id") or e.get("url")
#             if not vid:
#                 continue
#             if str(vid).startswith("http"):
#                 video_urls.append(str(vid))
#             else:
#                 video_urls.append(f"https://www.youtube.com/watch?v={vid}")

#         if not video_urls:
#             print("No available videos to download after filtering; nothing to do.")
#     else:
#         # entries empty => fall back to playlist URL (single video or yt-dlp will expand)
#         print("Could not get entries list; falling back to downloading the provided URL.")

#     # Start download: prefer list of filtered URLs when available
#     print("\nStarting download...")
#     try:
#         with YoutubeDL(ydl_opts) as ydl:
#             if video_urls:
#                 ydl.download(video_urls)
#             else:
#                 ydl.download([url])
#     except Exception as e:
#         # ensure we capture any failed IDs already added by progress hook; re-raise if needed
#         print(f"[ERROR] Download run raised an exception: {e}")

#     if SKIPPED_VIDEOS_ARCHIVE:
#         print("\nVideos skipped (already in archive or on disk):")
#         for v in SKIPPED_VIDEOS_ARCHIVE:
#             print(f"  - {v.get('title') or 'Unknown'} [{v.get('id')}] — {v['reason']}")
#     else:
#         print("\nNo videos were skipped due to archive.")

#     if as_mp3:
#         print("\nExtracting audio to MP3 from downloaded videos...")
#         extract_audio_for_existing_playlist_folder(playlist_folder, audio_folder)

#     print(f"\nDone. Video files in:\n{playlist_folder}")
#     print(f"MP3 files in:\n{audio_folder}")

#     return FAILED_VIDEO_IDS

def download_playlist_with_video_and_audio(url: str, as_mp3: bool = True, excluded_ids: Set[str] | None = None) -> Set[str]:
    """
    MODE 2:
      - Downloads bestvideo+bestaudio/best for a playlist/single video.
      - Uses CUSTOM archive logic (not yt-dlp's download_archive).
      - Downloads only if: (a) ID not in archive.txt OR (b) ID in archive but file missing on disk
      - After successful download, verifies file exists then updates archive.txt
      - If as_mp3 is True, extracts MP3 into audio subfolder.
      - excluded_ids: set of video IDs to skip (from GUI config)
    Returns:
      FAILED_VIDEO_IDS: set of failed/unavailable IDs for this run.
    """
    global SKIPPED_VIDEOS_ARCHIVE, FAILED_VIDEO_IDS, GLOBAL_CURRENT_PLAYLIST_URL
    SKIPPED_VIDEOS_ARCHIVE = []
    FAILED_VIDEO_IDS = set()
    GLOBAL_CURRENT_PLAYLIST_URL = url  # set for hooks

    if excluded_ids is None:
        excluded_ids = set()

    try:
        print("Fetching playlist information...")
        title = _get_playlist_info_title(url)

        # Create folders immediately when playlist is added
        playlist_folder, archive_file, audio_folder = _build_playlist_paths(title, create_folders=True)

        print(f"\nBase path      : {BASE_DOWNLOAD_PATH}")
        print(f"Playlist title : {title}")
        print(f"Playlist folder: {playlist_folder}")
        print(f"Archive file   : {archive_file}")
        print(f"Audio folder   : {audio_folder}")

        # Load custom archive
        archived_ids = _load_custom_archive(archive_file)
        print(f"Loaded {len(archived_ids)} IDs from custom archive")

        # Get filtered video URLs (skip unavailable)
        entries = []
        try:
            entries = _get_playlist_entries(url, playlist_folder)
        except Exception as e:
            print(f"Warning: failed to enumerate playlist entries ({e}), will fall back to downloading the playlist URL.")

        videos_to_download: List[Tuple[str, str]] = []  # (video_id, video_url)
        
        if entries:
            print(f"Found {len(entries)} entries; filtering based on custom archive logic...")
            for e in entries:
                # Check cancellation during enumeration
                if GLOBAL_RUNSTATE is not None and getattr(GLOBAL_RUNSTATE, "cancelled", False):
                    print("\n⚠️ Cancellation detected during entry filtering. Stopping...")
                    return FAILED_VIDEO_IDS
                
                if not e:
                    continue
                
                vid = e.get("id") or e.get("url") or "unknown"
                
                # Skip if in excluded_ids (from GUI config)
                if vid in excluded_ids:
                    effective_title = _get_effective_title(e)
                    print(f"  Skipping (excluded): {effective_title} [{vid}]")
                    FAILED_VIDEO_IDS.add(vid)
                    continue
                
                # Skip if detected as unavailable/private by heuristic
                if is_entry_unavailable(e, excluded_ids=excluded_ids):
                    effective_title = _get_effective_title(e)
                    print(f"  Skipping unavailable/private: {effective_title} [{vid}]")
                    if e.get("id"):
                        FAILED_VIDEO_IDS.add(e.get("id"))
                    continue

                if not vid:
                    continue
                
                # Get effective title (with channel fallback for empty titles)
                video_title = _get_effective_title(e)
                
                # CUSTOM ARCHIVE LOGIC: Check if we should download
                # This also checks for old format (title only) and renames if found
                should_download = _should_download_video(archive_file, playlist_folder, vid, video_title)
                
                if not should_download:
                    print(f"  ✓ Already downloaded: {video_title} [{vid}]")
                    SKIPPED_VIDEOS_ARCHIVE.append({
                        "id": vid,
                        "title": video_title,
                        "reason": "already in custom archive and file exists on disk",
                    })
                    continue
                
                # Debug specific video
                if vid == "87XbYi98DTg":
                    print(f"[DEBUG] Video 87XbYi98DTg marked for download")
                    print(f"[DEBUG] Archive file: {archive_file}")
                    print(f"[DEBUG] Playlist folder: {playlist_folder}")
                    archived = _load_custom_archive(archive_file)
                    print(f"[DEBUG] In archive: {vid in archived}")
                    file_path = _get_video_file_path(playlist_folder, vid)
                    print(f"[DEBUG] File path found: {file_path}")
                
                # Add to download list
                if str(vid).startswith("http"):
                    video_url = str(vid)
                else:
                    video_url = f"https://www.youtube.com/watch?v={vid}"
                
                videos_to_download.append((vid, video_url))

        if not videos_to_download and entries:
            print("No new videos to download after filtering; all up to date.")
            return FAILED_VIDEO_IDS

        # ====== SMART BATCH MANAGEMENT ======
        # Load existing batch progress
        batch_progress = _load_batch_progress(playlist_folder)
        
        # Get current batch size (dynamically loaded from settings)
        batch_size = _get_batch_size()
        
        # Check if we have an ongoing batch
        has_ongoing_batch = (
            batch_progress["pending_video_ids"] and 
            not batch_progress.get("completed", False)
        )
        
        if has_ongoing_batch:
            # RESUME MODE: Continue existing batch
            print(f"\n{'='*60}")
            print(f"RESUMING BATCH DOWNLOAD")
            print(f"{'='*60}")
            
            # Detect new videos added to playlist since last batch
            old_pending_ids = set(batch_progress["pending_video_ids"])
            current_video_ids = set([vid for vid, _ in videos_to_download])
            new_video_ids = current_video_ids - old_pending_ids
            
            if new_video_ids:
                print(f"🆕 Detected {len(new_video_ids)} NEW videos added to playlist since last batch")
                # Add new videos to pending list
                batch_progress["pending_video_ids"].extend(list(new_video_ids))
                batch_progress["total_videos"] = batch_progress["total_videos"] + len(new_video_ids)
                _save_batch_progress(playlist_folder, batch_progress)
                print(f"   Updated batch progress to include new videos")
            
            print(f"Total videos in playlist: {batch_progress['total_videos']}")
            print(f"Already downloaded: {batch_progress['downloaded_count']}")
            print(f"Remaining (including new): {len(batch_progress['pending_video_ids'])}")
            print(f"Last batch: {batch_progress['last_batch_date']}")
            print(f"Batch size: {batch_progress['batch_size']}")
            
            # Filter videos_to_download to only include pending IDs
            pending_ids = set(batch_progress["pending_video_ids"])
            videos_to_download = [(vid, url) for vid, url in videos_to_download if vid in pending_ids]
            
        elif batch_progress.get("completed", False):
            # Previous batch completed - archive it and start fresh
            print(f"\n✓ Previous batch completed. Archiving old progress file...")
            _archive_completed_batch_progress(playlist_folder)
            
            # Check if new download is needed
            if len(videos_to_download) > batch_size:
                # Start new batch
                all_video_ids = [vid for vid, _ in videos_to_download]
                batch_progress = _initialize_batch_progress(playlist_folder, all_video_ids)
                
                print(f"\n{'='*60}")
                print(f"NEW BATCH DOWNLOAD STARTED")
                print(f"{'='*60}")
                print(f"Total videos to download: {len(videos_to_download)}")
                print(f"Batch size: {batch_size}")
                print(f"Estimated batches: {(len(videos_to_download) + batch_size - 1) // batch_size}")
                print(f"This session will download: {min(batch_size, len(videos_to_download))} videos")
                print(f"{'='*60}\n")
            else:
                # Small update, no batching needed
                print(f"\n✓ Small update detected ({len(videos_to_download)} videos)")
                print(f"   No batching needed (threshold: {batch_size})\n")
                
        elif len(videos_to_download) > batch_size:
            # First time batch - initialize new batch progress
            all_video_ids = [vid for vid, _ in videos_to_download]
            batch_progress = _initialize_batch_progress(playlist_folder, all_video_ids)
            
            print(f"\n{'='*60}")
            print(f"BATCH DOWNLOAD MODE ENABLED")
            print(f"{'='*60}")
            print(f"Total videos to download: {len(videos_to_download)}")
            print(f"Batch size: {batch_size}")
            print(f"Estimated batches: {(len(videos_to_download) + batch_size - 1) // batch_size}")
            print(f"This session will download: {min(batch_size, len(videos_to_download))} videos")
            print(f"{'='*60}\n")
        else:
            # Small download, no batching needed
            print(f"\n✓ Downloading {len(videos_to_download)} videos (no batching needed)\n")
        
        # Determine if we need to limit to batch size
        needs_batching = (
            has_ongoing_batch or 
            (batch_progress.get("total_videos", 0) > batch_size)
        )
        
        if needs_batching:
            # Limit to batch size for this session
            current_batch = videos_to_download[:batch_size]
            remaining_after_batch = len(videos_to_download) - len(current_batch)
            
            if remaining_after_batch > 0:
                print(f"⚠️  Note: {remaining_after_batch} videos will remain for next batch")
                print(f"   Run 'Download Videos' again to continue downloading remaining videos\n")
        else:
            # Download all videos in one go
            current_batch = videos_to_download

        # Prepare yt-dlp options WITHOUT download_archive (we manage it ourselves)
        common_opts = {
            "outtmpl": os.path.join(playlist_folder, "%(title|channel|Unknown)s [%(id)s].%(ext)s"),  # Use channel as fallback for empty titles
            "ignoreerrors": False,
            # NO download_archive - we manage it ourselves
            "quiet": False,
            "no_warnings": True,
            "progress_hooks": [_progress_hook_custom, _slow_down_hook],  # Keep hook to catch yt-dlp errors
        }

        if USE_BROWSER_COOKIES:
            print(f"✓ Loading cookies from {BROWSER_NAME} (browser is running)")
            common_opts["cookies_from_browser"] = (BROWSER_NAME,)
        elif COOKIES_FILE and os.path.isfile(COOKIES_FILE):
            print(f"✓ Loading cookies from file: {COOKIES_FILE}")
            common_opts["cookiefile"] = COOKIES_FILE
        else:
            print("⚠️  Warning: No valid cookies found. Age-restricted videos will likely fail.")

        if USER_AGENT:
            common_opts["user_agent"] = USER_AGENT
        common_opts.update(_base_speed_opts())

        ydl_opts = {
            "format": "bestvideo+bestaudio/best",
            "merge_output_format": "mp4",
        }
        ydl_opts.update(common_opts)

        print(f"\nStarting download of {len(current_batch)} videos in this batch...")
        
        # Download videos one by one with custom archive management
        successfully_downloaded = []
        
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.cache.remove()
                for idx, (vid, video_url) in enumerate(current_batch, 1):
                    # Check cancellation BEFORE each video
                    if GLOBAL_RUNSTATE is not None and getattr(GLOBAL_RUNSTATE, "cancelled", False):
                        print(f"\n⚠️ Cancellation detected at video {idx}/{len(current_batch)}. Stopping download...")
                        break
                    
                    # Prepare batch info string
                    batch_info = None
                    if needs_batching and batch_progress.get("total_videos", 0) > 0:
                        total_videos = batch_progress["total_videos"]
                        downloaded_so_far = batch_progress["downloaded_count"] + idx - 1
                        remaining = len(batch_progress["pending_video_ids"])
                        batch_info = f"{downloaded_so_far}/{total_videos} total ({remaining} remaining)"
                    
                    # Update progress BEFORE downloading
                    callback = GLOBAL_DOWNLOAD_PROGRESS_CALLBACK or GLOBAL_PROGRESS_CALLBACK
                    if callback is not None:
                        callback(len(current_batch), idx - 1, batch_info)
                    
                    try:
                        _log(f"[{idx}/{len(current_batch)}] Downloading: {vid}")
                        if batch_info:
                            _log(f"  Progress: {batch_info}")
                        
                        # Check if video is already in archive (shouldn't happen, but safety check)
                        archived_ids = _load_custom_archive(archive_file)
                        if vid in archived_ids:
                            _log(f"  ⚠️  Video {vid} already in archive - checking if file exists...")
                            existing_path = _get_video_file_path(playlist_folder, vid, wait_for_file=False)
                            if existing_path:
                                _log(f"  ✓ File found: {os.path.basename(existing_path)}")
                                _log(f"  Skipping download (already complete)")
                                successfully_downloaded.append(vid)
                                
                                # Update progress
                                callback = GLOBAL_DOWNLOAD_PROGRESS_CALLBACK or GLOBAL_PROGRESS_CALLBACK
                                if callback is not None:
                                    callback(len(current_batch), idx, batch_info)
                                
                                # Update batch progress
                                if needs_batching:
                                    _remove_from_batch_progress(playlist_folder, vid)
                                continue
                            else:
                                _log(f"  File not found despite being in archive - will attempt re-download")
                        
                        # Download the video
                        download_result = ydl.download([video_url])
                        _log(f"  yt-dlp download() returned: {download_result}")
                        
                        # List all files in folder that were modified in last 10 seconds
                        # This helps identify what file yt-dlp just created
                        import time as time_module
                        current_time = time_module.time()
                        recent_files = []
                        for pattern in ("*.mp4", "*.mkv", "*.webm", "*.m4v", "*.part"):
                            for f in glob.glob(os.path.join(playlist_folder, pattern)):
                                mtime = os.path.getmtime(f)
                                if current_time - mtime < 10:  # Modified in last 10 seconds
                                    recent_files.append((f, current_time - mtime))
                        
                        if recent_files:
                            _log(f"  Files modified in last 10 seconds:")
                            for f, age in sorted(recent_files, key=lambda x: x[1]):
                                basename = os.path.basename(f)
                                _log(f"    - {basename} ({age:.1f}s ago)")
                                if vid in basename:
                                    _log(f"      ^ Contains video ID {vid}")
                        else:
                            _log(f"  ⚠️  No files modified in last 10 seconds")
                            _log(f"      This means yt-dlp did not create or modify any file")
                            _log(f"      yt-dlp likely detected the file already exists and skipped download")
                            _log(f"      Searching for existing file with different naming...")
                        
                        # Check for .part files (incomplete downloads)
                        part_files = glob.glob(os.path.join(playlist_folder, "*.part"))
                        matching_part = [pf for pf in part_files if vid in pf]
                        if matching_part:
                            _log(f"  ⚠️  Incomplete download detected (.part file)")
                            _log(f"      File: {os.path.basename(matching_part[0])}")
                            _log(f"      This indicates the download was interrupted or failed")
                            _log(f"      Delete the .part file and retry download")
                            
                            # Update progress even for failed downloads
                            callback = GLOBAL_DOWNLOAD_PROGRESS_CALLBACK or GLOBAL_PROGRESS_CALLBACK
                            if callback is not None:
                                callback(len(current_batch), idx, batch_info)
                            continue
                        
                        # VERIFY file exists on disk before adding to archive
                        # Wait up to 5 seconds for file to appear (handles file system delays)
                        video_path = _get_video_file_path(playlist_folder, vid, wait_for_file=True)
                        
                        # If not found with standard pattern, try alternative search
                        if not video_path and download_result == 0:
                            _log(f"  Trying alternative file search methods...")
                            
                            # Method 1: Search for any file containing the video ID (case-insensitive)
                            try:
                                all_filenames = os.listdir(playlist_folder)
                                video_exts_tuple = (".mp4", ".mkv", ".webm", ".m4v")
                                vid_lower = vid.lower()
                                
                                for filename in all_filenames:
                                    full_path = os.path.join(playlist_folder, filename)
                                    if not os.path.isfile(full_path):
                                        continue
                                    if not any(filename.lower().endswith(ext) for ext in video_exts_tuple):
                                        continue
                                    
                                    filename_lower = filename.lower()
                                    if vid_lower in filename_lower:
                                        _log(f"  ✓ Found file with video ID (case-insensitive): {filename}")
                                        video_path = full_path
                                        break
                            except Exception as e:
                                _log(f"  ✗ Alternative search failed: {e}")
                        
                        if video_path:
                            _log(f"  ✓ Download verified, adding {vid} to archive")
                            _add_to_custom_archive(archive_file, vid)
                            successfully_downloaded.append(vid)
                            
                            # Notify that video was downloaded (for parallel extraction)
                            if GLOBAL_VIDEO_DOWNLOADED_CALLBACK is not None:
                                GLOBAL_VIDEO_DOWNLOADED_CALLBACK(video_path)
                            
                            # Update batch info for next iteration
                            if needs_batching and batch_progress.get("total_videos", 0) > 0:
                                total_videos = batch_progress["total_videos"]
                                downloaded_so_far = batch_progress["downloaded_count"] + idx
                                remaining = len(batch_progress["pending_video_ids"]) - 1
                                batch_info = f"{downloaded_so_far}/{total_videos} total ({remaining} remaining)"
                            
                            # Update progress AFTER successful download
                            callback = GLOBAL_DOWNLOAD_PROGRESS_CALLBACK or GLOBAL_PROGRESS_CALLBACK
                            if callback is not None:
                                callback(len(current_batch), idx, batch_info)
                            
                            # Update batch progress immediately after each successful download
                            # This ensures progress is saved even if app crashes
                            if needs_batching:
                                _remove_from_batch_progress(playlist_folder, vid)
                        else:
                            _log(f"  ⚠️  Download completed but file not found on disk for {vid}")
                            _log(f"      This is likely a file detection issue, not a permanent error")
                            _log(f"      Video will NOT be added to exclusion list")
                            
                            # DO NOT add to FAILED_VIDEO_IDS - this is not a permanent error
                            # The video might already exist but wasn't detected, or there's a naming issue
                            # Adding it to FAILED_VIDEO_IDS would cause it to be excluded permanently
                            
                            # Update progress even for failed downloads
                            callback = GLOBAL_DOWNLOAD_PROGRESS_CALLBACK or GLOBAL_PROGRESS_CALLBACK
                            if callback is not None:
                                callback(len(current_batch), idx, batch_info)
                            
                    except Exception as e:
                        error_msg = str(e)
                        print(f"[WARN] Download failed for {vid}: {error_msg}")
                        
                        # Classify error and persist to GUI config if permanent
                        # Only add to FAILED_VIDEO_IDS if it's a permanent error
                        try:
                            if GLOBAL_CURRENT_PLAYLIST_URL:
                                _add_excluded_id_to_gui_config(GLOBAL_CURRENT_PLAYLIST_URL, vid, error_msg)
                                # Only add to FAILED_VIDEO_IDS if it was actually excluded (permanent error)
                                if _is_permanent_error(error_msg):
                                    FAILED_VIDEO_IDS.add(vid)
                        except Exception as persist_err:
                            print(f"[WARN] Could not persist failed id {vid}: {persist_err}")
                        continue
                        
        except Exception as e:
            print(f"\n❌ Download run failed: {e}")

        print(f"\n✓ Successfully downloaded and archived: {len(successfully_downloaded)} videos")
        
        # Update batch progress and archive if completed
        if needs_batching:
            batch_progress = _update_batch_progress(playlist_folder, successfully_downloaded)
            print(f"\n{'='*60}")
            print(f"BATCH PROGRESS UPDATE")
            print(f"{'='*60}")
            print(f"Total videos: {batch_progress['total_videos']}")
            print(f"Downloaded: {batch_progress['downloaded_count']}")
            print(f"Remaining: {len(batch_progress['pending_video_ids'])}")
            
            if batch_progress['completed']:
                print(f"✓ All videos downloaded! Batch complete.")
                print(f"   Archiving batch progress file...")
                _archive_completed_batch_progress(playlist_folder)
            else:
                print(f"⚠️  {len(batch_progress['pending_video_ids'])} videos remaining")
                print(f"   Run 'Download Videos' again to continue")
            print(f"{'='*60}\n")
        
        if SKIPPED_VIDEOS_ARCHIVE:
            print(f"\nVideos skipped (already downloaded): {len(SKIPPED_VIDEOS_ARCHIVE)}")

        if as_mp3:
            # Check if cancelled before extracting
            if GLOBAL_RUNSTATE is not None and getattr(GLOBAL_RUNSTATE, "cancelled", False):
                print("\n⚠️ Cancellation requested. Skipping audio extraction.")
            else:
                print("\nExtracting audio to MP3 from downloaded videos...")
                try:
                    extract_audio_for_existing_playlist_folder(playlist_folder, audio_folder)
                except KeyboardInterrupt:
                    print("\n⚠️ Audio extraction cancelled by user.")

        # Note: Failed IDs are already persisted to GUI config during download
        # FAILED_VIDEO_IDS now only contains permanent failures for stats display

    finally:
        GLOBAL_CURRENT_PLAYLIST_URL = None

    return FAILED_VIDEO_IDS

# ====== MODE 1: EXTRACT FROM EXISTING ======

def extract_audio_for_existing_playlist(title: str):
    safe_title = _sanitize_title(title)
    playlist_folder = os.path.join(BASE_DOWNLOAD_PATH, safe_title)
    audio_folder = os.path.join(playlist_folder, safe_title)
    os.makedirs(audio_folder, exist_ok=True)
    extract_audio_for_existing_playlist_folder(playlist_folder, audio_folder)


def _extract_single_audio(vid_path: str, audio_folder: str, ffmpeg_path: str, idx: int, total: int) -> Dict:
    """Extract audio from a single video file. Returns result dict."""
    from subprocess import run, DEVNULL, CalledProcessError
    import threading
    
    thread_id = threading.current_thread().name
    base_name = os.path.splitext(os.path.basename(vid_path))[0]
    
    # Determine output file extension based on mode
    if AUDIO_EXTRACT_MODE == "copy":
        # For copy mode, use .m4a for AAC audio (most common in YouTube videos)
        # Note: May fail for some codecs, automatic fallback to MP3 will handle it
        audio_ext = ".m4a"
    elif AUDIO_EXTRACT_MODE == "opus":
        audio_ext = ".opus"
    else:  # mp3_best or mp3_high
        audio_ext = ".mp3"
    
    audio_path = os.path.join(audio_folder, base_name + audio_ext)
    
    # Check if audio already exists in ANY format (mp3, m4a, opus, etc.)
    # This handles cases where extraction mode changed between runs
    audio_extensions = [".mp3", ".m4a", ".opus", ".mka", ".aac", ".ogg"]
    for ext in audio_extensions:
        existing_audio = os.path.join(audio_folder, base_name + ext)
        if os.path.isfile(existing_audio):
            return {
                "status": "skipped",
                "video": vid_path,
                "audio": existing_audio,
                "reason": f"already exists as {ext}",
                "thread_id": thread_id
            }
    
    # Check if video file exists and is readable
    if not os.path.exists(vid_path):
        return {
            "status": "failed",
            "video": vid_path,
            "audio": audio_path,
            "error": "Video file not found",
            "thread_id": thread_id
        }
    
    if os.path.getsize(vid_path) == 0:
        return {
            "status": "failed",
            "video": vid_path,
            "audio": audio_path,
            "error": "Video file is empty (0 bytes)",
            "thread_id": thread_id
        }
    
    # Build ffmpeg command based on extraction mode
    if AUDIO_EXTRACT_MODE == "copy":
        cmd = [
            ffmpeg_path, "-y", "-i", vid_path,
            "-vn", "-acodec", "copy", audio_path,
        ]
        mode_label = "copy"
    elif AUDIO_EXTRACT_MODE == "opus":
        cmd = [
            ffmpeg_path, "-y", "-i", vid_path,
            "-vn", "-acodec", "libopus", "-b:a", "128k", audio_path,
        ]
        mode_label = "OPUS"
    elif AUDIO_EXTRACT_MODE == "mp3_best":
        cmd = [
            ffmpeg_path, "-y", "-i", vid_path,
            "-vn", "-acodec", "libmp3lame", "-q:a", "0", audio_path,
        ]
        mode_label = "MP3 best"
    else:  # mp3_high
        cmd = [
            ffmpeg_path, "-y", "-i", vid_path,
            "-vn", "-acodec", "libmp3lame", "-q:a", "2", audio_path,
        ]
        mode_label = "MP3 high"
    
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{thread_id}] [{idx}/{total}] Extracting ({mode_label}): {os.path.basename(vid_path)}")
    
    try:
        start = time.time()
        # First attempt with original command
        result = run(cmd, stdout=DEVNULL, stderr=DEVNULL, check=False)
        
        if result.returncode == 0:
            duration = time.time() - start
            print(f"[{timestamp}] [{thread_id}] [{idx}/{total}] ✓ Completed in {duration:.1f}s: {os.path.basename(audio_path)}")
            return {
                "status": "success",
                "video": vid_path,
                "audio": audio_path,
                "thread_id": thread_id,
                "duration": duration
            }
        else:
            # First attempt failed - try fallback strategies
            error_code = result.returncode
            
            # Error -22 (4294967274) often means invalid argument or no audio stream
            # Try with re-encoding instead of copy
            if AUDIO_EXTRACT_MODE == "copy" and error_code in [4294967274, -22, 22]:
                print(f"[{timestamp}] [{thread_id}] [{idx}/{total}] Copy mode failed, trying re-encode...")
                
                # Fallback to MP3 encoding
                fallback_audio_path = os.path.join(audio_folder, base_name + ".mp3")
                fallback_cmd = [
                    ffmpeg_path, "-y", "-i", vid_path,
                    "-vn", "-acodec", "libmp3lame", "-q:a", "2", fallback_audio_path,
                ]
                
                fallback_result = run(fallback_cmd, stdout=DEVNULL, stderr=DEVNULL, check=False)
                
                if fallback_result.returncode == 0:
                    duration = time.time() - start
                    print(f"[{timestamp}] [{thread_id}] [{idx}/{total}] ✓ Completed with fallback in {duration:.1f}s: {os.path.basename(fallback_audio_path)}")
                    return {
                        "status": "success",
                        "video": vid_path,
                        "audio": fallback_audio_path,
                        "thread_id": thread_id,
                        "duration": duration,
                        "fallback": True
                    }
            
            # All attempts failed
            print(f"[{timestamp}] [{thread_id}] [{idx}/{total}] ⚠️  Failed: {os.path.basename(vid_path)} (error code: {error_code})")
            return {
                "status": "failed",
                "video": vid_path,
                "audio": audio_path,
                "error": f"FFmpeg error code: {error_code}",
                "thread_id": thread_id
            }
    except Exception as e:
        print(f"[{timestamp}] [{thread_id}] [{idx}/{total}] ⚠️  Unexpected error: {os.path.basename(vid_path)} - {e}")
        return {
            "status": "failed",
            "video": vid_path,
            "audio": audio_path,
            "error": str(e),
            "thread_id": thread_id
        }

def extract_audio_for_existing_playlist_folder(playlist_folder: str, audio_folder: str):
    global SKIPPED_AUDIO_EXISTING, EXTRACTED_AUDIO
    SKIPPED_AUDIO_EXISTING = []
    EXTRACTED_AUDIO = []

    if not os.path.isdir(playlist_folder):
        print(f"Playlist folder does not exist: {playlist_folder}")
        return

    ffmpeg_path = _find_ffmpeg_windows()
    if not ffmpeg_path:
        print("FFmpeg not found; cannot extract audio.")
        return

    print(f"\nUsing FFmpeg at: {ffmpeg_path}")
    print(f"Scanning for video files in: {playlist_folder}")
    print(f"Audio output folder: {audio_folder}")
    print(f"Extraction mode: {AUDIO_EXTRACT_MODE}")
    print(f"Parallel workers: {MAX_EXTRACTION_WORKERS}\n")

    video_exts = ("*.mp4", "*.mkv", "*.webm", "*.m4v")
    video_files: List[str] = []
    for pattern in video_exts:
        video_files.extend(glob.glob(os.path.join(playlist_folder, pattern)))

    if not video_files:
        print("No video files found to extract audio from.")
        return

    total = len(video_files)
    print(f"Found {total} video files to process\n")
    
    start_time = time.time()
    completed = 0
    failed = 0
    
    # Use ThreadPoolExecutor for parallel extraction
    with ThreadPoolExecutor(max_workers=MAX_EXTRACTION_WORKERS) as executor:
        # Submit all extraction tasks
        future_to_video = {
            executor.submit(_extract_single_audio, vid_path, audio_folder, ffmpeg_path, idx, total): vid_path
            for idx, vid_path in enumerate(video_files, start=1)
        }
        
        # Process results as they complete
        for future in as_completed(future_to_video):
            # Check for cancellation
            if GLOBAL_RUNSTATE is not None and getattr(GLOBAL_RUNSTATE, "cancelled", False):
                print("\n⚠️  Cancellation requested. Stopping extraction...")
                executor.shutdown(wait=False, cancel_futures=True)
                break
            
            vid_path = future_to_video[future]
            try:
                result = future.result()
                completed += 1
                
                if result["status"] == "skipped":
                    SKIPPED_AUDIO_EXISTING.append({"video": result["video"], "audio": result["audio"]})
                elif result["status"] == "success":
                    EXTRACTED_AUDIO.append({"video": result["video"], "audio": result["audio"]})
                elif result["status"] == "failed":
                    failed += 1
                
                # Update progress
                callback = GLOBAL_EXTRACT_PROGRESS_CALLBACK or GLOBAL_PROGRESS_CALLBACK
                if callback is not None:
                    callback(total, completed)
                    
            except Exception as e:
                print(f"  ⚠️  Unexpected error processing {os.path.basename(vid_path)}: {e}")
                failed += 1
    
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n" + "="*60)
    print("Audio extraction summary:")
    print(f"  Total processed: {completed}/{total}")
    print(f"  Newly extracted: {len(EXTRACTED_AUDIO)}")
    print(f"  Skipped (already exist): {len(SKIPPED_AUDIO_EXISTING)}")
    print(f"  Failed: {failed}")
    print(f"  Time taken: {duration:.1f} seconds")
    if len(EXTRACTED_AUDIO) > 0:
        print(f"  Average: {duration/len(EXTRACTED_AUDIO):.1f} sec/file")
    print("="*60)

    if SKIPPED_AUDIO_EXISTING and len(SKIPPED_AUDIO_EXISTING) <= 10:
        print("\nSkipped (already exist):")
        for item in SKIPPED_AUDIO_EXISTING:
            print(f"  - {os.path.basename(item['audio'])}")
    elif len(SKIPPED_AUDIO_EXISTING) > 10:
        print(f"\nSkipped {len(SKIPPED_AUDIO_EXISTING)} files (already exist)")

    if EXTRACTED_AUDIO and len(EXTRACTED_AUDIO) <= 10:
        print("\nNewly extracted:")
        for item in EXTRACTED_AUDIO:
            print(f"  - {os.path.basename(item['audio'])}")
    elif len(EXTRACTED_AUDIO) > 10:
        print(f"\nExtracted {len(EXTRACTED_AUDIO)} new audio files")
