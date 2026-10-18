"""
Ad-hoc Single Video Download & Format Inspection Service.
Allows downloading individual YouTube videos with interactive quality/format inspection,
customizable destination path, metadata tracking, and automatic SQLite Track Index integration.
"""

import os
import json
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session
import yt_dlp

from app.core.config import settings
from app.core.logging_engine import get_logger
from app.utils.ytdlp_opts import build_ytdlp_options
from app.repositories import JobRepository, TrackRepository
from app.models.database import get_db_context

logger = get_logger("app.services.adhoc")


from urllib.parse import urlparse, parse_qs


def sanitize_youtube_url(url: str) -> str:
    """
    Sanitize YouTube URL by stripping playlist and radio query parameters
    (&list=..., &index=..., &start_radio=...) to ensure single-video operations target only the video.
    """
    clean = url.strip()
    try:
        parsed = urlparse(clean)
        if "youtube.com" in parsed.netloc:
            qs = parse_qs(parsed.query)
            vid = qs.get("v")
            if vid:
                return f"https://www.youtube.com/watch?v={vid[0]}"
        elif "youtu.be" in parsed.netloc:
            vid = parsed.path.strip("/")
            if vid:
                return f"https://youtu.be/{vid}"
    except Exception:
        pass
    return clean


def format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds to MM:SS or HH:MM:SS"""
    if not seconds:
        return "00:00"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def probe_video_info(url: str) -> Dict[str, Any]:
    """
    Fetch comprehensive video metadata and available stream formats without downloading.
    Returns resolutions (e.g. 4K, 1080p, 720p), cipher badges (Direct vs Adaptive DASH),
    fps, audio streams, duration, thumbnail, and stream options.
    """
    clean_url = sanitize_youtube_url(url)
    logger.info(f"[Adhoc] Probing video info for URL: {clean_url}")

    opts = build_ytdlp_options(mode="info", extra_opts={"noplaylist": True, "extract_flat": False})

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            if not info:
                raise ValueError("Could not fetch video information from YouTube.")

            # If it extracted as a playlist, get first entry
            if "entries" in info:
                entries = list(info["entries"])
                if entries:
                    info = entries[0]
                else:
                    raise ValueError("No video entry found at URL.")

            video_id = info.get("id", "")
            title = info.get("title", "")
            uploader = info.get("uploader") or info.get("channel") or "Unknown Artist"
            duration = info.get("duration", 0)
            thumbnail = info.get("thumbnail") or (info.get("thumbnails")[-1]["url"] if info.get("thumbnails") else "")
            view_count = info.get("view_count", 0)
            description = (info.get("description") or "")[:200]

            # Parse available video resolutions and encryption classification
            formats = info.get("formats") or []
            heights_map: Dict[int, Dict[str, Any]] = {}

            for f in formats:
                h = f.get("height")
                vcodec = f.get("vcodec")
                acodec = f.get("acodec")
                fps = f.get("fps") or 30
                filesize = f.get("filesize") or f.get("filesize_approx")

                if not h or vcodec == "none":
                    continue

                # Distinguish direct progressive (e.g. format 18) vs encrypted DASH
                is_direct = bool(vcodec and vcodec != "none" and acodec and acodec != "none")
                badge = "⚡ Direct" if is_direct else "🛡️ Adaptive DASH"
                badge_tooltip = (
                    "Unencrypted progressive stream (Challenge-Free)"
                    if is_direct else
                    "Deciphered high-definition adaptive stream"
                )

                # Keep best format per height (prefer higher fps or filesize)
                if h not in heights_map or (fps > heights_map[h].get("fps", 0)):
                    heights_map[h] = {
                        "height": h,
                        "fps": fps,
                        "vcodec": vcodec,
                        "acodec": acodec,
                        "filesize": filesize,
                        "is_direct": is_direct,
                        "badge": badge,
                        "badge_tooltip": badge_tooltip,
                    }

            sorted_heights = sorted(list(heights_map.keys()), reverse=True)
            resolution_options = []

            for h in sorted_heights:
                stream = heights_map[h]
                fps_tag = f" {stream['fps']}fps" if stream["fps"] > 30 else ""
                if h >= 2160:
                    label = f"{h}p{fps_tag} (4K UHD)"
                elif h >= 1440:
                    label = f"{h}p{fps_tag} (2K QHD)"
                elif h >= 1080:
                    label = f"{h}p{fps_tag} (Full HD)"
                elif h >= 720:
                    label = f"{h}p{fps_tag} (HD)"
                else:
                    label = f"{h}p{fps_tag}"

                resolution_options.append({
                    "height": h,
                    "label": label,
                    "fps": stream["fps"],
                    "vcodec": stream["vcodec"],
                    "is_direct": stream["is_direct"],
                    "badge": stream["badge"],
                    "badge_tooltip": stream["badge_tooltip"],
                    "filesize": stream["filesize"],
                })

            if not resolution_options:
                resolution_options.append({
                    "height": 0,
                    "label": "Best Available",
                    "fps": 30,
                    "vcodec": "unknown",
                    "is_direct": False,
                    "badge": "🛡️ Adaptive DASH",
                    "badge_tooltip": "Default highest available stream",
                    "filesize": None,
                })

            return {
                "status": "success",
                "video_id": video_id,
                "title": title,
                "uploader": uploader,
                "duration": duration,
                "formatted_duration": format_duration(duration),
                "thumbnail": thumbnail,
                "view_count": view_count,
                "description": description,
                "available_resolutions": resolution_options,
                "default_download_path": settings.get_adhoc_download_path()
            }

    except Exception as e:
        logger.error(f"[Adhoc] Probe failed for {clean_url}: {e}")
        return {
            "status": "error",
            "message": str(e),
            "video_id": "",
            "title": "",
            "available_resolutions": []
        }


def _update_adhoc_metadata(target_dir: str, video_info: Dict[str, Any], filepath: str, audio_filepath: Optional[str] = None):
    """
    Append or update video entry in adhoc_info.json and archive.txt in target directory.
    """
    os.makedirs(target_dir, exist_ok=True)
    json_path = os.path.join(target_dir, "adhoc_info.json")
    archive_path = os.path.join(target_dir, "archive.txt")

    # Update archive.txt
    vid = video_info.get("id") or video_info.get("video_id")
    if vid:
        try:
            with open(archive_path, "a", encoding="utf-8") as f:
                f.write(f"youtube {vid}\n")
        except Exception as e:
            logger.warning(f"[Adhoc] Could not update archive.txt: {e}")

    # Update adhoc_info.json
    try:
        entries = []
        if os.path.isfile(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                entries = json.load(f)
                if not isinstance(entries, list):
                    entries = []

        # Find existing entry or append
        existing_idx = next((i for i, item in enumerate(entries) if item.get("id") == vid), None)
        entry = {
            "id": vid,
            "title": video_info.get("title"),
            "uploader": video_info.get("uploader"),
            "duration": video_info.get("duration"),
            "filepath": filepath,
            "audio_filepath": audio_filepath,
            "downloaded_at": datetime.utcnow().isoformat() + "Z"
        }

        if existing_idx is not None:
            entries[existing_idx] = entry
        else:
            entries.append(entry)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

    except Exception as e:
        logger.warning(f"[Adhoc] Could not update adhoc_info.json: {e}")


def execute_adhoc_download(
    job_id: int,
    url: str,
    video_quality: str = "best",
    audio_format: str = "copy",
    extract_mode: str = "both",
    custom_download_path: Optional[str] = None,
    db: Optional[Session] = None,
    log_writer: Optional[Any] = None,
    cancel_token: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Execute ad-hoc single video download and optional audio extraction.
    Updates job stream metrics, metadata JSON, and registers file in Track index.
    """
    def write_log(msg: str, lvl: str = "INFO"):
        if log_writer:
            try:
                log_writer(job_id, msg, lvl)
            except Exception:
                pass
        else:
            logger.info(f"[Adhoc Job #{job_id}] {msg}")

    clean_url = sanitize_youtube_url(url)
    target_dir = os.path.abspath(custom_download_path or settings.get_adhoc_download_path())
    os.makedirs(target_dir, exist_ok=True)
    write_log(f"Target Directory: {target_dir} | Mode: {extract_mode} | Quality: {video_quality}")

    JobRepository.update_status(job_id, status="running", db=db)

    # Format selector configuration based on chosen resolution
    if video_quality and video_quality not in ("best", "0"):
        format_selector = f"bestvideo[height<={video_quality}]+bestaudio/best[height<={video_quality}]/best"
        outtmpl = os.path.join(target_dir, f"%(title)s [%(id)s] [{video_quality}p].%(ext)s")
    else:
        format_selector = "bestvideo+bestaudio/best"
        outtmpl = os.path.join(target_dir, "%(title)s [%(id)s] [%(resolution)s].%(ext)s")

    if extract_mode == "audio_only":
        outtmpl = os.path.join(target_dir, "%(title)s [%(id)s].%(ext)s")

    last_log_milestone = {"val": -1}

    def progress_hook(d):
        if cancel_token and getattr(cancel_token, "is_cancelled", False):
            raise Exception("Job cancelled by user")

        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            downloaded = d.get("downloaded_bytes") or 0
            speed = d.get("speed") or 0.0
            eta = d.get("eta") or 0
            raw_filename = os.path.basename(d.get("filename", ""))

            JobRepository.update_stream_progress(
                job_id=job_id,
                title=raw_filename,
                bytes_downloaded=downloaded,
                bytes_total=total,
                speed=speed,
                eta=eta,
                db=db
            )

            # Log periodically at 25%, 50%, 75%, 100%
            if total > 0:
                pct = int((downloaded / total) * 100)
                milestone = (pct // 25) * 25
                if milestone > last_log_milestone["val"] and milestone > 0:
                    last_log_milestone["val"] = milestone
                    speed_mb = speed / (1024 * 1024) if speed else 0.0
                    write_log(f"Progress: {milestone}% ({downloaded / (1024*1024):.1f}MB / {total / (1024*1024):.1f}MB) at {speed_mb:.2f} MB/s (ETA: {eta}s)")
        elif d.get("status") == "finished":
            write_log(f"Stream download finished, finalizing container...")

    # Base yt-dlp options
    ydl_opts = {
        "outtmpl": outtmpl,
        "noplaylist": True,
        "progress_hooks": [progress_hook],
        "quiet": True,
        "no_warnings": True,
        "ignoreerrors": False,
    }

    if extract_mode == "audio_only":
        # Extract audio directly
        ydl_opts["format"] = "bestaudio/best"
        postprocessors = []
        if audio_format in ("mp3_best", "mp3"):
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            })
        elif audio_format == "opus":
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "opus",
                "preferredquality": "160",
            })
        elif audio_format == "flac":
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "flac",
            })
        elif audio_format == "m4a":
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "256",
            })
        else:
            # Default copy / extract native
            postprocessors.append({
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
            })
        ydl_opts["postprocessors"] = postprocessors
    else:
        # Complete video or both
        ydl_opts["format"] = format_selector
        ydl_opts["merge_output_format"] = "mp4"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            if not info:
                raise ValueError("Download failed: No stream extracted.")

            vid = info.get("id", "")
            title = info.get("title", "")
            artist = info.get("uploader") or info.get("channel") or ""
            duration = info.get("duration")

            # Determine primary downloaded filepath
            downloaded_file = ydl.prepare_filename(info)
            if extract_mode == "audio_only":
                # Extracted audio extension
                base, _ = os.path.splitext(downloaded_file)
                ext = "mp3" if "mp3" in audio_format else ("opus" if audio_format == "opus" else "m4a")
                audio_file = f"{base}.{ext}" if not downloaded_file.endswith(f".{ext}") else downloaded_file
                primary_video = ""
                primary_audio = audio_file if os.path.isfile(audio_file) else downloaded_file
            else:
                primary_video = downloaded_file
                primary_audio = None

                # If "both", extract standalone audio copy
                if extract_mode == "both" and os.path.isfile(primary_video):
                    try:
                        import subprocess
                        base, _ = os.path.splitext(primary_video)
                        audio_target = f"{base}.mp3"
                        write_log(f"Extracting high-bitrate MP3 audio: {os.path.basename(audio_target)}")
                        cmd = ["ffmpeg", "-y", "-i", primary_video, "-vn", "-b:a", "320k", audio_target]
                        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                        if os.path.isfile(audio_target):
                            primary_audio = audio_target
                            write_log(f"✓ Extracted MP3 audio: {os.path.basename(audio_target)}", "SUCCESS")
                    except Exception as ex:
                        write_log(f"⚠️ Standalone audio extraction failed for {primary_video}: {ex}", "WARN")

            # Update adhoc metadata file
            write_log("Updating adhoc metadata index (adhoc_info.json)...")
            _update_adhoc_metadata(
                target_dir=target_dir,
                video_info=info,
                filepath=primary_video or primary_audio or "",
                audio_filepath=primary_audio
            )

            # Probe media metadata using local ffprobe
            from app.core.track_indexer import probe_local_media_metadata
            media_meta = probe_local_media_metadata(primary_video or "", primary_audio or "")
            res_list = []
            if media_meta.get("resolution"):
                res_list.append(f"{media_meta['resolution']}p")
            elif video_quality and video_quality not in ("best", "0"):
                res_list.append(f"{video_quality}p")

            # Register in global Track Index
            write_log("Indexing track in central SQLite track index...")
            TrackRepository.index_or_update_track(
                video_id=vid,
                title=title,
                filepath=primary_video or primary_audio or "",
                audio_filepath=primary_audio,
                artist=artist,
                duration=duration,
                downloaded_resolutions=res_list,
                downloaded_fps=media_meta.get("fps"),
                downloaded_audio_codec=media_meta.get("audio_codec"),
                downloaded_audio_bitrate=media_meta.get("audio_bitrate"),
                db=db
            )

            JobRepository.update_status(
                job_id=job_id,
                status="completed",
                completed_items=1,
                failed_items=0,
                db=db
            )

            write_log(f"✓ Successfully processed and indexed: {title} ({vid})", "SUCCESS")
            return {
                "status": "success",
                "job_id": job_id,
                "video_id": vid,
                "title": title,
                "filepath": primary_video or primary_audio
            }

    except Exception as e:
        logger.error(f"[Adhoc Job #{job_id}] Execution error: {e}")
        JobRepository.update_status(
            job_id=job_id,
            status="failed",
            error=str(e),
            db=db
        )
        return {
            "status": "error",
            "job_id": job_id,
            "error": str(e)
        }
