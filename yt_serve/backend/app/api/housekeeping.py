"""
Housekeeping & Storage Optimization API Endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.deduplication_service import (
    scan_library_duplicates,
    apply_library_deduplication
)

router = APIRouter(prefix="/api/housekeeping", tags=["housekeeping"])


class DeduplicationScanRequest(BaseModel):
    base_path: Optional[str] = None


class DeduplicationApplyRequest(BaseModel):
    base_path: Optional[str] = None
    duplicate_groups: Optional[List[Dict[str, Any]]] = None


@router.post("/deduplicate/scan")
async def scan_duplicates(req: DeduplicationScanRequest, db: Session = Depends(get_db)):
    """
    Scan library for physical file duplicates across playlist folders.
    Returns preview report with potential space savings.
    """
    try:
        res = scan_library_duplicates(base_path=req.base_path, db=db)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to scan duplicates: {str(e)}")


@router.post("/deduplicate/apply")
async def apply_deduplication(req: DeduplicationApplyRequest, db: Session = Depends(get_db)):
    """
    Execute zero-space hardlink replacement for redundant physical duplicates.
    Frees physical disk space while keeping files playable in all playlists.
    """
    try:
        res = apply_library_deduplication(
            duplicate_groups=req.duplicate_groups,
            base_path=req.base_path,
            db=db
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to apply deduplication: {str(e)}")
