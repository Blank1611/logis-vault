"""
Database models using SQLAlchemy
"""
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, Float, Text, JSON, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import os

# Import settings to get database path
from app.core.config import settings

# Resolve database path
# If DATABASE_PATH is absolute, use it as-is
# If relative, resolve it relative to backend directory
BACKEND_DIR = Path(__file__).parent.parent.parent
if os.path.isabs(settings.DATABASE_PATH):
    DB_PATH = Path(settings.DATABASE_PATH)
else:
    DB_PATH = BACKEND_DIR / settings.DATABASE_PATH

# Ensure parent directory exists
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

print(f"[DATABASE] Using database at: {DB_PATH}")
print(f"[DATABASE] Database exists: {DB_PATH.exists()}")

from sqlalchemy import event
from contextlib import contextmanager

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

@event.listens_for(engine, "connect")
def set_sqlite_pragmas(dbapi_connection, connection_record):
    """Enable SQLite WAL mode, normal synchronous, busy timeout, and foreign keys for high concurrency."""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception as e:
        print(f"[DB] Note setting SQLite pragmas: {e}")

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class QualityProfile(Base):
    """Quality Profile model for Radarr/Sonarr style extraction & resolution control"""
    __tablename__ = "quality_profiles"

    id = Column(String, primary_key=True)               # e.g., 'ultra_4k', 'qhd_1440p', 'standard_1080p', 'standard_720p', 'fast_mixtape_360p', 'audio_only'
    name = Column(String, nullable=False)               # Display name: "Standard HD 720p"
    description = Column(String, nullable=True)
    max_resolution = Column(Integer, default=1080)      # 2160, 1440, 1080, 720, 360, or 0 (audio-only)
    audio_format = Column(String, default="mp3_320")    # "mp3_320", "opus_native", "m4a", "flac"
    cipher_strategy = Column(String, default="web_decipher")  # "web_decipher" vs "bypass_challenge"
    is_audio_only = Column(Boolean, default=False)
    is_builtin = Column(Boolean, default=False)         # Built-in profiles cannot be deleted
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Playlist(Base):
    """Playlist model"""
    __tablename__ = "playlists"
    
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
    quality_profile_id = Column(String, ForeignKey("quality_profiles.id"), default="standard_1080p", nullable=False)
    local_count = Column(Integer, default=0)
    playlist_count = Column(Integer, default=0)
    unavailable_count = Column(Integer, default=0)
    last_download = Column(DateTime, nullable=True)
    last_extract = Column(DateTime, nullable=True)
    excluded_ids = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Job(Base):
    """Download/Extract job model"""
    __tablename__ = "jobs"
    
    id = Column(Integer, primary_key=True, index=True)
    playlist_id = Column(Integer, nullable=False)
    job_type = Column(String, nullable=False)  # download, extract, both
    status = Column(String, default="pending")  # pending, running, completed, failed, cancelled
    
    # Overall progress (deprecated, kept for compatibility)
    progress = Column(Float, default=0.0)
    total_items = Column(Integer, default=0)
    completed_items = Column(Integer, default=0)
    failed_items = Column(Integer, default=0)
    
    # Separate download progress
    download_status = Column(String, nullable=True)  # pending, running, completed, failed
    download_total = Column(Integer, default=0)
    download_completed = Column(Integer, default=0)
    download_failed = Column(Integer, default=0)
    download_batch_info = Column(String, nullable=True)  # e.g., "Batch 1/3"
    
    # Separate extraction progress
    extract_status = Column(String, nullable=True)  # pending, running, completed, failed
    extract_total = Column(Integer, default=0)
    extract_completed = Column(Integer, default=0)
    extract_failed = Column(Integer, default=0)
    
    # In-flight active video byte stream telemetry (Dual-Tier progress)
    current_video_title = Column(String, nullable=True)
    current_video_id = Column(String, nullable=True)
    current_video_bytes_downloaded = Column(BigInteger, default=0)
    current_video_bytes_total = Column(BigInteger, default=0)
    current_video_speed = Column(Float, default=0.0)  # bytes per second
    current_video_eta = Column(Integer, default=0)  # seconds remaining
    
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

