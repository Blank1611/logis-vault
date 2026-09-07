#!/usr/bin/env python3
"""
migrate_legacy_snapshots.py

Standalone migration utility to import legacy timestamped playlist_info_*.json snapshots
across all playlist directories into Git version control in authentic chronological order.

Features:
- Intelligent commit grouping: groups snapshots by session window (e.g. 15-min scan batches)
  or by calendar day, drastically reducing commit bloat into clean atomic updates.
- Detailed multi-line changelogs showing per-playlist track deltas and video IDs.
- Full pre-flight and post-flight Git diagnostics (Author, Committer, Branch, Remote URL).
- True historical date preservation using both GIT_AUTHOR_DATE and GIT_COMMITTER_DATE.

Usage (via Docker Compose):
    # 1. Preview grouped timeline (Dry Run):
    docker compose run --rm --entrypoint python yt_serve migrations/migrate_legacy_snapshots.py --base-path /downloads --dry-run

    # 2. Run grouped migration (default: 15-min session window):
    docker compose run --rm --entrypoint python yt_serve migrations/migrate_legacy_snapshots.py --base-path /downloads

    # 3. Group by calendar day instead:
    docker compose run --rm --entrypoint python yt_serve migrations/migrate_legacy_snapshots.py --base-path /downloads --group-by day

    # 4. Run migration and cleanup legacy timestamped JSON files:
    docker compose run --rm --entrypoint python yt_serve migrations/migrate_legacy_snapshots.py --base-path /downloads --cleanup-legacy
"""

import os
import sys
import json
import re
import argparse
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.config import settings
from app.utils.git_sync import ensure_git_repo, _run_git_cmd, push_to_remote_sync, is_git_available


@dataclass
class SnapshotRecord:
    playlist_folder: str       # Full path to playlist root directory
    playlist_title: str        # Playlist title (or folder basename)
    source_file_path: str      # Path to the specific legacy snapshot file
    target_file_path: str      # Path to the canonical playlist_info.json
    timestamp: datetime        # Parsed historical datetime
    is_latest: bool            # True if this is the active unversioned playlist_info.json


@dataclass
class SnapshotGroup:
    timestamp: datetime           # Timestamp used for the Git commit
    records: List[SnapshotRecord] # Snapshots included in this commit


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


def group_snapshots(
    records: List[SnapshotRecord],
    mode: str = "session",
    window_minutes: int = 15
) -> List[SnapshotGroup]:
    """
    Group chronological snapshot records into batch commit groups.
    Modes:
    - 'session': Groups consecutive snapshots where time gap <= window_minutes
                 (and ensures at most one snapshot per playlist per group).
    - 'day': Groups all snapshots from the same calendar day.
    - 'none': 1 commit per snapshot record.
    """
    if not records:
        return []

    if mode == "none":
        return [SnapshotGroup(timestamp=r.timestamp, records=[r]) for r in records]

    groups: List[SnapshotGroup] = []
    current_records: List[SnapshotRecord] = []
    seen_playlists: Set[str] = set()
    current_group_start: Optional[datetime] = None
    last_timestamp: Optional[datetime] = None

    for rec in records:
        if not current_records:
            current_records = [rec]
            seen_playlists = {rec.playlist_folder}
            current_group_start = rec.timestamp
            last_timestamp = rec.timestamp
            continue

        should_split = False

        if mode == "day":
            if rec.timestamp.date() != current_group_start.date():
                should_split = True
            elif rec.playlist_folder in seen_playlists:
                should_split = True
        elif mode == "session":
            gap_minutes = (rec.timestamp - last_timestamp).total_seconds() / 60.0
            if gap_minutes > window_minutes:
                should_split = True
            elif rec.playlist_folder in seen_playlists:
                should_split = True

        if should_split:
            group_ts = current_records[-1].timestamp
            groups.append(SnapshotGroup(timestamp=group_ts, records=current_records))
            current_records = [rec]
            seen_playlists = {rec.playlist_folder}
            current_group_start = rec.timestamp
            last_timestamp = rec.timestamp
        else:
            current_records.append(rec)
            seen_playlists.add(rec.playlist_folder)
            last_timestamp = rec.timestamp

    if current_records:
        group_ts = current_records[-1].timestamp
        groups.append(SnapshotGroup(timestamp=group_ts, records=current_records))

    return groups


