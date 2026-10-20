"""
Full Container Image Contract & End-to-End Integration Tests.

Test Scope:
    This test suite validates capabilities that require the full production/development
    container build ('logis-vault:dev' or 'logis-vault:latest'), including:
    1. Node.js runtime availability (v22+ LTS) copied from frontend-builder stage.
    2. yt-dlp JavaScript runtime challenge options ('js_runtimes': {'node': {}}).
    3. End-to-end Ad-hoc Job persistence and multi-session durability across distinct DB connections.
    4. Active download queue retrieval via JobRepository.

Execution Instructions:
    These tests are designed to run within the compiled dev/prod image:
        docker run --rm logis-vault:dev python -m unittest tests/test_full_image_contract.py
"""

import unittest
import shutil
import subprocess
from app.models.database import SessionLocal, Job
from app.repositories import JobRepository
from app.utils.ytdlp_opts import build_ytdlp_options


class TestFullImageContract(unittest.TestCase):
    """Integration contract tests for the full containerized environment"""

    def test_nodejs_runtime_available_and_valid_version(self):
        """Verify Node.js v22+ is present in PATH for yt-dlp EJS challenges"""
        node_path = shutil.which("node")
        self.assertIsNotNone(node_path, "Node.js binary must be present in runner PATH")

        version_output = subprocess.check_output([node_path, "-v"], text=True).strip()
        self.assertTrue(version_output.startswith("v"), f"Unexpected node version string: {version_output}")
        major_version = int(version_output.lstrip("v").split(".")[0])
        self.assertGreaterEqual(major_version, 22, f"Node.js version must be >= 22.0.0, got: {version_output}")

    def test_ytdlp_options_injects_nodejs_runtime(self):
        """Verify yt-dlp option generator registers the node JS runtime"""
        opts = build_ytdlp_options(mode="download", playlist_folder="/tmp")
        self.assertIn("js_runtimes", opts)
        self.assertIn("node", opts["js_runtimes"])

    def test_adhoc_job_cross_session_durability(self):
        """Verify Ad-hoc Job creation, stream progress, and completion are durable across independent sessions"""
        job_id = None
        # Session 1: Create ad-hoc job (simulate POST /api/downloads/adhoc/start)
        with SessionLocal() as s1:
            job = JobRepository.create(
                playlist_id=0,
                job_type="adhoc_both",
                total_items=1,
                db=s1
            )
            job_id = job.id
            self.assertIsNotNone(job_id)
            self.assertEqual(job.status, "pending")

        # Session 2: Read from a separate session (simulate GET /api/downloads/jobs polled by frontend)
        with SessionLocal() as s2:
            fetched = JobRepository.get_by_id(job_id, db=s2)
            self.assertIsNotNone(fetched, f"Job #{job_id} must be durable and readable from fresh session")
            self.assertEqual(fetched.job_type, "adhoc_both")
            self.assertEqual(fetched.status, "pending")

            # Check that job is returned in the active queue list
            all_adhoc = JobRepository.get_all(playlist_id=0, db=s2)
            matching = [j for j in all_adhoc if j.id == job_id]
            self.assertEqual(len(matching), 1, "Ad-hoc job must be queryable in active queue list")

        # Session 3: Update live byte stream progress (simulate in-flight yt-dlp hook)
        with SessionLocal() as s3:
            JobRepository.update_stream_progress(
                job_id=job_id,
                title="Full Image Contract Video",
                video_id="fullContract123",
                bytes_downloaded=10485760,
                bytes_total=20971520,
                speed=4194304.0,
                eta=2,
                db=s3
            )

        # Session 4: Read telemetry from another session (simulate frontend progress bar poll)
        with SessionLocal() as s4:
            telemetry_job = JobRepository.get_by_id(job_id, db=s4)
            self.assertEqual(telemetry_job.current_video_title, "Full Image Contract Video")
            self.assertEqual(telemetry_job.current_video_bytes_downloaded, 10485760)
            self.assertEqual(telemetry_job.current_video_speed, 4194304.0)

        # Session 5: Mark completed
        with SessionLocal() as s5:
            JobRepository.update_status(job_id=job_id, status="completed", completed_items=1, db=s5)

        # Session 6: Verify final completion state
        with SessionLocal() as s6:
            completed_job = JobRepository.get_by_id(job_id, db=s6)
            self.assertEqual(completed_job.status, "completed")
            self.assertEqual(completed_job.completed_items, 1)


if __name__ == "__main__":
    unittest.main()
