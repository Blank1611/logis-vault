import unittest
import os
import json
import tempfile
from tests.test_db_helper import create_isolated_test_db
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
        self.db.close()
        self.temp_dir.cleanup()

    def test_extract_video_id(self):
        self.assertEqual(extract_video_id_from_filename("Artist - Song [dQw4w9WgXcQ].mp4"), "dQw4w9WgXcQ")
        self.assertEqual(extract_video_id_from_filename("Never Gonna Give You Up [abcdefghijk].mp3"), "abcdefghijk")
        self.assertEqual(extract_video_id_from_filename("Track_1234567890a.mp4"), "1234567890a")
        self.assertIsNone(extract_video_id_from_filename("invalid_filename.mp4"))

    def test_scan_and_ingest_existing_library(self):
        # Create Playlist A folder
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

        # Create Playlist B folder
        pl_b = os.path.join(self.temp_dir.name, "Workout Tracks")
        os.makedirs(pl_b, exist_ok=True)
        # Create media file in Playlist B
        with open(os.path.join(pl_b, "Eminem - Lose Yourself [xFYQQPAOz7Y].mp3"), "w") as f:
            f.write("dummy audio stream")

        # 1. Scan directory
        scan_res = scan_download_directory(self.temp_dir.name)
        self.assertTrue(scan_res["exists"])
        self.assertEqual(scan_res["discovered_playlists_count"], 2)

        # Verify Playlist A parsed metadata
        found_a = next(p for p in scan_res["discovered_playlists"] if p["folder_name"] == "Classic Rock")
        self.assertEqual(found_a["title"], "Classic Rock Hits")
        self.assertEqual(found_a["url"], "https://www.youtube.com/playlist?list=PL_ROCK_123")
        self.assertEqual(found_a["video_count"], 1)

        # 2. Ingest into isolated test SQLite database
        ingest_res = ingest_discovered_library(discovered_items=scan_res["discovered_playlists"], db=self.db)
        self.assertEqual(ingest_res["status"], "success")
        self.assertEqual(ingest_res["playlists_imported"], 2)
        self.assertEqual(ingest_res["tracks_indexed"], 2)

        # Verify records in isolated database
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

if __name__ == "__main__":
    unittest.main()
