"""
Background Daily Metadata Scheduler for 24/7 Server Deployments.

Periodically loops through all saved playlists once every 24 hours:
- Checks if metadata is stale (from previous days).
- Fetches fresh metadata via yt-dlp.
- Updates SQLite playlist stats.
- Triggers atomic Git commits per playlist for any added/privatized/removed tracks.
"""

import asyncio
import traceback
from datetime import datetime
from typing import Optional

from app.core.config import settings


async def run_daily_metadata_refresh():
    """
    Execute one pass over all active playlists to refresh stats and commit changes.
    """
    if not getattr(settings, "ENABLE_DAILY_AUTO_REFRESH", True):
        print("[SCHEDULER] Daily auto-refresh is disabled in settings.")
        return

    print(f"\n[SCHEDULER] Starting scheduled daily playlist metadata scan at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}...")

    from app.models.database import SessionLocal, Playlist
    from app.services.ytdlp_service import DownloadService

    db = SessionLocal()
    try:
        playlists_list = db.query(Playlist).all()
        if not playlists_list:
            print("[SCHEDULER] No playlists found to scan.")
            return

        download_service = DownloadService(settings.BASE_DOWNLOAD_PATH, {
            "audio_extract_mode": settings.AUDIO_EXTRACT_MODE,
            "max_extraction_workers": settings.MAX_CONCURRENT_EXTRACTIONS,
            "batch_size": settings.BATCH_SIZE,
            "use_browser_cookies": settings.USE_BROWSER_COOKIES,
            "browser_name": settings.BROWSER_NAME,
            "cookies_file": settings.COOKIES_FILE,
        })

        refreshed_count = 0
        for playlist in playlists_list:
            try:
                print(f"[SCHEDULER] Scanning: '{playlist.title}'...", end=" ", flush=True)
                # force_refresh=False so same-day scans are fast cache hits, but new days fetch fresh YouTube data
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

                # Brief pause between playlists to avoid bursting YouTube
                await asyncio.sleep(2)

            except Exception as item_err:
                print(f"✗ Error: {item_err}")

        print(f"[SCHEDULER] Completed daily scan of {refreshed_count}/{len(playlists_list)} playlists.\n")

    except Exception as e:
        print(f"[SCHEDULER] Error during daily scan: {e}")
        traceback.print_exc()
    finally:
        db.close()


async def _daily_scheduler_loop():
    """
    Continuous background loop that runs every 24 hours.
    """
    interval_hours = max(1, getattr(settings, "DAILY_REFRESH_INTERVAL_HOURS", 24))
    interval_seconds = interval_hours * 3600

    print(f"[SCHEDULER] Daily background metadata scheduler initialized (interval: {interval_hours}h).")

    # Initial delay to avoid colliding immediately with startup tasks
    await asyncio.sleep(60)

    while True:
        try:
            await run_daily_metadata_refresh()
        except asyncio.CancelledError:
            print("[SCHEDULER] Background scheduler loop cancelled.")
            break
        except Exception as e:
            print(f"[SCHEDULER] Unexpected loop error: {e}")

        await asyncio.sleep(interval_seconds)


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
