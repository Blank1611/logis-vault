#!/usr/bin/env python3
"""
Clean up .part files (incomplete downloads) from a playlist folder.
"""

import os
import sys
import glob
from pathlib import Path

def cleanup_part_files(playlist_folder: str, video_id: str = None, dry_run: bool = True):
    """
    Clean up .part files from a playlist folder.
    
    Args:
        playlist_folder: Path to the playlist folder
        video_id: Optional video ID to clean up specific .part file
        dry_run: If True, only show what would be deleted without actually deleting
    """
    
    if not os.path.exists(playlist_folder):
        print(f"❌ Playlist folder not found: {playlist_folder}")
        return
    
    print(f"Scanning for .part files in: {playlist_folder}\n")
    
    # Find all .part files
    part_files = glob.glob(os.path.join(playlist_folder, "*.part"))
    
    if not part_files:
        print("✓ No .part files found")
        return
    
    print(f"Found {len(part_files)} .part file(s):\n")
    
    # Filter by video ID if specified
    if video_id:
        part_files = [pf for pf in part_files if video_id in pf]
        if not part_files:
            print(f"No .part files found for video ID: {video_id}")
            return
        print(f"Filtered to {len(part_files)} file(s) matching video ID: {video_id}\n")
    
    # List files and calculate total size
    total_size = 0
    for pf in part_files:
        size_mb = os.path.getsize(pf) / (1024 * 1024)
        total_size += size_mb
        print(f"  - {os.path.basename(pf)} ({size_mb:.1f} MB)")
    
    print(f"\nTotal size: {total_size:.1f} MB")
    
    if dry_run:
        print("\n" + "=" * 60)
        print("DRY RUN MODE - No files will be deleted")
        print("=" * 60)
        print("\nTo actually delete these files, run with --delete flag:")
        if video_id:
            print(f'  python cleanup_part_files.py "{playlist_folder}" {video_id} --delete')
        else:
            print(f'  python cleanup_part_files.py "{playlist_folder}" --delete')
    else:
        print("\n" + "=" * 60)
        print("DELETING FILES")
        print("=" * 60)
        
        deleted_count = 0
        for pf in part_files:
            try:
                os.remove(pf)
                print(f"✓ Deleted: {os.path.basename(pf)}")
                deleted_count += 1
            except Exception as e:
                print(f"✗ Failed to delete {os.path.basename(pf)}: {e}")
        
        print(f"\n✓ Deleted {deleted_count} of {len(part_files)} file(s)")
        print(f"  Freed {total_size:.1f} MB of disk space")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python cleanup_part_files.py <playlist_folder> [video_id] [--delete]")
        print()
        print("Examples:")
        print('  # Dry run - show what would be deleted')
        print('  python cleanup_part_files.py "C:\\Downloads\\MyPlaylist"')
        print()
        print('  # Delete all .part files')
        print('  python cleanup_part_files.py "C:\\Downloads\\MyPlaylist" --delete')
        print()
        print('  # Delete .part file for specific video')
        print('  python cleanup_part_files.py "C:\\Downloads\\MyPlaylist" "87XbYi98DTg" --delete')
        sys.exit(1)
    
    playlist_folder = sys.argv[1]
    video_id = None
    dry_run = True
    
    # Parse arguments
    for arg in sys.argv[2:]:
        if arg == "--delete":
            dry_run = False
        elif not video_id:
            video_id = arg
    
    cleanup_part_files(playlist_folder, video_id, dry_run)
