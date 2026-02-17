# Relatenta — Implementation Guide

## Overview

This document describes the technical architecture, module responsibilities, and extension points for Relatenta. It is intended for developers who want to understand, modify, or extend the codebase.

---

## Architecture

Relatenta runs as a single Streamlit process. There is no separate backend server. The Streamlit app imports service modules directly.

```
streamlit_app.py          (UI, user interaction, session state)
  |
  +-- app/db.py           (in-memory SQLite engine per actor)
  +-- app/models.py       (SQLAlchemy ORM table definitions)
  +-- app/crud.py         (data operations, edge computation)
  +-- app/connectors_openalex.py  (OpenAlex API client)
  +-- app/services_graph.py       (4-layer graph builder)
  +-- app/services_heatmap.py     (heatmap matrix generator)
  +-- app/services_export.py      (CSV/ZIP export)
```

### Key Design Decisions

- **No FastAPI backend.** Streamlit Cloud only runs one process. All service calls are direct Python function imports.
- **In-memory SQLite.** Each actor gets a `sqlite://` (in-memory) engine. Data lives only during the session. Export/restore via CSV ZIP provides persistence.
- **PyVis only for network graphs.** Plotly is used only for heatmap visualization (`px.imshow`).

---

## Module Reference

### `app/db.py` — Database Layer

Manages in-memory SQLite engines, one per actor.

| Function | Description |
|----------|-------------|
| `get_db(actor_name)` | Context manager returning a SQLAlchemy session |
| `init_db(actor_name)` | Creates tables for an actor (idempotent) |
| `list_actors()` | Returns list of active actor names |
| `delete_actor_db(actor_name)` | Disposes engine and removes from cache |
| `get_actor_stats(actor_name)` | Returns row counts for all tables |

Internal state is stored in module-level dicts `_engines` and `_session_factories`.

### `app/models.py` — ORM Models

12 SQLAlchemy models:

| Model | Table | Primary Key |
|-------|-------|-------------|
| `Author` | `authors` | `id` (int, auto) |
| `AuthorAlias` | `author_aliases` | `id` (int, auto) |
| `Organization` | `organizations` | `id` (int, auto) |
| `Venue` | `venues` | `id` (int, auto) |
| `Work` | `works` | `id` (int, auto) |
| `WorkAuthor` | `work_authors` | `(work_id, author_id)` |
| `WorkAffiliation` | `work_affiliations` | `id` (int, auto) |
| `Keyword` | `keywords` | `id` (int, auto) |
| `WorkKeyword` | `work_keywords` | `(work_id, keyword_id)` |
| `CoauthorEdge` | `coauthor_edges` | `(a_id, b_id)` |
| `OrgEdge` | `org_edges` | `(org1_id, org2_id)` |
| `NationEdge` | `nation_edges` | `(n1, n2)` |
| `MergeLog` | `merges` | `id` (int, auto) |

### `app/crud.py` — Data Operations

| Function | Description |
|----------|-------------|
| `upsert_work_from_openalex(db, w)` | Insert or update a work from OpenAlex JSON |
| `get_or_create_author(db, name)` | Find existing author by normalized name or create new |
| `get_or_create_keyword(db, term)` | Find existing keyword or create new |
| `get_or_create_org(db, name)` | Find existing organization or create new |
| `get_or_create_venue(db, name, ...)` | Find existing venue or create new |
| `recompute_coauthor_edges(db)` | Rebuild co-authorship edges from `work_authors` |
| `recompute_org_edges(db)` | Rebuild organization edges from `work_affiliations` |
| `recompute_nation_edges(db)` | Rebuild nation edges from `work_affiliations` |
| `merge_authors(db, kept_id, removed_id, ...)` | Merge duplicate authors |

### `app/connectors_openalex.py` — OpenAlex API

| Function | Description |
|----------|-------------|
| `search_authors_by_name(name)` | Search authors with disambiguation info (H-index, ORCID, topics) |
| `list_author_works(author_id)` | Fetch paginated works for an author |

### `app/services_graph.py` — Graph Builder

`build_graph(db, layer, year_min, year_max, edge_min_weight, focus_ids, focus_only)`

Supports 4 layers: `authors`, `keywords`, `orgs`, `nations`.

Returns `{"nodes": [...], "edges": [...]}` where each node has `id`, `label`, `type`, and `focus` fields, and each edge has `source`, `target`, `weight`.

Focus modes:
- **Full Network:** All nodes shown, focus nodes get `type: "focus_*"`
- **Focus Only:** Only focus nodes and their direct neighbors are included

### `app/services_heatmap.py` — Heatmap Generator

| Function | Description |
|----------|-------------|
| `author_keyword_heat(db, year_min, year_max)` | Top-30 authors x top-30 keywords matrix |
| `nation_nation_heat(db, year_min, year_max)` | Nation-nation collaboration matrix |

Returns `{"rows": [...], "cols": [...], "data": [[...]]}`.

### `app/services_export.py` — CSV Export

`export_actor_to_csv(actor_name)` returns a ZIP file (as bytes) containing CSV files for all tables plus a metadata summary.

---

## Extension Points

### Adding a New Graph Layer

1. Add a new `elif layer == "your_layer":` branch in `app/services_graph.py`
2. Query the relevant models and build `nodes` and `edges` lists
3. Add the layer name to the selectbox in `streamlit_app.py` (`graph_tab` function)

### Adding a New Data Connector

1. Create `app/connectors_yourservice.py`
2. Implement functions that return data in a format compatible with `crud.upsert_work_from_openalex()`
3. Add a UI section in `sidebar_ingest()` in `streamlit_app.py`

### Adding a New Heatmap Type

1. Add a new function in `app/services_heatmap.py`
2. Return the standard `{"rows": [...], "cols": [...], "data": [...]}` format
3. Add the type to the selectbox in `heatmap_tab()` in `streamlit_app.py`

---

## Deployment on Streamlit Cloud

1. Push the repository to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io/)
3. Connect the repository and set `streamlit_app.py` as the main file
4. No environment variables or secrets are required
5. The app will auto-deploy on each push

### Limitations on Streamlit Cloud

- No persistent filesystem — data is in-memory only
- Single-threaded — large ingestions may be slow
- Session timeout — inactive sessions are terminated after ~15 minutes
- Memory limit — approximately 1 GB per app

---

## Testing

### Manual Test Checklist

- [ ] Create an actor
- [ ] Search and ingest an author from OpenAlex
- [ ] Build a graph for each layer (authors, keywords, orgs, nations)
- [ ] Compute both heatmap types
- [ ] Export data as ZIP
- [ ] Delete the actor
- [ ] Create a new actor and restore from ZIP
- [ ] Verify restored data matches original

### Running Locally

```bash
streamlit run streamlit_app.py
```

Open http://localhost:8501 and walk through the checklist above.

---

## License

This project is licensed under the MIT License.
