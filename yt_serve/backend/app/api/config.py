"""
Configuration API endpoints
"""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import os
from pathlib import Path
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_engine import get_logger
from app.models.database import get_db

logger = get_logger("app.api.config")
router = APIRouter()

class ConfigResponse(BaseModel):
    """Configuration response model"""
    base_download_path: str
    temp_download_path: Optional[str] = None
    audio_extract_mode: str
    max_extraction_workers: int
    max_concurrent_downloads: int
    batch_size: int
    sleep_interval_min: int = 1
    sleep_interval_max: int = 5
    concurrent_fragments: int = 2
    enable_daily_auto_refresh: bool = True
    daily_refresh_time: str = "04:00"
    daily_refresh_timezone: str = "Asia/Kolkata"
    daily_refresh_mode: str = "scheduled"
    daily_refresh_interval_minutes: int = 1440
    enable_git_metadata_sync: bool = True
    enable_git_remote_push: bool = False
    git_remote_url: Optional[str] = None
    git_auth_token: Optional[str] = None
    git_branch: str = "main"
    git_user_name: str = "YouTube Playlist Manager"
    git_user_email: str = "yt-manager@homelab.local"
    cookies_file: Optional[str]
    use_browser_cookies: bool
    browser_name: str
    cookies_auth_mode: str = "cookies_txt"
    enable_stream_integrity_check: bool
    flaresolverr_url: Optional[str]
    enable_auto_discovery: bool = True
    auto_discovery_interval_minutes: int = 60
    setup_completed: bool = False
    needs_setup: bool  # Flag for first-run setup
    adhoc_download_path: Optional[str] = None
    use_custom_adhoc_path: bool = False
    effective_adhoc_download_path: str = ""
    excluded_dirs: str = ""
    rename_folder_on_link: bool = False

class ConfigUpdate(BaseModel):
    """Configuration update model"""
    base_download_path: Optional[str] = None
    temp_download_path: Optional[str] = None
    audio_extract_mode: Optional[str] = None
    max_extraction_workers: Optional[int] = None
    max_concurrent_downloads: Optional[int] = None
    batch_size: Optional[int] = None
    sleep_interval_min: Optional[int] = None
    sleep_interval_max: Optional[int] = None
    concurrent_fragments: Optional[int] = None
    enable_daily_auto_refresh: Optional[bool] = None
    daily_refresh_time: Optional[str] = None
    daily_refresh_timezone: Optional[str] = None
    daily_refresh_mode: Optional[str] = None
    daily_refresh_interval_minutes: Optional[int] = None
    enable_git_metadata_sync: Optional[bool] = None
    enable_git_remote_push: Optional[bool] = None
    git_remote_url: Optional[str] = None
    git_auth_token: Optional[str] = None
    git_branch: Optional[str] = None
    git_user_name: Optional[str] = None
    git_user_email: Optional[str] = None
    cookies_file: Optional[str] = None
    use_browser_cookies: Optional[bool] = None
    browser_name: Optional[str] = None
    cookies_auth_mode: Optional[str] = None
    enable_stream_integrity_check: Optional[bool] = None
    flaresolverr_url: Optional[str] = None
    enable_auto_discovery: Optional[bool] = None
    auto_discovery_interval_minutes: Optional[int] = None
    setup_completed: Optional[bool] = None
    adhoc_download_path: Optional[str] = None
    use_custom_adhoc_path: Optional[bool] = None
    excluded_dirs: Optional[str] = None
    rename_folder_on_link: Optional[bool] = None

def _check_needs_setup(db=None) -> bool:
    """Check if initial setup is needed (requires explicit completion or opt-out flag)"""
    # 1. Explicit CLI flag --disable-onboarding / --no-onboarding or environment variable
    if getattr(settings, "CLI_DISABLE_ONBOARDING", False):
        return False
    if os.environ.get("DISABLE_ONBOARDING", "").lower() in ("true", "1", "yes"):
        return False
    if os.environ.get("NO_ONBOARDING", "").lower() in ("true", "1", "yes"):
        return False

    # 2. Check persistent database state in system_settings table
    try:
        from app.repositories import SystemSettingRepository
        val = SystemSettingRepository.get("setup_completed", default="false", db=db)
        if val and val.lower() in ("true", "1", "yes"):
            return False
    except Exception:
        pass

    # By default, initial setup/onboarding is needed until explicitly completed in the UI or skipped
    return True

