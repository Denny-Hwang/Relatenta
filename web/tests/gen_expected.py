#!/usr/bin/env python3
"""Generate parity fixtures for the JS port from the Python service layer.

Builds a deterministic synthetic OpenAlex-shaped dataset, runs it through the
*real* Python modules (app.crud, services_graph, services_heatmap,
services_report, services_insight, services_export) and writes the results to
web/tests/fixtures/ so `node --test web/tests` can assert that the JavaScript
port produces the same numbers.

Run from the repository root:

    python web/tests/gen_expected.py
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)
os.environ.pop("DATABASE_URL", None)

from app import crud  # noqa: E402
from app.db import get_db, init_db, reset_db  # noqa: E402
from app.services_export import export_to_csv  # noqa: E402
from app.services_graph import build_graph  # noqa: E402
from app.services_heatmap import author_keyword_heat, nation_nation_heat  # noqa: E402
from app.services_insight import (  # noqa: E402
    build_strategic_diagram,
    build_thematic_evolution,
    detect_bursts,
    detect_communities,
    detect_research_gaps,
    find_shortest_path,
    recommend_collaborators,
)
from app.services_report import gather_report  # noqa: E402

FIXTURE_DIR = os.path.join(ROOT, "web", "tests", "fixtures")


def make_works(seed: int = 7, n_works: int = 60) -> list[dict]:
    """Synthetic but realistic OpenAlex work payloads (subset of fields the app reads)."""
    rnd = random.Random(seed)
    authors = [
        ("Alice Kim", "US", "MIT"), ("Bob Lee", "US", "MIT"), ("Carol Park", "GB", "Cambridge"),
        ("Dave Choi", "GB", "Cambridge"), ("Eve Jung", "KR", "KAIST"), ("Frank Han", "KR", "KAIST"),
        ("Grace Oh", "DE", "TU Munich"), ("Heidi Yoon", "DE", "TU Munich"), ("Ivan Seo", "JP", "Tokyo"),
        ("Judy Kang", "JP", "Tokyo"), ("Kevin Lim", "US", "Stanford"), ("Laura Shin", "US", "Stanford"),
        ("Mallory Cho", "CN", "Tsinghua"), ("Niaj Moon", "CN", "Tsinghua"), ("Olivia Baek", "FR", "Sorbonne"),
        ("Peggy Nam", "FR", "Sorbonne"), ("Quentin Ha", "CA", "Toronto"), ("Rupert Song", "CA", "Toronto"),
        ("Sybil Kwon", "KR", "SNU"), ("Trent Yang", "KR", "SNU"),
    ]
    topics = [
        ["Machine learning", "Deep learning", "Neural network"],
        ["Computer vision", "Image segmentation", "Object detection"],
        ["Natural language processing", "Language model", "Transformer"],
        ["Graph theory", "Network science", "Community structure"],
        ["Bioinformatics", "Genomics", "Protein structure"],
    ]
    venues = ["NeurIPS", "ICML", "Nature", "Science", "CVPR", "ACL", "Bioinformatics"]
    works = []
    for i in range(n_works):
        year = 2015 + int((i / n_works) * 10)  # ascending years 2015..2024
        cluster = rnd.randrange(len(topics))
        n_auth = rnd.randint(1, 5)
        base = rnd.randrange(len(authors))
        # authors are picked near each other so co-author communities exist
        picked = [authors[(base + k) % len(authors)] for k in range(n_auth)]
        authorships = []
        for name, cc, inst in picked:
            authorships.append({
                "author": {"id": f"https://openalex.org/A{int(hashlib.md5(name.encode()).hexdigest()[:6], 16)}",
                           "display_name": name,
                           "orcid": None},
                "institutions": [{"display_name": inst, "country_code": cc}] if rnd.random() > 0.15 else [],
            })
        concepts = [{"display_name": t, "score": round(rnd.uniform(0.3, 0.9), 3)} for t in topics[cluster]]
        if rnd.random() > 0.5:
            other = topics[(cluster + 1) % len(topics)]
            concepts.append({"display_name": other[0], "score": 0.4})
        inv = {"This": [0], "is": [1], "paper": [2], str(i): [3]}
        works.append({
            "id": f"https://openalex.org/W{1000 + i}",
            "doi": f"https://doi.org/10.1000/test.{i}" if i % 4 else None,
            "title": f"Paper {i} on {topics[cluster][0]}",
            "publication_year": year,
            "type": "article",
            "language": "en",
            "cited_by_count": rnd.randint(0, 500),
            "host_venue": {"display_name": venues[i % len(venues)], "type": "journal", "issn": ["0000-0000"],
                           "publisher": "Pub"},
            "primary_location": {"source": {"url": f"https://example.org/{i}"}},
            "authorships": authorships,
            "concepts": concepts,
            "abstract_inverted_index": inv,
        })
    return works


def main() -> None:
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    works = make_works()
    with open(os.path.join(FIXTURE_DIR, "works.json"), "w", encoding="utf-8") as fh:
        json.dump(works, fh, indent=1)

    init_db()
    reset_db()
    with get_db() as db:
        for w in works:
            crud.upsert_work_from_openalex(db, w)
        # Upsert the first work twice to exercise the update path.
        crud.upsert_work_from_openalex(db, works[0])
        # NOTE: the session runs with autoflush=False, so relations of the most
        # recently upserted work are still pending when recompute_* queries the
        # tables. Flush explicitly so the fixture reflects the full dataset.
        db.flush()
        crud.recompute_coauthor_edges(db)
        crud.recompute_nation_edges(db)
        crud.recompute_org_edges(db)

    from app import models  # noqa: E402
    from sqlalchemy import select  # noqa: E402

    expected: dict = {}
    with get_db() as db:
        expected["stats"] = {
            "works": db.query(models.Work).count(),
            "authors": db.query(models.Author).count(),
            "organizations": db.query(models.Organization).count(),
            "keywords": db.query(models.Keyword).count(),
            "venues": db.query(models.Venue).count(),
        }
        expected["authors"] = [
            {"id": a.id, "display_name": a.display_name, "normalized_name": a.normalized_name}
            for a in db.execute(select(models.Author).order_by(models.Author.id)).scalars()
        ]
        expected["keywords"] = [
            {"id": k.id, "term_display": k.term_display}
            for k in db.execute(select(models.Keyword).order_by(models.Keyword.id)).scalars()
        ]
        expected["coauthor_edges"] = sorted(
            [[e.a_id, e.b_id, e.weight] for e in db.execute(select(models.CoauthorEdge)).scalars()]
        )
        expected["org_edges"] = sorted(
            [[e.org1_id, e.org2_id, e.weight] for e in db.execute(select(models.OrgEdge)).scalars()]
        )
        expected["nation_edges"] = sorted(
            [[e.n1, e.n2, e.weight] for e in db.execute(select(models.NationEdge)).scalars()]
        )
        first_author = db.execute(select(models.Author).order_by(models.Author.id)).scalars().first()
        first_kw = db.execute(select(models.Keyword).order_by(models.Keyword.id)).scalars().first()
        first_org = db.execute(select(models.Organization).order_by(models.Organization.id)).scalars().first()

        graphs = {}
        for layer in ("authors", "keywords", "orgs", "nations"):
            graphs[f"{layer}_full"] = build_graph(db, layer, 2000, 2026, 1.0, None, False)
            graphs[f"{layer}_range"] = build_graph(db, layer, 2018, 2021, 1.0, None, False)
            graphs[f"{layer}_edge2"] = build_graph(db, layer, None, None, 2.0, None, False)
        graphs["authors_focus"] = build_graph(db, "authors", 2000, 2026, 1.0, [first_author.id], False)
        graphs["authors_focus_only"] = build_graph(db, "authors", 2000, 2026, 1.0, [first_author.id], True)
        graphs["authors_focus_only_range"] = build_graph(db, "authors", 2020, 2024, 1.0, [first_author.id], True)
        graphs["keywords_focus_only"] = build_graph(db, "keywords", 2000, 2026, 1.0, [first_kw.id], True)
        graphs["orgs_focus_only"] = build_graph(db, "orgs", 2000, 2026, 1.0, [first_org.id], True)
        graphs["nations_focus_only"] = build_graph(db, "nations", 2000, 2026, 1.0, ["US"], True)
        graphs["nations_focus"] = build_graph(db, "nations", 2000, 2026, 1.0, ["KR"], False)
        graphs["authors_bad_focus"] = build_graph(db, "authors", 2000, 2026, 1.0, [999999], False)
        # Canonical ordering: row order of un-ORDERed SELECTs is not guaranteed,
        # and the JS test sorts both sides anyway.
        for g in graphs.values():
            g["nodes"].sort(key=lambda n: n["id"])
            g["edges"].sort(key=lambda e: (e["source"], e["target"]))
        expected["graphs"] = graphs
        expected["focus_ids"] = {"author": first_author.id, "keyword": first_kw.id, "org": first_org.id}

        expected["heat_author_keyword"] = author_keyword_heat(db, 2000, 2026)
        expected["heat_author_keyword_range"] = author_keyword_heat(db, 2018, 2021)
        expected["heat_nation"] = nation_nation_heat(db, 2000, 2026)

        rpt = gather_report(db)
        # Break ties deterministically (SQL ORDER BY ... LIMIT leaves tie order undefined).
        # Which tied rows survive a LIMIT is undefined, so keep only the numeric
        # columns (their multiset is stable); the JS test compares exactly those.
        keep = {
            "top_authors": ("papers",), "top_keywords": ("count",), "top_venues": ("papers",),
            "top_collabs": ("weight", "papers"), "top_kw_pairs": ("co_occurrences",),
            "highlight_works": ("cited_by_count",),
        }
        for key, cols in keep.items():
            rpt[key] = sorted(({c: row[c] for c in cols} for row in rpt[key]), key=lambda r: tuple(r.values()), reverse=True)
        rpt["country_dist"].sort(key=lambda x: (-x["papers"], x["country"]))
        rpt["n_graph_edges"] = len(rpt.pop("graph_edges"))
        rpt.pop("graph_nodes")
        expected["report"] = rpt

        expected["bursts"] = detect_bursts(db, 3, 3)
        expected["bursts_w2"] = detect_bursts(db, 2, 2)
        expected["recommend"] = recommend_collaborators(db, first_author.id, 10)
        a_ids = [a["id"] for a in expected["authors"]]
        expected["shortest_path"] = find_shortest_path(db, a_ids[0], a_ids[len(a_ids) // 2])
        expected["shortest_path_missing"] = find_shortest_path(db, a_ids[0], 999999)

        comm = detect_communities(db, "authors", 1.0, None, None)
        expected["communities_authors"] = {
            "num_nodes": len(comm["partition"]), "modularity": comm["modularity"],
            "num_communities": comm["num_communities"],
        }
        comm_k = detect_communities(db, "keywords", 1.0, None, None)
        expected["communities_keywords"] = {
            "num_nodes": len(comm_k["partition"]), "modularity": comm_k["modularity"],
            "num_communities": comm_k["num_communities"],
        }
        gaps = detect_research_gaps(db, None, None, 3, 15)
        expected["gaps_count"] = len(gaps)
        strat = build_strategic_diagram(db, None, None, 3)
        expected["strategic"] = {"n_themes": len(strat["themes"]),
                                 "quadrants": sorted(t["quadrant"] for t in strat["themes"])}
        evo = build_thematic_evolution(db, 3, 2)
        expected["evolution"] = {"periods": evo["periods"], "n_nodes": len(evo["nodes"]), "n_flows": len(evo["flows"])}

    # The ZIP embeds an export timestamp, so it lives in its own (non-diffed) file.
    with open(os.path.join(FIXTURE_DIR, "export.zip"), "wb") as fh:
        fh.write(export_to_csv())

    with open(os.path.join(FIXTURE_DIR, "expected.json"), "w", encoding="utf-8") as fh:
        json.dump(expected, fh, indent=1, default=str, sort_keys=True)
    print(f"wrote fixtures to {FIXTURE_DIR}: stats={expected['stats']}")


if __name__ == "__main__":
    main()
