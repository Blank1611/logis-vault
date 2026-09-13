"""
Background Daily Metadata Scheduler for 24/7 Server Deployments with Timezone Support.

Features:
- Timezone-aware target execution time (e.g. 04:00 AM IST / Asia/Kolkata or user-configured timezone).
- Dynamic calculation of sleep intervals until the next scheduled daily run.
- Real-time scanning state tracking (is_scanning, current_playlist, progress, next_scan_at).
- Concurrency guarding: disables on-demand refresh collisions while a scheduled scan is active.
"""

import asyncio
import traceback
import os
from datetime import datetime, time as dtime, timedelta
from typing import Optional, Dict, Any, Tuple

import zoneinfo

from app.core.config import settings

# Global thread-safe state dictionary for scheduler progress and lock status
_SCHEDULER_STATE: Dict[str, Any] = {
    "is_scanning": False,
    "current_playlist": None,
    "completed_count": 0,
    "total_count": 0,
    "last_scan_at": None,
    "next_scan_at": None,
    "last_scan_summary": None,
}

def get_scheduler_state() -> Dict[str, Any]:
    """Return a snapshot of the current scheduler state"""
    return dict(_SCHEDULER_STATE)

def is_scheduler_scanning() -> bool:
    """Check if the daily metadata scanner is currently executing"""
    return bool(_SCHEDULER_STATE.get("is_scanning", False))


TIMEZONE_ALIASES: Dict[str, str] = {
    "IST": "Asia/Kolkata",
    "INDIA": "Asia/Kolkata",
    "EST": "America/New_York",
    "EDT": "America/New_York",
    "CST": "America/Chicago",
    "CDT": "America/Chicago",
    "MST": "America/Denver",
    "MDT": "America/Denver",
    "PST": "America/Los_Angeles",
    "PDT": "America/Los_Angeles",
    "GMT": "GMT",
    "UTC": "UTC",
    "BST": "Europe/London",
    "CET": "Europe/Berlin",
    "CEST": "Europe/Berlin",
    "JST": "Asia/Tokyo",
    "KST": "Asia/Seoul",
    "SGT": "Asia/Singapore",
    "AEST": "Australia/Sydney",
    "AEDT": "Australia/Sydney",
}

def _resolve_timezone(tz_name: Optional[str]) -> Any:
    """Resolve timezone object from string, with alias support (e.g. IST -> Asia/Kolkata) and graceful fallback"""
    if not tz_name or not tz_name.strip():
        tz_name = getattr(settings, "DAILY_REFRESH_TIMEZONE", "Asia/Kolkata") or "Asia/Kolkata"

    tz_name = tz_name.strip()
    # Check for friendly aliases (case-insensitive)
    mapped_name = TIMEZONE_ALIASES.get(tz_name.upper(), tz_name)

    try:
        return zoneinfo.ZoneInfo(mapped_name)
    except Exception as e:
        print(f"[SCHEDULER] Warning: Could not load timezone '{tz_name}' ({e}), falling back to system local time")
        return datetime.now().astimezone().tzinfo


def calculate_seconds_until_next_run(target_time_str: str, tz_name: str) -> Tuple[float, datetime]:
    """
    Calculate the exact seconds to sleep until the next target_time_str (HH:MM) in the given timezone.
    Returns (seconds_to_sleep, next_run_datetime)
    """
    tz = _resolve_timezone(tz_name)
    now_in_tz = datetime.now(tz)

    try:
        parts = target_time_str.strip().split(":")
        target_hour = int(parts[0])
        target_minute = int(parts[1]) if len(parts) > 1 else 0
    except Exception:
        target_hour = 4
        target_minute = 0

    # Today's target time in target timezone
    target_dt = now_in_tz.replace(
        hour=target_hour,
        minute=target_minute,
        second=0,
        microsecond=0
    )

    # If target time today has already passed, schedule for tomorrow
    if target_dt <= now_in_tz:
        target_dt += timedelta(days=1)

    seconds = (target_dt - now_in_tz).total_seconds()
    return max(1.0, seconds), target_dt


