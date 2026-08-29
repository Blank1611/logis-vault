#!/usr/bin/env python3
"""
yt_playlist_audio_tools.py

Shared tools for:
1) Downloading YouTube playlists with best video + audio and extracting MP3s.
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

def _load_config(config_path: str = "config.json") -> dict:
    """Load configuration from JSON file."""
    if not os.path.isfile(config_path):
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, "r") as f:
        return json.load(f)


CONFIG = _load_config()

# ====== USER CONFIG (DEFAULTS, CAN BE OVERRIDDEN BY GUI) ======

BASE_DOWNLOAD_PATH = CONFIG.get("base_download_path")
USE_BROWSER_COOKIES = CONFIG.get("use_browser_cookies", False)
BROWSER_NAME = CONFIG.get("browser_name", "chrome")  # chrome, firefox, edge, safari
COOKIES_FILE = CONFIG.get("cookies_file")
USER_AGENT = "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Mobile Safari/537.36"
CONCURRENT_FRAGMENTS = 4

# Audio extraction settings
# Options:
#   "copy" - Copy original audio codec (no re-encoding, best quality, preserves original format)
#   "mp3_best" - MP3 VBR quality 0 (~245kbps, best MP3 quality)
#   "mp3_high" - MP3 VBR quality 2 (~190kbps, high quality, smaller files)
#   "opus" - OPUS codec (YouTube's native format, excellent quality at lower bitrates)
AUDIO_EXTRACT_MODE = CONFIG.get("audio_extract_mode", "mp3_best")

# Parallel extraction settings
# Number of concurrent ffmpeg processes for audio extraction
# Recommended: Number of CPU cores (default: 4)
MAX_EXTRACTION_WORKERS = CONFIG.get("max_extraction_workers", 4)

# Batch download settings
# Maximum videos to download per session to avoid bot detection
BATCH_SIZE = CONFIG.get("batch_size", 200)
# Delay between batches (in seconds) - not used for multi-day batching
BATCH_DELAY = CONFIG.get("batch_delay", 300)  # 5 minutes


# ====== GLOBALS ======

SKIPPED_VIDEOS_ARCHIVE: List[Dict] = []
SKIPPED_AUDIO_EXISTING: List[Dict] = []
EXTRACTED_AUDIO: List[Dict] = []

GLOBAL_PROGRESS_CALLBACK = None  # set by GUI
GLOBAL_RUNSTATE = None           # SimpleNamespace(cancelled=bool) set by GUI

FAILED_VIDEO_IDS: Set[str] = set()  # IDs that failed in last download run
PLAYLIST_INFO_CACHE: Dict[str, dict] = {} # Cache for playlist info extracted via yt-dlp.extract_info()

# NEW global to let hooks know which playlist we're processing
GLOBAL_CURRENT_PLAYLIST_URL: Optional[str] = None


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


def _video_exists_on_disk(playlist_folder: str, video_id: str, video_title: str = None) -> bool:
    """
    Check if a video file with the given ID exists on disk.
    If not found by ID but video_title provided, searches for old format (title only)
    and automatically renames to new format.
    """
    video_exts = ("*.mp4", "*.mkv", "*.webm", "*.m4v")
    
    # First, check if file exists in new format (with video ID)
    for pattern in video_exts:
        files = glob.glob(os.path.join(playlist_folder, pattern))
        for file in files:
            # Check if video ID is in filename (format: [video_id] or _video_id.)
            if f"[{video_id}]" in file or f"_{video_id}." in file:
                return True
    
    # If not found and title provided, try to find and rename old format
    if video_title:
        if _find_video_by_title_and_rename(playlist_folder, video_id, video_title):
            return True
    
    return False

def _should_download_video(archive_file: str, playlist_folder: str, video_id: str, video_title: str = None) -> bool:
    """
    Determine if a video should be downloaded based on:
    a. ID does not exist in archive.txt, OR
    b. ID exists in archive but file not actually on disk (checks old format too)
    
    If video exists in old format (title only), automatically renames to new format.
    """
    archived_ids = _load_custom_archive(archive_file)
    
    # Case a: Not in archive at all
    if video_id not in archived_ids:
        return True
    
    # Case b: In archive but file missing on disk
    # This also checks for old format and renames if found
    if not _video_exists_on_disk(playlist_folder, video_id, video_title):
        print(f"  ⚠️  Video {video_id} in archive but missing on disk - will re-download")
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
            "batch_size": BATCH_SIZE,
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
            "batch_size": BATCH_SIZE,
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
        "batch_size": BATCH_SIZE,
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
        "concurrent_fragment_downloads": CONCURRENT_FRAGMENTS,
        "continuedl": True,
        "retries": 5,
        "fragment_retries": 5,
        "noprogress": False,
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
                    print(f"  Skipping (excluded): {e.get('title') or vid} [{vid}]")
                    FAILED_VIDEO_IDS.add(vid)
                    continue
                
                # Skip if detected as unavailable/private by heuristic
                if is_entry_unavailable(e, excluded_ids=excluded_ids):
                    print(f"  Skipping unavailable/private: {e.get('title') or vid} [{vid}]")
                    if e.get("id"):
                        FAILED_VIDEO_IDS.add(e.get("id"))
                    continue

                if not vid:
                    continue
                
                # Get video title for old format detection
                video_title = e.get('title') or None
                
                # CUSTOM ARCHIVE LOGIC: Check if we should download
                # This also checks for old format (title only) and renames if found
                if not _should_download_video(archive_file, playlist_folder, vid, video_title):
                    print(f"  ✓ Already downloaded: {video_title or vid} [{vid}]")
                    SKIPPED_VIDEOS_ARCHIVE.append({
                        "id": vid,
                        "title": video_title or vid,
                        "reason": "already in custom archive and file exists on disk",
                    })
                    continue
                
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
            if len(videos_to_download) > BATCH_SIZE:
                # Start new batch
                all_video_ids = [vid for vid, _ in videos_to_download]
                batch_progress = _initialize_batch_progress(playlist_folder, all_video_ids)
                
                print(f"\n{'='*60}")
                print(f"NEW BATCH DOWNLOAD STARTED")
                print(f"{'='*60}")
                print(f"Total videos to download: {len(videos_to_download)}")
                print(f"Batch size: {BATCH_SIZE}")
                print(f"Estimated batches: {(len(videos_to_download) + BATCH_SIZE - 1) // BATCH_SIZE}")
                print(f"This session will download: {min(BATCH_SIZE, len(videos_to_download))} videos")
                print(f"{'='*60}\n")
            else:
                # Small update, no batching needed
                print(f"\n✓ Small update detected ({len(videos_to_download)} videos)")
                print(f"   No batching needed (threshold: {BATCH_SIZE})\n")
                
        elif len(videos_to_download) > BATCH_SIZE:
            # First time batch - initialize new batch progress
            all_video_ids = [vid for vid, _ in videos_to_download]
            batch_progress = _initialize_batch_progress(playlist_folder, all_video_ids)
            
            print(f"\n{'='*60}")
            print(f"BATCH DOWNLOAD MODE ENABLED")
            print(f"{'='*60}")
            print(f"Total videos to download: {len(videos_to_download)}")
            print(f"Batch size: {BATCH_SIZE}")
            print(f"Estimated batches: {(len(videos_to_download) + BATCH_SIZE - 1) // BATCH_SIZE}")
            print(f"This session will download: {min(BATCH_SIZE, len(videos_to_download))} videos")
            print(f"{'='*60}\n")
        else:
            # Small download, no batching needed
            print(f"\n✓ Downloading {len(videos_to_download)} videos (no batching needed)\n")
        
        # Determine if we need to limit to batch size
        needs_batching = (
            has_ongoing_batch or 
            (batch_progress.get("total_videos", 0) > BATCH_SIZE)
        )
        
        if needs_batching:
            # Limit to batch size for this session
            current_batch = videos_to_download[:BATCH_SIZE]
            remaining_after_batch = len(videos_to_download) - len(current_batch)
            
            if remaining_after_batch > 0:
                print(f"⚠️  Note: {remaining_after_batch} videos will remain for next batch")
                print(f"   Run 'Download Videos' again to continue downloading remaining videos\n")
        else:
            # Download all videos in one go
            current_batch = videos_to_download

        # Prepare yt-dlp options WITHOUT download_archive (we manage it ourselves)
        common_opts = {
            "outtmpl": os.path.join(playlist_folder, "%(title)s [%(id)s].%(ext)s"),  # Include ID in filename
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
                for idx, (vid, video_url) in enumerate(current_batch, 1):
                    # Check cancellation BEFORE each video
                    if GLOBAL_RUNSTATE is not None and getattr(GLOBAL_RUNSTATE, "cancelled", False):
                        print(f"\n⚠️ Cancellation detected at video {idx}/{len(current_batch)}. Stopping download...")
                        break
                    
                    try:
                        print(f"\n[{idx}/{len(videos_to_download)}] Downloading: {vid}")
                        ydl.download([video_url])
                        
                        # VERIFY file exists on disk before adding to archive
                        if _video_exists_on_disk(playlist_folder, vid):
                            print(f"  ✓ Download verified, adding {vid} to archive")
                            _add_to_custom_archive(archive_file, vid)
                            successfully_downloaded.append(vid)
                            
                            # Update batch progress immediately after each successful download
                            # This ensures progress is saved even if app crashes
                            if needs_batching:
                                _remove_from_batch_progress(playlist_folder, vid)
                        else:
                            print(f"  ⚠️  Download completed but file not found on disk for {vid}")
                            FAILED_VIDEO_IDS.add(vid)
                            
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
                if GLOBAL_PROGRESS_CALLBACK is not None:
                    GLOBAL_PROGRESS_CALLBACK(total, completed)
                    
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
