"""
Onboarding & Auto-Discovery Service for yt_serve.
Scans standard download directories, parses existing playlists & media files,
and populates the SQLite database (Playlist & tracks index) in <3 seconds.
"""

import os
import re
import json
import glob
import logging
import threading
import time
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.database import SessionLocal, Playlist, Track
from app.core.track_indexer import index_track
from app.core.logging_engine import get_logger

logger = get_logger("app.services.onboarding_service")

# Regex to extract 11-char YouTube video ID from filenames like "Title [dQw4w9WgXcQ].mp4" or "Title_dQw4w9WgXcQ.mp3"
YOUTUBE_ID_REGEX = re.compile(r'\[([a-zA-Z0-9_-]{11})\]|_([a-zA-Z0-9_-]{11})(?:\.[a-zA-Z0-9]+)?$')


def extract_video_id_from_filename(filename: str) -> Optional[str]:
    """Extract 11-character YouTube video ID from a filename."""
    match = YOUTUBE_ID_REGEX.search(filename)
    if match:
        return match.group(1) or match.group(2)
    return None


def scan_download_directory(base_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Scan a base download directory for existing playlist subdirectories,
    extract metadata, and return a preview of discovered playlists and tracks.
    """
    target_path = base_path or settings.BASE_DOWNLOAD_PATH
    if not target_path or not os.path.exists(target_path):
        return {
            "base_path": target_path,
            "exists": False,
            "total_folders_scanned": 0,
            "discovered_playlists_count": 0,
            "total_estimated_tracks": 0,
            "discovered_playlists": []
        }

    discovered = []
    unmanaged_folders = []
    total_tracks_count = 0
    excluded_dirs = settings.get_excluded_directories()

    try:
        entries = sorted(os.listdir(target_path))
    except Exception as e:
        logger.error(f"Error listing base path {target_path}: {e}")
        return {
            "base_path": target_path,
            "exists": True,
            "error": str(e),
            "total_folders_scanned": 0,
            "discovered_playlists_count": 0,
            "unmanaged_folders_count": 0,
            "total_estimated_tracks": 0,
            "discovered_playlists": [],
            "unmanaged_folders": []
        }

    for entry in entries:
        folder_path = os.path.join(target_path, entry)
        if not os.path.isdir(folder_path):
            continue

        # Skip internal system, temp, or explicitly excluded folders
        entry_lower = entry.lower()
        if entry.startswith('.') or entry_lower in excluded_dirs:
            continue

        playlist_title = entry
        playlist_url = ""
        total_online_count = 0
        archived_ids = set()
        video_files = []
        audio_files = []

        # 1. Check for playlist_info.json or snapshots
        info_json_candidates = [
            os.path.join(folder_path, "playlist_info.json"),
            os.path.join(folder_path, "playlist_info_snapshot", "playlist_info.json"),
        ]
        # Also check for any .info.json files
        snapshot_dir = os.path.join(folder_path, "playlist_info_snapshot")
        if os.path.isdir(snapshot_dir):
            for f in os.listdir(snapshot_dir):
                if f.endswith('.json'):
                    info_json_candidates.append(os.path.join(snapshot_dir, f))

        for candidate in info_json_candidates:
            if os.path.isfile(candidate):
                try:
                    with open(candidate, "r", encoding="utf-8") as jf:
                        data = json.load(jf)
                        if isinstance(data, dict):
                            playlist_title = data.get("title") or playlist_title
                            playlist_url = (
                                data.get("webpage_url") or 
                                data.get("url") or 
                                data.get("original_url") or 
                                ""
                            )
                            if not playlist_url and data.get("id"):
                                playlist_url = f"https://www.youtube.com/playlist?list={data.get('id')}"
                            total_online_count = data.get("playlist_count") or len(data.get("entries", []))
                            if playlist_url:
                                break
                except Exception as json_err:
                    logger.debug(f"Could not parse info json {candidate}: {json_err}")

        # 2. Check archive.txt / downloaded_videos.txt
        for archive_name in ("archive.txt", "downloaded_videos.txt"):
            arch_path = os.path.join(folder_path, archive_name)
            if os.path.isfile(arch_path):
                try:
                    with open(arch_path, "r", encoding="utf-8") as af:
                        for line in af:
                            line = line.strip()
                            if line:
                                # "youtube <id>" or raw id
                                parts = line.split()
                                vid = parts[-1] if len(parts) > 1 else line
                                archived_ids.add(vid)
                except Exception as arch_err:
                    logger.debug(f"Could not read archive {arch_path}: {arch_err}")

        # 3. Find video media files
        for ext in ("*.mp4", "*.mkv", "*.webm", "*.m4v"):
            for vfile in glob.glob(os.path.join(folder_path, ext)):
                if not vfile.endswith('.part'):
                    video_files.append(vfile)

        # 4. Find audio media files (both in root and safe title subfolder)
        for ext in ("*.mp3", "*.m4a", "*.opus", "*.flac", "*.wav"):
            for afile in glob.glob(os.path.join(folder_path, ext)):
                audio_files.append(afile)
            for afile in glob.glob(os.path.join(folder_path, "**", ext), recursive=True):
                if afile not in audio_files:
                    audio_files.append(afile)

        # Strict Qualification Criterion: Only classify as discovered playlist if valid playlist_info.json gave a URL
        if playlist_url:
            track_count = max(len(video_files), len(audio_files), len(archived_ids))
            total_tracks_count += track_count

            discovered.append({
                "folder_name": entry,
                "folder_path": folder_path,
                "title": playlist_title,
                "url": playlist_url,
                "video_count": len(video_files),
                "audio_count": len(audio_files),
                "archived_count": len(archived_ids),
                "total_online_count": total_online_count,
                "video_files": video_files,
                "audio_files": audio_files,
                "archived_ids": list(archived_ids),
            })
        else:
            # Unmanaged folder classification (never generate fake URL)
            unmanaged_folders.append({
                "folder_name": entry,
                "folder_path": folder_path,
                "video_count": len(video_files),
                "audio_count": len(audio_files),
                "total_files": len(video_files) + len(audio_files),
            })

    return {
        "base_path": target_path,
        "exists": True,
        "total_folders_scanned": len(entries),
        "discovered_playlists_count": len(discovered),
        "unmanaged_folders_count": len(unmanaged_folders),
        "total_estimated_tracks": total_tracks_count,
        "discovered_playlists": discovered,
        "unmanaged_folders": unmanaged_folders
    }


def ingest_discovered_library(
    discovered_items: Optional[List[Dict[str, Any]]] = None,
    base_path: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Ingest discovered playlists and tracks into SQLite database using repositories.
    Safe and idempotent - will not duplicate existing playlists or tracks.
    """
    from app.repositories import PlaylistRepository, TrackRepository
    from app.models.database import get_db_context, Playlist, Track

    with get_db_context(db) as session:
        if discovered_items is None:
            scan_res = scan_download_directory(base_path)
            discovered_items = scan_res.get("discovered_playlists", [])

        imported_count = 0
        skipped_count = 0
        tracks_indexed_count = 0

        for item in discovered_items:
            title = item.get("title") or item.get("folder_name")
            url = item.get("url")
            if not url:
                logger.warning(f"Skipping ingestion for item without URL: {item.get('folder_name')}")
                continue
            
            # Check if playlist already exists
            existing = PlaylistRepository.get_by_url_or_title(url=url, title=title, db=session)

            if existing:
                playlist_id = existing.id
                skipped_count += 1
            else:
                new_playlist = PlaylistRepository.create(
                    title=title,
                    url=url,
                    playlist_count=item.get("total_online_count") or max(item.get("video_count", 0), item.get("archived_count", 0)),
                    local_count=max(item.get("video_count", 0), item.get("audio_count", 0)),
                    db=session,
                )
                playlist_id = new_playlist.id
                imported_count += 1

            # Index tracks from video files
            audio_map = {}
            for afile in item.get("audio_files", []):
                vid = extract_video_id_from_filename(os.path.basename(afile))
                if vid:
                    audio_map[vid] = afile

            indexed_ids = set()
            for vfile in item.get("video_files", []):
                fname = os.path.basename(vfile)
                vid = extract_video_id_from_filename(fname)
                if not vid:
                    continue

                song_title = os.path.splitext(fname)[0]
                # Strip [video_id] from title
                song_title = re.sub(r'\[[a-zA-Z0-9_-]{11}\]', '', song_title).strip()
                if not song_title:
                    song_title = fname

                audio_file = audio_map.get(vid)
                index_track(
                    video_id=vid,
                    title=song_title,
                    filepath=vfile,
                    playlist_id=playlist_id,
                    audio_filepath=audio_file,
                    db=session
                )
                indexed_ids.add(vid)
                tracks_indexed_count += 1

            # Also index any audio-only files not already covered
            for afile in item.get("audio_files", []):
                fname = os.path.basename(afile)
                vid = extract_video_id_from_filename(fname)
                if not vid or vid in indexed_ids:
                    continue

                song_title = os.path.splitext(fname)[0]
                song_title = re.sub(r'\[[a-zA-Z0-9_-]{11}\]', '', song_title).strip()
                if not song_title:
                    song_title = fname

                index_track(
                    video_id=vid,
                    title=song_title,
                    filepath=afile,
                    playlist_id=playlist_id,
                    audio_filepath=afile,
                    db=session
                )
                indexed_ids.add(vid)
                tracks_indexed_count += 1

        logger.info(f"Onboarding complete: {imported_count} playlists imported, {skipped_count} existing, {tracks_indexed_count} tracks indexed.")

        return {
            "status": "success",
            "playlists_imported": imported_count,
            "playlists_skipped": skipped_count,
            "tracks_indexed": tracks_indexed_count,
            "total_playlists": session.query(Playlist).count(),
            "total_tracks": session.query(Track).count(),
        }


def batch_link_unmanaged_folders(
    items: List[Dict[str, Any]],
    global_rename: Optional[bool] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Batch link unmanaged folders to valid YouTube playlists.
    Each item in items contains:
      - folder_path: path to unmanaged folder (or folder_name relative to BASE_DOWNLOAD_PATH)
      - playlist_url: YouTube playlist URL
      - rename_folder: Optional[bool]
    """
    from app.repositories import PlaylistRepository
    from app.models.database import get_db_context, Playlist, Track
    from app.core.yt_playlist_audio_tools import _get_playlist_info, _sanitize_title

    results = []
    linked_count = 0
    failed_count = 0

    with get_db_context(db) as session:
        for item in items:
            folder_path = item.get("folder_path")
            if not folder_path:
                folder_name = item.get("folder_name")
                if folder_name:
                    folder_path = os.path.join(settings.BASE_DOWNLOAD_PATH, folder_name)

            if not folder_path or not os.path.exists(folder_path):
                failed_count += 1
                results.append({
                    "folder_path": folder_path,
                    "success": False,
                    "error": "Directory does not exist on disk"
                })
                continue

            raw_url = (item.get("playlist_url") or "").strip()
            if not raw_url:
                failed_count += 1
                results.append({
                    "folder_path": folder_path,
                    "success": False,
                    "error": "Playlist URL is required"
                })
                continue

            try:
                # 1. Fetch playlist metadata
                try:
                    info = _get_playlist_info(raw_url)
                except Exception as fetch_err:
                    logger.warning(f"Could not fetch online metadata for {raw_url}: {fetch_err}. Proceeding with minimal info.")
                    info = {"title": os.path.basename(folder_path), "webpage_url": raw_url}

                playlist_title = info.get("title") or os.path.basename(folder_path)
                playlist_url = info.get("webpage_url") or raw_url

                # 2. Check rename flag
                rename_flag = item.get("rename_folder")
                if rename_flag is None:
                    rename_flag = global_rename if global_rename is not None else getattr(settings, "RENAME_FOLDER_ON_LINK", False)

                if rename_flag:
                    safe_folder_name = _sanitize_title(playlist_title)
                    parent_dir = os.path.dirname(os.path.abspath(folder_path))
                    new_target_path = os.path.join(parent_dir, safe_folder_name)
                    if os.path.abspath(folder_path) != new_target_path:
                        if not os.path.exists(new_target_path):
                            os.rename(folder_path, new_target_path)
                            folder_path = new_target_path
                            logger.info(f"Renamed unmanaged folder to '{safe_folder_name}'")
                        else:
                            logger.warning(f"Target folder {new_target_path} already exists; keeping existing path {folder_path}")

                # 3. Write playlist_info.json and snapshot
                snapshot_dir = os.path.join(folder_path, "playlist_info_snapshot")
                os.makedirs(snapshot_dir, exist_ok=True)
                with open(os.path.join(folder_path, "playlist_info.json"), "w", encoding="utf-8") as jf:
                    json.dump(info, jf, indent=2)
                with open(os.path.join(snapshot_dir, "playlist_info.json"), "w", encoding="utf-8") as jf:
                    json.dump(info, jf, indent=2)

                # 4. Ingest and index tracks
                video_files = []
                for ext in ("*.mp4", "*.mkv", "*.webm", "*.m4v"):
                    for vfile in glob.glob(os.path.join(folder_path, ext)):
                        if not vfile.endswith('.part'):
                            video_files.append(vfile)

                audio_files = []
                for ext in ("*.mp3", "*.m4a", "*.opus", "*.flac", "*.wav"):
                    for afile in glob.glob(os.path.join(folder_path, ext)):
                        audio_files.append(afile)
                    for afile in glob.glob(os.path.join(folder_path, "**", ext), recursive=True):
                        if afile not in audio_files:
                            audio_files.append(afile)

                # Find or create playlist record
                existing = PlaylistRepository.get_by_url_or_title(url=playlist_url, title=playlist_title, db=session)
                if existing:
                    playlist_id = existing.id
                else:
                    new_pl = PlaylistRepository.create(
                        title=playlist_title,
                        url=playlist_url,
                        playlist_count=info.get("playlist_count") or max(len(video_files), len(audio_files)),
                        local_count=max(len(video_files), len(audio_files)),
                        db=session
                    )
                    playlist_id = new_pl.id

                # Index tracks
                audio_map = {}
                for afile in audio_files:
                    vid = extract_video_id_from_filename(os.path.basename(afile))
                    if vid:
                        audio_map[vid] = afile

                indexed_count = 0
                indexed_ids = set()
                for vfile in video_files:
                    fname = os.path.basename(vfile)
                    vid = extract_video_id_from_filename(fname)
                    if not vid:
                        continue
                    song_title = os.path.splitext(fname)[0]
                    song_title = re.sub(r'\[[a-zA-Z0-9_-]{11}\]', '', song_title).strip() or fname
                    audio_file = audio_map.get(vid)
                    index_track(
                        video_id=vid,
                        title=song_title,
                        filepath=vfile,
                        playlist_id=playlist_id,
                        audio_filepath=audio_file,
                        db=session
                    )
                    indexed_ids.add(vid)
                    indexed_count += 1

                for afile in audio_files:
                    fname = os.path.basename(afile)
                    vid = extract_video_id_from_filename(fname)
                    if not vid or vid in indexed_ids:
                        continue
                    song_title = os.path.splitext(fname)[0]
                    song_title = re.sub(r'\[[a-zA-Z0-9_-]{11}\]', '', song_title).strip() or fname
                    index_track(
                        video_id=vid,
                        title=song_title,
                        filepath=afile,
                        playlist_id=playlist_id,
                        audio_filepath=afile,
                        db=session
                    )
                    indexed_ids.add(vid)
                    indexed_count += 1

                linked_count += 1
                results.append({
                    "folder_path": folder_path,
                    "playlist_id": playlist_id,
                    "title": playlist_title,
                    "url": playlist_url,
                    "tracks_indexed": indexed_count,
                    "success": True
                })

            except Exception as item_err:
                logger.error(f"Error linking {folder_path}: {item_err}")
                failed_count += 1
                results.append({
                    "folder_path": folder_path,
                    "success": False,
                    "error": str(item_err)
                })

    return {
        "success": failed_count == 0,
        "linked_count": linked_count,
        "failed_count": failed_count,
        "results": results
    }


_discovery_thread: Optional[threading.Thread] = None
_discovery_stop_event = threading.Event()

def start_periodic_auto_discovery():
    """Start background periodic auto-discovery worker thread if interval > 0."""
    global _discovery_thread, _discovery_stop_event
    if not getattr(settings, "ENABLE_AUTO_DISCOVERY", True):
        logger.info("[Auto-Discovery] Periodic scanning disabled in settings.")
        return

    interval_minutes = getattr(settings, "AUTO_DISCOVERY_INTERVAL_MINUTES", 60)
    if interval_minutes <= 0:
        logger.info("[Auto-Discovery] Set to on_startup_only (interval=0). Periodic polling inactive.")
        return

    if _discovery_thread and _discovery_thread.is_alive():
        return

    _discovery_stop_event.clear()

    def _worker():
        logger.info(f"[Auto-Discovery] Periodic scanner active (every {interval_minutes} min).")
        while not _discovery_stop_event.is_set():
            if _discovery_stop_event.wait(timeout=max(60, interval_minutes * 60)):
                break
            try:
                logger.info("[Auto-Discovery] Performing periodic background library check...")
                scan_res = scan_download_directory(settings.BASE_DOWNLOAD_PATH)
                if scan_res.get("discovered_playlists_count", 0) > 0:
                    ingest_res = ingest_discovered_library(scan_res["discovered_playlists"])
                    if ingest_res.get("playlists_imported", 0) > 0 or ingest_res.get("tracks_indexed", 0) > 0:
                        logger.info(f"[Auto-Discovery] Ingested {ingest_res['playlists_imported']} new playlists, {ingest_res['tracks_indexed']} tracks.")
            except Exception as e:
                logger.error(f"[Auto-Discovery] Background scan error: {e}")

    _discovery_thread = threading.Thread(target=_worker, daemon=True, name="AutoDiscoveryWorker")
    _discovery_thread.start()

def stop_periodic_auto_discovery():
    """Stop the periodic auto-discovery worker thread."""
    global _discovery_stop_event
    _discovery_stop_event.set()
