"""
Smart Track Indexer & Zero-Space Hardlink Engine for yt_serve.
Provides instant local sourcing, NTFS/ext4 hardlinks, and inter-playlist move management.
"""

import os
import shutil
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import Track, MovedTrackHistory, Playlist, get_db_context
from app.repositories import TrackRepository, PlaylistRepository
from app.core.logging_engine import get_logger

logger = get_logger("app.core.track_indexer")


def create_hardlink_or_copy(src_path: str, dst_path: str) -> bool:
    """
    Create a zero-space hardlink (os.link) pointing to the same physical disk inode.
    Falls back to copying if crossing distinct filesystem volumes.
    """
    if not os.path.exists(src_path):
        logger.warning(f"Source file for hardlink does not exist: {src_path}")
        return False

    if os.path.exists(dst_path):
        return True

    os.makedirs(os.path.dirname(dst_path), exist_ok=True)

    try:
        os.link(src_path, dst_path)
        logger.info(f"Created zero-space hardlink: {dst_path} -> {src_path}")
        return True
    except OSError as e:
        logger.info(f"Hardlink not supported across volumes ({e}), falling back to copy: {src_path} -> {dst_path}")
        try:
            shutil.copy2(src_path, dst_path)
            return True
        except Exception as copy_err:
            logger.error(f"Failed to copy file from {src_path} to {dst_path}: {copy_err}")
            return False


def find_local_track(video_id: str, db: Optional[Session] = None) -> Optional[Dict[str, Any]]:
    """
    Check if a video ID already exists locally in the global track index.
    Verifies that the physical file actually exists on disk.
    """
    with get_db_context(db) as session:
        track = session.query(Track).filter(Track.video_id == video_id).first()
        if not track:
            return None

        # Verify video file exists on disk
        video_exists = os.path.isfile(track.primary_filepath)
        audio_exists = bool(track.primary_audio_filepath and os.path.isfile(track.primary_audio_filepath))

        if not video_exists and not audio_exists:
            logger.warning(f"Track {video_id} indexed in database but files missing on disk: {track.primary_filepath}")
            return None

        return {
            "video_id": track.video_id,
            "title": track.title,
            "artist": track.artist,
            "duration": track.duration,
            "primary_filepath": track.primary_filepath if video_exists else None,
            "primary_audio_filepath": track.primary_audio_filepath if audio_exists else None,
            "playlists": track.playlists_json or [],
            "is_hardlinked": track.is_hardlinked,
        }


def probe_local_media_metadata(filepath: Optional[str], audio_filepath: Optional[str] = None) -> Dict[str, Any]:
    """Run fast local ffprobe to extract video resolution, fps, audio codec, and bitrate."""
    res: Dict[str, Any] = {
        "resolution": None,
        "fps": None,
        "audio_codec": None,
        "audio_bitrate": None
    }
    if not filepath or not os.path.isfile(filepath):
        return res
    try:
        import subprocess
        import json
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", filepath
        ]
        p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if p.returncode == 0 and p.stdout:
            data = json.loads(p.stdout)
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "video" and not res["resolution"]:
                    h = stream.get("height")
                    if h:
                        res["resolution"] = f"{h}p"
                    r_frame_rate = stream.get("r_frame_rate", "")
                    if "/" in r_frame_rate:
                        num, den = r_frame_rate.split("/")
                        if den.isdigit() and int(den) > 0 and num.isdigit():
                            res["fps"] = round(int(num) / int(den))
                elif stream.get("codec_type") == "audio" and not res["audio_codec"]:
                    res["audio_codec"] = stream.get("codec_name")
                    bitrate = stream.get("bit_rate")
                    if bitrate and str(bitrate).isdigit():
                        res["audio_bitrate"] = round(int(bitrate) / 1000)
    except Exception as e:
        logger.debug(f"ffprobe probe failed for {filepath}: {e}")

    # Check dedicated audio file if present
    if audio_filepath and os.path.isfile(audio_filepath):
        try:
            import subprocess
            import json
            cmd = [
                "ffprobe", "-v", "quiet", "-print_format", "json",
                "-show_streams", audio_filepath
            ]
            p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            if p.returncode == 0 and p.stdout:
                data = json.loads(p.stdout)
                for stream in data.get("streams", []):
                    if stream.get("codec_type") == "audio":
                        res["audio_codec"] = stream.get("codec_name")
                        bitrate = stream.get("bit_rate")
                        if bitrate and str(bitrate).isdigit():
                            res["audio_bitrate"] = round(int(bitrate) / 1000)
                        break
        except Exception as e:
            logger.debug(f"ffprobe audio probe failed for {audio_filepath}: {e}")

    return res


