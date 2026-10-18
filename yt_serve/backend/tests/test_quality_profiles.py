"""
Unit & Integration Tests for Radarr/Sonarr-style Quality Profiles and Track Upgrades
"""
import unittest
from fastapi.testclient import TestClient

from app.main import app
from app.models.database import SessionLocal, QualityProfile, Playlist, Track
from app.services.adhoc_service import sanitize_youtube_url
from app.repositories.profile_repo import QualityProfileRepository


class TestQualityProfilesContract(unittest.TestCase):
    """Test Quality Profile models, repository operations, and REST endpoints"""

    def setUp(self):
        self.client = TestClient(app)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_seeded_builtin_profiles(self):
        """Verify standard built-in profiles are auto-seeded on database initialization"""
        profiles = QualityProfileRepository.get_all(self.db)
        profile_ids = {p.id for p in profiles}
        expected_ids = {"ultra_4k", "qhd_1440p", "standard_1080p", "standard_720p", "fast_mixtape_360p", "audio_only"}
        self.assertTrue(expected_ids.issubset(profile_ids), f"Missing built-in profiles: {expected_ids - profile_ids}")

        # Check fast_mixtape_360p cipher strategy
        fast_prof = QualityProfileRepository.get_by_id("fast_mixtape_360p", self.db)
        self.assertIsNotNone(fast_prof)
        self.assertEqual(fast_prof.cipher_strategy, "direct_format18")
        self.assertEqual(fast_prof.max_resolution, 360)

    def test_profile_crud_endpoints(self):
        """Test creating, fetching, updating, and deleting a custom profile"""
        # 1. Create
        create_payload = {
            "id": "custom_cinema_1440p",
            "name": "Custom Cinema 1440p",
            "description": "High resolution theater profile",
            "max_resolution": 1440,
            "audio_format": "flac",
            "cipher_strategy": "web_decipher",
            "is_audio_only": False
        }
        res = self.client.post("/api/profiles", json=create_payload)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        self.assertEqual(data["id"], "custom_cinema_1440p")
        self.assertEqual(data["is_builtin"], False)

        # 2. Get by ID
        res = self.client.get("/api/profiles/custom_cinema_1440p")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["name"], "Custom Cinema 1440p")

        # 3. Update
        update_payload = {"name": "Custom Cinema 1440p Enhanced", "audio_format": "opus_160"}
        res = self.client.put("/api/profiles/custom_cinema_1440p", json=update_payload)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["name"], "Custom Cinema 1440p Enhanced")
        self.assertEqual(res.json()["audio_format"], "opus_160")

        # 4. Built-in profile protection
        del_builtin = self.client.delete("/api/profiles/standard_1080p")
        self.assertEqual(del_builtin.status_code, 400)

        # 5. Delete custom profile
        res_del = self.client.delete("/api/profiles/custom_cinema_1440p")
        self.assertEqual(res_del.status_code, 204)

        # Verify gone
        res_gone = self.client.get("/api/profiles/custom_cinema_1440p")
        self.assertEqual(res_gone.status_code, 404)

    def test_url_sanitization(self):
        """Verify URL sanitizer strips playlist and radio params for adhoc operations"""
        dirty_url1 = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=PL123456789&index=3"
        clean1 = sanitize_youtube_url(dirty_url1)
        self.assertEqual(clean1, "https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        dirty_url2 = "https://youtu.be/dQw4w9WgXcQ?list=RDAMVMdQw4w9WgXcQ"
        clean2 = sanitize_youtube_url(dirty_url2)
        self.assertEqual(clean2, "https://youtu.be/dQw4w9WgXcQ")

    def test_track_properties(self):
        """Test computed primary_resolution and highest_available_resolution properties on Track"""
        track = Track(
            video_id="testTrackProp1",
            title="Resolution Test",
            primary_filepath="/downloads/test [testTrackProp1] [1080p].mp4",
            downloaded_resolutions_json=["720p", "1080p"],
            available_resolutions_json=[
                {"height": 2160, "label": "2160p (4K UHD)"},
                {"height": 1080, "label": "1080p (Full HD)"},
                {"height": 720, "label": "720p (HD)"}
            ]
        )
        self.assertEqual(track.primary_resolution, "1080p")
        self.assertEqual(track.highest_available_resolution, "2160p")


if __name__ == "__main__":
    unittest.main()
