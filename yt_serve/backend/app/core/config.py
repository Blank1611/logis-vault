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

def _has_cli_flag(flag_names: list) -> bool:
    """Check if any of the given boolean flags exist in sys.argv"""
    for arg in sys.argv:
        if arg in flag_names:
            return True
        for f in flag_names:
            if arg.startswith(f"{f}="):
                val = arg.split("=", 1)[1].lower()
                return val in ("true", "1", "yes")
    return False

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
_cli_disable_onboarding = _has_cli_flag(["--disable-onboarding", "--no-onboarding", "--no_onboarding", "--disable_onboarding"])
_cli_enable_auto_discovery = _has_cli_flag(["--enable-auto-discovery", "--auto-discovery"])
_cli_no_auto_discovery = _has_cli_flag(["--no-auto-discovery", "--disable-auto-discovery"])
_cli_auto_discovery_interval = _resolve_cli_flag("--auto-discovery-interval")

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

# Anti-rate-limit sleep delay jitter (seconds between video downloads)
SLEEP_INTERVAL_MIN=1
SLEEP_INTERVAL_MAX=5

# Concurrent DASH video stream fragments per download (1-16)
CONCURRENT_FRAGMENTS=2

# Automated Daily Background Refresh (24/7 Server Mode)
ENABLE_DAILY_AUTO_REFRESH=true
DAILY_REFRESH_TIME=04:00
DAILY_REFRESH_TIMEZONE=Asia/Kolkata

# Automated Git Metadata Sync & Versioning (uncomment and set to true when configured)
ENABLE_GIT_METADATA_SYNC=false
# GIT_REMOTE_URL=https://github.com/username/yt-playlists-metadata.git
# GIT_AUTH_TOKEN=ghp_yourPersonalAccessTokenHere
GIT_BRANCH=main

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
    
    # Batch & Rate-Limiting Settings
    BATCH_SIZE: int = 200
    SLEEP_INTERVAL_MIN: int = 1
    SLEEP_INTERVAL_MAX: int = 5
    CONCURRENT_FRAGMENTS: int = 2
    
    # Daily Scheduler
    ENABLE_DAILY_AUTO_REFRESH: bool = True
    DAILY_REFRESH_TIME: str = "04:00"
    DAILY_REFRESH_TIMEZONE: str = "Asia/Kolkata"
    
    # Git Metadata Sync (Disabled by default until repository and token are configured)
    ENABLE_GIT_METADATA_SYNC: bool = False
    GIT_REMOTE_URL: Optional[str] = None
    GIT_AUTH_TOKEN: Optional[str] = None
    GIT_BRANCH: str = "main"
    
    # Cookies
    COOKIES_FILE: Optional[str] = None
    USE_BROWSER_COOKIES: bool = False
    BROWSER_NAME: str = "chrome"
    
    # Experimental Integrity Safeguards
    ENABLE_STREAM_INTEGRITY_CHECK: bool = False
    
    # FlareSolverr Proxy (Optional)
    FLARESOLVERR_URL: Optional[str] = None

    # Auto-Discovery & Onboarding
    ENABLE_AUTO_DISCOVERY: bool = True
    AUTO_DISCOVERY_INTERVAL_MINUTES: int = 60  # 0 = on_startup_only
    CLI_DISABLE_ONBOARDING: bool = False

    # Ad-hoc / Single Video Downloads
    ADHOC_DOWNLOAD_PATH: Optional[str] = None
    USE_CUSTOM_ADHOC_PATH: bool = False

    def get_adhoc_download_path(self) -> str:
        """Resolve absolute ad-hoc downloads directory"""
        if self.USE_CUSTOM_ADHOC_PATH and self.ADHOC_DOWNLOAD_PATH:
            return os.path.abspath(self.ADHOC_DOWNLOAD_PATH)
        return os.path.abspath(os.path.join(self.BASE_DOWNLOAD_PATH, "_adhoc_downloads"))

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
        if _cli_disable_onboarding:
            self.CLI_DISABLE_ONBOARDING = True
        if _cli_enable_auto_discovery:
            self.ENABLE_AUTO_DISCOVERY = True
        if _cli_no_auto_discovery:
            self.ENABLE_AUTO_DISCOVERY = False
        if _cli_auto_discovery_interval is not None:
            try:
                self.AUTO_DISCOVERY_INTERVAL_MINUTES = int(_cli_auto_discovery_interval)
            except ValueError:
                pass
        
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
