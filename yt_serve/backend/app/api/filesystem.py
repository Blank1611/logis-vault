"""
Sandboxed Server Filesystem API for Directory Browsing and Validation.
Ensures file operations are securely confined to mounted storage (e.g. /downloads).
"""
import os
import re
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging_engine import get_logger
from app.models.database import get_db
from app.repositories import PlaylistRepository

logger = get_logger("app.api.filesystem")

router = APIRouter()


class DirectoryItem(BaseModel):
    name: str
    path: str
    has_children: bool = False
    is_writable: bool = True


class BrowseResponse(BaseModel):
    current_path: str
    parent_path: Optional[str]
    root_path: str
    subdirectories: List[DirectoryItem]


class CreateDirectoryRequest(BaseModel):
    parent_path: str = Field(..., description="Absolute path of parent directory within allowed mount")
    directory_name: str = Field(..., description="Name of new folder to create")


class ValidatePathResponse(BaseModel):
    valid: bool
    exists: bool
    is_dir: bool
    is_writable: bool
    is_inside_mount: bool
    resolved_path: str
    message: str


def get_allowed_roots() -> List[str]:
    """Retrieve canonical absolute paths of all permitted storage roots"""
    roots = []
    base_dir = os.path.realpath(settings.BASE_DOWNLOAD_PATH)
    if os.path.isdir(base_dir):
        roots.append(base_dir)

    adhoc_dir = settings.get_adhoc_download_path()
    if adhoc_dir:
        real_adhoc = os.path.realpath(adhoc_dir)
        if real_adhoc not in roots:
            roots.append(real_adhoc)

    # In case base_dir doesn't exist yet, ensure at least BASE_DOWNLOAD_PATH is registered
    if not roots:
        roots.append(os.path.abspath(settings.BASE_DOWNLOAD_PATH))

    return roots


def resolve_safe_path(requested_path: Optional[str]) -> str:
    """
    Resolve and validate that a requested path resides inside an allowed mount point.
    Raises HTTPException 403 on traversal attempts, 404 if parent does not exist.
    """
    allowed_roots = get_allowed_roots()
    primary_root = allowed_roots[0]

    if not requested_path or not requested_path.strip():
        return primary_root

    clean_path = os.path.abspath(os.path.expanduser(requested_path.strip()))
    real_path = os.path.realpath(clean_path)

    # Check containment within any allowed root
    is_safe = False
    for root in allowed_roots:
        try:
            if os.path.commonpath([real_path, root]) == root:
                is_safe = True
                break
        except ValueError:
            # Different drive letters on Windows or invalid comparison
            continue

    if not is_safe:
        logger.warning(f"[Filesystem Sandbox] Blocked path traversal attempt: '{requested_path}' -> '{real_path}'")
        raise HTTPException(
            status_code=403,
            detail=f"Access denied: '{requested_path}' is outside mounted storage directories ({primary_root})."
        )

    return real_path


