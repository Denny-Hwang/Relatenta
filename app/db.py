"""Database layer.

Default: per-Streamlit-session in-memory SQLite (data lost on refresh).
Override with ``DATABASE_URL`` environment variable to use a shared
persistent engine (file SQLite, Postgres, DuckDB, etc.). When that is
set the engine is created once and reused across sessions, so multiple
browser tabs see the same data and a refresh keeps it.
"""

import os
from contextlib import contextmanager
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

Base = declarative_base()

_engines: dict = {}
_factories: dict = {}
_MAX_SESSIONS = 50

# Persistent mode is opt-in via env var. Empty string → in-memory mode.
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
PERSISTENT = bool(DATABASE_URL)

# Globals reused only in persistent mode.
_shared_engine = None
_shared_factory = None


def is_persistent() -> bool:
    """Public flag so the UI can stop nagging users to Export CSV."""
    return PERSISTENT


def _session_key() -> str:
    """Return a unique key for the current Streamlit session (in-memory mode only)."""
    try:
        import streamlit as st
        if "_db_key" not in st.session_state:
            import uuid
            st.session_state._db_key = str(uuid.uuid4())
        return st.session_state._db_key
    except Exception:
        return "_default"


def _cleanup_if_needed():
    """Remove oldest sessions if we exceed the limit (in-memory mode only)."""
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


def _build_persistent_engine():
    """Create the single shared engine for PERSISTENT mode."""
    global _shared_engine
    if _shared_engine is not None:
        return _shared_engine
    # SQLite-on-disk needs check_same_thread=False; other dialects ignore it.
    connect_args = {}
    if DATABASE_URL.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    _shared_engine = create_engine(
        DATABASE_URL, connect_args=connect_args, future=True
    )
    from . import models  # noqa: F401
    Base.metadata.create_all(bind=_shared_engine)
    return _shared_engine


def _get_engine():
    """Get or create the engine for the current configuration."""
    if PERSISTENT:
        return _build_persistent_engine()

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
    global _shared_factory
    if PERSISTENT:
        if _shared_factory is None:
            _shared_factory = sessionmaker(
                bind=_get_engine(), autoflush=False, autocommit=False, future=True
            )
        return _shared_factory

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
    """Drop all data and recreate tables.

    In persistent mode this drops + recreates the shared schema (affects every
    open browser tab). In in-memory mode it only resets the current session.
    """
    global _shared_engine, _shared_factory
    if PERSISTENT:
        engine = _build_persistent_engine()
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        # Force-recreate the session factory so any cached state is dropped.
        _shared_factory = None
        return

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