def index_track(
    video_id: str,
    title: str,
    filepath: str,
    playlist_id: int,
    audio_filepath: Optional[str] = None,
    artist: Optional[str] = None,
    duration: Optional[int] = None,
    is_hardlinked: bool = False,
    db: Optional[Session] = None
) -> Track:
    """
    Register or update a track in the global SQLite tracks index.
    """
    with get_db_context(db) as session:
        track = session.query(Track).filter(Track.video_id == video_id).first()
        meta = probe_local_media_metadata(filepath, audio_filepath)
        if track:
            current_playlists = list(track.playlists_json or [])
            if playlist_id not in current_playlists:
                current_playlists.append(playlist_id)
                track.playlists_json = current_playlists

            if not os.path.exists(track.primary_filepath) and os.path.exists(filepath):
                track.primary_filepath = filepath
            if audio_filepath and os.path.exists(audio_filepath):
                track.primary_audio_filepath = audio_filepath

            # Update media specs if missing
            cur_resolutions = list(track.downloaded_resolutions_json or [])
            if meta["resolution"] and meta["resolution"] not in cur_resolutions:
                cur_resolutions.insert(0, meta["resolution"])
                track.downloaded_resolutions_json = cur_resolutions
            if not track.downloaded_fps and meta["fps"]:
                track.downloaded_fps = meta["fps"]
            if not track.downloaded_audio_codec and meta["audio_codec"]:
                track.downloaded_audio_codec = meta["audio_codec"]
            if not track.downloaded_audio_bitrate and meta["audio_bitrate"]:
                track.downloaded_audio_bitrate = meta["audio_bitrate"]

            track.updated_at = datetime.utcnow()
            session.flush()
            session.refresh(track)
            return track
        else:
            initial_resolutions = [meta["resolution"]] if meta["resolution"] else []
            new_track = Track(
                video_id=video_id,
                title=title,
                artist=artist,
                duration=duration,
                primary_filepath=filepath,
                primary_audio_filepath=audio_filepath,
                playlists_json=[playlist_id],
                is_hardlinked=is_hardlinked,
                downloaded_resolutions_json=initial_resolutions,
                downloaded_fps=meta["fps"],
                downloaded_audio_codec=meta["audio_codec"],
                downloaded_audio_bitrate=meta["audio_bitrate"],
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            session.add(new_track)
            session.flush()
            session.refresh(new_track)
            return new_track


def backfill_all_local_tracks_metadata(db: Optional[Session] = None) -> int:
    """Scan existing database tracks with missing resolution info and backfill using local ffprobe."""
    backfilled = 0
    with get_db_context(db) as session:
        tracks = session.query(Track).all()
        for t in tracks:
            if not t.downloaded_resolutions_json or len(t.downloaded_resolutions_json) == 0:
                meta = probe_local_media_metadata(t.primary_filepath, t.primary_audio_filepath)
                if meta["resolution"]:
                    t.downloaded_resolutions_json = [meta["resolution"]]
                    t.downloaded_fps = meta["fps"]
                    t.downloaded_audio_codec = meta["audio_codec"]
                    t.downloaded_audio_bitrate = meta["audio_bitrate"]
                    t.updated_at = datetime.utcnow()
                    backfilled += 1
        if backfilled > 0:
            session.flush()
            logger.info(f"Backfilled media resolution specs for {backfilled} existing tracks via local ffprobe.")
    return backfilled


def hardlink_track_to_playlist(
    video_id: str,
    target_playlist_id: int,
    target_playlist_dir: str,
    target_audio_dir: Optional[str] = None,
    db: Optional[Session] = None
) -> bool:
    """
    Locally source and hardlink an existing track into target playlist folders.
    """
    track_info = find_local_track(video_id, db=db)
    if not track_info:
        return False

    src_video = track_info.get("primary_filepath")
    src_audio = track_info.get("primary_audio_filepath")
    success = False

    # 1. Hardlink Video
    if src_video and os.path.isfile(src_video):
        filename = os.path.basename(src_video)
        dst_video = os.path.join(target_playlist_dir, filename)
        if create_hardlink_or_copy(src_video, dst_video):
            success = True

    # 2. Hardlink Audio
    if src_audio and os.path.isfile(src_audio):
        if not target_audio_dir:
            audio_sub = os.path.basename(os.path.dirname(src_audio))
            to_title = os.path.basename(target_playlist_dir)
            import re
            m = re.search(r"(\[.*?\])$", audio_sub)
            tag = m.group(1) if m else "[MP3]"
            target_audio_dir = os.path.join(target_playlist_dir, f"{to_title} {tag}")
            os.makedirs(target_audio_dir, exist_ok=True)

        audio_name = os.path.basename(src_audio)
        dst_audio = os.path.join(target_audio_dir, audio_name)
        create_hardlink_or_copy(src_audio, dst_audio)

    if success:
        index_track(
            video_id=video_id,
            title=track_info["title"],
            filepath=src_video or "",
            playlist_id=target_playlist_id,
            audio_filepath=src_audio,
            is_hardlinked=True,
            db=db
        )
        logger.info(f"✓ Zero-space hardlinked track '{track_info['title']}' ({video_id}) to playlist #{target_playlist_id}")

        # Regenerate .m3u8 playlists for target playlist
        try:
            from app.core.yt_playlist_audio_tools import generate_m3u_playlists
            generate_m3u_playlists(target_playlist_dir, [target_audio_dir] if target_audio_dir else None)
        except Exception as m3u_e:
            logger.debug(f"Target playlist m3u generation note: {m3u_e}")

    return success


def execute_track_move(
    video_id: str,
    from_playlist_id: int,
    to_playlist_id: int,
    db: Optional[Session] = None,
    status: str = "manually_moved"
) -> Dict[str, Any]:
    """
    Relocate track files from one playlist folder to another and log the move.
    """
    from app.core.config import settings

    with get_db_context(db) as session:
        from_playlist = session.query(Playlist).filter(Playlist.id == from_playlist_id).first()
        to_playlist = session.query(Playlist).filter(Playlist.id == to_playlist_id).first()

        if not from_playlist or not to_playlist:
            raise ValueError("Source or destination playlist not found")

        track = session.query(Track).filter(Track.video_id == video_id).first()
        title = track.title if track else video_id

        # Update Track playlists_json
        if track:
            current_playlists = list(track.playlists_json or [])
            if from_playlist_id in current_playlists:
                current_playlists.remove(from_playlist_id)
            if to_playlist_id not in current_playlists:
                current_playlists.append(to_playlist_id)
            track.playlists_json = current_playlists
            track.updated_at = datetime.utcnow()

        # Physical file relocation / hardlinks
        safe_from = "".join(c for c in from_playlist.title if c not in r'\/:*?"<>|').strip() or "playlist"
        safe_to = "".join(c for c in to_playlist.title if c not in r'\/:*?"<>|').strip() or "playlist"
        from_dir = os.path.join(settings.BASE_DOWNLOAD_PATH, safe_from)
        to_dir = os.path.join(settings.BASE_DOWNLOAD_PATH, safe_to)
        os.makedirs(to_dir, exist_ok=True)

        # 1. Move/Relocate video
        if track and track.primary_filepath and os.path.isfile(track.primary_filepath):
            fname = os.path.basename(track.primary_filepath)
            dest_video = os.path.join(to_dir, fname)
            if os.path.dirname(track.primary_filepath) == from_dir and not os.path.exists(dest_video):
                try:
                    shutil.move(track.primary_filepath, dest_video)
                    track.primary_filepath = dest_video
                except Exception as mv_e:
                    logger.warning(f"Could not move video file {track.primary_filepath} -> {dest_video}: {mv_e}")
            elif not os.path.exists(dest_video):
                create_hardlink_or_copy(track.primary_filepath, dest_video)

        # 2. Move/Relocate audio
        if track and track.primary_audio_filepath and os.path.isfile(track.primary_audio_filepath):
            audio_fname = os.path.basename(track.primary_audio_filepath)
            src_audio_dir = os.path.dirname(track.primary_audio_filepath)
            audio_sub = os.path.basename(src_audio_dir)
            import re
            m = re.search(r"(\[.*?\])$", audio_sub)
            tag = m.group(1) if m else "[MP3]"
            dest_audio_dir = os.path.join(to_dir, f"{safe_to} {tag}")
            os.makedirs(dest_audio_dir, exist_ok=True)
            dest_audio = os.path.join(dest_audio_dir, audio_fname)

            if src_audio_dir.startswith(from_dir) and not os.path.exists(dest_audio):
                try:
                    shutil.move(track.primary_audio_filepath, dest_audio)
                    track.primary_audio_filepath = dest_audio
                    # Fast metadata touch to update Album tag to new playlist title
                    try:
                        import subprocess
                        temp_meta_path = dest_audio + ".tmp"
                        cmd = ["ffmpeg", "-y", "-i", dest_audio, "-c", "copy", "-metadata", f"album={to_playlist.title}", temp_meta_path]
                        ret = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        if ret.returncode == 0 and os.path.isfile(temp_meta_path):
                            shutil.move(temp_meta_path, dest_audio)
                    except Exception as meta_touch_e:
                        logger.debug(f"Audio metadata touch skipped: {meta_touch_e}")
                except Exception as mv_a_e:
                    logger.warning(f"Could not move audio file: {mv_a_e}")
            elif not os.path.exists(dest_audio):
                create_hardlink_or_copy(track.primary_audio_filepath, dest_audio)

        # Record Move in History
        history_entry = MovedTrackHistory(
            video_id=video_id,
            title=title,
            from_playlist_id=from_playlist_id,
            from_playlist_title=from_playlist.title,
            to_playlist_id=to_playlist_id,
            to_playlist_title=to_playlist.title,
            moved_at=datetime.utcnow(),
            status=status
        )
        session.add(history_entry)
        session.flush()

        # Regenerate .m3u8 playlists for both playlists
        try:
            from app.core.yt_playlist_audio_tools import generate_m3u_playlists
            generate_m3u_playlists(from_dir)
            generate_m3u_playlists(to_dir)
        except Exception as m3u_e:
            logger.debug(f"M3U playlist regeneration note: {m3u_e}")

        logger.info(f"Moved track '{title}' ({video_id}) from '{from_playlist.title}' to '{to_playlist.title}'")

        return {
            "video_id": video_id,
            "title": title,
            "from_playlist": from_playlist.title,
            "to_playlist": to_playlist.title,
            "status": status,
            "moved_at": history_entry.moved_at.isoformat()
        }
