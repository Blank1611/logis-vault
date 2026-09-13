import unittest
import os
import json
import tempfile
from tests.test_db_helper import create_isolated_test_db, dispose_isolated_test_db
from app.models.database import Playlist, Track, SystemSetting, get_system_setting, set_system_setting
from app.services.onboarding_service import (
    extract_video_id_from_filename,
    scan_download_directory,
    ingest_discovered_library
)
from app.api.config import _check_needs_setup

class TestOnboardingService(unittest.TestCase):

    def setUp(self):
        # 100% isolated in-memory test database sandbox
        self.test_engine, self.TestingSession = create_isolated_test_db()
        self.db = self.TestingSession()
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        dispose_isolated_test_db(self.test_engine, self.db)
        self.temp_dir.cleanup()

    def test_extract_video_id(self):
        self.assertEqual(extract_video_id_from_filename("Artist - Song [dQw4w9WgXcQ].mp4"), "dQw4w9WgXcQ")
        self.assertEqual(extract_video_id_from_filename("Never Gonna Give You Up [abcdefghijk].mp3"), "abcdefghijk")
        self.assertEqual(extract_video_id_from_filename("Track_1234567890a.mp4"), "1234567890a")
        self.assertIsNone(extract_video_id_from_filename("invalid_filename.mp4"))

    def test_scan_and_ingest_existing_library(self):
        # Create Playlist A folder (Managed with playlist_info.json)
        pl_a = os.path.join(self.temp_dir.name, "Classic Rock")
        os.makedirs(pl_a, exist_ok=True)
        with open(os.path.join(pl_a, "playlist_info.json"), "w") as f:
            json.dump({
                "title": "Classic Rock Hits",
                "webpage_url": "https://www.youtube.com/playlist?list=PL_ROCK_123",
                "playlist_count": 2
            }, f)
        # Create media file in Playlist A
        with open(os.path.join(pl_a, "Queen - Bohemian Rhapsody [fJ9rUzIMcZQ].mp4"), "w") as f:
            f.write("dummy video stream")

        # Create Playlist B folder (Unmanaged without playlist_info.json)
        pl_b = os.path.join(self.temp_dir.name, "Workout Tracks")
        os.makedirs(pl_b, exist_ok=True)
        # Create media file in Playlist B
        with open(os.path.join(pl_b, "Eminem - Lose Yourself [xFYQQPAOz7Y].mp3"), "w") as f:
            f.write("dummy audio stream")

        # 1. Scan directory
        scan_res = scan_download_directory(self.temp_dir.name)
        self.assertTrue(scan_res["exists"])
        # Strict qualification: Only Playlist A qualifies as discovered playlist
        self.assertEqual(scan_res["discovered_playlists_count"], 1)
        self.assertEqual(scan_res["unmanaged_folders_count"], 1)

        # Verify Playlist A parsed metadata
        found_a = scan_res["discovered_playlists"][0]
        self.assertEqual(found_a["title"], "Classic Rock Hits")
        self.assertEqual(found_a["url"], "https://www.youtube.com/playlist?list=PL_ROCK_123")
        self.assertEqual(found_a["video_count"], 1)

        # Verify Playlist B is classified in unmanaged_folders
        found_b = scan_res["unmanaged_folders"][0]
        self.assertEqual(found_b["folder_name"], "Workout Tracks")
        self.assertEqual(found_b["audio_count"], 1)

        # 2. Ingest discovered playlists into isolated test SQLite database
        ingest_res = ingest_discovered_library(discovered_items=scan_res["discovered_playlists"], db=self.db)
        self.assertEqual(ingest_res["status"], "success")
        self.assertEqual(ingest_res["playlists_imported"], 1)
        self.assertEqual(ingest_res["tracks_indexed"], 1)

        # 3. Test batch linking the unmanaged folder (Playlist B)
        from app.services.onboarding_service import batch_link_unmanaged_folders
        link_res = batch_link_unmanaged_folders(
            items=[{
                "folder_path": pl_b,
                "playlist_url": "https://www.youtube.com/playlist?list=PL_WORKOUT_456"
            }],
            db=self.db
        )
        self.assertTrue(link_res["success"])
        self.assertEqual(link_res["linked_count"], 1)

        # Verify playlist_info.json was written to disk
        self.assertTrue(os.path.isfile(os.path.join(pl_b, "playlist_info.json")))

        # Verify records in isolated database (now both playlists are present and indexed)
        db_playlists = self.db.query(Playlist).all()
        self.assertEqual(len(db_playlists), 2)

        db_tracks = self.db.query(Track).all()
        self.assertEqual(len(db_tracks), 2)
        track_ids = {t.video_id for t in db_tracks}
        self.assertIn("fJ9rUzIMcZQ", track_ids)
        self.assertIn("xFYQQPAOz7Y", track_ids)

    def test_system_settings_and_needs_setup(self):
        val = get_system_setting("setup_completed", default="false", db=self.db)
        self.assertEqual(val, "false")

        # Set setup_completed in isolated test DB
        set_system_setting("setup_completed", "true", db=self.db)
        val2 = get_system_setting("setup_completed", default="false", db=self.db)
        self.assertEqual(val2, "true")

        # Check needs_setup is now false
        needs_setup = _check_needs_setup(db=self.db)
        self.assertFalse(needs_setup)

    def test_phantom_playlist_safe_purge(self):
        from app.services.recovery_service import RecoveryService
        # Create phantom record in DB
        phantom = Playlist(
            title="test_custom",
            url="https://www.youtube.com/playlist?list=test_custom",
            playlist_count=0,
            local_count=0
        )
        self.db.add(phantom)
        self.db.commit()
        self.assertEqual(self.db.query(Playlist).count(), 1)

        # Create dummy directory on disk for test_custom
        custom_dir = os.path.join(self.temp_dir.name, "test_custom")
        os.makedirs(custom_dir, exist_ok=True)
        dummy_file = os.path.join(custom_dir, "keep_me.txt")
        with open(dummy_file, "w") as f:
            f.write("user data that must never be deleted")

        # Run recovery phantom cleanup
        purged = RecoveryService.cleanup_phantom_playlists(self.db)
        self.assertEqual(purged, 1)

        # Verify record was purged from DB
        self.assertEqual(self.db.query(Playlist).count(), 0)

        # Verify disk folder and files remain 100% intact (zero disk deletion guarantee)
        self.assertTrue(os.path.isdir(custom_dir))
        self.assertTrue(os.path.isfile(dummy_file))

if __name__ == "__main__":
    unittest.main()

