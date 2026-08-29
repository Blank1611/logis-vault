# Parallel Operations Guide

## Overview
The application now supports running multiple operations simultaneously:
- **One download** at a time (to avoid YouTube bot detection)
- **Multiple audio extractions** in parallel (from different playlists)

## Operation Rules

### Download Operations
- ✓ Only **ONE** download can run at a time
- ✗ Cannot start new download while one is in progress
- ✓ Can extract audio from other playlists while downloading

### Audio Extraction Operations
- ✓ **Multiple** extractions can run simultaneously
- ✓ Can extract from different playlists at the same time
- ✗ Cannot extract from playlist currently being downloaded

## Usage Examples

### Example 1: Download + Extract from Different Playlists

**Step 1:** Start download for "Awesome" playlist
- Select "Awesome"
- Choose "1 - Download video + extract audio"
- Status: `🔽 Downloading: Awesome`

**Step 2:** While downloading, extract audio from "Hindi Old hits"
- Select "Hindi Old hits"
- Choose "3 - Extract audio only"
- Status: `🔽 Downloading: Awesome | 🎵 Extracting: Hindi Old hits`

**Step 3:** Extract from another playlist "Just music"
- Select "Just music"
- Choose "3 - Extract audio only"
- Status: `🔽 Downloading: Awesome | 🎵 Extracting: Hindi Old hits, Just music`

### Example 2: Multiple Extractions

**Step 1:** Extract from "Playlist A"
- Select "Playlist A"
- Choose "3 - Extract audio only"
- Status: `🎵 Extracting: Playlist A`

**Step 2:** Extract from "Playlist B"
- Select "Playlist B"
- Choose "3 - Extract audio only"
- Status: `🎵 Extracting: Playlist A, Playlist B`

**Step 3:** Extract from "Playlist C"
- Select "Playlist C"
- Choose "3 - Extract audio only"
- Status: `🎵 Extracting: Playlist A, Playlist B, Playlist C`

## Restrictions

### Cannot Do: Multiple Downloads
```
❌ Download "Awesome" + Download "Hindi Old hits"
```
**Reason:** Avoid YouTube bot detection

**Error Message:**
```
Download in Progress
A download is already running for 'Awesome'.
Please wait for it to complete or cancel it first.
```

### Cannot Do: Extract from Downloading Playlist
```
❌ Download "Awesome" + Extract "Awesome"
```
**Reason:** File conflicts and data corruption

**Error Message:**
```
Download in Progress
Cannot extract audio while downloading 'Awesome'.
Please wait for download to complete first.
```

### Cannot Do: Duplicate Extraction
```
❌ Extract "Awesome" + Extract "Awesome" again
```
**Reason:** Redundant operation

**Error Message:**
```
Extraction in Progress
Audio extraction is already running for 'Awesome'.
```

## Status Indicator

### Location
Bottom of window, below progress bar

### Format
```
🔽 Downloading: [playlist_name] | 🎵 Extracting: [playlist1], [playlist2], ...
```

### Examples

**Download only:**
```
🔽 Downloading: Awesome
```

**Extraction only:**
```
🎵 Extracting: Hindi Old hits
```

**Multiple extractions:**
```
🎵 Extracting: Hindi Old hits, Just music, Rock
```

**Download + Extractions:**
```
🔽 Downloading: Awesome | 🎵 Extracting: Hindi Old hits, Just music
```

**Idle:**
```
(empty)
```

## Cancellation

### Cancel Button Behavior

**When clicked:**
1. Shows list of all active operations
2. Asks for confirmation
3. Cancels ALL operations if confirmed

**Example Dialog:**
```
Cancel the following operations?

Download: 'Awesome'
Extraction: 'Hindi Old hits'
Extraction: 'Just music'

[Yes] [No]
```

### What Happens on Cancel
- All operations receive cancellation signal
- Each operation finishes current step
- Workers clean up and exit
- Status indicator updates

## Performance

### Resource Usage

**Download:**
- 1 worker thread
- Network I/O (primary bottleneck)
- Disk I/O (video writing)
- CPU: Low (~5-10%)

**Audio Extraction:**
- 4 worker threads per playlist (configurable)
- CPU: High (~50-80% per playlist)
- Disk I/O: High (reading videos, writing audio)

**Multiple Extractions:**
- CPU: Can reach 100% with 2-3 playlists
- Disk I/O: Very high
- Recommended: Max 2-3 simultaneous extractions

### Optimal Configurations

**High-end system (Ryzen 7, 32GB RAM):**
- 1 download + 2-3 extractions
- `max_extraction_workers: 4` per playlist

**Mid-range system (i5, 16GB RAM):**
- 1 download + 1-2 extractions
- `max_extraction_workers: 2-3` per playlist