def _load_json_safe(path: str) -> Optional[dict]:
    """Safely load JSON file content"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"  [WARN] Failed to read JSON at {path}: {e}")
        return None


def _format_playlist_delta(
    playlist_title: str,
    old_entries: Optional[List[dict]],
    new_info: dict,
    timestamp: datetime
) -> Tuple[str, bool]:
    """
    Compute delta between previous entries and new snapshot for a single playlist.
    Returns (delta_summary_string, has_diff).
    """
    actual_title = new_info.get("title") or playlist_title
    new_entries = new_info.get("entries") or []
    track_count = len(new_entries)

    if old_entries is None:
        return f"Initial '{actual_title}' ({track_count} tracks)", True

    old_ids = {e.get("id"): e for e in old_entries if e and e.get("id")}
    new_ids = {e.get("id"): e for e in new_entries if e and e.get("id")}

    added = [vid for vid in new_ids if vid not in old_ids]
    removed = [vid for vid in old_ids if vid not in new_ids]

    # Check for newly privatized / deleted status
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

    has_diff = bool(changes)
    if changes:
        change_summary = "; ".join(changes)
        return f"Update '{actual_title}': {change_summary} (Total: {track_count})", has_diff
    else:
        date_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        return f"Update '{actual_title}': Snapshot at {date_str} (Total: {track_count})", has_diff


def _format_group_commit_message(
    group_timestamp: datetime,
    deltas: List[Tuple[str, str, bool]]
) -> str:
    """Format commit message for a group of snapshots (single or multi-playlist)"""
    ts_str = group_timestamp.strftime("%Y-%m-%d %H:%M:%S")
    if len(deltas) == 1:
        return f"[Legacy Snapshot] {deltas[0][1]}"

    # Multi-playlist batch commit
    subject = f"[Legacy Snapshot] Batch update {len(deltas)} playlists ({ts_str})"
    body = "\n".join(f"- {d[1]}" for d in deltas)
    return f"{subject}\n\n{body}"


def get_git_diagnostics(
    base_path: str,
    override_author_name: Optional[str] = None,
    override_author_email: Optional[str] = None
) -> Dict[str, str]:
    """Retrieve Git configuration and repository state for diagnostics inspection"""
    diag = {
        "git_available": "NO",
        "git_version": "N/A",
        "git_path": "N/A",
        "repo_path": base_path,
        "is_repo": "NO",
        "branch": "N/A",
        "author_name": "N/A",
        "author_email": "N/A",
        "remote_name": "N/A",
        "remote_url": "None (Local repository only)",
        "commit_count": "0",
    }

    git_bin = shutil.which("git")
    if not git_bin:
        return diag

    diag["git_available"] = "YES"
    diag["git_path"] = git_bin

    code, v_out, _ = _run_git_cmd(["--version"], cwd=base_path)
    if code == 0:
        diag["git_version"] = v_out

    git_dir = os.path.join(base_path, ".git")
    if os.path.isdir(git_dir):
        diag["is_repo"] = "YES"

        # Current branch
        c, b_out, _ = _run_git_cmd(["branch", "--show-current"], cwd=base_path)
        if c == 0 and b_out:
            diag["branch"] = b_out
        else:
            diag["branch"] = "main"

        # Remote URL
        c, r_out, _ = _run_git_cmd(["remote", "-v"], cwd=base_path)
        if c == 0 and r_out:
            first_line = r_out.splitlines()[0]
            diag["remote_url"] = first_line
            parts = first_line.split()
            diag["remote_name"] = parts[0] if parts else "origin"

        # Total Commits
        c, count_out, _ = _run_git_cmd(["rev-list", "--count", "HEAD"], cwd=base_path)
        if c == 0 and count_out:
            diag["commit_count"] = count_out

    # Resolve author name
    if override_author_name and override_author_name.strip():
        diag["author_name"] = override_author_name.strip()
    elif os.environ.get("GIT_AUTHOR_NAME"):
        diag["author_name"] = os.environ["GIT_AUTHOR_NAME"]
    elif getattr(settings, "GIT_USER_NAME", None) and getattr(settings, "GIT_USER_NAME") != "YouTube Playlist Manager":
        diag["author_name"] = getattr(settings, "GIT_USER_NAME")
    else:
        c, n_out, _ = _run_git_cmd(["config", "user.name"], cwd=base_path)
        if c == 0 and n_out:
            diag["author_name"] = n_out
        else:
            diag["author_name"] = getattr(settings, "GIT_USER_NAME", "YouTube Playlist Manager")

    # Resolve author email
    if override_author_email and override_author_email.strip():
        diag["author_email"] = override_author_email.strip()
    elif os.environ.get("GIT_AUTHOR_EMAIL"):
        diag["author_email"] = os.environ["GIT_AUTHOR_EMAIL"]
    elif getattr(settings, "GIT_USER_EMAIL", None) and getattr(settings, "GIT_USER_EMAIL") != "yt-manager@homelab.local":
        diag["author_email"] = getattr(settings, "GIT_USER_EMAIL")
    else:
        c, e_out, _ = _run_git_cmd(["config", "user.email"], cwd=base_path)
        if c == 0 and e_out:
            diag["author_email"] = e_out
        else:
            diag["author_email"] = getattr(settings, "GIT_USER_EMAIL", "yt-manager@homelab.local")

    return diag


def print_git_diagnostics(diag: Dict[str, str], title: str = "GIT REPOSITORY & COMMITTED IDENTITY DIAGNOSTICS"):
    """Print clean formatted diagnostics box"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)
    print(f"  Git Binary     : {diag['git_path']} ({diag['git_version']})")
    print(f"  Repository Dir : {diag['repo_path']}")
    print(f"  Git Repo Init  : {diag['is_repo']}")
    print(f"  Target Branch  : {diag['branch']}")
    print(f"  Author Name    : {diag['author_name']}")
    print(f"  Author Email   : {diag['author_email']}")
    print(f"  Committer Name : {diag['author_name']} (Mirrors author)")
    print(f"  Committer Mail : {diag['author_email']} (Mirrors author)")
    print(f"  Remote Remote  : {diag['remote_url']}")
    print(f"  Existing Count : {diag['commit_count']} commits in repository")
    print("=" * 70 + "\n")


