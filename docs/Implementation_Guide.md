# Relatenta — Implementation Guide

## Architecture

Single Streamlit process. No separate backend. The Streamlit app imports service modules directly.

```
streamlit_app.py          (UI, user interaction)
  |
  +-- app/db.py           (single in-memory SQLite engine, StaticPool)
  +-- app/models.py       (SQLAlchemy ORM table definitions)
  +-- app/crud.py         (data operations, edge computation)
  +-- app/connectors_openalex.py  (OpenAlex API client)
  +-- app/services_graph.py       (4-layer graph builder)
  +-- app/services_heatmap.py     (heatmap matrix generator)
  +-- app/services_export.py      (CSV/ZIP export)
```

### Design Decisions

- **No Actor concept.** A single global in-memory database simplifies the code and eliminates stale session-state bugs.
- **StaticPool for SQLite.** Ensures all sessions share the same in-memory database connection.
- **`init_db()` on every script run.** Guarantees tables exist even after process restarts.

---

## Module Reference

### `app/db.py`

Single in-memory SQLite engine with `StaticPool`.

| Function | Description |
|----------|-------------|
| `get_db()` | Context manager yielding a SQLAlchemy session |
| `init_db()` | Ensure tables exist (called on every Streamlit run) |
| `reset_db()` | Dispose engine and recreate empty database |
| `get_stats()` | Return row counts for main tables |

### `app/models.py`

12 SQLAlchemy models: `Author`, `AuthorAlias`, `Organization`, `Venue`, `Work`, `WorkAuthor`, `WorkAffiliation`, `Keyword`, `WorkKeyword`, `CoauthorEdge`, `OrgEdge`, `NationEdge`, `MergeLog`.

### `app/crud.py`

| Function | Description |
|----------|-------------|
| `upsert_work_from_openalex(db, w)` | Insert/update a work from OpenAlex JSON |
| `get_or_create_author(db, name)` | Find or create author by normalized name |
| `get_or_create_keyword(db, term)` | Find or create keyword |
| `get_or_create_org(db, name)` | Find or create organization |
| `recompute_coauthor_edges(db)` | Rebuild co-authorship edges |
| `recompute_org_edges(db)` | Rebuild organization edges |
| `recompute_nation_edges(db)` | Rebuild nation edges |
| `merge_authors(db, kept_id, removed_id)` | Merge duplicate authors |

### `app/connectors_openalex.py`

| Function | Description |
|----------|-------------|
| `search_authors_by_name(name)` | Search with H-index, ORCID, topics |
| `list_author_works(author_id)` | Fetch paginated works |

### `app/services_graph.py`

`build_graph(db, layer, year_min, year_max, edge_min_weight, focus_ids, focus_only)`

Layers: `authors`, `keywords`, `orgs`, `nations`.
Returns `{"nodes": [...], "edges": [...]}`.

### `app/services_heatmap.py`

| Function | Description |
|----------|-------------|
| `author_keyword_heat(db, year_min, year_max)` | Top-30 authors x top-30 keywords |
| `nation_nation_heat(db, year_min, year_max)` | Nation-nation collaboration matrix |

### `app/services_export.py`

`export_to_csv()` — Returns ZIP bytes containing CSV files for all tables.

---

## Extension Points

### Adding a New Graph Layer

1. Add `elif layer == "your_layer":` in `app/services_graph.py`
2. Add the layer name to the selectbox in `streamlit_app.py`

### Adding a New Data Connector

1. Create `app/connectors_yourservice.py`
2. Add UI in the sidebar section of `streamlit_app.py`

### Adding a New Heatmap Type

1. Add a function in `app/services_heatmap.py`
2. Add the type to the selectbox in `streamlit_app.py`

---

## Deployment on Streamlit Cloud

1. Push to GitHub
2. Connect at [share.streamlit.io](https://share.streamlit.io/)
3. Set `streamlit_app.py` as the main file
4. No secrets or environment variables required

### Limitations

- In-memory database — data lost on session end
- Single-threaded — large ingestions may be slow
- Session timeout — ~15 minutes of inactivity
- Memory limit — ~1 GB per app

---

## License

MIT License.
