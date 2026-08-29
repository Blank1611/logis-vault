# Audio & Video Quality Settings Guide

## Current Configuration

### Video Quality
- **Format**: `bestvideo+bestaudio/best` ✓ **OPTIMAL**
- **Container**: MP4 (universal compatibility)
- **Quality**: Downloads highest quality available from YouTube
- **No upscaling**: Downloads original quality as-is

### Audio Extraction Modes

You can now choose how audio is extracted from videos by setting `audio_extract_mode` in `config.json`:

#### 1. **"copy"** - Original Quality (RECOMMENDED)
```json
"audio_extract_mode": "copy"
```
- **Pros**: 
  - Zero quality loss (no re-encoding)
  - Preserves YouTube's original audio codec (usually AAC or OPUS)
  - Fastest extraction
- **Cons**: 
  - File format varies (.m4a, .opus, .aac)
  - Slightly less compatible with older devices
- **File size**: Same as original
- **Use when**: You want absolute best quality

#### 2. **"mp3_best"** - Highest Quality MP3
```json
"audio_extract_mode": "mp3_best"
```
- **Pros**: 
  - Excellent quality (VBR ~245kbps)
  - Universal compatibility (.mp3)
- **Cons**: 
  - Slight quality loss from re-encoding
- **File size**: ~3-4 MB per minute
- **Use when**: You need MP3 format with best quality

#### 3. **"mp3_high"** - High Quality MP3 (Default)
```json
"audio_extract_mode": "mp3_high"
```
- **Pros**: 
  - Good quality (VBR ~190kbps)
  - Smaller files than mp3_best
  - Universal compatibility
- **Cons**: 
  - Noticeable quality loss vs original
- **File size**: ~2-3 MB per minute
- **Use when**: You want balance between quality and file size

#### 4. **"opus"** - OPUS Codec
```json
"audio_extract_mode": "opus"
```
- **Pros**: 
  - Excellent quality at low bitrates
  - 128kbps OPUS ≈ 192kbps MP3 quality
  - YouTube's native format
- **Cons**: 
  - Less compatible with older devices
- **File size**: ~1-2 MB per minute
- **Use when**: You want best quality-to-size ratio

## Quality Comparison

| Mode | Quality | File Size | Compatibility | Re-encoding |
|------|---------|-----------|---------------|-------------|
| **copy** | ⭐⭐⭐⭐⭐ | Medium | Good | No ✓ |
| **mp3_best** | ⭐⭐⭐⭐ | Large | Excellent | Yes |
| **mp3_high** | ⭐⭐⭐ | Medium | Excellent | Yes |
| **opus** | ⭐⭐⭐⭐⭐ | Small | Good | Yes |

## Recommendations

### For Archival/Best Quality:
```json
"audio_extract_mode": "copy"
```
This preserves the exact audio YouTube provides with zero quality loss.

### For Universal Compatibility:
```json
"audio_extract_mode": "mp3_best"
```
Works everywhere, excellent quality.

### For Space Efficiency:
```json
"audio_extract_mode": "opus"
```
Best quality per MB, modern format.

## Video Format Notes

Your current video settings are already optimal:
- `bestvideo+bestaudio/best` downloads the highest quality available
- MP4 container provides universal compatibility
- No upscaling or quality modification occurs
- You get exactly what YouTube provides

## Parallel Audio Extraction

Audio extraction now runs in parallel using multiple CPU cores for significantly faster processing!

### Configuration:
```json
"max_extraction_workers": 4
```

- **Default**: 4 workers (processes 4 files simultaneously)
- **Recommended**: Set to your CPU core count (e.g., 8 for 8-core CPU)
- **Performance**: ~3-4x faster than sequential extraction

### Example Performance:
- **Sequential** (old): 100 files in ~500 seconds (5 sec/file)
- **Parallel (4 workers)**: 100 files in ~125 seconds (1.25 sec/file)

## How to Change

1. Edit `config.json`
2. Add or modify the settings
3. Restart the application
4. New extractions will use the new settings

Example `config.json`:
```json
{
  "base_download_path": "E:\\2tbhdd\\songs\\syst\\New folder\\youtube",
  "cookies_file": "E:\\2tbhdd\\songs\\syst\\New folder\\youtube\\yt-cookies.txt",
  "use_browser_cookies": false,
  "browser_name": "chrome",
  "audio_extract_mode": "copy",
  "max_extraction_workers": 4
}
```

### Extraction Output Example:
```
Found 595 video files to process

[1/595] Extracting (copy): Video1.mp4
[2/595] Extracting (copy): Video2.mp4
[3/595] Extracting (copy): Video3.mp4
[4/595] Extracting (copy): Video4.mp4
...

============================================================
Audio extraction summary:
  Total processed: 595/595
  Newly extracted: 590
  Skipped (already exist): 5
  Failed: 0
  Time taken: 148.3 seconds
  Average: 0.3 sec/file
============================================================
```
