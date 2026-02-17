# Relatenta — User Manual

## Overview

Relatenta visualizes research collaboration networks. Search for researchers via OpenAlex, ingest their publication data, and explore interactive network graphs and heatmaps.

## Prerequisites

- Python 3.10+
- Modern web browser
- Internet connection (for OpenAlex)

## Installation

```bash
git clone https://github.com/Denny-Hwang/Relatenta.git
cd Relatenta
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Running

```bash
streamlit run streamlit_app.py
```

Opens at http://localhost:8501.

---

## Workflow

### 1. Search for Authors

In the sidebar under "OpenAlex Search":

1. Enter a researcher name (e.g., "Geoffrey Hinton")
2. Click "Search"
3. Review the results — each card shows:
   - Paper count, citation count
   - Institution and country
   - H-index
   - ORCID (if available)
   - Top 3 research topics with confidence scores

**Disambiguation:** Many researchers share the same name. Use institution, H-index, and research topics to identify the correct person before ingesting.

### 2. Ingest Data

1. Select one or more authors from the search results
2. Adjust "Max works per author" (default: 200)
3. Click "Ingest Selected"
4. Wait for ingestion to complete — the sidebar shows a summary of imported works

You can search and ingest multiple times to build up your dataset.

### 3. Visualize — Graph Tab

1. Select a layer: `authors`, `keywords`, `orgs`, or `nations`
2. Set year range and minimum edge weight
3. Click "Build Graph"

**Graph interaction:**
- Drag to pan the view
- Click nodes to select
- Scroll to zoom
- Press SPACE to toggle physics simulation

**Focus Mode (optional):**
- Use "Find Author IDs" / "Find Keyword IDs" expanders to look up IDs
- Enter comma-separated IDs in the focus input
- Choose "Full Network" (highlight) or "Focus Only" (isolate)

### 4. Visualize — Heatmaps Tab

1. Select type: `author_keyword` or `nation_nation`
2. Set year range
3. Click "Compute Heatmap"
4. Darker colors = stronger relationships

### 5. Export / Restore

- **Export:** Click "Export CSV" in the sidebar to download a ZIP file
- **Restore:** Upload a previously exported ZIP via "Restore from Export"
- **Clear:** Click "Clear All" to reset the database

---

## CSV Import

You can also import data from CSV files:

| Type | Required Columns |
|------|-----------------|
| `works` | title, doi, year, venue, type, language, keywords (semicolon-separated) |
| `authors` | work_title, work_doi, author_name, position |
| `affiliations` | work_title, work_doi, author_name, org_name, country_code |
| `keywords` | work_title, work_doi, term |

Import works first, then authors/affiliations/keywords (they link to works by DOI or title).

---

## Tips

- Start with 1-2 researchers and expand gradually
- Use year filters and edge weight thresholds to reduce graph complexity
- For large datasets (500+ papers), use Focus Only mode
- Always export before closing the browser

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Graph too cluttered | Increase edge weight minimum |
| No nodes in graph | Lower edge weight or widen year range |
| Data lost after refresh | Use Export/Restore to persist data |
| Slow ingestion | Reduce max works per author |

---

## License

MIT License.
