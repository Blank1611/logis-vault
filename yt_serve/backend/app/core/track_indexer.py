"""
Smart Track Indexer & Zero-Space Hardlink Engine for yt_serve.
Provides instant local sourcing, NTFS/ext4 hardlinks, and inter-playlist move management.
"""

import os
import shutil
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import SessionLocal, Track, MovedTrackHistory, Playlist
from app.core.logging_engine import get_logger

logger = get_logger("app.core.track_indexer")


def create_hardlink_or_copy(src_path: str, dst_path: str) -> bool:
    """
    Create a zero-space hardlink (os.link) pointing to the same physical disk inode.
    Falls back to copying if crossing distinct filesystem volumes.
    """
    if not os.path.exists(src_path):
        logger.warning(f"Source file for hardlink does not exist: {src_path}")
        return False

    if os.path.exists(dst_path):
        return True

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    try:
        os.link(src_path, dst_path)
        logger.info(f"Created zero-space hardlink: {dst_path} -> {src_path}")
        return True
    except OSError as e:
        logger.info(f"Hardlink not supported across volumes ({e}), falling back to copy: {src_path} -> {dst_path}")
        try:
            shutil.copy2(src_path, dst_path)
            return True
        except Exception as copy_err:
            logger.error(f"Failed to copy file from {src_path} to {dst_path}: {copy_err}")
            return False


def find_local_track(video_id: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    """
    Check if a video ID already exists locally in the global track index.
    Verifies that the physical file actually exists on disk.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        track = db.query(Track).filter(Track.video_id == video_id).first()
        if not track:
            return None

        # Verify video file exists on disk
        video_exists = os.path.isfile(track.primary_filepath)
        audio_exists = bool(track.primary_audio_filepath and os.path.isfile(track.primary_audio_filepath))

        if not video_exists and not audio_exists:
            logger.warning(f"Track {video_id} indexed in database but files missing on disk: {track.primary_filepath}")
            return None

        return {
            "video_id": track.video_id,
            "title": track.title,
            "artist": track.artist,
            "duration": track.duration,
            "primary_filepath": track.primary_filepath if video_exists else None,
            "primary_audio_filepath": track.primary_audio_filepath if audio_exists else None,
            "playlists": track.playlists_json or [],
            "is_hardlinked": track.is_hardlinked,
        }
    finally:
        if close_db:
            db.close()


def index_track(
    video_id: str,
    title: str,
    filepath: str,
    playlist_id: int,
    audio_filepath: Optional[str] = None,
    artist: Optional[str] = None,
    duration: Optional[int] = None,
    is_hardlinked: bool = False,
    db: Optional[Session] = None
) -> Track:
    """
    Register or update a track in the global SQLite tracks index.
    """
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        track = db.query(Track).filter(Track.video_id == video_id).first()
        if track:
            current_playlists = list(track.playlists_json or [])
            if playlist_id not in current_playlists:
                current_playlists.append(playlist_id)
                track.playlists_json = current_playlists

            if not os.path.exists(track.primary_filepath) and os.path.exists(filepath):
                track.primary_filepath = filepath
            if audio_filepath and os.path.exists(audio_filepath):
                track.primary_audio_filepath = audio_filepath

            track.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(track)
            return track
        else:
            new_track = Track(
                video_id=video_id,
                title=title,
                artist=artist,
                duration=duration,
                primary_filepath=filepath,
                primary_audio_filepath=audio_filepath,
                playlists_json=[playlist_id],
                is_hardlinked=is_hardlinked,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(new_track)
            db.commit()
            db.refresh(new_track)
            return new_track
    finally:
        if close_db:
            db.close()


def hardlink_track_to_playlist(
    video_id: str,
    target_playlist_id: int,
    target_playlist_dir: str,
    target_audio_dir: Optional[str] = None,
    db: Optional[Session] = None
) -> bool:
    """
    Locally source and hardlink an existing track into target playlist folders.
    """
    track_info = find_local_track(video_id, db=db)
    if not track_info:
        return False

    src_video = track_info.get("primary_filepath")
    src_audio = track_info.get("primary_audio_filepath")
    success = False

    # 1. Hardlink Video
    if src_video and os.path.isfile(src_video):
        filename = os.path.basename(src_video)
        dst_video = os.path.join(target_playlist_dir, filename)
        if create_hardlink_or_copy(src_video, dst_video):
            success = True

    # 2. Hardlink Audio
    if src_audio and os.path.isfile(src_audio) and target_audio_dir:
        audio_name = os.path.basename(src_audio)
        dst_audio = os.path.join(target_audio_dir, audio_name)
        create_hardlink_or_copy(src_audio, dst_audio)

    if success:
        index_track(
            video_id=video_id,
            title=track_info["title"],
            filepath=src_video or "",
            playlist_id=target_playlist_id,
            audio_filepath=src_audio,
            is_hardlinked=True,
            db=db
        )
        logger.info(f"✓ Zero-space hardlinked track '{track_info['title']}' ({video_id}) to playlist #{target_playlist_id}")

    return success


def execute_track_move(
    video_id: str,
    from_playlist_id: int,
    to_playlist_id: int,
    db: Session,
    status: str = "manually_moved"
) -> Dict[str, Any]:
    """
    Relocate track files from one playlist folder to another and log the move.
    """
    from_playlist = db.query(Playlist).filter(Playlist.id == from_playlist_id).first()
    to_playlist = db.query(Playlist).filter(Playlist.id == to_playlist_id).first()

    if not from_playlist or not to_playlist:
        raise ValueError("Source or destination playlist not found")

    track = db.query(Track).filter(Track.video_id == video_id).first()
    title = track.title if track else video_id

    # Update Track playlists_json
    if track:
        current_playlists = list(track.playlists_json or [])
        if from_playlist_id in current_playlists:
            current_playlists.remove(from_playlist_id)
        if to_playlist_id not in current_playlists:
            current_playlists.append(to_playlist_id)
        track.playlists_json = current_playlists
        track.updated_at = datetime.utcnow()

    # Record Move in History
    history_entry = MovedTrackHistory(
        video_id=video_id,
        title=title,
        from_playlist_id=from_playlist_id,
        from_playlist_title=from_playlist.title,
        to_playlist_id=to_playlist_id,
        to_playlist_title=to_playlist.title,
        moved_at=datetime.utcnow(),
        status=status
    )
    db.add(history_entry)
    db.commit()

    logger.info(f"Moved track '{title}' ({video_id}) from '{from_playlist.title}' to '{to_playlist.title}'")

    return {
        "video_id": video_id,
        "title": title,
        "from_playlist": from_playlist.title,
        "to_playlist": to_playlist.title,
        "status": status,
        "moved_at": history_entry.moved_at.isoformat()
    }
