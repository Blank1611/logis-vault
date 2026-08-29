# Batch Download Guide

## Overview
Batch downloading allows you to download large playlists (500+ videos) over multiple days to avoid YouTube's bot detection. Downloads are split into configurable batches (default: 200 videos per session).

## Why Batch Downloads?

### YouTube Bot Detection
- Downloading too many videos in one session can trigger YouTube's bot detection
- Recommended limit: ~200 videos per day
- Batch downloads spread the load over multiple days

### Benefits
- **Avoid blocks**: Stay under YouTube's radar
- **Resumable**: Continue where you left off
- **Progress tracking**: Know exactly what's remaining
- **Flexible**: Download at your own pace

## How It Works

### Automatic Batching
When you start a download for a playlist with more than 200 videos (configurable):

1. **First Session**:
   - Downloads first 200 videos
   - Creates `batch_progress.json` in playlist folder
   - Shows remaining count

2. **Subsequent Sessions**:
   - Click "Resume Download"
   - Downloads next 200 videos
   - Updates progress file

3. **Completion**:
   - When all videos downloaded
   - Progress file marked as completed
   - Can be deleted or kept for reference

### Progress Tracking

Progress is stored in `<playlist_folder>/batch_progress.json`:

```json
{
  "total_videos": 600,
  "downloaded_count": 200,
  "pending_video_ids": ["vid1", "vid2", "..."],
  "last_batch_date": "2024-12-01 16:30:45",
  "batch_size": 200,
  "completed": false
}
```

## Usage

### Starting a New Download

1. Select playlist in GUI
2. Click "Run on selected playlist"
3. Choose "1 - Download video + extract audio (New/Full Download)"
4. If playlist has >200 videos, batching activates automatically

**Output:**
```
============================================================
BATCH DOWNLOAD MODE ENABLED
============================================================
Total videos to download: 600
Batch size: 200
Estimated batches: 3
This session will download: 200 videos
============================================================

⚠️  Note: 400 videos will remain for next batch
   Run 'Resume Download' to continue downloading remaining videos
```

### Resuming a Download

1. Select same playlist
2. Click "Run on selected playlist"
3. Choose "2 - Resume Download (Continue from last batch)"

**Output:**
```
============================================================
RESUMING BATCH DOWNLOAD
============================================================
Total videos in playlist: 600
Already downloaded: 200
Remaining: 400
Last batch: 2024-12-01 16:30:45
Batch size: 200
============================================================

Starting download of 200 videos in this batch...
```

### Checking Progress

After each batch completes:

```
============================================================
BATCH PROGRESS UPDATE
============================================================
Total videos: 600
Downloaded: 400
Remaining: 200
⚠️  200 videos remaining
   Run 'Resume Download' to continue
============================================================
```

When complete:

```
============================================================
BATCH PROGRESS UPDATE
============================================================
Total videos: 600
Downloaded: 600
Remaining: 0
✓ All videos downloaded!
============================================================
```

## Configuration

### Batch Size

Edit `config.json` to change batch size:

```json
{
  "batch_size": 200
}
```

**Recommended values:**
- **Conservative**: 150 (safer, more batches)
- **Default**: 200 (balanced)
- **Aggressive**: 300 (faster, higher risk)

### Example Scenarios

#### Small Playlist (< 200 videos)
- No batching
- Downloads all at once
- No progress file created

#### Medium Playlist (200-400 videos)
- 2 batches
- Day 1: 200 videos
- Day 2: Remaining videos

#### Large Playlist (600 videos)
- 3 batches
- Day 1: 200 videos
- Day 2: 200 videos
- Day 3: 200 videos

#### Very Large Playlist (1000 videos)
- 5 batches
- Spread over 5 days
- ~200 videos per day

## Progress File Location

```
<base_download_path>/<playlist_name>/batch_progress.json
```

Example:
```
E:\2tbhdd\songs\syst\New folder\youtube\
└── Awesome/
    ├── batch_progress.json          # Progress tracking
    ├── archive.txt                   # Downloaded IDs
    ├── playlist_info_snapshot/
    └── *.mp4
```

## Handling New Videos Added to Playlist

### Automatic Detection
When you resume a batch download, the system automatically:
1. Fetches current playlist entries
2. Compares with pending IDs from last batch
3. Detects any new videos added since last batch
4. Adds new videos to the pending list
5. Updates total count

