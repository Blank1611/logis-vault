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
import contextvars
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
from datetime import datetime

from app.core.config import settings
from app.core.logging_engine import get_logger

logger = get_logger("app.utils.git_sync")

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
        logger.warning(f"[GIT SYNC] Git executable not available in system; skipping repository setup.")
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
            logger.info(f"[GIT SYNC] Generated metadata .gitignore at {gitignore_path}")
        except Exception as e:
            logger.warning(f"[GIT SYNC] Warning: Could not write .gitignore: {e}")

    # Init git repo if missing
    if not os.path.isdir(git_dir):
        code, stdout, stderr = _run_git_cmd(["init", "-b", getattr(settings, "GIT_BRANCH", "main")], base_path)
        if code != 0:
            # Fallback for older git versions without -b flag
            code, stdout, stderr = _run_git_cmd(["init"], base_path)
            if code != 0:
                logger.error(f"[GIT SYNC] Failed to git init in {base_path}: {stderr}")
                return False

        # Set committer identity from settings or defaults
        user_name = getattr(settings, "GIT_USER_NAME", "YouTube Playlist Manager")
        user_email = getattr(settings, "GIT_USER_EMAIL", "yt-manager@homelab.local")
        _run_git_cmd(["config", "user.name", user_name], base_path)
        _run_git_cmd(["config", "user.email", user_email], base_path)

        # Initial commit with .gitignore
        _run_git_cmd(["add", ".gitignore"], base_path)
        _run_git_cmd(["commit", "-m", "Initial commit: Setup playlist metadata tracking"], base_path)
        logger.info(f"[GIT SYNC] Initialized new Git metadata repository in {base_path}")

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
                logger.info(f"[GIT SYNC] Removed stale Git index lock: {lock_file}")
        except Exception as e:
            logger.warning(f"[GIT SYNC] Warning: Could not inspect/remove stale lock: {e}")

# Context variable tracking the active GitBatchSession (scoped per asyncio task/thread)
_CURRENT_GIT_BATCH: contextvars.ContextVar[Optional["GitBatchSession"]] = contextvars.ContextVar(
    "_CURRENT_GIT_BATCH", default=None
)

def _get_git_commit_env() -> Dict[str, str]:
    """Retrieve Git author and committer environment mapping from settings"""
    return {
        "GIT_AUTHOR_NAME": getattr(settings, "GIT_USER_NAME", "YouTube Playlist Manager"),
        "GIT_AUTHOR_EMAIL": getattr(settings, "GIT_USER_EMAIL", "yt-manager@homelab.local"),
        "GIT_COMMITTER_NAME": getattr(settings, "GIT_USER_NAME", "YouTube Playlist Manager"),
        "GIT_COMMITTER_EMAIL": getattr(settings, "GIT_USER_EMAIL", "yt-manager@homelab.local"),
    }

def _format_playlist_delta(playlist_title: str, old_info: Optional[Dict[str, Any]], new_info: Dict[str, Any]) -> str:
    """Format a human-readable delta line for a playlist update"""
    added_ids, removed_ids, total_count = _compute_video_deltas(old_info, new_info)
    if added_ids and removed_ids:
        sample_ids = [f"-{vid}" for vid in removed_ids[:3]] + [f"+{vid}" for vid in added_ids[:3]]
        return f"Update '{playlist_title}': +{len(added_ids)} added, -{len(removed_ids)} removed/private (Total: {total_count}) [IDs: {', '.join(sample_ids)}]"
    elif removed_ids:
        sample_ids = [f"{vid}" for vid in removed_ids[:5]]
        return f"Update '{playlist_title}': -{len(removed_ids)} removed/private (Total: {total_count}) [ID{'s' if len(sample_ids) > 1 else ''}: {', '.join(sample_ids)}]"
    elif added_ids:
        sample_ids = [f"{vid}" for vid in added_ids[:5]]
        return f"Update '{playlist_title}': +{len(added_ids)} added (Total: {total_count}) [ID{'s' if len(sample_ids) > 1 else ''}: {', '.join(sample_ids)}]"
    else:
        return f"Update '{playlist_title}': Metadata updated (Total: {total_count})"