class Track(Base):
    """Global index of downloaded tracks for cross-playlist hardlinking and deduplication"""
    __tablename__ = "tracks"

    video_id = Column(String, primary_key=True, index=True)
    title = Column(String, nullable=False)
    artist = Column(String, nullable=True)
    duration = Column(Integer, nullable=True)
    primary_filepath = Column(String, nullable=False)
    primary_audio_filepath = Column(String, nullable=True)
    playlists_json = Column(JSON, default=list)  # List of playlist IDs [1, 2, ...]
    is_hardlinked = Column(Boolean, default=False)
    downloaded_resolutions_json = Column(JSON, default=list)  # e.g. ["1080p", "720p"]
    downloaded_fps = Column(Integer, nullable=True)
    downloaded_audio_codec = Column(String, nullable=True)
    downloaded_audio_bitrate = Column(Integer, nullable=True)
    available_resolutions_json = Column(JSON, default=list)  # e.g. [2160, 1440, 1080, 720, 360]
    resolutions_last_checked = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def primary_resolution(self) -> Optional[str]:
        if self.primary_filepath:
            import re
            m = re.search(r"\[(\d+p)\]", self.primary_filepath)
            if m:
                return m.group(1)
        return self.downloaded_resolutions_json[0] if self.downloaded_resolutions_json else None

    @property
    def highest_available_resolution(self) -> Optional[str]:
        if not self.available_resolutions_json:
            return None
        max_h = 0
        for item in self.available_resolutions_json:
            if isinstance(item, int):
                max_h = max(max_h, item)
            elif isinstance(item, str):
                digits = "".join(filter(str.isdigit, item))
                val = int(digits) if digits else 0
                max_h = max(max_h, val)
            elif isinstance(item, dict):
                max_h = max(max_h, int(item.get("height", 0)))
        return f"{max_h}p" if max_h > 0 else None

class MovedTrackHistory(Base):
    """Audit log for tracks moved between playlists on YouTube"""
    __tablename__ = "moved_tracks_history"

    id = Column(Integer, primary_key=True, index=True)
    video_id = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    from_playlist_id = Column(Integer, nullable=False)
    from_playlist_title = Column(String, nullable=False)
    to_playlist_id = Column(Integer, nullable=False)
    to_playlist_title = Column(String, nullable=False)
    moved_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="auto_moved")  # auto_moved, manually_moved, ignored

