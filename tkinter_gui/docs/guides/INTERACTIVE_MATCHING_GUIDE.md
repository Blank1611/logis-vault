# Interactive Matching Guide

## Overview

The `rename_add_video_ids.py` script now includes an interactive mode for manually matching files that couldn't be automatically matched.

## How It Works

### Step 1: Automatic Matching

The script first tries to automatically match files:
```
Found 125 .mp4 files
Found 122 IDs in archive
Found 122 title mappings

✓ Already has ID: Song One [abc123].mp4
...

WILL RENAME 120 FILES:
...
```

### Step 2: Show Unmatched Files

Files that couldn't be matched are shown with similar titles:
```
⚠️  3 files could not be matched:

   File: Rauf & Faik — детство (Official video).mp4
   Normalized: rauffaikдетство...
   Most similar titles in playlist:
     - Rauf & Faik - childhood (Official video) (similarity: 53%)
       Normalized: rauffaikchildhood...
       ID: m-el0pQLQE4
     - Rauf Faik - evenings (Official video) (similarity: 53%)
       Normalized: rauffaikevenings...
       ID: BVXtQxkCrdU
```

### Step 3: Interactive Matching

The script asks if you want to manually match:
```
================================================================================
INTERACTIVE MATCHING FOR UNMATCHED FILES
================================================================================

Do you want to manually match the 3 unmatched files? (yes/no): yes
```

### Step 4: Select Matches

For each unmatched file, you can select the correct match:
```
================================================================================
File 1/3: Rauf & Faik — детство (Official video).mp4
Normalized: rauffaikдетство...
================================================================================

Similar titles found:
  1. Rauf & Faik - childhood (Official video)
     Similarity: 53%
     ID: m-el0pQLQE4
     Normalized: rauffaikchildhood...

  2. Rauf Faik - evenings (Official video)
     Similarity: 53%
     ID: BVXtQxkCrdU
     Normalized: rauffaikevenings...

  3. Rauf & Faik - колыбельная (Lyric Video)
     Similarity: 53%
     ID: tlEAEJKIatc
     Normalized: rauffaikколыбельная...

  0. Skip this file
  q. Quit interactive matching

Select match (0-3, or 'q' to quit): 1

✓ Matched: Rauf & Faik — детство (Official video).mp4
  → Rauf & Faik — детство [m-el0pQLQE4].mp4
```

### Step 5: Review and Confirm

After interactive matching, see the summary:
```
✓ Manually matched 3 files

================================================================================
RENAME SUMMARY
================================================================================
Total files to rename: 123
  - Automatically matched: 120
  - Manually matched: 3
================================================================================

Proceed with renaming 123 files? (yes/no): yes

✅ Successfully renamed 123 files
```

## Interactive Options

### Option 1-N: Select a Match
```
Select match (0-3, or 'q' to quit): 1
```
Renames the file using the selected title's video ID.

### Option 0: Skip File
```
Select match (0-3, or 'q' to quit): 0
```
Skips this file and moves to the next one.

### Option 'q': Quit
```
Select match (0-3, or 'q' to quit): q
```
Exits interactive matching immediately. Any files already matched will still be included in the final rename operation.

## Use Cases

### Case 1: Language Mismatch
```
Filename: "Song Title (Russian).mp4"
Playlist: "Song Title (English)"

Solution: Manually select the English version
```

### Case 2: Multiple Versions
```
Filename: "Song - Extended Mix.mp4"
Playlist options:
  1. Song (Original)
  2. Song (Extended Mix)
  3. Song (Radio Edit)

Solution: Select option 2
```

### Case 3: Uncertain Match
```
Filename: "Unknown Song.mp4"
Similar titles all have low similarity (30-40%)

Solution: Select option 0 to skip, investigate manually later
```

### Case 4: Artist Name Variations
```
Filename: "R&F - Song.mp4"
Playlist: "Rauf & Faik - Song"

Solution: Manually select the full artist name version
```

## Tips

### 1. Check Similarity Scores
- **>70%**: Probably correct match
- **50-70%**: Review carefully
- **<50%**: Double-check before selecting

### 2. Compare Normalized Versions
Look at the normalized strings to understand why they didn't auto-match:
```
Normalized filename: rauffaikдетство
Normalized title:    rauffaikchildhood
```
Different words = language mismatch

### 3. Use Video IDs to Verify
If unsure, copy the video ID and check on YouTube:
```
https://www.youtube.com/watch?v=m-el0pQLQE4
```

### 4. Skip When Uncertain
If you're not sure, skip (option 0) and handle it manually later. Better safe than wrong!

### 5. Quit Anytime
Press 'q' to exit interactive matching if you need to:
- Check something
- Take a break
- Review the playlist online

## Example Session

```bash
$ python rename_add_video_ids.py

Found 125 .mp4 files
Found 122 IDs in archive
Found 122 title mappings

# ... automatic matching ...

⚠️  3 files could not be matched:
   - File 1 (Russian title)
   - File 2 (Russian title)
   - File 3 (Japanese title)

Do you want to manually match the 3 unmatched files? (yes/no): yes

# File 1: Russian → English
Select match (0-3, or 'q' to quit): 1
✓ Matched!

# File 2: Russian → English
Select match (0-3, or 'q' to quit): 2
✓ Matched!

# File 3: Japanese → Not sure
Select match (0-3, or 'q' to quit): 0
Skipped

✓ Manually matched 2 files

RENAME SUMMARY
Total files to rename: 122
  - Automatically matched: 120
  - Manually matched: 2

Proceed with renaming 122 files? (yes/no): yes

✅ Successfully renamed 122 files
```

## Advantages

✅ **No Manual Commands**: No need to type `mv` or `ren` commands

✅ **Visual Confirmation**: See the new filename before confirming

✅ **Flexible**: Skip uncertain matches, quit anytime

✅ **Safe**: Review all changes before final confirmation

✅ **Efficient**: Handle multiple files in one session

✅ **Informative**: See similarity scores and normalized versions

## Troubleshooting

### Problem: No Similar Titles Shown

**Cause**: File is very different from all playlist titles

**Solution**: 
1. Check if file is in the right playlist folder
2. Verify playlist_info.json has the correct titles
3. May need to manually check archive.txt for the video ID

### Problem: All Similarity Scores Low (<40%)

**Cause**: Filename format very different from playlist titles

**Solution**:
1. Skip in interactive mode
2. Search for the video on YouTube manually
3. Use the video ID from YouTube URL to rename

### Problem: Multiple Files Match Same Title

**Cause**: Duplicate or very similar titles in playlist

**Solution**:
1. Check the video IDs on YouTube to verify which is which
2. Look at upload dates or other metadata
3. Skip if uncertain

## See Also

- [Rename Script Guide](RENAME_SCRIPT_GUIDE.md) - Main documentation
- [Rename Script Troubleshooting](RENAME_SCRIPT_TROUBLESHOOTING.md) - Debugging help
- [Old Format Auto-Rename](OLD_FORMAT_AUTO_RENAME.md) - Automatic renaming in main app
