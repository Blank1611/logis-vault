import os
import json

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

def main():
    # Modify these for your playlist
    base_path = "E:\\2tbhdd\\songs\\syst\\New folder\\youtube"
    playlist_title = "Awesome"
    
    playlist_folder = os.path.join(base_path, playlist_title)
    output_file = os.path.join(playlist_folder, "archive_titles.txt")
    
    print(f"Reading from: {playlist_folder}")
    
    # Get archive IDs and title mappings
    archive_ids = get_archive_ids(playlist_folder)
    id_to_title = get_id_to_title_map(playlist_folder)
    
    print(f"Found {len(archive_ids)} IDs in archive.txt")
    print(f"Found {len(id_to_title)} title mappings in playlist_info.json")
    
    # Write titles to file
    titles_written = 0
    no_title_count = 0
    
    with open(output_file, "w", encoding="utf-8") as f:
        for vid in sorted(archive_ids):
            if vid in id_to_title:
                title = id_to_title[vid]
                f.write(f"{title}\n")
                titles_written += 1
            else:
                no_title_count += 1
    
    print(f"\n✅ Exported {titles_written} titles to: {output_file}")
    if no_title_count > 0:
        print(f"⚠️  {no_title_count} IDs had no title mapping")

if __name__ == "__main__":
    main()
