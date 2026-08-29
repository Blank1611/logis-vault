# Rename Script Guide - Enhanced Version

## Overview

The `rename_add_video_ids.py` script helps migrate old-format video files (title only) to new format (title + video ID) using aggressive alphanumeric-only matching.

## What It Does

Renames video files from:
```
Song Title.mp4  →  Song Title [dCWj-XGQcXs].mp4
```

## Key Features

### 1. Aggressive Normalization

**Removes ALL non-alphanumeric characters** for matching:
- Spaces, tabs, newlines
- Punctuation: `. , ; : ! ? ' "`
- Special characters: `- _ / \ | ( ) [ ] { }`
- Unicode characters normalized
- Everything except letters and numbers

**Example:**
```
Original:    "Song: The Best (2024) - Artist Name!"
Normalized:  "songthebest2024artistname"
```

### 2. Smart Matching Strategies

The script uses multiple matching strategies with scores:

#### Exact Match (Score: 100)
```
Filename: "SongTitle.mp4"
Title:    "Song Title"
Both normalize to: "songtitle"
Result: ✓ Perfect match
```

#### Contains Match (Score: 95)
```
Filename: "SongTitleRemix.mp4" → "songtitleremix"
Title:    "Song Title"         → "songtitle"
"songtitle" in "songtitleremix"
Result: ✓ Title contained in filename
```

#### Prefix Match (Score: 90)
```
Filename: "VeryLongSongTitleThatGotTruncated.mp4"
Title:    "Very Long Song Title That Got Truncated By System"
First 20 chars match: "verylongsongtitlethat"
Result: ✓ Prefix match (good for truncated names)
```

#### Partial Overlap (Score: 80)
```
Filename: "SongTitleVersionOne.mp4"
Title:    "Song Title (Version Two)"
Significant overlap in first 50 chars
Result: ✓ Partial match
```

#### Fuzzy Match (Score: 70)
```
Filename: "ShortSong.mp4"
Title:    "Short Song Name"
Common prefix matches
Result: ✓ Fuzzy match (minimum threshold)
```

### 3. Detailed Output

Shows normalized versions for debugging:
```
1. OLD: Song Title.mp4
   NEW: Song Title [dCWj-XGQcXs].mp4
   Title: Song Title
   Match score: 100
   Normalized filename: songtitle...
   Normalized title:    songtitle...
```

## Usage

### 1. Configure the Script

Edit these lines in the script:
```python
base_path = "E:\\2tbhdd\\songs\\syst\\New folder\\youtube"
playlist_title = "Hindi Old hits"
```

### 2. Run the Script

```bash
python rename_add_video_ids.py
```

### 3. Review Matches

The script will show:
- Files that already have IDs (skipped)
- Files that will be renamed (with match scores)
- Files that couldn't be matched

### 4. Confirm Rename

```
Rename 122 files? (yes/no): yes
```

Type `yes` to proceed, anything else to cancel.

## Requirements

The script needs:
1. **archive.txt** - Contains video IDs that were downloaded
2. **playlist_info.json** - Contains ID → Title mappings
   - Looks in `playlist_info_snapshot/` folder first
   - Falls back to root folder if not found

## Example Output

```
Scanning folder: E:\youtube\Hindi Old hits

Found 125 .mp4 files
Found 122 IDs in archive
Found 122 title mappings

✓ Already has ID: Song One [abc123].mp4
✓ Already has ID: Song Two [def456].mp4

================================================================================
WILL RENAME 120 FILES:
================================================================================

1. OLD: Zubaida.mp4
   NEW: Zubaida [dCWj-XGQcXs].mp4
   Title: Zubaida
   Match score: 100
   Normalized filename: zubaida...
   Normalized title:    zubaida...

2. OLD: Tum Hi Ho.mp4
   NEW: Tum Hi Ho [IXaEamvT2Bo].mp4
   Title: Tum Hi Ho
   Match score: 100
   Normalized filename: tumhiho...
   Normalized title:    tumhiho...

... and 118 more

⚠️  3 files could not be matched:
   - Unknown File.mp4
     Normalized: unknownfile...

================================================================================
Rename 120 files? (yes/no): yes

✅ Successfully renamed 120 files
```

## Matching Examples

### Example 1: Special Characters Removed
```
Filename: "Song: The Best (2024).mp4"
Title:    "Song: The Best (2024)"

Normalized filename: "songthebest2024"
Normalized title:    "songthebest2024"
Match: ✓ Exact (100)
```