@router.get("/browse", response_model=BrowseResponse)
async def browse_directories(
    path: Optional[str] = Query(None, description="Path to browse (defaults to base download path)"),
    exclude_managed: bool = Query(False, description="Exclude managed playlist directories and Layer 1 noise"),
    db: Session = Depends(get_db)
):
    """
    List subdirectories inside a sandboxed folder for directory selection.
    Guarantees client cannot escape container mount boundaries.
    """
    safe_path = resolve_safe_path(path)
    allowed_roots = get_allowed_roots()
    primary_root = allowed_roots[0]

    if not os.path.exists(safe_path):
        # Create base directory if missing
        if safe_path in allowed_roots:
            os.makedirs(safe_path, exist_ok=True)
        else:
            raise HTTPException(status_code=404, detail=f"Directory '{safe_path}' does not exist.")

    if not os.path.isdir(safe_path):
        raise HTTPException(status_code=400, detail=f"Path '{safe_path}' is a file, not a directory.")

    # Determine parent path if safely above primary_root
    parent_path = None
    real_parent = os.path.realpath(os.path.join(safe_path, ".."))
    for root in allowed_roots:
        try:
            if os.path.commonpath([real_parent, root]) == root and real_parent != safe_path:
                parent_path = real_parent
                break
        except ValueError:
            continue

    managed_playlist_paths = set()
    layer1_excluded = set(settings.get_excluded_directories())
    if exclude_managed:
        try:
            for pl in PlaylistRepository.get_all(db=db):
                if pl.title:
                    managed_playlist_paths.add(os.path.realpath(os.path.join(settings.BASE_DOWNLOAD_PATH, pl.title)))
        except Exception as e:
            logger.debug(f"Could not load playlists for exclusion: {e}")

    subdirs: List[DirectoryItem] = []
    try:
        with os.scandir(safe_path) as entries:
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        # Filter out internal/system hidden folders
                        if entry.name.startswith(".") or entry.name in ("__pycache__",):
                            continue

                        entry_name_lower = entry.name.lower()
                        if exclude_managed and entry_name_lower in layer1_excluded:
                            continue

                        entry_real_path = os.path.realpath(entry.path)
                        if exclude_managed and entry_real_path in managed_playlist_paths:
                            continue
                        # Check if it has child directories
                        has_children = False
                        try:
                            with os.scandir(entry_real_path) as child_entries:
                                has_children = any(c.is_dir(follow_symlinks=False) and not c.name.startswith(".") for c in child_entries)
                        except (PermissionError, FileNotFoundError):
                            has_children = False

                        is_writable = os.access(entry_real_path, os.W_OK)
                        subdirs.append(
                            DirectoryItem(
                                name=entry.name,
                                path=entry_real_path,
                                has_children=has_children,
                                is_writable=is_writable
                            )
                        )
                except (PermissionError, FileNotFoundError):
                    continue
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied reading directory: '{safe_path}'")

    # Sort subdirectories alphabetically
    subdirs.sort(key=lambda d: d.name.lower())

    return BrowseResponse(
        current_path=safe_path,
        parent_path=parent_path,
        root_path=primary_root,
        subdirectories=subdirs
    )


@router.post("/create-directory")
async def create_directory(payload: CreateDirectoryRequest):
    """
    Safely create a new subfolder inside an allowed mounted storage path.
    """
    parent_safe = resolve_safe_path(payload.parent_path)

    if not os.path.isdir(parent_safe):
        raise HTTPException(status_code=404, detail=f"Parent directory '{parent_safe}' does not exist.")

    dir_name = payload.directory_name.strip()
    # Sanitize folder name
    if not dir_name or "/" in dir_name or "\\" in dir_name or ".." in dir_name:
        raise HTTPException(status_code=400, detail="Invalid directory name. Special characters / \\ .. are prohibited.")

    new_path = os.path.join(parent_safe, dir_name)
    real_new_path = os.path.realpath(new_path)

    # Double-check sandbox containment
    resolve_safe_path(real_new_path)

    try:
        os.makedirs(real_new_path, exist_ok=True)
        return {
            "status": "success",
            "message": f"Directory '{dir_name}' created successfully.",
            "path": real_new_path
        }
    except Exception as e:
        logger.error(f"[Filesystem] Failed to create directory '{real_new_path}': {e}")
        raise HTTPException(status_code=500, detail=f"Could not create directory: {str(e)}")


@router.get("/validate-path", response_model=ValidatePathResponse)
async def validate_path(path: str = Query(..., description="Path to validate")):
    """
    Validate whether a path exists, is writable, and resides inside Docker mount points.
    """
    clean_path = path.strip()
    try:
        safe_path = resolve_safe_path(clean_path)
        exists = os.path.exists(safe_path)
        is_dir = os.path.isdir(safe_path) if exists else False
        is_writable = os.access(safe_path, os.W_OK) if exists else os.access(os.path.dirname(safe_path), os.W_OK)

        return ValidatePathResponse(
            valid=True,
            exists=exists,
            is_dir=is_dir,
            is_writable=is_writable,
            is_inside_mount=True,
            resolved_path=safe_path,
            message="Path is valid and contained within mounted container storage."
        )
    except HTTPException as e:
        return ValidatePathResponse(
            valid=False,
            exists=False,
            is_dir=False,
            is_writable=False,
            is_inside_mount=False,
            resolved_path=clean_path,
            message=e.detail
        )
    except Exception as ex:
        return ValidatePathResponse(
            valid=False,
            exists=False,
            is_dir=False,
            is_writable=False,
            is_inside_mount=False,
            resolved_path=clean_path,
            message=str(ex)
        )
