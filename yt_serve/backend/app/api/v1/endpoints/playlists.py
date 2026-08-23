"""
Playlist management API endpoints for multi-platform playlist operations
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import List, Optional
from pydantic import BaseModel, HttpUrl
from sqlalchemy.orm import Session
from datetime import datetime
import os

from app.models.database import get_db, Playlist
from app.services.ytdlp_service import DownloadService
from app.core.config import settings

router = APIRouter()

class PlaylistCreate(BaseModel):
    """Playlist creation model"""
    url: HttpUrl
    title: Optional[str] = None

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
    
    class Config:
        from_attributes = True

class PlaylistUpdate(BaseModel):
    """Playlist update model"""
    title: Optional[str] = None
    excluded_ids: Optional[List[str]] = None

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
        playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
        if not playlist:
            return
        
        download_service = get_download_service()
        local_count, available_count, unavailable_count = await download_service.get_playlist_stats(
            playlist.title,
            playlist.url,
            playlist.excluded_ids or [],
            source="ondemand"
        )
        
        playlist.local_count = local_count
        playlist.playlist_count = available_count
        playlist.unavailable_count = unavailable_count
        playlist.updated_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()

@router.get("/", response_model=List[PlaylistResponse])
async def list_playlists(db: Session = Depends(get_db)):
    """Get all playlists"""
    playlists = db.query(Playlist).all()
    
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
            excluded_ids=p.excluded_ids or []
        ))
    
    return result

# Route without trailing slash for compatibility
@router.get("", response_model=List[PlaylistResponse])
async def list_playlists_no_slash(db: Session = Depends(get_db)):
    """Get all playlists (no trailing slash version)"""
    return await list_playlists(db)

@router.post("/", response_model=PlaylistResponse, status_code=201)
async def create_playlist(
    playlist: PlaylistCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Add a new playlist"""
    # Check if playlist already exists
    existing = db.query(Playlist).filter(Playlist.url == str(playlist.url)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Playlist already exists")
    
    # Get playlist info
    download_service = get_download_service()
    try:
        info = await download_service.get_playlist_info(str(playlist.url))
        title = playlist.title or info.get("title", "Unknown Playlist")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not fetch playlist info: {str(e)}")
    
    # Create playlist
    db_playlist = Playlist(
        url=str(playlist.url),
        title=title,
        excluded_ids=[]
    )
    db.add(db_playlist)
    db.commit()
    db.refresh(db_playlist)
    
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
        excluded_ids=[]
    )

@router.get("/{playlist_id}", response_model=PlaylistResponse)
async def get_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """Get playlist by ID"""
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
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
        excluded_ids=playlist.excluded_ids or []
    )

@router.put("/{playlist_id}", response_model=PlaylistResponse)
async def update_playlist(
    playlist_id: int,
    playlist: PlaylistUpdate,
    db: Session = Depends(get_db)
):
    """Update playlist"""
    db_playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not db_playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    # Update fields
    if playlist.title is not None:
        db_playlist.title = playlist.title
    if playlist.excluded_ids is not None:
        db_playlist.excluded_ids = playlist.excluded_ids
    
    db_playlist.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_playlist)
    
    return PlaylistResponse(
        id=db_playlist.id,
        url=db_playlist.url,
        title=db_playlist.title,
        local_count=db_playlist.local_count,
        playlist_count=db_playlist.playlist_count,
        unavailable_count=db_playlist.unavailable_count,
        last_download=db_playlist.last_download.isoformat() if db_playlist.last_download else None,
        last_extract=db_playlist.last_extract.isoformat() if db_playlist.last_extract else None,
        excluded_ids=db_playlist.excluded_ids or []
    )

@router.delete("/{playlist_id}", status_code=204)
async def delete_playlist(playlist_id: int, db: Session = Depends(get_db)):
    """Delete playlist"""
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    db.delete(playlist)
    db.commit()
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

    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    # Refresh stats in background
    background_tasks.add_task(refresh_playlist_stats_task, playlist_id)
    
    return {"message": "Refresh started", "playlist_id": playlist_id}

@router.post("/{playlist_id}/open-folder")
async def open_playlist_folder(playlist_id: int, db: Session = Depends(get_db)):
    """Open playlist folder in file explorer (or return path in headless mode)"""
    from app.core import yt_playlist_audio_tools as tools
    from app.utils.system import open_folder_in_explorer
    
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
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
    """Get video information (titles) for a playlist from playlist_info.json snapshots"""
    import json
    from app.core import yt_playlist_audio_tools as tools
    
    playlist = db.query(Playlist).filter(Playlist.id == playlist_id).first()
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    
    # Get playlist folder
    safe_title = tools._sanitize_title(playlist.title)
    playlist_folder = os.path.join(settings.BASE_DOWNLOAD_PATH, safe_title)
    snapshot_folder = os.path.join(playlist_folder, "playlist_info_snapshot")
    
    # Find the most recent playlist_info.json
    video_info = {}
    if os.path.exists(snapshot_folder):
        json_files = [f for f in os.listdir(snapshot_folder) if f.startswith("playlist_info_") and f.endswith(".json")]
        if json_files:
            # Get the most recent file
            json_files.sort(reverse=True)
            latest_file = os.path.join(snapshot_folder, json_files[0])
            
            try:
                with open(latest_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    entries = data.get('entries', [])
                    
                    # Build a map of video_id -> title
                    for entry in entries:
                        if entry and entry.get('id'):
                            video_info[entry['id']] = {
                                'title': entry.get('title', 'Unknown Title'),
                                'duration': entry.get('duration'),
                                'uploader': entry.get('uploader'),
                            }
            except Exception as e:
                print(f"Error reading playlist info: {e}")
    
    return video_info

