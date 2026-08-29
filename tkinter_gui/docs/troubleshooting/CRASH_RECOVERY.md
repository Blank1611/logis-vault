# Crash Recovery Guide

## Overview
The system is designed to be resilient to crashes, cancellations, and interruptions. Progress is saved incrementally to ensure minimal data loss.

## What Happens During a Crash

### Files Updated Immediately (Safe)
1. **archive.txt** - Updated after EACH successful download
2. **batch_progress.json** - Updated after EACH successful download
3. **Video files** - Written to disk as they download

### Result
If the app crashes during download:
- ✓ All successfully downloaded videos are tracked
- ✓ Batch progress reflects completed downloads
- ✓ No duplicate downloads on resume

## Crash Scenarios

### Scenario 1: Crash During Download

**What happens:**
```
Downloading video 1/200... ✓ Success (saved to archive + batch progress)
Downloading video 2/200... ✓ Success (saved to archive + batch progress)
Downloading video 3/200... ✓ Success (saved to archive + batch progress)
Downloading video 4/200... ⚠️ CRASH!
```

**State after crash:**
- Videos 1-3: ✓ In archive.txt
- Videos 1-3: ✓ Removed from batch_progress.json pending list
- Video 4: ✗ Not in archive (will retry on resume)
- Videos 5-200: Still in pending list

**On resume:**
- Skips videos 1-3 (already in archive)
- Retries video 4
- Continues with videos 5-200

### Scenario 2: Crash During Audio Extraction

**What happens:**
```
Downloaded 200 videos ✓
Extracting audio from video 1... ✓
Extracting audio from video 2... ✓
Extracting audio from video 3... ⚠️ CRASH!
```

**State after crash:**
- All 200 videos: ✓ Downloaded and in archive
- Audio files 1-2: ✓ Extracted
- Audio files 3-200: ✗ Not extracted

**On resume:**
- Choose "Extract audio only"
- Skips audio files 1-2 (already exist)
- Extracts audio files 3-200

### Scenario 3: Crash Before Batch Progress Update

**Old behavior (before fix):**
- Batch progress only updated at end
- Crash = lose all progress tracking
- Resume would try to re-download everything

**New behavior (after fix):**
- Batch progress updated after EACH video
- Crash = only lose current video
- Resume continues from next video

## Recovery Steps

### Step 1: Restart Application
Simply restart the app - no special recovery needed.

### Step 2: Select Playlist
Select the same playlist you were downloading.

### Step 3: Choose Resume
Click "Run on selected playlist" → "2 - Resume Download"

### Step 4: Verify
The system will:
- Load batch_progress.json
- Check archive.txt
- Skip already downloaded videos
- Continue from where it left off

## Verification

### Check What Was Downloaded
```powershell
# Count videos in playlist folder
Get-ChildItem "<base_path>\Awesome\*.mp4" | Measure-Object

# Check archive entries
Get-Content "<base_path>\Awesome\archive.txt" | Measure-Object -Line
```

### Check Batch Progress
```powershell
# View batch progress
Get-Content "<base_path>\Awesome\batch_progress.json" | ConvertFrom-Json
```

### Check Audio Files
```powershell
# Count audio files
Get-ChildItem "<base_path>\Awesome\Awesome\*.m4a" | Measure-Object
```

## Edge Cases

### Partial Video Download
**Problem**: Video partially downloaded, then crash

**Behavior**:
- Partial file exists on disk
- Not added to archive (verification failed)
- Next run will re-download completely

**Why**: `_video_exists_on_disk()` checks for complete files with video ID in filename

### Corrupted batch_progress.json
**Problem**: Progress file corrupted during crash

**Behavior**:
- System loads default empty progress
- Checks archive.txt for what's downloaded
- Skips archived videos
- Downloads remaining

**Recovery**: Delete batch_progress.json and start fresh

### Archive.txt Corrupted
**Problem**: Archive file corrupted

**Behavior**:
- System may re-download some videos
- Duplicate detection by filename
- yt-dlp skips if file exists

**Recovery**: Rebuild archive from filenames (see below)

## Manual Recovery

