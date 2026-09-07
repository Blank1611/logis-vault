"""
Automated Git Synchronization and Versioning Engine for Playlist Metadata.

Features:
- Initializes local Git repository in BASE_DOWNLOAD_PATH with whitelist .gitignore.
- Creates atomic, one-by-one commits per playlist when playlist_info.json changes.
- Formats concise commit messages with video IDs for added or privatized/removed videos.
- Safely pushes commits to remote GitHub repository in background threads.
"""

import os
import shutil
import subprocess
import threading
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from datetime import datetime

from app.core.config import settings

def is_git_available() -> bool:
    """Check if git executable exists in system PATH"""
    return shutil.which("git") is not None

# Whitelist .gitignore content for BASE_DOWNLOAD_PATH
BASE_DOWNLOAD_GITIGNORE = """# YouTube Playlist Manager - Metadata Whitelist .gitignore
# Ignore all files by default
*

# Allow traversing folder trees
!*/

# Whitelist metadata and archives only
!playlist_info.json
!*/playlist_info.json
!playlist_info_snapshot/
!playlist_info_snapshot/playlist_info.json
!archive.txt
!*/archive.txt

# Strictly ignore all media and temp download files
*.mp4
*.m4a
*.mp3
*.opus
*.webm
*.part
*.ytdl
*.temp
"""

def _run_git_cmd(
    args: List[str],
    cwd: str,
    timeout: int = 30,
    env_vars: Optional[Dict[str, str]] = None
) -> Tuple[int, str, str]:
    """Execute a git command with timeout and return (returncode, stdout, stderr)"""
    if not is_git_available():
        return -1, "", "git executable not found in PATH"

    try:
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        proc = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            env=env
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as e:
        return -1, "", str(e)


def ensure_git_repo(base_path: str) -> bool:
    """
    Ensure a local git repository exists in base_path and .gitignore is in place.
    Safely bypassed if git sync is disabled or git is not installed.
    """
    if not getattr(settings, "ENABLE_GIT_METADATA_SYNC", False):
        return False

    if not is_git_available():
        print(f"[GIT SYNC] Git executable not available in system; skipping repository setup.")
        return False

    if not os.path.isdir(base_path):
        os.makedirs(base_path, exist_ok=True)

    git_dir = os.path.join(base_path, ".git")
    gitignore_path = os.path.join(base_path, ".gitignore")

    # Write .gitignore if not present
    if not os.path.isfile(gitignore_path):
        try:
            with open(gitignore_path, "w", encoding="utf-8") as f:
                f.write(BASE_DOWNLOAD_GITIGNORE)
            print(f"[GIT SYNC] Generated metadata .gitignore at {gitignore_path}")
        except Exception as e:
            print(f"[GIT SYNC] Warning: Could not write .gitignore: {e}")

    # Init git repo if missing
    if not os.path.isdir(git_dir):
        code, stdout, stderr = _run_git_cmd(["init", "-b", getattr(settings, "GIT_BRANCH", "main")], base_path)
        if code != 0:
            # Fallback for older git versions without -b flag
            code, stdout, stderr = _run_git_cmd(["init"], base_path)
            if code != 0:
                print(f"[GIT SYNC] Failed to git init in {base_path}: {stderr}")
                return False

        # Set committer identity from settings or defaults
        user_name = getattr(settings, "GIT_USER_NAME", "YouTube Playlist Manager")
        user_email = getattr(settings, "GIT_USER_EMAIL", "yt-manager@homelab.local")
        _run_git_cmd(["config", "user.name", user_name], base_path)
        _run_git_cmd(["config", "user.email", user_email], base_path)

        # Initial commit with .gitignore
        _run_git_cmd(["add", ".gitignore"], base_path)
        _run_git_cmd(["commit", "-m", "Initial commit: Setup playlist metadata tracking"], base_path)
        print(f"[GIT SYNC] Initialized new Git metadata repository in {base_path}")

    return True


