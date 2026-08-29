# Unified Download Button Guide

## Overview

The download system now uses a **single unified "Download Videos" button** that automatically handles all download scenarios intelligently.

## How It Works

### Smart Detection

When you click "Download Videos + Extract Audio", the system automatically:

1. **Checks for ongoing batch downloads**
   - If a batch is in progress → Resumes from where it left off
   - Detects new videos added to the playlist since last batch
   - Automatically adds new videos to the pending list

2. **Checks for completed batches**
   - If previous batch completed → Archives old progress file with creation datetime
   - Format: `batch_progress_YYYYMMDD_HHMMSS.json`
   - Creates fresh progress file if new batch needed

3. **Determines if batching is needed**
   - If videos to download > batch_size (default: 200) → Enables batch mode
   - If videos to download ≤ batch_size → Downloads all in one go

### Batch Progress Archiving

When a batch completes successfully:
- Old `batch_progress.json` is renamed to `batch_progress_YYYYMMDD_HHMMSS.json`
- Timestamp reflects when the batch was originally created
- New progress file created only if another large batch is needed
- Keeps history of all batch downloads for reference

## Usage Examples

### Scenario 1: New Playlist (500 videos)
1. Click "Download Videos + Extract Audio"
2. System detects 500 videos > 200 batch size
3. Downloads first 200 videos
4. Creates `batch_progress.json` to track remaining 300
5. Click "Download Videos" again to continue

### Scenario 2: Resuming Batch
1. Click "Download Videos + Extract Audio"
2. System detects existing `batch_progress.json`
3. Shows: "(Auto-resume batch)" in button text
4. Continues downloading remaining videos from last session

### Scenario 3: Adding New Songs to Completed Playlist
1. Playlist already fully downloaded (batch completed)
2. You add 5 new songs to YouTube playlist
3. Click "Download Videos + Extract Audio"
4. System archives old `batch_progress.json` → `batch_progress_20241202_143022.json`
5. Downloads only the 5 new songs (no batching needed)

### Scenario 4: New Videos During Batch
1. Batch in progress: 150/500 downloaded
2. You add 10 new videos to YouTube playlist
3. Click "Download Videos + Extract Audio"
4. System detects 10 new videos
5. Adds them to pending list: now 360 remaining
6. Continues downloading next batch

## Benefits

✅ **Simpler UX**: One button instead of two separate "Download" and "Resume" buttons

✅ **Automatic**: No need to remember which mode to use

✅ **Smart**: Handles all scenarios automatically

✅ **Safe**: Archives completed batches for history/reference

✅ **Flexible**: Works for both large batches and small updates

## Configuration

Batch size can be configured in `config.json`:

```json
{
  "batch_size": 200,
  "batch_delay": 300
}
```

- `batch_size`: Maximum videos per session (default: 200)
- `batch_delay`: Not used for multi-day batching (kept for compatibility)

## Bug Fix: Transient Error Handling

**Issue Fixed**: Videos with transient errors (file system issues, network timeouts) were being permanently excluded.

**Root Cause**: 
- Video IDs were added to `FAILED_VIDEO_IDS` before error classification
- All failed IDs were merged into excluded list at end, regardless of error type

**Solution**:
- Only add to `FAILED_VIDEO_IDS` if error is classified as permanent
- Error classification happens before adding to exclusion list
- Transient errors are logged but video will retry in next session

**Transient Errors** (will retry):
- File system errors: "No such file or directory", "Errno 2"
- Network issues: "connection reset", "timeout", "network"
- Fragment download failures: "fragment", "part-frag"
- Server errors: HTTP 5xx, HTTP 429 (rate limit)

**Permanent Errors** (will exclude):
- Video unavailable, private, deleted
- Copyright claims, account terminated
- Members-only, age-restricted content

## Technical Details

### Batch Progress States

1. **No progress file**: First download or small update
2. **Progress file with pending videos**: Ongoing batch (resume)
3. **Progress file with completed=true**: Batch finished (archive and start fresh)

### Archive Naming

- Format: `batch_progress_YYYYMMDD_HHMMSS.json`
- Timestamp: File creation time (when batch started)
- Location: Same folder as playlist videos

### New Video Detection

During batch resume, the system:
1. Compares current playlist entries with pending IDs
2. Identifies videos not in pending list
3. Adds new videos to batch progress
4. Updates total count
5. Continues downloading

## See Also

- [Batch Download Guide](BATCH_DOWNLOAD_GUIDE.md) - Original batch download documentation
- [Parallel Operations](PARALLEL_OPERATIONS.md) - Concurrent download + extraction
- [Error Classification](ERROR_CLASSIFICATION.md) - Smart error handling
