import os
from contextlib import contextmanager
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv
from typing import Optional

load_dotenv()

# Base directory for all actor databases
DATABASES_DIR = os.getenv("DATABASES_DIR", "./databases")
os.makedirs(DATABASES_DIR, exist_ok=True)

Base = declarative_base()

# Store active database sessions
_active_engines = {}
_active_sessions = {}

def get_actor_db_path(actor_name: str) -> str:
    """Get the database file path for a specific actor."""
    # Sanitize actor name for filesystem
    safe_name = "".join(c if c.isalnum() or c in ('_', '-') else '_' for c in actor_name)
    return os.path.join(DATABASES_DIR, f"{safe_name}.db")

def get_engine(actor_name: str):
    """Get or create engine for a specific actor's database."""
    if actor_name not in _active_engines:
        db_path = get_actor_db_path(actor_name)
        database_url = f"sqlite:///{db_path}"
        _active_engines[actor_name] = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            future=True,
        )
    return _active_engines[actor_name]

def get_session_factory(actor_name: str):
    """Get session factory for a specific actor's database."""
    if actor_name not in _active_sessions:
        engine = get_engine(actor_name)
        _active_sessions[actor_name] = sessionmaker(
            bind=engine, 
            autoflush=False, 
            autocommit=False, 
            future=True
        )
    return _active_sessions[actor_name]

@contextmanager
def get_db(actor_name: str = "default"):
    """Get database session for a specific actor."""
    SessionLocal = get_session_factory(actor_name)
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

def init_db(actor_name: str = "default"):
    """Initialize database for a specific actor."""
    from . import models  # ensure models are imported
    engine = get_engine(actor_name)
    Base.metadata.create_all(bind=engine)

def list_actors() -> list:
    """List all available actor databases."""
    actors = []
    if os.path.exists(DATABASES_DIR):
        for file in os.listdir(DATABASES_DIR):
            if file.endswith('.db'):
                actor_name = file[:-3]  # Remove .db extension
                db_path = os.path.join(DATABASES_DIR, file)
                size_mb = os.path.getsize(db_path) / (1024 * 1024)
                actors.append({
                    "name": actor_name,
                    "file": file,
                    "path": db_path,
                    "size_mb": round(size_mb, 2)
                })
    return actors

def delete_actor_db(actor_name: str) -> bool:
    """Delete an actor's database."""
    try:
        # Close any active connections
        if actor_name in _active_engines:
            _active_engines[actor_name].dispose()
            del _active_engines[actor_name]
        if actor_name in _active_sessions:
            del _active_sessions[actor_name]
        
        # Delete the file
        db_path = get_actor_db_path(actor_name)
        if os.path.exists(db_path):
            os.remove(db_path)
            return True
        return False
    except Exception as e:
        print(f"Error deleting actor database: {e}")
        return False

def get_actor_stats(actor_name: str) -> dict:
    """Get statistics for an actor's database."""
    from sqlalchemy import select, func
    from . import models
    
    stats = {
        "actor": actor_name,
        "exists": False,
        "works": 0,
        "authors": 0,
        "organizations": 0,
        "keywords": 0,
        "venues": 0
    }
    
    db_path = get_actor_db_path(actor_name)
    if not os.path.exists(db_path):
        return stats
    
    stats["exists"] = True
    
    try:
        with get_db(actor_name) as db:
            stats["works"] = db.execute(select(func.count(models.Work.id))).scalar() or 0
            stats["authors"] = db.execute(select(func.count(models.Author.id))).scalar() or 0
            stats["organizations"] = db.execute(select(func.count(models.Organization.id))).scalar() or 0
            stats["keywords"] = db.execute(select(func.count(models.Keyword.id))).scalar() or 0
            stats["venues"] = db.execute(select(func.count(models.Venue.id))).scalar() or 0
    except:
        pass
    
    return stats