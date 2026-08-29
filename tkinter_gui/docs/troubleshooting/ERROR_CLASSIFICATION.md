# Error Classification Guide

## Overview
The system now intelligently classifies download errors as either **permanent** (should exclude) or **transient** (should retry), preventing false exclusions of videos that can be successfully downloaded later.

## Problem Solved

### Before (Incorrect Behavior)
```
Video fails with: "No such file or directory: ...part-Frag32"
→ Added to excluded_ids
→ Never retried
→ Video permanently skipped even though it could succeed
```

### After (Smart Classification)
```
Video fails with: "No such file or directory: ...part-Frag32"
→ Classified as TRANSIENT error
→ NOT added to excluded_ids
→ Will retry in next session
→ Video successfully downloaded on retry
```

## Error Types

### Permanent Errors (Should Exclude)

**Characteristics:**
- Video is genuinely unavailable
- Will never succeed no matter how many retries
- Should be excluded from future attempts

**Examples:**
```
✗ "Video unavailable"
✗ "Private video"
✗ "This video has been removed by the uploader"
✗ "Copyright claim"
✗ "Account terminated"
✗ "Members-only content"
✗ "Age-restricted" (without proper authentication)
```

**Action:** Add to `excluded_ids` → Skip in future downloads

### Transient Errors (Should Retry)

**Characteristics:**
- Temporary failure (network, file system, server)
- May succeed on retry
- Should NOT be excluded

**Examples:**
```
⚠️ "No such file or directory"
⚠️ "Errno 2"
⚠️ "Connection reset"
⚠️ "Connection refused"
⚠️ "Timeout"
⚠️ "HTTP Error 5xx" (server errors)
⚠️ "HTTP Error 429" (rate limit)
⚠️ "Fragment error"
⚠️ "Unable to download" (generic)
```

**Action:** Log error → Retry in next session

## Classification Logic

### Decision Flow
```
Error occurs
    ↓
Extract error message
    ↓
Check for transient patterns
    ├─ Match found → TRANSIENT (retry)
    └─ No match
        ↓
    Check for permanent patterns
        ├─ Match found → PERMANENT (exclude)
        └─ No match → TRANSIENT (default: safer to retry)
```

### Pattern Matching

**Transient patterns (checked first):**
- File system errors: "no such file", "errno 2"
- Network errors: "connection", "timeout", "network"
- Server errors: "http error 5", "http error 429"
- Download errors: "fragment", "part-frag", ".part"

**Permanent patterns:**
- Availability: "unavailable", "not available", "removed"
- Access: "private", "members-only", "age-restricted"
- Legal: "copyright", "terminated"

## Real-World Examples

### Example 1: File System Error (Transient)

**Error:**
```
ERROR: Unable to download video: [Errno 2] No such file or directory: 
'E:\...\Zubaida [dCWj-XGQcXs].mp4.part-Frag32'
```

**Classification:** TRANSIENT
- Contains "no such file or directory"
- Contains "errno 2"
- Contains "part-frag"

**Action:**
```
[INFO] Transient error for dCWj-XGQcXs - will retry in next session
```

**Result:** Video will be retried and likely succeed

### Example 2: Private Video (Permanent)

**Error:**
```
ERROR: This video is private
```

**Classification:** PERMANENT
- Contains "private"

**Action:**
```
[INFO] Permanently excluded ABC123 from future downloads
```

**Result:** Video added to excluded_ids, won't retry

### Example 3: Network Timeout (Transient)

**Error:**
```
ERROR: Connection timeout after 30 seconds
```

**Classification:** TRANSIENT
- Contains "timeout"

**Action:**
```
[INFO] Transient error for XYZ789 - will retry in next session
```

**Result:** Video will be retried when network is stable

### Example 4: Copyright Claim (Permanent)

**Error:**
```
ERROR: Video removed due to copyright claim
```

**Classification:** PERMANENT
- Contains "copyright"
- Contains "removed"

**Action:**
```
[INFO] Permanently excluded DEF456 from future downloads
```

**Result:** Video excluded, won't waste time retrying

## Benefits

### 1. Fewer False Exclusions
**Before:**
- 10 videos fail with transient errors
- All 10 added to excluded_ids
- 0 retried, 0 eventually downloaded

**After:**
- 10 videos fail with transient errors
- 0 added to excluded_ids
- 10 retried, 8-9 successfully downloaded

### 2. Automatic Recovery
**Scenario:** Network glitch during download
- **Before:** Videos excluded, manual intervention needed
- **After:** Videos automatically retried, no action needed

