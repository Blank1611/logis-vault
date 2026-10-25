"""
Unit tests for Central Data Access Layer (DAL) Repositories and Session Context Manager.
Strictly isolated using in-memory SQLite sandbox.
"""
import unittest
from tests.test_db_helper import create_isolated_test_db, dispose_isolated_test_db
from app.repositories import (
    PlaylistRepository,
    TrackRepository,
    JobRepository,
    SystemSettingRepository,
    FolderStatusRepository
)
from app.models.database import Playlist, Job, get_db_context


class TestRepositories(unittest.TestCase):

    def setUp(self):
        self.test_engine, self.TestingSession = create_isolated_test_db()
        self.db = self.TestingSession()

    def tearDown(self):
        dispose_isolated_test_db(self.test_engine, self.db)

    def test_cross_session_job_durability(self):
        """Verify repository mutations persist immediately and are readable from independent sessions"""
        session_a = self.TestingSession()
        # 1. Create job using session A without manual caller commit
        job = JobRepository.create(
            playlist_id=999,
            job_type="adhoc_both",
            total_items=1,
            db=session_a
        )
        job_id = job.id
        session_a.close()

        # 2. Query from a completely fresh session B
        session_b = self.TestingSession()
        fetched_b = JobRepository.get_by_id(job_id, db=session_b)
        self.assertIsNotNone(fetched_b)
        self.assertEqual(fetched_b.job_type, "adhoc_both")
        self.assertEqual(fetched_b.status, "pending")

        # 3. Update stream metrics with session A
        session_a = self.TestingSession()
        JobRepository.update_stream_progress(
            job_id=job_id,
            title="Live Video Title",
            bytes_downloaded=5000000,
            bytes_total=10000000,
            speed=2.5,
            eta=2,
            db=session_a
        )
        session_a.close()

        # 4. Independent session B sees updated metrics immediately
        session_b.expire_all()
        fetched_after_progress = JobRepository.get_by_id(job_id, db=session_b)
        self.assertEqual(fetched_after_progress.current_video_title, "Live Video Title")
        self.assertEqual(fetched_after_progress.current_video_speed, 2.5)

        # 5. Complete job via session A
        session_a = self.TestingSession()
        JobRepository.update_status(job_id=job_id, status="completed", completed_items=1, db=session_a)
        session_a.close()

        # 6. Independent session B sees completed status
        session_b.expire_all()
        final_job = JobRepository.get_by_id(job_id, db=session_b)
        self.assertEqual(final_job.status, "completed")
        session_b.close()

    def test_folder_status_repository(self):
        """Verify FolderStatusRepository CRUD and durability"""
        # Set status
        record = FolderStatusRepository.set("MyExcludedPlaylist", "excluded", reason="user_test", db=self.db)
        self.assertIsNotNone(record)
        self.assertEqual(record.status, "excluded")

        # Get status
        fetched = FolderStatusRepository.get("MyExcludedPlaylist", db=self.db)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.reason, "user_test")

        # List statuses
        excluded_list = FolderStatusRepository.list(status="excluded", db=self.db)
        self.assertEqual(len(excluded_list), 1)

        # Remove status
        removed = FolderStatusRepository.remove("MyExcludedPlaylist", db=self.db)
        self.assertTrue(removed)
        self.assertIsNone(FolderStatusRepository.get("MyExcludedPlaylist", db=self.db))

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

        # Update general
        updated_gen = PlaylistRepository.update(pl.id, title="Renamed Playlist", db=self.db)
        self.assertEqual(updated_gen.title, "Renamed Playlist")

        # Delete
        success = PlaylistRepository.delete(pl.id, db=self.db)
        self.assertTrue(success)
        self.assertIsNone(PlaylistRepository.get_by_id(pl.id, db=self.db))

    def test_track_repository(self):
        # Create playlist
        pl = PlaylistRepository.create(
            url="https://youtube.com/playlist?list=PL_TEST_REPO",
            title="Repo PL",
            db=self.db
        )
        # Index track
        track = TrackRepository.index_or_update_track(
            video_id="repoVid123",
            title="Repository Track",
            filepath="/tmp/track.mp4",
            playlist_id=pl.id,
            db=self.db
        )
        self.assertEqual(track.video_id, "repoVid123")
        self.assertIn(pl.id, track.playlists_json)

        # Search tracks
        tracks = TrackRepository.get_all_tracks(search="Repository", db=self.db)
        self.assertEqual(len(tracks), 1)
        self.assertEqual(TrackRepository.count_tracks(search="Repository", db=self.db), 1)

        # Get playlist tracks
        pl_tracks = TrackRepository.get_playlist_tracks(pl.id, db=self.db)
        self.assertEqual(len(pl_tracks), 1)
        self.assertEqual(pl_tracks[0][0].video_id, "repoVid123")

        # Get tracks by playlist id
        tracks_by_pl = TrackRepository.get_tracks_by_playlist_id(pl.id, db=self.db)
        self.assertEqual(len(tracks_by_pl), 1)
        self.assertEqual(tracks_by_pl[0].video_id, "repoVid123")

        # Test multi-playlist tracks (associate with second playlist)
        pl2 = PlaylistRepository.create(
            url="https://youtube.com/playlist?list=PL_TEST_REPO_2",
            title="Repo PL 2",
            db=self.db
        )
        TrackRepository.index_or_update_track(
            video_id="repoVid123",
            title="Repository Track",
            filepath="/tmp/track.mp4",
            playlist_id=pl2.id,
            db=self.db
        )
        multi = TrackRepository.get_multi_playlist_tracks(db=self.db)
        self.assertEqual(len(multi), 1)
        self.assertEqual(multi[0].video_id, "repoVid123")

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
        self.assertEqual(TrackRepository.count_move_history(db=self.db), 1)

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

        # Active jobs count and query
        self.assertEqual(JobRepository.count_active(db=self.db), 1)
        active_job = JobRepository.get_active_job_for_playlist(1, db=self.db)
        self.assertIsNotNone(active_job)
        self.assertEqual(active_job.id, job.id)

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

        # Update progress
        JobRepository.update_progress(
            job_id=job.id,
            download_total=50,
            download_completed=25,
            download_status="running",
            db=self.db
        )
        in_prog = JobRepository.get_by_id(job.id, db=self.db)
        self.assertEqual(in_prog.download_completed, 25)

        # Stats by type and status
        stats = JobRepository.get_stats_by_type_and_status(db=self.db)
        self.assertTrue(any(s[0] == "download" for s in stats))

        # Update status
        JobRepository.update_status(job_id=job.id, status="completed", completed_items=50, db=self.db)
        completed_job = JobRepository.get_by_id(job.id, db=self.db)
        self.assertEqual(completed_job.status, "completed")
        self.assertEqual(JobRepository.count_active(db=self.db), 0)

        # Delete job
        self.assertTrue(JobRepository.delete(job.id, db=self.db))
        self.assertIsNone(JobRepository.get_by_id(job.id, db=self.db))

    def test_system_setting_repository(self):
        # Set setting
        SystemSettingRepository.set("theme", "dark", db=self.db)
        val = SystemSettingRepository.get("theme", db=self.db)
        self.assertEqual(val, "dark")

        # Default fallback
        non_existent = SystemSettingRepository.get("missing_key", default="fallback", db=self.db)
        self.assertEqual(non_existent, "fallback")

    def test_get_db_context_rollback_on_error(self):
        # Context manager rollback verification
        test_url = "https://youtube.com/pl_fail_rollback_test"
        try:
            with get_db_context(self.db) as session:
                pl = Playlist(url=test_url, title="Will Rollback")
                session.add(pl)
                session.flush()
                raise RuntimeError("Intentional transaction failure")
        except RuntimeError:
            self.db.rollback()

        # Verify rollback worked
        pl = self.db.query(Playlist).filter(Playlist.url == test_url).first()
        self.assertIsNone(pl)


if __name__ == "__main__":
    unittest.main()
