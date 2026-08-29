# Complete Folder Structure

## Overview
This document shows the complete folder structure for the YouTube Playlist Manager application.

## Application Directory (Project Root)
```
<project_directory>/
├── yt_playlist_manager_gui_final.py     # Main GUI application
├── yt_playlist_audio_tools.py           # Core functionality
├── config.json                           # Application configuration
├── yt_playlist_gui_config.json          # GUI state & playlists
├── requirements.txt                      # Python dependencies
│
└── ytdld/                                # Virtual environment (optional)
    └── ...
```

## Base Download Path Structure
```
<base_download_path>/                     # E.g., E:\2tbhdd\songs\syst\New folder\youtube
│
├── logs/                                 # All application logs
│   ├── app_startup.log                  # Current startup log
│   ├── app_startup_20241201_01.log     # Rotated startup logs
│   │
│   ├── Awesome/
│   │   ├── Awesome.log                  # Current playlist log
│   │   ├── Awesome_20241201_01.log     # Rotated playlist logs
│   │   └── Awesome_20241130_01.log
│   │
│   ├── Hindi_Old_hits/
│   │   ├── Hindi_Old_hits.log
│   │   └── Hindi_Old_hits_20241201_01.log
│   │
│   └── Just_music/
│       ├── Just_music.log
│       └── Just_music_20241201_01.log
│
├── Awesome/                              # Playlist folder
│   ├── playlist_info_snapshot/          # Playlist metadata
│   │   ├── playlist_info.json          # Current snapshot
│   │   ├── playlist_info_20241201_143022.json
│   │   └── playlist_info_20241130_091533.json
│   │
│   ├── archive.txt                      # Custom download archive
│   │
│   ├── Awesome/                         # Audio files subfolder
│   │   ├── Song1.m4a                   # Extracted audio (copy mode)
│   │   ├── Song2.m4a
│   │   └── Song3.m4a
│   │
│   ├── Song1 [video_id1].mp4           # Video files
│   ├── Song2 [video_id2].mp4
│   └── Song3 [video_id3].mp4
│
├── Hindi_Old_hits/                       # Another playlist
│   ├── playlist_info_snapshot/
│   │   └── playlist_info.json
│   ├── archive.txt
│   ├── Hindi_Old_hits/                  # Audio subfolder
│   │   └── *.m4a
│   └── *.mp4                            # Video files
│
└── Just_music/                           # Another playlist
    ├── playlist_info_snapshot/
    │   └── playlist_info.json
    ├── archive.txt
    ├── Just_music/                      # Audio subfolder
    │   └── *.m4a
    └── *.mp4                            # Video files
```

## Detailed Breakdown

### Application Logs (`<base_path>/logs/`)
- **Location**: In the base download path
- **Purpose**: Application-level logs (startup, errors, etc.)
- **Files**:
  - `app_startup.log` - Current startup operations
  - `app_startup_YYYYMMDD_RR.log` - Rotated logs

### Playlist Logs (`<base_path>/logs/<playlist_name>/`)
- **Location**: In base download path
- **Purpose**: Per-playlist operation logs (downloads, extractions)
- **Structure**: Each playlist has its own subdirectory
- **Files**:
  - `<playlist_name>.log` - Current operations
  - `<playlist_name>_YYYYMMDD_RR.log` - Rotated logs

### Playlist Folders (`<base_path>/<playlist_name>/`)
- **Location**: In base download path
- **Purpose**: Store videos, audio, and metadata for each playlist
- **Contents**:
  - `playlist_info_snapshot/` - Playlist metadata with versioning
  - `archive.txt` - Custom download tracking
  - `<playlist_name>/` - Audio files subfolder
  - `*.mp4` - Video files with IDs in filename

### Playlist Info Snapshots (`<base_path>/<playlist_name>/playlist_info_snapshot/`)
- **Location**: Inside each playlist folder
- **Purpose**: Store playlist metadata with version history
- **Files**:
  - `playlist_info.json` - Current playlist data
  - `playlist_info_YYYYMMDD_HHMMSS.json` - Historical snapshots

### Audio Files (`<base_path>/<playlist_name>/<playlist_name>/`)
- **Location**: Subfolder within playlist folder
- **Purpose**: Store extracted audio files
- **Format**: Depends on `audio_extract_mode`:
  - `copy` mode: `.m4a` or `.opus` (original codec)
  - `mp3_best` mode: `.mp3` (VBR quality 0)
  - `mp3_high` mode: `.mp3` (VBR quality 2)
  - `opus` mode: `.opus` (128kbps)

### Video Files (`<base_path>/<playlist_name>/`)
- **Location**: Root of playlist folder
- **Format**: `Title [video_id].mp4`
- **Example**: `Alec Benjamin - Let Me Down Slowly [PKonqhZ5PsA].mp4`

## Path Examples

### Real-World Example
If your `base_download_path` is `E:\2tbhdd\songs\syst\New folder\youtube`:

```
E:\2tbhdd\songs\syst\New folder\youtube\
├── logs\
│   ├── Awesome\
│   │   └── Awesome.log
│   └── Hindi_Old_hits\
│       └── Hindi_Old_hits.log
│
├── Awesome\
│   ├── playlist_info_snapshot\
│   │   └── playlist_info.json
│   ├── archive.txt
│   ├── Awesome\
│   │   ├── Song1.m4a
│   │   └── Song2.m4a
│   ├── Song1 [PKonqhZ5PsA].mp4
│   └── Song2 [tlEAEJKIatc].mp4
│
└── Hindi_Old_hits\
    ├── playlist_info_snapshot\
    │   └── playlist_info.json
    ├── archive.txt
    ├── Hindi_Old_hits\
    │   └── *.m4a
    └── *.mp4
```

## Benefits of This Structure

### 1. Organization
- Clear separation between app logs and playlist logs
- Each playlist has its own log directory
- Easy to find logs for specific playlists

### 2. Portability
- Playlist logs stay with playlist data
- Moving base path moves everything together
- App logs stay with application

### 3. Scalability
- No log file clutter in playlist folders
- Centralized log management per playlist
- Easy to clean up old logs

### 4. Maintenance
- Delete old playlist logs without affecting videos
- Archive entire playlists with their logs
- Separate app logs from data logs

## Configuration

The structure is controlled by:
- `base_download_path` in `config.json` - Where playlists and their logs are stored
- Application directory - Where app logs are stored

Example `config.json`:
```json
{
  "base_download_path": "E:\\2tbhdd\\songs\\syst\\New folder\\youtube",
  "cookies_file": "E:\\2tbhdd\\songs\\syst\\New folder\\youtube\\yt-cookies.txt",
  "use_browser_cookies": false,
  "browser_name": "chrome",
  "audio_extract_mode": "copy",
  "max_extraction_workers": 4,
  "max_log_lines": 5000,
  "max_log_size_mb": 10
}
```
