"""
System Setting Data Access Repository
"""
from typing import Optional, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.database import SystemSetting, get_db_context


class SystemSettingRepository:
    """Centralized repository for system key-value configuration state"""

    @staticmethod
    def get(key: str, default: Optional[str] = None, db: Optional[Session] = None) -> Optional[str]:
        """Fetch a system setting value by key"""
        try:
            with get_db_context(db) as session:
                setting = session.query(SystemSetting).filter(SystemSetting.key == key).first()
                return setting.value if setting else default
        except Exception:
            return default

    @staticmethod
    def set(key: str, value: str, db: Optional[Session] = None) -> Optional[SystemSetting]:
        """Persist or update a system setting value"""
        try:
            with get_db_context(db) as session:
                setting = session.query(SystemSetting).filter(SystemSetting.key == key).first()
                if setting:
                    setting.value = str(value)
                    setting.updated_at = datetime.utcnow()
                else:
                    setting = SystemSetting(key=key, value=str(value), updated_at=datetime.utcnow())
                    session.add(setting)
                session.flush()
                session.refresh(setting)
                return setting
        except Exception as e:
            print(f"[DB] Error setting system setting {key}: {e}")
            return None

    @staticmethod
    def get_all(db: Optional[Session] = None) -> Dict[str, str]:
        """Fetch all system settings as a dictionary"""
        try:
            with get_db_context(db) as session:
                settings = session.query(SystemSetting).all()
                return {s.key: s.value for s in settings}
        except Exception:
            return {}
