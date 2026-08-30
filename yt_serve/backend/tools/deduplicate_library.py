#!/usr/bin/env python3
"""
CLI Tool: Retroactive Library Deduplication & Hardlink Space Reclaimer
Scans a playlist music library, detects physical file duplicates across folders,
and converts them into zero-space NTFS/ext4 hardlinks.
"""

import sys
import os
from pathlib import Path
import argparse

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.services.deduplication_service import (
    scan_library_duplicates,
    apply_library_deduplication,
    format_bytes
)


def main():
    parser = argparse.ArgumentParser(
        description="Retroactive Library Deduplication & Zero-Space Hardlink Reclaimer"
    )
    parser.add_argument(
        "--base-path",
        type=str,
        default=None,
        help=f"Root download directory to scan (defaults to {settings.BASE_DOWNLOAD_PATH})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Scan and report duplicate files and potential space savings without modifying disk"
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Convert redundant physical duplicate files into zero-space hardlinks"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed file-by-file paths"
    )

    args = parser.parse_args()

    scan_path = args.base_path or settings.BASE_DOWNLOAD_PATH
    print(f"\n{'='*70}")
    print(" [*] Library Deduplication & Hardlink Space Reclaimer")
    print(f"{'='*70}")
    print(f" Target Directory : {os.path.abspath(scan_path)}")
    print(f" Mode             : {'APPLY (Convert to hardlinks)' if args.apply else 'DRY RUN (Preview only)'}")
    print(f"{'='*70}\n")

    print("Scanning library for duplicate tracks...")
    scan_res = scan_library_duplicates(base_path=scan_path)

    if scan_res.get("status") != "success":
        print(f"[!] Error: {scan_res.get('message')}")
        sys.exit(1)

    dup_groups = scan_res.get("duplicate_groups", [])
    total_dups = scan_res.get("total_duplicate_files", 0)
    reclaimable = scan_res.get("formatted_reclaimable_space", "0 B")

    print(f"[+] Scanned {scan_res.get('total_scanned_files')} media files.")
    print(f"[+] Found {len(dup_groups)} duplicate track groups ({total_dups} redundant physical copies).")
    print(f"[+] Potential Space Reclaimable: {reclaimable}\n")

    if not dup_groups:
        print("[+] Your library is already 100% deduplicated! Zero action needed.\n")
        return

    # Reconfigure stdout for UTF-8 on modern Python
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

    # Print summary table
    print(f"{'-'*70}")
    print(f" {'Track Title':<35} | {'Type':<6} | {'Duplicates':<10} | {'Space':<10}")
    print(f"{'-'*70}")
    for g in dup_groups[:30]:  # Show top 30 preview in terminal
        raw_title = g['title']
        try:
            title = raw_title[:33] + '..' if len(raw_title) > 35 else raw_title
        except Exception:
            title = g.get('video_id', 'Track')
        mtype = g.get('media_type', 'media')
        dup_count = len(g.get('redundant_copies', []))
        space_str = g.get('formatted_reclaimable_space', '0 B')
        print(f" {title:<35} | {mtype:<6} | {dup_count:<10} | {space_str:<10}")

        if args.verbose:
            print(f"   Master Copy : {g['master_file']['filepath']}")
            for r in g['redundant_copies']:
                print(f"   Redundant   : {r['filepath']} ({format_bytes(r['file_size'])})")
    
    if len(dup_groups) > 30:
        print(f" ... and {len(dup_groups) - 30} more duplicate track groups (use Web GUI for full interactive list).")
    print(f"{'-'*70}\n")

    if args.apply:
        print("[*] Applying zero-space hardlink conversion...")
        apply_res = apply_library_deduplication(duplicate_groups=dup_groups, base_path=scan_path)
        print(f"[+] Successfully converted {apply_res.get('files_converted')} files to zero-space hardlinks.")
        print(f"[+] Total Disk Space Reclaimed: {apply_res.get('formatted_space_reclaimed')}\n")
        if apply_res.get("errors"):
            print("[!] Warnings/Errors encountered:")
            for err in apply_res["errors"]:
                print(f"  - {err}")
    else:
        print("[i] Dry-run completed. To convert these files into hardlinks and reclaim space, run:")
        print(f"    python {sys.argv[0]} --apply\n")


if __name__ == "__main__":
    main()