### Rebuild archive.txt from Files
```python
import os
import re

playlist_folder = r"E:\2tbhdd\songs\syst\New folder\youtube\Awesome"
archive_file = os.path.join(playlist_folder, "archive.txt")

# Extract video IDs from filenames
video_ids = []
for file in os.listdir(playlist_folder):
    if file.endswith('.mp4'):
        match = re.search(r'\[([a-zA-Z0-9_-]{11})\]', file)
        if match:
            video_ids.append(match.group(1))

# Write to archive
with open(archive_file, 'w') as f:
    f.write("# Rebuilt archive\n")
    for vid in sorted(set(video_ids)):
        f.write(f"youtube {vid}\n")

print(f"Rebuilt archive with {len(video_ids)} entries")
```

### Rebuild batch_progress.json
```python
import json
import os

playlist_folder = r"E:\2tbhdd\songs\syst\New folder\youtube\Awesome"
progress_file = os.path.join(playlist_folder, "batch_progress.json")

# Get all video IDs from playlist (you need to fetch this)
all_video_ids = [...]  # List of all video IDs in playlist

# Get downloaded IDs from archive
archive_file = os.path.join(playlist_folder, "archive.txt")
downloaded_ids = set()
with open(archive_file, 'r') as f:
    for line in f:
        if line.startswith('youtube '):
            downloaded_ids.add(line.split()[1])

# Calculate pending
pending_ids = [vid for vid in all_video_ids if vid not in downloaded_ids]

# Create progress
progress = {
    "total_videos": len(all_video_ids),
    "downloaded_count": len(downloaded_ids),
    "pending_video_ids": pending_ids,
    "last_batch_date": "2024-12-01 00:00:00",
    "batch_size": 200,
    "completed": len(pending_ids) == 0
}

with open(progress_file, 'w') as f:
    json.dump(progress, f, indent=2)

print(f"Rebuilt progress: {len(downloaded_ids)}/{len(all_video_ids)} downloaded")
```

## Best Practices

### 1. Regular Monitoring
- Check logs after each batch
- Verify video counts match expectations
- Monitor disk space

### 2. Backup Progress Files
```powershell
# Backup batch progress
Copy-Item "<base_path>\Awesome\batch_progress.json" `
          "<base_path>\Awesome\batch_progress_backup.json"

# Backup archive
Copy-Item "<base_path>\Awesome\archive.txt" `
          "<base_path>\Awesome\archive_backup.txt"
```

### 3. Clean Shutdown
- Use "Stop current task" button instead of force-closing
- Wait for current video to finish
- Progress saved up to last completed video

### 4. Disk Space
- Ensure enough space before starting
- Monitor during large downloads
- Crash due to full disk = partial files

## Troubleshooting

### Resume Not Working
**Symptoms**: Resume downloads same videos again

**Check**:
1. Is batch_progress.json present?
2. Are video IDs in archive.txt?
3. Do video files have IDs in filenames?

**Fix**:
- Rebuild archive from filenames
- Delete batch_progress.json and start fresh

### Missing Videos
**Symptoms**: Some videos not downloaded after crash

**Check**:
1. Check logs for errors
2. Verify batch_progress.json pending list
3. Check if videos are in excluded_ids

**Fix**:
- Resume download (will retry failed videos)
- Check excluded_ids in GUI config

### Duplicate Downloads
**Symptoms**: Same video downloaded twice

**Cause**: Archive not updated before crash

**Prevention**: Now fixed - archive updated immediately

**Fix**: Delete duplicate files manually

## System Guarantees

### What's Guaranteed
✓ No data loss for completed downloads
✓ Progress saved after each video
✓ Archive updated immediately
✓ Batch progress updated immediately
✓ Resume continues from correct position

### What's Not Guaranteed
✗ Current downloading video (will retry)
✗ Audio extraction progress (re-extract on resume)
✗ Logs (may lose last few lines)

## Summary

The system is designed to be crash-resistant:
- **Incremental saves**: Progress saved after each video
- **Dual tracking**: Both archive.txt and batch_progress.json
- **Verification**: Files verified before marking complete
- **Resume-friendly**: Always safe to resume after crash
- **No duplicates**: Archive prevents re-downloading

Just restart the app and click "Resume Download" - the system handles the rest!
