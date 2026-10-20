"""
Folder Status Data Access Repository
"""
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import FolderStatus, get_db_context


class FolderStatusRepository:
    """Centralized repository for folder lifecycle tracking (excluded, soft-deleted)"""

    @staticmethod
    def get(folder_name: str, db: Optional[Session] = None) -> Optional[FolderStatus]:
        """Retrieve status record for a folder."""
        try:
            with get_db_context(db) as session:
                return session.query(FolderStatus).filter(FolderStatus.folder_name == folder_name).first()
        except Exception:
            return None

    @staticmethod
    def set(
        folder_name: str,
        status: str,
        reason: Optional[str] = None,
        delete_after: Optional[datetime] = None,
        db: Optional[Session] = None
    ) -> Optional[FolderStatus]:
        """Upsert a folder status record and commit."""
        try:
            with get_db_context(db) as session:
                record = session.query(FolderStatus).filter(FolderStatus.folder_name == folder_name).first()
                if record:
                    record.status = status
                    record.reason = reason
                    record.delete_after = delete_after
                    record.updated_at = datetime.utcnow()
                else:
                    record = FolderStatus(
                        folder_name=folder_name,
                        status=status,
                        reason=reason,
                        delete_after=delete_after,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    session.add(record)
                session.commit()
                session.refresh(record)
                return record
        except Exception as e:
            print(f"[DB] Error setting folder status for {folder_name}: {e}")
            return None

    @staticmethod
    def remove(folder_name: str, db: Optional[Session] = None) -> bool:
        """Delete a folder status record and commit."""
        try:
            with get_db_context(db) as session:
                record = session.query(FolderStatus).filter(FolderStatus.folder_name == folder_name).first()
                if record:
                    session.delete(record)
                    session.commit()
                    return True
                return False
        except Exception as e:
            print(f"[DB] Error removing folder status for {folder_name}: {e}")
            return False

    @staticmethod
    def list(status: Optional[str] = None, db: Optional[Session] = None) -> List[FolderStatus]:
        """List all folder statuses, optionally filtered by status."""
        try:
            with get_db_context(db) as session:
                query = session.query(FolderStatus)
                if status:
                    query = query.filter(FolderStatus.status == status)
                return query.all()
        except Exception:
            return []
