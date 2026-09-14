"""
Centralized yt-dlp configuration options factory.

Generates specialized, robust options dictionaries for:
- "info": Fast shallow playlist metadata extraction (no downloads).
- "download": Full video stream downloading with exponential backoff, anti-rate-limit jitter, and SSD buffering.
- "extract": Direct single-audio extraction.
"""

import os
from typing import Optional, Dict, Any, List
from app.core.config import settings
from app.core.logging_engine import YTDLPLoggerAdapter


def build_ytdlp_options(
    mode: str = "download",
    playlist_folder: Optional[str] = None,
    archive_file: Optional[str] = None,
    progress_hooks: Optional[List[Any]] = None,
    extra_opts: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build a customized yt-dlp options dictionary based on the requested mode.

    Args:
        mode: "info", "download", or "extract"
        playlist_folder: Destination directory on disk
        archive_file: Path to download archive file (if managed by yt-dlp)
        progress_hooks: List of hook callbacks for progress tracking
        extra_opts: Custom overrides or additions

    Returns:
        dict: Complete yt-dlp options ready to pass to YoutubeDL()
    """
    opts: Dict[str, Any] = {}

    # Attach logger adapter so yt-dlp messages conform to standard log format and sinks
    opts["logger"] = YTDLPLoggerAdapter()

    # 1. Base network & client emulation (applies to all modes)
    opts["extractor_args"] = {
        "youtube": {
            "player_client": ["android", "ios", "web_creator", "mweb", "web"],
            "player_skip": ["configs", "webpage_signature"]
        }
    }

    # 2. Authentication: Browser profile extraction vs cookies.txt file vs none
    auth_mode = getattr(settings, "COOKIES_AUTH_MODE", "cookies_txt")
    use_browser_cookies = getattr(settings, "USE_BROWSER_COOKIES", False)
    browser_name = getattr(settings, "BROWSER_NAME", "chrome")
    cookies_file = getattr(settings, "COOKIES_FILE", None)

    if auth_mode == "browser" or (use_browser_cookies and auth_mode != "none"):
        if browser_name:
            opts["cookies_from_browser"] = (browser_name,)
    elif auth_mode == "cookies_txt" or (not use_browser_cookies and auth_mode != "none"):
        if cookies_file and os.path.isfile(cookies_file):
            opts["cookiefile"] = cookies_file

    # 3. User-Agent
    user_agent = getattr(settings, "USER_AGENT", None)
    if user_agent:
        opts["user_agent"] = user_agent

    # 4. Mode-specific configurations
    if mode == "info":
        opts.update({
            "quiet": True,
            "skip_download": True,
            "extract_flat": "in_playlist",
            "no_warnings": True,
        })

    elif mode in ["download", "extract"]:
        # Standard format selection
        if mode == "download":
            opts.update({
                "format": "bestvideo+bestaudio/best",
                "merge_output_format": "mp4",
            })
        else:  # mode == "extract"
            audio_mode = getattr(settings, "AUDIO_EXTRACT_MODE", "copy")
            codec = "mp3" if "mp3" in audio_mode else ("opus" if audio_mode == "opus" else "best")
            opts.update({
                "format": "bestaudio/best",
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": codec,
                    "preferredquality": "0" if audio_mode == "mp3_best" else "2",
                }]
            })

        # Storage directory mapping (HDD destination vs fast SSD temp buffer)
        if playlist_folder:
            temp_dir = getattr(settings, "TEMP_DOWNLOAD_PATH", None)
            paths_config: Dict[str, str] = {"home": playlist_folder}
            if temp_dir and temp_dir.strip():
                temp_playlist_folder = os.path.join(temp_dir.strip(), os.path.basename(playlist_folder))
                os.makedirs(temp_playlist_folder, exist_ok=True)
                paths_config["temp"] = temp_playlist_folder

            opts["paths"] = paths_config
            opts["outtmpl"] = "%(title|channel|Unknown)s [%(id)s].%(ext)s"

        if archive_file:
            opts["download_archive"] = archive_file

        # Resilience, retries & exponential backoff
        min_sleep = getattr(settings, "SLEEP_INTERVAL_MIN", 1)
        max_sleep = getattr(settings, "SLEEP_INTERVAL_MAX", 5)
        fragments = getattr(settings, "CONCURRENT_FRAGMENTS", 2)

        opts.update({
            "ignoreerrors": False,
            "quiet": False,
            "no_warnings": True,
            "overwrites": True,
            "continuedl": False,
            "retries": 10,
            "fragment_retries": 10,
            "extractor_retries": 3,
            "file_access_retries": 3,
            "concurrent_fragment_downloads": max(1, fragments),
            "sleep_interval": min_sleep,
            "max_sleep_interval": max_sleep,
            "sleep_interval_subtitles": 0,
            "retry_sleep_functions": {
                "http": lambda n: min(4 ** n, 60),      # Exponential backoff for HTTP 429/403/503 errors
                "fragment": lambda n: min(2 ** n, 30),  # Exponential backoff for fragment timeouts
            }
        })

        if progress_hooks:
            opts["progress_hooks"] = progress_hooks

    # 5. Apply any manual overrides
    if extra_opts:
        opts.update(extra_opts)

    return opts
