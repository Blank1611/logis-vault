"""
Database models using SQLAlchemy
"""
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, Float, Text, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from pathlib import Path
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

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Playlist(Base):
    """Playlist model"""
    __tablename__ = "playlists"
    
    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=False)
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

# Create tables
Base.metadata.create_all(bind=engine)

def _auto_migrate_sqlite_columns():
    """Ensure newly added columns exist in existing SQLite database tables."""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            # Check existing columns in jobs table
            result = conn.execute(text("PRAGMA table_info(jobs)"))
            existing_cols = {row[1] for row in result.fetchall()}
            
            new_columns = [
                ("current_video_title", "VARCHAR"),
                ("current_video_id", "VARCHAR"),
                ("current_video_bytes_downloaded", "BIGINT DEFAULT 0"),
                ("current_video_bytes_total", "BIGINT DEFAULT 0"),
                ("current_video_speed", "FLOAT DEFAULT 0.0"),
                ("current_video_eta", "INTEGER DEFAULT 0"),
            ]
            for col_name, col_type in new_columns:
                if col_name not in existing_cols:
                    conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {col_name} {col_type}"))
                    conn.commit()
    except Exception as e:
        print(f"[DB] Auto-migration check note: {e}")

_auto_migrate_sqlite_columns()

# Dependency
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

