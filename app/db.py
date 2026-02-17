"""
In-memory SQLite database layer for Streamlit Cloud deployment.
Each actor gets an in-memory SQLite engine stored in st.session_state.
"""

from contextlib import contextmanager
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

# Module-level engine/session caches (within one Streamlit process)
_engines = {}
_session_factories = {}


def _get_engine(actor_name: str):
    """Get or create an in-memory SQLite engine for an actor."""
    if actor_name not in _engines:
        engine = create_engine(
            "sqlite://",  # in-memory
            connect_args={"check_same_thread": False},
            future=True,
        )
        _engines[actor_name] = engine
        # Create all tables immediately
        from . import models  # noqa: F401
        Base.metadata.create_all(bind=engine)
    return _engines[actor_name]


def _get_session_factory(actor_name: str):
    if actor_name not in _session_factories:
        engine = _get_engine(actor_name)
        _session_factories[actor_name] = sessionmaker(
            bind=engine, autoflush=False, autocommit=False, future=True
        )
    return _session_factories[actor_name]


@contextmanager
def get_db(actor_name: str = "default"):
    """Get database session for a specific actor."""
    factory = _get_session_factory(actor_name)
    db = factory()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def init_db(actor_name: str = "default"):
    """Ensure the in-memory database schema exists for this actor."""
    _get_engine(actor_name)  # triggers table creation


def list_actors() -> list:
    """List all active in-memory actor databases."""
    from . import models  # noqa: F401
    actors = []
    for name, engine in _engines.items():
        actors.append({"name": name, "size_mb": 0.0})
    return actors


def delete_actor_db(actor_name: str) -> bool:
    """Remove an actor's in-memory database."""
    if actor_name in _engines:
        _engines[actor_name].dispose()
        del _engines[actor_name]
    if actor_name in _session_factories:
        del _session_factories[actor_name]
    return True


def get_actor_stats(actor_name: str) -> dict:
    """Get statistics for an actor's database."""
    from . import models

    stats = {
        "actor": actor_name,
        "exists": actor_name in _engines,
        "works": 0,
        "authors": 0,
        "organizations": 0,
        "keywords": 0,
        "venues": 0,
    }
    if actor_name not in _engines:
        return stats

    try:
        with get_db(actor_name) as db:
            stats["works"] = db.execute(select(func.count(models.Work.id))).scalar() or 0
            stats["authors"] = db.execute(select(func.count(models.Author.id))).scalar() or 0
            stats["organizations"] = db.execute(select(func.count(models.Organization.id))).scalar() or 0
            stats["keywords"] = db.execute(select(func.count(models.Keyword.id))).scalar() or 0
            stats["venues"] = db.execute(select(func.count(models.Venue.id))).scalar() or 0
    except Exception:
        pass

    return stats
