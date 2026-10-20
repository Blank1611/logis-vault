from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.models.database import Base, init_db


def create_isolated_test_db():
    """
    Creates an isolated in-memory SQLite test engine and sessionmaker.
    Uses StaticPool so connections are deterministic and safely disposable.
    """
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    init_db(test_engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=test_engine)
    return test_engine, TestingSession


def dispose_isolated_test_db(test_engine, session=None):
    """Clean up session and dispose of the test engine connection pool to prevent ResourceWarning."""
    if session:
        try:
            session.close()
        except Exception:
            pass
    if test_engine:
        try:
            test_engine.dispose()
        except Exception:
            pass

