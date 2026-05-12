"""Regression tests for the four service modules.

Pinned to make sure the v1.1 N+1 refactors (services_graph keywords layer,
services_heatmap, services_insight.recommend_collaborators) keep their
existing semantics under future changes.
"""
from __future__ import annotations

from app.db import get_db
from app.services_graph import build_graph
from app.services_heatmap import author_keyword_heat, nation_nation_heat
from app.services_insight import (
    detect_bursts,
    detect_communities,
    find_shortest_path,
    recommend_collaborators,
)


def test_authors_layer_graph(sample_dataset):
    with get_db() as db:
        g = build_graph(db, "authors", 2000, 2025, 1.0, None, False)
    labels = {n["label"] for n in g["nodes"]}
    # Only the connected triangle has edges weight>=1
    assert {"Alice", "Bob", "Carol"}.issubset(labels)
    assert len(g["edges"]) == 3  # triangle


def test_keywords_layer_graph(sample_dataset):
    with get_db() as db:
        g = build_graph(db, "keywords", 2000, 2025, 1.0, None, False)
    labels = {n["label"] for n in g["nodes"]}
    assert labels == {"machine learning", "neural network", "data science"}
    assert len(g["edges"]) == 3  # each pair co-occurs


def test_keywords_focus_only(sample_dataset):
    """Focus Only should restrict to works containing the focus keyword."""
    ml_id = sample_dataset.k_ids["machine learning"]
    with get_db() as db:
        g = build_graph(db, "keywords", 2000, 2025, 1.0, [ml_id], focus_only=True)
    # All three keywords co-occur in ML-containing works (P0, P2, P3)
    labels = {n["label"] for n in g["nodes"]}
    assert "machine learning" in labels


def test_orgs_layer_graph(sample_dataset):
    with get_db() as db:
        g = build_graph(db, "orgs", 2000, 2025, 1.0, None, False)
    labels = {n["label"] for n in g["nodes"]}
    assert {"MIT", "Cambridge"}.issubset(labels)


def test_nations_layer_graph(sample_dataset):
    with get_db() as db:
        g = build_graph(db, "nations", 2000, 2025, 1.0, None, False)
    labels = {n["label"] for n in g["nodes"]}
    assert {"US", "GB"}.issubset(labels)


def test_author_keyword_heatmap(sample_dataset):
    with get_db() as db:
        hm = author_keyword_heat(db, 2000, 2025)
    assert len(hm["rows"]) == 4
    assert len(hm["cols"]) == 3
    # data is a list of lists, one row per author
    assert all(len(row) == 3 for row in hm["data"])


def test_nation_nation_heatmap(sample_dataset):
    with get_db() as db:
        hm = nation_nation_heat(db, 2000, 2025)
    # Symmetric matrix
    n = len(hm["rows"])
    assert n == len(hm["cols"])
    for i in range(n):
        for j in range(n):
            assert hm["data"][i][j] == hm["data"][j][i]


def test_recommend_collaborators_surfaces_disconnected_match(sample_dataset):
    """Dave is disconnected from Alice but shares all three keywords."""
    alice_id = sample_dataset.a_ids["Alice"]
    with get_db() as db:
        recs = recommend_collaborators(db, alice_id, top_n=5)
    names = [r["author_name"] for r in recs]
    assert "Dave" in names
    dave = next(r for r in recs if r["author_name"] == "Dave")
    # All 3 keywords overlap → Jaccard should be > 0.5
    assert dave["jaccard_similarity"] > 0.5
    # Disconnected → path_length == -1
    assert dave["path_length"] == -1


def test_community_detection_runs(sample_dataset):
    with get_db() as db:
        result = detect_communities(db, "authors", 1.0, None, None)
    # The triangle is one community; Dave is isolated so excluded from the
    # author co-author graph.
    assert result["num_communities"] >= 1
    assert 0.0 <= result["modularity"] <= 1.0 or result["modularity"] == 0.0


def test_burst_detection_returns_per_keyword_rows(sample_dataset):
    with get_db() as db:
        results = detect_bursts(db, window_years=2, min_papers=1)
    # 3 keywords each appear in 2 papers; results should be non-empty.
    assert len(results) >= 1
    for r in results:
        assert {"keyword", "burst_score", "status", "trend"}.issubset(r)


def test_shortest_path_inside_triangle(sample_dataset):
    alice = sample_dataset.a_ids["Alice"]
    carol = sample_dataset.a_ids["Carol"]
    with get_db() as db:
        result = find_shortest_path(db, alice, carol)
    assert result["path_exists"] is True
    # Alice -- Carol is a direct edge in the triangle.
    assert result["path_length"] == 1


def test_shortest_path_to_disconnected(sample_dataset):
    alice = sample_dataset.a_ids["Alice"]
    dave = sample_dataset.a_ids["Dave"]
    with get_db() as db:
        result = find_shortest_path(db, alice, dave)
    # Dave has no co-author edges → not in the graph → message returned
    assert result["path_exists"] is False
