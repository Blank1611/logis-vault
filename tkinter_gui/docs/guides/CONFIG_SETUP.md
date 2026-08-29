# Configuration Setup Guide

## Overview

This project uses configuration files that contain personal paths and settings. These files are **not tracked by Git** to protect your privacy.

## Quick Setup

### 1. Copy Template Files

Copy the template files and remove the `.template` extension:

**Windows (PowerShell)**:
```powershell
Copy-Item config.json.template config.json
```

**Windows (CMD)**:
```cmd
copy config.json.template config.json
```

**Linux/Mac**:
```bash
cp config.json.template config.json
```

### 2. Edit Your Config

Open `config.json` and update with your paths:

```json
{
  "base_download_path": "E:\\your\\actual\\path\\youtube",
  "cookies_file": "E:\\your\\actual\\path\\yt-cookies.txt",
  "use_browser_cookies": false,
  "browser_name": "chrome",
  "audio_extract_mode": "copy",
  "max_extraction_workers": 4,
  "max_log_lines": 5000,
  "max_log_size_mb": 10,
  "batch_size": 200
}
```

### 3. Verify .gitignore

The following files are automatically ignored by Git:
- `config.json` - Main configuration
- `yt_playlist_gui_config.json` - GUI playlist data
- `logs/` - Log files
- `ytdld/` - Virtual environment

## Configuration Files

### config.json (Required)

Main configuration file for the application.

**Location**: Project root directory

**Contains**:
- Download paths
- Cookie settings
- Audio extraction settings
- Performance settings

**Git Status**: ❌ Not tracked (in .gitignore)

### yt_playlist_gui_config.json (Auto-generated)

GUI application data including playlists and exclusions.

**Location**: Project root directory

**Contains**:
- Playlist URLs and titles
- Download/extraction timestamps
- Excluded video IDs
- Statistics

**Git Status**: ❌ Not tracked (in .gitignore)

**Note**: This file is created automatically when you add playlists in the GUI.

## Configuration Options

### base_download_path

**Type**: String (path)

**Description**: Root directory where all playlists will be downloaded

**Example**:
```json
"base_download_path": "E:\\Music\\YouTube"
```

**Result**:
```
E:\Music\YouTube\
├── Playlist 1\
├── Playlist 2\
└── Playlist 3\
```

### cookies_file

**Type**: String (path) or null

**Description**: Path to YouTube cookies file for authentication

**When to use**:
- Age-restricted videos
- Private playlists
- Member-only content

**Example**:
```json
"cookies_file": "E:\\Music\\YouTube\\yt-cookies.txt"
```

**How to get cookies**: Use browser extension like "Get cookies.txt"

### use_browser_cookies

**Type**: Boolean

**Description**: Load cookies directly from browser instead of file

**Options**:
- `true`: Load from browser (requires browser_cookie3)
- `false`: Use cookies_file instead

**Example**:
```json
"use_browser_cookies": false
```

### browser_name

**Type**: String

**Description**: Which browser to load cookies from (if use_browser_cookies is true)

**Options**: `"chrome"`, `"firefox"`, `"edge"`, `"safari"`

**Example**:
```json
"browser_name": "chrome"
```

### audio_extract_mode

**Type**: String

**Description**: How to extract audio from videos

**Options**:
- `"copy"`: Copy audio stream (fastest, best quality, may fail on some files)
- `"mp3_best"`: MP3 VBR quality 0 (~245kbps, always works)
- `"mp3_high"`: MP3 VBR quality 2 (~190kbps, smaller files)
- `"opus"`: Opus codec (excellent quality at lower bitrates)

**Example**:
```json
"audio_extract_mode": "copy"
```

**Recommendation**: Use `"copy"` with automatic fallback

### max_extraction_workers

**Type**: Number

**Description**: Number of concurrent FFmpeg processes for audio extraction

**Recommendation**:
- 4-core CPU: 4 workers
- 8-core CPU: 6-8 workers
- 16-core CPU: 10-12 workers

**Example**:
```json
"max_extraction_workers": 4
```

### max_log_lines

**Type**: Number

**Description**: Maximum lines before log rotation

**Default**: 5000

**Example**:
```json
"max_log_lines": 5000
```

### max_log_size_mb

**Type**: Number

**Description**: Maximum log file size (MB) before rotation

**Default**: 10

**Example**:
```json
"max_log_size_mb": 10
```

### batch_size

**Type**: Number

**Description**: Maximum videos to download per session (to avoid bot detection)

**Default**: 200

**Example**:
```json
"batch_size": 200
```

## Security Best Practices

### 1. Never Commit Personal Configs

✅ **Do**:
- Keep `config.json` in `.gitignore`
- Use template files for sharing
- Document configuration options

❌ **Don't**:
- Commit `config.json` with real paths
- Share cookies files
- Push personal data to Git

### 2. Protect Sensitive Data

**Sensitive files**:
- `config.json` - Contains your paths
- `yt_playlist_gui_config.json` - Contains playlist data
- `yt-cookies.txt` - Contains authentication cookies
- `logs/` - May contain personal information

**All are in .gitignore** ✓

### 3. Share Safely

When sharing your project:
1. Commit only template files
2. Update README with setup instructions
3. Let users create their own configs

## Troubleshooting

### Problem: Config File Not Found

**Error**: `Config file not found: config.json`

**Solution**:
```bash
# Copy template
copy config.json.template config.json

# Edit with your paths
notepad config.json
```

### Problem: Invalid JSON

**Error**: `JSONDecodeError: Expecting property name`

**Cause**: Syntax error in JSON file

**Solution**:
- Check for missing commas
- Check for trailing commas (not allowed in JSON)
- Verify quotes are correct
- Use JSON validator online

### Problem: Path Not Found

**Error**: `FileNotFoundError: [Errno 2] No such file or directory`

**Solution**:
- Use double backslashes in Windows paths: `"E:\\path\\to\\folder"`
- Or use forward slashes: `"E:/path/to/folder"`
- Verify path exists

### Problem: Accidentally Committed Config

**Solution**:
```bash
# Remove from Git but keep local file
git rm --cached config.json

# Verify .gitignore includes it
echo config.json >> .gitignore

# Commit the removal
git commit -m "Remove config.json from tracking"
```

## Example Configurations

### Minimal Setup
```json
{
  "base_download_path": "C:\\Music\\YouTube",
  "cookies_file": null,
  "use_browser_cookies": false,
  "browser_name": "chrome",
  "audio_extract_mode": "mp3_best",
  "max_extraction_workers": 4,
  "batch_size": 200
}
```

### Advanced Setup
```json
{
  "base_download_path": "E:\\Media\\YouTube\\Downloads",
  "cookies_file": "E:\\Media\\YouTube\\cookies.txt",
  "use_browser_cookies": false,
  "browser_name": "chrome",
  "audio_extract_mode": "copy",
  "max_extraction_workers": 8,
  "max_log_lines": 10000,
  "max_log_size_mb": 20,
  "batch_size": 300
}
```

### Browser Cookies Setup
```json
{
  "base_download_path": "C:\\Downloads\\YouTube",
  "cookies_file": null,
  "use_browser_cookies": true,
  "browser_name": "firefox",
  "audio_extract_mode": "opus",
  "max_extraction_workers": 6,
  "batch_size": 200
}
```

## See Also

- [README.md](README.md) - Main documentation
- [AUDIO_VIDEO_QUALITY_GUIDE.md](AUDIO_VIDEO_QUALITY_GUIDE.md) - Audio settings
- [FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md) - File organization