def run_migration(
    base_path: str,
    group_by: str = "session",
    window_minutes: int = 15,
    author_name: Optional[str] = None,
    author_email: Optional[str] = None,
    dry_run: bool = False,
    cleanup_legacy: bool = False,
    push: bool = False,
    verbose: bool = False
):
    """Execute the grouped chronological snapshot migration"""
    print("\n" + "=" * 70)
    print("  LEGACY PLAYLIST SNAPSHOT -> GIT MIGRATION UTILITY")
    print("=" * 70)
    print(f"Target Base Path  : {base_path}")
    print(f"Grouping Strategy : '{group_by.upper()}' (Window: {window_minutes}m)" if group_by == 'session' else f"'{group_by.upper()}'")
    print(f"Dry Run Mode      : {'YES (No files modified, no commits)' if dry_run else 'NO (Live Execution)'}")
    print(f"Cleanup Legacy    : {'YES (Old timestamped files will be removed)' if cleanup_legacy else 'NO (Preserve legacy files)'}")
    print(f"Push to Remote    : {'YES' if push else 'NO'}")
    print("=" * 70)

    # 1. Print Pre-flight Git Diagnostics
    pre_diag = get_git_diagnostics(base_path, override_author_name=author_name, override_author_email=author_email)
    print_git_diagnostics(pre_diag, "PRE-FLIGHT GIT ENVIRONMENT CHECK")

    # 2. Discover snapshots
    print("1. Discovering legacy snapshot files...")
    records, legacy_files = discover_all_snapshots(base_path)

    if not records:
        print("No snapshot files found to migrate.")
        return

    print(f"Found {len(records)} total snapshot records across all playlists.")
    print(f"Found {len(legacy_files)} legacy timestamped files eligible for cleanup.")

    # 3. Group snapshots
    groups = group_snapshots(records, mode=group_by, window_minutes=window_minutes)
    print(f"Grouped {len(records)} snapshots into {len(groups)} distinct batch sessions.\n")

    # Dry-Run Simulation
    if dry_run:
        print("--- [DRY RUN] In-Memory Chronological Playback Simulation ---")
        print("NOTE: Strictly read-only simulation. NO files are modified, NO Git commits are executed.\n")

        simulated_entries: Dict[str, List[dict]] = {}
        sim_committed = 0
        sim_skipped = 0

        for idx, group in enumerate(groups, 1):
            ts_str = group.timestamp.strftime("%Y-%m-%d %H:%M:%S")
            deltas: List[Tuple[str, str, bool]] = []
            group_has_diff = False

            for rec in group.records:
                data = _load_json_safe(rec.source_file_path)
                if not data:
                    continue

                old_entries = simulated_entries.get(rec.playlist_folder)
                delta_str, has_diff = _format_playlist_delta(
                    rec.playlist_title,
                    old_entries,
                    data,
                    rec.timestamp
                )
                deltas.append((rec.playlist_title, delta_str, has_diff))
                if has_diff:
                    group_has_diff = True

                simulated_entries[rec.playlist_folder] = data.get("entries") or []

            if not deltas:
                sim_skipped += 1
                continue

            if group_has_diff or idx == 1:
                sim_committed += 1
                commit_msg = _format_group_commit_message(group.timestamp, deltas)
                first_line = commit_msg.splitlines()[0]
                print(f"  [{idx:03d}/{len(groups):03d}] {ts_str} | {first_line}")
                if len(deltas) > 1:
                    for d in deltas:
                        print(f"         • {d[1]}")
            else:
                sim_skipped += 1
                if verbose:
                    print(f"  [{idx:03d}/{len(groups):03d}] {ts_str} | [SKIP NO DIFF] {len(deltas)} playlist(s) unchanged")

        print("\n" + "=" * 70)
        print(f"[DRY RUN SUMMARY] Would create {sim_committed} commits (grouped from {len(records)} snapshots).")
        print(f"[DRY RUN SUMMARY] {sim_skipped} identical/no-op groups skipped.")
        print(f"[DRY RUN SUMMARY] Would clean up {len(legacy_files)} legacy files if --cleanup-legacy was passed.")
        print("=" * 70)

        # Print Final Diagnostics in Dry Run
        print_git_diagnostics(pre_diag, "PROJECTED POST-MIGRATION GIT SUMMARY")
        print("[DRY RUN COMPLETE] Zero files were modified. Zero Git commands were run.\n")
        return

    # 4. Live Execution: Ensure Git repository is initialized
    print("2. Initializing / verifying Git repository in download folder...")
    if not ensure_git_repo(base_path):
        print(f"[ERROR] Failed to initialize Git repository in {base_path}")
        return

    # 5. Replay snapshot groups into Git
    print(f"3. Replaying {len(groups)} snapshot groups into Git...")

    last_entries_per_playlist: Dict[str, List[dict]] = {}
    committed_count = 0
    skipped_count = 0

    author_name = pre_diag["author_name"].replace(" (Default)", "")
    author_email = pre_diag["author_email"].replace(" (Default)", "")

    for idx, group in enumerate(groups, 1):
        ts_str = group.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        deltas: List[Tuple[str, str, bool]] = []

        # Copy each record to target canonical location and stage
        for rec in group.records:
            rel_target = os.path.relpath(rec.target_file_path, base_path).replace("\\", "/")
            data = _load_json_safe(rec.source_file_path)
            if not data:
                continue

            # Copy snapshot to canonical target playlist_info.json
            if os.path.abspath(rec.source_file_path) != os.path.abspath(rec.target_file_path):
                with open(rec.target_file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

            # Stage file
            add_code, add_out, add_err = _run_git_cmd(["add", rel_target], cwd=base_path)
            if add_code != 0:
                print(f"  [ERROR] Failed to git add {rel_target}: {add_err or add_out}")
                continue

            old_entries = last_entries_per_playlist.get(rec.playlist_folder)
            delta_str, has_diff = _format_playlist_delta(
                rec.playlist_title,
                old_entries,
                data,
                rec.timestamp
            )
            deltas.append((rec.playlist_title, delta_str, has_diff))
            last_entries_per_playlist[rec.playlist_folder] = data.get("entries") or []

        if not deltas:
            skipped_count += 1
            continue

        # Check if git diff exists in staged changes
        diff_code, _, _ = _run_git_cmd(["diff", "--cached", "--quiet"], cwd=base_path)
        if diff_code == 0:
            if verbose:
                print(f"  [{idx:03d}/{len(groups):03d}] {ts_str} No changes across {len(deltas)} playlists, skipping commit.")
            skipped_count += 1
            continue

        # Format commit message
        commit_msg = _format_group_commit_message(group.timestamp, deltas)

        # Historical commit environment
        commit_env = {
            "GIT_AUTHOR_DATE": ts_str,
            "GIT_COMMITTER_DATE": ts_str,
            "GIT_AUTHOR_NAME": author_name,
            "GIT_AUTHOR_EMAIL": author_email,
            "GIT_COMMITTER_NAME": author_name,
            "GIT_COMMITTER_EMAIL": author_email,
        }

        c_code, c_out, c_err = _run_git_cmd(
            ["commit", "-m", commit_msg, f"--date={ts_str}"],
            cwd=base_path,
            env_vars=commit_env
        )

        if c_code == 0:
            committed_count += 1
            first_line = commit_msg.splitlines()[0]
            print(f"  [{idx:03d}/{len(groups):03d}] {ts_str} -> {first_line}")
            if len(deltas) > 1 and verbose:
                for d in deltas:
                    print(f"         • {d[1]}")
        else:
            print(f"  [WARN] Failed to commit: {c_err or c_out}")

    print("\n" + "=" * 70)
    print(f"Migration Replay Summary: {committed_count} grouped commits created, {skipped_count} unchanged groups skipped.")
    print("=" * 70 + "\n")

    # 6. Ensure latest playlist_info.json files remain active on disk
    print("4. Verifying latest playlist_info.json files are active...")
    for rec in records:
        if rec.is_latest and os.path.exists(rec.source_file_path):
            if os.path.abspath(rec.source_file_path) != os.path.abspath(rec.target_file_path):
                shutil.copy2(rec.source_file_path, rec.target_file_path)

    # 7. Optional Legacy File Cleanup
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

    # 8. Optional Remote Push
    if push:
        print("\n6. Pushing migration commits to configured remote repository...")
        push_success, push_msg = push_to_remote_sync()
        if push_success:
            print(f"  [SUCCESS] {push_msg}")
        else:
            print(f"  [WARN] Remote push result: {push_msg}")

    # 9. Print Post-Flight Git Diagnostics
    post_diag = get_git_diagnostics(base_path)
    print_git_diagnostics(post_diag, "FINAL POST-MIGRATION REPOSITORY STATUS")
    print("[DONE] Historical Git snapshot migration finished successfully!\n")


def main():
    parser = argparse.ArgumentParser(
        description="Migrate historical playlist_info_*.json snapshots into Git version control."
    )
    parser.add_argument(
        "--base-path",
        type=str,
        default="",
        help="Root download directory containing playlists (defaults to settings.BASE_DOWNLOAD_PATH or /downloads)"
    )
    parser.add_argument(
        "--group-by",
        type=str,
        choices=["session", "day", "none"],
        default="session",
        help="Strategy to group snapshots into commits: 'session' (default, sliding time window), 'day' (calendar day), or 'none' (1 commit per file)"
    )
    parser.add_argument(
        "--window-minutes",
        type=int,
        default=15,
        help="Maximum gap in minutes between consecutive playlist snapshots to consider them part of the same scan session (default: 15)"
    )
    parser.add_argument(
        "--author-name",
        type=str,
        default="",
        help="Git committer/author name (defaults to settings.GIT_USER_NAME or Blank1611)"
    )
    parser.add_argument(
        "--author-email",
        type=str,
        default="",
        help="Git committer/author email (defaults to settings.GIT_USER_EMAIL or nikhilpatil.patil0@gmail.com)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate and print the grouped timeline without making file changes or Git commits"
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

    target_base_path = args.base_path or getattr(settings, "BASE_DOWNLOAD_PATH", "/downloads")
    if not target_base_path:
        target_base_path = "/downloads"

    run_migration(
        base_path=target_base_path,
        group_by=args.group_by,
        window_minutes=args.window_minutes,
        author_name=args.author_name or None,
        author_email=args.author_email or None,
        dry_run=args.dry_run,
        cleanup_legacy=args.cleanup_legacy,
        push=args.push,
        verbose=args.verbose
    )


if __name__ == "__main__":
    main()
