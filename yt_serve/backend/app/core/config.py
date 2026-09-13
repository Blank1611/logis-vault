"""
Application configuration
"""
import sys
import os
from pathlib import Path
from typing import Optional
from pydantic import Field
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
_cli_git_user_name = _resolve_cli_flag("--git.user.name")
_cli_git_user_email = _resolve_cli_flag("--git.user.email")
_cli_log_max_bytes = _resolve_cli_flag("--log.max-bytes")
_cli_log_backup_count = _resolve_cli_flag("--log.backup-count")
_cli_log_ring_buffer_size = _resolve_cli_flag("--log.ring-buffer-size")
_cli_job_log_max_days = _resolve_cli_flag("--job-log.max-days")
_cli_job_log_max_files = _resolve_cli_flag("--job-log.max-files")

class Settings(BaseSettings):
    """Application settings"""
    
    # API Settings
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "YouTube Playlist Manager"
    
    # Database
    DATABASE_PATH: str = Field(
        default=_cli_db_path or "yt_manager.db",
        description="Path to SQLite database file"
    )
    
    # Download settings
    BASE_DOWNLOAD_PATH: str = Field(
        default=_cli_downloads_path or "downloads",
        description="Root directory where playlists and media files will be saved"
    )
    TEMP_DOWNLOAD_PATH: Optional[str] = Field(
        default=_cli_temp_path or None,
        description="Optional fast SSD directory for active fragment downloads & FFmpeg processing"
    )
    MAX_CONCURRENT_DOWNLOADS: int = Field(
        default=1,
        description="Maximum concurrent video downloads"
    )
    MAX_CONCURRENT_EXTRACTIONS: int = Field(
        default=4,
        description="Maximum concurrent audio extractions"
    )
    
    # Audio settings
    AUDIO_EXTRACT_MODE: str = Field(
        default="copy",
        description="Audio extraction mode: copy (lossless stream copy), mp3_best, mp3_high, opus"
    )
    
    # Batch & Rate-Limiting Settings
    BATCH_SIZE: int = Field(
        default=200,
        description="Videos to process per batch"
    )
    SLEEP_INTERVAL_MIN: int = Field(
        default=1,
        description="Minimum sleep delay jitter in seconds between video downloads"
    )
    SLEEP_INTERVAL_MAX: int = Field(
        default=5,
        description="Maximum sleep delay jitter in seconds between video downloads"
    )
    CONCURRENT_FRAGMENTS: int = Field(
        default=2,
        description="Concurrent DASH video stream fragments per download (1-16)"
    )
    
    # Daily Scheduler
    ENABLE_DAILY_AUTO_REFRESH: bool = Field(
        default=True,
        description="Automated daily background metadata refresh (24/7 Server Mode)"
    )
    DAILY_REFRESH_TIME: str = Field(
        default="04:00",
        description="Scheduled daily scan time in HH:MM format"
    )
    DAILY_REFRESH_TIMEZONE: str = Field(
        default="Asia/Kolkata",
        description="Timezone for scheduled daily scan"
    )
    DAILY_REFRESH_MODE: str = Field(
        default="scheduled",
        description="Daily refresh execution mode: 'scheduled' (fixed daily clock time) or 'interval' (periodic duration)"
    )
    DAILY_REFRESH_INTERVAL_MINUTES: int = Field(
        default=1440,
        description="Periodic metadata refresh interval in minutes if DAILY_REFRESH_MODE == 'interval' (default: 1440 / 24h)"
    )
    
    # Git Metadata Sync (Disabled by default until repository and token are configured)
    ENABLE_GIT_METADATA_SYNC: bool = Field(
        default=False,
        description="Enable automatic Git metadata versioning and sync"
    )
    GIT_REMOTE_URL: Optional[str] = Field(
        default=None,
        description="Remote Git repository URL (e.g. https://github.com/username/yt-metadata.git)"
    )
    GIT_AUTH_TOKEN: Optional[str] = Field(
        default=None,
        description="Git personal access token for remote push"
    )
    GIT_BRANCH: str = Field(
        default="main",
        description="Target Git branch name"
    )
    GIT_USER_NAME: str = Field(
        default="YouTube Playlist Manager",
        description="Git author & committer name for metadata commits"
    )
    GIT_USER_EMAIL: str = Field(
        default="yt-manager@homelab.local",
        description="Git author & committer email for metadata commits"
    )
    
    # Cookies
    COOKIES_FILE: Optional[str] = Field(
        default=None,
        description="Path to YouTube authentication cookies (Netscape format)"
    )
    USE_BROWSER_COOKIES: bool = Field(
        default=False,
        description="Extract YouTube cookies directly from local browser"
    )
    BROWSER_NAME: str = Field(
        default="chrome",
        description="Browser to extract cookies from (chrome, firefox, etc.)"
    )
    
    # Experimental Integrity Safeguards
    ENABLE_STREAM_INTEGRITY_CHECK: bool = Field(
        default=False,
        description="Validate video stream integrity via FFprobe"
    )
    
    # FlareSolverr Proxy (Optional)
    FLARESOLVERR_URL: Optional[str] = Field(
        default=None,
        description="Optional FlareSolverr proxy URL (e.g. http://flaresolverr:8191/v1)"
    )

    # Auto-Discovery & Onboarding
    ENABLE_AUTO_DISCOVERY: bool = Field(
        default=True,
        description="Automatically discover and import playlists from download directory on boot"
    )
    AUTO_DISCOVERY_INTERVAL_MINUTES: int = Field(
        default=1440,
        description="Periodic auto-discovery interval in minutes (default: 1440 / 24h)"
    )
    CLI_DISABLE_ONBOARDING: bool = Field(
        default=False,
        description="Flag to bypass the initial onboarding setup wizard"
    )

    # Ad-hoc / Single Video Downloads
    ADHOC_DOWNLOAD_PATH: Optional[str] = Field(
        default=None,
        description="Custom directory for ad-hoc / single video downloads"
    )
    USE_CUSTOM_ADHOC_PATH: bool = Field(
        default=False,
        description="Whether to use ADHOC_DOWNLOAD_PATH instead of default _adhoc_downloads"
    )

    # Logging & Retention
    LOG_MAX_BYTES: int = Field(
        default=10 * 1024 * 1024,
        description="Max bytes before yt_manager.log rotates (default: 10MB)"
    )
    LOG_BACKUP_COUNT: int = Field(
        default=5,
        description="Number of rotated yt_manager.log historical files to keep (default: 5)"
    )
    LOG_RING_BUFFER_SIZE: int = Field(
        default=1000,
        description="In-memory circular buffer capacity for live logs (default: 1000, min: 100, max: 50000)"
    )
    JOB_LOG_MAX_DAYS: int = Field(
        default=30,
        description="Max age in days before job_{id}.log files are purged (default: 30)"
    )
    JOB_LOG_MAX_FILES: int = Field(
        default=100,
        description="Max number of recent job_{id}.log files to retain (default: 100)"
    )
    EXCLUDED_DIRS: str = Field(
        default="",
        description="Comma-separated list of directory names to exclude from auto-discovery"
    )
    RENAME_FOLDER_ON_LINK: bool = Field(
        default=False,
        description="Default policy whether to rename folder on disk when linking to playlist (default: False)"
    )

    def get_adhoc_download_path(self) -> str:
        """Resolve absolute ad-hoc downloads directory"""
        if self.USE_CUSTOM_ADHOC_PATH and self.ADHOC_DOWNLOAD_PATH:
            return os.path.abspath(self.ADHOC_DOWNLOAD_PATH)
        return os.path.abspath(os.path.join(self.BASE_DOWNLOAD_PATH, "_adhoc_downloads"))

    def get_excluded_directories(self) -> List[str]:
        """Return list of lowercase directory names to strictly exclude from auto-discovery"""
        excluded = {
            "temp", "logs", "scratch", "node_modules", ".git", ".cache", "lost+found",
            "_adhoc_downloads"
        }
        if self.ADHOC_DOWNLOAD_PATH:
            excluded.add(os.path.basename(self.ADHOC_DOWNLOAD_PATH).lower())
        if self.EXCLUDED_DIRS:
            for item in self.EXCLUDED_DIRS.split(","):
                cleaned = item.strip().lower()
                if cleaned:
                    excluded.add(cleaned)
        return list(excluded)

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
        if _cli_git_user_name:
            self.GIT_USER_NAME = _cli_git_user_name
        if _cli_git_user_email:
            self.GIT_USER_EMAIL = _cli_git_user_email

        # Logging & retention CLI flag overrides
        if _cli_log_max_bytes:
            try:
                self.LOG_MAX_BYTES = max(1024 * 1024, int(_cli_log_max_bytes))
            except ValueError:
                pass
        if _cli_log_backup_count:
            try:
                self.LOG_BACKUP_COUNT = max(1, int(_cli_log_backup_count))
            except ValueError:
                pass
        if _cli_log_ring_buffer_size:
            try:
                self.LOG_RING_BUFFER_SIZE = max(100, min(50000, int(_cli_log_ring_buffer_size)))
            except ValueError:
                pass
        else:
            # Enforce clamp on ring buffer size even if loaded from .env
            self.LOG_RING_BUFFER_SIZE = max(100, min(50000, self.LOG_RING_BUFFER_SIZE))

        if _cli_job_log_max_days:
            try:
                self.JOB_LOG_MAX_DAYS = max(1, int(_cli_job_log_max_days))
            except ValueError:
                pass
        if _cli_job_log_max_files:
            try:
                self.JOB_LOG_MAX_FILES = max(1, int(_cli_job_log_max_files))
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


