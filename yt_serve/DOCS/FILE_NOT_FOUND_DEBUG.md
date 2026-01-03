# File Not Found After Download - Debugging Guide

## Issue
Videos show "Download completed but file not found on disk" and get added to exclusion list, even though they were downloaded successfully in previous batches.

## Root Causes

### 1. File Detection Logic Issues (MOST COMMON)
- Video was downloaded successfully in a previous batch
- File exists on disk but doesn't match expected naming pattern
- System tries to re-download, fails to find file, adds to exclusion list
- **This is NOT a permanent error and should NOT exclude the video**

### 2. Naming Pattern Mismatches
- Expected pattern: `Title [VideoID].ext` or `Title_VideoID.ext`
- If file uses different pattern, it won't be detected
- Special characters in titles can cause sanitization differences
- Old format files (title only, no ID) won't be detected unless `ENABLE_OLD_FORMAT_AUTO_RENAME` is enabled

### 3. File System Timing Issues
- yt-dlp may report success before the file is fully written to disk
- File system operations (especially on network drives or slow disks) can have delays
- The verification check was happening immediately after download completion

### 4. Incomplete Downloads
- `.part` files indicate incomplete downloads
- If yt-dlp crashes or is interrupted, `.part` files remain
- These files are not detected by the verification logic

## Changes Made

### 1. Prevent False Exclusions (CRITICAL FIX)
- Videos that fail file detection are NO LONGER added to exclusion list
- "File not found after download" is treated as a detection issue, not a permanent error
- This prevents already-downloaded videos from being permanently excluded

### 2. Archive Check Before Download
- Before attempting download, checks if video is already in archive
- If in archive and file exists, skips download entirely
- Prevents unnecessary re-download attempts

### 3. Enhanced Debug Logging in _should_download_video()
When a video in archive is missing on disk, logs:
- Archive file path
- Playlist folder path
- All files containing the video ID
- Whether files match expected pattern
- Total video files in folder

### 4. Added Wait Logic
The `_get_video_file_path()` function now accepts a `wait_for_file` parameter:
- When `True`, waits up to 5 seconds for the file to appear
- Checks every 0.5 seconds (10 attempts total)
- Used immediately after download completion

### 5. Enhanced Debug Logging After Download
When a file is not found after download, logs:
- Video ID being searched for
- Playlist folder path
- Total number of video files in folder
- Any `.part` files (incomplete downloads)
- Files that contain the video ID but don't match the expected pattern

### 6. Download Result Logging
Now logs the return value from `ydl.download()`:
- `0` = success
- `1` = error
- Helps identify if yt-dlp actually succeeded

## What to Check in Logs

### Normal Successful Download
```
[1/2] Downloading: 87XbYi98DTg
  Progress: 654/1639 total (985 remaining)
  yt-dlp download() returned: 0
  ✓ Download verified, adding 87XbYi98DTg to archive
```

### Incomplete Download (.part file) - MOST COMMON ISSUE
```
[1/2] Downloading: 87XbYi98DTg
  Progress: 654/1639 total (985 remaining)
  yt-dlp download() returned: 0
  ⚠️  Incomplete download detected (.part file)
      File: Title [87XbYi98DTg].mp4.part
      This indicates the download was interrupted or failed
      Delete the .part file and retry download
```

**Solution**: Use the cleanup script:
```bash
python yt_serve/cleanup_part_files.py "E:\Downloads\Playlist" "87XbYi98DTg" --delete
```

### File System Delay (Now Fixed)
```
[1/2] Downloading: 87XbYi98DTg
  Progress: 654/1639 total (985 remaining)
  yt-dlp download() returned: 0
  [DEBUG] Video file not found for ID: 87XbYi98DTg (attempt 1)
  [DEBUG] Video file not found for ID: 87XbYi98DTg (attempt 2)
  ✓ Download verified, adding 87XbYi98DTg to archive
```

### Incomplete Download (.part file)
```
[1/2] Downloading: 87XbYi98DTg
  Progress: 654/1639 total (985 remaining)
  yt-dlp download() returned: 1
  [DEBUG] Video file not found for ID: 87XbYi98DTg
  [DEBUG] Found 1 .part files (incomplete downloads)
  [DEBUG] Found incomplete download: Title [87XbYi98DTg].mp4.part
  ⚠️  Download completed but file not found on disk for 87XbYi98DTg
```

### Naming Pattern Mismatch
```
[1/2] Downloading: 87XbYi98DTg
  Progress: 654/1639 total (985 remaining)
  yt-dlp download() returned: 0
  [DEBUG] Video file not found for ID: 87XbYi98DTg
  [DEBUG] Files containing video ID but not matching pattern:
  [DEBUG]   - Title_87XbYi98DTg.mp4
  ⚠️  Download completed but file not found on disk for 87XbYi98DTg
```

## Next Steps

### If Issue Persists

1. **Check the debug logs** for the specific video ID
2. **Look for `.part` files** in the playlist folder
3. **Verify the actual filename** of downloaded videos
4. **Check yt-dlp return code** (should be 0 for success)
5. **Check disk space** and write permissions

### Manual Recovery

If videos are downloaded but not detected:

1. Look for `.part` files and remove them (they're incomplete)
2. Check if files exist with the video ID but different naming
3. Manually add video IDs to `archive.txt` if files are confirmed present
4. Re-run download to skip already-present videos

### Configuration Check

Verify output template in code:
```python
"outtmpl": os.path.join(playlist_folder, "%(title)s [%(id)s].%(ext)s")
```

This should produce files like:
```
My Video Title [87XbYi98DTg].mp4
```

## Diagnostic Tools

### 1. Check Video File Status
Use `check_video_file.py` to diagnose file detection issues:

```bash
python yt_serve/check_video_file.py "C:\Downloads\MyPlaylist" "87XbYi98DTg"
```

This will:
- Check if video ID is in archive.txt
- Search for files matching expected patterns
- List files containing the video ID
- Check for incomplete downloads (.part files)
- Provide recommendations

### 2. Clean Up Incomplete Downloads
Use `cleanup_part_files.py` to remove .part files:

```bash
# Dry run - show what would be deleted
python yt_serve/cleanup_part_files.py "C:\Downloads\MyPlaylist"

# Delete all .part files
python yt_serve/cleanup_part_files.py "C:\Downloads\MyPlaylist" --delete

# Delete .part file for specific video
python yt_serve/cleanup_part_files.py "C:\Downloads\MyPlaylist" "87XbYi98DTg" --delete
```

## Prevention

- Videos with file detection issues are NO LONGER added to exclusion list
- Archive check before download prevents unnecessary re-download attempts
- The wait logic should prevent most timing issues
- Enhanced logging will help diagnose remaining issues
- Consider increasing wait time if on slow/network drives

## Removing False Exclusions

If videos were incorrectly added to exclusion list in previous runs:

1. Check your playlist's excluded_ids in the GUI config
2. Remove video IDs that shouldn't be excluded
3. The videos will be included in next download check
4. If files already exist, they'll be detected and skipped