def _compute_video_deltas(old_info: Optional[Dict[str, Any]], new_info: Dict[str, Any]) -> Tuple[List[str], List[str], int]:
    """
    Compare previous playlist info against new playlist info.
    Returns (added_ids, removed_or_privatized_ids, total_count)
    """
    new_entries = new_info.get("entries") or []
    new_total = len(new_entries)

    if not old_info:
        # First scan: all current IDs are considered baseline
        added_ids = [e.get("id") for e in new_entries if e and e.get("id")]
        return added_ids[:10], [], new_total

    old_entries = old_info.get("entries") or []

    def _get_active_ids(entries: list) -> Dict[str, bool]:
        # Maps video_id -> is_available
        id_map = {}
        for e in entries:
            if not e:
                continue
            vid = e.get("id")
            if not vid:
                continue
            title = str(e.get("title") or "").lower()
            avail = str(e.get("availability") or "").lower()
            is_unavail = (
                "[private video]" in title or
                "[deleted video]" in title or
                avail in ["private", "unlisted", "subscriber_only"]
            )
            id_map[vid] = not is_unavail
        return id_map

    old_map = _get_active_ids(old_entries)
    new_map = _get_active_ids(new_entries)

    added_ids = []
    removed_ids = []

    # Detect new IDs
    for vid in new_map:
        if vid not in old_map:
            added_ids.append(vid)

    # Detect removed or newly privatized IDs
    for vid, was_avail in old_map.items():
        if vid not in new_map:
            # Completely removed from playlist
            removed_ids.append(vid)
        elif was_avail and not new_map.get(vid, False):
            # Still in playlist but transitioned to Private / Deleted
            removed_ids.append(vid)

    return added_ids, removed_ids, new_total


# Global thread lock to serialize all Git repository operations and prevent .git/index.lock collisions
_GIT_MUTEX = threading.Lock()

def _cleanup_stale_git_lock(base_path: str):
    """Clean up stale .git/index.lock if left over from an interrupted process"""
    lock_file = os.path.join(base_path, ".git", "index.lock")
    if os.path.isfile(lock_file):
        try:
            # If lock file is older than 60 seconds, it is stale from a crash
            mtime = os.path.getmtime(lock_file)
            if (datetime.now().timestamp() - mtime) > 60:
                os.remove(lock_file)
                print(f"[GIT SYNC] Removed stale Git index lock: {lock_file}")
        except Exception as e:
            print(f"[GIT SYNC] Warning: Could not inspect/remove stale lock: {e}")

def commit_playlist_atomic(
    playlist_folder: str,
    playlist_title: str,
    old_info: Optional[Dict[str, Any]],
    new_info: Dict[str, Any],
    source: str = "ondemand"
) -> bool:
    """
    Stages ONLY this playlist's playlist_info.json and creates a concise atomic commit if changed.
    Thread-safe: acquired via _GIT_MUTEX to prevent index.lock conflicts.
    """
    if not getattr(settings, "ENABLE_GIT_METADATA_SYNC", False):
        return False

    if not is_git_available():
        return False

    base_path = settings.BASE_DOWNLOAD_PATH

    with _GIT_MUTEX:
        if not ensure_git_repo(base_path):
            return False

        _cleanup_stale_git_lock(base_path)

        # Path to the playlist_info.json relative to base_path
        snapshot_json = os.path.join(playlist_folder, "playlist_info_snapshot", "playlist_info.json")
        if not os.path.isfile(snapshot_json):
            # Fallback to playlist root if not in snapshot dir
            snapshot_json = os.path.join(playlist_folder, "playlist_info.json")
            if not os.path.isfile(snapshot_json):
                return False

        rel_path = os.path.relpath(snapshot_json, base_path)

        # Stage this specific file
        code, _, stderr = _run_git_cmd(["add", rel_path], base_path)
        if code != 0:
            print(f"[GIT SYNC] Error staging {rel_path}: {stderr}")
            return False

        # Check if there are staged changes (0 means NO changes)
        code, _, _ = _run_git_cmd(["diff", "--cached", "--quiet", "--", rel_path], base_path)
        if code == 0:
            # No changes in this playlist's metadata -> skip commit
            return False

        # Compute deltas for commit message
        added_ids, removed_ids, total_count = _compute_video_deltas(old_info, new_info)

        # Build concise commit message with IDs
        parts = []
        if added_ids and removed_ids:
            parts.append(f"+{len(added_ids)} added, -{len(removed_ids)} removed/private")
            sample_ids = [f"-{vid}" for vid in removed_ids[:3]] + [f"+{vid}" for vid in added_ids[:3]]
            parts.append(f"[IDs: {', '.join(sample_ids)}]")
        elif removed_ids:
            parts.append(f"-{len(removed_ids)} removed/private")
            sample_ids = [f"{vid}" for vid in removed_ids[:5]]
            parts.append(f"[ID{'s' if len(sample_ids) > 1 else ''}: {', '.join(sample_ids)}]")
        elif added_ids:
            parts.append(f"+{len(added_ids)} added")
            sample_ids = [f"{vid}" for vid in added_ids[:5]]
            parts.append(f"[ID{'s' if len(sample_ids) > 1 else ''}: {', '.join(sample_ids)}]")
        else:
            parts.append("Metadata updated")

        prefix_map = {
            "scheduled": "[Daily Schedule]",
            "ondemand": "[On-Demand]",
            "manual": "[On-Demand]",
            "startup": "[Startup Scan]",
        }
        tag = prefix_map.get(source.lower(), f"[{source.capitalize()}]")
        commit_env = {
            "GIT_AUTHOR_NAME": getattr(settings, "GIT_USER_NAME", "YouTube Playlist Manager"),
            "GIT_AUTHOR_EMAIL": getattr(settings, "GIT_USER_EMAIL", "yt-manager@homelab.local"),
            "GIT_COMMITTER_NAME": getattr(settings, "GIT_USER_NAME", "YouTube Playlist Manager"),
            "GIT_COMMITTER_EMAIL": getattr(settings, "GIT_USER_EMAIL", "yt-manager@homelab.local"),
        }
        code, stdout, stderr = _run_git_cmd(["commit", "-m", commit_title, "--", rel_path], base_path, env_vars=commit_env)
        if code == 0:
            print(f"[GIT SYNC] ✓ Committed: {commit_title}")
            # Asynchronously trigger push
            push_to_remote_async()
            return True
        else:
            print(f"[GIT SYNC] Commit failed: {stderr}")
            return False