@router.get("", response_model=ConfigResponse)
@router.get("/", response_model=ConfigResponse)
async def get_config(db: Session = Depends(get_db)):
    """Get current configuration"""
    from app.repositories import SystemSettingRepository
    is_setup_done = (SystemSettingRepository.get("setup_completed", default="false", db=db) or "false").lower() in ("true", "1", "yes")

    return ConfigResponse(
        base_download_path=settings.BASE_DOWNLOAD_PATH,
        temp_download_path=settings.TEMP_DOWNLOAD_PATH,
        audio_extract_mode=settings.AUDIO_EXTRACT_MODE,
        max_extraction_workers=settings.MAX_CONCURRENT_EXTRACTIONS,
        max_concurrent_downloads=settings.MAX_CONCURRENT_DOWNLOADS,
        batch_size=settings.BATCH_SIZE,
        sleep_interval_min=getattr(settings, "SLEEP_INTERVAL_MIN", 1),
        sleep_interval_max=getattr(settings, "SLEEP_INTERVAL_MAX", 5),
        concurrent_fragments=getattr(settings, "CONCURRENT_FRAGMENTS", 2),
        enable_daily_auto_refresh=getattr(settings, "ENABLE_DAILY_AUTO_REFRESH", True),
        daily_refresh_time=getattr(settings, "DAILY_REFRESH_TIME", "04:00") or "04:00",
        daily_refresh_timezone=getattr(settings, "DAILY_REFRESH_TIMEZONE", "Asia/Kolkata") or "Asia/Kolkata",
        daily_refresh_mode=getattr(settings, "DAILY_REFRESH_MODE", "scheduled") or "scheduled",
        daily_refresh_interval_minutes=getattr(settings, "DAILY_REFRESH_INTERVAL_MINUTES", 1440) or 1440,
        enable_git_metadata_sync=getattr(settings, "ENABLE_GIT_METADATA_SYNC", True),
        enable_git_remote_push=getattr(settings, "ENABLE_GIT_REMOTE_PUSH", False),
        git_remote_url=getattr(settings, "GIT_REMOTE_URL", None),
        git_auth_token=getattr(settings, "GIT_AUTH_TOKEN", None),
        git_branch=getattr(settings, "GIT_BRANCH", "main") or "main",
        git_user_name=SystemSettingRepository.get("git_user_name", default=getattr(settings, "GIT_USER_NAME", "YouTube Playlist Manager"), db=db),
        git_user_email=SystemSettingRepository.get("git_user_email", default=getattr(settings, "GIT_USER_EMAIL", "yt-manager@homelab.local"), db=db),
        cookies_file=settings.COOKIES_FILE,
        use_browser_cookies=settings.USE_BROWSER_COOKIES,
        browser_name=settings.BROWSER_NAME,
        cookies_auth_mode=getattr(settings, "COOKIES_AUTH_MODE", "cookies_txt"),
        enable_stream_integrity_check=getattr(settings, "ENABLE_STREAM_INTEGRITY_CHECK", False),
        flaresolverr_url=getattr(settings, "FLARESOLVERR_URL", None),
        enable_auto_discovery=getattr(settings, "ENABLE_AUTO_DISCOVERY", True),
        auto_discovery_interval_minutes=getattr(settings, "AUTO_DISCOVERY_INTERVAL_MINUTES", 60),
        setup_completed=is_setup_done,
        needs_setup=_check_needs_setup(db=db),
        adhoc_download_path=getattr(settings, "ADHOC_DOWNLOAD_PATH", None),
        use_custom_adhoc_path=getattr(settings, "USE_CUSTOM_ADHOC_PATH", False),
        effective_adhoc_download_path=settings.get_adhoc_download_path(),
        excluded_dirs=getattr(settings, "EXCLUDED_DIRS", "") or "",
        rename_folder_on_link=getattr(settings, "RENAME_FOLDER_ON_LINK", False),
    )