**Low-end system (i3, 8GB RAM):**
- 1 download + 1 extraction
- `max_extraction_workers: 2` per playlist

## Benefits

### 1. Time Efficiency
**Before:**
```
Download Playlist A (30 min)
  → Extract Playlist A (10 min)
    → Download Playlist B (30 min)
      → Extract Playlist B (10 min)

Total: 80 minutes
```

**After:**
```
Download Playlist A (30 min)
  ├─ Extract Playlist B (10 min) ← Parallel
  └─ Extract Playlist C (10 min) ← Parallel

Total: 30 minutes (2.7x faster)
```

### 2. Resource Utilization
- Download: Uses network + minimal CPU
- Extraction: Uses CPU + disk
- Running both: Maximizes resource usage
- No idle time waiting

### 3. Flexibility
- Start extractions while downloading
- Queue up multiple extractions
- Cancel individual operations
- Monitor all operations at once

## Best Practices

### 1. Prioritize Downloads
- Start download first (limited by bot detection)
- Queue extractions while downloading
- Downloads are the bottleneck

### 2. Limit Concurrent Extractions
- Don't exceed CPU capacity
- Monitor system performance
- 2-3 extractions max recommended

### 3. Monitor Status
- Check status indicator regularly
- Watch for completion messages
- Verify operations completed successfully

### 4. Plan Operations
```
Good workflow:
1. Start download for large playlist
2. Extract audio from 2-3 already-downloaded playlists
3. Wait for download to complete
4. Extract audio from newly downloaded playlist
5. Start next download
```

## Troubleshooting

### UI Becomes Slow
**Symptom:** UI freezing or sluggish

**Cause:** Too many concurrent extractions

**Solution:**
- Cancel some extractions
- Reduce `max_extraction_workers` in config
- Wait for operations to complete

### Operations Not Starting
**Symptom:** Can't start new operation

**Check:**
1. Is download already running? (only 1 allowed)
2. Is extraction already running for this playlist?
3. Is download running for this playlist?

**Solution:**
- Wait for conflicting operation to complete
- Cancel conflicting operation
- Choose different playlist

### Status Not Updating
**Symptom:** Status indicator shows old information

**Cause:** UI polling issue

**Solution:**
- Wait a few seconds (updates every 50ms)
- Restart application if persists

### Operations Stuck
**Symptom:** Operation shows running but no progress

**Check:**
1. Check log window for errors
2. Check if process is actually running
3. Check disk space

**Solution:**
- Cancel operation
- Check logs for errors
- Restart operation

## Technical Details

### State Management

**Download tracking:**
```python
self.is_downloading = True/False
self.downloading_playlist = "Playlist Name"
self.download_worker = Thread object
```

**Extraction tracking:**
```python
self.extraction_workers = {
    "Playlist A": Thread object,
    "Playlist B": Thread object,
    ...
}
```

### Thread Safety
- Each operation has independent worker thread
- No shared state between operations
- Queue-based communication with UI
- Thread-safe cleanup on completion

### Operation Lifecycle

**Download:**
```
1. Check: No other download running
2. Create: Download worker thread
3. Track: Set is_downloading = True
4. Run: Download + extract audio
5. Cleanup: Set is_downloading = False
6. Update: Refresh UI
```

**Extraction:**
```
1. Check: Not downloading this playlist
2. Check: Not already extracting this playlist
3. Create: Extraction worker thread
4. Track: Add to extraction_workers dict
5. Run: Extract audio (parallel ffmpeg)
6. Cleanup: Remove from extraction_workers
7. Update: Refresh UI
```

## Configuration

### Adjust Extraction Workers
Edit `config.json`:
```json
{
  "max_extraction_workers": 4
}
```

**Values:**
- `2`: Low CPU usage, slower extraction
- `4`: Balanced (default)
- `8`: High CPU usage, faster extraction

### Monitor Resource Usage

**Windows Task Manager:**
- CPU: Should be <100% total
- Memory: Should have 2-4GB free
- Disk: Monitor read/write speeds

**Adjust based on:**
- System specifications
- Number of concurrent operations
- Performance requirements

## Summary

### What You Can Do
✓ Download 1 playlist + Extract from multiple others
✓ Extract from multiple playlists simultaneously
✓ Monitor all operations in status indicator
✓ Cancel all operations at once

### What You Cannot Do
✗ Download multiple playlists simultaneously
✗ Extract from playlist being downloaded
✗ Start duplicate operations

### Benefits
- 2-3x faster overall workflow
- Better resource utilization
- More flexible operation scheduling
- Real-time status monitoring

The parallel operations feature maximizes efficiency while respecting YouTube's rate limits!
