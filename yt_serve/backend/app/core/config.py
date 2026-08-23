"""
Application configuration
"""
import sys
import os
from pathlib import Path
from typing import Optional
from pydantic_settings import BaseSettings

# Base backend directory
BACKEND_DIR = Path(__file__).parent.parent.parent

def _resolve_cli_flag(flag_name: str) -> Optional[str]:
    """Extract flag value from sys.argv (supports --flag=val and --flag val)"""
    for idx, arg in enumerate(sys.argv):
        if arg.startswith(f"{flag_name}="):
            return arg.split("=", 1)[1]
        elif arg == flag_name and idx + 1 < len(sys.argv):
            return sys.argv[idx + 1]
    return None

# Resolve Config File Path:
# Priority:
# 1. CLI flag --config.file
# 2. Environment variable CONFIG_FILE
# 3. Persistent Docker directory /app/data/config.env (if /app/data exists)
# 4. Local BACKEND_DIR / ".env"
_cli_config_file = _resolve_cli_flag("--config.file")
_env_config_file = os.getenv("CONFIG_FILE")
_docker_data_env = Path("/app/data/config.env")

if _cli_config_file:
    ENV_FILE = Path(_cli_config_file)
elif _env_config_file:
    ENV_FILE = Path(_env_config_file)
elif _docker_data_env.parent.is_dir():
    ENV_FILE = _docker_data_env
else:
    ENV_FILE = BACKEND_DIR / ".env"

# CLI flag overrides
_cli_db_path = _resolve_cli_flag("--storage.db.path")
_cli_downloads_path = _resolve_cli_flag("--storage.downloads.path")
_cli_temp_path = _resolve_cli_flag("--storage.temp.path")

DEFAULT_ENV_TEMPLATE = """# ==============================================================================
# YouTube Playlist Manager Configuration (yt_serve)
# ==============================================================================

# Root directory where playlists and media files will be saved (e.g. 2TB external HDD)
BASE_DOWNLOAD_PATH=/downloads

# Optional fast SSD directory for active fragment downloads & FFmpeg processing (e.g. /downloads-temp)
# Leave commented or empty to download directly to BASE_DOWNLOAD_PATH
# TEMP_DOWNLOAD_PATH=/downloads-temp

# Audio extraction mode:
# - copy: Stream copy AAC audio to .m4a / Opus to .opus without re-encoding (lossless & fastest)
# - mp3_best: Re-encode to highest quality MP3 (VBR ~250-320 kbps)
# - mp3_high: Re-encode to standard high quality MP3 (VBR ~190-250 kbps)
# - opus: Re-encode to Opus codec (128 kbps)
AUDIO_EXTRACT_MODE=copy

# Concurrency limits
MAX_CONCURRENT_EXTRACTIONS=4
MAX_CONCURRENT_DOWNLOADS=1

# Videos to process per batch (prevents platform rate limiting)
BATCH_SIZE=200

# Path to YouTube authentication cookies (Netscape format)
# Upload via Web UI or specify path here
# COOKIES_FILE=/app/data/cookies.txt

# Experimental stream integrity validation via FFprobe (true/false)
ENABLE_STREAM_INTEGRITY_CHECK=false

# Optional FlareSolverr Proxy URL (e.g. http://flaresolverr:8191/v1)
# FLARESOLVERR_URL=http://flaresolverr:8191/v1
"""

def _ensure_default_env_file():
    """Auto-generate documented default config.env if not present on disk"""
    try:
        if not ENV_FILE.is_file():
            # If parent directory exists (e.g. /app/data or backend), write template
            if ENV_FILE.parent.is_dir():
                with open(ENV_FILE, "w", encoding="utf-8") as f:
                    f.write(DEFAULT_ENV_TEMPLATE)
                print(f"[CONFIG] Generated default configuration template at: {ENV_FILE}")
    except Exception as e:
        print(f"[CONFIG] Note: Could not auto-generate default template file ({e})")

# Check and auto-generate default config file on startup if needed
_ensure_default_env_file()

class Settings(BaseSettings):
    """Application settings"""
    
    # API Settings
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "YouTube Playlist Manager"
    
    # Database
    DATABASE_PATH: str = _cli_db_path or "yt_manager.db"
    
    # Download settings
    BASE_DOWNLOAD_PATH: str = _cli_downloads_path or "downloads"
    TEMP_DOWNLOAD_PATH: Optional[str] = _cli_temp_path or None
    MAX_CONCURRENT_DOWNLOADS: int = 1
    MAX_CONCURRENT_EXTRACTIONS: int = 4
    
    # Audio settings
    AUDIO_EXTRACT_MODE: str = "copy"  # copy, mp3_best, mp3_high, opus
    
    # Batch settings
    BATCH_SIZE: int = 200
    
    # Cookies
    COOKIES_FILE: Optional[str] = None
    USE_BROWSER_COOKIES: bool = False
    BROWSER_NAME: str = "chrome"
    
    # Experimental Integrity Safeguards
    ENABLE_STREAM_INTEGRITY_CHECK: bool = False
    
    # FlareSolverr Proxy (Optional)
    FLARESOLVERR_URL: Optional[str] = None

    class Config:
        env_file = str(ENV_FILE) if ENV_FILE.is_file() else None
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env
    
    def get_env_file_path(self) -> Path:
        """Get the active .env configuration file path"""
        return ENV_FILE

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Apply CLI flag overrides if present
        if _cli_db_path:
            self.DATABASE_PATH = _cli_db_path
        if _cli_downloads_path:
            self.BASE_DOWNLOAD_PATH = _cli_downloads_path
        if _cli_temp_path:
            self.TEMP_DOWNLOAD_PATH = _cli_temp_path
        
        # Normalize empty string temp path to None
        if self.TEMP_DOWNLOAD_PATH and not self.TEMP_DOWNLOAD_PATH.strip():
            self.TEMP_DOWNLOAD_PATH = None
        
        # Debug: Print loaded configuration
        print(f"[CONFIG] Loaded settings:")
        print(f"  BASE_DOWNLOAD_PATH: {self.BASE_DOWNLOAD_PATH}")
        print(f"  TEMP_DOWNLOAD_PATH: {self.TEMP_DOWNLOAD_PATH or '(Disabled - downloading directly to destination)'}")
        print(f"  DATABASE_PATH: {self.DATABASE_PATH}")
        print(f"  Config file location: {ENV_FILE}")
        print(f"  Config file exists: {ENV_FILE.exists()}")
        
        # Create download path if it doesn't exist and is configured
        if self.BASE_DOWNLOAD_PATH and self.BASE_DOWNLOAD_PATH != "downloads":
            try:
                os.makedirs(self.BASE_DOWNLOAD_PATH, exist_ok=True)
                print(f"  Download path ready: {self.BASE_DOWNLOAD_PATH}")
            except Exception as e:
                print(f"  Warning: Could not create download path {self.BASE_DOWNLOAD_PATH}: {e}")
                
        # Create temp download path if configured
        if self.TEMP_DOWNLOAD_PATH:
            try:
                os.makedirs(self.TEMP_DOWNLOAD_PATH, exist_ok=True)
                print(f"  Temp SSD download path ready: {self.TEMP_DOWNLOAD_PATH}")
            except Exception as e:
                print(f"  Warning: Could not create temp download path {self.TEMP_DOWNLOAD_PATH}: {e}")

settings = Settings()