def _get_authenticated_remote_url() -> Optional[str]:
    """Inject GitHub PAT auth token into HTTPS remote URL if configured"""
    url = getattr(settings, "GIT_REMOTE_URL", None)
    if not url or not url.strip():
        return None

    url = url.strip()
    token = getattr(settings, "GIT_AUTH_TOKEN", None)
    if token and token.strip():
        token = token.strip()
        if url.startswith("https://") and "@" not in url:
            # Replace https://github.com/... with https://<token>@github.com/...
            url = f"https://oauth2:{token}@" + url[len("https://"):]
    return url


def push_to_remote_sync() -> Tuple[bool, str]:
    """Synchronously push commits to configured Git remote repository"""
    base_path = settings.BASE_DOWNLOAD_PATH
    remote_url = _get_authenticated_remote_url()
    branch = getattr(settings, "GIT_BRANCH", "main") or "main"

    if not remote_url:
        return True, "No remote URL configured (local commits only)"

    with _GIT_MUTEX:
        _cleanup_stale_git_lock(base_path)

        # Set or update origin remote
        _run_git_cmd(["remote", "remove", "origin"], base_path)
        code, _, stderr = _run_git_cmd(["remote", "add", "origin", remote_url], base_path)
        if code != 0 and "already exists" not in stderr:
            return False, f"Failed to set remote origin: {stderr}"

        # Push to remote branch
        code, stdout, stderr = _run_git_cmd(["push", "-u", "origin", branch], base_path, timeout=60)
        if code == 0:
            return True, f"Successfully pushed metadata commits to {branch} on remote"
        else:
            # Mask token from error output
            token = getattr(settings, "GIT_AUTH_TOKEN", "")
            clean_err = stderr.replace(token, "******") if token else stderr
            return False, f"Git push failed: {clean_err}"


def push_to_remote_async():
    """Trigger background push without blocking caller"""
    remote_url = getattr(settings, "GIT_REMOTE_URL", None)
    if not remote_url or not remote_url.strip():
        return

    def _worker():
        success, msg = push_to_remote_sync()
        if success:
            print(f"[GIT SYNC] ✓ {msg}")
        else:
            print(f"[GIT SYNC] ⚠️ {msg}")

    threading.Thread(target=_worker, daemon=True, name="git-sync-push").start()
