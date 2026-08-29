# Custom Archive Logic Improvements

## Summary
Replaced yt-dlp's unreliable `download_archive` with custom archive management to fix duplicate ID issues.

## Folder Structure
```
BASE_DOWNLOAD_PATH/
└── Playlist_Name/
    ├── archive.txt                          # Custom archive file
    ├── playlist_info_snapshot/              # NEW: Snapshot directory
    │   ├── playlist_info.json              # Current playlist info
    │   ├── playlist_info_20241201_143022.json  # Archived snapshots
    │   └── playlist_info_20241130_091533.json
    ├── Playlist_Name/                       # Audio folder (MP3s)
    │   └── *.mp3
    └── *.mp4                                # Video files
```

## Changes Made

### 1. Custom Archive Functions (yt_playlist_audio_tools.py)

#### New Functions:
- `_load_custom_archive(archive_file)` - Load video IDs from archive.txt
- `_save_custom_archive(archive_file, video_ids)` - Save all IDs to archive
- `_add_to_custom_archive(archive_file, video_id)` - Append single ID to archive
- `_video_exists_on_disk(playlist_folder, video_id)` - Check if video file exists
- `_should_download_video(archive_file, playlist_folder, video_id)` - Determine if download needed

#### Download Logic:
Downloads a video ONLY if:
- **a)** ID does not exist in archive.txt, OR
- **b)** ID exists in archive but file not actually on disk

After successful download:
1. Verifies file exists on disk
2. Only then adds ID to archive.txt

### 2. Playlist Info Versioning (yt_playlist_audio_tools.py)

#### New Function:
- `_save_playlist_info_with_versioning(playlist_folder, info)` - Saves playlist_info.json with automatic versioning

When saving playlist_info.json:
- Saves to `playlist_info_snapshot/` subdirectory
- If file exists, renames old file with creation date (e.g., `playlist_info_20241201_143022.json`)
- Then saves new file as `playlist_info.json`
- All snapshots kept in same subdirectory for easy access

### 3. Automatic Folder Creation (yt_playlist_manager_gui_final.py)

When adding a playlist:
1. **Immediately creates** playlist folder structure:
   - Main playlist folder
   - Audio subfolder
   - `playlist_info_snapshot/` subdirectory
2. **Immediately saves** playlist_info.json with all entries to snapshot directory
3. No longer waits for first download attempt

### 4. Filename Format Update

Videos now downloaded with ID in filename:
- Format: `%(title)s [%(id)s].%(ext)s`
- Example: `Alec Benjamin - Let Me Down Slowly [PKonqhZ5PsA].mp4`

This ensures reliable ID-based verification.

## Benefits

1. **No Duplicate IDs**: Custom logic prevents archive.txt from having duplicate entries
2. **Reliable Tracking**: Only adds to archive after verifying file exists on disk
3. **Re-download Missing**: Automatically re-downloads if file missing but ID in archive
4. **Better Organization**: Folders created immediately when playlist added
5. **Version History**: Old playlist_info.json files preserved with timestamps
6. **Accurate Stats**: Stats reflect actual downloaded files, not phantom archive entries

## Migration for Existing Playlists

### Automatic Migration (On Startup)
When you start the GUI, it will automatically:
1. Check all existing playlists for proper folder structure **in parallel** (up to 5 concurrent)
2. Create missing `playlist_info_snapshot/` directories
3. Fetch and save `playlist_info.json` if missing
4. Log all actions to `logs/app_startup.log` with timestamps
5. Display total time taken for startup operations

**Performance**: With parallel processing, startup is ~5x faster for multiple playlists!

### Manual Migration (Button)
A new button "Fix folder structure for all" allows you to:
- Manually trigger folder structure creation for all playlists
- Useful if automatic migration fails or for troubleshooting
- Shows progress in the log window

### What Gets Created
For each existing playlist:
- Main playlist folder (if missing)
- Audio subfolder (if missing)
- `playlist_info_snapshot/` subdirectory (if missing)
- `playlist_info.json` in snapshot directory (if missing)

## Migration Notes

- Existing archive.txt files will continue to work
- New downloads will use the improved logic
- Video IDs now included in filenames for reliable verification
- Existing playlists will be automatically upgraded on first startup