def _save_to_env(config: ConfigUpdate):
    """Save configuration to active .env file"""
    env_path = settings.get_env_file_path()
    os.makedirs(env_path.parent, exist_ok=True)
    
    # Read existing .env content
    env_content = {}
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_content[key.strip()] = value.strip()
    
    # Update with new values
    if config.base_download_path is not None:
        env_content['BASE_DOWNLOAD_PATH'] = config.base_download_path
    if config.temp_download_path is not None:
        env_content['TEMP_DOWNLOAD_PATH'] = config.temp_download_path if config.temp_download_path else ''
    if config.audio_extract_mode is not None:
        env_content['AUDIO_EXTRACT_MODE'] = config.audio_extract_mode
    if config.max_extraction_workers is not None:
        env_content['MAX_CONCURRENT_EXTRACTIONS'] = str(config.max_extraction_workers)
    if config.max_concurrent_downloads is not None:
        env_content['MAX_CONCURRENT_DOWNLOADS'] = str(config.max_concurrent_downloads)
    if config.batch_size is not None:
        env_content['BATCH_SIZE'] = str(config.batch_size)
    if config.sleep_interval_min is not None:
        env_content['SLEEP_INTERVAL_MIN'] = str(config.sleep_interval_min)
    if config.sleep_interval_max is not None:
        env_content['SLEEP_INTERVAL_MAX'] = str(config.sleep_interval_max)
    if config.concurrent_fragments is not None:
        env_content['CONCURRENT_FRAGMENTS'] = str(config.concurrent_fragments)
    if config.enable_daily_auto_refresh is not None:
        env_content['ENABLE_DAILY_AUTO_REFRESH'] = 'true' if config.enable_daily_auto_refresh else 'false'
    if config.daily_refresh_time is not None:
        env_content['DAILY_REFRESH_TIME'] = config.daily_refresh_time
    if config.daily_refresh_timezone is not None:
        env_content['DAILY_REFRESH_TIMEZONE'] = config.daily_refresh_timezone
    if config.daily_refresh_mode is not None:
        env_content['DAILY_REFRESH_MODE'] = config.daily_refresh_mode
    if config.daily_refresh_interval_minutes is not None:
        env_content['DAILY_REFRESH_INTERVAL_MINUTES'] = str(config.daily_refresh_interval_minutes)
    if config.enable_git_metadata_sync is not None:
        env_content['ENABLE_GIT_METADATA_SYNC'] = 'true' if config.enable_git_metadata_sync else 'false'
    if config.enable_git_remote_push is not None:
        env_content['ENABLE_GIT_REMOTE_PUSH'] = 'true' if config.enable_git_remote_push else 'false'
    if config.git_remote_url is not None:
        env_content['GIT_REMOTE_URL'] = config.git_remote_url.strip() if config.git_remote_url else ''
    if config.git_auth_token is not None:
        env_content['GIT_AUTH_TOKEN'] = config.git_auth_token.strip() if config.git_auth_token else ''
    if config.git_branch is not None:
        env_content['GIT_BRANCH'] = config.git_branch
    if config.git_user_name is not None:
        env_content['GIT_USER_NAME'] = config.git_user_name
    if config.git_user_email is not None:
        env_content['GIT_USER_EMAIL'] = config.git_user_email
    if config.cookies_file is not None:
        env_content['COOKIES_FILE'] = config.cookies_file if config.cookies_file else ''
    if config.use_browser_cookies is not None:
        env_content['USE_BROWSER_COOKIES'] = 'true' if config.use_browser_cookies else 'false'
    if config.browser_name is not None:
        env_content['BROWSER_NAME'] = config.browser_name
    if config.cookies_auth_mode is not None:
        env_content['COOKIES_AUTH_MODE'] = config.cookies_auth_mode
    if config.enable_stream_integrity_check is not None:
        env_content['ENABLE_STREAM_INTEGRITY_CHECK'] = 'true' if config.enable_stream_integrity_check else 'false'
    if config.flaresolverr_url is not None:
        env_content['FLARESOLVERR_URL'] = config.flaresolverr_url if config.flaresolverr_url else ''
    if config.enable_auto_discovery is not None:
        env_content['ENABLE_AUTO_DISCOVERY'] = 'true' if config.enable_auto_discovery else 'false'
    if config.auto_discovery_interval_minutes is not None:
        env_content['AUTO_DISCOVERY_INTERVAL_MINUTES'] = str(config.auto_discovery_interval_minutes)
    if config.adhoc_download_path is not None:
        env_content['ADHOC_DOWNLOAD_PATH'] = config.adhoc_download_path if config.adhoc_download_path else ''
    if config.use_custom_adhoc_path is not None:
        env_content['USE_CUSTOM_ADHOC_PATH'] = 'true' if config.use_custom_adhoc_path else 'false'
    if config.excluded_dirs is not None:
        env_content['EXCLUDED_DIRS'] = config.excluded_dirs if config.excluded_dirs else ''
    if config.rename_folder_on_link is not None:
        env_content['RENAME_FOLDER_ON_LINK'] = 'true' if config.rename_folder_on_link else 'false'
    
    # Write back to .env
    with open(env_path, 'w', encoding='utf-8') as f:
        f.write("# YouTube Playlist Manager Configuration\n")
        f.write("# Generated by web interface\n\n")
        for key, value in env_content.items():
            f.write(f"{key}={value}\n")