async def run_daily_metadata_refresh():
    """
    Execute one pass over all active playlists to refresh stats and commit changes.
    Guarded by is_scanning flag to prevent concurrent on-demand scraping collisions.
    """
    if not getattr(settings, "ENABLE_DAILY_AUTO_REFRESH", True):
        print("[SCHEDULER] Daily auto-refresh is disabled in settings.")
        return

    if _SCHEDULER_STATE["is_scanning"]:
        print("[SCHEDULER] Scan already in progress, skipping duplicate execution.")
        return

    _SCHEDULER_STATE["is_scanning"] = True
    _SCHEDULER_STATE["completed_count"] = 0
    _SCHEDULER_STATE["total_count"] = 0
    _SCHEDULER_STATE["current_playlist"] = "Initializing..."

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n[SCHEDULER] Starting scheduled daily playlist metadata scan at {now_str}...")

    from app.models.database import SessionLocal, Playlist
    from app.services.ytdlp_service import DownloadService

    db = SessionLocal()
    try:
        playlists_list = db.query(Playlist).all()
        if not playlists_list:
            print("[SCHEDULER] No playlists found to scan.")
            _SCHEDULER_STATE["is_scanning"] = False
            _SCHEDULER_STATE["current_playlist"] = None
            _SCHEDULER_STATE["last_scan_at"] = now_str
            _SCHEDULER_STATE["last_scan_summary"] = "0 playlists found"
            return

        _SCHEDULER_STATE["total_count"] = len(playlists_list)

        download_service = DownloadService(settings.BASE_DOWNLOAD_PATH, {
            "audio_extract_mode": settings.AUDIO_EXTRACT_MODE,
            "max_extraction_workers": settings.MAX_CONCURRENT_EXTRACTIONS,
            "batch_size": settings.BATCH_SIZE,
            "use_browser_cookies": settings.USE_BROWSER_COOKIES,
            "browser_name": settings.BROWSER_NAME,
            "cookies_file": settings.COOKIES_FILE,
        })

        from app.utils.git_sync import GitBatchSession
        refreshed_count = 0
        async with GitBatchSession(source="scheduled", label="Daily Schedule"):
            for idx, playlist in enumerate(playlists_list, start=1):
                _SCHEDULER_STATE["current_playlist"] = playlist.title
                _SCHEDULER_STATE["completed_count"] = idx - 1

                try:
                    print(f"[SCHEDULER] ({idx}/{len(playlists_list)}) Scanning: '{playlist.title}'...", end=" ", flush=True)
                    local_count, available_count, unavailable_count = await download_service.get_playlist_stats(
                        playlist.title,
                        playlist.url,
                        playlist.excluded_ids or [],
                        source="scheduled"
                    )

                    playlist.local_count = local_count
                    playlist.playlist_count = available_count
                    playlist.unavailable_count = unavailable_count
                    db.commit()

                    status = "Caught up" if local_count >= available_count else f"{available_count - local_count} new"
                    print(f"✓ {status} ({local_count}/{available_count})")
                    refreshed_count += 1

                    # 2-second rate-limit pause between playlists
                    await asyncio.sleep(2)

                except Exception as item_err:
                    print(f"✗ Error: {item_err}")

        _SCHEDULER_STATE["completed_count"] = len(playlists_list)
        _SCHEDULER_STATE["last_scan_at"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        _SCHEDULER_STATE["last_scan_summary"] = f"Scanned {refreshed_count}/{len(playlists_list)} playlists successfully"
        print(f"[SCHEDULER] Completed daily scan of {refreshed_count}/{len(playlists_list)} playlists.\n")

    except Exception as e:
        print(f"[SCHEDULER] Error during daily scan: {e}")
        _SCHEDULER_STATE["last_scan_summary"] = f"Scan error: {str(e)}"
        traceback.print_exc()
    finally:
        _SCHEDULER_STATE["is_scanning"] = False
        _SCHEDULER_STATE["current_playlist"] = None
        db.close()


async def _daily_scheduler_loop():
    """
    Continuous background loop that waits until target DAILY_REFRESH_TIME in DAILY_REFRESH_TIMEZONE.
    """
    target_time_str = getattr(settings, "DAILY_REFRESH_TIME", "04:00") or "04:00"
    tz_name = getattr(settings, "DAILY_REFRESH_TIMEZONE", "Asia/Kolkata") or "Asia/Kolkata"

    print(f"[SCHEDULER] Daily background metadata scheduler initialized (Target: {target_time_str} {tz_name}).")

    while True:
        try:
            # Refresh config values in case user updated them via Settings UI
            mode = getattr(settings, "DAILY_REFRESH_MODE", "scheduled") or "scheduled"
            target_time_str = getattr(settings, "DAILY_REFRESH_TIME", "04:00") or "04:00"
            tz_name = getattr(settings, "DAILY_REFRESH_TIMEZONE", "Asia/Kolkata") or "Asia/Kolkata"
            interval_mins = getattr(settings, "DAILY_REFRESH_INTERVAL_MINUTES", 1440) or 1440

            if mode == "interval":
                sleep_seconds = max(60.0, float(interval_mins * 60))
                next_run_dt = datetime.now() + timedelta(seconds=sleep_seconds)
                next_run_str = next_run_dt.strftime('%Y-%m-%d %H:%M:%S')
                _SCHEDULER_STATE["next_scan_at"] = next_run_str
                print(f"[SCHEDULER] Next periodic metadata scan in {interval_mins} mins (at {next_run_str})")
            else:
                sleep_seconds, next_run_dt = calculate_seconds_until_next_run(target_time_str, tz_name)
                next_run_str = next_run_dt.strftime('%Y-%m-%d %H:%M:%S %Z')
                _SCHEDULER_STATE["next_scan_at"] = next_run_str
                print(f"[SCHEDULER] Next daily metadata scan scheduled at: {next_run_str} (in {sleep_seconds/3600:.2f} hours)")

            await asyncio.sleep(sleep_seconds)

            # Trigger the daily refresh
            await run_daily_metadata_refresh()

        except asyncio.CancelledError:
            print("[SCHEDULER] Background scheduler loop cancelled.")
            break
        except Exception as e:
            print(f"[SCHEDULER] Unexpected loop error: {e}")
            await asyncio.sleep(60)


_scheduler_task: Optional[asyncio.Task] = None


def start_daily_scheduler():
    """Start the background scheduler task if not already running"""
    global _scheduler_task
    if _scheduler_task is None or _scheduler_task.done():
        try:
            loop = asyncio.get_event_loop()
            _scheduler_task = loop.create_task(_daily_scheduler_loop())
        except Exception as e:
            print(f"[SCHEDULER] Failed to start background task: {e}")


def stop_daily_scheduler():
    """Cancel the background scheduler task"""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        _scheduler_task = None
