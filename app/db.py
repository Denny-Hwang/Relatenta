"""
In-memory SQLite database layer.
Single global database — no Actor concept.
"""

from contextlib import contextmanager
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

_engine = None
_session_factory = None


def _get_engine():
    """Get or create the single in-memory SQLite engine."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=__import__("sqlalchemy.pool", fromlist=["StaticPool"]).StaticPool,
            future=True,
        )
        from . import models  # noqa: F401
        Base.metadata.create_all(bind=_engine)
    return _engine


def _get_session_factory():
    global _session_factory
    if _session_factory is None:
        engine = _get_engine()
        _session_factory = sessionmaker(
            bind=engine, autoflush=False, autocommit=False, future=True
        )
    return _session_factory


@contextmanager
def get_db():
    """Get a database session."""
    factory = _get_session_factory()
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db():
    """Ensure the in-memory database schema exists."""
    _get_engine()


def reset_db():
    """Drop all data and recreate tables."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None
    _get_engine()


def get_stats() -> dict:
    """Get record counts for all main tables."""
    from . import models

    stats = {"works": 0, "authors": 0, "organizations": 0, "keywords": 0, "venues": 0}
    try:
        with get_db() as db:
            stats["works"] = db.execute(select(func.count(models.Work.id))).scalar() or 0
            stats["authors"] = db.execute(select(func.count(models.Author.id))).scalar() or 0
            stats["organizations"] = db.execute(select(func.count(models.Organization.id))).scalar() or 0
            stats["keywords"] = db.execute(select(func.count(models.Keyword.id))).scalar() or 0
            stats["venues"] = db.execute(select(func.count(models.Venue.id))).scalar() or 0
    except Exception:
        pass
    return stats
