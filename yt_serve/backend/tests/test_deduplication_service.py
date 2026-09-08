"""
Unit tests for Deduplication & Hardlink Space Reclaimer Service.
Strictly isolated using in-memory SQLite sandbox (never touches production yt_manager.db).
"""

import unittest
import os
import tempfile
from tests.test_db_helper import create_isolated_test_db, dispose_isolated_test_db
from app.services.deduplication_service import (
    scan_library_duplicates,
    apply_library_deduplication,
    format_bytes,
    are_same_physical_file
)
from app.models.database import Track


class TestDeduplicationService(unittest.TestCase):

    def setUp(self):
        # 100% isolated in-memory test database sandbox
        self.test_engine, self.TestingSession = create_isolated_test_db()
        self.db = self.TestingSession()
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        dispose_isolated_test_db(self.test_engine, self.db)
        self.temp_dir.cleanup()

    def test_format_bytes(self):
        self.assertEqual(format_bytes(500), "500 B")
        self.assertEqual(format_bytes(1536), "1.5 KB")
        self.assertEqual(format_bytes(10485760), "10.0 MB")
        self.assertEqual(format_bytes(2684354560), "2.50 GB")

    def test_scan_and_apply_deduplication(self):
        base_path = self.temp_dir.name

        # Create 3 playlist folders
        pl1 = os.path.join(base_path, "Rock Playlist")
        pl2 = os.path.join(base_path, "Party Playlist")
        pl3 = os.path.join(base_path, "Gym Playlist")
        os.makedirs(pl1, exist_ok=True)
        os.makedirs(pl2, exist_ok=True)
        os.makedirs(pl3, exist_ok=True)

        # Video duplicate: Queen in pl1 and pl2
        queen_pl1 = os.path.join(pl1, "Queen - Bohemian Rhapsody [fJ9rUzIMcZQ].mp4")
        queen_pl2 = os.path.join(pl2, "Queen - Bohemian Rhapsody [fJ9rUzIMcZQ].mp4")
        video_payload = b"X" * 1024 * 100  # 100 KB
        with open(queen_pl1, "wb") as f:
            f.write(video_payload)
        with open(queen_pl2, "wb") as f:
            f.write(video_payload)

        # Audio duplicate: Eminem in pl2 and pl3
        eminem_pl2 = os.path.join(pl2, "Eminem - Lose Yourself [xFYQQPAOz7Y].mp3")
        eminem_pl3 = os.path.join(pl3, "Eminem - Lose Yourself [xFYQQPAOz7Y].mp3")
        audio_payload = b"Y" * 1024 * 50  # 50 KB
        with open(eminem_pl2, "wb") as f:
            f.write(audio_payload)
        with open(eminem_pl3, "wb") as f:
            f.write(audio_payload)

        # Unique song: Beatles only in pl1
        beatles_pl1 = os.path.join(pl1, "Beatles - Yesterday [abcdefghijk].mp3")
        with open(beatles_pl1, "wb") as f:
            f.write(b"Z" * 1024 * 30)

        # 1. Test Scan
        scan_res = scan_library_duplicates(base_path=base_path, db=self.db)
        self.assertEqual(scan_res["status"], "success")
        self.assertEqual(scan_res["total_scanned_files"], 5)
        self.assertEqual(scan_res["duplicate_groups_count"], 2)
        self.assertEqual(scan_res["total_duplicate_files"], 2)
        self.assertEqual(scan_res["reclaimable_bytes"], 1024 * 150)

        # Verify initial files are separate physical files (not yet hardlinked)
        self.assertFalse(are_same_physical_file(queen_pl1, queen_pl2))
        self.assertFalse(are_same_physical_file(eminem_pl2, eminem_pl3))

        # 2. Test Apply Deduplication
        apply_res = apply_library_deduplication(
            duplicate_groups=scan_res["duplicate_groups"],
            base_path=base_path,
            db=self.db
        )
        self.assertEqual(apply_res["status"], "success")
        self.assertEqual(apply_res["files_converted"], 2)
        self.assertEqual(apply_res["space_reclaimed_bytes"], 1024 * 150)

        # Verify files are now zero-space hardlinks (share physical inode)
        self.assertTrue(are_same_physical_file(queen_pl1, queen_pl2))
        self.assertTrue(are_same_physical_file(eminem_pl2, eminem_pl3))

        # Verify content remained 100% identical and readable
        with open(queen_pl2, "rb") as f:
            self.assertEqual(f.read(), video_payload)
        with open(eminem_pl3, "rb") as f:
            self.assertEqual(f.read(), audio_payload)

        # 3. Test Idempotency: Second scan should report 0 redundant copies
        second_scan = scan_library_duplicates(base_path=base_path, db=self.db)
        self.assertEqual(second_scan["status"], "success")
        self.assertEqual(second_scan["total_duplicate_files"], 0)
        self.assertEqual(second_scan["reclaimable_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