### Example Scenario

**Day 1:** Start download (600 videos)
- Downloads 200 videos
- Pending: 400 videos

**Day 2:** You add 50 new videos to the YouTube playlist

**Day 2 Resume:**
```
🆕 Detected 50 NEW videos added to playlist since last batch
   Updated batch progress to include new videos

Total videos in playlist: 650
Already downloaded: 200
Remaining (including new): 450
```

**Result:**
- Old pending videos: 400
- New videos: 50
- Total to download: 450
- All videos will be downloaded over remaining batches

### Benefits
- ✓ Never miss new videos
- ✓ Automatic detection
- ✓ Seamless integration
- ✓ No manual intervention needed

## Best Practices

### 1. Daily Downloads
- Download one batch per day
- Reduces risk of detection
- Sustainable approach

### 2. Monitor Progress
- Check batch_progress.json
- Verify downloads completed
- Resume if interrupted

### 3. Don't Mix Modes
- Don't start new download while batch in progress
- Always use "Resume Download" for ongoing batches
- Complete batch before starting new playlist

### 4. Backup Progress
- Progress file is small (few KB)
- Backup if doing long downloads
- Can manually edit if needed

## Troubleshooting

### Progress File Missing
**Problem**: batch_progress.json deleted or missing

**Solution**:
- Start new download (not resume)
- System will re-scan and create new progress
- Already downloaded videos will be skipped

### Wrong Batch Count
**Problem**: Progress shows wrong numbers

**Solution**:
- Delete batch_progress.json
- Start new download
- System will recalculate

### Stuck Progress
**Problem**: Resume doesn't download anything

**Solution**:
1. Check if all videos already downloaded
2. Verify batch_progress.json has pending IDs
3. Delete progress file and start fresh if needed

### Want to Change Batch Size Mid-Download
**Problem**: Started with 200, want to change to 150

**Solution**:
1. Edit config.json: `"batch_size": 150`
2. Resume download
3. Next batch will use new size
4. Already downloaded videos unaffected

## Manual Progress Management

### View Progress
```powershell
# Windows PowerShell
Get-Content "<base_path>\Awesome\batch_progress.json" | ConvertFrom-Json
```

### Reset Progress
```powershell
# Delete progress file to start fresh
Remove-Item "<base_path>\Awesome\batch_progress.json"
```

### Edit Progress
Open `batch_progress.json` in text editor:
- Remove IDs from `pending_video_ids` to skip them
- Adjust `downloaded_count` if needed
- Change `batch_size` for next batch

## Example Workflow

### Day 1: Start Download
```
1. Select "Awesome" playlist (600 videos)
2. Click "Run on selected playlist"
3. Choose "1 - Download video + extract audio"
4. System downloads 200 videos
5. Creates batch_progress.json
6. Shows "400 videos remaining"
```

### Day 2: Resume
```
1. Select "Awesome" playlist
2. Click "Run on selected playlist"
3. Choose "2 - Resume Download"
4. System downloads next 200 videos
5. Updates batch_progress.json
6. Shows "200 videos remaining"
```

### Day 3: Complete
```
1. Select "Awesome" playlist
2. Click "Run on selected playlist"
3. Choose "2 - Resume Download"
4. System downloads final 200 videos
5. Marks batch as completed
6. Shows "✓ All videos downloaded!"
```

## Integration with Other Features

### Works With:
- ✓ Custom archive tracking
- ✓ Parallel audio extraction
- ✓ Log rotation
- ✓ Progress callbacks
- ✓ Cancellation

### Batch + Audio Extraction
- Each batch downloads videos
- Then extracts audio for that batch
- Next batch continues same pattern

### Batch + Cancellation
- Can cancel during batch
- Progress saved up to last completed video
- Resume continues from where stopped

## Configuration Example

Complete `config.json` with batch settings:

```json
{
  "base_download_path": "E:\\2tbhdd\\songs\\syst\\New folder\\youtube",
  "cookies_file": "E:\\2tbhdd\\songs\\syst\\New folder\\youtube\\yt-cookies.txt",
  "use_browser_cookies": false,
  "browser_name": "chrome",
  "audio_extract_mode": "copy",
  "max_extraction_workers": 4,
  "max_log_lines": 5000,
  "max_log_size_mb": 10,
  "batch_size": 200
}
```
