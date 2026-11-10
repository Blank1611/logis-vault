"""
Ad-hoc Single Video Download & Format Inspection Service.
Allows downloading individual YouTube videos with interactive quality/format inspection,
customizable destination path, metadata tracking, and automatic SQLite Track Index integration.
"""

import os
import re
import json
import time
import logging
from typing import Optional, List, Dict, Any, Callable
from datetime import datetime
from sqlalchemy.orm import Session
import yt_dlp

from app.core.config import settings
from app.core.logging_engine import get_logger
from app.utils.ytdlp_opts import build_ytdlp_options
from app.repositories import JobRepository, TrackRepository, SystemSettingRepository
from app.models.database import get_db_context, Job

logger = get_logger("app.services.adhoc")


from urllib.parse import urlparse, parse_qs


def sanitize_youtube_url(url: str) -> str:
    """
    Sanitize YouTube URL by stripping playlist and radio query parameters
    (&list=..., &index=..., &start_radio=...) to ensure single-video operations target only the video.
    """
    clean = url.strip()
    try:
        parsed = urlparse(clean)
        if "youtube.com" in parsed.netloc:
            qs = parse_qs(parsed.query)
            vid = qs.get("v")
            if vid:
                return f"https://www.youtube.com/watch?v={vid[0]}"
        elif "youtu.be" in parsed.netloc:
            vid = parsed.path.strip("/")
            if vid:
                return f"https://youtu.be/{vid}"
    except Exception:
        pass
    return clean


def extract_video_id_from_url(url: str) -> Optional[str]:
    """Extract YouTube video ID from standard or shortened URL"""
    clean = url.strip()
    try:
        parsed = urlparse(clean)
        if "youtube.com" in parsed.netloc:
            qs = parse_qs(parsed.query)
            vid = qs.get("v")
            if vid:
                return vid[0]
        elif "youtu.be" in parsed.netloc:
            return parsed.path.strip("/")
    except Exception:
        pass
    return None


