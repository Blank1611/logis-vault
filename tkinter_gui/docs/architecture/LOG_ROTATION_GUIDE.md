# Log Rotation Guide

## Overview
Automatic log rotation prevents log files from growing too large by archiving old logs and starting fresh files.

## Log Directory Structure

### All Logs (In Base Path)
```
<base_download_path>/
└── logs/
    ├── app_startup.log                    # Current startup log
    ├── app_startup_20241201_01.log       # Rotated startup logs
    ├── app_startup_20241130_01.log
    │
    ├── Awesome/
    │   ├── Awesome.log                    # Current playlist log
    │   ├── Awesome_20241201_01.log       # Rotated playlist logs
    │   └── Awesome_20241130_01.log
    │
    ├── Hindi_Old_hits/
    │   ├── Hindi_Old_hits.log
    │   └── Hindi_Old_hits_20241201_01.log
    │
    └── Just_music/
        ├── Just_music.log
        └── Just_music_20241201_01.log
```

### Why This Structure?
- **All logs in one place**: Everything in `<base_path>/logs/`
- **App startup logs**: At root of logs directory
- **Playlist logs**: Each in its own subdirectory
- **Portability**: All logs move with the data if you change base path
- **Organization**: Easy to find and manage all logs

## How It Works

### Rotation Triggers
Logs are automatically rotated when they exceed either:
- **Line count**: Default 5,000 lines
- **File size**: Default 10 MB

### When Rotation Happens
- **Startup log** (`app_startup.log`): Checked before each write
- **Playlist logs** (`logs/Playlist_Name.log`): Checked when starting a new operation

### Rotation Naming Format
```
original_name_YYYYMMDD_RR.log
```

Where:
- `YYYYMMDD` = Date from the log file's modification time
- `RR` = Revision number (01, 02, 03, etc.) for same-day rotations

## Examples

### Single Rotation Per Day
```
<base_path>/logs/Awesome/
├── Awesome.log                    # Current log
└── Awesome_20241201_01.log       # Rotated on Dec 1, 2024
```

### Multiple Rotations Same Day
```
<base_path>/logs/Awesome/
├── Awesome.log                    # Current log
├── Awesome_20241201_01.log       # First rotation today
├── Awesome_20241201_02.log       # Second rotation today
└── Awesome_20241130_01.log       # Rotation from yesterday
```

### Startup Log Rotation
```
<project_dir>/logs/
├── app_startup.log                # Current startup log
├── app_startup_20241201_01.log   # Rotated today
└── app_startup_20241130_01.log   # Rotated yesterday
```

## Configuration

### Default Settings
```json
{
  "max_log_lines": 5000,
  "max_log_size_mb": 10
}
```

### Customizing Rotation Thresholds

Edit `config.json` to adjust when logs rotate:

```json
{
  "base_download_path": "E:\\2tbhdd\\songs\\syst\\New folder\\youtube",
  "cookies_file": "E:\\2tbhdd\\songs\\syst\\New folder\\youtube\\yt-cookies.txt",
  "use_browser_cookies": false,
  "browser_name": "chrome",
  "audio_extract_mode": "copy",
  "max_extraction_workers": 4,
  "max_log_lines": 10000,
  "max_log_size_mb": 20
}
```

### Recommended Settings

#### For Frequent Operations (Many Downloads)
```json
"max_log_lines": 3000,
"max_log_size_mb": 5
```
- Keeps logs smaller and more manageable
- More frequent rotations

#### For Infrequent Operations
```json
"max_log_lines": 10000,
"max_log_size_mb": 20
```
- Fewer rotations
- Longer history in single file

#### For Debugging (Keep Everything)
```json
"max_log_lines": 50000,
"max_log_size_mb": 100
```
- Very large logs before rotation
- Good for troubleshooting

## Benefits

### 1. Prevents Disk Space Issues
- Logs don't grow indefinitely
- Old logs are archived with clear naming

### 2. Better Performance
- Smaller log files open faster
- Easier to search and analyze

### 3. Historical Tracking
- Archived logs preserve history
- Date-based naming makes finding old logs easy

### 4. Automatic Management
- No manual intervention needed
- Rotation happens transparently

## Log Management

