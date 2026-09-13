"""
API Route Contract and Smoke Test Suite.
Validates HTTP methods, path formatting (trailing slash vs no trailing slash),
dependency injection, status codes, and route discovery.
Strictly isolated using in-memory SQLite sandbox (never touches production yt_manager.db).
"""

import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.database import Base, get_db, Playlist
from tests.test_db_helper import create_isolated_test_db, dispose_isolated_test_db


class TestRoutesContract(unittest.TestCase):

    def setUp(self):
        # 100% isolated in-memory test database sandbox
        self.test_engine, self.TestingSession = create_isolated_test_db()

        def override_get_db():
            db = self.TestingSession()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_get_db

        # Patch SessionLocal in database module and startup recovery to keep sandbox completely clean
        self.patcher_session = patch("app.models.database.SessionLocal", self.TestingSession)
        self.patcher_recovery = patch("app.services.recovery_service.RecoveryService.run_startup_recovery", new_callable=AsyncMock)
        self.patcher_session.start()
        self.patcher_recovery.start()

        self.client = TestClient(app)

    def tearDown(self):
        self.patcher_recovery.stop()
        self.patcher_session.stop()
        app.dependency_overrides.clear()
        dispose_isolated_test_db(self.test_engine)

    def test_playlists_get_contract_slash_and_no_slash(self):
        """Verify GET /api/playlists and GET /api/playlists/ both return 200 OK without 405/404."""
        # Pre-seed a playlist in the isolated test DB
        db = self.TestingSession()
        pl = Playlist(url="https://www.youtube.com/playlist?list=PLcontract_test", title="Contract Playlist")
        db.add(pl)
        db.commit()
        db.close()

        # Test without trailing slash
        res_no_slash = self.client.get("/api/playlists")
        self.assertEqual(res_no_slash.status_code, 200)
        data_no_slash = res_no_slash.json()
        self.assertEqual(len(data_no_slash), 1)
        self.assertEqual(data_no_slash[0]["title"], "Contract Playlist")

        # Test with trailing slash
        res_slash = self.client.get("/api/playlists/")
        self.assertEqual(res_slash.status_code, 200)
        data_slash = res_slash.json()
        self.assertEqual(len(data_slash), 1)
        self.assertEqual(data_slash[0]["title"], "Contract Playlist")

    @patch("app.api.playlists.get_download_service")
    def test_playlists_post_contract_slash_and_no_slash(self, mock_get_svc):
        """Verify POST /api/playlists and POST /api/playlists/ both return 201 Created and prevent 405."""
        mock_svc = MagicMock()
        mock_svc.get_playlist_info = AsyncMock(return_value={
            "id": "mock_pl_1",
            "title": "Discovered Title",
            "playlist_count": 10
        })
        mock_svc.get_playlist_stats = AsyncMock(return_value=(10, 10, 0))
        mock_get_svc.return_value = mock_svc

        # 1. POST without trailing slash (this previously failed with 405 before the fix)
        payload_1 = {"url": "https://www.youtube.com/playlist?list=PLno_slash_test"}
        res_1 = self.client.post("/api/playlists", json=payload_1)
        self.assertEqual(res_1.status_code, 201, f"Expected 201, got {res_1.status_code}: {res_1.text}")
        data_1 = res_1.json()
        self.assertEqual(data_1["title"], "Discovered Title")
        self.assertEqual(data_1["url"], payload_1["url"])

        # 2. POST with trailing slash
        payload_2 = {"url": "https://www.youtube.com/playlist?list=PLwith_slash_test"}
        res_2 = self.client.post("/api/playlists/", json=payload_2)
        self.assertEqual(res_2.status_code, 201, f"Expected 201, got {res_2.status_code}: {res_2.text}")
        data_2 = res_2.json()
        self.assertEqual(data_2["title"], "Discovered Title")

        # 3. Duplicate POST should return 400 Bad Request
        res_dup = self.client.post("/api/playlists", json=payload_1)
        self.assertEqual(res_dup.status_code, 400)
        self.assertIn("already exists", res_dup.json()["detail"])

    def test_config_routes_contract(self):
        """Verify GET and PUT on /api/config work cleanly including scheduler dual-mode fields."""
        # GET /api/config
        get_res = self.client.get("/api/config")
        self.assertEqual(get_res.status_code, 200)
        cfg = get_res.json()
        self.assertIn("daily_refresh_mode", cfg)
        self.assertIn("daily_refresh_interval_minutes", cfg)
        self.assertIn("daily_refresh_timezone", cfg)

        # GET /api/config/
        get_res_slash = self.client.get("/api/config/")
        self.assertEqual(get_res_slash.status_code, 200)

        # PUT /api/config
        with patch("app.api.config._save_to_env", return_value=None):
            put_payload = {
                "daily_refresh_mode": "interval",
                "daily_refresh_interval_minutes": 180,
                "daily_refresh_timezone": "Asia/Kolkata"
            }
            put_res = self.client.put("/api/config", json=put_payload)
            self.assertEqual(put_res.status_code, 200)
            res_data = put_res.json()
            self.assertEqual(res_data.get("daily_refresh_mode"), "interval")
            self.assertEqual(res_data.get("daily_refresh_interval_minutes"), 180)
            self.assertEqual(res_data.get("daily_refresh_timezone"), "Asia/Kolkata")

    def test_housekeeping_and_jobs_endpoints(self):
        """Verify operational and housekeeping endpoints return 200 OK."""
        res_folders = self.client.get("/api/config/unmanaged-folders")
        self.assertEqual(res_folders.status_code, 200)
        data = res_folders.json()
        self.assertIn("unmanaged_folders", data)
        self.assertIsInstance(data["unmanaged_folders"], list)

        # Verify /jobs both with and without trailing slash
        res_jobs = self.client.get("/api/downloads/jobs")
        self.assertEqual(res_jobs.status_code, 200)
        self.assertIsInstance(res_jobs.json(), list)

        res_jobs_slash = self.client.get("/api/downloads/jobs/")
        self.assertEqual(res_jobs_slash.status_code, 200)
        self.assertIsInstance(res_jobs_slash.json(), list)

    def test_all_registered_get_routes_sanity(self):
        """
        Automated Route Discovery Sanity:
        Iterates over all registered static GET endpoints across the application
        and verifies none of them throw 500 (Internal Server Error) or 405 (Method Not Allowed).
        """
        tested_paths = set()
        for route in app.routes:
            # Check route methods
            methods = getattr(route, "methods", set())
            path = getattr(route, "path", None)

            # Skip dynamic parameterized routes (e.g. /api/playlists/{playlist_id}),
            # WebSocket routes, and root/SPA static catch-alls
            if (
                path
                and "GET" in methods
                and "{" not in path
                and path.startswith("/api/")
                and path not in tested_paths
            ):
                tested_paths.add(path)
                res = self.client.get(path)
                self.assertNotEqual(
                    res.status_code,
                    500,
                    f"Route {path} failed with 500 Internal Server Error: {res.text}"
                )
                self.assertNotEqual(
                    res.status_code,
                    405,
                    f"Route {path} returned 405 Method Not Allowed"
                )


if __name__ == "__main__":
    unittest.main()