def generate_default_env() -> str:
    """Dynamically generate clean, documented .env content from Settings schema"""
    lines = [
        "# ==============================================================================",
        "# YouTube Playlist Manager Configuration (yt_serve)",
        "# ==============================================================================",
        "# Auto-generated from Settings schema\n"
    ]

    sections = {
        "Storage & Directories": [
            "BASE_DOWNLOAD_PATH", "TEMP_DOWNLOAD_PATH", "DATABASE_PATH",
            "ADHOC_DOWNLOAD_PATH", "USE_CUSTOM_ADHOC_PATH"
        ],
        "Extraction & Concurrency": [
            "AUDIO_EXTRACT_MODE", "MAX_CONCURRENT_DOWNLOADS",
            "MAX_CONCURRENT_EXTRACTIONS", "BATCH_SIZE"
        ],
        "Rate-Limiting & Network": [
            "SLEEP_INTERVAL_MIN", "SLEEP_INTERVAL_MAX", "CONCURRENT_FRAGMENTS",
            "ENABLE_STREAM_INTEGRITY_CHECK", "FLARESOLVERR_URL"
        ],
        "Cookies & Authentication": [
            "USE_BROWSER_COOKIES", "BROWSER_NAME", "COOKIES_FILE"
        ],
        "Daily Automation & Scheduler": [
            "ENABLE_DAILY_AUTO_REFRESH", "DAILY_REFRESH_TIME",
            "DAILY_REFRESH_TIMEZONE", "ENABLE_AUTO_DISCOVERY", "AUTO_DISCOVERY_INTERVAL_MINUTES"
        ],
        "Git Metadata Sync & Versioning": [
            "ENABLE_GIT_METADATA_SYNC", "GIT_REMOTE_URL", "GIT_AUTH_TOKEN",
            "GIT_BRANCH", "GIT_USER_NAME", "GIT_USER_EMAIL"
        ],
        "Logging & Retention": [
            "LOG_MAX_BYTES", "LOG_BACKUP_COUNT", "LOG_RING_BUFFER_SIZE",
            "JOB_LOG_MAX_DAYS", "JOB_LOG_MAX_FILES"
        ],
    }

    categorized = set()
    for cat_name, field_names in sections.items():
        lines.append(f"# --- {cat_name} ---")
        for fn in field_names:
            if fn in Settings.model_fields:
                categorized.add(fn)
                f_info = Settings.model_fields[fn]
                if f_info.description:
                    lines.append(f"# {f_info.description}")
                val = f_info.default
                if val is None or val == "":
                    lines.append(f"#{fn}=")
                elif isinstance(val, bool):
                    lines.append(f"{fn}={'true' if val else 'false'}")
                else:
                    lines.append(f"{fn}={val}")
                lines.append("")

    for fn, f_info in Settings.model_fields.items():
        if fn in categorized or fn.startswith("_") or fn in ("API_V1_STR", "PROJECT_NAME", "CLI_DISABLE_ONBOARDING"):
            continue
        if f_info.description:
            lines.append(f"# {f_info.description}")
        val = f_info.default
        if val is None or val == "":
            lines.append(f"#{fn}=")
        elif isinstance(val, bool):
            lines.append(f"{fn}={'true' if val else 'false'}")
        else:
            lines.append(f"{fn}={val}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def _ensure_default_env_file():
    """Auto-generate documented default config.env if not present on disk"""
    try:
        if not ENV_FILE.is_file():
            if ENV_FILE.parent.is_dir():
                with open(ENV_FILE, "w", encoding="utf-8") as f:
                    f.write(generate_default_env())
                print(f"[CONFIG] Generated default configuration template from schema at: {ENV_FILE}")
    except Exception as e:
        print(f"[CONFIG] Note: Could not auto-generate default template file ({e})")


_ensure_default_env_file()

settings = Settings()
