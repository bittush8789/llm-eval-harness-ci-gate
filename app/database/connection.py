"""Database connection, engine configuration, and session management."""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from app.core.config import settings
from app.core.logging import logger
from app.database.models import Base


def create_db_engine():
    """Create SQLAlchemy engine with appropriate dialect arguments."""
    db_url = settings.DATABASE_URL

    if db_url.startswith("sqlite"):
        from sqlalchemy.pool import StaticPool
        connect_args = {"check_same_thread": False}
        kwargs = {"connect_args": connect_args, "echo": False}
        if ":memory:" in db_url:
            kwargs["poolclass"] = StaticPool
        return create_engine(db_url, **kwargs)

    # PostgreSQL configuration
    try:
        return create_engine(
            db_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            echo=False,
        )
    except Exception as e:
        logger.warning(
            f"Failed to create database engine for '{db_url}': {e}. Falling back to SQLite local database."
        )
        return create_engine(
            "sqlite:///./ai_evaluation.db",
            connect_args={"check_same_thread": False},
            echo=False,
        )


engine = create_db_engine()
SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize database tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}")
        raise


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager for transactional database sessions."""
    session: Session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database session injection."""
    session: Session = SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
