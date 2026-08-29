# Exclusions Editor Guide

## Overview

The improved Exclusions Editor provides a user-friendly interface for managing excluded videos in your playlists.

## Features

### Visual List with Titles
- Shows video titles alongside IDs
- Easy to identify which videos are excluded
- Scrollable list for large exclusion lists

### Multiple Selection
- Select multiple videos at once
- Remove multiple exclusions in one action
- Copy multiple IDs to clipboard

### Quick Actions
- **Remove Selected**: Unexclude selected videos
- **Add Video ID**: Manually add a video ID to exclude
- **Clear All**: Remove all exclusions at once
- **Copy Selected IDs**: Copy video IDs to clipboard
- **Open in YouTube**: Open selected video in browser

## How to Use

### Opening the Editor

1. Select a playlist in the main window
2. Click "Edit exclusions for selected" button
3. The Exclusions Editor window opens

### Removing Exclusions

**To unexclude videos (make them downloadable again):**

1. Select one or more videos in the list
2. Click "Remove Selected"
3. Videos are removed from exclusion list
4. Click "Save" to apply changes

**Example:**
```
Before: 21 excluded videos
Select 3 videos → Click "Remove Selected"
After: 18 excluded videos
```

### Adding Exclusions

**To manually exclude a video:**

1. Click "Add Video ID"
2. Enter the 11-character video ID
3. Video is added to exclusion list
4. Click "Save" to apply changes

**Where to get video ID:**
```
YouTube URL: https://www.youtube.com/watch?v=dQw4w9WgXcQ
Video ID:    dQw4w9WgXcQ (11 characters)
```

### Clearing All Exclusions

**To remove all exclusions:**

1. Click "Clear All"
2. Confirm the action
3. All videos become downloadable again
4. Click "Save" to apply changes

### Copying Video IDs

**To copy IDs for reference:**

1. Select one or more videos
2. Click "Copy Selected IDs"
3. IDs are copied to clipboard (one per line)
4. Paste into text editor or other tool

**Example output:**
```
dQw4w9WgXcQ
m-el0pQLQE4
BVXtQxkCrdU
```

### Opening in YouTube

**To verify a video:**

1. Select a single video
2. Click "Open in YouTube"
3. Video opens in your default browser
4. Verify if it's actually unavailable or just a mistake

## Interface Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Edit Exclusions - Playlist Name                             │
├─────────────────────────────────────────────────────────────┤
│ Manage excluded videos for: Playlist Name                   │
│ Excluded videos will not be downloaded...                   │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────┐  ┌──────────────┐  │
│ │ Song Title 1 [abc123xyz]            │  │ Remove       │  │
│ │ Song Title 2 [def456uvw]            │  │ Selected     │  │
│ │ Song Title 3 [ghi789rst]            │  ├──────────────┤  │
│ │ Unknown Title [jkl012mno]           │  │ Add Video ID │  │
│ │ ...                                 │  ├──────────────┤  │
│ │                                     │  │ Clear All    │  │
│ │                                     │  ├──────────────┤  │
│ │                                     │  │ Quick Actions│  │
│ │                                     │  ├──────────────┤  │
│ │                                     │  │ Copy IDs     │  │
│ │                                     │  ├──────────────┤  │
│ │                                     │  │ Open YouTube │  │
│ └─────────────────────────────────────┘  └──────────────┘  │
├─────────────────────────────────────────────────────────────┤
│ Excluded videos: 21                      [Cancel] [Save]    │
└─────────────────────────────────────────────────────────────┘
```

## Use Cases

### Case 1: Accidentally Excluded Video

**Problem**: Video was marked as unavailable due to transient error

**Solution**:
1. Open Exclusions Editor
2. Find the video in the list
3. Select it and click "Remove Selected"
4. Click "Save"
5. Video will be downloaded in next session

### Case 2: Verify Exclusions

**Problem**: Not sure why certain videos are excluded

**Solution**:
1. Open Exclusions Editor
2. Select a video
3. Click "Open in YouTube"
4. Check if video is actually unavailable
5. Remove from exclusions if it's available

### Case 3: Bulk Cleanup

**Problem**: Many old exclusions that might be available now

**Solution**:
1. Open Exclusions Editor
2. Click "Clear All"
3. Confirm
4. Click "Save"
5. Run download - system will re-check all videos

### Case 4: Manual Exclusion

**Problem**: Want to skip a specific video permanently

**Solution**:
1. Get video ID from YouTube URL
2. Open Exclusions Editor
3. Click "Add Video ID"
4. Enter the ID
5. Click "Save"

### Case 5: Export Exclusions

**Problem**: Need list of excluded videos for reference

**Solution**:
1. Open Exclusions Editor
2. Select all videos (Ctrl+A)
3. Click "Copy Selected IDs"
4. Paste into text file
5. Save for reference

## Keyboard Shortcuts

- **Ctrl+A**: Select all videos
- **Delete**: Remove selected (if implemented)
- **Ctrl+C**: Copy (use "Copy Selected IDs" button instead)
- **Escape**: Cancel and close

## Tips

### 1. Review Before Clearing

Before clicking "Clear All", consider:
- How many videos are excluded?
- Were they excluded for good reasons?
- Do you want to re-download them all?

### 2. Check Unknown Titles

Videos showing "Unknown Title" might be:
- Deleted from YouTube
- Private videos
- Videos not in playlist_info.json

Use "Open in YouTube" to verify.

### 3. Backup Exclusions

Before major changes:
1. Select all videos
2. Copy IDs to clipboard
3. Paste into text file
4. Save as backup

### 4. Transient vs Permanent Errors

The system now classifies errors:
- **Transient**: Network issues, file system errors (not excluded)
- **Permanent**: Unavailable, private, deleted (excluded)

If you see many exclusions, some might be from old transient errors.

### 5. Refresh After Changes

After removing exclusions:
1. Click "Save"
2. Run "Download Videos" for the playlist
3. System will attempt to download previously excluded videos

## Advantages Over Old System

### Before (Simple Text Input)
```
❌ Just a list of IDs
❌ No titles shown
❌ Hard to identify videos
❌ Manual copy/paste needed
❌ No way to verify videos
❌ Difficult to manage many exclusions
```

### After (Exclusions Editor)
```
✅ Visual list with titles
✅ Easy identification
✅ Multiple selection
✅ Quick actions (copy, open)
✅ Verify in YouTube
✅ User-friendly interface
```

## Troubleshooting

### Problem: "Unknown Title" for All Videos

**Cause**: playlist_info.json not found or outdated

**Solution**:
1. Close Exclusions Editor
2. Click "Refresh playlists (force)" in main window
3. Reopen Exclusions Editor

### Problem: Can't Remove Video

**Cause**: Video might be re-added by system if still unavailable

**Solution**:
1. Remove from exclusions
2. Try downloading
3. If it fails with permanent error, it will be re-excluded
4. If it succeeds, it stays removed

### Problem: Changes Not Saved

**Cause**: Clicked "Cancel" instead of "Save"

**Solution**:
- Always click "Save" to apply changes
- "Cancel" discards all changes

### Problem: Video Still Not Downloading

**Cause**: Video might be in archive.txt already

**Solution**:
1. Check archive.txt in playlist folder
2. Remove the video ID line if present
3. Try downloading again

## See Also

- [Error Classification](ERROR_CLASSIFICATION.md) - How errors are classified
- [Transient Error Fix](TRANSIENT_ERROR_FIX.md) - Transient vs permanent errors
- [Custom Archive Logic](CUSTOM_ARCHIVE_IMPROVEMENTS.md) - Archive system
