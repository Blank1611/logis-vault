"""
Prometheus Metrics Exporter for yt_serve
Exposes standard Prometheus exposition format at /metrics
"""
from fastapi import APIRouter, Response
from sqlalchemy import func
from typing import Optional
import os

from app.models.database import SessionLocal, Playlist, Job
from app.core.config import settings
from app.api.config import _parse_cookie_file_status

router = APIRouter()

def generate_prometheus_metrics() -> str:
    """Generate Prometheus exposition format v0.0.4 text"""
    lines = []
    
    db = SessionLocal()
    try:
        # 1. Playlist and Video Statistics
        playlists = db.query(Playlist).all()
        total_playlists = len(playlists)
        local_total = sum(p.local_count or 0 for p in playlists)
        remote_total = sum(p.playlist_count or 0 for p in playlists)
        pending_total = sum(max(0, (p.playlist_count or 0) - (p.local_count or 0)) for p in playlists)
        
        # 2. Active Jobs
        active_jobs = db.query(Job).filter(Job.status.in_(["running", "pending"])).count()
        
        # 3. Job execution statistics by type and status
        job_stats = db.query(Job.job_type, Job.status, func.count(Job.id)).group_by(Job.job_type, Job.status).all()
        
        # 4. Cookie Status & Days Remaining
        cookie_status = _parse_cookie_file_status(settings.COOKIES_FILE)
        days_remaining = cookie_status.days_remaining if cookie_status.days_remaining is not None else -1
        current_status = cookie_status.status
        
        # --- Format Prometheus Metrics ---
        
        # Cookie metrics
        lines.append("# HELP yt_serve_cookies_days_remaining Days remaining until YouTube cookies expire (-1 if not installed)")
        lines.append("# TYPE yt_serve_cookies_days_remaining gauge")
        lines.append(f"yt_serve_cookies_days_remaining {days_remaining}")
        lines.append("")
        
        lines.append("# HELP yt_serve_cookies_status Status of YouTube authentication cookies (1 for current status)")
        lines.append("# TYPE yt_serve_cookies_status gauge")
        for st in ["valid", "expiring_soon", "expired", "invalid", "not_installed"]:
            val = 1 if current_status == st else 0
            lines.append(f'yt_serve_cookies_status{{status="{st}"}} {val}')
        lines.append("")
        
        # Playlist & Video metrics
        lines.append("# HELP yt_serve_playlists_total Total number of tracked playlists")
        lines.append("# TYPE yt_serve_playlists_total gauge")
        lines.append(f"yt_serve_playlists_total {total_playlists}")
        lines.append("")
        
        lines.append("# HELP yt_serve_videos_local_total Total number of downloaded audio/video files on disk")
        lines.append("# TYPE yt_serve_videos_local_total gauge")
        lines.append(f"yt_serve_videos_local_total {local_total}")
        lines.append("")
        
        lines.append("# HELP yt_serve_videos_remote_total Total number of videos across remote YouTube playlists")
        lines.append("# TYPE yt_serve_videos_remote_total gauge")
        lines.append(f"yt_serve_videos_remote_total {remote_total}")
        lines.append("")
        
        lines.append("# HELP yt_serve_videos_pending_total Total number of pending videos waiting for download")
        lines.append("# TYPE yt_serve_videos_pending_total gauge")
        lines.append(f"yt_serve_videos_pending_total {pending_total}")
        lines.append("")
        
        # Job Metrics
        lines.append("# HELP yt_serve_jobs_active Number of currently running or queued jobs")
        lines.append("# TYPE yt_serve_jobs_active gauge")
        lines.append(f"yt_serve_jobs_active {active_jobs}")
        lines.append("")
        
        lines.append("# HELP yt_serve_jobs_total Cumulative count of job executions by type and status")
        lines.append("# TYPE yt_serve_jobs_total counter")
        
        # Known statuses and types to initialize counters
        all_types = ["download", "extract", "both"]
        all_statuses = ["completed", "failed", "cancelled", "running", "pending"]
        stats_map = {(j_type, status): 0 for j_type in all_types for status in all_statuses}
        for j_type, status, count in job_stats:
            stats_map[(j_type, status)] = count
            
        for (j_type, status), count in sorted(stats_map.items()):
            lines.append(f'yt_serve_jobs_total{{job_type="{j_type}",status="{status}"}} {count}')
        lines.append("")

        # 4. Observability & Logging metrics
        from app.core.logging_engine import _ring_buffer, _buffer_lock
        with _buffer_lock:
            buf_len = len(_ring_buffer)
            counts = {"DEBUG": 0, "INFO": 0, "WARNING": 0, "ERROR": 0, "CRITICAL": 0}
            for item in _ring_buffer:
                lvl = item.get("level", "INFO")
                if lvl in counts:
                    counts[lvl] += 1

        lines.append("# HELP yt_serve_log_ring_buffer_size Current number of in-memory buffered log entries")
        lines.append("# TYPE yt_serve_log_ring_buffer_size gauge")
        lines.append(f"yt_serve_log_ring_buffer_size {buf_len}")
        lines.append("")

        lines.append("# HELP yt_serve_log_entries_buffered Number of buffered log entries by level")
        lines.append("# TYPE yt_serve_log_entries_buffered gauge")
        for lvl, cnt in counts.items():
            lines.append(f'yt_serve_log_entries_buffered{{level="{lvl.lower()}"}} {cnt}')
        lines.append("")

    except Exception as e:
        lines.append(f"# ERROR generating metrics: {e}")
    finally:
        db.close()
        
    return "\n".join(lines) + "\n"

@router.get("/metrics")
async def get_metrics():
    """Expose Prometheus metrics endpoint"""
    content = generate_prometheus_metrics()
    return Response(content=content, media_type="text/plain; version=0.0.4; charset=utf-8")
