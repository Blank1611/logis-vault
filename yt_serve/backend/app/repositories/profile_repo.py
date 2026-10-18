"""
Quality Profile Repository
Centralized data access for Radarr/Sonarr-style quality and extraction profiles.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import QualityProfile, Playlist, get_db_context


class QualityProfileRepository:
    """Repository managing QualityProfile CRUD and playlist assignment"""

    @staticmethod
    def get_all(db: Optional[Session] = None) -> List[QualityProfile]:
        """Fetch all quality profiles ordered by max_resolution descending"""
        with get_db_context(db) as session:
            return session.query(QualityProfile).order_by(QualityProfile.max_resolution.desc()).all()

    @staticmethod
    def get_by_id(profile_id: str, db: Optional[Session] = None) -> Optional[QualityProfile]:
        """Fetch quality profile by ID"""
        with get_db_context(db) as session:
            return session.query(QualityProfile).filter(QualityProfile.id == profile_id).first()

    @staticmethod
    def create(
        id: str,
        name: str,
        description: Optional[str] = None,
        max_resolution: int = 1080,
        audio_format: str = "mp3_320",
        cipher_strategy: str = "web_decipher",
        is_audio_only: bool = False,
        is_builtin: bool = False,
        db: Optional[Session] = None
    ) -> QualityProfile:
        """Create and persist a new Quality Profile"""
        clean_id = id.strip().lower().replace(" ", "_")
        with get_db_context(db) as session:
            existing = session.query(QualityProfile).filter(QualityProfile.id == clean_id).first()
            if existing:
                raise ValueError(f"Profile with ID '{clean_id}' already exists.")

            profile = QualityProfile(
                id=clean_id,
                name=name.strip(),
                description=description,
                max_resolution=max_resolution,
                audio_format=audio_format,
                cipher_strategy=cipher_strategy,
                is_audio_only=is_audio_only,
                is_builtin=is_builtin,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(profile)
            session.commit()
            session.refresh(profile)
            return profile

    @staticmethod
    def update(
        profile_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        max_resolution: Optional[int] = None,
        audio_format: Optional[str] = None,
        cipher_strategy: Optional[str] = None,
        is_audio_only: Optional[bool] = None,
        db: Optional[Session] = None
    ) -> Optional[QualityProfile]:
        """Update an existing quality profile"""
        with get_db_context(db) as session:
            profile = session.query(QualityProfile).filter(QualityProfile.id == profile_id).first()
            if not profile:
                return None

            if name is not None:
                profile.name = name.strip()
            if description is not None:
                profile.description = description
            if max_resolution is not None:
                profile.max_resolution = max_resolution
            if audio_format is not None:
                profile.audio_format = audio_format
            if cipher_strategy is not None:
                profile.cipher_strategy = cipher_strategy
            if is_audio_only is not None:
                profile.is_audio_only = is_audio_only

            profile.updated_at = datetime.utcnow()
            session.commit()
            session.refresh(profile)
            return profile

    @staticmethod
    def delete(profile_id: str, db: Optional[Session] = None) -> bool:
        """Delete a custom quality profile. Reassigns any affected playlist to 'standard_1080p'."""
        with get_db_context(db) as session:
            profile = session.query(QualityProfile).filter(QualityProfile.id == profile_id).first()
            if not profile:
                return False
            if profile.is_builtin:
                raise ValueError("Built-in system quality profiles cannot be deleted.")

            # Reassign any playlists using this profile to standard_1080p fallback
            playlists_to_reassign = session.query(Playlist).filter(Playlist.quality_profile_id == profile_id).all()
            for p in playlists_to_reassign:
                p.quality_profile_id = "standard_1080p"
                p.updated_at = datetime.utcnow()

            session.delete(profile)
            session.commit()
            return True