@router.put("", response_model=ConfigResponse)
@router.put("/", response_model=ConfigResponse)
async def update_config(config: ConfigUpdate, db: Session = Depends(get_db)):
    """Update configuration and persist to .env file and database"""
    
    # Update in-memory settings
    if config.base_download_path is not None:
        settings.BASE_DOWNLOAD_PATH = config.base_download_path
    if config.temp_download_path is not None:
        settings.TEMP_DOWNLOAD_PATH = config.temp_download_path if config.temp_download_path else None
    if config.audio_extract_mode is not None:
        settings.AUDIO_EXTRACT_MODE = config.audio_extract_mode
    if config.max_extraction_workers is not None:
        settings.MAX_CONCURRENT_EXTRACTIONS = config.max_extraction_workers
    if config.max_concurrent_downloads is not None:
        settings.MAX_CONCURRENT_DOWNLOADS = config.max_concurrent_downloads
    if config.batch_size is not None:
        settings.BATCH_SIZE = config.batch_size
    if config.sleep_interval_min is not None:
        settings.SLEEP_INTERVAL_MIN = config.sleep_interval_min
    if config.sleep_interval_max is not None:
        settings.SLEEP_INTERVAL_MAX = config.sleep_interval_max
    if config.concurrent_fragments is not None:
        settings.CONCURRENT_FRAGMENTS = config.concurrent_fragments
    if config.enable_daily_auto_refresh is not None:
        settings.ENABLE_DAILY_AUTO_REFRESH = config.enable_daily_auto_refresh
    if config.daily_refresh_time is not None:
        settings.DAILY_REFRESH_TIME = config.daily_refresh_time
    if config.daily_refresh_timezone is not None:
        settings.DAILY_REFRESH_TIMEZONE = config.daily_refresh_timezone
    if config.daily_refresh_mode is not None:
        settings.DAILY_REFRESH_MODE = config.daily_refresh_mode
    if config.daily_refresh_interval_minutes is not None:
        settings.DAILY_REFRESH_INTERVAL_MINUTES = config.daily_refresh_interval_minutes
    # Enforce Git Remote Push verification if remote push is being enabled or saved as active
    target_remote_push = config.enable_git_remote_push if config.enable_git_remote_push is not None else getattr(settings, "ENABLE_GIT_REMOTE_PUSH", False)
    target_remote_url = (config.git_remote_url.strip() if config.git_remote_url is not None else (getattr(settings, "GIT_REMOTE_URL", None) or "")).strip()
    target_auth_token = (config.git_auth_token.strip() if config.git_auth_token is not None else (getattr(settings, "GIT_AUTH_TOKEN", None) or "")).strip()
    target_branch = (config.git_branch.strip() if config.git_branch is not None else (getattr(settings, "GIT_BRANCH", "main") or "main")).strip()

    if target_remote_push:
        if not target_remote_url:
            raise HTTPException(status_code=400, detail="Remote Git repository URL is required to enable remote push.")
        from app.utils.git_sync import test_git_connection_sync
        ok, err_msg = test_git_connection_sync(target_remote_url, target_auth_token, target_branch)
        if not ok:
            raise HTTPException(status_code=400, detail=f"Cannot enable remote push: {err_msg}")

    if config.enable_git_metadata_sync is not None:
        settings.ENABLE_GIT_METADATA_SYNC = config.enable_git_metadata_sync
    if config.enable_git_remote_push is not None:
        settings.ENABLE_GIT_REMOTE_PUSH = config.enable_git_remote_push
    if config.git_remote_url is not None:
        settings.GIT_REMOTE_URL = config.git_remote_url.strip() if config.git_remote_url.strip() else None
    if config.git_auth_token is not None:
        settings.GIT_AUTH_TOKEN = config.git_auth_token.strip() if config.git_auth_token.strip() else None
    if config.git_branch is not None:
        settings.GIT_BRANCH = config.git_branch
    if config.git_user_name is not None:
        settings.GIT_USER_NAME = config.git_user_name
        from app.models.database import set_system_setting
        set_system_setting("git_user_name", config.git_user_name, db=db)
    if config.git_user_email is not None:
        settings.GIT_USER_EMAIL = config.git_user_email
        from app.models.database import set_system_setting
        set_system_setting("git_user_email", config.git_user_email, db=db)
    if config.cookies_file is not None:
        settings.COOKIES_FILE = config.cookies_file.strip() if config.cookies_file.strip() else None
    if config.use_browser_cookies is not None:
        settings.USE_BROWSER_COOKIES = config.use_browser_cookies
    if config.browser_name is not None:
        settings.BROWSER_NAME = config.browser_name
    if config.cookies_auth_mode is not None:
        settings.COOKIES_AUTH_MODE = config.cookies_auth_mode
    if config.enable_stream_integrity_check is not None:
        settings.ENABLE_STREAM_INTEGRITY_CHECK = config.enable_stream_integrity_check
    if config.flaresolverr_url is not None:
        settings.FLARESOLVERR_URL = config.flaresolverr_url
    if config.enable_auto_discovery is not None:
        settings.ENABLE_AUTO_DISCOVERY = config.enable_auto_discovery
    if config.auto_discovery_interval_minutes is not None:
        settings.AUTO_DISCOVERY_INTERVAL_MINUTES = config.auto_discovery_interval_minutes
    if config.adhoc_download_path is not None:
        settings.ADHOC_DOWNLOAD_PATH = config.adhoc_download_path
    if config.use_custom_adhoc_path is not None:
        settings.USE_CUSTOM_ADHOC_PATH = config.use_custom_adhoc_path
    if config.excluded_dirs is not None:
        settings.EXCLUDED_DIRS = config.excluded_dirs
    if config.rename_folder_on_link is not None:
        settings.RENAME_FOLDER_ON_LINK = config.rename_folder_on_link
    if config.setup_completed is not None:
        from app.models.database import set_system_setting
        set_system_setting("setup_completed", "true" if config.setup_completed else "false", db=db)
    
    # Synchronize or clean up local origin remote
    from app.utils.git_sync import sync_git_remote_origin
    sync_git_remote_origin(
        settings.BASE_DOWNLOAD_PATH,
        settings.GIT_REMOTE_URL,
        getattr(settings, "ENABLE_GIT_REMOTE_PUSH", False)
    )

    # Persist to .env file
    _save_to_env(config)

    from app.repositories import SystemSettingRepository
    is_setup_done = (SystemSettingRepository.get("setup_completed", default="false", db=db) or "false").lower() in ("true", "1", "yes")
    
    return ConfigResponse(
        base_download_path=settings.BASE_DOWNLOAD_PATH,
        temp_download_path=settings.TEMP_DOWNLOAD_PATH,
        audio_extract_mode=settings.AUDIO_EXTRACT_MODE,
        max_extraction_workers=settings.MAX_CONCURRENT_EXTRACTIONS,
        max_concurrent_downloads=settings.MAX_CONCURRENT_DOWNLOADS,
        batch_size=settings.BATCH_SIZE,
        sleep_interval_min=getattr(settings, "SLEEP_INTERVAL_MIN", 1),
        sleep_interval_max=getattr(settings, "SLEEP_INTERVAL_MAX", 5),
        concurrent_fragments=getattr(settings, "CONCURRENT_FRAGMENTS", 2),
        enable_daily_auto_refresh=getattr(settings, "ENABLE_DAILY_AUTO_REFRESH", True),
        daily_refresh_time=getattr(settings, "DAILY_REFRESH_TIME", "04:00") or "04:00",
        daily_refresh_timezone=getattr(settings, "DAILY_REFRESH_TIMEZONE", "Asia/Kolkata") or "Asia/Kolkata",
        daily_refresh_mode=getattr(settings, "DAILY_REFRESH_MODE", "scheduled") or "scheduled",
        daily_refresh_interval_minutes=getattr(settings, "DAILY_REFRESH_INTERVAL_MINUTES", 1440) or 1440,
        enable_git_metadata_sync=getattr(settings, "ENABLE_GIT_METADATA_SYNC", True),
        enable_git_remote_push=getattr(settings, "ENABLE_GIT_REMOTE_PUSH", False),
        git_remote_url=getattr(settings, "GIT_REMOTE_URL", None),
        git_auth_token=getattr(settings, "GIT_AUTH_TOKEN", None),
        git_branch=getattr(settings, "GIT_BRANCH", "main") or "main",
        git_user_name=SystemSettingRepository.get("git_user_name", default=getattr(settings, "GIT_USER_NAME", "YouTube Playlist Manager"), db=db),
        git_user_email=SystemSettingRepository.get("git_user_email", default=getattr(settings, "GIT_USER_EMAIL", "yt-manager@homelab.local"), db=db),
        cookies_file=settings.COOKIES_FILE,
        use_browser_cookies=settings.USE_BROWSER_COOKIES,
        browser_name=settings.BROWSER_NAME,
        cookies_auth_mode=getattr(settings, "COOKIES_AUTH_MODE", "cookies_txt"),
        enable_stream_integrity_check=getattr(settings, "ENABLE_STREAM_INTEGRITY_CHECK", False),
        flaresolverr_url=getattr(settings, "FLARESOLVERR_URL", None),
        enable_auto_discovery=getattr(settings, "ENABLE_AUTO_DISCOVERY", True),
        auto_discovery_interval_minutes=getattr(settings, "AUTO_DISCOVERY_INTERVAL_MINUTES", 60),
        setup_completed=is_setup_done,
        needs_setup=_check_needs_setup(db=db),
        adhoc_download_path=getattr(settings, "ADHOC_DOWNLOAD_PATH", None),
        use_custom_adhoc_path=getattr(settings, "USE_CUSTOM_ADHOC_PATH", False),
        effective_adhoc_download_path=settings.get_adhoc_download_path(),
        excluded_dirs=getattr(settings, "EXCLUDED_DIRS", "") or "",
        rename_folder_on_link=getattr(settings, "RENAME_FOLDER_ON_LINK", False),
    )

