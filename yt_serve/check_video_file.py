#!/usr/bin/env python3
"""
Check if a specific video file exists in a playlist folder.
Helps debug "file not found" issues.
"""

import os
import sys
import glob
from pathlib import Path

def check_video_file(playlist_folder: str, video_id: str):
    """Check if a video file with the given ID exists."""
    
    if not os.path.exists(playlist_folder):
        print(f"❌ Playlist folder not found: {playlist_folder}")
        return
    
    print(f"Checking for video ID: {video_id}")
    print(f"In folder: {playlist_folder}\n")
    
    # Check archive
    archive_file = os.path.join(playlist_folder, "archive.txt")
    if os.path.exists(archive_file):
        with open(archive_file, "r", encoding="utf-8") as f:
            archived_ids = set()
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    parts = line.split()
                    vid_id = parts[-1] if parts else line
                    archived_ids.add(vid_id)
        
        if video_id in archived_ids:
            print(f"✓ Video ID found in archive.txt")
        else:
            print(f"✗ Video ID NOT in archive.txt")
    else:
        print(f"✗ No archive.txt found")
    
    print()
    
    # Search for video files
    video_exts = ("*.mp4", "*.mkv", "*.webm", "*.m4v")
    all_files = []
    for pattern in video_exts:
        all_files.extend(glob.glob(os.path.join(playlist_folder, pattern)))
    
    print(f"Total video files in folder: {len(all_files)}\n")
    
    # Check for exact pattern matches
    print("Checking for expected patterns:")
    print(f"  Pattern 1: [video_id] in filename")
    print(f"  Pattern 2: _video_id. in filename\n")
    
    exact_matches = []
    for file in all_files:
        if f"[{video_id}]" in file or f"_{video_id}." in file:
            exact_matches.append(file)
    
    if exact_matches:
        print(f"✓ Found {len(exact_matches)} file(s) matching expected pattern:")
        for f in exact_matches:
            size_mb = os.path.getsize(f) / (1024 * 1024)
            print(f"  - {os.path.basename(f)} ({size_mb:.1f} MB)")
    else:
        print(f"✗ No files found matching expected pattern")
    
    print()
    
    # Check for any file containing the video ID
    partial_matches = []
    for file in all_files:
        if video_id in os.path.basename(file):
            partial_matches.append(file)
    
    if partial_matches:
        print(f"Files containing video ID (but not matching pattern):")
        for f in partial_matches:
            size_mb = os.path.getsize(f) / (1024 * 1024)
            print(f"  - {os.path.basename(f)} ({size_mb:.1f} MB)")
    else:
        print(f"No files found containing video ID {video_id}")
    
    print()
    
    # Check for .part files
    part_files = glob.glob(os.path.join(playlist_folder, "*.part"))
    if part_files:
        print(f"⚠️  Found {len(part_files)} incomplete download(s) (.part files):")
        for pf in part_files:
            if video_id in pf:
                size_mb = os.path.getsize(pf) / (1024 * 1024)
                print(f"  - {os.path.basename(pf)} ({size_mb:.1f} MB) ⚠️  MATCHES VIDEO ID")
            else:
                size_mb = os.path.getsize(pf) / (1024 * 1024)
                print(f"  - {os.path.basename(pf)} ({size_mb:.1f} MB)")
    
    print()
    
    # Recommendations
    print("=" * 60)
    print("RECOMMENDATIONS:")
    print("=" * 60)
    
    if exact_matches:
        print("✓ File exists and matches expected pattern")
        print("  The file should be detected correctly")
        print("  If still having issues, check file permissions")
    elif partial_matches:
        print("⚠️  File exists but doesn't match expected pattern")
        print("  Expected: Title [VideoID].ext or Title_VideoID.ext")
        print(f"  Found: {os.path.basename(partial_matches[0])}")
        print("  Consider renaming the file to match expected pattern")
    elif part_files and any(video_id in pf for pf in part_files):
        print("⚠️  Incomplete download found (.part file)")
        print("  Delete the .part file and re-download")
    else:
        print("✗ File not found")
        print("  Video needs to be downloaded")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python check_video_file.py <playlist_folder> <video_id>")
        print()
        print("Example:")
        print('  python check_video_file.py "C:\\Downloads\\MyPlaylist" "87XbYi98DTg"')
        sys.exit(1)
    
    playlist_folder = sys.argv[1]
    video_id = sys.argv[2]
    
    check_video_file(playlist_folder, video_id)
