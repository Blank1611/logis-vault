"""
Isolated In-Memory Database Sandbox for Unit Tests.
Guarantees that production yt_manager.db is never touched by test suites.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.database import Base


def create_isolated_test_db():
    """
    Creates an isolated in-memory SQLite test engine and sessionmaker.
    This guarantees 100% test isolation from the production yt_manager.db.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    return test_engine, TestingSession
