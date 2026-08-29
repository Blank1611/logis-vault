import os
import json
from glob import glob
import yt_playlist_audio_tools as tools
import unicodedata

def get_archive_ids(playlist_folder: str) -> set[str]:
    """Load all video IDs from download_archive file."""
    archive_file = os.path.join(playlist_folder, "archive.txt")
    ids = set()
    if os.path.isfile(archive_file):
        try:
            with open(archive_file, "r", encoding="utf-8") as f:
                for line in f:
                    # Format: youtube VIDEO_ID
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        ids.add(parts[1])
        except Exception as e:
            print(f"Error reading archive: {e}")
    return ids

def get_local_mp4_files(playlist_folder: str) -> set[str]:
    """Get set of .mp4 filenames in folder."""
    files = set()
    for filepath in glob(os.path.join(playlist_folder, "*.mp4")):
        basename = os.path.basename(filepath)
        files.add(basename)
    return files

def extract_video_id_from_filename(filename: str) -> str:
    """Extract YouTube video ID from filename.
    Looks for pattern [VIDEO_ID] in filename."""
    import re
    # Look for [VIDEO_ID] pattern - YouTube IDs are 11 characters
    match = re.search(r'\[([a-zA-Z0-9_-]{11})\]', filename)
    if match:
        return match.group(1)
    return None



def get_id_to_title_map(playlist_folder: str) -> dict[str, str]:
    """Load ID -> Title mapping from playlist_info.json."""
    id_map = {}
    info_file = os.path.join(playlist_folder, "playlist_info.json")
    if os.path.isfile(info_file):
        try:
            with open(info_file, "r", encoding="utf-8") as f:
                info = json.load(f)
                entries = info.get("entries") or []
                for e in entries:
                    if e:
                        vid = e.get("id")
                        title = e.get("title")
                        if vid and title:
                            id_map[vid] = title
        except Exception as e:
            print(f"Error reading playlist_info.json: {e}")
    return id_map

def _sanitize_title_for_comparison(title: str) -> str:
    """Normalize title for flexible comparison with filenames.
    Removes/normalizes characters that yt-dlp might replace differently."""
    # First normalize unicode
    normalized = unicodedata.normalize('NFKD', title)
    
    # Remove or replace problematic characters that yt-dlp handles
    # Include both the original chars and their Unicode replacements
    chars_to_remove = r'\/:*?"<>|⧸⧹｜'  # Added ⧸ (big solidus), ⧹ (big reverse solidus), ｜ (fullwidth vertical line)
    result = []
    for c in normalized:
        if c not in chars_to_remove:
            result.append(c)
    
    return ''.join(result).strip().lower()

