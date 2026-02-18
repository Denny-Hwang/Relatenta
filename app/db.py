"""
In-memory SQLite database layer.
Per-session isolation — each Streamlit session gets its own DB.
"""

from contextlib import contextmanager
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

Base = declarative_base()

_engines: dict = {}
_factories: dict = {}
_MAX_SESSIONS = 50


def _session_key() -> str:
    """Return a unique key for the current Streamlit session."""
    try:
        import streamlit as st
        if "_db_key" not in st.session_state:
            import uuid
            st.session_state._db_key = str(uuid.uuid4())
        return st.session_state._db_key
    except Exception:
        return "_default"


def _cleanup_if_needed():
    """Remove oldest sessions if we exceed the limit."""
    if len(_engines) > _MAX_SESSIONS:
        current = _session_key()
        for k in list(_engines.keys()):
            if k != current:
                try:
                    _engines[k].dispose()
                except Exception:
                    pass
                _engines.pop(k, None)
                _factories.pop(k, None)


def _get_engine():
    """Get or create the engine for the current session."""
    key = _session_key()
    if key not in _engines:
        _cleanup_if_needed()
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            future=True,
        )
        from . import models  # noqa: F401
        Base.metadata.create_all(bind=engine)
        _engines[key] = engine
    return _engines[key]


def _get_session_factory():
    key = _session_key()
    if key not in _factories:
        engine = _get_engine()
        _factories[key] = sessionmaker(
            bind=engine, autoflush=False, autocommit=False, future=True
        )
    return _factories[key]


@contextmanager
def get_db():
    """Get a database session for the current Streamlit session."""
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
    """Ensure the in-memory database schema exists for this session."""
    _get_engine()


def reset_db():
    """Drop all data and recreate tables for this session."""
    key = _session_key()
    if key in _engines:
        _engines[key].dispose()
        del _engines[key]
    _factories.pop(key, None)
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