class GitBatchSession:
    """
    Context manager that defers committing Git changes until the entire multi-playlist
    batch scan (e.g. Daily Schedule or Startup Scan) completes, consolidating all modified
    playlists into a single structured commit with bulleted changelogs.
    """
    def __init__(self, source: str = "scheduled", label: Optional[str] = None):
        self.source = source
        self.label = label or ("Daily Schedule" if source == "scheduled" else "Startup Scan")
        self.staged_entries: List[Dict[str, Any]] = []
        self._token: Optional[contextvars.Token] = None

    def __enter__(self):
        self._token = _CURRENT_GIT_BATCH.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.commit_batch()
        finally:
            if self._token is not None:
                _CURRENT_GIT_BATCH.reset(self._token)

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)

    def commit_batch(self) -> bool:
        """Commit all accumulated changes in this batch session into a single Git commit"""
        if not getattr(settings, "ENABLE_GIT_METADATA_SYNC", False):
            return False
        if not is_git_available():
            return False

        base_path = settings.BASE_DOWNLOAD_PATH

        with _GIT_MUTEX:
            if not ensure_git_repo(base_path):
                return False

            _cleanup_stale_git_lock(base_path)

            # Verify if there are changes currently staged in git index
            code, _, _ = _run_git_cmd(["diff", "--cached", "--quiet"], base_path)
            if code == 0:
                # 0 means NO staged changes -> 0 commits created
                return False

            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            prefix_map = {
                "scheduled": "[Daily Schedule]",
                "startup": "[Startup Scan]",
                "ondemand": "[On-Demand]",
                "manual": "[On-Demand]",
            }
            tag = prefix_map.get(self.source.lower(), f"[{self.source.capitalize()}]")

            if len(self.staged_entries) == 1:
                commit_msg = f"{tag} {self.staged_entries[0]['summary']}"
            elif len(self.staged_entries) > 1:
                header = f"{tag} Batch update {len(self.staged_entries)} playlists ({now_str})"
                bullets = [f"• {entry['summary']}" for entry in self.staged_entries]
                commit_msg = f"{header}\n\n" + "\n".join(bullets)
            else:
                commit_msg = f"{tag} Batch metadata update ({now_str})"

            commit_env = _get_git_commit_env()
            code, stdout, stderr = _run_git_cmd(["commit", "-m", commit_msg], base_path, env_vars=commit_env)
            if code == 0:
                logger.info(f"[GIT SYNC] ✓ Committed batch: {commit_msg.splitlines()[0]}")
                push_to_remote_async()
                return True
            else:
                logger.error(f"[GIT SYNC] Batch commit failed: {stderr}")
                return False


def reconcile_uncommitted_metadata(base_path: str) -> bool:
    """
    Checks for uncommitted metadata changes or dead locks on container boot and commits them cleanly.
    Called by RecoveryService during startup recovery.
    """
    if not getattr(settings, "ENABLE_GIT_METADATA_SYNC", False):
        return False
    if not is_git_available():
        return False

    with _GIT_MUTEX:
        _cleanup_stale_git_lock(base_path)
        if not ensure_git_repo(base_path):
            return False

        # Check git status for modified or untracked metadata files
        code, stdout, _ = _run_git_cmd(["status", "--porcelain"], base_path)
        if not stdout.strip():
            return False

        dirty_lines = [line.strip() for line in stdout.splitlines() if "playlist_info.json" in line]
        if not dirty_lines:
            return False

        # Stage modified playlist metadata files
        _run_git_cmd(["add", "-u"], base_path)

        # Check if there are differences against HEAD
        code, _, _ = _run_git_cmd(["diff", "--cached", "--quiet"], base_path)
        if code == 0:
            return False

        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        commit_msg = (
            f"[Startup Recovery] Reconcile uncommitted playlist metadata after restart ({now_str})\n\n"
            f"• Automatically reconciled {len(dirty_lines)} metadata file(s) left uncommitted from prior crash/restart."
        )
        commit_env = _get_git_commit_env()
        code, stdout, stderr = _run_git_cmd(["commit", "-m", commit_msg], base_path, env_vars=commit_env)
        if code == 0:
            logger.info(f"[GIT SYNC] ✓ Startup Recovery: Reconciled {len(dirty_lines)} uncommitted metadata file(s).")
            push_to_remote_async()
            return True
        else:
            logger.error(f"[GIT SYNC] Startup Recovery commit failed: {stderr}")
            return False


