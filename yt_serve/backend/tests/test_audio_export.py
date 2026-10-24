import unittest
import os
import json
import tempfile
import zipfile
from app.core import yt_playlist_audio_tools as tools
from tests.test_db_helper import create_isolated_test_db, dispose_isolated_test_db
from app.models.database import Playlist, Track

class TestAudioExport(unittest.TestCase):

    def setUp(self):
        self.test_engine, self.TestingSession = create_isolated_test_db()
        self.db = self.TestingSession()
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        dispose_isolated_test_db(self.test_engine, self.db)
        self.temp_dir.cleanup()

    def test_resolve_audio_format_info(self):
        """Verify format mapping to clean folder labels, extensions, and mode strings."""
        label, ext, mode = tools.resolve_audio_format_info("mp3_best")
        self.assertEqual(label, "MP3")
        self.assertEqual(ext, ".mp3")
        self.assertEqual(mode, "mp3_best")

        label, ext, mode = tools.resolve_audio_format_info("mp3_v0")
        self.assertEqual(label, "MP3 V0")
        self.assertEqual(ext, ".mp3")
        self.assertEqual(mode, "mp3_high")

        label, ext, mode = tools.resolve_audio_format_info("flac")
        self.assertEqual(label, "FLAC")
        self.assertEqual(ext, ".flac")
        self.assertEqual(mode, "flac")

        label, ext, mode = tools.resolve_audio_format_info("aac")
        self.assertEqual(label, "AAC")
        self.assertEqual(ext, ".m4a")
        self.assertEqual(mode, "aac")

        label, ext, mode = tools.resolve_audio_format_info("opus")
        self.assertEqual(label, "OPUS")
        self.assertEqual(ext, ".opus")
        self.assertEqual(mode, "opus")

    def test_build_playlist_paths_folder_naming(self):
        """Verify phone-ready destination folder formatting: <Playlist> [<FORMAT>]."""
        title = "Rock & Roll Classics"
        folder, archive, audio_folder = tools._build_playlist_paths(title, create_folders=False, extract_mode="mp3_best")

        expected_audio_dir_name = "Rock & Roll Classics [MP3]"
        self.assertEqual(os.path.basename(audio_folder), expected_audio_dir_name)
        self.assertTrue(audio_folder.startswith(folder))

        folder_flac, _, audio_flac = tools._build_playlist_paths(title, create_folders=False, extract_mode="flac")
        self.assertEqual(os.path.basename(audio_flac), "Rock & Roll Classics [FLAC]")

    def test_generate_m3u_playlists(self):
        """Verify generation of dual UTF-8 .m3u8 and .m3u playlists matching YouTube order."""
        playlist_dir = os.path.join(self.temp_dir.name, "Synthwave")
        os.makedirs(playlist_dir, exist_ok=True)

        audio_dir = os.path.join(playlist_dir, "Synthwave [MP3]")
        os.makedirs(audio_dir, exist_ok=True)

        # Create dummy video and audio files with Unicode / emojis
        v1 = os.path.join(playlist_dir, "01 Midnight City 🎵 [vid_1].mp4")
        v2 = os.path.join(playlist_dir, "02 Resonance [vid_2].mkv")
        open(v1, "w").close()
        open(v2, "w").close()

        a1 = os.path.join(audio_dir, "01 Midnight City 🎵 [vid_1].mp3")
        a2 = os.path.join(audio_dir, "02 Resonance [vid_2].mp3")
        open(a1, "w").close()
        open(a2, "w").close()

        # Write snapshot JSON with top-to-bottom YouTube order
        snapshot_dir = os.path.join(playlist_dir, "playlist_info_snapshot")
        os.makedirs(snapshot_dir, exist_ok=True)
        snapshot_file = os.path.join(snapshot_dir, "playlist_info.json")
        with open(snapshot_file, "w", encoding="utf-8") as f:
            json.dump({
                "title": "Synthwave",
                "entries": [
                    {"id": "vid_2", "title": "02 Resonance", "duration": 180, "uploader": "HOME"},
                    {"id": "vid_1", "title": "01 Midnight City 🎵", "duration": 240, "uploader": "M83"}
                ]
            }, f)

        # Generate playlists
        tools.generate_m3u_playlists(playlist_dir, [audio_dir])

        # Check root video playlists exist (.m3u8 and .m3u)
        m3u8_video = os.path.join(playlist_dir, "Synthwave.m3u8")
        m3u_video = os.path.join(playlist_dir, "Synthwave.m3u")
        self.assertTrue(os.path.isfile(m3u8_video))
        self.assertTrue(os.path.isfile(m3u_video))

        # Check audio playlists exist inside audio export folder
        m3u8_audio = os.path.join(audio_dir, "Synthwave [MP3].m3u8")
        m3u_audio = os.path.join(audio_dir, "Synthwave [MP3].m3u")
        self.assertTrue(os.path.isfile(m3u8_audio))
        self.assertTrue(os.path.isfile(m3u_audio))

        # Check that order strictly followed snapshot (vid_2 first, then vid_1)
        with open(m3u8_audio, "r", encoding="utf-8") as f:
            content = f.read()
            self.assertIn("#EXTM3U", content)
            self.assertIn("02 Resonance [vid_2].mp3", content)
            self.assertIn("01 Midnight City 🎵 [vid_1].mp3", content)
            pos_v2 = content.find("02 Resonance [vid_2].mp3")
            pos_v1 = content.find("01 Midnight City 🎵 [vid_1].mp3")
            self.assertLess(pos_v2, pos_v1, "Tracks must be ordered strictly according to YouTube playlist snapshot")

    def test_zip_packaging(self):
        """Verify uncompressed ZIP creation preserving folder hierarchy and .m3u8 files."""
        audio_folder = os.path.join(self.temp_dir.name, "Chillout [MP3]")
        os.makedirs(audio_folder, exist_ok=True)

        f1 = os.path.join(audio_folder, "Song A.mp3")
        f2 = os.path.join(audio_folder, "Song B.mp3")
        pl = os.path.join(audio_folder, "Chillout [MP3].m3u8")

        with open(f1, "w") as f: f.write("audio_a")
        with open(f2, "w") as f: f.write("audio_b")
        with open(pl, "w") as f: f.write("#EXTM3U\nSong A.mp3\nSong B.mp3\n")

        zip_path = os.path.join(self.temp_dir.name, "export.zip")
        folder_in_zip = "Chillout [MP3]"
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
            for root, dirs, files in os.walk(audio_folder):
                for file in sorted(files):
                    full = os.path.join(root, file)
                    rel = os.path.relpath(full, audio_folder)
                    zf.write(full, arcname=os.path.join(folder_in_zip, rel))

        self.assertTrue(os.path.isfile(zip_path))
        with zipfile.ZipFile(zip_path, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("Chillout [MP3]/Song A.mp3", namelist)
            self.assertIn("Chillout [MP3]/Song B.mp3", namelist)
            self.assertIn("Chillout [MP3]/Chillout [MP3].m3u8", namelist)


if __name__ == "__main__":
    unittest.main()
