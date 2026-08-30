"""
Unit tests for Central Data Access Layer (DAL) Repositories and Session Context Manager.
Strictly isolated using in-memory SQLite sandbox.
"""
import unittest
from tests.test_db_helper import create_isolated_test_db
from app.repositories import (
    PlaylistRepository,
    TrackRepository,
    JobRepository,
    SystemSettingRepository
)
from app.models.database import get_db_context


class TestRepositories(unittest.TestCase):

    def setUp(self):
        self.test_engine, self.TestingSession = create_isolated_test_db()
        self.db = self.TestingSession()

    def tearDown(self):
        self.db.close()

    def test_playlist_repository(self):
        # Create playlist
        pl = PlaylistRepository.create(
            url="https://youtube.com/playlist?list=PL_TEST",
            title="Repo Test Playlist",
            local_count=10,
            playlist_count=15,
            db=self.db
        )
        self.assertIsNotNone(pl.id)
        self.assertEqual(pl.title, "Repo Test Playlist")

        # Fetch by ID
        fetched = PlaylistRepository.get_by_id(pl.id, db=self.db)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.url, "https://youtube.com/playlist?list=PL_TEST")

        # Fetch by URL or Title
        fetched_or = PlaylistRepository.get_by_url_or_title(
            url="https://youtube.com/playlist?list=PL_TEST",
            title="Non-existent",
            db=self.db
        )
        self.assertIsNotNone(fetched_or)

        # Update counts
        updated = PlaylistRepository.update_counts(pl.id, local_count=12, playlist_count=15, db=self.db)
        self.assertEqual(updated.local_count, 12)

        # Delete
        success = PlaylistRepository.delete(pl.id, db=self.db)
        self.assertTrue(success)
        self.assertIsNone(PlaylistRepository.get_by_id(pl.id, db=self.db))

    def test_track_repository(self):
        # Index track
        track = TrackRepository.index_or_update_track(
            video_id="repoVid123",
            title="Repository Track",
            filepath="/tmp/track.mp4",
            playlist_id=1,
            db=self.db
        )
        self.assertEqual(track.video_id, "repoVid123")
        self.assertIn(1, track.playlists_json)

        # Search tracks
        tracks = TrackRepository.get_all_tracks(search="Repository", db=self.db)
        self.assertEqual(len(tracks), 1)

        # Record move history
        hist = TrackRepository.record_move_history(
            video_id="repoVid123",
            title="Repository Track",
            from_playlist_id=1,
            from_playlist_title="PL1",
            to_playlist_id=2,
            to_playlist_title="PL2",
            db=self.db
        )
        self.assertEqual(hist.status, "auto_moved")
        all_hist = TrackRepository.get_move_history(db=self.db)
        self.assertEqual(len(all_hist), 1)

    def test_job_repository(self):
        # Create job
        job = JobRepository.create(
            playlist_id=1,
            job_type="download",
            total_items=50,
            db=self.db
        )
        self.assertEqual(job.status, "pending")
        self.assertIsNotNone(job.id)

        # Update stream progress
        JobRepository.update_stream_progress(
            job_id=job.id,
            title="In Flight Song",
            bytes_downloaded=1024000,
            speed=4.5,
            eta=12,
            db=self.db
        )

        fetched = JobRepository.get_by_id(job.id, db=self.db)
        self.assertEqual(fetched.current_video_title, "In Flight Song")
        self.assertEqual(fetched.current_video_speed, 4.5)

        # Update status
        JobRepository.update_status(job_id=job.id, status="completed", completed_items=50, db=self.db)
        completed_job = JobRepository.get_by_id(job.id, db=self.db)
        self.assertEqual(completed_job.status, "completed")

    def test_system_setting_repository(self):
        # Set setting
        SystemSettingRepository.set("theme", "dark", db=self.db)
        val = SystemSettingRepository.get("theme", db=self.db)
        self.assertEqual(val, "dark")

        # Default fallback
        non_existent = SystemSettingRepository.get("missing_key", default="fallback", db=self.db)
        self.assertEqual(non_existent, "fallback")

    def test_get_db_context_rollback_on_error(self):
        # Context manager rollback verification using fresh session
        try:
            with get_db_context() as session:
                PlaylistRepository.create(url="https://youtube.com/pl_fail", title="Will Rollback", db=session)
                raise RuntimeError("Intentional transaction failure")
        except RuntimeError:
            pass

        # Verify rollback worked
        pl = PlaylistRepository.get_by_url("https://youtube.com/pl_fail", db=self.db)
        self.assertIsNone(pl)


if __name__ == "__main__":
    unittest.main()
