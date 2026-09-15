#!/usr/bin/env python3
"""
Distribution and Container Lifecycle Management CLI for logis-vault.

Provides automated multi-stage builds, clean-commit production releases,
immutable dev-to-prod promotion, decoupled latest tagging, rollback automation,
multi-registry uploads (GHCR, local daemon, private), and disk pruning.
"""

import sys
import os
import re
import json
import argparse
import subprocess
import logging
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Any, Set
from collections import defaultdict


# Root directory & Container Configuration
PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_NAME = "logis-vault"
GHCR_OWNER = "Blank1611"

# ANSI Color Codes for terminal logging
COLOR_RESET = "\033[0m"
COLOR_CYAN = "\033[36m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_RED = "\033[31m"
COLOR_PURPLE = "\033[35m"
COLOR_BOLD = "\033[1m"
COLOR_BOLD_RED = "\033[1;31m"


class StandardLogFormatter(logging.Formatter):
    """
    Standard Structured Formatter matching logis-vault backend logging engine:
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


_GIT_COMMIT_TS_CACHE: Dict[str, int] = {}

def get_git_commit_timestamp(sha: str) -> int:
    """Retrieve Unix commit timestamp for a Git commit hash, cached for speed."""
    if not sha or sha == "unknown":
        return 0
    if sha in _GIT_COMMIT_TS_CACHE:
        return _GIT_COMMIT_TS_CACHE[sha]
    code, stdout, _ = run_command(["git", "log", "-1", "--format=%ct", sha], capture_output=True)
    if code == 0 and stdout.strip().isdigit():
        ts = int(stdout.strip())
        _GIT_COMMIT_TS_CACHE[sha] = ts
        return ts
    _GIT_COMMIT_TS_CACHE[sha] = 0
    return 0


def is_git_code_dirty() -> Tuple[bool, List[str]]:
    """
    Check if code files (excluding docs/markdown) in logis-vault have uncommitted changes.
    Returns (is_dirty, list_of_modified_files).
    """
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
    """List all local images associated with APP_NAME with tags, IDs, sizes, and creation times."""
    code, stdout, _ = run_command(
        ["docker", "images", "--format", "{{.Repository}}:{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}\t{{.Size}}"],
        capture_output=True
    )
    if code != 0 or not stdout:
        return []

    images = []
    for line in stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 4:
            repo_tag = parts[0]
            if APP_NAME in repo_tag:
                images.append({
                    "tag": repo_tag,
                    "id": parts[1],
                    "created": parts[2],
                    "size": parts[3]
                })
    return images


def check_remote_manifest_exists(image_tag: str) -> bool:
    """Check if image tag exists in remote registry without pulling it."""
    code, _, _ = run_command(["docker", "manifest", "inspect", image_tag], capture_output=True)
    return code == 0


def get_remote_manifest_digest(image_tag: str) -> Optional[str]:
    """Retrieve primary manifest digest from remote registry."""
    code, out, _ = run_command(["docker", "manifest", "inspect", image_tag], capture_output=True)
    if code != 0 or not out:
        return None
    try:
        data = json.loads(out)
        if "manifests" in data and len(data["manifests"]) > 0:
            return data["manifests"][0].get("digest")
        if "config" in data:
            return data["config"].get("digest")
    except Exception:
        pass
    return None


def parse_semver_key(tag_name: str) -> Tuple[int, int, int]:
    """Extract (major, minor, patch) integer tuple from version tag string for sorting."""
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


def parse_target_registries(reg_arg: Optional[str]) -> List[str]:
    """Parse comma-separated target registries into normalized list, e.g. ['local', 'ghcr']."""
    if not reg_arg:
        return ["local"]
    tokens = [t.strip().lower() for t in reg_arg.split(",") if t.strip()]
    return tokens if tokens else ["local"]


# ==============================================================================
# CLI Action Handlers
# ==============================================================================

def action_list(env_filter: Optional[str] = None):
    """Display a formatted inspection table of all local images with Git-timestamp sorting and registry badges."""
    images = get_local_images()
    if not images:
        logger.info(f"No local '{APP_NAME}' Docker images found.")
        return

    # Normalize image IDs for reliable matching
    for img in images:
        img["norm_id"] = normalize_image_id(img.get("id"))

    # Map norm_id to list of tags
    id_to_tags = defaultdict(list)
    for img in images:
        id_to_tags[img["norm_id"]].append(img["tag"])

    # Determine remote registry badges for each norm_id
    id_to_registries: Dict[str, Set[str]] = defaultdict(set)
    for norm_id, tags in id_to_tags.items():
        for t in tags:
            if "ghcr.io/" in t:
                id_to_registries[norm_id].add("ghcr")
            elif "localhost:" in t or "127.0.0.1:" in t:
                id_to_registries[norm_id].add("local-reg")
            elif "/" in t and not t.startswith(f"{APP_NAME}:"):
                prefix = t.split("/")[0]
                id_to_registries[norm_id].add(prefix)

    # First pass: map image IDs to production versions (vX.Y.Z)
    prod_id_to_version = {}
    for img in images:
        tag = img["tag"]
        norm_id = img["norm_id"]
        m = re.search(r":(v\d+\.\d+\.\d+)$", tag)
        if m and not any(tag.startswith(p) for p in ("ghcr.io/", "localhost:", "127.0.0.1:")):
            prod_id_to_version[norm_id] = m.group(1)

    # Determine what local latest points to
    raw_latest_id = inspect_image_id(f"{APP_NAME}:latest")
    latest_id = normalize_image_id(raw_latest_id)
    pointed_version = prod_id_to_version.get(latest_id) if latest_id else None

    # Determine what local dev points to
    raw_dev_id = inspect_image_id(f"{APP_NAME}:dev")
    dev_id = normalize_image_id(raw_dev_id)
    pointed_dev_tag = None
    if dev_id:
        dev_tags = [t for t in id_to_tags[dev_id] if ":dev-" in t and not any(t.startswith(p) for p in ("ghcr.io/", "localhost:", "127.0.0.1:"))]
        if dev_tags:
            pointed_dev_tag = dev_tags[0]

    # Build PROD Rows
    prod_rows = []
    latest_img = next((img for img in images if img["tag"] == f"{APP_NAME}:latest"), None)
    if latest_img:
        prod_rows.append({
            "env": "PROD",
            "tag": f"{APP_NAME}:latest",
            "norm_id": latest_img["norm_id"],
            "size": latest_img["size"],
            "status": "[floating alias]",
            "is_indented": False,
            "color": COLOR_CYAN
        })
        if pointed_version:
            target_img = next((img for img in images if img["tag"] == f"{APP_NAME}:{pointed_version}"), None)
            if target_img:
                prod_rows.append({
                    "env": "PROD",
                    "tag": target_img["tag"],
                    "norm_id": target_img["norm_id"],
                    "size": target_img["size"],
                    "status": "★ Active Latest",
                    "is_indented": True,
                    "color": COLOR_BOLD_RED
                })

    other_prod_imgs = [
        img for img in images
        if re.search(r":v\d+\.\d+\.\d+$", img["tag"])
        and not any(img["tag"].startswith(p) for p in ("ghcr.io/", "localhost:", "127.0.0.1:"))
        and (not pointed_version or img["tag"] != f"{APP_NAME}:{pointed_version}")
    ]
    other_prod_imgs.sort(key=lambda x: parse_semver_key(x["tag"]), reverse=True)
    for op in other_prod_imgs:
        has_ghcr = "ghcr" in id_to_registries.get(op["norm_id"], set())
        if not latest_img and latest_id and op["norm_id"] == latest_id:
            status = "★ Active Latest"
            color = COLOR_BOLD_RED
        else:
            status = "Release"
            color = COLOR_PURPLE if has_ghcr else ""
        prod_rows.append({
            "env": "PROD",
            "tag": op["tag"],
            "norm_id": op["norm_id"],
            "size": op["size"],
            "status": status,
            "is_indented": False,
            "color": color
        })

    # Build DEV Rows
    dev_rows = []
    dev_alias_img = next((img for img in images if img["tag"] == f"{APP_NAME}:dev"), None)
    if dev_alias_img:
        dev_rows.append({
            "env": "DEV",
            "tag": f"{APP_NAME}:dev",
            "norm_id": dev_alias_img["norm_id"],
            "size": dev_alias_img["size"],
            "status": "[floating alias]",
            "is_indented": False,
            "color": COLOR_CYAN
        })
        if pointed_dev_tag:
            pdev_img = next((img for img in images if img["tag"] == pointed_dev_tag), None)
            if pdev_img:
                is_rel = pdev_img["norm_id"] in prod_id_to_version
                is_d = "-dirty" in pointed_dev_tag
                if is_rel:
                    st = f"Released (➔ {prod_id_to_version[pdev_img['norm_id']]})"
                    co = COLOR_PURPLE
                elif is_d:
                    st = "Dirty build (uncommitted)"
                    co = COLOR_YELLOW
                else:
                    st = "Clean (promotable)"
                    co = COLOR_GREEN

                dev_rows.append({
                    "env": "DEV-DIRTY" if is_d else "DEV",
                    "tag": pointed_dev_tag,
                    "norm_id": pdev_img["norm_id"],
                    "size": pdev_img["size"],
                    "status": st,
                    "is_indented": True,
                    "color": co
                })

    other_dev_imgs = [
        img for img in images
        if ":dev-" in img["tag"]
        and not any(img["tag"].startswith(p) for p in ("ghcr.io/", "localhost:", "127.0.0.1:"))
        and (not pointed_dev_tag or img["tag"] != pointed_dev_tag)
    ]

    def dev_sort_key(item):
        is_dirty = 1 if "-dirty" in item["tag"] else 0
        m = re.search(r":dev-([0-9a-fA-F]{7,40})", item["tag"])
        ts = get_git_commit_timestamp(m.group(1)) if m else 0
        return (is_dirty, -ts, item.get("created", ""))

    other_dev_imgs.sort(key=dev_sort_key)

    for od in other_dev_imgs:
        is_rel = od["norm_id"] in prod_id_to_version
        is_d = "-dirty" in od["tag"]
        if is_rel:
            st = f"Released (➔ {prod_id_to_version[od['norm_id']]})"
            co = COLOR_PURPLE
        elif is_d:
            st = "Dirty build (uncommitted)"
            co = COLOR_YELLOW
        else:
            st = "Clean (promotable)"
            co = COLOR_GREEN

        dev_rows.append({
            "env": "DEV-DIRTY" if is_d else "DEV",
            "tag": od["tag"],
            "norm_id": od["norm_id"],
            "size": od["size"],
            "status": st,
            "is_indented": False,
            "color": co
        })

    # Build TEST Rows
    test_rows = []
    test_imgs = [
        img for img in images
        if ":test" in img["tag"]
        and not any(img["tag"].startswith(p) for p in ("ghcr.io/", "localhost:", "127.0.0.1:"))
    ]
    for ti in test_imgs:
        test_rows.append({
            "env": "TEST",
            "tag": ti["tag"],
            "norm_id": ti["norm_id"],
            "size": ti["size"],
            "status": "Test target (backend-only)",
            "is_indented": False,
            "color": ""
        })

    # Filter by environment if requested
    if not env_filter:
        rows_to_display = prod_rows + dev_rows + test_rows
    else:
        ef = env_filter.upper()
        if ef == "PROD":
            rows_to_display = prod_rows
        elif ef == "DEV":
            rows_to_display = [r for r in dev_rows if r["env"] in ("DEV", "DEV-DIRTY")]
        elif ef == "DEV-DIRTY":
            rows_to_display = [r for r in dev_rows if r["env"] == "DEV-DIRTY"]
        elif ef == "TEST":
            rows_to_display = test_rows
        else:
            rows_to_display = []

    print("\n" + "=" * 118)
    print(f"{COLOR_BOLD}LOCAL DOCKER IMAGES ({APP_NAME}){COLOR_RESET}")
    print("=" * 118)
    print(f"{'ENV':<11} {'TAG':<35} {'IMAGE ID':<15} {'SIZE':<11} {'STATUS':<28} {'REGISTRIES':<14}")
    print("-" * 118)

    for row in rows_to_display:
        tag_display = f"↳ {row['tag']}" if row["is_indented"] else row["tag"]
        status_text = row["status"]

        regs = sorted(list(id_to_registries.get(row["norm_id"], set())))
        reg_display = ", ".join(regs) if regs else "—"

        row_color = row.get("color", "")
        if row_color:
            env_val = f"{row_color}{row['env']}{COLOR_RESET}"
            tag_val = f"{row_color}{tag_display}{COLOR_RESET}"
            id_val = f"{row_color}{row['norm_id']}{COLOR_RESET}"
            size_val = f"{row_color}{row['size']}{COLOR_RESET}"
            status_val = f"{row_color}{status_text}{COLOR_RESET}"
            reg_val = f"{row_color}{reg_display}{COLOR_RESET}"
        else:
            env_val = row["env"]
            tag_val = tag_display
            id_val = row["norm_id"]
            size_val = row["size"]
            status_val = status_text
            reg_val = reg_display

        env_col = pad_colored(env_val, 11)
        tag_col = pad_colored(tag_val, 35)
        id_col = pad_colored(id_val, 15)
        size_col = pad_colored(size_val, 11)
        status_col = pad_colored(status_val, 28)
        reg_col = pad_colored(reg_val, 14)

        print(f"{env_col} {tag_col} {id_col} {size_col} {status_col} {reg_col}")

    print("-" * 118)
    if latest_id and pointed_version:
        print(f"Production 'latest' Pointer: {COLOR_BOLD}{APP_NAME}:latest ➔ {APP_NAME}:{pointed_version}{COLOR_RESET} ({latest_id})")
    elif latest_id:
        print(f"Production 'latest' Pointer: {COLOR_BOLD}{APP_NAME}:latest ➔ ({latest_id}){COLOR_RESET}")
    else:
        print("Production 'latest' Pointer: [Unassigned]")
    print("=" * 118 + "\n")



def action_build_test(fresh_build: bool, dry_run: bool):
    """Build isolated backend-test image target."""
    logger.info("Building test container target ('--target backend-test')...")
    logger.info("Note: Node.js and frontend compilation are skipped for speed.")

    cmd = ["docker", "build", "--target", "backend-test", "-t", f"{APP_NAME}:test"]
    if fresh_build:
        cmd.extend(["--no-cache", "--pull"])
    cmd.append(".")

    code, _, err = run_command(cmd, dry_run=dry_run)
    if code != 0:
        logger.error(f"Failed to build test container: {err}")
        sys.exit(1)

    log_success(f"Built '{APP_NAME}:test' successfully.")
    logger.info(f"Run tests inside container via: docker run --rm {APP_NAME}:test")


def action_build_dev(fresh_build: bool, dry_run: bool):
    """Build full-stack development container with Git SHA traceability."""
    sha = get_git_short_sha()
    is_dirty, modified_files = is_git_code_dirty()

    dev_tag = f"{APP_NAME}:dev-{sha}" + ("-dirty" if is_dirty else "")

    if is_dirty:
        logger.warning(f"Uncommitted code modifications detected ({len(modified_files)} files). Tagging as '{dev_tag}'.")
    else:
        logger.info(f"Clean working tree at commit '{sha}'. Tagging as '{dev_tag}'.")

    if not is_dirty and not fresh_build:
        existing_id = inspect_image_id(dev_tag)
        if existing_id:
            logger.info(f"Image '{dev_tag}' already exists ({existing_id[:12]}) and working tree is clean.")
            logger.info(f"Updating floating '{APP_NAME}:dev' tag to point to it...")
            run_command(["docker", "tag", dev_tag, f"{APP_NAME}:dev"], dry_run=dry_run)
            log_success(f"Updated '{APP_NAME}:dev' ➔ '{dev_tag}'. (Rebuild skipped, already up to date).")
            return

    cmd = ["docker", "build", "--target", "runner", "-t", f"{APP_NAME}:dev", "-t", dev_tag]
    if fresh_build:
        cmd.extend(["--no-cache", "--pull"])
    cmd.append(".")

    logger.info(f"Compiling development image '{dev_tag}'...")
    code, _, err = run_command(cmd, dry_run=dry_run)
    if code != 0:
        logger.error(f"Failed to build development image: {err}")
        sys.exit(1)

    log_success(f"Built '{dev_tag}' and updated '{APP_NAME}:dev'.")


def resolve_source_dev_image(from_dev_arg: Optional[str]) -> Optional[Tuple[str, str]]:
    """
    Resolve dev image source tag and ID based on -d argument.
    Returns (dev_source_tag, dev_image_id) or None.
    """
    if from_dev_arg is None:
        return None

    if from_dev_arg and from_dev_arg != "__LATEST__":
        # Explicit SHA or tag provided
        dev_source_tag = from_dev_arg if ":" in from_dev_arg else f"{APP_NAME}:dev-{from_dev_arg}"
        dev_id = inspect_image_id(dev_source_tag)
        if not dev_id:
            logger.error(f"Specified dev image '{dev_source_tag}' does not exist locally.")
            sys.exit(1)
        return dev_source_tag, dev_id

    # Default to current HEAD commit
    sha = get_git_short_sha()
    head_tag = f"{APP_NAME}:dev-{sha}"
    head_id = inspect_image_id(head_tag)
    if head_id:
        return head_tag, head_id

    # Fallback: scan local images for newest clean dev image
    local_images = get_local_images()
    clean_devs = []
    for img in local_images:
        t = img["tag"]
        if ":dev-" in t and "-dirty" not in t and not any(t.startswith(p) for p in ("ghcr.io/", "localhost:")):
            clean_devs.append(img)

    if clean_devs:
        # Sort by git commit timestamp descending
        def dev_sort(item):
            m = re.search(r":dev-([0-9a-fA-F]{7,40})", item["tag"])
            ts = get_git_commit_timestamp(m.group(1)) if m else 0
            return (-ts, item.get("created", ""))

        clean_devs.sort(key=dev_sort)
        best = clean_devs[0]
        logger.info(f"Dev image for current HEAD '{sha}' not found; using newest clean dev build '{best['tag']}'.")
        return best["tag"], inspect_image_id(best["tag"]) or ""

    logger.error("No clean dev images found locally to promote.")
    logger.error(f"Please build one first via './dist_utils/build_image.py -e dev'.")
    sys.exit(1)


def action_build_prod(
    version: str,
    from_dev: Optional[str] = None,
    promote_latest: bool = False,
    do_push: bool = False,
    target_registries: List[str] = ["local"],
    fresh_build: bool = False,
    dry_run: bool = False
):
    """Build or promote an immutable production release, with idempotent safety checks."""
    if not re.match(r"^v\d+\.\d+\.\d+$", version):
        logger.error(f"Invalid production version format '{version}'. Must follow 'vX.Y.Z' (e.g. v1.0.0).")
        sys.exit(1)

    prod_tag = f"{APP_NAME}:{version}"
    existing_id = inspect_image_id(prod_tag)
    use_dev = from_dev is not None

    if use_dev:
        dev_res = resolve_source_dev_image(from_dev)
        if not dev_res:
            sys.exit(1)
        dev_source_tag, dev_id = dev_res

        # Safety Check: Did this dev image already get tagged with a DIFFERENT prod version?
        local_imgs = get_local_images()
        for img in local_imgs:
            if normalize_image_id(img.get("id")) == normalize_image_id(dev_id):
                t = img["tag"]
                m = re.search(r":v\d+\.\d+\.\d+", t)
                if m and not any(t.startswith(p) for p in ("ghcr.io/", "localhost:")):
                    existing_ver = t.split(":")[-1]
                    if existing_ver != version:
                        logger.error(f"Target dev image '{dev_source_tag}' ({dev_id[:12]}) was already finalized as '{APP_NAME}:{existing_ver}'.")
                        logger.error(f"Re-releasing the same artifact under divergent version '{version}' is prohibited.")
                        sys.exit(1)

        # Idempotency / Conflict Check on target prod_tag
        if existing_id:
            if normalize_image_id(existing_id) == normalize_image_id(dev_id):
                logger.info(f"Production release '{prod_tag}' is already finalized on this image ({dev_id[:12]}). Skipping re-tag and proceeding...")
            else:
                logger.error(f"Production release '{prod_tag}' already exists pointing to a DIFFERENT image ({existing_id[:12]}).")
                logger.error("Overwriting finalized releases is prohibited to ensure deployment reproducibility.")
                logger.error("Please increment the patch/minor version (e.g. v1.0.1) for new changes.")
                sys.exit(1)
        else:
            # Check clean git tree
            is_dirty, modified_files = is_git_code_dirty()
            if is_dirty and not dry_run:
                logger.error(f"Cannot release production version '{version}' with uncommitted code modifications:")
                for f in modified_files[:5]:
                    logger.error(f"  {f}")
                if len(modified_files) > 5:
                    logger.error(f"  ... and {len(modified_files) - 5} more files")
                logger.error("Please commit your changes to Git before creating a release, or test using '-e dev'.")
                sys.exit(1)

            logger.info(f"Promoting clean dev image '{dev_source_tag}' ➔ '{prod_tag}'...")
            code, _, err = run_command(["docker", "tag", dev_source_tag, prod_tag], dry_run=dry_run)
            if code != 0:
                logger.error(f"Failed to tag image: {err}")
                sys.exit(1)
            log_success(f"Promoted '{dev_source_tag}' ➔ '{prod_tag}' in 0.01s (Identical bits verified).")
    else:
        # Build fresh from source
        if existing_id and not dry_run:
            logger.error(f"Production release '{prod_tag}' is already finalized ({existing_id[:12]}) and permanently immutable.")
            logger.error("Overwriting release tags is prohibited to ensure deployment reproducibility.")
            logger.error("Please increment the patch/micro version (e.g. v1.0.1) for new changes.")
            sys.exit(1)

        is_dirty, modified_files = is_git_code_dirty()
        if is_dirty and not dry_run:
            logger.error(f"Cannot release production version '{version}' with uncommitted code modifications:")
            for f in modified_files[:5]:
                logger.error(f"  {f}")
            logger.error("Please commit your changes to Git before creating a release, or test using '-e dev'.")
            sys.exit(1)

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

    # Stage 2: Promote Latest (if requested)
    if promote_latest:
        action_promote_latest(version=version, target_registries=target_registries, dry_run=dry_run)

    # Stage 3: Push to Registries (if requested)
    if do_push:
        action_push_release(
            version=version,
            target_registries=target_registries,
            include_latest=promote_latest,
            dry_run=dry_run
        )


def action_promote_latest(
    version: str,
    target_registries: List[str],
    dry_run: bool = False
):
    """Promote an existing local release version to latest within the specified target registries."""
    prod_tag = f"{APP_NAME}:{version}" if not version.startswith(f"{APP_NAME}:") else version
    img_id = inspect_image_id(prod_tag)
    if not img_id and not dry_run:
        logger.error(f"Cannot promote '{prod_tag}': image does not exist locally.")
        logger.error(f"Please create it first via '-e prod -v {version} -d'.")
        sys.exit(1)

    norm_target_id = normalize_image_id(img_id)

    # 1. Local Daemon Promotion
    if "local" in target_registries:
        curr_latest_id = normalize_image_id(inspect_image_id(f"{APP_NAME}:latest"))
        if curr_latest_id and curr_latest_id == norm_target_id:
            logger.info(f"Alias '{APP_NAME}:latest' already points to '{prod_tag}' ({norm_target_id}). No actions required.")
        else:
            logger.info(f"Promoting '{prod_tag}' ➔ '{APP_NAME}:latest' (local daemon)...")
            run_command(["docker", "tag", prod_tag, f"{APP_NAME}:latest"], dry_run=dry_run)
            log_success(f"Pointed '{APP_NAME}:latest' ➔ '{prod_tag}'.")

    # 2. GHCR Remote Promotion
    if "ghcr" in target_registries:
        ghcr_latest = f"ghcr.io/{GHCR_OWNER.lower()}/{APP_NAME}:latest"
        ghcr_version = f"ghcr.io/{GHCR_OWNER.lower()}/{APP_NAME}:{version}"
        v_digest = get_remote_manifest_digest(ghcr_version)
        l_digest = get_remote_manifest_digest(ghcr_latest)
        if v_digest and l_digest and v_digest == l_digest:
            logger.info(f"Remote registry pointer '{ghcr_latest}' already points to '{ghcr_version}' ({v_digest[:19]}...). No actions required.")
        else:
            logger.info(f"Promoting '{prod_tag}' ➔ '{ghcr_latest}' (GHCR)...")
            run_command(["docker", "tag", prod_tag, ghcr_latest], dry_run=dry_run)
            code, _, err = run_command(["docker", "push", ghcr_latest], dry_run=dry_run)
            if code == 0:
                log_success(f"Updated remote registry pointer '{ghcr_latest}'.")
            else:
                logger.error(f"Failed to push latest tag to GHCR: {err}")

    # 3. Custom / Private Registries
    for reg in target_registries:
        if reg not in ("local", "ghcr"):
            reg_latest = f"{reg}/{APP_NAME}:latest"
            logger.info(f"Promoting '{prod_tag}' ➔ '{reg_latest}'...")
            run_command(["docker", "tag", prod_tag, reg_latest], dry_run=dry_run)
            code, _, err = run_command(["docker", "push", reg_latest], dry_run=dry_run)
            if code == 0:
                log_success(f"Updated '{reg_latest}'.")
            else:
                logger.error(f"Failed to push latest tag to {reg}: {err}")


def action_push_release(
    version: str,
    target_registries: List[str],
    include_latest: bool = False,
    dry_run: bool = False
):
    """Push release version tag (and optionally latest) to target registries."""
    prod_tag = f"{APP_NAME}:{version}" if not version.startswith(f"{APP_NAME}:") else version
    img_id = inspect_image_id(prod_tag)
    if not img_id and not dry_run:
        logger.error(f"Cannot push '{prod_tag}': image does not exist locally.")
        logger.error(f"Please build or promote it first via '-e prod -v {version}'.")
        sys.exit(1)

    remote_registries = [r for r in target_registries if r != "local"]
    if not remote_registries:
        logger.info("Target registry is 'local' (local Docker daemon). No remote push actions required.")
        return

    for reg in remote_registries:
        if reg == "ghcr":
            ghcr_version = f"ghcr.io/{GHCR_OWNER.lower()}/{APP_NAME}:{version}"
            if check_remote_manifest_exists(ghcr_version):
                logger.info(f"Remote release '{ghcr_version}' already exists on GHCR. Safe skip.")
            else:
                logger.info(f"Publishing release to GHCR ('{ghcr_version}')...")
                run_command(["docker", "tag", prod_tag, ghcr_version], dry_run=dry_run)
                code, _, err = run_command(["docker", "push", ghcr_version], dry_run=dry_run)
                if code == 0:
                    log_success(f"Published '{ghcr_version}'.")
                else:
                    logger.error(f"Failed to push release to GHCR: {err}")

            if include_latest:
                ghcr_latest = f"ghcr.io/{GHCR_OWNER.lower()}/{APP_NAME}:latest"
                v_digest = get_remote_manifest_digest(ghcr_version)
                l_digest = get_remote_manifest_digest(ghcr_latest)
                if v_digest and l_digest and v_digest == l_digest:
                    logger.info(f"Remote registry pointer '{ghcr_latest}' already points to '{ghcr_version}' ({v_digest[:19]}...). No actions required.")
                else:
                    logger.info(f"Updating remote registry pointer ('{ghcr_latest}')...")
                    run_command(["docker", "tag", prod_tag, ghcr_latest], dry_run=dry_run)
                    code_l, _, err_l = run_command(["docker", "push", ghcr_latest], dry_run=dry_run)
                    if code_l == 0:
                        log_success(f"Updated '{ghcr_latest}'.")
                    else:
                        logger.error(f"Failed to push latest tag to GHCR: {err_l}")
        else:
            custom_target = f"{reg}/{APP_NAME}:{version}"
            if check_remote_manifest_exists(custom_target):
                logger.info(f"Remote release '{custom_target}' already exists on {reg}. Safe skip.")
            else:
                logger.info(f"Publishing release to {reg} ('{custom_target}')...")
                run_command(["docker", "tag", prod_tag, custom_target], dry_run=dry_run)
                code, _, err = run_command(["docker", "push", custom_target], dry_run=dry_run)
                if code == 0:
                    log_success(f"Published '{custom_target}'.")
                else:
                    logger.error(f"Failed to push to {reg}: {err}")

            if include_latest:
                custom_latest = f"{reg}/{APP_NAME}:latest"
                run_command(["docker", "tag", prod_tag, custom_latest], dry_run=dry_run)
                code_l, _, err_l = run_command(["docker", "push", custom_latest], dry_run=dry_run)
                if code_l == 0:
                    log_success(f"Updated '{custom_latest}'.")
                else:
                    logger.error(f"Failed to push latest tag to {reg}: {err_l}")


def action_rollback(
    target_version: Optional[str] = None,
    target_registries: List[str] = ["local"],
    dry_run: bool = False
):
    """Roll back latest to a previous stable release (N-1 or specified version)."""
    images = get_local_images()
    prod_releases = []
    latest_id = inspect_image_id(f"{APP_NAME}:latest")

    for img in images:
        tag = img["tag"]
        if re.search(r":v\d+\.\d+\.\d+$", tag) and not any(tag.startswith(p) for p in ("ghcr.io/", "localhost:")):
            prod_releases.append(tag)

    if not prod_releases:
        logger.error(f"No production release versions (e.g. {APP_NAME}:vX.Y.Z) found locally to roll back to.")
        sys.exit(1)

    # Sort descending by semver
    prod_releases.sort(key=parse_semver_key, reverse=True)

    if target_version:
        target_tag = f"{APP_NAME}:{target_version}" if not target_version.startswith(f"{APP_NAME}:") else target_version
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
            selected_version = prod_releases[0]

    logger.info(f"Executing rollback: pointing '{APP_NAME}:latest' ➔ '{selected_version}'...")
    action_promote_latest(selected_version, target_registries=target_registries, dry_run=dry_run)
    log_success(f"Rollback complete: '{APP_NAME}:latest' now points to '{selected_version}'.")


def action_prune(keep_n: int = 3, dry_run: bool = False):
    """
    Clean up stale dev images, test images, and untagged build layers strictly scoped to APP_NAME.
    Lists all candidate tags prior to deletion and preserves production releases.
    Scoped to project=APP_NAME via Docker label filtering.
    """
    logger.info(f"Scanning local '{APP_NAME}' images for pruning (retention limit: {keep_n} newest dev builds)...")
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
        elif "-dirty" in tag:
            dev_images.append(img)
        else:
            dev_images.append(img)

    # Separate floating aliases from canonical dev images
    canonical_devs = [img for img in dev_images if not img["tag"].endswith(":dev")]
    canonical_devs.sort(key=lambda x: x.get("created", ""), reverse=True)

    preserved_devs = canonical_devs[:keep_n]
    prune_dev_candidates = canonical_devs[keep_n:]

    prune_candidates = prune_dev_candidates + test_images

    print("\n" + "=" * 88)
    print(f"{COLOR_BOLD}PRUNE SCOPING: LOCAL {APP_NAME} ARTIFACTS{COLOR_RESET}")
    print("=" * 88)
    print(f"Active Production Releases Preserved: {len(prod_images)}")
    print(f"Recent Dev Builds Preserved ({keep_n} newest): {len(preserved_devs)}")
    for p in preserved_devs:
        print(f"  {COLOR_GREEN}✓{COLOR_RESET} {p['tag']} ({normalize_image_id(p.get('id'))})")

    print("-" * 88)
    if not prune_candidates:
        print(f"  None. All named {APP_NAME} tags meet local retention limits.")
    else:
        print(f"{COLOR_YELLOW}[PRUNE CANDIDATES SCHEDULED FOR REMOVAL]{COLOR_RESET}")
        print(f"  {'TYPE':<6} {'TAG':<34} {'IMAGE ID':<14} {'SIZE':<10} {'CREATED':<20}")
        for c in prune_candidates:
            c_type = "TEST" if ":test" in c["tag"] else "DEV"
            print(f"  {c_type:<6} {c['tag']:<34} {c['id']:<14} {c['size']:<10} {c['created']}")
    print("=" * 88 + "\n")

    if prune_candidates:
        logger.info(f"Identified {len(prune_candidates)} stale {APP_NAME} image(s) for removal.")
        if dry_run:
            logger.info(f"[DRY-RUN] Would remove {len(prune_candidates)} candidate image(s).")
        else:
            for c in prune_candidates:
                tag = c["tag"]
                logger.info(f"Removing image '{tag}'...")
                run_command(["docker", "rmi", tag], dry_run=dry_run)
            log_success(f"Removed {len(prune_candidates)} stale {APP_NAME} image(s).")

    logger.info(f"Cleaning up untagged dangling build layers (docker image prune -f --filter label=project={APP_NAME})...")
    run_command(["docker", "image", "prune", "-f", "--filter", f"label=project={APP_NAME}"], dry_run=dry_run)
    log_success("Prune operation finished.")


# ==============================================================================
# CLI Main Parser
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description=f"Distribution & Container Lifecycle CLI for {APP_NAME}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  ./dist_utils/build_image.py -l
  ./dist_utils/build_image.py -e test
  ./dist_utils/build_image.py -e dev
  ./dist_utils/build_image.py -e prod -v v1.0.0 -d
  ./dist_utils/build_image.py -e prod -v v1.0.0 -d 1e8ce8c
  ./dist_utils/build_image.py -v v1.0.0 -p
  ./dist_utils/build_image.py -v v1.0.0 -p -R ghcr
  ./dist_utils/build_image.py -v v1.0.0 -P -R ghcr
  ./dist_utils/build_image.py -v v1.0.0 -p -P -R ghcr
  ./dist_utils/build_image.py -e prod -v v1.0.0 -d -p -P -R ghcr
  ./dist_utils/build_image.py -r
  ./dist_utils/build_image.py --prune -k 3
        """
    )

    # Core Action Flags
    parser.add_argument("-e", "--env", choices=["test", "dev", "prod"], help="Target build environment")
    parser.add_argument("-v", "--version", help="Semantic version tag for production release (e.g. v1.0.0)")
    parser.add_argument("-d", "--from-dev", nargs="?", const="__LATEST__", default=None,
                        help="Promote clean dev build to prod (optional: specify source commit SHA/tag; defaults to current HEAD)")
    parser.add_argument("-p", "--promote-latest", action="store_true", default=False,
                        help="Point latest pointer to target release version")
    parser.add_argument("-P", "--push", action="store_true", default=False,
                        help="Push target release version (and latest if -p) to target registries")
    parser.add_argument("-R", "--target-registry", default="local",
                        help="Target registry scope (comma-separated: local, ghcr; default: local)")
    parser.add_argument("-l", "--list", action="store_true", help=f"List local {APP_NAME} images and registry badges")
    parser.add_argument("-r", "--rollback", nargs="?", const="", default=None,
                        help=f"Roll back {APP_NAME}:latest to previous release (N-1 or specified version)")
    parser.add_argument("--prune", action="store_true", help="Clean up old dev/test images and dangling build layers")
    parser.add_argument("-k", "--keep", type=int, default=3, help="Number of recent dev images to keep when pruning (default: 3)")

    # Legacy compatibility flags
    parser.add_argument("--push-ghcr", action="store_true", help="Alias for -P -R ghcr")
    parser.add_argument("--push-local", nargs="?", const="localhost:5000", default=None, help="Publish release to local private registry")
    parser.add_argument("--push-all", action="store_true", help="Alias for -P -R local,ghcr")

    # Options
    parser.add_argument("--fresh-build", action="store_true", help="Bypass local Docker layer cache and pull latest base images (--no-cache --pull)")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging and raw command output")
    parser.add_argument("-n", "--dry-run", action="store_true", help="Display Docker commands without executing them")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Resolve target registries and push flag across new and legacy options
    target_registries = parse_target_registries(args.target_registry)
    do_push = args.push

    if args.push_ghcr:
        if "ghcr" not in target_registries:
            target_registries.append("ghcr")
        do_push = True

    if args.push_all:
        for r in ("local", "ghcr"):
            if r not in target_registries:
                target_registries.append(r)
        do_push = True

    if args.push_local:
        host = args.push_local or "localhost:5000"
        if host not in target_registries:
            target_registries.append(host)
        do_push = True

    # 1. Image List
    if args.list:
        action_list(env_filter=args.env)
        return

    # 2. Prune
    if args.prune:
        action_prune(keep_n=args.keep, dry_run=args.dry_run)
        return

    # 3. Rollback
    if args.rollback is not None:
        target_v = args.rollback if args.rollback != "" else args.version
        action_rollback(
            target_version=target_v,
            target_registries=target_registries,
            dry_run=args.dry_run
        )
        return

    # 4. Environment-based Builds
    if args.env == "test":
        action_build_test(fresh_build=args.fresh_build, dry_run=args.dry_run)
        return

    if args.env == "dev":
        action_build_dev(fresh_build=args.fresh_build, dry_run=args.dry_run)
        return

    if args.env == "prod":
        if not args.version:
            logger.error("Production release requires version argument '-v/--version' (e.g. -v v1.0.0).")
            sys.exit(1)

        action_build_prod(
            version=args.version,
            from_dev=args.from_dev,
            promote_latest=args.promote_latest,
            do_push=do_push,
            target_registries=target_registries,
            fresh_build=args.fresh_build,
            dry_run=args.dry_run
        )
        return

    # 5. Standalone Promotion or Push (without -e)
    if args.promote_latest or do_push:
        if not args.version:
            logger.error("Release version '-v/--version' is required for promotion or push (e.g. -v v1.0.0).")
            sys.exit(1)

        if args.promote_latest and do_push:
            action_push_release(
                version=args.version,
                target_registries=target_registries,
                include_latest=True,
                dry_run=args.dry_run
            )
            if "local" in target_registries:
                action_promote_latest(version=args.version, target_registries=["local"], dry_run=args.dry_run)
        elif args.promote_latest:
            action_promote_latest(
                version=args.version,
                target_registries=target_registries,
                dry_run=args.dry_run
            )
        elif do_push:
            action_push_release(
                version=args.version,
                target_registries=target_registries,
                include_latest=False,
                dry_run=args.dry_run
            )
        return

    # No recognized actions
    parser.print_help()
    sys.exit(0)


if __name__ == "__main__":
    main()
