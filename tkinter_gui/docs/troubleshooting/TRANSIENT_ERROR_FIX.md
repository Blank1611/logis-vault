# Transient Error Exclusion Bug Fix

## Problem

Video ID `dCWj-XGQcXs` was permanently excluded from downloads even though it failed with a **transient error** (file system issue):

```
ERROR: Unable to download video: [Errno 2] No such file or directory: 
'E:\\2tbhdd\\songs\\syst\\New folder\\youtube\\Hindi\\Zubaida [dCWj-XGQcXs].mp4.part-Frag32'
```

The system correctly logged:
```
[INFO] Transient error for dCWj-XGQcXs - will retry in next session
```

But the video was still added to the `excluded_ids` list, preventing future retry attempts.

## Root Cause

The bug occurred in two places in `yt_playlist_audio_tools.py`:

### 1. Progress Hook (`_progress_hook_custom`)
```python
if status == "error":
    FAILED_VIDEO_IDS.add(vid)  # ❌ Added BEFORE classification
    _add_excluded_id_to_gui_config(GLOBAL_CURRENT_PLAYLIST_URL, vid, msg)
```

### 2. Download Exception Handler
```python
except Exception as e:
    FAILED_VIDEO_IDS.add(vid)  # ❌ Added BEFORE classification
    _add_excluded_id_to_gui_config(GLOBAL_CURRENT_PLAYLIST_URL, vid, error_msg)
```

### 3. Final Merge Loop
```python
# At end of download function
for vid in list(FAILED_VIDEO_IDS):
    _add_excluded_id_to_gui_config(url, vid)  # ❌ No error message = can't classify
```

**The Issue**: Video IDs were added to `FAILED_VIDEO_IDS` **before** error classification, and then blindly merged into the exclusion list at the end.

## Solution

### Changes Made

1. **Only add to FAILED_VIDEO_IDS if permanent error**:
```python
if status == "error":
    print(f"[WARN] Download failed (hook) for {vid}: {msg}")
    if GLOBAL_CURRENT_PLAYLIST_URL:
        _add_excluded_id_to_gui_config(GLOBAL_CURRENT_PLAYLIST_URL, vid, msg)
        # ✅ Only add if permanent error
        if _is_permanent_error(msg):
            FAILED_VIDEO_IDS.add(vid)
```

2. **Same fix in exception handler**:
```python
except Exception as e:
    error_msg = str(e)
    print(f"[WARN] Download failed for {vid}: {error_msg}")
    if GLOBAL_CURRENT_PLAYLIST_URL:
        _add_excluded_id_to_gui_config(GLOBAL_CURRENT_PLAYLIST_URL, vid, error_msg)
        # ✅ Only add if permanent error
        if _is_permanent_error(error_msg):
            FAILED_VIDEO_IDS.add(vid)
```

3. **Removed redundant final merge loop**:
```python
# Note: Failed IDs are already persisted to GUI config during download
# FAILED_VIDEO_IDS now only contains permanent failures for stats display
```

### Manual Fix Applied

Removed `dCWj-XGQcXs` from the "Hindi" playlist's `excluded_ids` in `yt_playlist_gui_config.json` since it was incorrectly excluded due to a transient error.

## Error Classification

The `_is_permanent_error()` function correctly identifies error types:

### Transient Errors (Will Retry)
- File system: `"no such file or directory"`, `"errno 2"`
- Network: `"connection reset"`, `"connection refused"`, `"timeout"`, `"network"`
- Fragments: `"fragment"`, `"part-frag"`, `".part"`
- Server: `"http error 5"` (5xx), `"http error 429"` (rate limit)

### Permanent Errors (Will Exclude)
- Availability: `"video unavailable"`, `"private video"`, `"deleted video"`
- Removal: `"has been removed"`, `"account associated with this video has been terminated"`
- Access: `"members-only content"`, `"join this channel"`, `"age-restricted"`
- Copyright: `"copyright"`

## Testing

After this fix:
1. Videos with transient errors will be logged but NOT excluded
2. They will be retried in the next download session
3. Only permanent errors will add videos to `excluded_ids`
4. `FAILED_VIDEO_IDS` now accurately reflects only permanent failures

## Impact

- **Before**: Transient errors (network glitches, file system issues) permanently excluded videos
- **After**: Only genuine permanent errors (unavailable, private, deleted) exclude videos
- **Result**: More reliable downloads with automatic retry for temporary failures

## Related Files

- `yt_playlist_audio_tools.py` - Core download logic with error handling
- `yt_playlist_gui_config.json` - Playlist configuration with excluded_ids
- `ERROR_CLASSIFICATION.md` - Documentation of error classification system
- `UNIFIED_DOWNLOAD_GUIDE.md` - Updated with bug fix details
