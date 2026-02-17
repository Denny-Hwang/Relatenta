# Relatenta

**Research Relationship Visualization** — Visualize collaboration networks among researchers, institutions, keywords, and nations using interactive network graphs.

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
- **CSV Import/Export** — Bulk import and export of works, authors, affiliations, and keywords
- **Focus Filtering** — Ego-network analysis centered on specific nodes
- **Streamlit Cloud Ready** — In-memory database with ZIP export/restore for data persistence

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/Denny-Hwang/Relatenta.git
cd Relatenta

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt
```

### 2. Run

```bash
streamlit run streamlit_app.py
```

The app opens at **http://localhost:8501**.

### 3. Usage

1. **Search** for a researcher name in the sidebar (e.g., "Geoffrey Hinton")
2. **Review** the search results — check institution, H-index, and topics to disambiguate
3. **Select** one or more authors and click "Ingest Selected"
4. **Visualize** — go to the Graph tab, pick a layer, click "Build Graph"
5. **Export** your data as ZIP before closing the browser

---

## Architecture

```
streamlit_app.py              (UI, sidebar, tabs)
  |
  +-- app/db.py               (single in-memory SQLite engine)
  +-- app/models.py            (SQLAlchemy ORM, 12 tables)
  +-- app/crud.py              (data ops, edge computation)
  +-- app/connectors_openalex.py  (OpenAlex API client)
  +-- app/services_graph.py    (4-layer network graph builder)
  +-- app/services_heatmap.py  (heatmap matrix generator)
  +-- app/services_export.py   (CSV/ZIP export)
```

Single Streamlit process. No separate backend server. One in-memory SQLite database shared across the session.

---

## Data Persistence

This app uses an **in-memory database**. Data exists only during the active browser session.

| Action | How |
|--------|-----|
| **Save** | Sidebar > "Export CSV" — downloads a ZIP with all tables |
| **Restore** | Sidebar > "Restore from Export" — upload a previously exported ZIP |

---

## Visualization Layers

| Layer | Nodes | Edges | Use Case |
|-------|-------|-------|----------|
| **Co-authorship** | Authors | Shared publications | Identify collaborators |
| **Keyword Co-occurrence** | Keywords | Papers with both topics | Map research landscapes |
| **Institutional** | Organizations | Joint publications | Discover partnerships |
| **National** | Countries | International co-authorships | Analyze global patterns |

---

## Tech Stack

- **App:** Streamlit, PyVis (network graphs), Plotly (heatmaps)
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
