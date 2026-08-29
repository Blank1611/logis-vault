import os
import json
from glob import glob
import unicodedata
import shutil

def get_archive_ids(playlist_folder: str) -> set[str]:
    """Load all video IDs from download_archive file."""
    archive_file = os.path.join(playlist_folder, "archive.txt")
    ids = set()
    if os.path.isfile(archive_file):
        try:
            with open(archive_file, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        ids.add(parts[1])
        except Exception as e:
            print(f"Error reading archive: {e}")
    return ids

def get_id_to_title_map(playlist_folder: str) -> dict[str, str]:
    """Load ID -> Title mapping from playlist_info.json."""
    id_map = {}
    
    # Try new location first (playlist_info_snapshot folder)
    info_file = os.path.join(playlist_folder, "playlist_info_snapshot", "playlist_info.json")
    
    # Fall back to old location if not found
    if not os.path.isfile(info_file):
        info_file = os.path.join(playlist_folder, "playlist_info.json")
    
    if os.path.isfile(info_file):
        try:
            print(f"Loading playlist info from: {os.path.basename(os.path.dirname(info_file))}/playlist_info.json")
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
    else:
        print(f"⚠️  Warning: playlist_info.json not found in {playlist_folder}")
    
    return id_map

def remove_common_patterns(text: str) -> str:
    """
    Remove common patterns from video titles/filenames that don't help matching.
    These are typically added by uploaders but not in the actual title.
    """
    # Common patterns to remove (case-insensitive)
    patterns_to_remove = [
        'official video',
        'official lyric video',
        'official music video',
        'official audio',
        'lyric video',
        'music video',
        'official mv',
        'official',
        'hd',
        '4k',
        '1080p',
        '720p',
        'full video',
        'full song',
        'video song',
        'audio',
        'lyrics',
        'feat',
        'ft',
        'featuring',
    ]
    
    text_lower = text.lower()
    
    # Remove each pattern
    for pattern in patterns_to_remove:
        text_lower = text_lower.replace(pattern, '')
    
    # Normalize various artist separators to space
    # This helps match "Artist - Song" with "Artist Song" or "Artist & Artist - Song"
    separators = ['—', '–', '-', '&', '|', '/', '\\']
    for sep in separators:
        text_lower = text_lower.replace(sep, ' ')
    
    return text_lower


def normalize_for_comparison(text: str) -> str:
    """
    Aggressively normalize text for comparison.
    Removes ALL non-alphanumeric characters (spaces, punctuation, special chars).
    Result is lowercase alphanumeric only.
    """
    # First normalize unicode (e.g., accented characters)
    normalized = unicodedata.normalize('NFKD', text)
    
    # Remove file extension if present
    if '.' in normalized:
        normalized = normalized.rsplit('.', 1)[0]
    
    # Remove common video patterns that don't help matching
    normalized = remove_common_patterns(normalized)
    
    # Keep only alphanumeric characters (letters and numbers)
    # This removes: spaces, punctuation, special characters, everything
    alphanumeric_only = ''.join(c for c in normalized if c.isalnum())
    
    # Convert to lowercase for case-insensitive matching
    return alphanumeric_only.lower()

def find_similar_titles(normalized_filename: str, title_to_id: dict, id_to_title: dict, top_n: int = 3) -> list:
    """Find the most similar titles for debugging unmatched files."""
    similarities = []
    
    for norm_title, vid in title_to_id.items():
        # Calculate simple similarity score
        if norm_title in normalized_filename or normalized_filename in norm_title:
            similarity = 90
        elif len(norm_title) >= 10 and len(normalized_filename) >= 10:
            # Check prefix similarity
            min_len = min(len(norm_title), len(normalized_filename), 20)
            matching_chars = sum(1 for i in range(min_len) if i < len(norm_title) and i < len(normalized_filename) and norm_title[i] == normalized_filename[i])
            similarity = (matching_chars / min_len) * 100
        else:
            similarity = 0
        
        if similarity > 30:  # Only show if somewhat similar
            similarities.append({
                'title': id_to_title.get(vid, ''),
                'normalized': norm_title,
                'similarity': similarity,
                'id': vid
            })
    
    # Sort by similarity and return top N
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    return similarities[:top_n]


def main():
    # Configuration
    base_path = "E:\\2tbhdd\\songs\\syst\\New folder\\youtube"
    playlist_title = "Turk"
    
    playlist_folder = os.path.join(base_path, playlist_title)
    
    print(f"Scanning folder: {playlist_folder}\n")
    
    # Get data
    archive_ids = get_archive_ids(playlist_folder)
    id_to_title = get_id_to_title_map(playlist_folder)
    
    # Get all mp4 files
    mp4_files = []
    for filepath in glob(os.path.join(playlist_folder, "*.mp4")):
        mp4_files.append(filepath)
    
    print(f"Found {len(mp4_files)} .mp4 files")
    print(f"Found {len(archive_ids)} IDs in archive")
    print(f"Found {len(id_to_title)} title mappings\n")
    
    # Create reverse mapping: normalized title -> video ID
    title_to_id = {}
    for vid in archive_ids:
        if vid in id_to_title:
            title = id_to_title[vid]
            normalized = normalize_for_comparison(title)
            title_to_id[normalized] = vid
    
    # Match files to video IDs
    rename_operations = []
    unmatched_files = []
    
    for filepath in mp4_files:
        filename = os.path.basename(filepath)
        name_without_ext = os.path.splitext(filename)[0]
        
        # Check if already has video ID
        if name_without_ext.endswith(']') and '[' in name_without_ext:
            potential_id = name_without_ext.split('[')[-1].rstrip(']')
            if len(potential_id) == 11 and potential_id in archive_ids:
                print(f"✓ Already has ID: {filename}")
                continue
        
        # Aggressively normalize filename (alphanumeric only)
        normalized_filename = normalize_for_comparison(filename)
        
        matched_id = None
        best_score = 0
        best_title = None
        
        # Try to match with titles using alphanumeric-only comparison
        for norm_title, vid in title_to_id.items():
            score = 0
            match_type = None
            
            # Exact match (best)
            if norm_title == normalized_filename:
                score = 100
                match_type = "exact"
            
            # One contains the other (very good)
            elif norm_title in normalized_filename:
                score = 95
                match_type = "title in filename"
            elif normalized_filename in norm_title:
                score = 95
                match_type = "filename in title"
            
            # Prefix match (good for truncated names)
            elif len(normalized_filename) >= 20 and len(norm_title) >= 20:
                # Check if first 20 chars match
                if normalized_filename[:20] == norm_title[:20]:
                    score = 90
                    match_type = "prefix match"
            
            # Partial overlap (decent)
            elif len(normalized_filename) >= 30 and len(norm_title) >= 30:
                # Check for significant overlap
                min_len = min(len(normalized_filename), len(norm_title))
                overlap_len = min(50, min_len)
                
                if normalized_filename[:overlap_len] in norm_title or norm_title[:overlap_len] in normalized_filename:
                    score = 80
                    match_type = "partial overlap"
            
            # Fuzzy match for shorter strings
            elif len(normalized_filename) >= 10 and len(norm_title) >= 10:
                # Calculate similarity based on common substring
                shorter = min(len(normalized_filename), len(norm_title))
                if normalized_filename[:shorter] == norm_title[:shorter]:
                    score = 70
                    match_type = "fuzzy match"
            
            # Additional fallback: Check if significant portion of title is in filename
            # This helps with cases like "Artist - Song [Official Video]" vs "Song"
            elif len(norm_title) >= 8:
                # Check if at least 80% of title appears consecutively in filename
                title_len = len(norm_title)
                check_len = int(title_len * 0.8)
                
                if check_len >= 8:
                    # Try different positions in the title
                    for start_pos in range(0, title_len - check_len + 1):
                        title_chunk = norm_title[start_pos:start_pos + check_len]
                        if title_chunk in normalized_filename:
                            score = 65
                            match_type = "partial title match"
                            break
            
            if score > best_score:
                best_score = score
                matched_id = vid
                best_title = id_to_title.get(vid, "")
        
        if matched_id and best_score >= 65:
            # Create new filename with video ID
            new_filename = f"{name_without_ext} [{matched_id}].mp4"
            new_filepath = os.path.join(playlist_folder, new_filename)
            
            rename_operations.append({
                'old': filepath,
                'new': new_filepath,
                'old_name': filename,
                'new_name': new_filename,
                'id': matched_id,
                'title': best_title,
                'score': best_score,
                'norm_filename': normalized_filename,
                'norm_title': title_to_id.get(matched_id, "")
            })
        else:
            # Find similar titles for debugging
            similar = find_similar_titles(normalized_filename, title_to_id, id_to_title, top_n=3)
            unmatched_files.append({
                'filename': filename,
                'normalized': normalized_filename,
                'similar_titles': similar
            })
    
    # Show what will be renamed
    if rename_operations:
        print(f"\n{'='*80}")
        print(f"WILL RENAME {len(rename_operations)} FILES:")
        print(f"{'='*80}\n")
        
        for idx, op in enumerate(rename_operations[:10], 1):
            print(f"{idx}. OLD: {op['old_name']}")
            print(f"   NEW: {op['new_name']}")
            print(f"   Title: {op['title']}")
            print(f"   Match score: {op['score']}")
            print(f"   Normalized filename: {op['norm_filename'][:60]}...")
            print(f"   Normalized title:    {op['norm_title'][:60]}...\n")
        
        if len(rename_operations) > 10:
            print(f"... and {len(rename_operations) - 10} more\n")
    
    if unmatched_files:
        print(f"\n⚠️  {len(unmatched_files)} files could not be matched:")
        for item in unmatched_files[:5]:
            print(f"\n   File: {item['filename']}")
            print(f"   Normalized: {item['normalized'][:60]}...")
            
            if item.get('similar_titles'):
                print(f"   Most similar titles in playlist:")
                for sim in item['similar_titles']:
                    print(f"     - {sim['title']} (similarity: {sim['similarity']:.0f}%)")
                    print(f"       Normalized: {sim['normalized'][:50]}...")
                    print(f"       ID: {sim['id']}")
            else:
                print(f"   No similar titles found in playlist")
            print()
        
        if len(unmatched_files) > 5:
            print(f"   ... and {len(unmatched_files) - 5} more\n")
    
    # Interactive matching for unmatched files
    if unmatched_files:
        print(f"\n{'='*80}")
        print("INTERACTIVE MATCHING FOR UNMATCHED FILES")
        print(f"{'='*80}\n")
        
        response = input(f"Do you want to manually match the {len(unmatched_files)} unmatched files? (yes/no): ").strip().lower()
        
        if response == 'yes':
            manual_matches = []
            
            for idx, item in enumerate(unmatched_files, 1):
                print(f"\n{'='*80}")
                print(f"File {idx}/{len(unmatched_files)}: {item['filename']}")
                print(f"Normalized: {item['normalized'][:60]}...")
                print(f"{'='*80}")
                
                if item.get('similar_titles'):
                    print("\nSimilar titles found:")
                    for i, sim in enumerate(item['similar_titles'], 1):
                        print(f"  {i}. {sim['title']}")
                        print(f"     Similarity: {sim['similarity']:.0f}%")
                        print(f"     ID: {sim['id']}")
                        print(f"     Normalized: {sim['normalized'][:50]}...\n")
                    
                    print("  0. Skip this file")
                    print("  q. Quit interactive matching\n")
                    
                    while True:
                        choice = input(f"Select match (0-{len(item['similar_titles'])}, or 'q' to quit): ").strip().lower()
                        
                        if choice == 'q':
                            print("Exiting interactive matching...")
                            break
                        elif choice == '0':
                            print(f"Skipped: {item['filename']}\n")
                            break
                        elif choice.isdigit() and 1 <= int(choice) <= len(item['similar_titles']):
                            selected = item['similar_titles'][int(choice) - 1]
                            
                            # Get the original filepath
                            filepath = None
                            for f in mp4_files:
                                if os.path.basename(f) == item['filename']:
                                    filepath = f
                                    break
                            
                            if filepath:
                                name_without_ext = os.path.splitext(item['filename'])[0]
                                new_filename = f"{name_without_ext} [{selected['id']}].mp4"
                                new_filepath = os.path.join(playlist_folder, new_filename)
                                
                                manual_matches.append({
                                    'old': filepath,
                                    'new': new_filepath,
                                    'old_name': item['filename'],
                                    'new_name': new_filename,
                                    'id': selected['id'],
                                    'title': selected['title'],
                                    'score': 'manual',
                                    'norm_filename': item['normalized'],
                                    'norm_title': selected['normalized']
                                })
                                
                                print(f"✓ Matched: {item['filename']}")
                                print(f"  → {new_filename}\n")
                            break
                        else:
                            print(f"Invalid choice. Please enter 0-{len(item['similar_titles'])} or 'q'")
                    
                    if choice == 'q':
                        break
                else:
                    print("No similar titles found. Skipping...\n")
            
            # Add manual matches to rename operations
            if manual_matches:
                print(f"\n✓ Manually matched {len(manual_matches)} files")
                rename_operations.extend(manual_matches)
    
    # Ask for confirmation
    if rename_operations:
        # Count auto vs manual matches
        auto_matches = sum(1 for op in rename_operations if op.get('score') != 'manual')
        manual_matches = sum(1 for op in rename_operations if op.get('score') == 'manual')
        
        print(f"\n{'='*80}")
        print("RENAME SUMMARY")
        print(f"{'='*80}")
        print(f"Total files to rename: {len(rename_operations)}")
        print(f"  - Automatically matched: {auto_matches}")
        print(f"  - Manually matched: {manual_matches}")
        print(f"{'='*80}\n")
        
        response = input(f"Proceed with renaming {len(rename_operations)} files? (yes/no): ").strip().lower()
        
        if response == 'yes':
            success_count = 0
            error_count = 0
            
            for op in rename_operations:
                try:
                    os.rename(op['old'], op['new'])
                    success_count += 1
                except Exception as e:
                    print(f"❌ Error renaming {op['old_name']}: {e}")
                    error_count += 1
            
            print(f"\n✅ Successfully renamed {success_count} files")
            if error_count > 0:
                print(f"❌ Failed to rename {error_count} files")
        else:
            print("Cancelled. No files were renamed.")
    else:
        print("\nNo files need to be renamed.")

if __name__ == "__main__":
    main()
