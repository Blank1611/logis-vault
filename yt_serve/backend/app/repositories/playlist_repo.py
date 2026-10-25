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
        quality_profile_id: str = "standard_1080p",
        local_count: int = 0,
        playlist_count: int = 0,
        unavailable_count: int = 0,
        excluded_ids: Optional[List[str]] = None,
        db: Optional[Session] = None
    ) -> Playlist:
        """Create and persist a new Playlist with atomic commit"""
        with get_db_context(db) as session:
            playlist = Playlist(
                url=url,
                title=title,
                quality_profile_id=quality_profile_id or "standard_1080p",
                local_count=local_count,
                playlist_count=playlist_count,
                unavailable_count=unavailable_count,
                excluded_ids=excluded_ids or [],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(playlist)
            session.commit()
            session.refresh(playlist)
            return playlist

    @staticmethod
    def update(
        playlist_id: int,
        title: Optional[str] = None,
        quality_profile_id: Optional[str] = None,
        excluded_ids: Optional[List[str]] = None,
        db: Optional[Session] = None
    ) -> Optional[Playlist]:
        """Update playlist properties and commit"""
        with get_db_context(db) as session:
            playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
            if not playlist:
                return None
            if title is not None:
                playlist.title = title
            if quality_profile_id is not None:
                playlist.quality_profile_id = quality_profile_id
            if excluded_ids is not None:
                playlist.excluded_ids = excluded_ids
            playlist.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(playlist)
            return playlist

    @staticmethod
    def update_quality_profile(playlist_id: int, quality_profile_id: str, db: Optional[Session] = None) -> Optional[Playlist]:
        """Update playlist assigned quality profile and commit"""
        with get_db_context(db) as session:
            playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
            if not playlist:
                return None
            playlist.quality_profile_id = quality_profile_id or "standard_1080p"
            playlist.updated_at = datetime.utcnow()
            session.commit()
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
        """Update playlist track counts, timestamps, and commit"""
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
            session.commit()
            session.refresh(playlist)
            return playlist

    @staticmethod
    def update_exclusions(playlist_id: int, excluded_ids: List[str], db: Optional[Session] = None) -> Optional[Playlist]:
        """Update excluded video IDs list and commit"""
        with get_db_context(db) as session:
            playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
            if not playlist:
                return None
            playlist.excluded_ids = excluded_ids
            playlist.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(playlist)
            return playlist

    @staticmethod
    def exclude_video_id(playlist_id: int, video_id: str, db: Optional[Session] = None) -> Optional[Playlist]:
        """Add a video ID to the exclusion list and commit"""
        with get_db_context(db) as session:
            playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
            if not playlist:
                return None
            current_exclusions = list(playlist.excluded_ids or [])
            if video_id not in current_exclusions:
                current_exclusions.append(video_id)
                playlist.excluded_ids = current_exclusions
                playlist.updated_at = datetime.utcnow()
                session.commit()
                session.refresh(playlist)
            return playlist

    @staticmethod
    def include_video_id(playlist_id: int, video_id: str, db: Optional[Session] = None) -> Optional[Playlist]:
        """Remove a video ID from the exclusion list and commit"""
        with get_db_context(db) as session:
            playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
            if not playlist:
                return None
            current_exclusions = list(playlist.excluded_ids or [])
            if video_id in current_exclusions:
                current_exclusions.remove(video_id)
                playlist.excluded_ids = current_exclusions
                playlist.updated_at = datetime.utcnow()
                session.commit()
                session.refresh(playlist)
            return playlist

    @staticmethod
    def delete(playlist_id: int, db: Optional[Session] = None) -> bool:
        """Delete a playlist by ID and commit"""
        with get_db_context(db) as session:
            playlist = session.query(Playlist).filter(Playlist.id == playlist_id).first()
            if not playlist:
                return False
            session.delete(playlist)
            session.commit()
            return True

    @staticmethod
    def get_phantom_candidates(
        excluded_dirs: List[str],
        base_download_path: str,
        db: Optional[Session] = None
    ) -> List[Playlist]:
        """Find phantom database records without valid on-disk playlist_info.json"""
        import os
        candidates = []
        with get_db_context(db) as session:
            matched = session.query(Playlist).filter(
                or_(
                    Playlist.url.like("%list=test_custom%"),
                    Playlist.url.like("%list=_adhoc_downloads%")
                )
            ).all()
            candidates.extend(matched)

            all_pls = session.query(Playlist).all()
            for p in all_pls:
                if p in candidates:
                    continue
                if p.title.lower() in excluded_dirs or p.url.endswith(f"list={p.title}"):
                    folder = os.path.join(base_download_path, p.title)
                    info_json = os.path.join(folder, "playlist_info.json")
                    if not os.path.isfile(info_json):
                        candidates.append(p)
        return candidates

