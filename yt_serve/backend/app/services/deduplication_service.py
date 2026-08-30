"""
Retroactive Library Deduplication & Zero-Space Hardlink Space Reclaimer Service.
Scans library for physical duplicate media files across playlists and converts them to NTFS/ext4 hardlinks.
"""

import os
import re
import glob
import logging
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_engine import get_logger
from app.core.track_indexer import create_hardlink_or_copy
from app.services.onboarding_service import extract_video_id_from_filename
from app.repositories import TrackRepository
from app.models.database import get_db_context

logger = get_logger("app.services.deduplication")

MEDIA_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".mp3", ".m4a", ".opus", ".flac", ".aac", ".wav"}


def format_bytes(size_bytes: int) -> str:
    """Format bytes into human-readable string (e.g. 1.25 GB, 450.0 MB)"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def are_same_physical_file(path1: str, path2: str) -> bool:
    """
    Check if two filepaths already share the exact same physical inode/file ID on disk.
    Works seamlessly on Windows (NTFS FileID) and Linux (POSIX Inode).
    """
    try:
        if not os.path.exists(path1) or not os.path.exists(path2):
            return False
        return os.path.samefile(path1, path2)
    except Exception:
        return False


def scan_library_duplicates(
    base_path: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Scan all playlist directories for independent physical duplicate files.
    Identifies which files are already zero-space hardlinks vs redundant physical copies.
    """
    target_path = os.path.abspath(base_path or settings.BASE_DOWNLOAD_PATH)
    if not os.path.isdir(target_path):
        return {
            "status": "error",
            "message": f"Target download directory does not exist: {target_path}",
            "base_path": target_path,
            "total_scanned_files": 0,
            "duplicate_groups_count": 0,
            "total_duplicate_files": 0,
            "reclaimable_bytes": 0,
            "formatted_reclaimable_space": "0 B",
            "duplicate_groups": []
        }

    logger.info(f"[Deduplicator] Starting library duplicate scan on: {target_path}")

    # Map video_id -> List of file info dicts
    # Separate video streams from audio streams so audio files aren't linked to video files
    video_map: Dict[str, List[Dict[str, Any]]] = {}
    audio_map: Dict[str, List[Dict[str, Any]]] = {}
    total_scanned = 0

    AUDIO_EXTS = {".mp3", ".m4a", ".opus", ".flac", ".aac", ".wav"}
    VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".avi", ".mov"}

    for root, dirs, files in os.walk(target_path):
        # Skip temporary, snapshot, or hidden directories
        if any(skip in os.path.basename(root).lower() for skip in ["temp", ".git", "snapshot", "logs"]):
            continue

        playlist_folder_name = os.path.basename(root)
        if root == target_path:
            continue

        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext not in MEDIA_EXTENSIONS:
                continue

            total_scanned += 1
            vid = extract_video_id_from_filename(fname)
            if not vid:
                continue

            full_path = os.path.join(root, fname)
            try:
                stat = os.stat(full_path)
                file_size = stat.st_size
            except Exception:
                file_size = 0

            file_info = {
                "video_id": vid,
                "filename": fname,
                "filepath": full_path,
                "file_size": file_size,
                "playlist_folder": playlist_folder_name,
                "extension": ext,
                "is_audio": ext in AUDIO_EXTS
            }

            if ext in AUDIO_EXTS:
                audio_map.setdefault(vid, []).append(file_info)
            else:
                video_map.setdefault(vid, []).append(file_info)

    # Process duplicate groups
    duplicate_groups: List[Dict[str, Any]] = []
    total_reclaimable_bytes = 0
    total_duplicate_files = 0

    all_maps = [("video", video_map), ("audio", audio_map)]

    for media_type, mapping in all_maps:
        for vid, file_list in mapping.items():
            if len(file_list) <= 1:
                continue

            # Pick the primary master file (first valid file on disk)
            master_file = None
            for f in file_list:
                if os.path.isfile(f["filepath"]):
                    master_file = f
                    break

            if not master_file:
                continue

            redundant_copies = []
            already_hardlinked_count = 0

            for candidate in file_list:
                if candidate["filepath"] == master_file["filepath"]:
                    continue

                if are_same_physical_file(master_file["filepath"], candidate["filepath"]):
                    already_hardlinked_count += 1
                else:
                    redundant_copies.append(candidate)
                    total_reclaimable_bytes += candidate["file_size"]
                    total_duplicate_files += 1

            if redundant_copies:
                song_title = os.path.splitext(master_file["filename"])[0]
                song_title = re.sub(r'\[[a-zA-Z0-9_-]{11}\]', '', song_title).strip() or master_file["filename"]

                group_info = {
                    "video_id": vid,
                    "title": song_title,
                    "media_type": media_type,
                    "master_file": master_file,
                    "redundant_copies": redundant_copies,
                    "already_hardlinked_count": already_hardlinked_count,
                    "reclaimable_bytes": sum(c["file_size"] for c in redundant_copies),
                    "formatted_reclaimable_space": format_bytes(sum(c["file_size"] for c in redundant_copies)),
                    "playlists": list(set([master_file["playlist_folder"]] + [c["playlist_folder"] for c in redundant_copies]))
                }
                duplicate_groups.append(group_info)

    logger.info(
        f"[Deduplicator] Scan complete: Found {len(duplicate_groups)} duplicate groups, "
        f"{total_duplicate_files} redundant files, {format_bytes(total_reclaimable_bytes)} reclaimable space."
    )

    return {
        "status": "success",
        "base_path": target_path,
        "total_scanned_files": total_scanned,
        "duplicate_groups_count": len(duplicate_groups),
        "total_duplicate_files": total_duplicate_files,
        "reclaimable_bytes": total_reclaimable_bytes,
        "formatted_reclaimable_space": format_bytes(total_reclaimable_bytes),
        "duplicate_groups": duplicate_groups
    }


