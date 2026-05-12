"""Connector-layer tests that do NOT hit the network.

We only validate parsing/format helpers and the polite-pool / session wiring;
HTTP calls themselves are intentionally not exercised here so the suite stays
hermetic.
"""
from __future__ import annotations

from app import connectors_openalex as oa


def test_detect_query_type_orcid_bare():
    assert oa.detect_query_type("0000-0001-2345-6789") == "orcid"


def test_detect_query_type_orcid_url():
    assert oa.detect_query_type("https://orcid.org/0000-0001-2345-6789") == "orcid"


def test_detect_query_type_google_scholar():
    assert oa.detect_query_type("https://scholar.google.com/citations?user=ABC") == "google_scholar"


def test_detect_query_type_plain_name():
    assert oa.detect_query_type("Geoffrey Hinton") == "name"


def test_format_author_result_minimal_payload():
    item = {"id": "https://openalex.org/A123", "display_name": "Test Author"}
    out = oa._format_author_result(item)
    assert out["id"] == "https://openalex.org/A123"
    assert out["display_name"] == "Test Author"
    assert out["h_index"] == 0
    assert out["top_concepts"] == []


def test_format_author_result_rich_payload():
    item = {
        "id": "https://openalex.org/A1",
        "display_name": "Test",
        "works_count": 100,
        "cited_by_count": 5000,
        "orcid": "https://orcid.org/0000-0001-2345-6789",
        "summary_stats": {"h_index": 42, "i10_index": 60},
        "last_known_institution": {
            "display_name": "MIT", "country_code": "US", "type": "education"
        },
        "x_concepts": [
            {"display_name": "AI", "score": 0.9},
            {"display_name": "ML", "score": 0.7},
            {"display_name": "Robotics", "score": 0.4},
            {"display_name": "Vision", "score": 0.2},
        ],
    }
    out = oa._format_author_result(item)
    assert out["h_index"] == 42
    assert out["last_known_institution"] == "MIT"
    assert out["institution_country"] == "US"
    # Only the top 3 concepts are kept and they are sorted by score desc.
    assert [c["name"] for c in out["top_concepts"]] == ["AI", "ML", "Robotics"]


def test_polite_helper_no_mailto_by_default(monkeypatch):
    """When OPENALEX_MAILTO is unset, _polite must not inject a mailto param."""
    monkeypatch.setattr(oa, "_OPENALEX_MAILTO", "")
    assert "mailto" not in oa._polite({"search": "x"})


def test_polite_helper_injects_mailto_when_set(monkeypatch):
    monkeypatch.setattr(oa, "_OPENALEX_MAILTO", "ops@example.com")
    out = oa._polite({"search": "x"})
    assert out["mailto"] == "ops@example.com"
    # Original args preserved
    assert out["search"] == "x"


def test_session_has_user_agent():
    ua = oa._SESSION.headers.get("User-Agent", "")
    assert ua.startswith("Relatenta/")
