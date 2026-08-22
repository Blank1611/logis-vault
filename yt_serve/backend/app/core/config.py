"""
Application configuration
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os
from pathlib import Path

# Get the backend directory (where .env should be)
BACKEND_DIR = Path(__file__).parent.parent.parent
ENV_FILE = BACKEND_DIR / ".env"

class Settings(BaseSettings):
    """Application settings"""
    
    # API Settings
    API_V1_STR: str = "/api"
    PROJECT_NAME: str = "YouTube Playlist Manager"
    
    # Database
    # Default to backend directory, but can be overridden in .env
    DATABASE_PATH: str = "yt_manager.db"  # Relative to backend directory
    
    # Download settings
    BASE_DOWNLOAD_PATH: str = "downloads"
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
        env_file = str(ENV_FILE)
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Debug: Print loaded configuration
        print(f"[CONFIG] Loaded settings:")
        print(f"  BASE_DOWNLOAD_PATH: {self.BASE_DOWNLOAD_PATH}")
        print(f"  .env file location: {ENV_FILE}")
        print(f"  .env exists: {ENV_FILE.exists()}")
        
        # Create download path if it doesn't exist and is configured
        if self.BASE_DOWNLOAD_PATH and self.BASE_DOWNLOAD_PATH != "downloads":
            try:
                os.makedirs(self.BASE_DOWNLOAD_PATH, exist_ok=True)
                print(f"  Download path ready: {self.BASE_DOWNLOAD_PATH}")
            except Exception as e:
                print(f"  Warning: Could not create download path {self.BASE_DOWNLOAD_PATH}: {e}")

settings = Settings()
