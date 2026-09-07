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
    ensure_git_repo
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
        self.assertIn("BASE_DOWNLOAD_PATH=/downloads", content)
        self.assertIn("AUDIO_EXTRACT_MODE=copy", content)
        self.assertIn("ENABLE_GIT_METADATA_SYNC=false", content)
        self.assertIn("# Scheduled daily scan time in HH:MM format", content)

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


if __name__ == "__main__":
    unittest.main(verbosity=2)

