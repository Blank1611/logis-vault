#!/usr/bin/env python3
"""
migrate_legacy_snapshots.py

Standalone migration utility to import legacy timestamped playlist_info_*.json snapshots
across all playlist directories into Git version control in authentic chronological order.

Location: yt_serve/backend/migrations/migrate_legacy_snapshots.py
Usage:
    # 1. Preview timeline (Dry Run):
    python yt_serve/backend/migrations/migrate_legacy_snapshots.py --dry-run

    # 2. Run historical migration:
    python yt_serve/backend/migrations/migrate_legacy_snapshots.py

    # 3. Run migration and cleanup legacy timestamped JSON files:
    python yt_serve/backend/migrations/migrate_legacy_snapshots.py --cleanup-legacy

    # 4. Optional push to remote after migration:
    python yt_serve/backend/migrations/migrate_legacy_snapshots.py --push
"""

import os
import sys
import json
import re
import argparse
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.utils.git_sync import ensure_git_repo, _run_git_cmd, push_to_remote_sync


@dataclass
class SnapshotRecord:
    playlist_folder: str       # Full path to playlist root directory
    playlist_title: str        # Playlist title (or folder basename)
    source_file_path: str      # Path to the specific legacy snapshot file
    target_file_path: str      # Path to the canonical playlist_info.json
    timestamp: datetime        # Parsed historical datetime
    is_latest: bool            # True if this is the active unversioned playlist_info.json


def _parse_snapshot_timestamp(file_name: str, file_path: str) -> Tuple[datetime, bool]:
    """
    Parse datetime from filename pattern playlist_info_YYYYMMDD_HHMMSS.json
    or fallback to file mtime for unversioned playlist_info.json.
    """
    pattern = r"playlist_info_(\d{4})(\d{2})(\d{2})_(\d{2})(\d{2})(\d{2})\.json$"
    match = re.search(pattern, file_name, re.IGNORECASE)
    if match:
        year, month, day, hour, minute, second = map(int, match.groups())
        try:
            return datetime(year, month, day, hour, minute, second), False
        except ValueError:
            pass
            
    # Unversioned active file or non-matching timestamp -> use mtime
    mtime = os.path.getmtime(file_path)
    return datetime.fromtimestamp(mtime), True


def discover_all_snapshots(base_path: str) -> Tuple[List[SnapshotRecord], List[str]]:
    """
    Scan all playlist directories under base_path and collect all snapshot files.
    Returns (sorted_snapshot_records, legacy_files_to_cleanup).
    """
    records: List[SnapshotRecord] = []
    legacy_files: List[str] = []

    if not os.path.exists(base_path):
        print(f"[ERROR] Base download path does not exist: {base_path}")
        return records, legacy_files

    entries = [d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))]
    
    for entry in entries:
        if entry.startswith(".") or entry.lower() in ("logs", "temp", "tmp", "__pycache__"):
            continue

        playlist_folder = os.path.join(base_path, entry)
        snap_dir = os.path.join(playlist_folder, "playlist_info_snapshot")
        canonical_target = os.path.join(snap_dir, "playlist_info.json")

        if not os.path.exists(snap_dir):
            continue

        # Look for all playlist_info*.json in snap_dir
        for fname in os.listdir(snap_dir):
            if not fname.lower().startswith("playlist_info") or not fname.lower().endswith(".json"):
                continue

            full_file_path = os.path.join(snap_dir, fname)
            if not os.path.isfile(full_file_path):
                continue

            ts, is_latest = _parse_snapshot_timestamp(fname, full_file_path)
            
            if not is_latest:
                legacy_files.append(full_file_path)

            records.append(SnapshotRecord(
                playlist_folder=playlist_folder,
                playlist_title=entry,
                source_file_path=full_file_path,
                target_file_path=canonical_target,
                timestamp=ts,
                is_latest=is_latest
            ))

    # Sort records globally by timestamp ascending
    # For identical timestamps, keep unversioned latest file last
    records.sort(key=lambda r: (r.timestamp, 1 if r.is_latest else 0))
    return records, legacy_files


