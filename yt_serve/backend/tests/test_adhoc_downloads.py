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
    _update_adhoc_metadata,
    find_existing_local_video,
    extract_audio_from_video
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

    def test_find_existing_local_video(self):
        target_dir = self.temp_dir.name
        vid = "foundVid123"
        video_file = os.path.join(target_dir, f"Artist - Song [{vid}] [1080p].mp4")
        with open(video_file, "wb") as f:
            f.write(b"video_bytes")

        # Must find in directory
        found = find_existing_local_video(target_dir, vid, db=self.db)
        self.assertEqual(found, video_file)

        # Must return None for non-existent video
        notFound = find_existing_local_video(target_dir, "nonExistent999", db=self.db)
        self.assertIsNone(notFound)

    @patch("subprocess.run")
    @patch("app.core.track_indexer.probe_local_media_metadata")
    def test_extract_audio_from_video_opus(self, mock_probe, mock_subproc):
        target_dir = self.temp_dir.name
        video_file = os.path.join(target_dir, "Nikke Song [zvPf3vyjkd0] [2160p].mp4")
        with open(video_file, "wb") as f:
            f.write(b"mp4_content")

        # Simulate audio codec is opus in webm/dash
        mock_probe.return_value = {"audio_codec": "opus", "audio_bitrate": 160000}

        # Create target audio file upon mock ffmpeg run
        expected_audio = os.path.join(target_dir, "Nikke Song [zvPf3vyjkd0] [2160p].opus")
        def fake_ffmpeg(cmd, **kwargs):
            with open(expected_audio, "wb") as f:
                f.write(b"opus_content")
            return MagicMock(returncode=0)
        mock_subproc.side_effect = fake_ffmpeg

        res = extract_audio_from_video(video_file, audio_format="copy")
        self.assertEqual(res, expected_audio)
        self.assertTrue(os.path.isfile(expected_audio))

        # Verify ffmpeg was called with -c:a copy into .opus
        last_call_cmd = mock_subproc.call_args[0][0]
        self.assertIn("-c:a", last_call_cmd)
        self.assertIn("copy", last_call_cmd)
        self.assertTrue(last_call_cmd[-1].endswith(".opus"))

    @patch("app.services.adhoc_service.extract_audio_from_video")
    @patch("yt_dlp.YoutubeDL")
    def test_audio_only_local_fast_path(self, mock_ydl_class, mock_extract_audio):
        target_dir = self.temp_dir.name
        vid = "fastPathVid123"
        video_file = os.path.join(target_dir, f"Local Video Title [{vid}] [1080p].mp4")
        with open(video_file, "wb") as f:
            f.write(b"fast_path_data")

        expected_audio = os.path.join(target_dir, f"Local Video Title [{vid}] [1080p].opus")
        mock_extract_audio.return_value = expected_audio

        # Create Job in isolated DB
        job = JobRepository.create(playlist_id=0, job_type="adhoc_audio_only", total_items=1, db=self.db)

        # Execute audio-only
        res = execute_adhoc_download(
            job_id=job.id,
            url=f"https://www.youtube.com/watch?v={vid}",
            audio_format="copy",
            extract_mode="audio_only",
            custom_download_path=target_dir,
            db=self.db
        )

        self.assertEqual(res["status"], "success")
        self.assertEqual(res["filepath"], expected_audio)

        # YoutubeDL must NEVER be called because video was local!
        mock_ydl_class.assert_not_called()

        # Job completed
        updated_job = JobRepository.get_by_id(job.id, db=self.db)
        self.assertEqual(updated_job.status, "completed")


if __name__ == "__main__":
    unittest.main()
