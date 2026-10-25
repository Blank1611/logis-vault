"""
Playlist management API endpoints for multi-platform playlist operations
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from typing import List, Optional, Set
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from datetime import datetime
import os
import threading

from app.models.database import get_db
from app.repositories import PlaylistRepository, TrackRepository
from app.services.ytdlp_service import DownloadService
from app.core.config import settings

router = APIRouter()

# Thread-safe in-flight playlist refresh tracker
_ACTIVE_REFRESH_PLAYLISTS: Set[int] = set()
_REFRESH_LOCK = threading.Lock()

class PlaylistCreate(BaseModel):
    """Playlist creation model"""
    url: HttpUrl
    title: Optional[str] = None
    quality_profile_id: Optional[str] = "standard_1080p"

class PlaylistResponse(BaseModel):
    """Playlist response model"""
    id: int
    url: str
    title: str
    local_count: int
    playlist_count: int
    unavailable_count: int
    last_download: Optional[str]
    last_extract: Optional[str]
    excluded_ids: List[str]
    quality_profile_id: Optional[str] = "standard_1080p"
    
    class Config:
        from_attributes = True

class PlaylistUpdate(BaseModel):
    """Playlist update model"""
    title: Optional[str] = None
    excluded_ids: Optional[List[str]] = None
    quality_profile_id: Optional[str] = None

def get_download_service() -> DownloadService:
    """Get download service instance"""
    return DownloadService(settings.BASE_DOWNLOAD_PATH, {
        "audio_extract_mode": settings.AUDIO_EXTRACT_MODE,
        "max_extraction_workers": settings.MAX_CONCURRENT_EXTRACTIONS,
        "batch_size": settings.BATCH_SIZE,
        "use_browser_cookies": settings.USE_BROWSER_COOKIES,
        "browser_name": settings.BROWSER_NAME,
        "cookies_file": settings.COOKIES_FILE,
    })

async def refresh_playlist_stats_task(playlist_id: int):
    """Background task to refresh playlist stats"""
    from app.models.database import SessionLocal
    db = SessionLocal()
    
    try:
        playlist = PlaylistRepository.get_by_id(playlist_id, db=db)
        if not playlist:
            return
        
        download_service = get_download_service()
        local_count, available_count, unavailable_count = await download_service.get_playlist_stats(
            playlist.title,
            playlist.url,
            playlist.excluded_ids or [],
            source="manual",
            force_refresh=True
        )
        
        PlaylistRepository.update_counts(
            playlist_id=playlist.id,
            local_count=local_count,
            playlist_count=available_count,
            unavailable_count=unavailable_count,
            db=db
        )

        # Notify connected frontend clients via WebSocket
        try:
            from app.api.websocket import manager as ws_manager
            await ws_manager.broadcast("playlist_updated", {"playlist_id": playlist.id})
        except Exception:
            pass
    finally:
        with _REFRESH_LOCK:
            _ACTIVE_REFRESH_PLAYLISTS.discard(playlist_id)
        db.close()

@router.get("/", response_model=List[PlaylistResponse])
async def list_playlists(db: Session = Depends(get_db)):
    """Get all playlists"""
    playlists = PlaylistRepository.get_all(db=db)
    
    # Convert datetime to string for response
    result = []
    for p in playlists:
        result.append(PlaylistResponse(
            id=p.id,
            url=p.url,
            title=p.title,
            local_count=p.local_count,
            playlist_count=p.playlist_count,
            unavailable_count=p.unavailable_count,
            last_download=p.last_download.isoformat() if p.last_download else None,
            last_extract=p.last_extract.isoformat() if p.last_extract else None,
            excluded_ids=p.excluded_ids or [],
            quality_profile_id=getattr(p, "quality_profile_id", "standard_1080p") or "standard_1080p"
        ))
    
    return result

# Add route without trailing slash for compatibility
@router.get("", response_model=List[PlaylistResponse])
async def list_playlists_no_slash(db: Session = Depends(get_db)):
    """Get all playlists (no trailing slash version)"""
    return await list_playlists(db)

@router.post("", response_model=PlaylistResponse, status_code=201)
@router.post("/", response_model=PlaylistResponse, status_code=201)
async def create_playlist(
    playlist: PlaylistCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Add a new playlist"""
    # Check if playlist already exists
    existing = PlaylistRepository.get_by_url(str(playlist.url), db=db)
    if existing:
        raise HTTPException(status_code=400, detail="Playlist already exists")
    
    # Get playlist info
    download_service = get_download_service()
    try:
        info = await download_service.get_playlist_info(str(playlist.url))
        title = playlist.title or info.get("title", "Unknown Playlist")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch playlist info: {str(e)}")
    
    # Create playlist via repository with atomic commit
    profile_id = playlist.quality_profile_id or "standard_1080p"
    db_playlist = PlaylistRepository.create(
        url=str(playlist.url),
        title=title,
        quality_profile_id=profile_id,
        db=db
    )
    
    # Fetch stats in background
    background_tasks.add_task(refresh_playlist_stats_task, db_playlist.id)
    
    return PlaylistResponse(
        id=db_playlist.id,
        url=db_playlist.url,
        title=db_playlist.title,
        local_count=0,
        playlist_count=0,
        unavailable_count=0,
        last_download=None,
        last_extract=None,
        excluded_ids=[],
        quality_profile_id=db_playlist.quality_profile_id or "standard_1080p"
    )

