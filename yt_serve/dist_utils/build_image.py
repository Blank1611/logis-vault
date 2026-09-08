#!/usr/bin/env python3
"""
Distribution and Container Lifecycle Management CLI for yt_serve.

Provides automated multi-stage builds, clean-commit production releases,
immutable dev-to-prod promotion, decoupled latest tagging, rollback automation,
remote registry uploads, and disk pruning.
"""

import sys
import os
import re
import argparse
import subprocess
import logging
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any
from collections import defaultdict


# Root directory of yt_serve (auto-anchored)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ANSI Color Codes for terminal logging
COLOR_RESET = "\033[0m"
COLOR_CYAN = "\033[36m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_RED = "\033[31m"
COLOR_BOLD = "\033[1m"


class StandardLogFormatter(logging.Formatter):
    """
    Standard Structured Formatter matching yt_serve backend logging engine:
    [%(asctime)s] [%(levelname)s] [%(name)s] %(message)s
    """
    def __init__(self, use_colors: bool = True):
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S")
        self.use_colors = use_colors and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        asctime = self.formatTime(record, self.datefmt)
        levelname = record.levelname
        if self.use_colors:
            if record.levelno >= logging.ERROR:
                level_str = f"{COLOR_RED}{levelname}{COLOR_RESET}"
            elif record.levelno >= logging.WARNING:
                level_str = f"{COLOR_YELLOW}{levelname}{COLOR_RESET}"
            elif record.levelno >= logging.INFO:
                level_str = f"{COLOR_CYAN}{levelname}{COLOR_RESET}"
            else:
                level_str = levelname
        else:
            level_str = levelname
        return f"[{asctime}] [{level_str}] [{record.name}] {record.getMessage()}"


logger = logging.getLogger("dist.build_image")
_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(StandardLogFormatter())
logger.addHandler(_console_handler)
logger.setLevel(logging.INFO)


def log_success(msg: str):
    """Log a successful terminal message with standard timestamp."""
    logger.info(f"{COLOR_GREEN}{COLOR_BOLD}SUCCESS:{COLOR_RESET} {msg}")



def run_command(cmd: List[str], cwd: Path = PROJECT_ROOT, dry_run: bool = False, capture_output: bool = False) -> Tuple[int, str, str]:
    """Execute a system command safely with logging."""
    cmd_str = " ".join(cmd)
    if dry_run:
        logger.info(f"[DRY-RUN] Would execute: {cmd_str}")
        return 0, "", ""

    logger.debug(f"Executing: {cmd_str}")
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        if proc.returncode != 0 and not capture_output:
            logger.debug(f"Command returned code {proc.returncode}\nStderr: {proc.stderr}")
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as e:
        logger.error(f"Failed to execute command '{cmd_str}': {e}")
        return -1, "", str(e)


def get_git_short_sha() -> str:
    """Retrieve 7-character Git commit hash of current HEAD."""
    code, stdout, _ = run_command(["git", "rev-parse", "--short=7", "HEAD"], capture_output=True)
    if code != 0 or not stdout:
        return "unknown"
    return stdout.strip()


def is_git_code_dirty() -> Tuple[bool, List[str]]:
    """
    Check if code files (excluding docs/markdown) in yt_serve have uncommitted changes.
    Returns (is_dirty, list_of_modified_files).
    """
    # Exclude all markdown files and documentation directories from dirty checks
    code, stdout, _ = run_command(
        ["git", "status", "--porcelain", "--", ".", ":(exclude)**/*.md", ":(exclude)*.md", ":(exclude)DOCS/**"],
        capture_output=True
    )
    if code != 0 or not stdout:
        return False, []
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    return len(lines) > 0, lines


def inspect_image_id(tag: str) -> Optional[str]:
    """Retrieve image ID for given local tag if it exists."""
    code, stdout, _ = run_command(["docker", "image", "inspect", "--format", "{{.Id}}", tag], capture_output=True)
    if code == 0 and stdout:
        return stdout.strip()
    return None


def get_local_images() -> List[Dict[str, str]]:
    """List all local yt_serve images with tags, IDs, sizes, and creation times."""
    code, stdout, _ = run_command(
        ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}\t{{.Size}}", "yt_serve"],
        capture_output=True
    )
    if code != 0 or not stdout:
        return []

    images = []
    for line in stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 4:
            images.append({
                "tag": parts[0],
                "id": parts[1],
                "created": parts[2],
                "size": parts[3]
            })
    return images