def commit_playlist_atomic(
    playlist_folder: str,
    playlist_title: str,
    old_info: Optional[Dict[str, Any]],
    new_info: Dict[str, Any],
    source: str = "ondemand"
) -> bool:
    """
    Stages this playlist's playlist_info.json.
    - If a GitBatchSession is active: defers commit until batch completion.
    - If no GitBatchSession is active: commits immediately and atomically.
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
            snapshot_json = os.path.join(playlist_folder, "playlist_info.json")
            if not os.path.isfile(snapshot_json):
                return False

        rel_path = os.path.relpath(snapshot_json, base_path)

        # Stage this specific file
        code, _, stderr = _run_git_cmd(["add", rel_path], base_path)
        if code != 0:
            logger.error(f"[GIT SYNC] Error staging {rel_path}: {stderr}")
            return False

        # Check if there are staged changes (0 means NO changes)
        code, _, _ = _run_git_cmd(["diff", "--cached", "--quiet", "--", rel_path], base_path)
        if code == 0:
            # No changes in this playlist's metadata -> skip commit
            return False

        # Compute delta summary for commit message
        delta_summary = _format_playlist_delta(playlist_title, old_info, new_info)

        # If inside an active batch session, register entry and defer commit
        active_batch = _CURRENT_GIT_BATCH.get()
        if active_batch is not None:
            active_batch.staged_entries.append({
                "title": playlist_title,
                "summary": delta_summary,
                "rel_path": rel_path
            })
            logger.info(f"[GIT SYNC] Staged for batch commit: {delta_summary}")
            return True

        # Outside a batch session -> create immediate atomic commit
        prefix_map = {
            "scheduled": "[Daily Schedule]",
            "ondemand": "[On-Demand]",
            "manual": "[On-Demand]",
            "startup": "[Startup Scan]",
        }
        tag = prefix_map.get(source.lower(), f"[{source.capitalize()}]")
        commit_title = f"{tag} {delta_summary}"

        commit_env = _get_git_commit_env()
        code, stdout, stderr = _run_git_cmd(["commit", "-m", commit_title, "--", rel_path], base_path, env_vars=commit_env)
        if code == 0:
            logger.info(f"[GIT SYNC] ✓ Committed: {commit_title}")
            push_to_remote_async()
            return True
        else:
            logger.error(f"[GIT SYNC] Commit failed: {stderr}")
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


def test_git_connection_sync(
    remote_url: Optional[str] = None,
    auth_token: Optional[str] = None,
    branch: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Test remote Git repository connectivity and PAT authentication in a strictly read-only manner.
    Uses 'git ls-remote' - zero writes, zero commits, zero pushes.
    Provides intelligent diagnosis for PAT, URL, repo existence, or network issues.
    """
    if not is_git_available():
        return False, "Git executable not found in system PATH."

    url = remote_url if remote_url is not None else getattr(settings, "GIT_REMOTE_URL", None)
    if not url or not url.strip():
        return False, "Remote Git repository URL is empty."

    url = url.strip()
    token = auth_token if auth_token is not None else getattr(settings, "GIT_AUTH_TOKEN", None)
    if token and token.strip():
        token = token.strip()
        if url.startswith("https://") and "@" not in url:
            auth_url = f"https://oauth2:{token}@" + url[len("https://"):]
        else:
            auth_url = url
    else:
        auth_url = url

    target_branch = branch if branch is not None else getattr(settings, "GIT_BRANCH", "main") or "main"
    base_path = settings.BASE_DOWNLOAD_PATH
    if not os.path.isdir(base_path):
        os.makedirs(base_path, exist_ok=True)

    # Execute read-only ls-remote with 15s timeout
    code, stdout, stderr = _run_git_cmd(["ls-remote", "--heads", auth_url, target_branch], base_path, timeout=15)

    # Always mask token from any outputs/errors
    if token:
        stderr = stderr.replace(token, "******")
        stdout = stdout.replace(token, "******")

    if code == 0:
        return True, "Verified Connected: Remote URL and Personal Access Token (PAT) authenticated successfully."

    # Parse and diagnose stderr
    err_lower = stderr.lower()
    if any(k in err_lower for k in ["authentication failed", "invalid username or token", "access denied", "401", "403"]):
        return False, "Authentication Error: Your Personal Access Token (PAT) is invalid, expired, or missing write permissions."
    elif any(k in err_lower for k in ["not found", "repository not found", "404"]):
        return False, "Repository Not Found: The repository does not exist, or it is private and your PAT does not have access to it."
    elif any(k in err_lower for k in ["could not resolve host", "unable to access", "failed to connect", "timed out", "network"]):
        return False, "Connection Error: Unable to reach the remote host. Please check your network connection or the domain name in the URL."
    elif "does not appear to be a git repository" in err_lower:
        return False, "Invalid Git URL: The provided address does not appear to be a valid Git repository."
    else:
        clean_msg = stderr.strip() or "Connection test failed."
        return False, f"Git Verification Failed: {clean_msg}"