@router.get("/active-refreshes", response_model=List[int])
async def get_active_refreshes():
    """Return list of playlist IDs currently actively being refreshed in the background"""
    with _REFRESH_LOCK:
        return list(_ACTIVE_REFRESH_PLAYLISTS)

@router.get("/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """Get playlist by ID"""
    playlist = PlaylistRepository.get_by_id(playlist_id, db=db)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    return PlaylistResponse(
        id=playlist.id,
        url=playlist.url,
        title=playlist.title,
        local_count=playlist.local_count,
        playlist_count=playlist.playlist_count,
        unavailable_count=playlist.unavailable_count,
        last_download=playlist.last_download.isoformat() if playlist.last_download else None,
        last_extract=playlist.last_extract.isoformat() if playlist.last_extract else None,
        excluded_ids=playlist.excluded_ids or [],
        quality_profile_id=getattr(playlist, "quality_profile_id", "standard_1080p") or "standard_1080p"
    )

@router.put("/{playlist_id}", response_model=PlaylistResponse)
async def update_playlist(
    playlist_id: int,
    playlist: PlaylistUpdate,
    db: Session = Depends(get_db)
):
    """Update playlist via repository with atomic commit"""
    db_playlist = PlaylistRepository.update(
        playlist_id=playlist_id,
        title=playlist.title,
        quality_profile_id=playlist.quality_profile_id,
        excluded_ids=playlist.excluded_ids,
        db=db
    )
    if not db_playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    return PlaylistResponse(
        id=db_playlist.id,
        url=db_playlist.url,
        title=db_playlist.title,
        local_count=db_playlist.local_count,
        playlist_count=db_playlist.playlist_count,
        unavailable_count=db_playlist.unavailable_count,
        last_download=db_playlist.last_download.isoformat() if db_playlist.last_download else None,
        last_extract=db_playlist.last_extract.isoformat() if db_playlist.last_extract else None,
        excluded_ids=db_playlist.excluded_ids or [],
        quality_profile_id=getattr(db_playlist, "quality_profile_id", "standard_1080p") or "standard_1080p"
    )

@router.delete("/{playlist_id}", status_code=204)
async def delete_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """Delete playlist via repository with atomic commit"""
    success = PlaylistRepository.delete(playlist_id, db=db)
    if not success:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return None

@router.post("/{playlist_id}/refresh")
async def refresh_playlist(
    playlist_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Refresh playlist stats"""
    from app.services.scheduler import is_scheduler_scanning
    if is_scheduler_scanning():
        raise HTTPException(
            status_code=409,
            detail="Daily scheduled scan is currently running in the background. Please wait for it to complete."
        )

    playlist = PlaylistRepository.get_by_id(playlist_id, db=db)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    with _REFRESH_LOCK:
        if playlist_id in _ACTIVE_REFRESH_PLAYLISTS:
            raise HTTPException(
                status_code=409,
                detail=f"A refresh is already actively in progress for '{playlist.title}'."
            )
        _ACTIVE_REFRESH_PLAYLISTS.add(playlist_id)

    # Refresh stats in background
    background_tasks.add_task(refresh_playlist_stats_task, playlist_id)
    
    return {"message": "Refresh started", "playlist_id": playlist_id}


@router.post("/{playlist_id}/open-folder")
async def open_playlist_folder(playlist_id: int, db: Session = Depends(get_db)):
    """Open playlist folder in file explorer"""
    from app.core import yt_playlist_audio_tools as tools
    from app.utils.system import open_folder_in_explorer
    
    playlist = PlaylistRepository.get_by_id(playlist_id, db=db)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    # Get playlist folder
    safe_title = tools._sanitize_title(playlist.title)
    playlist_folder = os.path.join(settings.BASE_DOWNLOAD_PATH, safe_title)
    
    try:
        result = open_folder_in_explorer(playlist_folder)
        return result
    except FileNotFoundError:
        raise HTTPException(
            status_code=404, 
            detail=f"Playlist folder not found: {playlist_folder}"
        )
    except OSError as e:
        raise HTTPException(
            status_code=500, 
            detail=str(e)
        )


@router.get("/{playlist_id}/video-info")
async def get_playlist_video_info(playlist_id: int, db: Session = Depends(get_db)):
    """Get video information (titles) for a playlist from playlist_info.json"""
    import json
    import os
    from app.core import yt_playlist_audio_tools as tools
    from app.services.ytdlp_service import ytdlp_service
    
    playlist = PlaylistRepository.get_by_id(playlist_id, db=db)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    # Get playlist folder using case-insensitive resolver
    playlist_folder = ytdlp_service.resolve_playlist_folder(playlist.title)
    snapshot_folder = os.path.join(playlist_folder, "playlist_info_snapshot")
    
    latest_file = None
    if os.path.exists(snapshot_folder):
        json_files = [f for f in os.listdir(snapshot_folder) if f.startswith("playlist_info_") and f.endswith(".json")]
        if json_files:
            json_files.sort(reverse=True)
            latest_file = os.path.join(snapshot_folder, json_files[0])
            
    if not latest_file:
        direct_file = os.path.join(playlist_folder, "playlist_info.json")
        if os.path.exists(direct_file):
            latest_file = direct_file
    
    # Build map of video_id -> info
    video_info = {}
    if latest_file and os.path.exists(latest_file):
        try:
            with open(latest_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                entries = data.get('entries', [])
                
                for entry in entries:
                    if entry and entry.get('id'):
                        is_unavail = tools.is_entry_unavailable(entry, None) if tools else False
                        video_info[entry['id']] = {
                            'title': entry.get('title', 'Unknown Title'),
                            'duration': entry.get('duration'),
                            'uploader': entry.get('uploader'),
                            'is_unavailable': is_unavail,
                        }
        except Exception as e:
            pass
    return video_info


# =========================================================================
# Track Quality & Upgrades Endpoints
# =========================================================================

class TrackUpgradeRequest(BaseModel):
    target_resolution: int
    delete_older: bool = False


class AudioUpgradeRequest(BaseModel):
    audio_format: str = "mp3_320"


class SetPrimaryRequest(BaseModel):
    resolution: str


def _find_track_versions(playlist_folder: str, video_id: str) -> List[Dict[str, Any]]:
    """Scan playlist directory for all video copies matching video_id"""
    import re
    versions = []
    if not os.path.isdir(playlist_folder):
        return versions
    for fname in os.listdir(playlist_folder):
        if f"[{video_id}]" in fname and fname.lower().endswith((".mp4", ".mkv", ".webm")):
            fpath = os.path.join(playlist_folder, fname)
            if os.path.isfile(fpath):
                size = os.path.getsize(fpath)
                res_match = re.search(r"\[(\d{3,4}p)\]", fname)
                res = res_match.group(1) if res_match else "unknown"
                versions.append({
                    "resolution": res,
                    "filename": fname,
                    "filepath": fpath,
                    "size_bytes": size
                })
    return versions


@router.get("/{playlist_id}/tracks")
async def get_playlist_tracks(playlist_id: int, db: Session = Depends(get_db)):
    """Fetch all tracks belonging to this playlist with resolutions, specs, and file sizes"""
    from app.models.database import Track
    from app.services.ytdlp_service import ytdlp_service
    import os

    playlist = PlaylistRepository.get_by_id(playlist_id, db=db)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    playlist_folder = ytdlp_service.resolve_playlist_folder(playlist.title)

    records = TrackRepository.get_playlist_tracks(playlist_id, db=db)

    result = []
    for t, pt in records:
        disk_versions = _find_track_versions(playlist_folder, t.video_id)
        v_size = os.path.getsize(t.primary_filepath) if (t.primary_filepath and os.path.isfile(t.primary_filepath)) else 0
        a_size = os.path.getsize(t.primary_audio_filepath) if (t.primary_audio_filepath and os.path.isfile(t.primary_audio_filepath)) else 0

        # Merge known resolutions
        known_resolutions = list(t.downloaded_resolutions_json or [])
        for dv in disk_versions:
            if dv["resolution"] != "unknown" and dv["resolution"] not in known_resolutions:
                known_resolutions.append(dv["resolution"])

        result.append({
            "video_id": t.video_id,
            "title": t.title,
            "artist": t.artist,
            "duration": t.duration,
            "position": pt.position,
            "is_archived": pt.is_archived,
            "primary_filepath": t.primary_filepath,
            "primary_audio_filepath": t.primary_audio_filepath,
            "primary_resolution": t.primary_resolution,
            "downloaded_resolutions": known_resolutions,
            "downloaded_fps": t.downloaded_fps,
            "downloaded_audio_codec": t.downloaded_audio_codec,
            "downloaded_audio_bitrate": t.downloaded_audio_bitrate,
            "available_resolutions": t.available_resolutions_json or [],
            "highest_available_resolution": t.highest_available_resolution,
            "resolutions_last_checked": t.resolutions_last_checked.isoformat() if t.resolutions_last_checked else None,
            "video_size_bytes": v_size,
            "audio_size_bytes": a_size,
            "is_hardlinked": t.is_hardlinked,
            "disk_versions": disk_versions,
        })

    return result


@router.post("/{playlist_id}/tracks/refresh-resolutions")
async def refresh_tracks_resolutions(playlist_id: int, db: Session = Depends(get_db)):
    """On-demand probe of YouTube available video resolutions for tracks in this playlist"""
    playlist = PlaylistRepository.get_by_id(playlist_id, db=db)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    tracks = TrackRepository.get_tracks_by_playlist_id(playlist_id, db=db)
    probed_count = 0

    for t in tracks:
        try:
            info = probe_video_info(f"https://www.youtube.com/watch?v={t.video_id}")
            if info.get("status") == "success" and info.get("available_resolutions"):
                TrackRepository.set_available_resolutions(t.video_id, info["available_resolutions"], db=db)
                probed_count += 1
        except Exception as e:
            logger.warning(f"Failed to refresh resolutions for {t.video_id}: {e}")

    return {"message": f"Refreshed available resolutions for {probed_count} tracks", "playlist_id": playlist_id}


@router.post("/{playlist_id}/tracks/{video_id}/upgrade")
async def upgrade_track_resolution(
    playlist_id: int,
    video_id: str,
    payload: TrackUpgradeRequest,
    db: Session = Depends(get_db)
):
    """
    Method B Track Upgrade:
    Downloads the targeted resolution with verified bracket naming [1080p].
    Retains older copy by default for verification; deletes if delete_older=True.
    """
    import yt_dlp
    from app.models.database import Track
    from app.services.ytdlp_service import ytdlp_service
    from app.utils.ytdlp_opts import build_ytdlp_options
    from app.core.track_indexer import probe_local_media_metadata

    playlist = PlaylistRepository.get_by_id(playlist_id, db=db)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    track = TrackRepository.get_by_video_id(video_id, db=db)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    playlist_folder = ytdlp_service.resolve_playlist_folder(playlist.title)
    os.makedirs(playlist_folder, exist_ok=True)

    target_res = payload.target_resolution
    outtmpl = os.path.join(playlist_folder, f"%(title)s [%(id)s] [{target_res}p].%(ext)s")
    format_selector = f"bestvideo[height<={target_res}]+bestaudio/best[height<={target_res}]/best"

    ydl_opts = build_ytdlp_options(
        mode="download",
        playlist_folder=playlist_folder,
        extra_opts={
            "format": format_selector,
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
            "noplaylist": True,
        }
    )

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            info = ydl.extract_info(video_url, download=True)
            if not info:
                raise ValueError("Could not extract or download upgraded stream from YouTube.")

            upgraded_filepath = ydl.prepare_filename(info)
            if not os.path.isfile(upgraded_filepath):
                # Check mp4 fallback
                base, _ = os.path.splitext(upgraded_filepath)
                if os.path.isfile(f"{base}.mp4"):
                    upgraded_filepath = f"{base}.mp4"

            # Verify local media metadata with ffprobe
            media_meta = probe_local_media_metadata(upgraded_filepath, track.primary_audio_filepath or "")

            # Update downloaded resolutions
            res_str = f"{target_res}p"
            current_res = list(track.downloaded_resolutions_json or [])
            if res_str not in current_res:
                current_res.append(res_str)

            # Delete older versions if requested
            if payload.delete_older:
                for fname in os.listdir(playlist_folder):
                    if f"[{video_id}]" in fname and fname.lower().endswith((".mp4", ".mkv", ".webm")):
                        fpath = os.path.join(playlist_folder, fname)
                        if fpath != upgraded_filepath and os.path.isfile(fpath):
                            try:
                                os.remove(fpath)
                            except Exception as ex:
                                logger.warning(f"Could not delete older copy {fpath}: {ex}")
                current_res = [res_str]

            track = TrackRepository.update_resolutions_metadata(
                video_id=video_id,
                primary_filepath=upgraded_filepath,
                downloaded_resolutions=current_res,
                downloaded_fps=media_meta.get("fps"),
                db=db
            )

            return {
                "status": "success",
                "video_id": video_id,
                "resolution": res_str,
                "primary_filepath": upgraded_filepath,
                "downloaded_resolutions": track.downloaded_resolutions_json,
                "fps": track.downloaded_fps,
            }

    except Exception as e:
        logger.error(f"Upgrade failed for {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Upgrade failed: {str(e)}")


@router.post("/{playlist_id}/tracks/{video_id}/upgrade-audio")
async def upgrade_track_audio(
    playlist_id: int,
    video_id: str,
    payload: AudioUpgradeRequest,
    db: Session = Depends(get_db)
):
    """
    Upgrade track audio:
    If local video exists, extract directly (0 network usage).
    Otherwise, download standalone Format 251 Opus / MP3 from YouTube.
    """
    import subprocess
    import yt_dlp
    from app.models.database import Track
    from app.services.ytdlp_service import ytdlp_service
    from app.utils.ytdlp_opts import build_ytdlp_options
    from app.core.track_indexer import probe_local_media_metadata

    playlist = PlaylistRepository.get_by_id(playlist_id, db=db)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    track = TrackRepository.get_by_video_id(video_id, db=db)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    playlist_folder = ytdlp_service.resolve_playlist_folder(playlist.title)
    audio_folder = os.path.join(playlist_folder, "audio")
    os.makedirs(audio_folder, exist_ok=True)

    fmt = payload.audio_format
    ext = "mp3" if "mp3" in fmt else ("opus" if "opus" in fmt else "m4a")

    # If local video file exists, extract directly without downloading!
    if track.primary_filepath and os.path.isfile(track.primary_filepath):
        safe_title = os.path.splitext(os.path.basename(track.primary_filepath))[0]
        # Remove any resolution bracket from audio filename
        import re
        safe_title = re.sub(r"\s*\[\d{3,4}p\]", "", safe_title)
        target_audio = os.path.join(audio_folder, f"{safe_title}.{ext}")

        bitrate = "320k" if "320" in fmt else ("160k" if "160" in fmt else "256k")
        cmd = ["ffmpeg", "-y", "-i", track.primary_filepath, "-vn", "-b:a", bitrate, target_audio]
        res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if res.returncode == 0 and os.path.isfile(target_audio):
            meta = probe_local_media_metadata(track.primary_filepath, target_audio)
            track = TrackRepository.update_audio_metadata(
                video_id=video_id,
                audio_filepath=target_audio,
                codec=meta.get("audio_codec") or ext,
                bitrate=meta.get("audio_bitrate") or bitrate,
                db=db
            )
            return {
                "status": "success",
                "source": "local_extraction",
                "audio_filepath": target_audio,
                "codec": track.downloaded_audio_codec,
                "bitrate": track.downloaded_audio_bitrate
            }

    # Otherwise fetch Format 251 Opus from YouTube
    outtmpl = os.path.join(audio_folder, f"%(title)s [%(id)s].%(ext)s")
    codec = "mp3" if "mp3" in fmt else ("opus" if "opus" in fmt else "m4a")
    ydl_opts = build_ytdlp_options(
        mode="extract",
        playlist_folder=audio_folder,
        extra_opts={
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": codec,
                "preferredquality": "320" if "320" in fmt else "160",
            }]
        }
    )

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            info = ydl.extract_info(video_url, download=True)
            downloaded = ydl.prepare_filename(info)
            base, _ = os.path.splitext(downloaded)
            final_audio = f"{base}.{codec}" if os.path.isfile(f"{base}.{codec}") else downloaded

            meta = probe_local_media_metadata(track.primary_filepath or "", final_audio)
            track = TrackRepository.update_audio_metadata(
                video_id=video_id,
                audio_filepath=final_audio,
                codec=meta.get("audio_codec") or codec,
                bitrate=meta.get("audio_bitrate") or "320k",
                db=db
            )

            return {
                "status": "success",
                "source": "youtube_download",
                "audio_filepath": final_audio,
                "codec": track.downloaded_audio_codec,
                "bitrate": track.downloaded_audio_bitrate
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio upgrade failed: {str(e)}")


@router.post("/{playlist_id}/tracks/{video_id}/set-primary")
async def set_primary_track_version(
    playlist_id: int,
    video_id: str,
    payload: SetPrimaryRequest,
    db: Session = Depends(get_db)
):
    """Set a specific resolution file as the primary copy"""
    from app.models.database import Track
    from app.services.ytdlp_service import ytdlp_service

    playlist = PlaylistRepository.get_by_id(playlist_id, db=db)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    track = TrackRepository.get_by_video_id(video_id, db=db)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    playlist_folder = ytdlp_service.resolve_playlist_folder(playlist.title)
    target_res = payload.resolution.lower()

    # Search for file matching resolution
    found_path = None
    for fname in os.listdir(playlist_folder):
        if f"[{video_id}]" in fname and f"[{target_res}]" in fname.lower():
            found_path = os.path.join(playlist_folder, fname)
            break

    if not found_path or not os.path.isfile(found_path):
        raise HTTPException(status_code=404, detail=f"No local file found with resolution '{target_res}'")

    track = TrackRepository.update_resolutions_metadata(
        video_id=video_id,
        primary_filepath=found_path,
        db=db
    )

    return {"status": "success", "primary_filepath": found_path, "primary_resolution": track.primary_resolution}


@router.delete("/{playlist_id}/tracks/{video_id}/versions/{resolution}")
async def delete_track_version(
    playlist_id: int,
    video_id: str,
    resolution: str,
    db: Session = Depends(get_db)
):
    """Delete a specific resolution file for a track"""
    from app.models.database import Track
    from app.services.ytdlp_service import ytdlp_service

    playlist = PlaylistRepository.get_by_id(playlist_id, db=db)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    track = TrackRepository.get_by_video_id(video_id, db=db)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    playlist_folder = ytdlp_service.resolve_playlist_folder(playlist.title)
    target_res = resolution.lower()

    # Find file matching resolution
    deleted = False
    for fname in os.listdir(playlist_folder):
        if f"[{video_id}]" in fname and f"[{target_res}]" in fname.lower():
            fpath = os.path.join(playlist_folder, fname)
            if os.path.isfile(fpath):
                os.remove(fpath)
                deleted = True

    # Update downloaded resolutions
    current_res = [r for r in (track.downloaded_resolutions_json or []) if r.lower() != target_res]

    # If deleted copy was primary, reassign primary to highest remaining version
    remaining_versions = _find_track_versions(playlist_folder, video_id)
    new_primary = remaining_versions[0]["filepath"] if remaining_versions else ""

    track = TrackRepository.update_resolutions_metadata(
        video_id=video_id,
        primary_filepath=new_primary,
        downloaded_resolutions=current_res,
        db=db
    )

    return {
        "status": "success",
        "deleted": deleted,
        "remaining_resolutions": track.downloaded_resolutions_json,
        "primary_filepath": track.primary_filepath
    }


@router.get("/{playlist_id}/export-audio/zip")
async def export_audio_as_zip(
    playlist_id: int,
    format: str = "mp3",
    db: Session = Depends(get_db)
):
    """
    Stream a lossless, uncompressed ZIP archive containing the extracted audio folder
    and its .m3u8/.m3u playlist files for immediate browser download.
    """
    import zipfile
    import tempfile
    from app.services.ytdlp_service import ytdlp_service
    from app.core import yt_playlist_audio_tools as tools

    playlist = PlaylistRepository.get_by_id(playlist_id, db=db)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    format_label, audio_ext, effective_mode = tools.resolve_audio_format_info(format)
    playlist_folder = ytdlp_service.resolve_playlist_folder(playlist.title)
    safe_title = tools._sanitize_title(playlist.title)

    candidates = [
        os.path.join(playlist_folder, f"{safe_title} [{format_label}]"),
        os.path.join(playlist_folder, safe_title),
        os.path.join(playlist_folder, "audio")
    ]

    target_audio_folder = None
    for cand in candidates:
        if os.path.isdir(cand):
            files = [f for f in os.listdir(cand) if f.lower().endswith(audio_ext)]
            if files:
                target_audio_folder = cand
                break

    if not target_audio_folder:
        for cand in candidates:
            if os.path.isdir(cand):
                files = [f for f in os.listdir(cand) if f.lower().endswith((".mp3", ".opus", ".flac", ".m4a", ".aac"))]
                if files:
                    target_audio_folder = cand
                    break

    if not target_audio_folder or not os.path.isdir(target_audio_folder):
        raise HTTPException(
            status_code=404,
            detail=f"No audio files found for format '{format_label}'. Please run audio extraction first."
        )

    # Ensure m3u8 and m3u exist in target_audio_folder
    try:
        tools.generate_m3u_playlists(playlist_folder, [target_audio_folder])
    except Exception:
        pass

    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    temp_zip_path = temp_zip.name
    temp_zip.close()

    folder_name_in_zip = f"{safe_title} [{format_label}]"
    with zipfile.ZipFile(temp_zip_path, "w", zipfile.ZIP_STORED) as zf:
        for root, dirs, files in os.walk(target_audio_folder):
            for file in sorted(files):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, target_audio_folder)
                arcname = os.path.join(folder_name_in_zip, rel_path)
                zf.write(full_path, arcname=arcname)

    return FileResponse(
        temp_zip_path,
        filename=f"{folder_name_in_zip}.zip",
        media_type="application/zip",
        background=BackgroundTask(os.remove, temp_zip_path)
    )


