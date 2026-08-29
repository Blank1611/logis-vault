import os
import re
from glob import glob

def get_archive_ids(playlist_folder: str) -> set[str]:
    """Load all video IDs from download_archive file."""
    archive_file = os.path.join(playlist_folder, "archive.txt")
    ids = set()
    if os.path.isfile(archive_file):
        with open(archive_file, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    ids.add(parts[1])
    return ids

def get_video_ids_from_files(playlist_folder: str) -> dict[str, str]:
    """Extract video IDs from filenames. Returns dict of {video_id: filename}"""
    id_to_file = {}
    for filepath in glob(os.path.join(playlist_folder, "*.mp4")):
        filename = os.path.basename(filepath)
        match = re.search(r'\[([a-zA-Z0-9_-]{11})\]', filename)
        if match:
            video_id = match.group(1)
            id_to_file[video_id] = filename
    return id_to_file

def main():
    base_path = "E:\\2tbhdd\\songs\\syst\\New folder\\youtube"
    playlist_title = "Awesome"
    playlist_folder = os.path.join(base_path, playlist_title)
    
    print(f"Analyzing: {playlist_folder}\n")
    
    # Get IDs from both sources
    archive_ids = get_archive_ids(playlist_folder)
    file_ids_map = get_video_ids_from_files(playlist_folder)
    file_ids = set(file_ids_map.keys())
    
    print(f"Archive IDs:     {len(archive_ids)}")
    print(f"File IDs:        {len(file_ids)}")
    print(f"Files w/o IDs:   {len(glob(os.path.join(playlist_folder, '*.mp4'))) - len(file_ids)}\n")
    
    # Find IDs in archive but NOT in files
    missing_from_disk = archive_ids - file_ids
    
    # Find IDs in files but NOT in archive
    extra_on_disk = file_ids - archive_ids
    
    # Find IDs in both
    in_both = archive_ids & file_ids
    
    print("="*80)
    print(f"IDs IN BOTH archive.txt AND files: {len(in_both)}")
    print("="*80)
    
    # Save detailed results to file
    output_file = os.path.join(playlist_folder, "id_comparison_report.txt")
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("="*80 + "\n")
        f.write(f"IDs IN ARCHIVE but NOT in files: {len(missing_from_disk)}\n")
        f.write("="*80 + "\n")
        if missing_from_disk:
            f.write("\nThese videos are marked as downloaded in archive.txt\n")
            f.write("but no file with this ID exists on disk:\n\n")
            for idx, vid in enumerate(sorted(missing_from_disk), 1):
                f.write(f"  {idx:3}. {vid}\n")
        
        f.write("\n" + "="*80 + "\n")
        f.write(f"IDs IN FILES but NOT in archive: {len(extra_on_disk)}\n")
        f.write("="*80 + "\n")
        if extra_on_disk:
            f.write("\nThese files exist on disk but their IDs are NOT in archive.txt\n")
            f.write("(possibly re-uploaded videos or manually added):\n\n")
            for idx, vid in enumerate(sorted(extra_on_disk), 1):
                filename = file_ids_map[vid]
                f.write(f"  {idx:3}. [{vid}] {filename}\n")
    
    print(f"\n✅ Detailed report saved to: {output_file}")
    
    print("\n" + "="*80)
    print(f"IDs IN ARCHIVE but NOT in files: {len(missing_from_disk)}")
    print("="*80)
    if missing_from_disk:
        print(f"\nShowing first 10 of {len(missing_from_disk)}:")
        for idx, vid in enumerate(sorted(list(missing_from_disk))[:10], 1):
            print(f"  {idx:3}. {vid}")
        if len(missing_from_disk) > 10:
            print(f"  ... and {len(missing_from_disk) - 10} more (see report file)")
    
    print("\n" + "="*80)
    print(f"IDs IN FILES but NOT in archive: {len(extra_on_disk)}")
    print("="*80)
    if extra_on_disk:
        print(f"\nShowing first 10 of {len(extra_on_disk)}:")
        for idx, vid in enumerate(sorted(list(extra_on_disk))[:10], 1):
            filename = file_ids_map[vid]
            print(f"  {idx:3}. [{vid}] {filename[:60]}...")
        if len(extra_on_disk) > 10:
            print(f"  ... and {len(extra_on_disk) - 10} more (see report file)")
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"  Total archive IDs:           {len(archive_ids)}")
    print(f"  Total file IDs:              {len(file_ids)}")
    print(f"  Matched (in both):           {len(in_both)}")
    print(f"  Missing from disk:           {len(missing_from_disk)}")
    print(f"  Extra on disk:               {len(extra_on_disk)}")
    print(f"  Net difference:              {len(archive_ids) - len(file_ids)}")
    print("="*80)

if __name__ == "__main__":
    main()