class YtDlpVersionResponse(BaseModel):
    version: str

class YtDlpUpdateResponse(BaseModel):
    success: bool
    message: str
    old_version: str
    new_version: str
    output: str

class FlareSolverrTestRequest(BaseModel):
    url: Optional[str] = None

class FlareSolverrTestResponse(BaseModel):
    success: bool
    message: str
    version: Optional[str] = None
    response_time_ms: Optional[float] = None

@router.get("/ytdlp-version", response_model=YtDlpVersionResponse)
async def get_ytdlp_version():
    """Get current yt-dlp version"""
    import yt_dlp.version
    return YtDlpVersionResponse(version=yt_dlp.version.__version__)

@router.post("/update-ytdlp", response_model=YtDlpUpdateResponse)
async def update_ytdlp():
    """Update yt-dlp package using pip"""
    import sys
    import subprocess
    import yt_dlp.version
    import importlib
    
    old_version = yt_dlp.version.__version__
    
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        try:
            importlib.reload(yt_dlp.version)
            new_version = yt_dlp.version.__version__
        except Exception:
            new_version = old_version
            
        if proc.returncode == 0:
            return YtDlpUpdateResponse(
                success=True,
                message=f"yt-dlp updated successfully: {old_version} -> {new_version}",
                old_version=old_version,
                new_version=new_version,
                output=proc.stdout
            )
        else:
            return YtDlpUpdateResponse(
                success=False,
                message=f"Failed to update yt-dlp: {proc.stderr}",
                old_version=old_version,
                new_version=old_version,
                output=proc.stderr
            )
    except Exception as e:
        return YtDlpUpdateResponse(
            success=False,
            message=f"Error updating yt-dlp: {str(e)}",
            old_version=old_version,
            new_version=old_version,
            output=str(e)
        )