### Example 2: Spaces and Punctuation
```
Filename: "Song - Title, Part 1.mp4"
Title:    "Song Title Part 1"

Normalized filename: "songtitlepart1"
Normalized title:    "songtitlepart1"
Match: ✓ Exact (100)
```

### Example 3: Unicode Characters
```
Filename: "गाना नाम.mp4"
Title:    "गाना नाम"

Normalized filename: "गानानाम"
Normalized title:    "गानानाम"
Match: ✓ Exact (100)
```

### Example 4: Truncated Names
```
Filename: "Very Long Song Title That Got Trunca.mp4"
Title:    "Very Long Song Title That Got Truncated"

Normalized filename: "verylongsongtitlethatgottrunc"
Normalized title:    "verylongsongtitlethatgottruncated"
Match: ✓ Prefix (90)
```

### Example 5: Extra Words
```
Filename: "Song Title Official Video.mp4"
Title:    "Song Title"

Normalized filename: "songtitleofficialvideo"
Normalized title:    "songtitle"
Match: ✓ Contains (95) - title in filename
```

## Advantages of Alphanumeric-Only Matching

### Before (With Special Characters)
```
Filename: "Song: Title (2024)"  → "song: title (2024)"
Title:    "Song - Title 2024"   → "song - title 2024"
Match: ✗ Different (colon vs dash, parentheses vs space)
```

### After (Alphanumeric Only)
```
Filename: "Song: Title (2024)"  → "songtitle2024"
Title:    "Song - Title 2024"   → "songtitle2024"
Match: ✓ Exact (100)
```

## Troubleshooting

### No Matches Found

**Problem**: Script finds 0 matches

**Solutions**:
1. Check if `archive.txt` exists and has video IDs
2. Check if `playlist_info.json` exists (in `playlist_info_snapshot/` or root)
3. Verify playlist_title matches folder name exactly
4. Check if files already have video IDs (script skips them)

### Low Match Scores

**Problem**: Files matched with score < 70

**Cause**: Filenames very different from titles

**Solution**: Lower the threshold in the script:
```python
if matched_id and best_score >= 60:  # Changed from 70
```

### Files Already Have IDs

**Problem**: Script says "Already has ID" for all files

**Cause**: Files already in new format

**Solution**: No action needed - files already renamed!

### Permission Errors

**Problem**: `❌ Error renaming: [Errno 13] Permission denied`

**Solutions**:
1. Close any programs using the files (media players, etc.)
2. Run script as administrator
3. Check file permissions

## Safety Features

✅ **Preview Before Rename**: Shows all changes before applying

✅ **Confirmation Required**: Must type "yes" to proceed

✅ **Skip Already Renamed**: Won't rename files that already have IDs

✅ **Error Handling**: Catches and reports rename failures

✅ **Non-Destructive**: Only renames, never deletes

✅ **Detailed Logging**: Shows match scores and normalized versions

## Advanced Usage

### Batch Process Multiple Playlists

Create a wrapper script:
```python
playlists = ["Hindi", "Awesome", "Turk"]

for playlist in playlists:
    print(f"\n{'='*80}")
    print(f"Processing: {playlist}")
    print(f"{'='*80}\n")
    
    # Update playlist_title and run main()
    # ... (modify script to accept parameters)
```

### Adjust Match Threshold

For stricter matching:
```python
if matched_id and best_score >= 90:  # Only high-confidence matches
```

For looser matching:
```python
if matched_id and best_score >= 60:  # Accept more matches
```

### Export Match Report

Add before confirmation:
```python
import csv

with open('rename_report.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['old_name', 'new_name', 'score'])
    writer.writeheader()
    writer.writerows(rename_operations)
```

## Integration with Main App

The main app (`yt_playlist_audio_tools.py`) now includes similar logic:
- Automatically detects old format during downloads
- Renames on-the-fly without user intervention
- Uses same aggressive normalization

**When to use this script:**
- Bulk rename existing files before first run
- Migrate large libraries to new format
- Debug matching issues with detailed output

**When to use auto-rename:**
- Normal operation (automatic)
- New downloads (automatic)
- Small updates (automatic)

## See Also

- [Old Format Auto-Rename](OLD_FORMAT_AUTO_RENAME.md) - Automatic renaming in main app
- [Custom Archive Logic](CUSTOM_ARCHIVE_IMPROVEMENTS.md) - Archive system
- [Folder Structure](FOLDER_STRUCTURE.md) - File organization
