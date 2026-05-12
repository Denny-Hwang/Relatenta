"""Tests for the DATABASE_URL persistent-storage opt-in.

We run these in a subprocess so the module-level DATABASE_URL is read fresh
from the environment for each scenario (the app.db module captures the env
var at import time, so monkeypatching after import doesn't take effect).
"""
from __future__ import annotations

import subprocess
import sys
import textwrap


def _run(env: dict[str, str], snippet: str) -> str:
    proc = subprocess.run(
        [sys.executable, "-c", textwrap.dedent(snippet)],
        capture_output=True, text=True, env={**env}, check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"Subprocess failed: {proc.stderr}\nstdout: {proc.stdout}")
    return proc.stdout.strip()


def test_default_mode_is_in_memory(monkeypatch_env_minimal):
    out = _run(
        monkeypatch_env_minimal,
        """
        from app.db import is_persistent, init_db
        init_db()
        print(is_persistent())
        """,
    )
    assert out == "False"


def test_database_url_enables_persistent_mode(monkeypatch_env_minimal, tmp_path):
    db_path = tmp_path / "relatenta.db"
    env = {**monkeypatch_env_minimal, "DATABASE_URL": f"sqlite:///{db_path}"}
    out = _run(
        env,
        """
        from app.db import is_persistent, init_db, get_db
        from app import crud
        init_db()
        with get_db() as db:
            crud.get_or_create_author(db, "Persistent Author")
        print(is_persistent())
        """,
    )
    assert out == "True"
    assert db_path.exists(), "SQLite file should have been created on disk"


def test_persistent_data_survives_process_restart(monkeypatch_env_minimal, tmp_path):
    db_path = tmp_path / "relatenta.db"
    env = {**monkeypatch_env_minimal, "DATABASE_URL": f"sqlite:///{db_path}"}

    # Process 1 — write an author.
    _run(
        env,
        """
        from app.db import init_db, get_db
        from app import crud
        init_db()
        with get_db() as db:
            crud.get_or_create_author(db, "Survives Reboot")
        """,
    )

    # Process 2 — read it back.
    out = _run(
        env,
        """
        from app.db import init_db, get_db
        from app import models
        from sqlalchemy import select
        init_db()
        with get_db() as db:
            rows = db.execute(select(models.Author.display_name)).scalars().all()
        print(",".join(sorted(rows)))
        """,
    )
    assert "Survives Reboot" in out
