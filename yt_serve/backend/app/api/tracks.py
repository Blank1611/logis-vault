"""
Track Index & Reorganization REST API Router for yt_serve.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.database import get_db, Track, MovedTrackHistory, Playlist
from app.core.track_indexer import execute_track_move

router = APIRouter()


class ApplyMoveRequest(BaseModel):
    video_id: str
    from_playlist_id: int
    to_playlist_id: int
    action: str = "move"  # move or ignore


class BatchApplyMovesRequest(BaseModel):
    moves: List[ApplyMoveRequest]


@router.get("/index")
async def list_indexed_tracks(
    search: Optional[str] = Query(None, description="Search by title or video_id"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    List all globally indexed tracks in the library.
    """
    query = db.query(Track)
    if search:
        s = f"%{search}%"
        query = query.filter((Track.title.ilike(s)) | (Track.video_id.ilike(s)))

    total = query.count()
    tracks = query.order_by(desc(Track.updated_at)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "video_id": t.video_id,
                "title": t.title,
                "artist": t.artist,
                "duration": t.duration,
                "primary_filepath": t.primary_filepath,
                "primary_audio_filepath": t.primary_audio_filepath,
                "playlists": t.playlists_json or [],
                "is_hardlinked": t.is_hardlinked,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in tracks
        ]
    }


@router.get("/reorganize/pending")
async def get_pending_reorganizations(db: Session = Depends(get_db)):
    """
    Analyze playlists to identify tracks that appear to have been moved
    (e.g., removed from one playlist but added to another).
    """
    playlists = db.query(Playlist).all()
    # Simple pending reorganization suggestion logic based on multi-playlist coexistence & history
    pending_moves: List[Dict[str, Any]] = []

    # Get tracks in multiple playlists that could be reviewed
    multi_tracks = db.query(Track).all()
    playlists_map = {p.id: p.title for p in playlists}

    for track in multi_tracks:
        pl_ids = list(track.playlists_json or [])
        if len(pl_ids) >= 2:
            # Multi-playlist coexistence info
            pending_moves.append({
                "video_id": track.video_id,
                "title": track.title,
                "from_playlist_id": pl_ids[0],
                "from_playlist_title": playlists_map.get(pl_ids[0], f"Playlist #{pl_ids[0]}"),
                "to_playlist_id": pl_ids[1],
                "to_playlist_title": playlists_map.get(pl_ids[1], f"Playlist #{pl_ids[1]}"),
                "type": "coexistence",
                "suggested_action": "hardlink"
            })

    return {
        "count": len(pending_moves),
        "pending": pending_moves
    }


@router.post("/reorganize/apply")
async def apply_batch_reorganization(
    payload: BatchApplyMovesRequest,
    db: Session = Depends(get_db)
):
    """
    Apply selected batch relocations and log to moved_tracks_history.
    """
    results = []
    for item in payload.moves:
        try:
            res = execute_track_move(
                video_id=item.video_id,
                from_playlist_id=item.from_playlist_id,
                to_playlist_id=item.to_playlist_id,
                db=db,
                status="manually_moved" if item.action == "move" else "ignored"
            )
            results.append({"status": "success", "data": res})
        except Exception as e:
            results.append({"status": "error", "video_id": item.video_id, "error": str(e)})

    return {
        "processed": len(results),
        "results": results
    }


@router.get("/reorganize/history")
async def get_reorganization_history(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Get audit history of moved/reorganized tracks.
    """
    total = db.query(MovedTrackHistory).count()
    items = db.query(MovedTrackHistory).order_by(desc(MovedTrackHistory.moved_at)).offset(offset).limit(limit).all()

    return {
        "total": total,
        "items": [
            {
                "id": h.id,
                "video_id": h.video_id,
                "title": h.title,
                "from_playlist_id": h.from_playlist_id,
                "from_playlist_title": h.from_playlist_title,
                "to_playlist_id": h.to_playlist_id,
                "to_playlist_title": h.to_playlist_title,
                "status": h.status,
                "moved_at": h.moved_at.isoformat() if h.moved_at else None
            }
            for h in items
        ]
    }
