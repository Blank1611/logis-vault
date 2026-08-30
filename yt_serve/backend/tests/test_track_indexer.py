import unittest
import os
import tempfile
from app.models.database import SessionLocal, Track, MovedTrackHistory, Playlist, _auto_migrate_sqlite_columns
from app.core.track_indexer import (
    create_hardlink_or_copy,
    find_local_track,
    index_track,
    execute_track_move
)

class TestTrackIndexer(unittest.TestCase):

    def setUp(self):
        _auto_migrate_sqlite_columns()
        self.db = SessionLocal()
        self.temp_dir = tempfile.TemporaryDirectory()

        # Create dummy source and destination playlists
        self.p1 = Playlist(url="https://youtube.com/playlist?list=PL1", title="Playlist One")
        self.p2 = Playlist(url="https://youtube.com/playlist?list=PL2", title="Playlist Two")
        self.db.add(self.p1)
        self.db.add(self.p2)
        self.db.commit()
        self.db.refresh(self.p1)
        self.db.refresh(self.p2)

    def tearDown(self):
        # Cleanup playlists and tracks
        self.db.query(MovedTrackHistory).delete()
        self.db.query(Track).delete()
        self.db.query(Playlist).filter(Playlist.id.in_([self.p1.id, self.p2.id])).delete()
        self.db.commit()
        self.db.close()
        self.temp_dir.cleanup()

    def test_hardlink_creation(self):
        src = os.path.join(self.temp_dir.name, "source.mp4")
        with open(src, "w") as f:
            f.write("test content video stream")

        dst = os.path.join(self.temp_dir.name, "nested", "hardlinked.mp4")
        success = create_hardlink_or_copy(src, dst)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(dst))

        with open(dst, "r") as f:
            self.assertEqual(f.read(), "test content video stream")

    def test_index_and_find_local_track(self):
        vid = "dQw4w9WgXcQ"
        dummy_file = os.path.join(self.temp_dir.name, "Never_Gonna_Give_You_Up.mp4")
        with open(dummy_file, "w") as f:
            f.write("audio_data")

        # Index track
        track = index_track(
            video_id=vid,
            title="Never Gonna Give You Up",
            filepath=dummy_file,
            playlist_id=self.p1.id,
            db=self.db
        )
        self.assertIsNotNone(track)
        self.assertEqual(track.video_id, vid)
        self.assertIn(self.p1.id, track.playlists_json)

        # Find track locally
        found = find_local_track(vid, db=self.db)
        self.assertIsNotNone(found)
        self.assertEqual(found["title"], "Never Gonna Give You Up")
        self.assertEqual(found["primary_filepath"], dummy_file)

    def test_execute_track_move(self):
        vid = "moveTest123"
        dummy_file = os.path.join(self.temp_dir.name, "Song.mp4")
        with open(dummy_file, "w") as f:
            f.write("song")

        index_track(
            video_id=vid,
            title="Moving Song",
            filepath=dummy_file,
            playlist_id=self.p1.id,
            db=self.db
        )

        res = execute_track_move(
            video_id=vid,
            from_playlist_id=self.p1.id,
            to_playlist_id=self.p2.id,
            db=self.db,
            status="manually_moved"
        )

        self.assertEqual(res["video_id"], vid)
        self.assertEqual(res["from_playlist"], "Playlist One")
        self.assertEqual(res["to_playlist"], "Playlist Two")

        # Check track playlists_json updated
        updated_track = self.db.query(Track).filter(Track.video_id == vid).first()
        self.assertNotIn(self.p1.id, updated_track.playlists_json)
        self.assertIn(self.p2.id, updated_track.playlists_json)

        # Check history audit entry
        hist = self.db.query(MovedTrackHistory).filter(MovedTrackHistory.video_id == vid).first()
        self.assertIsNotNone(hist)
        self.assertEqual(hist.status, "manually_moved")

if __name__ == "__main__":
    unittest.main()