@router.post("/{playlist_id}/tracks/{video_id}/extract-audio")
async def extract_single_track_audio(
    playlist_id: int,
    video_id: str,
    format: str = "mp3",
    db: Session = Depends(get_db)
):
    """
    On-demand single track audio extraction with rich ID3 metadata injection and M3U8 update.
    Prioritizes local audio source or extracts from local video container without network call.
    """
    import json
    from app.services.ytdlp_service import ytdlp_service
    from app.core import yt_playlist_audio_tools as tools
    from app.core.track_indexer import probe_local_media_metadata

    playlist = PlaylistRepository.get_by_id(playlist_id, db=db)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")

    track = TrackRepository.get_by_video_id(video_id, db=db)
    if not track:
        raise HTTPException(status_code=404, detail="Track not found")

    format_label, audio_ext, effective_mode = tools.resolve_audio_format_info(format)
    playlist_folder = ytdlp_service.resolve_playlist_folder(playlist.title)
    safe_title = tools._sanitize_title(playlist.title)
    audio_folder = os.path.join(playlist_folder, f"{safe_title} [{format_label}]")
    os.makedirs(audio_folder, exist_ok=True)

    # Find source file
    source_file = None
    if track.primary_audio_filepath and os.path.isfile(track.primary_audio_filepath):
        source_file = track.primary_audio_filepath
    elif track.primary_filepath and os.path.isfile(track.primary_filepath):
        source_file = track.primary_filepath
    else:
        for fname in os.listdir(playlist_folder):
            if f"[{video_id}]" in fname:
                full = os.path.join(playlist_folder, fname)
                if os.path.isfile(full):
                    source_file = full
                    break

    if not source_file or not os.path.isfile(source_file):
        raise HTTPException(
            status_code=404,
            detail="No local media file found for this track. Please download the track first."
        )

    ffmpeg_path = tools._find_ffmpeg()
    if not ffmpeg_path:
        raise HTTPException(status_code=500, detail="FFmpeg not found on system")

    # Read YouTube index and metadata from snapshot
    meta = None
    idx = 1
    total_tracks = 1
    snapshot_file = os.path.join(playlist_folder, "playlist_info_snapshot", "playlist_info.json")
    if os.path.isfile(snapshot_file):
        try:
            with open(snapshot_file, "r", encoding="utf-8") as f:
                s_data = json.load(f)
                entries = s_data.get("entries") or []
                total_tracks = max(len(entries), 1)
                for i, e in enumerate(entries, start=1):
                    if e.get("id") == video_id:
                        idx = i
                        meta = {
                            "title": e.get("title") or track.title,
                            "artist": e.get("uploader") or e.get("channel") or track.artist or "Unknown Artist",
                            "album": playlist.title,
                            "track": f"{idx}/{total_tracks}",
                            "date": (e.get("upload_date") or "")[:4] or str(datetime.utcnow().year)
                        }
                        break
        except Exception:
            pass

    if not meta:
        meta = {
            "title": track.title,
            "artist": track.artist or "Unknown Artist",
            "album": playlist.title,
            "track": "1/1",
            "date": str(datetime.utcnow().year)
        }

    res = tools._extract_single_audio(
        vid_path=source_file,
        audio_folder=audio_folder,
        ffmpeg_path=ffmpeg_path,
        idx=idx,
        total=total_tracks,
        extract_mode=format,
        metadata=meta
    )

    if res.get("status") == "failed":
        raise HTTPException(status_code=500, detail="Audio extraction failed")

    target_audio = res.get("audio")
    if target_audio and os.path.isfile(target_audio):
        meta_probe = probe_local_media_metadata(track.primary_filepath or "", target_audio)
        track = TrackRepository.update_audio_metadata(
            video_id=video_id,
            audio_filepath=target_audio,
            codec=meta_probe.get("audio_codec") or audio_ext.lstrip("."),
            bitrate=meta_probe.get("audio_bitrate") or "320k",
            db=db
        )
        try:
            tools.generate_m3u_playlists(playlist_folder, [audio_folder])
        except Exception:
            pass

    return {
        "status": "success",
        "audio_filepath": target_audio,
        "format": format_label,
        "codec": track.downloaded_audio_codec,
        "bitrate": track.downloaded_audio_bitrate
    }