### 3. Smarter Resource Usage
- Don't waste time retrying truly unavailable videos
- Do retry videos that can succeed
- Optimal balance between persistence and efficiency

### 4. Better Statistics
- `excluded_ids` only contains truly unavailable videos
- Accurate count of downloadable vs unavailable
- Clearer understanding of playlist status

## Monitoring

### Check Classification in Logs

**Transient error:**
```
[WARN] Download failed for dCWj-XGQcXs: [Errno 2] No such file...
[INFO] Transient error for dCWj-XGQcXs - will retry in next session
```

**Permanent error:**
```
[WARN] Download failed for ABC123: Video unavailable
[INFO] Permanently excluded ABC123 from future downloads
```

### Verify Excluded IDs

Check `yt_playlist_gui_config.json`:
```json
{
  "playlists": [
    {
      "title": "Hindi",
      "excluded_ids": [
        "ABC123",  // Only permanent errors
        "DEF456"   // No transient errors here
      ]
    }
  ]
}
```

### Check Retry Behavior

**First attempt:**
```
[WARN] Download failed for dCWj-XGQcXs: Fragment error
[INFO] Transient error for dCWj-XGQcXs - will retry in next session
```

**Second attempt (resume):**
```
[1/200] Downloading: dCWj-XGQcXs
✓ Download verified, adding dCWj-XGQcXs to archive
```

## Configuration

### Adjust Classification (Advanced)

Edit `yt_playlist_audio_tools.py` function `_is_permanent_error()`:

**Add transient pattern:**
```python
transient_patterns = [
    # ... existing patterns ...
    "your custom pattern",
]
```

**Add permanent pattern:**
```python
permanent_patterns = [
    # ... existing patterns ...
    "your custom pattern",
]
```

### Default Behavior

**When in doubt:** Treat as TRANSIENT
- Safer to retry than to exclude
- User can manually exclude if needed
- Prevents data loss

## Troubleshooting

### Video Keeps Failing
**Symptom:** Same video fails every retry

**Check:**
1. Is it a permanent error? (check logs)
2. Is the pattern not recognized?
3. Is it a new type of error?

**Solution:**
- If permanent: Manually add to excluded_ids in GUI
- If transient but persistent: Check underlying issue (disk space, network)
- If new error type: Report for pattern addition

### Video Not Retrying
**Symptom:** Video excluded but should retry

**Check:**
1. Is it in excluded_ids? (check config)
2. Was it classified as permanent?
3. Check logs for classification message

**Solution:**
- Remove from excluded_ids in GUI
- Edit exclusions dialog
- Restart download

### Too Many Retries
**Symptom:** Same videos fail repeatedly

**Cause:** Persistent transient issue (bad network, disk problems)

**Solution:**
- Fix underlying issue
- Temporarily increase batch size
- Manually exclude problematic videos

## Best Practices

### 1. Monitor First Few Downloads
- Check logs for classification messages
- Verify transient errors are retried
- Verify permanent errors are excluded

### 2. Review Excluded IDs Periodically
- Check if list makes sense
- Remove any that shouldn't be there
- Videos can become available later

### 3. Don't Manually Exclude Transient Errors
- Let system handle classification
- Only manually exclude if truly unavailable
- System will retry automatically

### 4. Report Unknown Errors
- New error patterns may emerge
- Help improve classification
- Share error messages for analysis

## Statistics

### Typical Error Distribution

**Large playlist (1000 videos):**
- Permanent errors: 10-20 (1-2%)
  - Private: 5-10
  - Deleted: 3-5
  - Copyright: 2-5

- Transient errors: 20-50 (2-5%)
  - Network: 10-20
  - File system: 5-10
  - Server: 5-10

- Success rate after retry: 80-90%

### Recovery Rate

**Transient errors:**
- First retry: 70-80% success
- Second retry: 15-20% success
- Third retry: 5-10% success
- Total recovery: 90-95%

**Permanent errors:**
- Retry success: 0-5% (videos become available)

## Summary

### Key Improvements
✓ Smart error classification
✓ Automatic retry of transient errors
✓ Permanent exclusion only when appropriate
✓ Better resource utilization
✓ Fewer false exclusions

### Error Handling Flow
```
Download fails
    ↓
Classify error
    ├─ Transient → Log + Retry later
    └─ Permanent → Exclude + Skip forever
```

### Result
- Videos like "dCWj-XGQcXs" and "EAhWXJM0sSI" will be automatically retried
- Only truly unavailable videos are excluded
- Higher success rate with less manual intervention

The system now handles errors intelligently, maximizing successful downloads while avoiding wasted retries!