### Finding Recent Logs
Current operations always write to the base log file:
```
<project_dir>/logs/app_startup.log
<base_path>/logs/Awesome/Awesome.log
<base_path>/logs/Hindi_Old_hits/Hindi_Old_hits.log
```

### Finding Historical Logs
Archived logs are named with dates:
```powershell
# List all Awesome playlist logs
Get-ChildItem "<base_path>\logs\Awesome\*.log" | Sort-Object LastWriteTime

# Find logs from specific date across all playlists
Get-ChildItem "<base_path>\logs\*\*20241201*.log"

# List all startup logs
Get-ChildItem "logs\app_startup*.log"
```

### Cleaning Old Logs
Delete archived logs older than 30 days:
```powershell
# Windows PowerShell - Clean playlist logs
Get-ChildItem "<base_path>\logs\*\*_????????_??.log" | 
  Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | 
  Remove-Item

# Clean startup logs
Get-ChildItem "logs\app_startup_????????_??.log" | 
  Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-30) } | 
  Remove-Item
```

### Analyzing Rotated Logs
Combine multiple log files for analysis:
```powershell
# Combine all Awesome logs
Get-Content "<base_path>\logs\Awesome\*.log" | Out-File combined_awesome.log

# Search across all logs for a playlist
Get-ChildItem "<base_path>\logs\Awesome\*.log" | Select-String "error"

# Search across ALL playlists
Get-ChildItem "<base_path>\logs\*\*.log" | Select-String "error"
```

## Rotation Behavior

### What Triggers Rotation
1. **Before writing**: Log is checked before each write operation
2. **Size check**: File size in MB
3. **Line check**: Total line count
4. **Either condition**: Rotation happens if EITHER limit is exceeded

### What Happens During Rotation
1. Current log file is renamed with date and revision
2. New empty log file is created with original name
3. New operations write to the fresh log file
4. Console shows rotation message: `Rotated log: Awesome.log -> Awesome_20241201_01.log`

### Revision Numbers
- Start at `01` for each date
- Increment if multiple rotations happen same day
- Format: `_01`, `_02`, `_03`, etc.

## Troubleshooting

### Logs Not Rotating
**Check**: Are limits set too high?
```json
"max_log_lines": 1000000,  // Too high!
"max_log_size_mb": 1000    // Too high!
```

**Solution**: Lower the thresholds in `config.json`

### Too Many Rotations
**Check**: Are limits set too low?
```json
"max_log_lines": 100,  // Too low!
"max_log_size_mb": 1   // Too low!
```

**Solution**: Increase the thresholds

### Can't Find Old Logs
**Check**: Look for archived logs with date suffix:
```powershell
Get-ChildItem logs\*_????????_??.log
```

### Rotation Failed
If rotation fails (permissions, disk full, etc.):
- Warning message is printed to console
- Original log continues to grow
- Fix the underlying issue and restart app

## Best Practices

1. **Regular Cleanup**: Delete very old archived logs periodically
2. **Monitor Disk Space**: Ensure enough space for log rotation
3. **Adjust Thresholds**: Tune based on your usage patterns
4. **Backup Important Logs**: Archive critical logs before cleanup
5. **Check Rotation**: Verify rotation is working as expected

## Example Workflow

### Daily Operations
```
Day 1:
  <base_path>/logs/Awesome/Awesome.log (grows to 5000 lines)
  -> Rotates to Awesome_20241201_01.log
  -> New Awesome.log created

Day 2:
  <base_path>/logs/Awesome/Awesome.log (grows to 5000 lines)
  -> Rotates to Awesome_20241202_01.log
  -> New Awesome.log created

Day 3 (Heavy usage):
  <base_path>/logs/Awesome/Awesome.log (5000 lines)
  -> Rotates to Awesome_20241203_01.log
  <base_path>/logs/Awesome/Awesome.log (5000 lines again)
  -> Rotates to Awesome_20241203_02.log
  -> New Awesome.log created
```

### Result After 3 Days
```
<base_path>/logs/Awesome/
├── Awesome.log                    # Current
├── Awesome_20241203_02.log       # Day 3, 2nd rotation
├── Awesome_20241203_01.log       # Day 3, 1st rotation
├── Awesome_20241202_01.log       # Day 2
└── Awesome_20241201_01.log       # Day 1
```