def apply_library_deduplication(
    duplicate_groups: Optional[List[Dict[str, Any]]] = None,
    base_path: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Execute zero-space hardlink conversion for all identified redundant physical duplicate files.
    Safely replaces redundant duplicate files with NTFS/ext4 hardlinks pointing to master file.
    """
    if duplicate_groups is None:
        scan_res = scan_library_duplicates(base_path=base_path, db=db)
        if scan_res.get("status") != "success":
            return scan_res
        duplicate_groups = scan_res.get("duplicate_groups", [])

    converted_count = 0
    total_space_reclaimed = 0
    errors: List[str] = []

    with get_db_context(db) as session:
        for group in duplicate_groups:
            master = group.get("master_file", {})
            master_path = master.get("filepath")

            if not master_path or not os.path.isfile(master_path):
                errors.append(f"Master file missing: {master_path}")
                continue

            for redundant in group.get("redundant_copies", []):
                dup_path = redundant.get("filepath")
                file_size = redundant.get("file_size", 0)

                if not dup_path or not os.path.isfile(dup_path):
                    continue

                if are_same_physical_file(master_path, dup_path):
                    # Already hardlinked
                    continue

                # Atomic link-and-replace:
                # 1. Create temporary hardlink in target folder
                temp_hl_path = dup_path + ".dedup_tmp"
                try:
                    if os.path.exists(temp_hl_path):
                        os.remove(temp_hl_path)

                    link_created = create_hardlink_or_copy(master_path, temp_hl_path)
                    if not link_created:
                        errors.append(f"Failed to create hardlink from {master_path} to {temp_hl_path}")
                        continue

                    # 2. Safely remove duplicate file and rename temp link
                    os.remove(dup_path)
                    os.rename(temp_hl_path, dup_path)

                    converted_count += 1
                    total_space_reclaimed += file_size

                    # 3. Update track record in database index
                    TrackRepository.index_or_update_track(
                        video_id=group.get("video_id", ""),
                        title=group.get("title", ""),
                        filepath=master_path,
                        is_hardlinked=True,
                        db=session
                    )

                except Exception as e:
                    logger.error(f"[Deduplicator] Error replacing {dup_path}: {e}")
                    errors.append(f"Error replacing {os.path.basename(dup_path)}: {str(e)}")
                    if os.path.exists(temp_hl_path):
                        try:
                            os.remove(temp_hl_path)
                        except Exception:
                            pass

    logger.info(
        f"[Deduplicator] Ingestion complete: Converted {converted_count} files to zero-space hardlinks, "
        f"reclaimed {format_bytes(total_space_reclaimed)} physical disk space."
    )

    return {
        "status": "success",
        "files_converted": converted_count,
        "space_reclaimed_bytes": total_space_reclaimed,
        "formatted_space_reclaimed": format_bytes(total_space_reclaimed),
        "errors": errors
    }