class SystemSetting(Base):
    """Key-value system setting and state persistence"""
    __tablename__ = "system_settings"

    key = Column(String, primary_key=True, index=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def get_system_setting(key: str, default: Optional[str] = None, db: Optional[Session] = None) -> Optional[str]:
    """Retrieve a system setting from SQLite database."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        return setting.value if setting else default
    except Exception:
        return default
    finally:
        if close_db:
            db.close()

def set_system_setting(key: str, value: str, db: Optional[Session] = None) -> Optional[SystemSetting]:
    """Persist a system setting into SQLite database."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if setting:
            setting.value = str(value)
            setting.updated_at = datetime.utcnow()
        else:
            setting = SystemSetting(key=key, value=str(value), updated_at=datetime.utcnow())
            db.add(setting)
        db.commit()
        db.refresh(setting)
        return setting
    except Exception as e:
        print(f"[DB] Error setting system setting {key}: {e}")
        return None
    finally:
        if close_db:
            db.close()

class FolderStatus(Base):
    """Lifecycle tracking for disk folders (e.g. excluded, pending_deletion for soft-delete retention)"""
    __tablename__ = "folder_status"

    folder_name = Column(String, primary_key=True, index=True)
    status = Column(String, nullable=False, index=True)  # 'excluded', 'pending_deletion', etc.
    reason = Column(String, nullable=True)               # e.g. 'user_excluded', 'soft_deleted'
    delete_after = Column(DateTime, nullable=True)       # Timestamp after which folder can be permanently purged
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

def get_folder_status(folder_name: str, db: Optional[Session] = None) -> Optional[FolderStatus]:
    """Retrieve status record for a folder."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        return db.query(FolderStatus).filter(FolderStatus.folder_name == folder_name).first()
    except Exception:
        return None
    finally:
        if close_db:
            db.close()

def set_folder_status(
    folder_name: str,
    status: str,
    reason: Optional[str] = None,
    delete_after: Optional[datetime] = None,
    db: Optional[Session] = None
) -> Optional[FolderStatus]:
    """Upsert a folder status record."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        record = db.query(FolderStatus).filter(FolderStatus.folder_name == folder_name).first()
        if record:
            record.status = status
            record.reason = reason
            record.delete_after = delete_after
            record.updated_at = datetime.utcnow()
        else:
            record = FolderStatus(
                folder_name=folder_name,
                status=status,
                reason=reason,
                delete_after=delete_after,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(record)
        db.commit()
        db.refresh(record)
        return record
    except Exception as e:
        print(f"[DB] Error setting folder status for {folder_name}: {e}")
        return None
    finally:
        if close_db:
            db.close()

def remove_folder_status(folder_name: str, db: Optional[Session] = None) -> bool:
    """Delete a folder status record (restoring it to normal/unmanaged)."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        record = db.query(FolderStatus).filter(FolderStatus.folder_name == folder_name).first()
        if record:
            db.delete(record)
            db.commit()
            return True
        return False
    except Exception as e:
        print(f"[DB] Error removing folder status for {folder_name}: {e}")
        return False
    finally:
        if close_db:
            db.close()

def list_folder_statuses(status: Optional[str] = None, db: Optional[Session] = None) -> List[FolderStatus]:
    """List all folder statuses, optionally filtered by status."""
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        query = db.query(FolderStatus)
        if status:
            query = query.filter(FolderStatus.status == status)
        return query.all()
    except Exception:
        return []
    finally:
        if close_db:
            db.close()

# Create tables
Base.metadata.create_all(bind=engine)

def _auto_migrate_sqlite_columns():
    """Ensure newly added columns exist in existing SQLite database tables and seed default profiles."""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            # 1. Check existing columns in jobs table
            result = conn.execute(text("PRAGMA table_info(jobs)"))
            existing_cols_jobs = {row[1] for row in result.fetchall()}
            
            new_job_columns = [
                ("current_video_title", "VARCHAR"),
                ("current_video_id", "VARCHAR"),
                ("current_video_bytes_downloaded", "BIGINT DEFAULT 0"),
                ("current_video_bytes_total", "BIGINT DEFAULT 0"),
                ("current_video_speed", "FLOAT DEFAULT 0.0"),
                ("current_video_eta", "INTEGER DEFAULT 0"),
            ]
            for col_name, col_type in new_job_columns:
                if col_name not in existing_cols_jobs:
                    conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}"))
                    conn.commit()

            # 2. Check existing columns in playlists table
            result = conn.execute(text("PRAGMA table_info(playlists)"))
            existing_cols_playlists = {row[1] for row in result.fetchall()}
            if "quality_profile_id" not in existing_cols_playlists:
                conn.execute(text("ALTER TABLE playlists ADD COLUMN quality_profile_id VARCHAR DEFAULT 'standard_1080p'"))
                conn.commit()

            # 3. Check existing columns in tracks table
            result = conn.execute(text("PRAGMA table_info(tracks)"))
            existing_cols_tracks = {row[1] for row in result.fetchall()}
            new_track_columns = [
                ("downloaded_resolutions_json", "JSON DEFAULT '[]'"),
                ("downloaded_fps", "INTEGER"),
                ("downloaded_audio_codec", "VARCHAR"),
                ("downloaded_audio_bitrate", "INTEGER"),
                ("available_resolutions_json", "JSON DEFAULT '[]'"),
                ("resolutions_last_checked", "DATETIME"),
            ]
            for col_name, col_type in new_track_columns:
                if col_name not in existing_cols_tracks:
                    conn.execute(text(f"ALTER TABLE tracks ADD COLUMN {col_name} {col_type}"))
                    conn.commit()

            # 4. Seed default built-in quality profiles if quality_profiles table is empty
            profile_count = conn.execute(text("SELECT COUNT(*) FROM quality_profiles")).scalar()
            if profile_count == 0:
                default_profiles = [
                    ("ultra_4k", "Ultra 4K", "4K Ultra HD resolution with highest available audio quality", 2160, "mp3_320", "web_decipher", 0, 1),
                    ("qhd_1440p", "Quad HD 1440p", "2K Quad HD resolution with highest available audio quality", 1440, "mp3_320", "web_decipher", 0, 1),
                    ("standard_1080p", "Standard HD 1080p", "1080p Full HD resolution with highest available audio quality", 1080, "mp3_320", "web_decipher", 0, 1),
                    ("standard_720p", "Standard HD 720p", "720p HD resolution with high quality audio and balanced file sizes", 720, "mp3_320", "web_decipher", 0, 1),
                    ("fast_mixtape_360p", "Fast / Mixtape 360p (Challenge-Free)", "360p progressive stream, zero JS challenge deciphering, ideal for long background mixtapes", 360, "mp3_320", "direct_format18", 0, 1),
                    ("audio_only", "Audio Only Vault", "Direct audio stream extraction, no video file stored on disk", 0, "mp3_320", "web_decipher", 1, 1),
                ]
                now_str = datetime.utcnow().isoformat()
                for p in default_profiles:
                    conn.execute(text(
                        "INSERT INTO quality_profiles (id, name, description, max_resolution, audio_format, cipher_strategy, is_audio_only, is_builtin, created_at, updated_at) "
                        "VALUES (:id, :name, :description, :max_res, :audio_fmt, :cipher, :is_audio, :is_builtin, :created_at, :updated_at)"
                    ), {
                        "id": p[0], "name": p[1], "description": p[2], "max_res": p[3],
                        "audio_fmt": p[4], "cipher": p[5], "is_audio": p[6], "is_builtin": p[7],
                        "created_at": now_str, "updated_at": now_str
                    })
                conn.commit()
            else:
                # Ensure fast_mixtape_360p has cipher_strategy set to direct_format18
                conn.execute(text("UPDATE quality_profiles SET cipher_strategy = 'direct_format18' WHERE id = 'fast_mixtape_360p' AND cipher_strategy = 'bypass_challenge'"))
                conn.commit()
    except Exception as e:
        print(f"[DB] Auto-migration check note: {e}")

_auto_migrate_sqlite_columns()

# Dispose connection pool after import-time table creation and auto-migration
engine.dispose()

import atexit
atexit.register(engine.dispose)


# Dependency for FastAPI
def get_db():
    """Get database session for FastAPI request lifecycle"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_db_context(existing_db: Optional[Session] = None):
    """
    Context manager for background workers, services, and tasks.
    Auto-commits on success, rolls back on error, and closes session cleanly when creating a new session.
    If an existing session is passed, yields it directly for nested re-use.
    """
    if existing_db is not None:
        yield existing_db
    else:
        db = SessionLocal()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

