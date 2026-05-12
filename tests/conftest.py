"""Shared pytest fixtures for Relatenta backend tests.

Builds a tiny synthetic dataset that exercises every layer (authors, keywords,
organizations, nations) so service-layer functions can be validated end-to-end
without touching the OpenAlex network.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from app import crud, models
from app.db import get_db, init_db, reset_db


@dataclass
class Fixture:
    """Lightweight handle exposing the IDs created by ``sample_dataset``."""

    a_ids: dict[str, int]
    k_ids: dict[str, int]
    o_ids: dict[str, int]


@pytest.fixture()
def sample_dataset() -> Fixture:
    """Create a small but non-trivial dataset.

    - 4 authors: Alice/Bob/Carol form a connected triangle; Dave is isolated.
    - 3 keywords overlapping enough to produce a connected co-occurrence graph.
    - 2 organizations across 2 countries to test org + nation layers.
    """
    init_db()
    reset_db()

    a = {}
    k = {}
    o = {}

    with get_db() as db:
        for name in ("Alice", "Bob", "Carol", "Dave"):
            a[name] = crud.get_or_create_author(db, name).id

        for term in ("machine learning", "neural network", "data science"):
            k[term] = crud.get_or_create_keyword(db, term).id

        o["MIT"] = crud.get_or_create_org(db, "MIT", country="US").id
        o["Cambridge"] = crud.get_or_create_org(db, "Cambridge", country="GB").id

        works = [
            # year, authors, keywords, (author -> org)
            (2020, ["Alice", "Bob"], ["machine learning", "neural network"],
             {"Alice": "MIT", "Bob": "MIT"}),
            (2021, ["Bob", "Carol"], ["neural network", "data science"],
             {"Bob": "MIT", "Carol": "Cambridge"}),
            (2022, ["Alice", "Carol"], ["machine learning", "data science"],
             {"Alice": "MIT", "Carol": "Cambridge"}),
            # Dave shares all keywords with Alice but is disconnected
            (2023, ["Dave"], ["machine learning", "neural network", "data science"],
             {"Dave": "Cambridge"}),
        ]

        for i, (year, authors, kws, aff) in enumerate(works):
            w = models.Work(title=f"Paper {i}", year=year, source="test", source_uid=f"test:{i}")
            db.add(w)
            db.flush()
            for pos, name in enumerate(authors):
                db.add(models.WorkAuthor(work_id=w.id, author_id=a[name], position=pos))
            for term in kws:
                db.add(models.WorkKeyword(work_id=w.id, keyword_id=k[term], weight=1.0))
            for name, org in aff.items():
                db.add(models.WorkAffiliation(
                    work_id=w.id, author_id=a[name], org_id=o[org],
                    org_label_raw=org, country_code="US" if org == "MIT" else "GB",
                ))

        crud.recompute_coauthor_edges(db)
        crud.recompute_nation_edges(db)
        try:
            crud.recompute_org_edges(db)
        except Exception:
            pass

    yield Fixture(a_ids=a, k_ids=k, o_ids=o)

    # Tear down so subsequent tests get a clean DB.
    reset_db()