def sync_git_remote_origin(
    base_path: str,
    remote_url: Optional[str] = None,
    auth_token: Optional[str] = None,
    enable_push: Optional[bool] = None
) -> bool:
    """
    Synchronizes or cleans up the local Git repository's 'origin' remote.
    - If remote_url is provided and remote push is enabled: sets/updates 'origin'.
    - If remote_url is empty or remote push is disabled: removes 'origin' so no stale tokens linger in .git/config.
    """
    if not is_git_available() or not os.path.isdir(os.path.join(base_path, ".git")):
        return False

    should_push = enable_push if enable_push is not None else getattr(settings, "ENABLE_GIT_REMOTE_PUSH", False)
    url = remote_url if remote_url is not None else getattr(settings, "GIT_REMOTE_URL", None)

    with _GIT_MUTEX:
        _cleanup_stale_git_lock(base_path)
        if not should_push or not url or not url.strip():
            # Remove origin remote to prevent stale credentials lingering on disk
            _run_git_cmd(["remote", "remove", "origin"], base_path)
            return True

        token = auth_token if auth_token is not None else getattr(settings, "GIT_AUTH_TOKEN", None)
        url_clean = url.strip()
        if token and token.strip() and url_clean.startswith("https://") and "@" not in url_clean:
            auth_url = f"https://oauth2:{token.strip()}@" + url_clean[len("https://"):]
        else:
            auth_url = url_clean

        _run_git_cmd(["remote", "remove", "origin"], base_path)
        code, _, _ = _run_git_cmd(["remote", "add", "origin", auth_url], base_path)
        return code == 0


def push_to_remote_sync() -> Tuple[bool, str]:
    """Synchronously push commits to configured Git remote repository"""
    if not getattr(settings, "ENABLE_GIT_REMOTE_PUSH", False):
        return True, "Remote Git push is disabled (local commits only)"

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
    if not getattr(settings, "ENABLE_GIT_REMOTE_PUSH", False):
        return

    remote_url = getattr(settings, "GIT_REMOTE_URL", None)
    if not remote_url or not remote_url.strip():
        return

    def _worker():
        success, msg = push_to_remote_sync()
        if success:
            logger.info(f"[GIT SYNC] ✓ {msg}")
        else:
            logger.warning(f"[GIT SYNC] ⚠️ {msg}")

    threading.Thread(target=_worker, daemon=True, name="git-sync-push").start()