def format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds to MM:SS or HH:MM:SS"""
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def probe_video_info(url: str) -> Dict[str, Any]:
    """
    Fetch comprehensive video metadata and available stream formats without downloading.
    Returns resolutions (e.g. 4K, 1080p, 720p), cipher badges (Direct vs Adaptive DASH),
    fps, audio streams, duration, thumbnail, and stream options.
    """
    clean_url = sanitize_youtube_url(url)
    logger.info(f"[Adhoc] Probing video info for URL: {clean_url}")

    opts = build_ytdlp_options(mode="info", extra_opts={"noplaylist": True, "extract_flat": False})

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            if not info:
                raise ValueError("Could not fetch video information from YouTube.")

            # If it extracted as a playlist, get first entry
            if "entries" in info:
                entries = list(info["entries"])
                if entries:
                    info = entries[0]
                else:
                    raise ValueError("No video entry found at URL.")

            video_id = info.get("id", "")
            title = info.get("title", "")
            uploader = info.get("uploader") or info.get("channel") or "Unknown Artist"
            duration = info.get("duration", 0)
            thumbnail = info.get("thumbnail") or (info.get("thumbnails")[-1]["url"] if info.get("thumbnails") else "")
            view_count = info.get("view_count", 0)
            description = (info.get("description") or "")[:200]

            # Parse available video resolutions and encryption classification
            formats = info.get("formats") or []
            heights_map: Dict[int, Dict[str, Any]] = {}

            for f in formats:
                h = f.get("height")
                vcodec = f.get("vcodec")
                acodec = f.get("acodec")
                fps = f.get("fps") or 30
                filesize = f.get("filesize") or f.get("filesize_approx")

                if not h or vcodec == "none":
                    continue

                # Distinguish direct progressive (e.g. format 18) vs encrypted DASH
                is_direct = bool(vcodec and vcodec != "none" and acodec and acodec != "none")
                badge = "⚡ Direct" if is_direct else "🛡️ Adaptive DASH"
                badge_tooltip = (
                    "Unencrypted progressive stream (Challenge-Free)"
                    if is_direct else
                    "Deciphered high-definition adaptive stream"
                )

                # Keep best format per height (prefer higher fps or filesize)
                if h not in heights_map or (fps > heights_map[h].get("fps", 0)):
                    heights_map[h] = {
                        "height": h,
                        "fps": fps,
                        "vcodec": vcodec,
                        "acodec": acodec,
                        "filesize": filesize,
                        "is_direct": is_direct,
                        "badge": badge,
                        "badge_tooltip": badge_tooltip,
                    }

            sorted_heights = sorted(list(heights_map.keys()), reverse=True)
            resolution_options = []

            for h in sorted_heights:
                stream = heights_map[h]
                fps_tag = f" {stream['fps']}fps" if stream["fps"] > 30 else ""
                if h >= 2160:
                    label = f"{h}p{fps_tag} (4K UHD)"
                elif h >= 1440:
                    label = f"{h}p{fps_tag} (2K QHD)"
                elif h >= 1080:
                    label = f"{h}p{fps_tag} (Full HD)"
                elif h >= 720:
                    label = f"{h}p{fps_tag} (HD)"
                else:
                    label = f"{h}p{fps_tag}"

                resolution_options.append({
                    "height": h,
                    "label": label,
                    "fps": stream["fps"],
                    "vcodec": stream["vcodec"],
                    "is_direct": stream["is_direct"],
                    "badge": stream["badge"],
                    "badge_tooltip": stream["badge_tooltip"],
                    "filesize": stream["filesize"],
                })

            if not resolution_options:
                resolution_options.append({
                    "height": 0,
                    "label": "Best Available",
                    "fps": 30,
                    "vcodec": "unknown",
                    "is_direct": False,
                    "badge": "🛡️ Adaptive DASH",
                    "badge_tooltip": "Default highest available stream",
                    "filesize": None,
                })

            return {
                "status": "success",
                "video_id": video_id,
                "title": title,
                "uploader": uploader,
                "duration": duration,
                "formatted_duration": format_duration(duration),
                "thumbnail": thumbnail,
                "view_count": view_count,
                "description": description,
                "available_resolutions": resolution_options,
                "default_download_path": settings.get_adhoc_download_path()
            }

    except Exception as e:
        logger.error(f"[Adhoc] Probe failed for {clean_url}: {e}")
        return {
            "status": "error",
            "message": str(e),
            "video_id": "",
            "title": "",
            "available_resolutions": []
        }


MEDIA_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".mp3", ".m4a", ".opus", ".flac", ".wav", ".aac"}
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".avi", ".mov"}
AUDIO_EXTENSIONS = {".mp3", ".m4a", ".opus", ".flac", ".wav", ".aac"}
TRACKED_DIRS_KEY = "tracked_adhoc_directories"


def _update_adhoc_metadata(
    target_dir: str,
    video_info: Dict[str, Any],
    filepath: str,
    audio_filepath: Optional[str] = None,
    media_meta: Optional[Dict[str, Any]] = None,
    media_type: str = "video"
):
    """
    Append video entry to archive.txt in target directory to prevent re-downloads.
    Metadata is now discovered dynamically directly from the physical filesystem.
    """
    os.makedirs(target_dir, exist_ok=True)
    archive_path = os.path.join(target_dir, "archive.txt")

    vid = video_info.get("id") or video_info.get("video_id")
    if vid:
        try:
            existing_vids = set()
            if os.path.isfile(archive_path):
                with open(archive_path, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 2 and parts[0] == "youtube":
                            existing_vids.add(parts[1])
            if vid not in existing_vids:
                with open(archive_path, "a", encoding="utf-8") as f:
                    f.write(f"youtube {vid}\n")
        except Exception as e:
            logger.warning(f"[Adhoc] Could not update archive.txt: {e}")


def get_tracked_directories(include_unmanaged: bool = False, db: Optional[Session] = None) -> List[Dict[str, Any]]:
    """
    Get tracked ad-hoc directories with stats and tiering.
    Guarantees default ad-hoc directory is always present as the first entry (tier: 'default').
    Up to 5 recent directories are marked with tier: 'recent_adhoc'.
    If include_unmanaged=True, also discovers candidate unmanaged library folders (tier: 'unmanaged')
    excluding managed playlist folders and Layer 1 noise.
    """
    default_path = os.path.abspath(settings.get_adhoc_download_path())
    raw = SystemSettingRepository.get(TRACKED_DIRS_KEY, default="[]", db=db)
    try:
        data = json.loads(raw) if raw else []
        if not isinstance(data, list):
            data = []
    except Exception:
        data = []

    dir_map = {}
    for d in data:
        if isinstance(d, dict) and d.get("path"):
            norm_p = os.path.abspath(d["path"])
            dir_map[norm_p] = d

    if default_path not in dir_map:
        dir_map[default_path] = {
            "path": default_path,
            "display_name": os.path.basename(default_path) or "_adhoc_downloads",
            "is_default": True,
            "item_count": 0,
            "total_size_bytes": 0,
            "last_used_at": datetime.utcnow().isoformat() + "Z"
        }
    else:
        dir_map[default_path]["is_default"] = True

    # Seed all known ad-hoc directories that exist on disk (e.g. system _adhoc_downloads)
    for known_p in settings.get_known_adhoc_paths():
        norm_known = os.path.abspath(known_p)
        if norm_known != default_path and os.path.isdir(norm_known):
            if norm_known not in dir_map:
                dir_map[norm_known] = {
                    "path": norm_known,
                    "display_name": os.path.basename(norm_known) or "_adhoc_downloads",
                    "is_default": False,
                    "item_count": 0,
                    "total_size_bytes": 0,
                    "last_used_at": None
                }

    default_item = dir_map[default_path]
    default_item["tier"] = "default"

    other_tracked = [item for p, item in dir_map.items() if p != default_path]
    other_tracked.sort(key=lambda x: x.get("last_used_at") or "", reverse=True)

    # Top 5 most recent
    top5_recent = other_tracked[:5]
    for item in top5_recent:
        item["tier"] = "recent_adhoc"
        item["is_default"] = False

    older_adhoc = other_tracked[5:]
    for item in older_adhoc:
        item["tier"] = "unmanaged"
        item["is_default"] = False

    result = [default_item] + top5_recent

    # Guarantee all existing known adhoc paths are present in result
    known_adhoc_norm = {os.path.abspath(kp) for kp in settings.get_known_adhoc_paths() if os.path.isdir(kp)}
    existing_paths = {os.path.abspath(x["path"]) for x in result}
    for item in other_tracked:
        item_path_norm = os.path.abspath(item["path"])
        if item_path_norm in known_adhoc_norm and item_path_norm not in existing_paths:
            item["tier"] = "recent_adhoc"
            result.append(item)
            existing_paths.add(item_path_norm)

    if include_unmanaged:
        managed_playlist_paths = set()
        try:
            from app.repositories import PlaylistRepository
            for pl in PlaylistRepository.get_all(db=db):
                if pl.title:
                    managed_playlist_paths.add(os.path.abspath(os.path.join(settings.BASE_DOWNLOAD_PATH, pl.title)))
        except Exception as pl_err:
            logger.debug(f"Could not load playlists for exclusion: {pl_err}")

        layer1_excluded = set(settings.get_excluded_directories())
        existing_paths = {os.path.abspath(x["path"]) for x in result}

        unmanaged_list = []
        for item in older_adhoc:
            norm_old = os.path.abspath(item["path"])
            if norm_old not in existing_paths and norm_old not in managed_playlist_paths:
                unmanaged_list.append(item)
                existing_paths.add(norm_old)

        if os.path.isdir(settings.BASE_DOWNLOAD_PATH):
            try:
                for entry in sorted(os.listdir(settings.BASE_DOWNLOAD_PATH)):
                    full_p = os.path.join(settings.BASE_DOWNLOAD_PATH, entry)
                    if not os.path.isdir(full_p):
                        continue
                    entry_lower = entry.lower()
                    if entry.startswith('.') or entry_lower in layer1_excluded:
                        continue
                    norm_p = os.path.abspath(full_p)
                    if norm_p in managed_playlist_paths or norm_p in existing_paths:
                        continue

                    # Count physical media files directly
                    item_count = 0
                    try:
                        with os.scandir(full_p) as sc:
                            for fe in sc:
                                if fe.is_file():
                                    ext = os.path.splitext(fe.name)[1].lower()
                                    if ext in MEDIA_EXTENSIONS:
                                        item_count += 1
                    except Exception:
                        item_count = 0

                    unmanaged_list.append({
                        "path": norm_p,
                        "display_name": entry,
                        "is_default": False,
                        "tier": "unmanaged",
                        "item_count": item_count,
                        "total_size_bytes": 0,
                        "last_used_at": None
                    })
                    existing_paths.add(norm_p)
            except Exception as scan_err:
                logger.warning(f"Error scanning base path for unmanaged folders: {scan_err}")

        unmanaged_list.sort(key=lambda x: x.get("display_name", "").lower())
        result.extend(unmanaged_list)
    else:
        result.extend(older_adhoc)

    return result


def track_adhoc_directory(dir_path: str, db: Optional[Session] = None) -> None:
    """
    Add or touch directory in tracked ad-hoc MRU list.
    """
    norm_path = os.path.abspath(dir_path)
    default_path = os.path.abspath(settings.get_adhoc_download_path())
    tracked = get_tracked_directories(db=db)

    found = False
    for item in tracked:
        if os.path.abspath(item["path"]) == norm_path:
            item["last_used_at"] = datetime.utcnow().isoformat() + "Z"
            found = True
            break

    if not found:
        tracked.append({
            "path": norm_path,
            "display_name": os.path.basename(norm_path) or norm_path,
            "is_default": (norm_path == default_path),
            "item_count": 0,
            "total_size_bytes": 0,
            "last_used_at": datetime.utcnow().isoformat() + "Z"
        })

    SystemSettingRepository.set(TRACKED_DIRS_KEY, json.dumps(tracked), db=db)


def untrack_adhoc_directory(dir_path: str, db: Optional[Session] = None) -> bool:
    """
    Remove a directory from the tracked MRU list.
    Cannot untrack the default ad-hoc directory.
    """
    norm_path = os.path.abspath(dir_path)
    default_path = os.path.abspath(settings.get_adhoc_download_path())
    if norm_path == default_path:
        return False

    tracked = get_tracked_directories(db=db)
    updated = [d for d in tracked if os.path.abspath(d["path"]) != norm_path]
    SystemSettingRepository.set(TRACKED_DIRS_KEY, json.dumps(updated), db=db)
    return True


def reconcile_and_scan_directory(dir_path: str) -> Dict[str, Any]:
    """
    Scans an ad-hoc directory directly from the physical filesystem.
    Physical disk files are the authoritative source of truth:
    - 1 physical file on disk = exactly 1 media item.
    - Title matches the disk filename without extension verbatim (no tag stripping or desync).
    - Resolution and YouTube ID are inferred from bracket tags if present.
    - archive.txt is cleaned of missing video IDs so re-downloads are unblocked.
    """
    clean_dir = os.path.abspath(dir_path)
    if not os.path.isdir(clean_dir):
        return {
            "path": clean_dir,
            "item_count": 0,
            "total_size_bytes": 0,
            "items": []
        }

    archive_path = os.path.join(clean_dir, "archive.txt")
    valid_entries = []
    present_vids = set()

    try:
        with os.scandir(clean_dir) as it:
            for entry in it:
                if entry.is_file():
                    ext = os.path.splitext(entry.name)[1].lower()
                    if ext in MEDIA_EXTENSIONS:
                        real_p = os.path.realpath(entry.path)
                        is_video = ext in VIDEO_EXTENSIONS
                        try:
                            stat = entry.stat()
                            size_bytes = stat.st_size
                            mtime = stat.st_mtime
                        except Exception:
                            size_bytes = 0
                            mtime = time.time()

                        bracket_matches = re.findall(r'\[([a-zA-Z0-9_.-]+)\]', entry.name)
                        resolution = ""
                        candidate_vids = []
                        for b in bracket_matches:
                            if re.match(r'^\d{3,4}p(?:\d+)?$', b, re.IGNORECASE) or b.upper() in ("4K", "2K", "HD"):
                                resolution = b
                            elif 6 <= len(b) <= 16:
                                candidate_vids.append(b)

                        # Prefer exact 11-character YouTube video ID if present, else fallback to candidate or file_<mtime>
                        vid = next((c for c in candidate_vids if len(c) == 11), None)
                        if not vid and candidate_vids:
                            vid = candidate_vids[0]

                        if not vid:
                            vid = f"file_{int(mtime)}"
                        else:
                            present_vids.add(vid)

                        # Preserve exact physical disk filename verbatim including extension
                        title = entry.name

                        # Check for local companion thumbnail if any
                        base_no_ext = os.path.splitext(real_p)[0]
                        thumbnail = ""
                        for img_ext in (".jpg", ".webp", ".png"):
                            cand = f"{base_no_ext}{img_ext}"
                            if os.path.isfile(cand):
                                thumbnail = cand
                                break

                        new_entry = {
                            "id": vid,
                            "title": title,
                            "filename": entry.name,
                            "uploader": "Local Media",
                            "duration": 0,
                            "filepath": real_p if is_video else "",
                            "audio_filepath": real_p if not is_video else None,
                            "format": ext.lstrip("."),
                            "resolution": resolution,
                            "fps": None,
                            "audio_codec": None,
                            "audio_bitrate": None,
                            "thumbnail": thumbnail,
                            "size_bytes": size_bytes,
                            "media_type": "video" if is_video else "audio",
                            "downloaded_at": datetime.fromtimestamp(mtime).isoformat() + "Z"
                        }
                        valid_entries.append(new_entry)
    except Exception as e:
        logger.warning(f"[Adhoc] Error scanning directory {clean_dir}: {e}")

    # Reconcile archive.txt: only keep lines for video IDs that actually exist on disk
    if os.path.isfile(archive_path):
        try:
            with open(archive_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            new_lines = []
            for line in lines:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[0] == "youtube":
                    line_vid = parts[1]
                    if line_vid in present_vids:
                        new_lines.append(line)
                else:
                    new_lines.append(line)
            if len(new_lines) != len(lines):
                with open(archive_path, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                logger.info(f"[Adhoc Reconciler] Cleaned {len(lines) - len(new_lines)} deleted IDs from {archive_path}")
        except Exception as e:
            logger.warning(f"[Adhoc] Error reconciling {archive_path}: {e}")

    total_size = sum(item.get("size_bytes", 0) for item in valid_entries)
    return {
        "path": clean_dir,
        "item_count": len(valid_entries),
        "total_size_bytes": total_size,
        "items": valid_entries
    }


def get_all_adhoc_media_items(
    directory_filter: Optional[str] = None,
    media_type_filter: Optional[str] = None,
    search: Optional[str] = None,
    db: Optional[Session] = None
) -> Dict[str, Any]:
    """
    Reconciles all tracked directories and aggregates media items into a unified table.
    Filters by directory, media type (video/audio), and search term.
    """
    tracked = get_tracked_directories(db=db)
    all_items = []
    dir_names = []
    updated_tracked = []

    for t in tracked:
        dpath = t["path"]
        scan_res = reconcile_and_scan_directory(dpath)
        items = scan_res.get("items", [])
        cnt = len(items)
        sz = scan_res.get("total_size_bytes", 0)

        t["item_count"] = cnt
        t["total_size_bytes"] = sz
        updated_tracked.append(t)

        dname = t.get("display_name") or os.path.basename(dpath)
        dir_names.append(dname)

        for it in items:
            it_copy = dict(it)
            it_copy["directory"] = dpath
            it_copy["directory_display"] = dname
            # Provide safe streaming/preview filename
            target_file = it_copy.get("filepath") or it_copy.get("audio_filepath") or ""
            it_copy["filename"] = os.path.basename(target_file)
            all_items.append(it_copy)

    SystemSettingRepository.set(TRACKED_DIRS_KEY, json.dumps(updated_tracked), db=db)

    filtered = all_items
    if directory_filter and directory_filter.strip() and directory_filter.lower() != "all":
        df = directory_filter.strip().lower()
        filtered = [
            it for it in filtered
            if it.get("directory_display", "").lower() == df or it.get("directory", "").lower() == df
        ]

    if media_type_filter and media_type_filter.strip() and media_type_filter.lower() != "all":
        mf = media_type_filter.strip().lower()
        filtered = [it for it in filtered if it.get("media_type", "").lower() == mf]

    if search and search.strip():
        q = search.strip().lower()
        filtered = [
            it for it in filtered
            if q in (it.get("title") or "").lower()
            or q in (it.get("id") or "").lower()
            or q in (it.get("uploader") or "").lower()
            or q in (it.get("filename") or "").lower()
        ]

    filtered.sort(key=lambda x: x.get("downloaded_at") or "", reverse=True)

    return {
        "total_items": len(filtered),
        "total_size_bytes": sum(it.get("size_bytes", 0) for it in filtered),
        "directories": list(dict.fromkeys(dir_names)),
        "items": filtered
    }


def delete_adhoc_media_item(filepath: str, db: Optional[Session] = None) -> bool:
    """
    Deletes physical media file and companion thumbnail from disk, then reconciles archive.txt.
    """
    clean_path = os.path.abspath(filepath)
    parent_dir = os.path.dirname(clean_path)
    base_name, _ = os.path.splitext(clean_path)

    if os.path.isfile(clean_path):
        try:
            os.remove(clean_path)
        except Exception as e:
            logger.error(f"[Adhoc] Error removing file {clean_path}: {e}")
            return False

    # Check companion audio/video or thumbnails
    for ext in (".mp3", ".opus", ".m4a", ".flac", ".mp4", ".mkv", ".webm", ".jpg", ".webp", ".png"):
        companion = f"{base_name}{ext}"
        if companion != clean_path and os.path.isfile(companion):
            try:
                os.remove(companion)
            except Exception:
                pass

    if os.path.isdir(parent_dir):
        reconcile_and_scan_directory(parent_dir)
    return True


def promote_adhoc_to_playlist(
    source_directory: str,
    filepaths: List[str],
    playlist_title: str,
    db: Session
) -> Dict[str, Any]:
    """
    Converts ad-hoc staged files into a permanent Playlist with Track and PlaylistTrack entries in SQLite.
    """
    from app.repositories import PlaylistRepository, TrackRepository
    from app.models.database import Playlist
    from app.core.track_indexer import probe_local_media_metadata

    clean_dir = os.path.abspath(source_directory)
    pl = db.query(Playlist).filter(Playlist.title == playlist_title).first()
    if not pl:
        pl = PlaylistRepository.create(
            url=f"local://adhoc/{os.path.basename(clean_dir)}",
            title=playlist_title,
            db=db
        )

    tracks_added = 0
    for fp in filepaths:
        real_fp = os.path.abspath(fp)
        if not os.path.isfile(real_fp):
            continue

        base_name = os.path.splitext(os.path.basename(real_fp))[0]
        match = re.search(r'\[([a-zA-Z0-9_-]{11})\]', base_name)
        vid = match.group(1) if match else f"local_{int(time.time()*1000)}_{tracks_added}"

        is_audio = real_fp.endswith(('.mp3', '.opus', '.m4a', '.flac'))
        media_meta = probe_local_media_metadata(None if is_audio else real_fp, real_fp if is_audio else None)

        track = TrackRepository.index_or_update_track(
            video_id=vid,
            title=base_name,
            filepath="" if is_audio else real_fp,
            audio_filepath=real_fp if is_audio else None,
            downloaded_resolutions=[f"{media_meta.get('resolution')}p"] if media_meta.get('resolution') else [],
            downloaded_fps=media_meta.get("fps"),
            downloaded_audio_codec=media_meta.get("audio_codec"),
            downloaded_audio_bitrate=media_meta.get("audio_bitrate"),
            playlist_id=pl.id,
            db=db
        )
        if track:
            tracks_added += 1

    return {
        "status": "success",
        "playlist_id": pl.id,
        "playlist_title": pl.title,
        "tracks_added": tracks_added
    }


def run_startup_adhoc_reconciliation(db: Optional[Session] = None) -> None:
    """
    Server startup activity:
    Scans and reconciles all tracked ad-hoc directories, cleans archive.txt of deleted items,
    and updates directory MRU statistics.
    """
    logger.info("[STARTUP] Reconciling tracked ad-hoc directories and metadata...")
    try:
        tracked = get_tracked_directories(db=db)
        total_media = 0
        for item in tracked:
            dpath = item.get("path")
            if dpath and os.path.isdir(dpath):
                res = reconcile_and_scan_directory(dpath)
                cnt = len(res.get("items", []))
                total_media += cnt
                item["item_count"] = cnt
                item["total_size_bytes"] = res.get("total_size_bytes", 0)
        SystemSettingRepository.set(TRACKED_DIRS_KEY, json.dumps(tracked), db=db)
        logger.info(f"[STARTUP] ✓ Ad-hoc reconciliation complete: {total_media} media items across {len(tracked)} tracked directories.")
    except Exception as e:
        logger.warning(f"[STARTUP] Ad-hoc startup reconciliation note: {e}")


def find_existing_local_video(target_dir: str, video_id: str, db: Optional[Session] = None) -> Optional[str]:
    """
    Check if a video file already exists locally in target_dir or the global track index.
    """
    if not video_id:
        return None

    # 1. Scan target directory for files containing [video_id]
    if os.path.isdir(target_dir):
        for fname in os.listdir(target_dir):
            if f"[{video_id}]" in fname:
                ext = os.path.splitext(fname)[1].lower()
                if ext in (".mp4", ".mkv", ".webm"):
                    candidate = os.path.join(target_dir, fname)
                    if os.path.isfile(candidate):
                        return candidate

    # 2. Check central SQLite Track Index
    try:
        from app.repositories import TrackRepository
        track = TrackRepository.get_by_video_id(video_id, db=db)
        if track and track.primary_filepath and os.path.isfile(track.primary_filepath):
            ext = os.path.splitext(track.primary_filepath)[1].lower()
            if ext in (".mp4", ".mkv", ".webm"):
                return track.primary_filepath
    except Exception as e:
        logger.warning(f"[Adhoc] Error querying track index for video {video_id}: {e}")

    return None


def extract_audio_from_video(
    video_path: str,
    audio_format: str = "copy",
    write_log: Optional[Callable] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[str]:
    """
    Extract audio from a local video container.
    Honors audio_format:
    - 'copy' (Native Copy): probes stream codec; uses -c:a copy into .opus or .m4a (lossless, zero-CPU).
    - 'opus': copies if already Opus, else encodes via libopus at 160k into .opus.
    - 'mp3' / 'mp3_best': encodes via libmp3lame at 320k into .mp3.
    - 'flac': encodes via flac into .flac.
    - 'm4a': copies if already AAC, else encodes via aac at 256k into .m4a.
    """
    import subprocess
    from app.core.track_indexer import probe_local_media_metadata

    def log(msg: str, lvl: str = "INFO"):
        if write_log:
            try:
                write_log(msg, lvl)
            except Exception:
                pass
        else:
            logger.info(msg)

    if not video_path or not os.path.isfile(video_path):
        return None

    media_meta = probe_local_media_metadata(video_path, None)
    detected_codec = (media_meta.get("audio_codec") or "").lower()

    base, _ = os.path.splitext(video_path)

    if audio_format == "copy":
        if "opus" in detected_codec:
            ext = "opus"
            ffmpeg_args = ["-c:a", "copy"]
        elif "aac" in detected_codec:
            ext = "m4a"
            ffmpeg_args = ["-c:a", "copy"]
        elif "mp3" in detected_codec:
            ext = "mp3"
            ffmpeg_args = ["-c:a", "copy"]
        elif "flac" in detected_codec:
            ext = "flac"
            ffmpeg_args = ["-c:a", "copy"]
        else:
            # Default copy strategy
            ext = "opus" if "webm" in video_path.lower() else "m4a"
            ffmpeg_args = ["-c:a", "copy"]
    elif audio_format == "opus":
        ext = "opus"
        if "opus" in detected_codec:
            ffmpeg_args = ["-c:a", "copy"]
        else:
            ffmpeg_args = ["-c:a", "libopus", "-b:a", "160k"]
    elif audio_format in ("mp3_best", "mp3"):
        ext = "mp3"
        if "mp3" in detected_codec:
            ffmpeg_args = ["-c:a", "copy"]
        else:
            ffmpeg_args = ["-c:a", "libmp3lame", "-b:a", "320k"]
    elif audio_format == "flac":
        ext = "flac"
        ffmpeg_args = ["-c:a", "flac"]
    elif audio_format == "m4a":
        ext = "m4a"
        if "aac" in detected_codec:
            ffmpeg_args = ["-c:a", "copy"]
        else:
            ffmpeg_args = ["-c:a", "aac", "-b:a", "256k"]
    else:
        # Default fallback
        ext = "mp3"
        ffmpeg_args = ["-c:a", "libmp3lame", "-b:a", "320k"]

    target_audio = f"{base}.{ext}"
    log(f"Extracting {ext.upper()} audio ({audio_format}): {os.path.basename(target_audio)}")

    meta_args = []
    if metadata:
        if metadata.get("title"):
            meta_args.extend(["-metadata", f"title={metadata['title']}"])
        artist = metadata.get("artist") or metadata.get("uploader") or ""
        if artist:
            meta_args.extend(["-metadata", f"artist={artist}"])
        meta_args.extend(["-metadata", f"album={metadata.get('album') or 'Ad-hoc Downloads'}"])
        if metadata.get("upload_date"):
            meta_args.extend(["-metadata", f"date={str(metadata['upload_date'])[:4]}"])

    try:
        cmd = ["ffmpeg", "-y", "-i", video_path, "-vn"] + ffmpeg_args + meta_args + [target_audio]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        if os.path.isfile(target_audio):
            log(f"✓ Extracted {ext.upper()} audio: {os.path.basename(target_audio)}", "SUCCESS")
            return target_audio
    except Exception as ex:
        log(f"⚠️ Audio extraction failed: {ex}", "WARN")

    return None


def execute_adhoc_download(
    job_id: int,
    url: str,
    video_quality: str = "best",
    audio_format: str = "copy",
    extract_mode: str = "both",
    custom_download_path: Optional[str] = None,
    db: Optional[Session] = None,
    log_writer: Optional[Any] = None,
    cancel_token: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Execute ad-hoc single video download and optional audio extraction.
    Updates job stream metrics, metadata JSON, and registers file in Track index.
    """
    def write_log(msg: str, lvl: str = "INFO"):
        if log_writer:
            try:
                log_writer(job_id, msg, lvl)
            except Exception:
                pass
        else:
            logger.info(f"[Adhoc Job #{job_id}] {msg}")

    clean_url = sanitize_youtube_url(url)
    vid = extract_video_id_from_url(clean_url) or ""
    target_dir = os.path.abspath(custom_download_path or settings.get_adhoc_download_path())
    os.makedirs(target_dir, exist_ok=True)
    write_log(f"Target Directory: {target_dir} | Mode: {extract_mode} | Quality: {video_quality}")

    JobRepository.update_status(job_id, status="running", db=db)
    if db and vid:
        JobRepository.update_stream_progress(job_id=job_id, video_id=vid, db=db)

    # Check for zero-network audio-only fast-path if video is already on disk
    if extract_mode == "audio_only" and vid:
        existing_video = find_existing_local_video(target_dir, vid, db=db)
        if existing_video:
            write_log(f"Found existing local video: {os.path.basename(existing_video)}. Extracting audio locally without network usage...", "INFO")
            audio_file = extract_audio_from_video(existing_video, audio_format=audio_format, write_log=write_log, metadata={"title": os.path.splitext(os.path.basename(existing_video))[0], "album": "Ad-hoc Downloads"})
            if audio_file:
                from app.core.track_indexer import probe_local_media_metadata
                media_meta = probe_local_media_metadata(None, audio_file)
                base_name = os.path.splitext(os.path.basename(existing_video))[0]
                
                # Update adhoc metadata file on disk
                _update_adhoc_metadata(
                    target_dir=target_dir,
                    video_info={"id": vid, "title": base_name, "uploader": "Local Media", "duration": 0},
                    filepath="",
                    audio_filepath=audio_file,
                    media_meta=media_meta,
                    media_type="audio"
                )
                track_adhoc_directory(target_dir, db=db)
                
                JobRepository.update_status(job_id=job_id, status="completed", completed_items=1, failed_items=0, db=db)
                if db and os.path.isfile(audio_file):
                    JobRepository.update_stream_progress(job_id=job_id, title=os.path.basename(audio_file), db=db)
                write_log(f"✓ Extracted and saved ad-hoc audio: {os.path.basename(audio_file)}", "SUCCESS")
                return {
                    "status": "success",
                    "job_id": job_id,
                    "video_id": vid,
                    "title": base_name,
                    "filepath": audio_file
                }

    # Format selector configuration based on chosen resolution
    if video_quality and video_quality not in ("best", "0"):
        format_selector = f"bestvideo[height<={video_quality}]+bestaudio/best[height<={video_quality}]/best"
        outtmpl = os.path.join(target_dir, f"%(title)s [%(id)s] [{video_quality}p].%(ext)s")
    else:
        format_selector = "bestvideo+bestaudio/best"
        outtmpl = os.path.join(target_dir, "%(title)s [%(id)s] [%(resolution)s].%(ext)s")

    if extract_mode == "audio_only":
        outtmpl = os.path.join(target_dir, "%(title)s [%(id)s].%(ext)s")

    last_log_milestone = {"val": -1}

    def progress_hook(d):
        if cancel_token and getattr(cancel_token, "is_cancelled", False):
            raise Exception("Job cancelled by user")

        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            speed = d.get("speed") or 0.0
            eta = d.get("eta") or 0
            raw_filename = os.path.basename(d.get("filename", ""))

            JobRepository.update_stream_progress(
                job_id=job_id,
                title=raw_filename,
                bytes_downloaded=downloaded,
                bytes_total=total,
                speed=speed,
                eta=eta,
                db=db
            )

            # Log periodically at 25%, 50%, 75%, 100%
            if total > 0:
                pct = int((downloaded / total) * 100)
                milestone = (pct // 25) * 25
                if milestone > last_log_milestone["val"] and milestone > 0:
                    last_log_milestone["val"] = milestone
                    speed_mb = speed / (1024 * 1024) if speed else 0.0
                    write_log(f"Progress: {milestone}% ({downloaded / (1024*1024):.1f}MB / {total / (1024*1024):.1f}MB) at {speed_mb:.2f} MB/s (ETA: {eta}s)")
        elif d.get("status") == "finished":
            write_log(f"Stream download finished, finalizing container...")

    # Build yt-dlp options with Node.js runtime and network resilience
    extra_opts = {
        "outtmpl": outtmpl,
        "noplaylist": True,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
    }

    if extract_mode == "audio_only":
        extra_opts["format"] = "bestaudio/best"
        postprocessors = []
        if audio_format in ("mp3_best", "mp3"):
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            })
        elif audio_format == "opus":
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "opus",
                "preferredquality": "160",
            })
        elif audio_format == "flac":
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "flac",
            })
        elif audio_format == "m4a":
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "256",
            })
        # If audio_format == "copy", do not add postprocessors to keep native bestaudio
        if postprocessors:
            extra_opts["postprocessors"] = postprocessors
    else:
        extra_opts["format"] = format_selector
        extra_opts["merge_output_format"] = "mp4"

    ydl_opts = build_ytdlp_options(mode="download", extra_opts=extra_opts)

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            if not info:
                raise ValueError("Download failed: No stream extracted.")

            vid = info.get("id", "")
            title = info.get("title", "")
            artist = info.get("uploader") or info.get("channel") or ""
            duration = info.get("duration")

            # Determine primary downloaded filepath
            downloaded_file = ydl.prepare_filename(info)
            if extract_mode == "audio_only":
                base, _ = os.path.splitext(downloaded_file)
                ext = "mp3" if "mp3" in audio_format else ("opus" if audio_format == "opus" else ("m4a" if audio_format == "m4a" else "opus"))
                audio_file = f"{base}.{ext}" if not downloaded_file.endswith(f".{ext}") else downloaded_file
                primary_video = ""
                primary_audio = audio_file if os.path.isfile(audio_file) else downloaded_file
            else:
                primary_video = downloaded_file
                primary_audio = None

                # If "both", extract standalone audio copy respecting audio_format
                if extract_mode == "both" and os.path.isfile(primary_video):
                    primary_audio = extract_audio_from_video(
                        primary_video,
                        audio_format=audio_format,
                        write_log=write_log,
                        metadata=info
                    )

            # Probe media metadata using local ffprobe
            from app.core.track_indexer import probe_local_media_metadata
            media_meta = probe_local_media_metadata(primary_video or "", primary_audio or "")
            res_list = []
            if media_meta.get("resolution"):
                res_list.append(f"{media_meta['resolution']}p")
            elif video_quality and video_quality not in ("best", "0"):
                res_list.append(f"{video_quality}p")

            # Update adhoc download archive on disk
            write_log("Updating download archive (archive.txt)...")
            _update_adhoc_metadata(
                target_dir=target_dir,
                video_info=info,
                filepath=primary_video or primary_audio or "",
                audio_filepath=primary_audio,
                media_meta=media_meta,
                media_type="audio" if extract_mode == "audio_only" else "video"
            )
            track_adhoc_directory(target_dir, db=db)

            JobRepository.update_status(
                job_id=job_id,
                status="completed",
                completed_items=1,
                failed_items=0,
                db=db
            )
            final_out = primary_audio if extract_mode == "audio_only" else (primary_video or primary_audio)
            if db and final_out and os.path.isfile(final_out):
                JobRepository.update_stream_progress(job_id=job_id, title=os.path.basename(final_out), db=db)

            write_log(f"✓ Successfully processed ad-hoc download: {title} ({vid})", "SUCCESS")
            return {
                "status": "success",
                "job_id": job_id,
                "video_id": vid,
                "title": title,
                "filepath": primary_video or primary_audio
            }

    except Exception as e:
        logger.error(f"[Adhoc Job #{job_id}] Execution error: {e}")
        JobRepository.update_status(
            job_id=job_id,
            status="failed",
            error=str(e),
            db=db
        )
        return {
            "status": "error",
            "job_id": job_id,
            "error": str(e)
        }
