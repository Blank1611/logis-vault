#!/usr/bin/env python3
"""
Production start script for yt_serve with standard Prometheus/Loki-style CLI flags
"""
import argparse
import sys
import os
import uvicorn

def parse_args():
    parser = argparse.ArgumentParser(
        prog="yt_serve",
        description="YouTube Playlist Manager & Audio Extractor Server"
    )
    
    parser.add_argument(
        "--config.file",
        dest="config_file",
        type=str,
        default=None,
        help="Path to .env / configuration file (e.g. /app/data/config.env)"
    )
    
    parser.add_argument(
        "--storage.db.path",
        dest="db_path",
        type=str,
        default=None,
        help="Path to SQLite database file (e.g. /app/data/yt_manager.db)"
    )
    
    parser.add_argument(
        "--storage.downloads.path",
        dest="downloads_path",
        type=str,
        default=None,
        help="Root directory for video and audio downloads (e.g. /downloads)"
    )
    
    parser.add_argument(
        "--storage.temp.path",
        dest="temp_path",
        type=str,
        default=None,
        help="Optional fast SSD directory for active downloads and FFmpeg processing (e.g. /downloads-temp)"
    )
    
    parser.add_argument(
        "--web.listen-address",
        dest="listen_address",
        type=str,
        default="0.0.0.0:8000",
        help="Address and port to bind web interface and API (default: 0.0.0.0:8000)"
    )
    
    parser.add_argument(
        "--log.level",
        dest="log_level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Logging verbosity level (default: info)"
    )
    
    parser.add_argument(
        "--git.user.name",
        dest="git_user_name",
        type=str,
        default=None,
        help="Git committer/author name for playlist metadata versioning (e.g. Blank1611)"
    )
    
    parser.add_argument(
        "--git.user.email",
        dest="git_user_email",
        type=str,
        default=None,
        help="Git committer/author email for playlist metadata versioning (e.g. your.email@example.com)"
    )

    parser.add_argument(
        "--log.max-bytes",
        dest="log_max_bytes",
        type=int,
        default=None,
        help="Max bytes before yt_manager.log rotates (default: 10485760 / 10MB)"
    )

    parser.add_argument(
        "--log.backup-count",
        dest="log_backup_count",
        type=int,
        default=None,
        help="Number of rotated yt_manager.log historical files to keep (default: 5)"
    )

    parser.add_argument(
        "--log.ring-buffer-size",
        dest="log_ring_buffer_size",
        type=int,
        default=None,
        help="In-memory circular buffer capacity for live logs (default: 1000, min: 100, max: 50000)"
    )

    parser.add_argument(
        "--job-log.max-days",
        dest="job_log_max_days",
        type=int,
        default=None,
        help="Max age in days before job_{id}.log files are purged (default: 30)"
    )

    parser.add_argument(
        "--job-log.max-files",
        dest="job_log_max_files",
        type=int,
        default=None,
        help="Max number of recent job_{id}.log files to retain (default: 100)"
    )
    
    return parser.parse_known_args()

if __name__ == "__main__":
    args, unknown = parse_args()
    
    if args.git_user_name:
        os.environ["GIT_USER_NAME"] = args.git_user_name
    if args.git_user_email:
        os.environ["GIT_USER_EMAIL"] = args.git_user_email
    if args.log_max_bytes is not None:
        os.environ["LOG_MAX_BYTES"] = str(args.log_max_bytes)
    if args.log_backup_count is not None:
        os.environ["LOG_BACKUP_COUNT"] = str(args.log_backup_count)
    if args.log_ring_buffer_size is not None:
        os.environ["LOG_RING_BUFFER_SIZE"] = str(args.log_ring_buffer_size)
    if args.job_log_max_days is not None:
        os.environ["JOB_LOG_MAX_DAYS"] = str(args.job_log_max_days)
    if args.job_log_max_files is not None:
        os.environ["JOB_LOG_MAX_FILES"] = str(args.job_log_max_files)
    
    # Parse host and port from --web.listen-address
    host = "0.0.0.0"
    port = 8000
    if args.listen_address:
        if ":" in args.listen_address:
            parts = args.listen_address.split(":", 1)
            host = parts[0] or "0.0.0.0"
            try:
                port = int(parts[1])
            except ValueError:
                port = 8000
        else:
            host = args.listen_address
            
    print("=" * 60)
    print("Playlist Manager - Production Server")
    print("=" * 60)
    print(f"Listen Address:  http://{host}:{port}")
    print(f"API Docs:        http://{host}:{port}/docs")
    print(f"Prometheus:      http://{host}:{port}/metrics")
    print(f"Log Level:       {args.log_level}")
    print("=" * 60 + "\n")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level=args.log_level.lower()
    )
