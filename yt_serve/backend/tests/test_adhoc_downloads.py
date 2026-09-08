"""
Unit tests for Ad-hoc Single Video Download & Format Probing Service.
Strictly isolated using in-memory SQLite sandbox (never touches production yt_manager.db).
"""

import unittest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock

from tests.test_db_helper import create_isolated_test_db, dispose_isolated_test_db
from app.services.adhoc_service import (
    format_duration,
    probe_video_info,
    execute_adhoc_download,
    _update_adhoc_metadata
)
from app.repositories import JobRepository, TrackRepository
from app.models.database import Track, Job


class TestAdhocDownloads(unittest.TestCase):

    def setUp(self):
        # 100% isolated in-memory test database sandbox
        self.test_engine, self.TestingSession = create_isolated_test_db()
        self.db = self.TestingSession()
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        dispose_isolated_test_db(self.test_engine, self.db)
        self.temp_dir.cleanup()

    def test_format_duration(self):
        self.assertEqual(format_duration(0), "00:00")
        self.assertEqual(format_duration(65), "01:05")
        self.assertEqual(format_duration(3665), "01:01:05")

    @patch("yt_dlp.YoutubeDL")
    def test_probe_video_info(self, mock_ydl_class):
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = {
            "id": "probeTest123",
            "title": "Probe Test Video Title",
            "uploader": "Test Channel",
            "duration": 245,
            "thumbnail": "https://example.com/thumb.jpg",
            "view_count": 15000,
            "description": "Video description test snippet",
            "formats": [
                {"height": 2160, "vcodec": "avc1"},
                {"height": 1080, "vcodec": "avc1"},
                {"height": 720, "vcodec": "avc1"},
                {"height": 360, "vcodec": "avc1"},
            ]
        }
        mock_ydl_class.return_value.__enter__.return_value = mock_instance

        res = probe_video_info("https://www.youtube.com/watch?v=probeTest123")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["video_id"], "probeTest123")
        self.assertEqual(res["title"], "Probe Test Video Title")
        self.assertEqual(res["formatted_duration"], "04:05")
        self.assertEqual(len(res["available_resolutions"]), 4)
        self.assertEqual(res["available_resolutions"][0]["height"], 2160)
        self.assertEqual(res["available_resolutions"][0]["label"], "2160p (4K UHD)")

    def test_update_adhoc_metadata(self):
        target_dir = self.temp_dir.name
        video_info = {
            "id": "metaVid999",
            "title": "Metadata Song",
            "uploader": "Artist Nine",
            "duration": 180
        }
        dummy_file = os.path.join(target_dir, "Metadata Song [metaVid999].mp4")
        with open(dummy_file, "wb") as f:
            f.write(b"data")

        _update_adhoc_metadata(
            target_dir=target_dir,
            video_info=video_info,
            filepath=dummy_file
        )

        # Check archive.txt
        archive_path = os.path.join(target_dir, "archive.txt")
        self.assertTrue(os.path.isfile(archive_path))
        with open(archive_path, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("youtube metaVid999", content)

        # Check adhoc_info.json
        json_path = os.path.join(target_dir, "adhoc_info.json")
        self.assertTrue(os.path.isfile(json_path))
        with open(json_path, "r", encoding="utf-8") as f:
            entries = json.load(f)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["id"], "metaVid999")
            self.assertEqual(entries[0]["title"], "Metadata Song")

    @patch("yt_dlp.YoutubeDL")
    def test_execute_adhoc_download(self, mock_ydl_class):
        target_dir = self.temp_dir.name
        mock_instance = MagicMock()
        mock_info = {
            "id": "adhocExec123",
            "title": "Adhoc Executed Song",
            "uploader": "Exec Artist",
            "duration": 210,
            "ext": "mp4"
        }
        mock_instance.extract_info.return_value = mock_info
        out_file = os.path.join(target_dir, "Adhoc Executed Song [adhocExec123].mp4")
        mock_instance.prepare_filename.return_value = out_file
        mock_ydl_class.return_value.__enter__.return_value = mock_instance

        # Create dummy file so os.path.isfile is true
        with open(out_file, "wb") as f:
            f.write(b"test_payload")

        # Create Job in isolated DB
        job = JobRepository.create(playlist_id=0, job_type="adhoc_video_only", total_items=1, db=self.db)

        # Execute
        res = execute_adhoc_download(
            job_id=job.id,
            url="https://youtube.com/watch?v=adhocExec123",
            video_quality="1080",
            extract_mode="video_only",
            custom_download_path=target_dir,
            db=self.db
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["video_id"], "adhocExec123")

        # Verify Job updated to completed
        updated_job = JobRepository.get_by_id(job.id, db=self.db)
        self.assertEqual(updated_job.status, "completed")
        self.assertEqual(updated_job.completed_items, 1)

        # Verify Track index registration
        indexed_track = TrackRepository.get_by_video_id("adhocExec123", db=self.db)
        self.assertIsNotNone(indexed_track)
        self.assertEqual(indexed_track.title, "Adhoc Executed Song")


if __name__ == "__main__":
    unittest.main()