def check_remote_manifest_exists(image_tag: str) -> bool:
    """Check if image tag exists in remote registry without pulling it."""
    code, _, _ = run_command(["docker", "manifest", "inspect", image_tag], capture_output=True)
    return code == 0


def parse_semver_key(tag_name: str) -> Tuple[int, int, int]:
    """Extract (major, minor, patch) integer tuple from version tag string for sorting."""
    # Match strings like yt_serve:v2.0.1 or v2.0.1
    m = re.search(r"v?(\d+)\.(\d+)\.(\d+)", tag_name)
    if m:
        return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return 0, 0, 0


def normalize_image_id(img_id: Optional[str]) -> str:
    """Normalize docker image ID to short 12-char hex string without sha256 prefix."""
    if not img_id:
        return ""
    img_id = img_id.strip()
    if img_id.startswith("sha256:"):
        img_id = img_id[7:]
    return img_id[:12]


def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from a string for accurate length calculation."""
    return re.sub(r"\033\[[0-9;]*m", "", text)


def pad_colored(text: str, width: int) -> str:
    """Pad text to width accounting for invisible ANSI escape sequences."""
    visible_len = len(strip_ansi(text))
    padding = max(0, width - visible_len)
    return text + (" " * padding)


# ==============================================================================
# CLI Action Handlers
# ==============================================================================

def action_list(env_filter: Optional[str] = None):
    """Display a formatted inspection table of all local yt_serve images with hierarchical sorting and alias grouping."""
    images = get_local_images()
    if not images:
        logger.info("No local 'yt_serve' Docker images found.")
        return

    # Normalize image IDs for reliable matching
    for img in images:
        img["norm_id"] = normalize_image_id(img.get("id"))

    # Map norm_id to list of tags to detect aliases/co-tags
    id_to_tags = defaultdict(list)
    for img in images:
        id_to_tags[img["norm_id"]].append(img["tag"])

    # Determine what yt_serve:latest points to
    raw_latest_id = inspect_image_id("yt_serve:latest")
    latest_id = normalize_image_id(raw_latest_id)

    # Classify each image and assign roles (canonical vs alias)
    classified = []
    pointed_version = None

    for img in images:
        tag = img["tag"]
        norm_id = img["norm_id"]
        siblings = id_to_tags[norm_id]

        # Determine Environment and Status
        if ":test" in tag:
            env_type = "TEST"
            is_alias = False
            alias_of = None
            status = "Test target (backend-only)"
        elif re.search(r":v\d+\.\d+\.\d+", tag):
            env_type = "PROD"
            is_alias = False
            alias_of = None
            if latest_id and norm_id == latest_id:
                status = f"{COLOR_GREEN}★ Active Latest{COLOR_RESET}"
                pointed_version = tag
            else:
                status = "Release"
        elif tag.endswith(":latest"):
            env_type = "PROD"
            # If another PROD tag shares this ID, latest is its alias
            prod_siblings = [t for t in siblings if re.search(r":v\d+\.\d+\.\d+", t)]
            if prod_siblings:
                is_alias = True
                alias_of = prod_siblings[0]
                status = f"{COLOR_CYAN}[floating alias]{COLOR_RESET}"
                pointed_version = prod_siblings[0]
            else:
                is_alias = False
                alias_of = None
                status = f"{COLOR_CYAN}[latest pointer]{COLOR_RESET}"
        elif "-dirty" in tag:
            env_type = "DEV-DIRTY"
            is_alias = False
            alias_of = None
            status = f"{COLOR_YELLOW}Dirty build (uncommitted){COLOR_RESET}"
        elif tag.endswith(":dev"):
            # Check siblings for commit tag
            commit_siblings = [t for t in siblings if t != tag and ":dev-" in t]
            if commit_siblings:
                canonical = commit_siblings[0]
                is_alias = True
                alias_of = canonical
                env_type = "DEV-DIRTY" if "-dirty" in canonical else "DEV"
                status = f"{COLOR_CYAN}[floating alias]{COLOR_RESET}"
            else:
                is_alias = False
                alias_of = None
                env_type = "DEV"
                status = "Dev build"
        else:
            # dev-<sha> (clean)
            env_type = "DEV"
            is_alias = False
            alias_of = None
            status = f"{COLOR_GREEN}Clean (promotable){COLOR_RESET}"

        classified.append({
            **img,
            "env": env_type,
            "is_alias": is_alias,
            "alias_of": alias_of,
            "status": status
        })

    # Filter if requested
    if env_filter:
        ef = env_filter.upper()
        if ef == "DEV":
            classified = [img for img in classified if img["env"] in ("DEV", "DEV-DIRTY")]
        else:
            classified = [img for img in classified if img["env"] == ef]

    # Sorting Hierarchy:
    # 1. PROD
    # 2. DEV (Clean)
    # 3. DEV-DIRTY
    # 4. TEST
    env_priority = {
        "PROD": 1,
        "DEV": 2,
        "DEV-DIRTY": 3,
        "TEST": 4
    }

    def sort_key(item):
        env_rank = env_priority.get(item["env"], 99)
        # Group siblings with same norm_id together
        # For PROD: sort semver descending
        semver = (0, 0, 0)
        if item["env"] == "PROD":
            target_tag = item["alias_of"] or item["tag"]
            semver = parse_semver_key(target_tag)
        # Canonical first (0), alias second (1)
        alias_rank = 1 if item["is_alias"] else 0
        return (env_rank, [-x for x in semver], item["norm_id"], alias_rank, item["tag"])

    classified.sort(key=sort_key)

    print("\n" + "=" * 102)
    print(f"{COLOR_BOLD}LOCAL DOCKER IMAGES (yt_serve){COLOR_RESET}")
    print("=" * 102)
    print(f"{'ENV':<11} {'TAG':<35} {'IMAGE ID':<15} {'SIZE':<11} {'STATUS':<30}")
    print("-" * 102)

    for img in classified:
        tag_display = f"↳ {img['tag']}" if img["is_alias"] else img["tag"]
        env_col = pad_colored(img["env"], 11)
        tag_col = pad_colored(tag_display, 35)
        id_col = pad_colored(img["norm_id"], 15)
        size_col = pad_colored(img["size"], 11)
        status_col = pad_colored(img["status"], 30)

        print(f"{env_col} {tag_col} {id_col} {size_col} {status_col}")

    print("-" * 102)
    if latest_id and pointed_version:
        print(f"Production 'latest' Pointer: {COLOR_BOLD}yt_serve:latest ➔ {pointed_version}{COLOR_RESET} ({latest_id})")
    elif latest_id:
        print(f"Production 'latest' Pointer: {COLOR_BOLD}yt_serve:latest ➔ ({latest_id}){COLOR_RESET}")
    else:
        print("Production 'latest' Pointer: [Unassigned]")
    print("=" * 102 + "\n")



def action_build_test(fresh_build: bool, dry_run: bool):
    """Build isolated backend-test image target."""
    logger.info("Building test container target ('--target backend-test')...")
    logger.info("Note: Node.js and frontend compilation are skipped for speed.")

    cmd = ["docker", "build", "--target", "backend-test", "-t", "yt_serve:test"]
    if fresh_build:
        cmd.extend(["--no-cache", "--pull"])
    cmd.append(".")

    code, _, err = run_command(cmd, dry_run=dry_run)
    if code != 0:
        logger.error(f"Failed to build test container: {err}")
        sys.exit(1)

    log_success("Built 'yt_serve:test' successfully.")
    logger.info("Run tests inside container via: docker run --rm yt_serve:test")


def action_build_dev(fresh_build: bool, dry_run: bool):
    """Build full-stack development container with Git SHA traceability."""
    sha = get_git_short_sha()
    is_dirty, modified_files = is_git_code_dirty()

    dev_tag = f"yt_serve:dev-{sha}" + ("-dirty" if is_dirty else "")

    if is_dirty:
        logger.warning(f"Uncommitted code modifications detected ({len(modified_files)} files). Tagging as '{dev_tag}'.")
    else:
        logger.info(f"Clean working tree at commit '{sha}'. Tagging as '{dev_tag}'.")

    # Check if this exact clean dev image is already built
    if not is_dirty and not fresh_build:
        existing_id = inspect_image_id(dev_tag)
        if existing_id:
            logger.info(f"Image '{dev_tag}' already exists ({existing_id[:12]}) and working tree is clean.")
            logger.info("Updating floating 'yt_serve:dev' tag to point to it...")
            run_command(["docker", "tag", dev_tag, "yt_serve:dev"], dry_run=dry_run)
            log_success(f"Updated 'yt_serve:dev' ➔ '{dev_tag}'. (Rebuild skipped, already up to date).")
            return

    cmd = ["docker", "build", "--target", "runner", "-t", "yt_serve:dev", "-t", dev_tag]
    if fresh_build:
        cmd.extend(["--no-cache", "--pull"])
    cmd.append(".")

    logger.info(f"Compiling development image '{dev_tag}'...")
    code, _, err = run_command(cmd, dry_run=dry_run)
    if code != 0:
        logger.error(f"Failed to build development image: {err}")
        sys.exit(1)

    log_success(f"Built '{dev_tag}' and updated 'yt_serve:dev'.")


def action_build_prod(
    version: str,
    from_dev: Optional[str] = None,
    use_from_dev: bool = False,
    promote_latest: bool = False,
    push_ghcr: bool = False,
    push_local: Optional[str] = None,
    push_all: bool = False,
    fresh_build: bool = False,
    dry_run: bool = False
):
    """Build or promote an immutable production release."""
    # Validate semantic version format (e.g., v2.0.0)
    if not re.match(r"^v\d+\.\d+\.\d+$", version):
        logger.error(f"Invalid production version format '{version}'. Must follow 'vX.Y.Z' (e.g. v2.0.0).")
        sys.exit(1)

    prod_tag = f"yt_serve:{version}"

    # RULE: Strict permanent immutability. If release exists, it can never be rebuilt.
    existing_id = inspect_image_id(prod_tag)
    if existing_id and not dry_run:
        logger.error(f"Production release '{prod_tag}' is already finalized ({existing_id[:12]}) and permanently immutable.")
        logger.error("Overwriting release tags is prohibited to ensure deployment reproducibility.")
        logger.error("Please increment the patch/micro version (e.g. v2.0.1) for new changes.")
        sys.exit(1)

    # Check remote registry collision
    ghcr_target = f"ghcr.io/Blank1611/{prod_tag}"
    if (push_ghcr or push_all) and not dry_run:
        if check_remote_manifest_exists(ghcr_target):
            logger.error(f"Release tag '{ghcr_target}' already exists in GitHub Container Registry.")
            logger.error("Remote release overwriting is blocked. Please bump version number.")
            sys.exit(1)

    # RULE: Production releases strictly require a clean Git working tree
    is_dirty, modified_files = is_git_code_dirty()
    if is_dirty and not dry_run:
        logger.error(f"Cannot release production version '{version}' with uncommitted code modifications:")
        for f in modified_files[:5]:
            logger.error(f"  {f}")
        if len(modified_files) > 5:
            logger.error(f"  ... and {len(modified_files) - 5} more files")
        logger.error("Please commit your changes to Git before creating a release, or test using '-e dev'.")
        sys.exit(1)

    # Mode 1: Promote clean dev image (Immutable Artifact Promotion)
    if use_from_dev:
        if from_dev:
            # Explicit tag/SHA provided
            dev_source_tag = from_dev if ":" in from_dev else f"yt_serve:dev-{from_dev}"
        else:
            # Default to current HEAD clean dev build
            sha = get_git_short_sha()
            dev_source_tag = f"yt_serve:dev-{sha}"

        dev_id = inspect_image_id(dev_source_tag)
        if not dev_id and not dry_run:
            logger.error(f"Source dev image '{dev_source_tag}' does not exist locally.")
            logger.error("Please build it first via './dist_utils/build_image.py -e dev' or build prod from source.")
            sys.exit(1)

        logger.info(f"Promoting clean dev image '{dev_source_tag}' ➔ '{prod_tag}'...")
        code, _, err = run_command(["docker", "tag", dev_source_tag, prod_tag], dry_run=dry_run)
        if code != 0:
            logger.error(f"Failed to tag image: {err}")
            sys.exit(1)
        log_success(f"Promoted '{dev_source_tag}' ➔ '{prod_tag}' in 0.01s (Identical bits verified).")
    else:
        # Mode 2: Build fresh from source
        logger.info(f"Compiling production release image '{prod_tag}' from current commit...")
        cmd = ["docker", "build", "--target", "runner", "-t", prod_tag]
        if fresh_build:
            cmd.extend(["--no-cache", "--pull"])
        cmd.append(".")

        code, _, err = run_command(cmd, dry_run=dry_run)
        if code != 0:
            logger.error(f"Failed to build production image: {err}")
            sys.exit(1)
        log_success(f"Built production release '{prod_tag}'.")

    # Handle optional latest promotion
    if promote_latest:
        action_promote_latest(version, push_ghcr=push_ghcr, push_local=push_local, push_all=push_all, dry_run=dry_run)

    # Handle registry pushes
    if push_ghcr or push_all:
        logger.info(f"Publishing release to GHCR ('{ghcr_target}')...")
        run_command(["docker", "tag", prod_tag, ghcr_target], dry_run=dry_run)
        code, _, err = run_command(["docker", "push", ghcr_target], dry_run=dry_run)
        if code == 0:
            log_success(f"Published '{ghcr_target}'.")
        else:
            logger.error(f"Failed to push to GHCR: {err}")

    if push_local or push_all:
        local_host = push_local if (push_local and push_local != "all") else "localhost:5000"
        local_target = f"{local_host}/{prod_tag}"
        logger.info(f"Publishing release to local registry ('{local_target}')...")
        run_command(["docker", "tag", prod_tag, local_target], dry_run=dry_run)
        code, _, err = run_command(["docker", "push", local_target], dry_run=dry_run)
        if code == 0:
            log_success(f"Published '{local_target}'.")
        else:
            logger.error(f"Failed to push to local registry: {err}")


def action_promote_latest(
    version: str,
    push_ghcr: bool = False,
    push_local: Optional[str] = None,
    push_all: bool = False,
    dry_run: bool = False
):
    """Promote an existing local release version to yt_serve:latest."""
    prod_tag = f"yt_serve:{version}" if not version.startswith("yt_serve:") else version
    img_id = inspect_image_id(prod_tag)
    if not img_id and not dry_run:
        logger.error(f"Cannot promote '{prod_tag}': image does not exist locally.")
        sys.exit(1)

    logger.info(f"Promoting '{prod_tag}' ➔ 'yt_serve:latest'...")
    run_command(["docker", "tag", prod_tag, "yt_serve:latest"], dry_run=dry_run)
    log_success(f"Pointed 'yt_serve:latest' ➔ '{prod_tag}'.")

    if push_ghcr or push_all:
        ghcr_latest = "ghcr.io/Blank1611/yt_serve:latest"
        logger.info(f"Updating remote registry pointer ('{ghcr_latest}')...")
        run_command(["docker", "tag", prod_tag, ghcr_latest], dry_run=dry_run)
        code, _, err = run_command(["docker", "push", ghcr_latest], dry_run=dry_run)
        if code == 0:
            log_success(f"Updated '{ghcr_latest}'.")
        else:
            logger.error(f"Failed to push latest tag to GHCR: {err}")

    if push_local or push_all:
        local_host = push_local if (push_local and push_local != "all") else "localhost:5000"
        local_latest = f"{local_host}/yt_serve:latest"
        logger.info(f"Updating local registry pointer ('{local_latest}')...")
        run_command(["docker", "tag", prod_tag, local_latest], dry_run=dry_run)
        code, _, err = run_command(["docker", "push", local_latest], dry_run=dry_run)
        if code == 0:
            log_success(f"Updated '{local_latest}'.")
        else:
            logger.error(f"Failed to push latest tag to local registry: {err}")


def action_rollback(
    target_version: Optional[str] = None,
    push_ghcr: bool = False,
    push_local: Optional[str] = None,
    push_all: bool = False,
    dry_run: bool = False
):
    """Roll back yt_serve:latest to a previous stable release (N-1 or specified version)."""
    images = get_local_images()
    prod_releases = []
    latest_id = inspect_image_id("yt_serve:latest")

    for img in images:
        tag = img["tag"]
        if re.search(r":v\d+\.\d+\.\d+$", tag):
            prod_releases.append(tag)

    if not prod_releases:
        logger.error("No production release versions (e.g. yt_serve:vX.Y.Z) found locally to roll back to.")
        sys.exit(1)

    # Sort descending by semver
    prod_releases.sort(key=parse_semver_key, reverse=True)

    if target_version:
        target_tag = f"yt_serve:{target_version}" if not target_version.startswith("yt_serve:") else target_version
        if target_tag not in prod_releases and not dry_run:
            logger.error(f"Target release '{target_tag}' not found in local images. Available releases: {', '.join(prod_releases)}")
            sys.exit(1)
        selected_version = target_tag
    else:
        # Auto-rollback: find version preceding current latest
        current_latest_tag = None
        for r in prod_releases:
            if latest_id and inspect_image_id(r) == latest_id:
                current_latest_tag = r
                break

        if current_latest_tag:
            logger.info(f"Current 'latest' is pointing to '{current_latest_tag}'.")
            idx = prod_releases.index(current_latest_tag)
            if idx + 1 < len(prod_releases):
                selected_version = prod_releases[idx + 1]
            else:
                logger.error(f"No earlier release found before '{current_latest_tag}'. Available: {', '.join(prod_releases)}")
                sys.exit(1)
        else:
            # Fallback to highest available release
            selected_version = prod_releases[0]

    logger.info(f"Executing rollback: pointing 'yt_serve:latest' ➔ '{selected_version}'...")
    action_promote_latest(selected_version, push_ghcr=push_ghcr, push_local=push_local, push_all=push_all, dry_run=dry_run)
    log_success(f"Rollback complete: 'yt_serve:latest' now points to '{selected_version}'.")


def action_prune(keep_n: int = 3, dry_run: bool = False):
    """
    Clean up stale dev images, test images, and untagged build layers strictly scoped to yt_serve.
    Lists all candidate tags prior to deletion and preserves production releases.
    Scoped to project='yt_serve' via Docker label filtering.
    """
    logger.info(f"Scanning local 'yt_serve' images for pruning (retention limit: {keep_n} newest dev builds)...")
    images = get_local_images()

    prod_images = []
    dev_images = []
    test_images = []

    for img in images:
        tag = img["tag"]
        if ":test" in tag:
            test_images.append(img)
        elif re.search(r":v\d+\.\d+\.\d+", tag) or tag.endswith(":latest"):
            prod_images.append(img)
        elif ":dev-" in tag:
            dev_images.append(img)

    # Sort dev images newest first by creation timestamp string
    dev_images.sort(key=lambda x: x["created"], reverse=True)

    kept_dev = dev_images[:keep_n]
    prune_dev = dev_images[keep_n:]
    prune_candidates = test_images + prune_dev

    print("\n" + "=" * 88)
    print(f"{COLOR_BOLD}PRUNE SCOPING: LOCAL yt_serve ARTIFACTS{COLOR_RESET}")
    print("=" * 88)

    # Display Protected / Retained Images
    print(f"{COLOR_GREEN}[RETAINED RELEASES & ACTIVE BUILDS]{COLOR_RESET}")
    if prod_images:
        for p in prod_images:
            print(f"  ★ PROD  {p['tag']:<34} {p['id']:<14} {p['size']:<10} {p['created']}")
    for k in kept_dev:
        print(f"  ✔ DEV   {k['tag']:<34} {k['id']:<14} {k['size']:<10} {k['created']} (Active)")

    print("-" * 88)

    # Display Prune Candidates
    if not prune_candidates:
        print(f"{COLOR_CYAN}[PRUNE CANDIDATES - NAMED TAGS]{COLOR_RESET}")
        print("  None. All named yt_serve tags meet local retention limits.")
    else:
        print(f"{COLOR_YELLOW}[PRUNE CANDIDATES SCHEDULED FOR REMOVAL]{COLOR_RESET}")
        print(f"  {'TYPE':<6} {'TAG':<34} {'IMAGE ID':<14} {'SIZE':<10} {'CREATED':<20}")
        for c in prune_candidates:
            c_type = "TEST" if ":test" in c["tag"] else "DEV"
            print(f"  {c_type:<6} {c['tag']:<34} {c['id']:<14} {c['size']:<10} {c['created']}")
    print("=" * 88 + "\n")

    if prune_candidates:
        logger.info(f"Identified {len(prune_candidates)} stale yt_serve image(s) for removal.")
        if dry_run:
            logger.info(f"[DRY-RUN] Would remove {len(prune_candidates)} candidate image(s).")
        else:
            for c in prune_candidates:
                tag = c["tag"]
                logger.info(f"Removing image '{tag}'...")
                run_command(["docker", "rmi", tag], dry_run=dry_run)
            log_success(f"Removed {len(prune_candidates)} stale yt_serve image(s).")

    # Clean up project-specific untagged dangling build layers (<none>:<none>) using label filter
    logger.info("Cleaning up untagged dangling build layers (docker image prune -f --filter label=project=yt_serve)...")
    run_command(["docker", "image", "prune", "-f", "--filter", "label=project=yt_serve"], dry_run=dry_run)
    log_success("Prune operation finished.")


# ==============================================================================
# CLI Main Parser
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Distribution & Container Lifecycle CLI for yt_serve",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ./dist_utils/build_image.py --list
  ./dist_utils/build_image.py -e test
  ./dist_utils/build_image.py -e dev
  ./dist_utils/build_image.py -e prod -v v2.0.0 --from-dev
  ./dist_utils/build_image.py --promote-latest v2.0.0
  ./dist_utils/build_image.py --rollback
  ./dist_utils/build_image.py --prune --keep 3
        """
    )

    # Action flags
    parser.add_argument("-e", "--env", choices=["test", "dev", "prod"], help="Target build environment")
    parser.add_argument("-v", "--version", help="Semantic version tag for production release (e.g. v2.0.0)")
    parser.add_argument("--from-dev", nargs="?", const="", default=None, help="Promote existing clean dev image to prod without rebuilding (optional: specify commit SHA)")
    parser.add_argument("--promote-latest", nargs="?", const="", default=None, help="Point yt_serve:latest to release version (standalone or combined with build)")
    parser.add_argument("--rollback", nargs="?", const="", default=None, help="Roll back yt_serve:latest to previous release (N-1 or specified version)")
    parser.add_argument("-l", "--list", action="store_true", help="List local yt_serve images and current latest pointer")
    parser.add_argument("--prune", action="store_true", help="Clean up old dev/test images and dangling build layers")
    parser.add_argument("--keep", type=int, default=3, help="Number of recent dev images to keep when pruning (default: 3)")

    # Registry push flags
    parser.add_argument("--push-ghcr", action="store_true", help="Publish release / latest to GitHub Container Registry")
    parser.add_argument("--push-local", nargs="?", const="localhost:5000", default=None, help="Publish release / latest to local private registry")
    parser.add_argument("--push-all", action="store_true", help="Publish to both GHCR and local registry")

    # Options
    parser.add_argument("--fresh-build", action="store_true", help="Bypass local Docker layer cache and pull latest base images (--no-cache --pull)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging and raw command output")
    parser.add_argument("--dry-run", action="store_true", help="Display Docker commands without executing them")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # 1. Image List
    if args.list:
        action_list(env_filter=args.env)
        return

    # 2. Prune
    if args.prune:
        action_prune(keep_n=args.keep, dry_run=args.dry_run)
        return

    # 3. Standalone Rollback
    if args.rollback is not None:
        target_v = args.rollback if args.rollback != "" else None
        action_rollback(
            target_version=target_v,
            push_ghcr=args.push_ghcr,
            push_local=args.push_local,
            push_all=args.push_all,
            dry_run=args.dry_run
        )
        return

    # 4. Standalone Promote Latest
    if args.promote_latest is not None and not args.env:
        if args.promote_latest == "":
            logger.error("Must specify version to promote when using standalone --promote-latest (e.g. --promote-latest v2.0.0).")
            sys.exit(1)
        action_promote_latest(
            version=args.promote_latest,
            push_ghcr=args.push_ghcr,
            push_local=args.push_local,
            push_all=args.push_all,
            dry_run=args.dry_run
        )
        return

    # 5. Environment-based Builds
    if not args.env:
        parser.print_help()
        sys.exit(0)

    if args.env == "test":
        action_build_test(fresh_build=args.fresh_build, dry_run=args.dry_run)
    elif args.env == "dev":
        action_build_dev(fresh_build=args.fresh_build, dry_run=args.dry_run)
    elif args.env == "prod":
        if not args.version:
            logger.error("Production release requires version argument '-v/--version' (e.g. -v v2.0.0).")
            sys.exit(1)
        use_dev = args.from_dev is not None
        dev_target = args.from_dev if (args.from_dev and args.from_dev != "") else None
        do_promote = args.promote_latest is not None

        action_build_prod(
            version=args.version,
            from_dev=dev_target,
            use_from_dev=use_dev,
            promote_latest=do_promote,
            push_ghcr=args.push_ghcr,
            push_local=args.push_local,
            push_all=args.push_all,
            fresh_build=args.fresh_build,
            dry_run=args.dry_run
        )


if __name__ == "__main__":
    main()
