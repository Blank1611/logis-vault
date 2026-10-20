"""
Track Data Access Repository
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.database import Track, MovedTrackHistory, get_db_context


class TrackRepository:
    """Centralized repository for all Track Index and Move History operations"""

    @staticmethod
    def get_by_video_id(video_id: str, db: Optional[Session] = None) -> Optional[Track]:
        """Fetch indexed track by YouTube video ID"""
        with get_db_context(db) as session:
            return session.query(Track).filter(Track.video_id == video_id).first()

    @staticmethod
    def get_all_tracks(
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        db: Optional[Session] = None
    ) -> List[Track]:
        """Fetch indexed tracks with optional title search and pagination"""
        with get_db_context(db) as session:
            query = session.query(Track)
            if search:
                query = query.filter(
                    or_(Track.title.ilike(f"%{search}%"), Track.video_id.ilike(f"%{search}%"))
                )
            return query.order_by(Track.updated_at.desc()).offset(offset).limit(limit).all()

    @staticmethod
    def count_tracks(search: Optional[str] = None, db: Optional[Session] = None) -> int:
        """Count total tracks matching optional search filter"""
        with get_db_context(db) as session:
            query = session.query(Track)
            if search:
                query = query.filter(
                    or_(Track.title.ilike(f"%{search}%"), Track.video_id.ilike(f"%{search}%"))
                )
            return query.count()

    @staticmethod
    def index_or_update_track(
        video_id: str,
        title: str,
        filepath: str,
        playlist_id: Optional[int] = None,
        audio_filepath: Optional[str] = None,
        artist: Optional[str] = None,
        duration: Optional[int] = None,
        is_hardlinked: bool = False,
        downloaded_resolutions: Optional[List[str]] = None,
        downloaded_fps: Optional[int] = None,
        downloaded_audio_codec: Optional[str] = None,
        downloaded_audio_bitrate: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Track:
        """Create or update a track record in the index with optional media metadata"""
        with get_db_context(db) as session:
            track = session.query(Track).filter(Track.video_id == video_id).first()
            if track:
                if filepath:
                    track.primary_filepath = filepath
                if audio_filepath:
                    track.primary_audio_filepath = audio_filepath
                if title and (not track.title or track.title == video_id):
                    track.title = title
                if duration is not None:
                    track.duration = duration
                if artist:
                    track.artist = artist
                if is_hardlinked:
                    track.is_hardlinked = True
                if downloaded_resolutions is not None:
                    track.downloaded_resolutions_json = downloaded_resolutions
                if downloaded_fps is not None:
                    track.downloaded_fps = downloaded_fps
                if downloaded_audio_codec is not None:
                    track.downloaded_audio_codec = downloaded_audio_codec
                if downloaded_audio_bitrate is not None:
                    track.downloaded_audio_bitrate = downloaded_audio_bitrate

                # Update associated playlists
                current_playlists = list(track.playlists_json or [])
                if playlist_id is not None and playlist_id not in current_playlists:
                    current_playlists.append(playlist_id)
                    track.playlists_json = current_playlists

                track.updated_at = datetime.utcnow()
                session.commit()
                session.refresh(track)
                return track
            else:
                playlists = [playlist_id] if playlist_id is not None else []
                new_track = Track(
                    video_id=video_id,
                    title=title or video_id,
                    artist=artist,
                    duration=duration,
                    primary_filepath=filepath or "",
                    primary_audio_filepath=audio_filepath,
                    playlists_json=playlists,
                    is_hardlinked=is_hardlinked,
                    downloaded_resolutions_json=downloaded_resolutions or [],
                    downloaded_fps=downloaded_fps,
                    downloaded_audio_codec=downloaded_audio_codec,
                    downloaded_audio_bitrate=downloaded_audio_bitrate,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                )
                session.add(new_track)
                session.commit()
                session.refresh(new_track)
                return new_track

    @staticmethod
    def update_resolutions_metadata(
        video_id: str,
        primary_filepath: Optional[str] = None,
        downloaded_resolutions: Optional[List[str]] = None,
        downloaded_fps: Optional[int] = None,
        db: Optional[Session] = None
    ) -> Optional[Track]:
        """Update downloaded resolutions, primary filepath, and fps with commit"""
        with get_db_context(db) as session:
            track = session.query(Track).filter(Track.video_id == video_id).first()
            if not track:
                return None
            if primary_filepath is not None:
                track.primary_filepath = primary_filepath
            if downloaded_resolutions is not None:
                track.downloaded_resolutions_json = downloaded_resolutions
            if downloaded_fps is not None:
                track.downloaded_fps = downloaded_fps
            track.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(track)
            return track

    @staticmethod
    def update_audio_metadata(
        video_id: str,
        audio_filepath: str,
        codec: Optional[str] = None,
        bitrate: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Optional[Track]:
        """Update extracted audio filepath, codec, bitrate, and commit"""
        with get_db_context(db) as session:
            track = session.query(Track).filter(Track.video_id == video_id).first()
            if not track:
                return None
            track.primary_audio_filepath = audio_filepath
            if codec is not None:
                track.downloaded_audio_codec = codec
            if bitrate is not None:
                track.downloaded_audio_bitrate = bitrate
            track.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(track)
            return track

    @staticmethod
    def set_available_resolutions(
        video_id: str,
        available_resolutions: List[Any],
        db: Optional[Session] = None
    ) -> Optional[Track]:
        """Update probed available resolutions and commit"""
        with get_db_context(db) as session:
            track = session.query(Track).filter(Track.video_id == video_id).first()
            if not track:
                return None
            track.available_resolutions_json = available_resolutions
            track.resolutions_last_checked = datetime.utcnow()
            track.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(track)
            return track

    @staticmethod
    def record_move_history(
        video_id: str,
        title: str,
        from_playlist_id: int,
        from_playlist_title: str,
        to_playlist_id: int,
        to_playlist_title: str,
        status: str = "auto_moved",
        db: Optional[Session] = None
    ) -> MovedTrackHistory:
        """Record an inter-playlist track move audit entry and commit"""
        with get_db_context(db) as session:
            history = MovedTrackHistory(
                video_id=video_id,
                title=title,
                from_playlist_id=from_playlist_id,
                from_playlist_title=from_playlist_title,
                to_playlist_id=to_playlist_id,
                to_playlist_title=to_playlist_title,
                moved_at=datetime.utcnow(),
                status=status,
            )
            session.add(history)
            session.commit()
            session.refresh(history)
            return history

    @staticmethod
    def get_move_history(limit: int = 50, db: Optional[Session] = None) -> List[MovedTrackHistory]:
        """Fetch recent track move history audit logs"""
        with get_db_context(db) as session:
            return session.query(MovedTrackHistory).order_by(
                MovedTrackHistory.moved_at.desc()
            ).limit(limit).all()
