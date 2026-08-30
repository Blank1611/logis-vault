"""
Playlist Data Access Repository
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.database import Playlist, get_db_context


class PlaylistRepository:
    """Centralized repository for all Playlist data operations"""

    @staticmethod
    def get_by_id(playlist_id: int, db: Optional[Session] = None) -> Optional[Playlist]:
        """Fetch playlist by ID"""
        with get_db_context(db) as session:
            return session.query(Playlist).filter(Playlist.id == playlist_id).first()

    @staticmethod
    def get_by_url(url: str, db: Optional[Session] = None) -> Optional[Playlist]:
        """Fetch playlist by exact URL"""
        with get_db_context(db) as session:
            return session.query(Playlist).filter(Playlist.url == url).first()

    @staticmethod
    def get_by_url_or_title(url: str, title: str, db: Optional[Session] = None) -> Optional[Playlist]:
        """Fetch playlist matching URL or Title"""
        with get_db_context(db) as session:
            return session.query(Playlist).filter(
                or_(Playlist.url == url, Playlist.title == title)
            ).first()

    @staticmethod
    def get_all(db: Optional[Session] = None) -> List[Playlist]:
        """Fetch all playlists"""
        with get_db_context(db) as session:
            return session.query(Playlist).all()

    @staticmethod
    def create(
        url: str,
        title: str,
        local_count: int = 0,
        playlist_count: int = 0,
        unavailable_count: int = 0,
        excluded_ids: Optional[List[str]] = None,
        db: Optional[Session] = None
    ) -> Playlist:
        """Create and persist a new Playlist"""
        with get_db_context(db) as session:
            playlist = Playlist(
                url=url,
                title=title,
                local_count=local_count,
                playlist_count=playlist_count,
                unavailable_count=unavailable_count,
                excluded_ids=excluded_ids or [],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(playlist)
            session.flush()
            session.refresh(playlist)
            return playlist

    @staticmethod
    def update_counts(
        playlist_id: int,
        local_count: Optional[int] = None,
        playlist_count: Optional[int] = None,
        unavailable_count: Optional[int] = None,
        last_download: Optional[datetime] = None,
        last_extract: Optional[datetime] = None,
        db: Optional[Session] = None
    ) -> Optional[Playlist]:
        """Update playlist track counts and timestamps"""
        with get_db_context(db) as session:
            playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
            if not playlist:
                return None
            if local_count is not None:
                playlist.local_count = local_count
            if playlist_count is not None:
                playlist.playlist_count = playlist_count
            if unavailable_count is not None:
                playlist.unavailable_count = unavailable_count
            if last_download is not None:
                playlist.last_download = last_download
            if last_extract is not None:
                playlist.last_extract = last_extract
            playlist.updated_at = datetime.utcnow()
            return playlist

    @staticmethod
    def update_exclusions(playlist_id: int, excluded_ids: List[str], db: Optional[Session] = None) -> Optional[Playlist]:
        """Update excluded video IDs list"""
        with get_db_context(db) as session:
            playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
            if not playlist:
                return None
            playlist.excluded_ids = excluded_ids
            playlist.updated_at = datetime.utcnow()
            return playlist

    @staticmethod
    def delete(playlist_id: int, db: Optional[Session] = None) -> bool:
        """Delete a playlist by ID"""
        with get_db_context(db) as session:
            playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
            if not playlist:
                return False
            session.delete(playlist)
            session.flush()
            if db is not None:
                session.commit()
            return True