@router.post("/test-flaresolverr", response_model=FlareSolverrTestResponse)
async def test_flaresolverr(request: Optional[FlareSolverrTestRequest] = None):
    """Test connectivity to FlareSolverr container"""
    import urllib.request
    import json
    import time
    
    target_url = (request.url if request and request.url else getattr(settings, "FLARESOLVERR_URL", None)) or "http://localhost:8191/v1"
    target_url = target_url.rstrip("/")
    if not target_url.endswith("/v1"):
        endpoint = f"{target_url}/v1"
    else:
        endpoint = target_url
        
    start_time = time.time()
    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps({"cmd": "sessions.list"}).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            resp_time = round((time.time() - start_time) * 1000, 2)
            data = json.loads(response.read().decode('utf-8'))
            version = data.get("version", "Unknown")
            return FlareSolverrTestResponse(
                success=True,
                message=f"Connected to FlareSolverr successfully! (v{version})",
                version=version,
                response_time_ms=resp_time
            )
    except Exception as e:
        return FlareSolverrTestResponse(
            success=False,
            message=f"Failed to connect to FlareSolverr at {endpoint}: {str(e)}"
        )

class GitTestRequest(BaseModel):
    git_remote_url: Optional[str] = None
    git_auth_token: Optional[str] = None
    git_branch: Optional[str] = None

class GitSyncTestResponse(BaseModel):
    success: bool
    message: str

@router.post("/test-git-sync", response_model=GitSyncTestResponse)
async def test_git_sync(body: Optional[GitTestRequest] = None):
    """Test Git repository initialization and remote push/connectivity using read-only git ls-remote"""
    from app.utils.git_sync import ensure_git_repo, test_git_connection_sync
    
    base_path = settings.BASE_DOWNLOAD_PATH
    if not ensure_git_repo(base_path):
        return GitSyncTestResponse(
            success=False,
            message=f"Failed to initialize local Git repository in {base_path}"
        )

    remote_url = (body.git_remote_url if (body and body.git_remote_url is not None) else getattr(settings, "GIT_REMOTE_URL", None))
    if not remote_url or not remote_url.strip():
        return GitSyncTestResponse(
            success=True,
            message="Local Git repository is initialized and ready. Enter a remote URL to test remote connectivity."
        )

    auth_token = (body.git_auth_token if (body and body.git_auth_token is not None) else getattr(settings, "GIT_AUTH_TOKEN", None))
    branch = (body.git_branch if (body and body.git_branch is not None) else getattr(settings, "GIT_BRANCH", "main")) or "main"

    success, msg = test_git_connection_sync(remote_url, auth_token, branch)
    return GitSyncTestResponse(success=success, message=msg)

class SchedulerStatusResponse(BaseModel):
    is_scanning: bool
    current_playlist: Optional[str] = None
    completed_count: int = 0
    total_count: int = 0
    last_scan_at: Optional[str] = None
    next_scan_at: Optional[str] = None
    last_scan_summary: Optional[str] = None

@router.get("/scheduler-status", response_model=SchedulerStatusResponse)
async def get_scheduler_status():
    """Get current daily background scheduler execution state and progress"""
    from app.services.scheduler import get_scheduler_state
    return SchedulerStatusResponse(**get_scheduler_state())

# ============================================================================
# COOKIES MANAGEMENT & EXPIRATION DETECTION
# ============================================================================

class CookieStatusResponse(BaseModel):
    is_installed: bool
    status: str  # "valid", "expiring_soon", "expired", "invalid", "not_installed"
    status_message: str
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    last_modified: Optional[str] = None
    earliest_expiration: Optional[str] = None
    days_remaining: Optional[int] = None
    auth_cookies_found: List[str] = []

