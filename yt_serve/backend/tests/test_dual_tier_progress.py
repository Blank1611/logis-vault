import unittest
import time
from app.core import yt_playlist_audio_tools as tools
from app.models.database import SessionLocal, Job, _auto_migrate_sqlite_columns

class TestDualTierProgress(unittest.TestCase):

    def setUp(self):
        _auto_migrate_sqlite_columns()
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()
        tools.GLOBAL_INFLIGHT_PROGRESS_CALLBACK = None

    def test_inflight_progress_hook_callback(self):
        captured = []

        def mock_callback(vid, title, bytes_done, bytes_total, speed, eta):
            captured.append({
                "vid": vid,
                "title": title,
                "bytes_done": bytes_done,
                "bytes_total": bytes_total,
                "speed": speed,
                "eta": eta
            })

        tools.GLOBAL_INFLIGHT_PROGRESS_CALLBACK = mock_callback
        tools._LAST_INFLIGHT_TICK_TIME = 0.0

        # Simulate yt-dlp downloading hook dict
        d = {
            "status": "downloading",
            "downloaded_bytes": 1048576,
            "total_bytes": 10485760,
            "speed": 5242880.0,
            "eta": 2,
            "info_dict": {
                "id": "abc123xyz",
                "title": "Awesome Track"
            }
        }

        tools._progress_hook_custom(d)

        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0]["vid"], "abc123xyz")
        self.assertEqual(captured[0]["title"], "Awesome Track")
        self.assertEqual(captured[0]["bytes_done"], 1048576)
        self.assertEqual(captured[0]["bytes_total"], 10485760)
        self.assertEqual(captured[0]["speed"], 5242880.0)
        self.assertEqual(captured[0]["eta"], 2)

    def test_job_model_inflight_fields(self):
        test_job = Job(
            playlist_id=9999,
            job_type="download",
            status="running",
            current_video_title="In-Flight Track",
            current_video_id="video99",
            current_video_bytes_downloaded=5000000,
            current_video_bytes_total=10000000,
            current_video_speed=2500000.0,
            current_video_eta=2
        )
        self.db.add(test_job)
        self.db.commit()

        retrieved = self.db.query(Job).filter(Job.id == test_job.id).first()
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.current_video_title, "In-Flight Track")
        self.assertEqual(retrieved.current_video_id, "video99")
        self.assertEqual(retrieved.current_video_bytes_downloaded, 5000000)
        self.assertEqual(retrieved.current_video_bytes_total, 10000000)
        self.assertEqual(retrieved.current_video_speed, 2500000.0)
        self.assertEqual(retrieved.current_video_eta, 2)

        # Cleanup
        self.db.delete(retrieved)
        self.db.commit()

if __name__ == "__main__":
    unittest.main()
