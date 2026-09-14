"""
Automated Verification Test Suite for:
1. Dynamic Config Generator (generate_default_env)
2. GitBatchSession commit grouping & zero-change handling
3. Standalone atomic commits outside batch sessions
4. Startup Recovery Engine (stale lock clearing & metadata reconciliation)
5. Scheduler Scan 409 Concurrency Guards
6. Active Playlist Refresh Deduplication Lock

Designed to run seamlessly both inside the containerized Docker image
(e.g., `python tests/test_batch_recovery_guards.py` or `python -m unittest`)
and in standard development environments.
"""

import os
import tempfile
import json
import time
import unittest
from pathlib import Path

from app.core.config import Settings, generate_default_env, settings
from app.utils.git_sync import (
    GitBatchSession,
    commit_playlist_atomic,
    reconcile_uncommitted_metadata,
    _run_git_cmd,
    ensure_git_repo,
    test_git_connection_sync,
    sync_git_remote_origin,
    push_to_remote_sync,
)
from app.services.recovery_service import RecoveryService
from app.services.scheduler import _SCHEDULER_STATE, is_scheduler_scanning
from app.api.playlists import _ACTIVE_REFRESH_PLAYLISTS, _REFRESH_LOCK


class TestBatchRecoveryGuards(unittest.TestCase):
    """Container-ready test suite for batch commits, recovery, and concurrency guards."""

    def setUp(self):
        # Create self-cleaning isolated git repository sandbox
        self.temp_dir_obj = tempfile.TemporaryDirectory(prefix="test_yt_git_")
        self.temp_dir = self.temp_dir_obj.name
        self.orig_base = settings.BASE_DOWNLOAD_PATH
        self.orig_enable_git = settings.ENABLE_GIT_METADATA_SYNC

        settings.BASE_DOWNLOAD_PATH = self.temp_dir
        settings.ENABLE_GIT_METADATA_SYNC = True
        ensure_git_repo(self.temp_dir)

    def tearDown(self):
        settings.BASE_DOWNLOAD_PATH = self.orig_base
        settings.ENABLE_GIT_METADATA_SYNC = self.orig_enable_git
        self.temp_dir_obj.cleanup()

    def _make_playlist(self, title: str, video_ids: list):
        """Helper to create and commit an initial baseline playlist snapshot."""
        p_folder = os.path.join(self.temp_dir, title)
        snap_dir = os.path.join(p_folder, "playlist_info_snapshot")
        os.makedirs(snap_dir, exist_ok=True)
        info = {
            "title": title,
            "entries": [{"id": vid, "title": f"Song {vid}"} for vid in video_ids]
        }
        json_path = os.path.join(snap_dir, "playlist_info.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(info, f, indent=2)
        commit_playlist_atomic(p_folder, title, None, info, source="manual")
        return p_folder, info

    def test_dynamic_config_generator(self):
        """Verify dynamic generation of documented template from Settings model schema."""
        content = generate_default_env()
        self.assertIn("YouTube Playlist Manager Configuration (yt_serve)", content)
        self.assertIn("BASE_DOWNLOAD_PATH=", content)
        self.assertIn("AUDIO_EXTRACT_MODE=copy", content)
        self.assertIn("ENABLE_GIT_METADATA_SYNC=false", content)
        self.assertIn("# Scheduled daily scan time in HH:MM format", content)
        self.assertIn("LOG_MAX_BYTES=10485760", content)
        self.assertIn("LOG_BACKUP_COUNT=5", content)

    def test_git_batch_session_grouping(self):
        """Verify GitBatchSession defers and groups multiple playlist updates into 1 commit."""
        p1_folder, p1_info = self._make_playlist("Rock Classics", ["vid1", "vid2"])
        p2_folder, p2_info = self._make_playlist("Jazz Vibes", ["vid3", "vid4"])

        # Update both playlists
        p1_new_info = {
            "title": "Rock Classics",
            "entries": [
                {"id": "vid1", "title": "Song vid1"},
                {"id": "vid2", "title": "Song vid2"},
                {"id": "vid5", "title": "Song vid5"}
            ]
        }
        with open(os.path.join(p1_folder, "playlist_info_snapshot", "playlist_info.json"), "w", encoding="utf-8") as f:
            json.dump(p1_new_info, f, indent=2)

        p2_new_info = {
            "title": "Jazz Vibes",
            "entries": [{"id": "vid3", "title": "Song vid3"}]  # vid4 removed
        }
        with open(os.path.join(p2_folder, "playlist_info_snapshot", "playlist_info.json"), "w", encoding="utf-8") as f:
            json.dump(p2_new_info, f, indent=2)

        # Batch execution (e.g. Scheduled Daily Scan or Startup Scan)
        with GitBatchSession(source="scheduled", label="Daily Schedule"):
            c1 = commit_playlist_atomic(p1_folder, "Rock Classics", p1_info, p1_new_info, source="scheduled")
            c2 = commit_playlist_atomic(p2_folder, "Jazz Vibes", p2_info, p2_new_info, source="scheduled")
            self.assertTrue(c1, "Rock Classics should stage successfully")
            self.assertTrue(c2, "Jazz Vibes should stage successfully")

        # Verify only 1 batch commit was created with structured bullets
        code, stdout, _ = _run_git_cmd(["log", "-n", "1", "--pretty=format:%B"], self.temp_dir)
        self.assertEqual(code, 0)
        self.assertIn("[Daily Schedule] Batch update 2 playlists", stdout)
        self.assertIn("• Update 'Rock Classics': +1 added", stdout)
        self.assertIn("• Update 'Jazz Vibes': -1 removed", stdout)

    def test_git_batch_session_zero_changes(self):
        """Verify GitBatchSession creates zero commits if playlists had no metadata changes."""
        p1_folder, p1_info = self._make_playlist("Rock Classics", ["vid1", "vid2"])
        code, head_before, _ = _run_git_cmd(["rev-parse", "HEAD"], self.temp_dir)

        with GitBatchSession(source="scheduled", label="Daily Schedule"):
            commit_playlist_atomic(p1_folder, "Rock Classics", p1_info, p1_info, source="scheduled")

        code, head_after, _ = _run_git_cmd(["rev-parse", "HEAD"], self.temp_dir)
        self.assertEqual(head_before, head_after, "No commit should be generated when zero diffs occur")

    def test_standalone_atomic_commit(self):
        """Verify standalone on-demand operations commit immediately outside batch sessions."""
        p1_folder, p1_info = self._make_playlist("Rock Classics", ["vid1", "vid2"])
        p1_atomic_info = {
            "title": "Rock Classics",
            "entries": [
                {"id": "vid1", "title": "Song vid1"},
                {"id": "vid2", "title": "Song vid2"},
                {"id": "vid6", "title": "Song vid6"}
            ]
        }
        with open(os.path.join(p1_folder, "playlist_info_snapshot", "playlist_info.json"), "w", encoding="utf-8") as f:
            json.dump(p1_atomic_info, f, indent=2)

        c = commit_playlist_atomic(p1_folder, "Rock Classics", p1_info, p1_atomic_info, source="manual")
        self.assertTrue(c)

        code, stdout, _ = _run_git_cmd(["log", "-n", "1", "--pretty=format:%s"], self.temp_dir)
        self.assertEqual(code, 0)
        self.assertIn("[On-Demand] Update 'Rock Classics': +1 added", stdout)

    def test_startup_recovery_engine(self):
        """Verify RecoveryService removes stale .git/index.lock and reconciles uncommitted metadata."""
        p1_folder, _ = self._make_playlist("Rock Classics", ["vid1"])

        # Simulate uncommitted file written right before a crash
        p1_crash_info = {
            "title": "Rock Classics",
            "entries": [{"id": "vid1", "title": "Song vid1"}, {"id": "vid99", "title": "Crashed song"}]
        }
        with open(os.path.join(p1_folder, "playlist_info_snapshot", "playlist_info.json"), "w", encoding="utf-8") as f:
            json.dump(p1_crash_info, f, indent=2)

        # Simulate stale .git/index.lock backdated by 120 seconds
        lock_file = os.path.join(self.temp_dir, ".git", "index.lock")
        with open(lock_file, "w") as f:
            f.write("stale_lock")
        old_time = time.time() - 120
        os.utime(lock_file, (old_time, old_time))

        reconciled = RecoveryService.recover_git_metadata(self.temp_dir)
        self.assertTrue(reconciled, "RecoveryService should reconcile uncommitted files")
        self.assertFalse(os.path.exists(lock_file), "Stale index.lock should be cleaned up")

        code, stdout, _ = _run_git_cmd(["log", "-n", "1", "--pretty=format:%B"], self.temp_dir)
        self.assertEqual(code, 0)
        self.assertIn("[Startup Recovery] Reconcile uncommitted playlist metadata after restart", stdout)

    def test_concurrency_and_lock_guards(self):
        """Verify scheduler active scan flag and per-playlist refresh deduplication lock."""
        # Test scheduler scanning state tracking
        _SCHEDULER_STATE["is_scanning"] = True
        self.assertTrue(is_scheduler_scanning())
        _SCHEDULER_STATE["is_scanning"] = False
        self.assertFalse(is_scheduler_scanning())

        # Test active refresh deduplication locking
        playlist_id = 42
        with _REFRESH_LOCK:
            _ACTIVE_REFRESH_PLAYLISTS.clear()
            _ACTIVE_REFRESH_PLAYLISTS.add(playlist_id)

        self.assertIn(playlist_id, _ACTIVE_REFRESH_PLAYLISTS)

        with _REFRESH_LOCK:
            _ACTIVE_REFRESH_PLAYLISTS.discard(playlist_id)

        self.assertNotIn(playlist_id, _ACTIVE_REFRESH_PLAYLISTS)

    def test_sync_git_remote_origin_lifecycle(self):
        """Verify adding, updating, and removing origin in .git/config."""
        # 1. Add origin
        sync_git_remote_origin(self.temp_dir, "https://github.com/user/repo.git", auth_token="ghp_test123", enable_push=True)
        code, stdout, _ = _run_git_cmd(["remote", "get-url", "origin"], self.temp_dir)
        self.assertEqual(code, 0)
        self.assertIn("ghp_test123@github.com/user/repo.git", stdout)

        # 2. Disable push -> origin removed to prevent credential lingering
        sync_git_remote_origin(self.temp_dir, "https://github.com/user/repo.git", auth_token="ghp_test123", enable_push=False)
        code, _, _ = _run_git_cmd(["remote", "get-url", "origin"], self.temp_dir)
        self.assertNotEqual(code, 0, "Origin should be removed when remote push is disabled")

        # 3. Re-add and then clear url
        sync_git_remote_origin(self.temp_dir, "https://github.com/user/repo.git", auth_token=None, enable_push=True)
        code, stdout, _ = _run_git_cmd(["remote", "get-url", "origin"], self.temp_dir)
        self.assertEqual(code, 0)

        sync_git_remote_origin(self.temp_dir, "", enable_push=True)
        code, _, _ = _run_git_cmd(["remote", "get-url", "origin"], self.temp_dir)
        self.assertNotEqual(code, 0, "Origin should be removed when remote URL is cleared")

    def test_remote_push_disabled_guard(self):
        """Verify push_to_remote_sync does not execute git push when ENABLE_GIT_REMOTE_PUSH is False."""
        orig_push = settings.ENABLE_GIT_REMOTE_PUSH
        orig_url = settings.GIT_REMOTE_URL
        try:
            settings.ENABLE_GIT_REMOTE_PUSH = False
            settings.GIT_REMOTE_URL = "https://github.com/user/repo.git"
            success, msg = push_to_remote_sync()
            self.assertTrue(success)
            self.assertIn("disabled", msg.lower())
        finally:
            settings.ENABLE_GIT_REMOTE_PUSH = orig_push
            settings.GIT_REMOTE_URL = orig_url

    def test_test_git_connection_sync_diagnosis(self):
        """Verify intelligent error diagnosis for invalid PAT and non-existent remotes."""
        # Unreachable / invalid host
        success, msg = test_git_connection_sync(
            "https://invalid-nonexistent-domain-12345678.com/repo.git",
            auth_token="dummy_token"
        )
        self.assertFalse(success)
        self.assertTrue(
            "unable to reach" in msg.lower() or "could not resolve host" in msg.lower() or "failed" in msg.lower(),
            f"Expected diagnosis message, got: {msg}"
        )

    def test_batch_link_unmanaged_folders_invalid_url(self):
        """Verify invalid URLs do not write dummy files to disk and remain unmanaged."""
        from app.services.onboarding_service import batch_link_unmanaged_folders, scan_download_directory

        folder_path = os.path.join(self.temp_dir, "unmanaged_custom")
        os.makedirs(folder_path, exist_ok=True)
        with open(os.path.join(folder_path, "sample [abc12345678].mp4"), "w") as f:
            f.write("dummy video data")

        # Linking with an invalid scheme string
        res = batch_link_unmanaged_folders(
            items=[{
                "folder_name": "unmanaged_custom",
                "folder_path": folder_path,
                "playlist_url": "random_garbage_string"
            }]
        )

        self.assertFalse(res["success"])
        self.assertEqual(res["failed_count"], 1)
        self.assertEqual(res["linked_count"], 0)

        # Ensure NO metadata files were dumped to disk
        self.assertFalse(os.path.exists(os.path.join(folder_path, "playlist_info.json")))
        self.assertFalse(os.path.exists(os.path.join(folder_path, "playlist_info_snapshot")))

        # Verify folder is still classified as unmanaged
        scan = scan_download_directory(self.temp_dir)
        unmanaged_names = [f["folder_name"] for f in scan.get("unmanaged_folders", [])]
        self.assertIn("unmanaged_custom", unmanaged_names)

    def test_batch_link_unmanaged_folders_valid_commit(self):
        """Verify valid URL links unmanaged folder, persists playlist to database, and writes metadata."""
        from unittest.mock import patch
        from app.services.onboarding_service import batch_link_unmanaged_folders
        from app.repositories import PlaylistRepository
        from app.models.database import SessionLocal

        folder_path = os.path.join(self.temp_dir, "my_music_collection")
        os.makedirs(folder_path, exist_ok=True)
        with open(os.path.join(folder_path, "Track 1 [12345678901].mp3"), "w") as f:
            f.write("dummy audio")

        mock_info = {
            "title": "My Super Playlist",
            "webpage_url": "https://www.youtube.com/playlist?list=PL_TEST_VALID",
            "playlist_count": 1,
            "entries": [{"id": "12345678901", "title": "Track 1"}]
        }

        with patch("app.core.yt_playlist_audio_tools._get_playlist_info", return_value=mock_info):
            res = batch_link_unmanaged_folders(
                items=[{
                    "folder_name": "my_music_collection",
                    "folder_path": folder_path,
                    "playlist_url": "https://www.youtube.com/playlist?list=PL_TEST_VALID",
                    "rename_folder": False
                }]
            )

        self.assertTrue(res["success"])
        self.assertEqual(res["linked_count"], 1)
        self.assertEqual(res["failed_count"], 0)

        # Verify files on disk
        self.assertTrue(os.path.exists(os.path.join(folder_path, "playlist_info.json")))

        # Verify database persistence across fresh session
        with SessionLocal() as db_session:
            pl = PlaylistRepository.get_by_url(
                url="https://www.youtube.com/playlist?list=PL_TEST_VALID",
                db=db_session
            )
            self.assertIsNotNone(pl, "Playlist should be committed to database")
            self.assertEqual(pl.title, "My Super Playlist")


if __name__ == "__main__":
    unittest.main(verbosity=2)

