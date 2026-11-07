"""
Unit tests for Ad-Hoc Directory Management, Filesystem Sandbox, and Unified Media Viewer.
Strictly isolated using in-memory SQLite sandbox and temporary directories.
"""
import unittest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

from tests.test_db_helper import create_isolated_test_db, dispose_isolated_test_db
from app.api.filesystem import resolve_safe_path, get_allowed_roots
from app.services.adhoc_service import (
    get_tracked_directories,
    track_adhoc_directory,
    untrack_adhoc_directory,
    reconcile_and_scan_directory,
    get_all_adhoc_media_items,
    delete_adhoc_media_item,
    promote_adhoc_to_playlist,
    run_startup_adhoc_reconciliation,
    _update_adhoc_metadata
)
from app.models.database import Playlist, Track, PlaylistTrack
from app.core.config import settings


class TestAdhocManagement(unittest.TestCase):

    def setUp(self):
        self.test_engine, self.TestingSession = create_isolated_test_db()
        self.db = self.TestingSession()
        self.temp_mount = tempfile.TemporaryDirectory()
        self.orig_base = settings.BASE_DOWNLOAD_PATH
        settings.BASE_DOWNLOAD_PATH = self.temp_mount.name

    def tearDown(self):
        settings.BASE_DOWNLOAD_PATH = self.orig_base
        dispose_isolated_test_db(self.test_engine, self.db)
        self.temp_mount.cleanup()

    def test_sandbox_path_resolution_and_traversal_protection(self):
        """Test that paths inside mount resolve safely, while escapes are blocked with 403"""
        base = os.path.realpath(self.temp_mount.name)
        valid_sub = os.path.join(base, "Tutorials")
        os.makedirs(valid_sub, exist_ok=True)

        # Valid path
        resolved = resolve_safe_path(valid_sub)
        self.assertEqual(resolved, os.path.realpath(valid_sub))

        # None/empty defaults to base mount
        self.assertEqual(resolve_safe_path(None), base)
        self.assertEqual(resolve_safe_path(""), base)

        # Path traversal escapes
        with self.assertRaises(HTTPException) as ctx:
            resolve_safe_path("/etc/passwd")
        self.assertEqual(ctx.exception.status_code, 403)

        with self.assertRaises(HTTPException) as ctx:
            resolve_safe_path(os.path.join(base, "../../root"))
        self.assertEqual(ctx.exception.status_code, 403)

    def test_directory_tracking_mru(self):
        """Test tracked ad-hoc directory MRU list and default directory persistence"""
        dirs = get_tracked_directories(db=self.db)
        self.assertTrue(len(dirs) >= 1)
        self.assertTrue(dirs[0]["is_default"])

        # Track a new custom folder
        custom_folder = os.path.join(self.temp_mount.name, "Podcasts")
        os.makedirs(custom_folder, exist_ok=True)
        track_adhoc_directory(custom_folder, db=self.db)

        dirs_after = get_tracked_directories(db=self.db)
        paths = [d["path"] for d in dirs_after]
        self.assertIn(os.path.abspath(custom_folder), paths)

        # Cannot untrack default directory
        default_dir = dirs[0]["path"]
        self.assertFalse(untrack_adhoc_directory(default_dir, db=self.db))

        # Can untrack custom directory
        self.assertTrue(untrack_adhoc_directory(custom_folder, db=self.db))
        dirs_final = get_tracked_directories(db=self.db)
        self.assertNotIn(os.path.abspath(custom_folder), [d["path"] for d in dirs_final])

    def test_self_healing_reconciliation_on_deleted_file(self):
        """Test that deleted/moved files are pruned from adhoc_info.json and archive.txt"""
        target_dir = os.path.join(self.temp_mount.name, "TestDir")
        os.makedirs(target_dir, exist_ok=True)

        vid_file = os.path.join(target_dir, "Cool_Video [vid12345678].mp4")
        with open(vid_file, "wb") as f:
            f.write(b"dummy video content 12345")

        # Save metadata
        _update_adhoc_metadata(
            target_dir=target_dir,
            video_info={"id": "vid12345678", "title": "Cool Video", "uploader": "Creator"},
            filepath=vid_file
        )

        # Verify scan finds it
        res = reconcile_and_scan_directory(target_dir)
        self.assertEqual(res["item_count"], 1)
        self.assertEqual(res["items"][0]["id"], "vid12345678")

        # Now simulate terminal rm (file deleted from disk)
        os.remove(vid_file)

        # Reconcile again: should prune missing file
        res_after = reconcile_and_scan_directory(target_dir)
        self.assertEqual(res_after["item_count"], 0)

        # Verify archive.txt also had the deleted video ID removed to unblock re-download
        archive_path = os.path.join(target_dir, "archive.txt")
        if os.path.isfile(archive_path):
            with open(archive_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertNotIn("vid12345678", content)

    def test_unindexed_physical_file_auto_discovery(self):
        """Test that manually placed or unindexed media files are auto-discovered into adhoc_info.json"""
        target_dir = os.path.join(self.temp_mount.name, "ManualDrop")
        os.makedirs(target_dir, exist_ok=True)

        # Drop a file manually
        dropped_file = os.path.join(target_dir, "Tutorial Episode [abc12345678].mp4")
        with open(dropped_file, "wb") as f:
            f.write(b"manual media data content")

        res = reconcile_and_scan_directory(target_dir)
        self.assertEqual(res["item_count"], 1)
        item = res["items"][0]
        self.assertEqual(item["id"], "abc12345678")
        self.assertEqual(item["media_type"], "video")
        self.assertEqual(item["format"], "mp4")

    def test_unified_aggregation_and_filters(self):
        """Test multi-directory unified item aggregation and column filters"""
        dir1 = os.path.join(self.temp_mount.name, "FolderA")
        dir2 = os.path.join(self.temp_mount.name, "FolderB")
        os.makedirs(dir1, exist_ok=True)
        os.makedirs(dir2, exist_ok=True)

        # Add video in FolderA
        f1 = os.path.join(dir1, "Guitar Solo [vidAAAA1111].mp4")
        with open(f1, "wb") as f:
            f.write(b"guitar video")
        _update_adhoc_metadata(dir1, {"id": "vidAAAA1111", "title": "Guitar Solo", "uploader": "Musician"}, f1, media_type="video")
        track_adhoc_directory(dir1, db=self.db)

        # Add audio in FolderB
        f2 = os.path.join(dir2, "Tech Podcast [vidBBBB2222].mp3")
        with open(f2, "wb") as f:
            f.write(b"podcast audio")
        _update_adhoc_metadata(dir2, {"id": "vidBBBB2222", "title": "Tech Podcast", "uploader": "Host"}, "", audio_filepath=f2, media_type="audio")
        track_adhoc_directory(dir2, db=self.db)

        # Fetch all
        all_res = get_all_adhoc_media_items(db=self.db)
        self.assertEqual(all_res["total_items"], 2)

        # Filter by directory
        filt_dir = get_all_adhoc_media_items(directory_filter="FolderA", db=self.db)
        self.assertEqual(filt_dir["total_items"], 1)
        self.assertEqual(filt_dir["items"][0]["title"], "Guitar Solo")

        # Filter by media type
        filt_type = get_all_adhoc_media_items(media_type_filter="audio", db=self.db)
        self.assertEqual(filt_type["total_items"], 1)
        self.assertEqual(filt_type["items"][0]["title"], "Tech Podcast")

        # Search filter
        filt_search = get_all_adhoc_media_items(search="Guitar", db=self.db)
        self.assertEqual(filt_search["total_items"], 1)
        self.assertEqual(filt_search["items"][0]["id"], "vidAAAA1111")

    def test_delete_adhoc_media_item(self):
        """Test deleting media file and accompanying metadata"""
        target_dir = os.path.join(self.temp_mount.name, "DeleteTest")
        os.makedirs(target_dir, exist_ok=True)
        vid_p = os.path.join(target_dir, "Sample [del12345678].mp4")
        with open(vid_p, "wb") as f:
            f.write(b"content")

        _update_adhoc_metadata(target_dir, {"id": "del12345678", "title": "Sample"}, vid_p)
        self.assertTrue(os.path.isfile(vid_p))

        # Delete via service
        deleted = delete_adhoc_media_item(vid_p, db=self.db)
        self.assertTrue(deleted)
        self.assertFalse(os.path.isfile(vid_p))

        # Verify pruned
        res = reconcile_and_scan_directory(target_dir)
        self.assertEqual(res["item_count"], 0)

    def test_promote_adhoc_to_playlist(self):
        """Test explicit promotion of ad-hoc media into SQLite Playlist and Track tables"""
        target_dir = os.path.join(self.temp_mount.name, "StagedPromo")
        os.makedirs(target_dir, exist_ok=True)
        vid_p = os.path.join(target_dir, "Epic Song [promo123456].mp4")
        with open(vid_p, "wb") as f:
            f.write(b"staged media content")

        result = promote_adhoc_to_playlist(
            source_directory=target_dir,
            filepaths=[vid_p],
            playlist_title="Promoted Playlist",
            db=self.db
        )

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["tracks_added"], 1)

        # Verify playlist and track in database
        pl = self.db.query(Playlist).filter(Playlist.title == "Promoted Playlist").first()
        self.assertIsNotNone(pl)
        track = self.db.query(Track).filter(Track.video_id == "promo123456").first()
        self.assertIsNotNone(track)

    def test_two_layer_exclusion_and_adhoc_classification(self):
        """Test Layer 1 filters noise (.git, node_modules) and Layer 2 classifies _adhoc_downloads with is_adhoc=True"""
        from app.services.onboarding_service import scan_download_directory, ingest_discovered_library

        # Create Layer 1 noise folders
        os.makedirs(os.path.join(self.temp_mount.name, ".git"), exist_ok=True)
        os.makedirs(os.path.join(self.temp_mount.name, "node_modules"), exist_ok=True)
        os.makedirs(os.path.join(self.temp_mount.name, "lost+found"), exist_ok=True)

        # Create Layer 2 ad-hoc folder with video
        adhoc_dir = os.path.join(self.temp_mount.name, "_adhoc_downloads")
        os.makedirs(adhoc_dir, exist_ok=True)
        with open(os.path.join(adhoc_dir, "adhoc_clip.mp4"), "wb") as f:
            f.write(b"clip content")

        # Create candidate unmanaged folder with video
        unmanaged_dir = os.path.join(self.temp_mount.name, "My_Podcasts")
        os.makedirs(unmanaged_dir, exist_ok=True)
        with open(os.path.join(unmanaged_dir, "episode1.mp4"), "wb") as f:
            f.write(b"episode content")

        scan_res = scan_download_directory(self.temp_mount.name)
        unmanaged = scan_res["unmanaged_folders"]
        unmanaged_names = {u["folder_name"]: u for u in unmanaged}

        # Layer 1 noise must be excluded
        self.assertNotIn(".git", unmanaged_names)
        self.assertNotIn("node_modules", unmanaged_names)
        self.assertNotIn("lost+found", unmanaged_names)

        # Layer 2 adhoc folder must be present with is_adhoc=True
        self.assertIn("_adhoc_downloads", unmanaged_names)
        self.assertTrue(unmanaged_names["_adhoc_downloads"]["is_adhoc"])
        self.assertEqual(unmanaged_names["_adhoc_downloads"]["adhoc_type"], "system_default")
        self.assertEqual(unmanaged_names["_adhoc_downloads"]["video_count"], 1)

        # Candidate unmanaged folder must have is_adhoc=False
        self.assertIn("My_Podcasts", unmanaged_names)
        self.assertFalse(unmanaged_names["My_Podcasts"]["is_adhoc"])

        # Discovered playlists must be empty (adhoc is immune from playlist discovery)
        self.assertEqual(len(scan_res["discovered_playlists"]), 0)

        # Auto-discovery ingest safety test
        ingest_res = ingest_discovered_library(
            discovered_items=[{"folder_name": "_adhoc_downloads", "is_adhoc": True, "url": "https://youtube.com/playlist?list=fake"}],
            db=self.db
        )
        self.assertEqual(ingest_res["playlists_imported"], 0)

    def test_get_tracked_directories_tiering_and_unmanaged(self):
        """Test get_tracked_directories 3-tier grouping (default, recent_adhoc with top 5 cap, unmanaged)"""
        # Create unmanaged directories in base path
        os.makedirs(os.path.join(self.temp_mount.name, "FolderA"), exist_ok=True)
        os.makedirs(os.path.join(self.temp_mount.name, "FolderB"), exist_ok=True)

        # Track multiple ad-hoc directories
        for i in range(1, 8):
            d_path = os.path.join(self.temp_mount.name, f"Adhoc_{i}")
            os.makedirs(d_path, exist_ok=True)
            track_adhoc_directory(d_path, db=self.db)

        dirs = get_tracked_directories(include_unmanaged=True, db=self.db)
        self.assertTrue(len(dirs) >= 8)

        # Tier 1: exactly 1 default
        tier1 = [d for d in dirs if d.get("tier") == "default"]
        self.assertEqual(len(tier1), 1)
        self.assertTrue(tier1[0]["is_default"])

        # Tier 2: capped at top 5 recent adhoc
        tier2 = [d for d in dirs if d.get("tier") == "recent_adhoc"]
        self.assertEqual(len(tier2), 5)

        # Tier 3: remaining older adhoc + unmanaged library folders
        tier3 = [d for d in dirs if d.get("tier") == "unmanaged"]
        tier3_names = [d["display_name"] for d in tier3]
        self.assertIn("FolderA", tier3_names)
        self.assertIn("FolderB", tier3_names)

    def test_batch_link_and_batch_exclude_adhoc_guards(self):
        """Test API endpoints guard against linking or excluding adhoc storage folders"""
        from app.main import app
        from app.models.database import get_db

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)

        try:
            # Attempt to link _adhoc_downloads as a playlist -> should be rejected with 400
            resp = client.post("/api/config/batch-link-unmanaged-folders", json={
                "items": [{"folder_name": "_adhoc_downloads", "playlist_url": "https://www.youtube.com/playlist?list=PL12345"}]
            })
            self.assertEqual(resp.status_code, 400)
            self.assertIn("dedicated Ad-hoc Storage", resp.json()["detail"])

            # Attempt to exclude _adhoc_downloads -> should be rejected with 400
            ex_resp = client.post("/api/config/batch-exclude-folders", json={
                "folder_names": ["_adhoc_downloads"]
            })
            self.assertEqual(ex_resp.status_code, 400)
            self.assertIn("cannot be excluded", ex_resp.json()["detail"])

            # Check GET /api/config/unmanaged-folders returns EXCLUDED_DIRS as config_env
            settings.EXCLUDED_DIRS = "custom_skip_dir"
            unman_resp = client.get("/api/config/unmanaged-folders")
            self.assertEqual(unman_resp.status_code, 200)
            data = unman_resp.json()
            sys_excluded = [x for x in data["excluded_folders"] if x["folder_name"] == "custom_skip_dir"]
            self.assertEqual(len(sys_excluded), 1)
            self.assertTrue(sys_excluded[0]["is_system"])
            self.assertEqual(sys_excluded[0]["reason"], "config_env")
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_known_adhoc_paths_seeded_when_present_on_disk(self):
        """Test that system _adhoc_downloads on disk is always tracked even if a custom adhoc path is active"""
        custom_adhoc = os.path.join(self.temp_mount.name, "custom_adhoc")
        std_adhoc = os.path.join(self.temp_mount.name, "_adhoc_downloads")
        os.makedirs(custom_adhoc, exist_ok=True)
        os.makedirs(std_adhoc, exist_ok=True)

        orig_custom = settings.ADHOC_DOWNLOAD_PATH
        try:
            settings.ADHOC_DOWNLOAD_PATH = custom_adhoc
            dirs = get_tracked_directories(include_unmanaged=False, db=self.db)
            paths = [os.path.realpath(d["path"]) for d in dirs]
            self.assertIn(os.path.realpath(std_adhoc), paths)
            self.assertIn(os.path.realpath(custom_adhoc), paths)
        finally:
            settings.ADHOC_DOWNLOAD_PATH = orig_custom

    def test_browse_directories_exclude_managed_and_layer1(self):
        """Test /api/filesystem/browse with exclude_managed=True excludes playlist dirs and Layer 1 noise"""
        from app.main import app
        from app.models.database import get_db

        base = os.path.realpath(self.temp_mount.name)
        pl_dir = os.path.join(base, "MyRockPlaylist")
        unman_dir = os.path.join(base, "UnmanagedClips")
        layer1_dir = os.path.join(base, "node_modules")
        os.makedirs(pl_dir, exist_ok=True)
        os.makedirs(unman_dir, exist_ok=True)
        os.makedirs(layer1_dir, exist_ok=True)

        # Create managed playlist in DB
        pl = Playlist(
            id=999,
            title="MyRockPlaylist",
            url="https://www.youtube.com/playlist?list=PLTEST999"
        )
        self.db.add(pl)
        self.db.commit()

        def override_get_db():
            try:
                yield self.db
            finally:
                pass

        app.dependency_overrides[get_db] = override_get_db
        client = TestClient(app)
        try:
            resp = client.get(f"/api/filesystem/browse?path={base}&exclude_managed=true")
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            subdir_names = [d["name"] for d in data["subdirectories"]]
            self.assertIn("UnmanagedClips", subdir_names)
            self.assertNotIn("MyRockPlaylist", subdir_names)
            self.assertNotIn("node_modules", subdir_names)
        finally:
            app.dependency_overrides.pop(get_db, None)

    def test_exact_title_preservation_and_no_bracket_stripping(self):
        """Test that disk filenames with bracketed tags are preserved verbatim without regex stripping"""
        target_dir = os.path.join(self.temp_mount.name, "BracketTest")
        os.makedirs(target_dir, exist_ok=True)

        filename = "Bodo Wartke • Kuckuck und Hai (feat. @Tom.Boettcher ) [Offizielles Musikvideo] [jEuBa23RkH0].mp4"
        file_path = os.path.join(target_dir, filename)
        with open(file_path, "wb") as f:
            f.write(b"test video payload")

        res = reconcile_and_scan_directory(target_dir)
        self.assertEqual(res["item_count"], 1)
        item = res["items"][0]
        # Title should match exact filename without extension, preserving [Offizielles Musikvideo] and [jEuBa23RkH0]
        expected_title = "Bodo Wartke • Kuckuck und Hai (feat. @Tom.Boettcher ) [Offizielles Musikvideo] [jEuBa23RkH0]"
        self.assertEqual(item["title"], expected_title)
        self.assertEqual(item["id"], "jEuBa23RkH0")
        self.assertEqual(item["format"], "mp4")
        self.assertEqual(item["media_type"], "video")

    def test_dual_video_and_audio_file_splitting_and_format_backfill(self):
        """Test that legacy collapsed entries with both video & audio are split into two distinct items and format is backfilled"""
        target_dir = os.path.join(self.temp_mount.name, "DualTest")
        os.makedirs(target_dir, exist_ok=True)

        vid_path = os.path.join(target_dir, "DualSong [vid123].mp4")
        aud_path = os.path.join(target_dir, "DualSong [vid123].opus")
        with open(vid_path, "wb") as f:
            f.write(b"video data")
        with open(aud_path, "wb") as f:
            f.write(b"audio data")

        # Write legacy collapsed entry lacking format
        legacy_entry = [{
            "id": "vid123",
            "title": "DualSong",
            "uploader": "Artist",
            "duration": 180,
            "filepath": vid_path,
            "audio_filepath": aud_path,
            # format missing
            "resolution": "1080p",
            "media_type": "audio"
        }]
        with open(os.path.join(target_dir, "adhoc_info.json"), "w", encoding="utf-8") as f:
            json.dump(legacy_entry, f)

        res = reconcile_and_scan_directory(target_dir)
        # Should now have 2 items: 1 video and 1 audio
        self.assertEqual(res["item_count"], 2)
        items = res["items"]
        vid_item = next((it for it in items if it["media_type"] == "video"), None)
        aud_item = next((it for it in items if it["media_type"] == "audio"), None)

        self.assertIsNotNone(vid_item)
        self.assertIsNotNone(aud_item)
        self.assertEqual(vid_item["format"], "mp4")
        self.assertEqual(vid_item["filepath"], os.path.realpath(vid_path))
        self.assertIsNone(vid_item["audio_filepath"])

        self.assertEqual(aud_item["format"], "opus")
        self.assertEqual(aud_item["audio_filepath"], os.path.realpath(aud_path))
        self.assertEqual(aud_item["filepath"], "")


if __name__ == "__main__":
    unittest.main()
