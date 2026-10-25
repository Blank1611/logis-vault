"""
Unit tests for Orphan and Unavailable Media Preservation System:
- Sequence Alignment Engine (handling 1, 3, and consecutive deleted tracks)
- 3-Tier Metadata Fallback Ladder (Snapshot entries -> archived_entries -> SQLite -> Regex)
- PlaylistTrack junction table ordering and cascade behaviors
- Dual UTF-8 .m3u8 and .m3u playlist generation preserving deleted tracks
- Snapshot delta merge and archived_entries generation
"""
import os
import json
import tempfile
import unittest
from datetime import datetime

from tests.test_db_helper import create_isolated_test_db, dispose_isolated_test_db
from app.models.database import Playlist, Track, PlaylistTrack, get_db_context
from app.repositories import PlaylistRepository, TrackRepository
from app.core.track_indexer import index_track
from app.core.yt_playlist_audio_tools import (
    is_deleted_or_private_title,
    resolve_track_metadata,
    build_aligned_playlist_sequence,
    generate_m3u_playlists,
    _save_playlist_info_with_versioning
)
from migrations.migrate_legacy_snapshots import (
    consolidate_archived_entries,
    SnapshotRecord
)


class TestOrphanMediaPreservation(unittest.TestCase):

    def setUp(self):
        self.test_engine, self.TestingSession = create_isolated_test_db()
        self.db = self.TestingSession()
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        dispose_isolated_test_db(self.test_engine, self.db)
        self.temp_dir.cleanup()

    def test_consecutive_deletions_sequence_alignment(self):
        """
        Test Sequence Alignment when 3 consecutive tracks are deleted from YouTube.
        Historical: [F] -> [E] -> [D] -> [C] -> [B] -> [A]
        YouTube Today: [G] (new), [F], [E], [A] (shifted up)
        Expected Aligned: [G, F, E, D, C, B, A]
        """
        playlist_folder = os.path.join(self.temp_dir.name, "ClassicRock")
        os.makedirs(playlist_folder, exist_ok=True)
        snap_dir = os.path.join(playlist_folder, "playlist_info_snapshot")
        os.makedirs(snap_dir, exist_ok=True)

        info_data = {
            "title": "ClassicRock",
            "entries": [
                {"id": "vid_G", "title": "Song G", "uploader": "Artist G", "duration": 180},
                {"id": "vid_F", "title": "Song F", "uploader": "Artist F", "duration": 200},
                {"id": "vid_E", "title": "Song E", "uploader": "Artist E", "duration": 210},
                {"id": "vid_A", "title": "Song A", "uploader": "Artist A", "duration": 240},
            ],
            "archived_entries": [
                {
                    "id": "vid_D",
                    "title": "Song D (Deleted)",
                    "uploader": "Artist D",
                    "duration": 220,
                    "historical_slot": {"preceding_id": "vid_E", "succeeding_id": "vid_C"}
                },
                {
                    "id": "vid_C",
                    "title": "Song C (Deleted)",
                    "uploader": "Artist C",
                    "duration": 195,
                    "historical_slot": {"preceding_id": "vid_D", "succeeding_id": "vid_B"}
                },
                {
                    "id": "vid_B",
                    "title": "Song B (Deleted)",
                    "uploader": "Artist B",
                    "duration": 230,
                    "historical_slot": {"preceding_id": "vid_C", "succeeding_id": "vid_A"}
                }
            ]
        }

        with open(os.path.join(snap_dir, "playlist_info.json"), "w", encoding="utf-8") as f:
            json.dump(info_data, f)

        # Create dummy physical files on disk for all 7 songs
        all_ids = ["vid_G", "vid_F", "vid_E", "vid_D", "vid_C", "vid_B", "vid_A"]
        for vid in all_ids:
            dummy_file = os.path.join(playlist_folder, f"Track_{vid} [{vid}].mp4")
            with open(dummy_file, "w") as f:
                f.write("media")

        # Run sequence alignment
        aligned = build_aligned_playlist_sequence(playlist_folder, db=self.db)
        self.assertEqual(len(aligned), 7)

        # Check sequence order matches exact historical slotting
        ordered_ids = [item["video_id"] for item in aligned]
        self.assertEqual(ordered_ids, ["vid_G", "vid_F", "vid_E", "vid_D", "vid_C", "vid_B", "vid_A"])

        # Check continuous 1-based track positions
        for expected_pos, item in enumerate(aligned, start=1):
            self.assertEqual(item["position"], expected_pos)

        # Check archive flags
        self.assertFalse(aligned[0]["is_archived"])  # G
        self.assertFalse(aligned[1]["is_archived"])  # F
        self.assertFalse(aligned[2]["is_archived"])  # E
        self.assertTrue(aligned[3]["is_archived"])   # D
        self.assertTrue(aligned[4]["is_archived"])   # C
        self.assertTrue(aligned[5]["is_archived"])   # B
        self.assertFalse(aligned[6]["is_archived"])  # A

    def test_three_tier_metadata_fallback_ladder(self):
        """Verify 3-Tier resolution: Snapshot active -> Snapshot archived -> SQLite -> Regex"""
        playlist_folder = os.path.join(self.temp_dir.name, "TestLadder")
        os.makedirs(playlist_folder, exist_ok=True)
        snap_dir = os.path.join(playlist_folder, "playlist_info_snapshot")
        os.makedirs(snap_dir, exist_ok=True)

        info_data = {
            "title": "TestLadder",
            "entries": [
                {"id": "tier1_act", "title": "Active Song", "uploader": "Active Artist"}
            ],
            "archived_entries": [
                {"id": "tier1_arc", "title": "Archived Song", "uploader": "Archived Artist"}
            ]
        }
        with open(os.path.join(snap_dir, "playlist_info.json"), "w", encoding="utf-8") as f:
            json.dump(info_data, f)

        # 1. Tier 1A: Snapshot active
        m1a = resolve_track_metadata(playlist_folder, "tier1_act", db=self.db)
        self.assertEqual(m1a["title"], "Active Song")
        self.assertEqual(m1a["artist"], "Active Artist")
        self.assertEqual(m1a["source"], "snapshot_active")

        # 2. Tier 1B: Snapshot archived
        m1b = resolve_track_metadata(playlist_folder, "tier1_arc", db=self.db)
        self.assertEqual(m1b["title"], "Archived Song")
        self.assertEqual(m1b["artist"], "Archived Artist")
        self.assertEqual(m1b["source"], "snapshot_archived")

        # 3. Tier 2: SQLite Track table
        with get_db_context(self.db) as session:
            session.add(Track(
                video_id="tier2_db",
                title="Database Stored Title",
                artist="Database Artist",
                primary_filepath="/path/dummy.mp4"
            ))
            session.commit()

        m2 = resolve_track_metadata(playlist_folder, "tier2_db", db=self.db)
        self.assertEqual(m2["title"], "Database Stored Title")
        self.assertEqual(m2["artist"], "Database Artist")
        self.assertEqual(m2["source"], "sqlite_track")

        # 4. Tier 3: Filename Regex Heuristic
        m3 = resolve_track_metadata(
            playlist_folder,
            "tier3_reg",
            filename="Carpenter Brut - Turbo Killer [tier3_reg].mp4",
            db=self.db
        )
        self.assertEqual(m3["title"], "Turbo Killer")
        self.assertEqual(m3["artist"], "Carpenter Brut")
        self.assertEqual(m3["source"], "filename_regex")

    def test_playlist_tracks_junction_table_ordering_and_cascade(self):
        """Verify PlaylistTrack model maintains strict position order and cascades cleanly on delete"""
        with get_db_context(self.db) as session:
            pl = Playlist(url="https://youtube.com/playlist?list=PL_JUNC", title="Junction Mix")
            session.add(pl)
            session.flush()

            t1 = Track(video_id="vid1", title="First", primary_filepath="/p/1.mp4")
            t2 = Track(video_id="vid2", title="Second", primary_filepath="/p/2.mp4")
            t3 = Track(video_id="vid3", title="Third (Archived)", primary_filepath="/p/3.mp4")
            session.add_all([t1, t2, t3])
            session.flush()

            # Insert out-of-order in playlist_tracks
            session.add(PlaylistTrack(playlist_id=pl.id, track_id="vid2", position=2, is_archived=False))
            session.add(PlaylistTrack(playlist_id=pl.id, track_id="vid1", position=1, is_archived=False))
            session.add(PlaylistTrack(playlist_id=pl.id, track_id="vid3", position=3, is_archived=True))
            session.commit()

            # Query joined ordered by position
            tracks = (
                session.query(Track, PlaylistTrack)
                .join(PlaylistTrack, Track.video_id == PlaylistTrack.track_id)
                .filter(PlaylistTrack.playlist_id == pl.id)
                .order_by(PlaylistTrack.position.asc())
                .all()
            )

            self.assertEqual(len(tracks), 3)
            self.assertEqual(tracks[0][0].video_id, "vid1")
            self.assertEqual(tracks[0][1].position, 1)
            self.assertEqual(tracks[1][0].video_id, "vid2")
            self.assertEqual(tracks[1][1].position, 2)
            self.assertEqual(tracks[2][0].video_id, "vid3")
            self.assertEqual(tracks[2][1].position, 3)
            self.assertTrue(tracks[2][1].is_archived)

            # Test cascade delete: deleting playlist removes junction records
            session.delete(pl)
            session.commit()

            junction_count = session.query(PlaylistTrack).filter(PlaylistTrack.playlist_id == pl.id).count()
            self.assertEqual(junction_count, 0)
            # Physical tracks themselves remain intact in catalog
            self.assertEqual(session.query(Track).count(), 3)

    def test_m3u_playlist_generation_with_archived_tracks(self):
        """Verify generate_m3u_playlists writes both active and preserved tracks in exact sequence"""
        playlist_folder = os.path.join(self.temp_dir.name, "Synthwave")
        os.makedirs(playlist_folder, exist_ok=True)
        snap_dir = os.path.join(playlist_folder, "playlist_info_snapshot")
        os.makedirs(snap_dir, exist_ok=True)

        info = {
            "title": "Synthwave",
            "entries": [
                {"id": "act1", "title": "First Song", "duration": 150},
                {"id": "act2", "title": "Third Song", "duration": 180}
            ],
            "archived_entries": [
                {
                    "id": "del1",
                    "title": "Second Song (Deleted from YT)",
                    "duration": 200,
                    "historical_slot": {"preceding_id": "act1", "succeeding_id": "act2"}
                }
            ]
        }
        with open(os.path.join(snap_dir, "playlist_info.json"), "w", encoding="utf-8") as f:
            json.dump(info, f)

        # Create video files in root
        f1 = os.path.join(playlist_folder, "01 First Song [act1].mp4")
        f2 = os.path.join(playlist_folder, "02 Second Song [del1].mp4")
        f3 = os.path.join(playlist_folder, "03 Third Song [act2].mp4")
        for f in (f1, f2, f3):
            with open(f, "w") as fp:
                fp.write("dummy")

        # Create audio export subfolder
        audio_sub = os.path.join(playlist_folder, "Synthwave [MP3]")
        os.makedirs(audio_sub, exist_ok=True)
        a1 = os.path.join(audio_sub, "01 First Song [act1].mp3")
        a2 = os.path.join(audio_sub, "02 Second Song [del1].mp3")
        a3 = os.path.join(audio_sub, "03 Third Song [act2].mp3")
        for a in (a1, a2, a3):
            with open(a, "w") as fp:
                fp.write("dummy_audio")

        # Generate M3U playlists
        generate_m3u_playlists(playlist_folder, [audio_sub])

        # Verify root .m3u8 exists and has 3 tracks in order
        root_m3u8 = os.path.join(playlist_folder, "Synthwave.m3u8")
        self.assertTrue(os.path.isfile(root_m3u8))
        with open(root_m3u8, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        self.assertEqual(len(lines), 3)
        self.assertIn("act1", lines[0])
        self.assertIn("del1", lines[1])
        self.assertIn("act2", lines[2])

        # Verify audio folder .m3u8 exists and has 3 audio tracks in order
        audio_m3u8 = os.path.join(audio_sub, "Synthwave [MP3].m3u8")
        self.assertTrue(os.path.isfile(audio_m3u8))
        with open(audio_m3u8, "r", encoding="utf-8") as f:
            a_lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
        self.assertEqual(len(a_lines), 3)
        self.assertIn("act1", a_lines[0])
        self.assertIn("del1", a_lines[1])
        self.assertIn("act2", a_lines[2])

    def test_snapshot_delta_merge_preserves_archived_entries(self):
        """Verify _save_playlist_info_with_versioning automatically saves missing songs into archived_entries"""
        playlist_folder = os.path.join(self.temp_dir.name, "DeltaTest")
        os.makedirs(playlist_folder, exist_ok=True)
        snap_dir = os.path.join(playlist_folder, "playlist_info_snapshot")
        os.makedirs(snap_dir, exist_ok=True)

        old_info = {
            "title": "DeltaTest",
            "entries": [
                {"id": "keep1", "title": "Staying 1", "duration": 100},
                {"id": "drop1", "title": "Will Be Deleted", "duration": 200, "uploader": "Old Artist"},
                {"id": "keep2", "title": "Staying 2", "duration": 300}
            ]
        }
        with open(os.path.join(snap_dir, "playlist_info.json"), "w", encoding="utf-8") as f:
            json.dump(old_info, f)

        # YouTube returns fresh scan without drop1
        new_info = {
            "title": "DeltaTest",
            "entries": [
                {"id": "keep1", "title": "Staying 1", "duration": 100},
                {"id": "keep2", "title": "Staying 2", "duration": 300}
            ]
        }

        _save_playlist_info_with_versioning(playlist_folder, new_info, source="test")

        # Verify drop1 was preserved into archived_entries with slot info
        with open(os.path.join(snap_dir, "playlist_info.json"), "r", encoding="utf-8") as f:
            saved = json.load(f)

        self.assertEqual(len(saved["entries"]), 2)
        self.assertEqual(len(saved["archived_entries"]), 1)
        archived_item = saved["archived_entries"][0]
        self.assertEqual(archived_item["id"], "drop1")
        self.assertEqual(archived_item["title"], "Will Be Deleted")
        self.assertEqual(archived_item["historical_slot"]["preceding_id"], "keep1")
        self.assertEqual(archived_item["historical_slot"]["succeeding_id"], "keep2")


if __name__ == "__main__":
    unittest.main()
