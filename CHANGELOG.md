# Changelog

All notable changes to Relatenta will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and [Semantic Versioning](https://semver.org/).

---

## [1.2.0] - 2026-09-08

### Summary
GitHub Pages port — the full GUI now also runs as a static site in the browser
(`web/`), deployed automatically to https://denny-hwang.github.io/Relatenta/.
The Streamlit app is unchanged.

### Added
- **`web/` static app** (vanilla ES modules, no build step): sidebar search /
  ingest (OpenAlex name + ORCID), CSV import, ZIP export/restore, Graph,
  Heatmaps, Report and Insights tabs, EN/KO language toggle.
- **Interactive network view** built directly on vis-network (no iframe):
  hover tooltips, neighbour highlighting, inspector panel (neighbours, papers,
  "Focus on this node"), find-and-zoom, physics toggle, fit, labels toggle,
  PNG export, fullscreen, stabilisation progress, keyboard shortcuts
  (Space / F / Esc), ForceAtlas2 option and a performance mode for large graphs.
- **Analytics ported 1:1** — graph builder, heatmaps, report, burst detection,
  collaborator recommendation, shortest path, research gaps, strategic diagram,
  thematic evolution; Louvain community detection implemented in JS.
- **Browser persistence** — dataset saved in IndexedDB, survives refreshes.
- **Parity test suite** (`web/tests`): fixtures generated from the Python
  service layer, asserted against the JS port with `node --test`; a Playwright
  browser smoke test drives every tab.
- **CI/CD** — `pages.yml` deploys `web/` on push to `main`; `test.yml` gained a
  `web` job that regenerates fixtures and runs the parity tests.

### Not available in the static version
- Google Scholar URL lookup (server-side scraping; blocked by CORS in browsers)
- Shared persistent storage via `DATABASE_URL`

---

## [1.1.0] - 2026-03-13

### Summary
Research Insight Enhancement — transforms Relatenta from a visualization tool into a research insight platform. Adds 7 new analysis features in a new "Insights" tab.

### Added
- **New "Insights" tab** with 7 analysis types
- **Community Detection** — Louvain algorithm identifies research clusters with color-coded visualization
- **Burst Detection (Emerging Topics)** — Growth-rate analysis identifies keywords with sudden recent increase
- **Collaborator Recommendation** — Multi-signal scoring (Jaccard keyword similarity + network proximity + complementarity) suggests potential collaborators
- **Shortest Path Analysis** — BFS-based path finding between any two researchers in the co-authorship network
- **Research Gap Detection** — Structural hole analysis on keyword network identifies under-explored research combinations
- **Strategic Diagram** — Callon's centrality-density map classifies themes as Motor / Niche / Emerging / Basic
- **Thematic Evolution** — Sankey diagram showing how keyword clusters evolve, merge, split across time periods
- **Community-colored graph visualization** — 15-color palette for community detection overlay
- **Development log system** — VERSION file, CHANGELOG.md, docs/devlog/ directory

### New Files
- `app/services_insight.py` — All 7 insight analysis functions (standalone module)
- `VERSION` — Semantic version tracking
- `CHANGELOG.md` — Project changelog
- `docs/devlog/v1.0.0_Feature_Specification.md` — v1.0.0 feature documentation
- `docs/devlog/v1.1.0_Enhancement_Development_Spec.md` — v1.1.0 development specification

### Modified
- `streamlit_app.py` — Added Insights tab, community color support in PyVis graph

### Dependencies
- No new dependencies (uses NetworkX built-in `louvain_communities`, available since NetworkX 3.0)

### Benchmarked From
| Feature | Benchmark Service |
|---------|------------------|
| Community Detection | VOSviewer |
| Burst Detection | CiteSpace |
| Collaborator Recommendation | ResearchRabbit |
| Shortest Path | Inciteful (Literature Connector) |
| Research Gap Detection | Inciteful + SciSpace |
| Strategic Diagram | SciMAT + Bibliometrix |
| Thematic Evolution | Bibliometrix |

---

## [1.0.0] - 2026-03-13

### Summary
Initial stable release. Research Relationship Visualization platform with 4-layer network graphs and heatmap analysis.

### Features
- **OpenAlex Author Search** — Enhanced disambiguation with H-index, citations, ORCID, and research topics
- **4-Layer Network Visualization**
  - Co-authorship network (authors as nodes, shared publications as edges)
  - Keyword co-occurrence network (research topics and their relationships)
  - Institutional collaboration network (organizations and joint publications)
  - International collaboration network (countries and cross-border co-authorship)
- **Heatmap Analysis**
  - Author-keyword collaboration matrix (top 30x30)
  - Nation-nation collaboration matrix (symmetric)
- **Interactive Graph (PyVis)**
  - Force-directed layout with Barnes-Hut physics engine
  - Node sizing by connection count, edge width by strength
  - Color-coded node types with focus highlighting
  - Interactive controls (drag, zoom, physics toggle)
- **Focus Filtering** — Ego-network analysis (highlight or isolate specific nodes)
- **Analytic Reports**
  - Publication trend (papers per year)
  - Top authors, keywords, venues, countries
  - Top collaborator pairs and keyword co-occurrence pairs
  - Highlight papers (top cited)
  - Simplified collaboration network graph
- **Data Management**
  - CSV/ZIP export containing all tables
  - ZIP restore with automated relationship reconstruction
  - Database reset
  - Edge recomputation after data changes
- **Demo Data** — Geoffrey Hinton auto-load on first visit

### Tech Stack
- Python 3.10+, Streamlit 1.28+, PyVis 0.3.2, Plotly 5.15+
- In-memory SQLite + SQLAlchemy 2.0+
- NetworkX 3.0+, Pandas 2.0+
- OpenAlex API (250M+ scholarly records)

### Architecture
- Single Streamlit process (no separate backend)
- In-memory SQLite with StaticPool (session-isolated)
- 13 SQLAlchemy ORM tables
- Pre-computed edge tables for fast graph rendering
