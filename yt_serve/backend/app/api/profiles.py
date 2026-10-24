"""
Quality Profiles API Router
Exposes CRUD endpoints for managing download quality profiles.
"""
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.repositories.profile_repo import QualityProfileRepository

router = APIRouter()


class QualityProfileBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Display name of profile")
    description: Optional[str] = Field(None, max_length=255, description="Brief description")
    max_resolution: int = Field(1080, ge=0, le=4320, description="Max vertical video resolution (0 for audio only, or 360, 720, 1080, 2160)")
    audio_format: str = Field("copy", description="Extracted audio format (e.g. copy, mp3_320, opus, flac)")
    cipher_strategy: str = Field("web_decipher", description="Cipher decryption strategy: 'web_decipher' or 'direct_format18'")
    is_audio_only: bool = Field(False, description="Whether this profile only archives audio tracks")


class QualityProfileCreate(QualityProfileBase):
    id: Optional[str] = Field(None, max_length=50, pattern=r"^[a-zA-Z0-9_\-]+$", description="Optional unique ID; auto-generated as prof_<hex> if omitted")


class QualityProfileUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=255)
    max_resolution: Optional[int] = Field(None, ge=0, le=4320)
    audio_format: Optional[str] = None
    cipher_strategy: Optional[str] = None
    is_audio_only: Optional[bool] = None


class QualityProfileResponse(QualityProfileBase):
    id: str
    is_builtin: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=List[QualityProfileResponse])
async def list_quality_profiles(db: Session = Depends(get_db)):
    """Fetch all available quality profiles ordered by max_resolution descending"""
    profiles = QualityProfileRepository.get_all(db=db)
    return profiles


@router.get("/{profile_id}", response_model=QualityProfileResponse)
async def get_quality_profile(profile_id: str, db: Session = Depends(get_db)):
    """Fetch a single quality profile by its ID"""
    profile = QualityProfileRepository.get_by_id(profile_id, db=db)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quality profile '{profile_id}' not found"
        )
    return profile


@router.post("", response_model=QualityProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_quality_profile(payload: QualityProfileCreate, db: Session = Depends(get_db)):
    """Create a new custom quality profile"""
    try:
        profile = QualityProfileRepository.create(
            id=payload.id,
            name=payload.name,
            description=payload.description,
            max_resolution=payload.max_resolution,
            audio_format=payload.audio_format,
            cipher_strategy=payload.cipher_strategy,
            is_audio_only=payload.is_audio_only,
            is_builtin=False,
            db=db
        )
        return profile
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.put("/{profile_id}", response_model=QualityProfileResponse)
async def update_quality_profile(profile_id: str, payload: QualityProfileUpdate, db: Session = Depends(get_db)):
    """Update an existing quality profile"""
    profile = QualityProfileRepository.get_by_id(profile_id, db=db)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Quality profile '{profile_id}' not found"
        )

    updated = QualityProfileRepository.update(
        profile_id=profile_id,
        name=payload.name,
        description=payload.description,
        max_resolution=payload.max_resolution,
        audio_format=payload.audio_format,
        cipher_strategy=payload.cipher_strategy,
        is_audio_only=payload.is_audio_only,
        db=db
    )
    return updated


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_quality_profile(profile_id: str, db: Session = Depends(get_db)):
    """Delete a custom quality profile. Reassigns affected playlists to 'standard_1080p'."""
    try:
        deleted = QualityProfileRepository.delete(profile_id, db=db)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Quality profile '{profile_id}' not found"
            )
        return None
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