def main():
    # Modify these for your playlist
    base_path = "E:\\2tbhdd\\songs\\syst\\New folder\\youtube"
    playlist_title = "Awesome_testing"

    safe_title = tools._sanitize_title(playlist_title)
    playlist_folder = os.path.join(base_path, safe_title)

    print(f"Checking: {playlist_title}")
    print(f"Folder: {playlist_folder}\n")

    # Get data from different sources
    archive_ids = get_archive_ids(playlist_folder)
    local_files = get_local_mp4_files(playlist_folder)
    id_to_title = get_id_to_title_map(playlist_folder)

    # Extract video IDs from local filenames
    local_video_ids = {}  # video_id -> filename
    files_without_ids = []
    
    for filename in local_files:
        vid = extract_video_id_from_filename(filename)
        if vid:
            local_video_ids[vid] = filename
        else:
            files_without_ids.append(filename)
    
    print(f"Archive entries:        {len(archive_ids)}")
    print(f"Local .mp4 files:       {len(local_files)}")
    print(f"Files with video IDs:   {len(local_video_ids)}")
    print(f"Files without IDs:      {len(files_without_ids)}")
    print(f"ID->Title mappings:     {len(id_to_title)}\n")
    
    if len(archive_ids) != len(local_files):
        print(f"⚠️  DISCREPANCY: {len(archive_ids)} IDs in archive but {len(local_files)} files on disk")
        print(f"   Difference: {len(archive_ids) - len(local_files)} videos\n")
    
    # Find videos in archive but NOT on disk (by video ID)
    missing_videos = []
    no_title_videos = []
    
    for vid in sorted(archive_ids):
        if vid not in local_video_ids:
            # Video ID from archive not found in any local file
            if vid in id_to_title:
                missing_videos.append({
                    "id": vid,
                    "title": id_to_title[vid]
                })
            else:
                no_title_videos.append(vid)
    
    print(f"✅ Videos found on disk:     {len(archive_ids) - len(missing_videos) - len(no_title_videos)}")
    print(f"❌ Videos missing from disk: {len(missing_videos)}")
    if len(no_title_videos) > 0:
        print(f"⚠️  Videos with no title:     {len(no_title_videos)}")
    print()



    if no_title_videos:
        print(f"⚠️  NO TITLE: Videos in archive but no title in playlist_info.json ({len(no_title_videos)}):\n")
        for idx, vid in enumerate(no_title_videos[:10], 1):
            print(f"  {idx}. {vid}")
        if len(no_title_videos) > 10:
            print(f"  ... and {len(no_title_videos) - 10} more\n")

    if no_title_videos:
        print(f"⚠️  NO TITLE: Videos in archive but no title in playlist_info.json ({len(no_title_videos)}):\n")
        for idx, vid in enumerate(no_title_videos[:10], 1):
            print(f"  {idx}. {vid}")
        if len(no_title_videos) > 10:
            print(f"  ... and {len(no_title_videos) - 10} more\n")
        print()
    
    if missing_videos:
        print(f"❌ MISSING: Videos in archive.txt but NOT found on disk ({len(missing_videos)}):\n")
        for idx, item in enumerate(missing_videos, 1):
            print(f"  {idx}. [{item['id']}] {item['title']}")
        print()
    else:
        print("✅ All archived videos are present on disk!\n")

    # Find videos on disk but NOT in archive (by video ID)
    extra_videos = []
    for filename in sorted(local_files):
        vid = extract_video_id_from_filename(filename)
        if vid:
            if vid not in archive_ids:
                extra_videos.append(filename)
        else:
            # File has no video ID, can't verify
            extra_videos.append(filename)

    if extra_videos:
        print(f"⚠️  EXTRA: Videos on disk but NOT in archive ({len(extra_videos)}):")
        print(f"   (These may be manually added or have no video ID in filename)\n")
        for idx, filename in enumerate(extra_videos[:10], 1):
            vid = extract_video_id_from_filename(filename)
            if vid:
                print(f"  {idx}. [{vid}] {filename}")
            else:
                print(f"  {idx}. [NO ID] {filename}")
        if len(extra_videos) > 10:
            print(f"  ... and {len(extra_videos) - 10} more")
        print()
    else:
        print("✅ No extra videos on disk.\n")

    # ===== SUMMARY SECTION =====
    print("\n" + "="*70)
    print("SUMMARY".center(70))
    print("="*70)
    print(f"  Archive IDs recorded:              {len(archive_ids):>4}")
    print(f"  Local .mp4 files found:            {len(local_files):>4}")
    print(f"  ID->Title mappings:                {len(id_to_title):>4}")
    print(f"  Videos with no title info:         {len(no_title_videos):>4}")
    print(f"  Missing (in archive, not on disk): {len(missing_videos):>4}")
    print(f"  Extra (on disk, not in archive):   {len(extra_videos):>4}")
    print("="*70)
    
    # Calculate expected vs actual
    found_count = len(archive_ids) - len(no_title_videos) - len(missing_videos)
    print(f"\n  Archive IDs:       {len(archive_ids)}")
    print(f"  - No title info:   {len(no_title_videos)}")
    print(f"  - Missing files:   {len(missing_videos)}")
    print(f"  = Found on disk:   {found_count}")
    print(f"  Actual files:      {len(local_files)}")
    print(f"  Extra files:       {len(extra_videos)}\n")
    
    if missing_videos:
        print(f"📋 Missing video IDs (these should be excluded or re-downloaded):")
        ids_str = ", ".join([f'"{v["id"]}"' for v in missing_videos])
        print(f"   {ids_str}\n")
    
    # Final analysis
    print(f"🔍 FINAL ANALYSIS:")
    print(f"   ✅ {found_count} videos from archive.txt are present on disk")
    print(f"   ❌ {len(missing_videos)} videos from archive.txt are MISSING")
    if len(extra_videos) > 0:
        print(f"   📁 {len(extra_videos)} extra files on disk (not in archive or no video ID)")
    if len(no_title_videos) > 0:
        print(f"   ⚠️  {len(no_title_videos)} archive IDs have no title information")
    print()
    
    if len(missing_videos) > 0:
        print(f"⚠️  The {len(missing_videos)} missing videos were marked as downloaded in archive.txt")
        print(f"   but the files are NOT present on disk.")
        print(f"   Possible reasons:")
        print(f"   - Download failed but was marked as complete in archive")
        print(f"   - Files were manually deleted after download")
        print(f"   - Files were moved to another location")
        print(f"   - Disk corruption or file system issues\n")

if __name__ == "__main__":
    main()
