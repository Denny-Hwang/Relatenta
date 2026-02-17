# Relatenta

**Multi-Actor Research Relationship Visualization Platform** — Visualize collaboration networks among researchers, institutions, keywords, and nations using interactive network graphs.

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)](https://streamlit.io)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

Relatenta ingests scholarly publication data from the [OpenAlex API](https://openalex.org/) (250M+ records) or CSV files, and renders **4-layer network graphs** and **heatmaps** that reveal collaboration patterns across researchers, topics, organizations, and countries.

### Key Features

- **OpenAlex Author Search** — Enhanced disambiguation with H-index, citations, ORCID, and research topics
- **4-Layer Network Visualization** — Co-authorship, keyword co-occurrence, institutional collaboration, and international collaboration
- **Heatmap Analysis** — Author-keyword and nation-nation collaboration matrices
- **Multi-Actor Architecture** — Manage multiple independent analysis projects in parallel
- **CSV Import/Export** — Bulk import and export of works, authors, affiliations, and keywords
- **Focus Filtering** — Ego-network analysis centered on specific nodes
- **Streamlit Cloud Ready** — In-memory database with ZIP export/restore for data persistence

---

## Folder Structure

```
Relatenta/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── streamlit_app.py             # Streamlit app (single-process, no separate backend)
├── app/                         # Core logic package
│   ├── __init__.py
│   ├── db.py                    # In-memory SQLite engine & session management
│   ├── models.py                # SQLAlchemy ORM models (12 tables)
│   ├── crud.py                  # CRUD operations & edge recomputation
│   ├── connectors_openalex.py   # OpenAlex API connector
│   ├── services_graph.py        # Network graph builder (4 layers)
│   ├── services_heatmap.py      # Heatmap data generator
│   └── services_export.py       # CSV/ZIP export service
├── databases/                   # (unused in cloud mode, kept for compatibility)
│   └── .gitkeep
└── docs/                        # Documentation
    ├── Implementation_Guide.md
    └── User_manual.md
```

---

## Architecture

```
┌──────────────────────────────────────────────┐
│            Streamlit Application              │
│            (streamlit_app.py)                 │
│                                               │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐ │
│  │ Actor    │  │ Graph &  │  │ Data       │ │
│  │ Mgmt UI  │  │ Heatmap  │  │ Ingestion  │ │
│  │          │  │ (PyVis)  │  │ & Export   │ │
│  └─────┬────┘  └────┬─────┘  └─────┬──────┘ │
│        │            │              │         │
│  ┌─────▼────────────▼──────────────▼───────┐ │
│  │        app/ (service layer)             │ │
│  │  db.py · crud.py · models.py            │ │
│  │  services_graph · services_heatmap      │ │
│  │  services_export · connectors_openalex  │ │
│  └─────────────────┬───────────────────────┘ │
└────────────────────┼─────────────────────────┘
                     │
       ┌─────────────┼──────────────┐
       │             │              │
┌──────▼──────┐ ┌───▼──────────┐ ┌─▼───────────┐
│ In-Memory   │ │ OpenAlex API │ │ CSV Files   │
│ SQLite      │ │ (250M+ recs) │ │ (Import /   │
│ (per actor) │ │              │ │  Export)    │
└─────────────┘ └──────────────┘ └─────────────┘
```

> **Note:** There is no separate backend server. Streamlit calls all service functions directly. Each actor gets its own in-memory SQLite database within the Streamlit process.

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Denny-Hwang/Relatenta.git
cd Relatenta

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run

```bash
streamlit run streamlit_app.py
```

The app opens at **http://localhost:8501**.

### 3. Basic Workflow

1. **Create an Actor** — Sidebar > "Create New Actor" > enter a project name
2. **Ingest Data** — Search for a researcher via OpenAlex > select > "Ingest Selected"
3. **Visualize** — Go to the "Graph" tab > pick a layer > "Build Graph"
4. **Export** — Click "Export CSV" to download your data as a ZIP file
5. **Restore** — Next session, upload the ZIP via "Restore from Export"

---

## Data Persistence

This app uses **in-memory SQLite** databases. Data exists only during the active browser session.

| Action | How |
|--------|-----|
| **Save data** | Sidebar > "Export CSV" — downloads a ZIP with all tables |
| **Restore data** | Sidebar > "Restore from Export" — upload a previously exported ZIP |

> Always export your data before closing the browser.

---

## Database Schema

12 tables managed via SQLAlchemy ORM:

| Table | Description |
|-------|-------------|
| `authors` | Researcher info (name, ORCID) |
| `author_aliases` | Name variants for disambiguation |
| `organizations` | Institutions and universities |
| `venues` | Journals and conferences |
| `works` | Publication metadata |
| `work_authors` | Work-author relationships |
| `work_affiliations` | Work-author-organization links |
| `keywords` | Keywords and concepts |
| `work_keywords` | Work-keyword relationships |
| `coauthor_edges` | Co-authorship network edges |
| `org_edges` | Institutional collaboration edges |
| `nation_edges` | International collaboration edges |
| `merges` | Entity merge audit log |

---

## Visualization Layers

| Layer | Nodes | Edges | Use Case |
|-------|-------|-------|----------|
| **Co-authorship** | Authors | Shared publications | Identify research collaborators |
| **Keyword Co-occurrence** | Keywords | Papers with both topics | Map research landscapes |
| **Institutional** | Organizations | Joint publications | Discover partnerships |
| **National** | Countries | International co-authorships | Analyze global patterns |

---

## Tech Stack

- **Frontend & App:** Streamlit, PyVis (network graphs), Plotly (heatmaps only)
- **Database:** In-memory SQLite + SQLAlchemy ORM
- **Data Source:** OpenAlex API
- **Language:** Python 3.10+

---

## Documentation

- [User Manual](docs/User_manual.md) — Step-by-step usage guide
- [Implementation Guide](docs/Implementation_Guide.md) — Technical details and extension guide

---

## Contributing

1. Fork this repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
