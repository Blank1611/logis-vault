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
    
    return parser.parse_known_args()

if __name__ == "__main__":
    args, unknown = parse_args()
    
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