def _load_json_safe(path: str) -> Optional[dict]:
    """Safely load JSON file content"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  [WARN] Failed to read JSON at {path}: {e}")
        return None


def _format_migration_commit_message(
    playlist_title: str,
    old_entries: Optional[List[dict]],
    new_info: dict,
    timestamp: datetime
) -> str:
    """Format descriptive commit message with video ID deltas"""
    actual_title = new_info.get("title") or playlist_title
    new_entries = new_info.get("entries") or []
    track_count = len(new_entries)

    if old_entries is None:
        return f"[Legacy Snapshot] Initial '{actual_title}' ({track_count} tracks)"

    old_ids = {e.get("id"): e for e in old_entries if e and e.get("id")}
    new_ids = {e.get("id"): e for e in new_entries if e and e.get("id")}

    added = [vid for vid in new_ids if vid not in old_ids]
    removed = [vid for vid in old_ids if vid not in new_ids]

    # Check for newly privatized / unavailable status
    newly_privatized = []
    for vid, entry in new_ids.items():
        if vid in old_ids:
            old_title = str(old_ids[vid].get("title", ""))
            new_title = str(entry.get("title", ""))
            if ("[Private video]" in new_title or "[Deleted video]" in new_title) and \
               ("[Private video]" not in old_title and "[Deleted video]" not in old_title):
                newly_privatized.append(vid)

    changes = []
    if added:
        id_str = ", ".join(added[:3]) + (f" +{len(added)-3} more" if len(added) > 3 else "")
        changes.append(f"+{len(added)} added [ID{'s' if len(added) > 1 else ''}: {id_str}]")
    if removed:
        id_str = ", ".join(removed[:3]) + (f" +{len(removed)-3} more" if len(removed) > 3 else "")
        changes.append(f"-{len(removed)} deleted [ID{'s' if len(removed) > 1 else ''}: {id_str}]")
    if newly_privatized:
        id_str = ", ".join(newly_privatized[:3]) + (f" +{len(newly_privatized)-3} more" if len(newly_privatized) > 3 else "")
        changes.append(f"-{len(newly_privatized)} removed/private [ID{'s' if len(newly_privatized) > 1 else ''}: {id_str}]")

    if changes:
        change_summary = "; ".join(changes)
        return f"[Legacy Snapshot] Update '{actual_title}': {change_summary} (Total: {track_count})"
    else:
        date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        return f"[Legacy Snapshot] Update '{actual_title}': Snapshot at {date_str} (Total: {track_count})"


def run_migration(
    base_path: str,
    dry_run: bool = False,
    cleanup_legacy: bool = False,
    push: bool = False,
    verbose: bool = False
):
    """Execute the chronological snapshot migration"""
    print("\n" + "=" * 70)
    print("  LEGACY PLAYLIST SNAPSHOT -> GIT MIGRATION UTILITY")
    print("=" * 70)
    print(f"Target Base Path : {base_path}")
    print(f"Dry Run Mode     : {'YES (No files modified)' if dry_run else 'NO (Live Execution)'}")
    print(f"Cleanup Legacy   : {'YES (Old timestamped files will be removed)' if cleanup_legacy else 'NO (Preserve legacy files)'}")
    print(f"Push to Remote   : {'YES' if push else 'NO'}")
    print("=" * 70 + "\n")

    # 1. Discover snapshots
    print("1. Discovering legacy snapshot files...")
    records, legacy_files = discover_all_snapshots(base_path)

    if not records:
        print("No snapshot files found to migrate.")
        return

    print(f"Found {len(records)} total snapshot records across all playlists.")
    print(f"Found {len(legacy_files)} legacy timestamped files eligible for cleanup.\n")

    if dry_run:
        print("--- [DRY RUN] In-Memory Chronological Playback Simulation ---")
        print("NOTE: Strictly read-only simulation. NO files are modified, NO Git commits are executed.\n")
        
        simulated_entries: Dict[str, List[dict]] = {}
        sim_committed = 0
        sim_skipped = 0

        for idx, rec in enumerate(records, 1):
            ts_str = rec.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            fname = os.path.basename(rec.source_file_path)
            
            data = _load_json_safe(rec.source_file_path)
            if not data:
                print(f"  [{idx:03d}/{len(records):03d}] {ts_str} | [WARN] Unreadable JSON: {fname}")
                sim_skipped += 1
                continue

            old_entries = simulated_entries.get(rec.playlist_folder)
            commit_msg = _format_migration_commit_message(
                rec.playlist_title,
                old_entries,
                data,
                rec.timestamp
            )

            # Check if there are content differences
            new_entries = data.get("entries") or []
            if old_entries is not None and old_entries == new_entries:
                sim_skipped += 1
                if verbose:
                    print(f"  [{idx:03d}/{len(records):03d}] {ts_str} | [SKIP NO DIFF] '{rec.playlist_title}' ({fname})")
            else:
                sim_committed += 1
                print(f"  [{idx:03d}/{len(records):03d}] {ts_str} | {commit_msg}")

            simulated_entries[rec.playlist_folder] = new_entries

        print("\n" + "=" * 70)
        print(f"[DRY RUN SUMMARY] Would create {sim_committed} commits, {sim_skipped} identical skipped.")
        print(f"[DRY RUN SUMMARY] Would clean up {len(legacy_files)} legacy files if --cleanup-legacy was passed.")
        print("[DRY RUN COMPLETE] Zero files were modified. Zero Git commands were run.")
        print("=" * 70 + "\n")
        return

    # 2. Ensure Git repository is initialized
    print("2. Initializing / verifying Git repository in download folder...")
    if not ensure_git_repo(base_path):
        print(f"[ERROR] Failed to initialize Git repository in {base_path}")
        return

    # 3. Process snapshots in chronological order
    print(f"3. Replaying {len(records)} historical snapshots into Git...")
    
    last_entries_per_playlist: Dict[str, List[dict]] = {}
    committed_count = 0
    skipped_count = 0

    for idx, rec in enumerate(records, 1):
        rel_target = os.path.relpath(rec.target_file_path, base_path).replace("\\", "/")
        ts_str = rec.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        fname = os.path.basename(rec.source_file_path)

        data = _load_json_safe(rec.source_file_path)
        if not data:
            print(f"  [{idx}/{len(records)}] Skipping unreadable snapshot: {fname}")
            skipped_count += 1
            continue

        # Overwrite target canonical playlist_info.json with this historical snapshot content
        if os.path.abspath(rec.source_file_path) != os.path.abspath(rec.target_file_path):
            with open(rec.target_file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        # Stage the target file
        add_code, add_out, add_err = _run_git_cmd(["add", rel_target], cwd=base_path)
        if add_code != 0:
            print(f"  [ERROR] Failed to git add {rel_target}: {add_err or add_out}")
            continue

        # Check if there is actual cached diff to commit
        diff_code, _, _ = _run_git_cmd(["diff", "--cached", "--quiet"], cwd=base_path)
        if diff_code == 0:
            # 0 means no diff detected
            if verbose:
                print(f"  [{idx:03d}/{len(records):03d}] {ts_str} '{rec.playlist_title}': No changes, skipping commit.")
            skipped_count += 1
            last_entries_per_playlist[rec.playlist_folder] = data.get("entries") or []
            continue

        # Format commit message with exact video ID deltas
        old_entries = last_entries_per_playlist.get(rec.playlist_folder)
        commit_msg = _format_migration_commit_message(
            rec.playlist_title,
            old_entries,
            data,
            rec.timestamp
        )

        # Commit with historical author & committer date
        commit_env = {
            "GIT_AUTHOR_DATE": ts_str,
            "GIT_COMMITTER_DATE": ts_str,
        }

        c_code, c_out, c_err = _run_git_cmd(
            ["commit", "-m", commit_msg, f"--date={ts_str}"],
            cwd=base_path,
            env_vars=commit_env
        )

        if c_code == 0:
            committed_count += 1
            print(f"  [{idx:03d}/{len(records):03d}] {ts_str} -> {commit_msg}")
        else:
            print(f"  [WARN] Failed to commit: {c_err or c_out}")

        last_entries_per_playlist[rec.playlist_folder] = data.get("entries") or []

    print("\n" + "=" * 70)
    print(f"Migration Replay Summary: {committed_count} commits created, {skipped_count} unchanged skipped.")
    print("=" * 70 + "\n")

    # 4. Ensure final active state is latest for all playlists
    print("4. Verifying latest playlist_info.json files are active...")
    for rec in records:
        if rec.is_latest and os.path.exists(rec.source_file_path):
            if os.path.abspath(rec.source_file_path) != os.path.abspath(rec.target_file_path):
                shutil.copy2(rec.source_file_path, rec.target_file_path)

    # 5. Optional Legacy File Cleanup
    if cleanup_legacy:
        print(f"5. Cleaning up {len(legacy_files)} legacy timestamped snapshot files...")
        cleaned_count = 0
        for l_path in legacy_files:
            try:
                if os.path.exists(l_path):
                    os.remove(l_path)
                    cleaned_count += 1
            except Exception as e:
                print(f"  [WARN] Failed to delete {l_path}: {e}")
        print(f"Successfully removed {cleaned_count} legacy timestamped snapshot files.")
    else:
        print("5. Preserving legacy timestamped files (pass --cleanup-legacy to delete).")

    # 6. Optional Remote Push
    if push:
        print("\n6. Pushing migration commits to configured remote repository...")
        push_success, push_msg = push_to_remote_sync()
        if push_success:
            print(f"  [SUCCESS] {push_msg}")
        else:
            print(f"  [WARN] Remote push result: {push_msg}")

    print("\n[DONE] Historical Git snapshot migration finished successfully!\n")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate historical playlist_info_*.json snapshots into Git version control."
    )
    parser.add_argument(
        "--base-path",
        type=str,
        default=None,
        help="Base download path (defaults to BASE_DOWNLOAD_PATH from settings)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate and print the chronological timeline without making file changes or Git commits"
    )
    parser.add_argument(
        "--cleanup-legacy",
        action="store_true",
        help="Delete legacy timestamped playlist_info_YYYYMMDD_HHMMSS.json files after migration"
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push created Git commits to remote GitHub repository"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed verbose output"
    )

    args = parser.parse_args()

    target_base_path = args.base_path or settings.BASE_DOWNLOAD_PATH
    if not target_base_path:
        print("[ERROR] BASE_DOWNLOAD_PATH is not configured.")
        sys.exit(1)

    run_migration(
        base_path=target_base_path,
        dry_run=args.dry_run,
        cleanup_legacy=args.cleanup_legacy,
        push=args.push,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()
