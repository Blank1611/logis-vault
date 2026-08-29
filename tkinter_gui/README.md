# YouTube Playlist Downloader (Desktop Tkinter GUI)

A lightweight, standalone desktop application built with Python's standard `tkinter` and `yt-dlp` for managing and downloading YouTube playlists with audio conversion and archive tracking.

---

## Features
* **Interactive Desktop GUI**: Built using pure Python Tkinter (no heavy GUI frameworks required).
* **Parallel Extraction & Batch Downloads**: Efficient concurrent metadata extraction and background downloading.
* **Exclusions & Archive Tracking**: Maintain playlist exclusion lists and prevent redownloading existing tracks.
* **Audio Processing**: High quality audio extraction (`copy`, `mp3_best`, `opus`).
* **Standalone & Portable**: Self-contained within this directory.

---

## Quickstart

### 1. Requirements
* Python 3.8+ (Python 3.10+ recommended)
* `ffmpeg` installed and in your system `PATH`

### 2. Installation
```powershell
pip install -r requirements.txt
```

### 3. Launching the App
```powershell
python yt_playlist_manager_gui_final.py
```

---

## Directory Structure
* `yt_playlist_manager_gui_final.py`: Main desktop application entry point.
* `yt_playlist_audio_tools.py`: Core extraction and download engine.
* `yt_playlist_gui_config.json`: Local playlist configuration and user settings.
* `docs/`:
  * `architecture/`: Threading architecture, parallel operations, logging.
  * `guides/`: Configuration, batch downloads, quality presets, folder structures.
  * `troubleshooting/`: Error classifications, crash recovery, UI responsiveness.
* `scripts/`: Standalone diagnostic and library maintenance utilities (`check_archive.py`, `rename_add_video_ids.py`, `debug_ytdlp_403.py`, etc.).
