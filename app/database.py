from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager

from app.config import config

# Import Base from Core - all models use this Base
from analysercomptacore.database import Base
import analysercomptacore.database as core_db


# Create engine with connection pooling
engine = create_engine(
    config.get_connection_string(),
    pool_pre_ping=True,
    pool_recycle=3600,
    echo=False
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Initialize Core database with same connection string
core_db.init_database(config.get_connection_string())


@contextmanager
def get_db() -> Session:
    """Context manager for database sessions."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_session() -> Session:
    """Get a new database session."""
    return SessionLocal()