def _parse_cookie_file_status(file_path: Optional[str]) -> CookieStatusResponse:
    """Parse Netscape format cookies file and evaluate expiration/staleness"""
    import time
    from datetime import datetime
    
    if not file_path or not os.path.isfile(file_path):
        return CookieStatusResponse(
            is_installed=False,
            status="not_installed",
            status_message="No cookies file installed (using mobile client emulation)",
            auth_cookies_found=[]
        )
        
    try:
        stat = os.stat(file_path)
        file_size = stat.st_size
        last_mod = datetime.utcfromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        
        auth_cookie_names = {"LOGIN_INFO", "__Secure-1PSID", "__Secure-3PSID", "SID", "SAPISID", "SSID", "HSID"}
        found_auth_cookies = set()
        expiration_timestamps = []
        
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split('\t')
                if len(parts) >= 7:
                    cookie_name = parts[5].strip()
                    try:
                        expiry = int(parts[4].strip())
                        if cookie_name in auth_cookie_names:
                            found_auth_cookies.add(cookie_name)
                            if expiry > 0:  # Exclude session-only cookies
                                expiration_timestamps.append(expiry)
                    except ValueError:
                        pass
                        
        if not found_auth_cookies:
            return CookieStatusResponse(
                is_installed=True,
                status="invalid",
                status_message="Cookies file is installed, but no YouTube session login cookies were found",
                file_path=file_path,
                file_size_bytes=file_size,
                last_modified=last_mod,
                auth_cookies_found=[]
            )
            
        current_time = time.time()
        if not expiration_timestamps:
            return CookieStatusResponse(
                is_installed=True,
                status="valid",
                status_message="Cookies Active (Session tokens detected)",
                file_path=file_path,
                file_size_bytes=file_size,
                last_modified=last_mod,
                auth_cookies_found=sorted(list(found_auth_cookies))
            )
            
        earliest_expiry = min(expiration_timestamps)
        earliest_dt = datetime.utcfromtimestamp(earliest_expiry)
        earliest_str = earliest_dt.strftime("%Y-%m-%d")
        seconds_left = earliest_expiry - current_time
        days_left = int(seconds_left // 86400)
        
        if seconds_left < 0:
            return CookieStatusResponse(
                is_installed=True,
                status="expired",
                status_message=f"Cookies Expired on {earliest_str} ({abs(days_left)} days ago). Please upload a fresh cookies.txt.",
                file_path=file_path,
                file_size_bytes=file_size,
                last_modified=last_mod,
                earliest_expiration=earliest_str,
                days_remaining=days_left,
                auth_cookies_found=sorted(list(found_auth_cookies))
            )
        elif days_left <= 7:
            return CookieStatusResponse(
                is_installed=True,
                status="expiring_soon",
                status_message=f"Cookies Expiring Soon (in {days_left} day{'s' if days_left != 1 else ''} on {earliest_str}).",
                file_path=file_path,
                file_size_bytes=file_size,
                last_modified=last_mod,
                earliest_expiration=earliest_str,
                days_remaining=days_left,
                auth_cookies_found=sorted(list(found_auth_cookies))
            )
        else:
            return CookieStatusResponse(
                is_installed=True,
                status="valid",
                status_message=f"Cookies Active & Valid (Expires in {days_left} days on {earliest_str})",
                file_path=file_path,
                file_size_bytes=file_size,
                last_modified=last_mod,
                earliest_expiration=earliest_str,
                days_remaining=days_left,
                auth_cookies_found=sorted(list(found_auth_cookies))
            )
            
    except Exception as e:
        return CookieStatusResponse(
            is_installed=True,
            status="invalid",
            status_message=f"Error reading cookies file: {str(e)}",
            file_path=file_path,
            auth_cookies_found=[]
        )

@router.get("/cookies-status", response_model=CookieStatusResponse)
async def get_cookies_status():
    """Get current cookie status, staleness, and expiration date"""
    return _parse_cookie_file_status(settings.COOKIES_FILE)

@router.post("/upload-cookies", response_model=CookieStatusResponse)
async def upload_cookies(file: UploadFile = File(...)):
    """Upload a new cookies.txt file directly via web UI"""
    data_dir = Path(__file__).parent.parent.parent.parent / "data"
    if not data_dir.exists():
        data_dir = Path(settings.BASE_DOWNLOAD_PATH)
    os.makedirs(data_dir, exist_ok=True)
    
    target_path = data_dir / "cookies.txt"
    
    content = await file.read()
    with open(target_path, "wb") as f:
        f.write(content)
        
    target_path_str = str(target_path.resolve())
    settings.COOKIES_FILE = target_path_str
    
    update_data = ConfigUpdate(cookies_file=target_path_str)
    _save_to_env(update_data)
    
    return _parse_cookie_file_status(target_path_str)

@router.delete("/cookies", response_model=CookieStatusResponse)
async def delete_cookies():
    """Remove installed cookies file and clear setting"""
    if settings.COOKIES_FILE and os.path.exists(settings.COOKIES_FILE):
        try:
            os.remove(settings.COOKIES_FILE)
        except Exception:
            pass
            
    settings.COOKIES_FILE = None
    update_data = ConfigUpdate(cookies_file="")
    _save_to_env(update_data)
    
    return _parse_cookie_file_status(None)


class OnboardingScanRequest(BaseModel):
    base_path: Optional[str] = None


class OnboardingConfirmRequest(BaseModel):
    base_path: Optional[str] = None
    items: Optional[List[dict]] = None


@router.post("/onboarding/scan")
async def scan_onboarding_library(payload: OnboardingScanRequest = OnboardingScanRequest()):
    """Scan directory for existing playlists and tracks preview"""
    from app.services.onboarding_service import scan_download_directory
    target = payload.base_path or settings.BASE_DOWNLOAD_PATH
    return scan_download_directory(target)


@router.post("/onboarding/confirm")
async def confirm_onboarding_ingest(
    payload: OnboardingConfirmRequest = OnboardingConfirmRequest(),
    db: Session = Depends(get_db)
):
    """Ingest discovered playlists and mark initial setup completed"""
    from app.services.onboarding_service import ingest_discovered_library
    from app.models.database import set_system_setting
    target = payload.base_path or settings.BASE_DOWNLOAD_PATH
    res = ingest_discovered_library(discovered_items=payload.items, base_path=target, db=db)
    set_system_setting("setup_completed", "true", db=db)
    return res


class BatchLinkItem(BaseModel):
    folder_path: Optional[str] = None
    folder_name: Optional[str] = None
    playlist_url: str
    rename_folder: Optional[bool] = None


class BatchLinkRequest(BaseModel):
    items: List[BatchLinkItem]
    global_rename: Optional[bool] = None


class BatchExcludeRequest(BaseModel):
    folder_names: List[str]
    reason: Optional[str] = "user_excluded"


class RestoreExcludedRequest(BaseModel):
    folder_name: str


@router.get("/unmanaged-folders")
async def get_unmanaged_folders(db: Session = Depends(get_db)):
    """Scan base download directory and return unmanaged and excluded folders"""
    from app.services.onboarding_service import scan_download_directory
    from app.models.database import list_folder_statuses
    scan_res = scan_download_directory(settings.BASE_DOWNLOAD_PATH)
    
    excluded_list = [
        {
            "folder_name": fs.folder_name,
            "reason": fs.reason or "user_excluded",
            "created_at": fs.created_at.isoformat() if fs.created_at else None,
        }
        for fs in list_folder_statuses(status="excluded", db=db)
    ]
    
    return {
        "base_path": settings.BASE_DOWNLOAD_PATH,
        "unmanaged_folders_count": scan_res.get("unmanaged_folders_count", 0),
        "unmanaged_folders": scan_res.get("unmanaged_folders", []),
        "excluded_folders_count": len(excluded_list),
        "excluded_folders": excluded_list
    }


@router.post("/batch-link-unmanaged-folders")
async def batch_link_folders(payload: BatchLinkRequest, db: Session = Depends(get_db)):
    """Batch link unmanaged folders to YouTube playlists"""
    from app.services.onboarding_service import batch_link_unmanaged_folders
    raw_items = [item.dict() for item in payload.items]
    return batch_link_unmanaged_folders(items=raw_items, global_rename=payload.global_rename, db=db)


@router.post("/batch-exclude-folders")
async def batch_exclude_folders(payload: BatchExcludeRequest, db: Session = Depends(get_db)):
    """Add folders to excluded status (persisted in database folder_status table)"""
    from app.models.database import set_folder_status
    logger.info(f"[Unmanaged Exclude] Received request to exclude folders: {payload.folder_names}")
    reason = payload.reason or "user_excluded"
    for f in payload.folder_names:
        cleaned = f.strip()
        if cleaned:
            set_folder_status(folder_name=cleaned, status="excluded", reason=reason, db=db)
    
    # Also sync in-memory settings.EXCLUDED_DIRS for backwards compatibility
    current_excluded = set(x.strip().lower() for x in (getattr(settings, "EXCLUDED_DIRS", "") or "").split(",") if x.strip())
    for f in payload.folder_names:
        cleaned = f.strip().lower()
        if cleaned:
            current_excluded.add(cleaned)
    new_excluded_str = ",".join(sorted(current_excluded))
    settings.EXCLUDED_DIRS = new_excluded_str
    try:
        _save_to_env(ConfigUpdate(excluded_dirs=new_excluded_str))
    except Exception as env_err:
        logger.debug(f"[Unmanaged Exclude] Note syncing .env: {env_err}")
    
    logger.info(f"[Unmanaged Exclude] Successfully excluded {len(payload.folder_names)} folder(s).")
    return {
        "success": True,
        "excluded_folders": payload.folder_names
    }


@router.post("/restore-excluded-folder")
async def restore_excluded_folder(payload: RestoreExcludedRequest, db: Session = Depends(get_db)):
    """Remove a folder from excluded status, restoring it to unmanaged"""
    from app.repositories import FolderStatusRepository
    folder_name = payload.folder_name.strip()
    logger.info(f"[Unmanaged Exclude] Restoring excluded folder: {folder_name}")
    
    # 1. Remove from database FolderStatus
    FolderStatusRepository.remove(folder_name, db=db)
    for fs in FolderStatusRepository.list(status="excluded", db=db):
        if fs.folder_name.lower() == folder_name.lower():
            FolderStatusRepository.remove(fs.folder_name, db=db)
            
    # 2. Sync in-memory settings.EXCLUDED_DIRS
    current_excluded = [x.strip() for x in (getattr(settings, "EXCLUDED_DIRS", "") or "").split(",") if x.strip()]
    updated_excluded = [x for x in current_excluded if x.lower() != folder_name.lower()]
    if len(current_excluded) != len(updated_excluded):
        new_str = ",".join(updated_excluded)
        settings.EXCLUDED_DIRS = new_str
        try:
            _save_to_env(ConfigUpdate(excluded_dirs=new_str))
        except Exception as env_err:
            logger.debug(f"[Unmanaged Exclude] Note syncing .env: {env_err}")
            
    return {
        "success": True,
        "restored_folder": folder_name
    }




