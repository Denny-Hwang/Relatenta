# Relatenta — User Manual

## Overview

Relatenta is a research relationship visualization service. It ingests publication data from OpenAlex or CSV files and generates interactive network graphs and heatmaps showing collaborations between authors, keywords, organizations, and nations.

## System Architecture

- **Application:** Single Streamlit process (no separate backend)
- **Database:** In-memory SQLite (one per actor, session-scoped)
- **Visualization:** PyVis for network graphs, Plotly for heatmaps
- **Data Source:** OpenAlex API and CSV files

## Prerequisites

- Python 3.10 or higher
- pip package manager
- Modern web browser
- Internet connection (for OpenAlex data ingestion)

## Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/Denny-Hwang/Relatenta.git
cd Relatenta
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv

# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Run the Application

```bash
streamlit run streamlit_app.py
```

The app opens automatically at http://localhost:8501.

---

## Using the Application

### 1. Actor Management

An **Actor** represents an independent analysis project with its own database. Think of it as a workspace.

**Create an Actor:**
1. In the left sidebar, expand "Create New Actor"
2. Enter a name (e.g., "AI Research Team", "Climate Science")
3. Click "Create"

**Select an Actor:**
- Use the dropdown under "Select Active Actor" in the sidebar

**Delete an Actor:**
- Click "Delete" next to the selected actor
- Enter the password (`8888`) to confirm

### 2. Data Ingestion

#### Option A: OpenAlex Import (Recommended)

1. In the sidebar under "Data Ingestion," enter a researcher name
2. Click "Search"
3. Review results — each card shows:
   - Paper count and citation count
   - Institution and country
   - Research topics
4. Select one or more authors from the list
5. Adjust "Max works per author" (default: 200)
6. Click "Ingest Selected"

#### Option B: CSV Import

1. Select a data type from the dropdown: `works`, `authors`, `affiliations`, or `keywords`
2. Upload a CSV file with the correct columns (see CSV Format below)
3. Click "Import CSV"

#### Option C: Restore from Export

1. Under "Restore from Export," upload a ZIP file from a previous export
2. Click "Restore Data"

### 3. Graph Visualization

Navigate to the **Graph** tab:

1. **Select Layer:**
   - `authors` — Co-authorship network
   - `keywords` — Keyword co-occurrence
   - `orgs` — Organization collaborations
   - `nations` — International collaborations

2. **Set Filters:**
   - Year range (e.g., 2015-2025)
   - Minimum edge weight (filters weak connections)

3. **Focus Mode (optional):**
   - Use the built-in search helper to find entity IDs
   - Enter comma-separated IDs in the focus input
   - Choose "Full Network" (highlight) or "Focus Only" (isolate)

4. Click **"Build Graph"**

5. **Graph Interaction:**
   - Drag nodes to rearrange
   - Hover over nodes for details
   - Scroll to zoom in/out
   - Press SPACE to toggle physics simulation

### 4. Heatmap Analysis

Navigate to the **Heatmaps** tab:

1. Select type: `author_keyword` or `nation_nation`
2. Set year range
3. Click "Compute Heatmap"
4. Hover over cells for values; darker colors = stronger relationships

### 5. Data Export

- Click "Export CSV" in the sidebar to download all data as a ZIP file
- The ZIP contains CSV files for works, authors, organizations, keywords, affiliations, venues, and metadata

---

## CSV Format Reference

### works.csv

```csv
title,doi,year,venue,type,language,keywords
"Deep Learning in Neural Networks",10.1016/j.neunet.2014.09.003,2015,"Neural Networks","journal-article","en","deep learning;neural networks"
```

### authors.csv

```csv
work_title,work_doi,author_name,position
"Deep Learning in Neural Networks",,John Smith,0
```

### affiliations.csv

```csv
work_title,work_doi,author_name,org_name,country_code
"Deep Learning in Neural Networks",,John Smith,MIT,US
```

### keywords.csv

```csv
work_title,work_doi,term
"Deep Learning in Neural Networks",,artificial intelligence
```

---

## Data Persistence

**Important:** This app uses in-memory databases. All data is lost when the session ends.

**To preserve your work:**
1. Click "Export CSV" to download a ZIP file
2. Store the ZIP file locally
3. In your next session, use "Restore from Export" to reload the data

---

## Tips and Best Practices

### Performance

- Start with 1-2 researchers (200 papers each) and expand gradually
- Use year filters to reduce graph complexity
- Increase edge weight threshold for cleaner visualizations
- For large datasets (500+ papers), use Focus Only mode

### Data Quality

- OpenAlex data is generally high quality but may have duplicates
- Verify author disambiguation using institution, H-index, and research topics
- Keywords are automatically extracted from OpenAlex concepts

### Troubleshooting

| Problem | Solution |
|---------|----------|
| Graph is too cluttered | Increase edge weight minimum (try 2.0+) |
| No nodes in graph | Reduce edge weight threshold or widen year range |
| Author search returns many results | Include full name; check institution and H-index |
| Data lost after refresh | Always export before closing; use Restore to reload |
| Slow ingestion | Reduce max works per author; import fewer authors at a time |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Actor** | An independent analysis project with its own database |
| **OpenAlex** | Free, open database of 250M+ scholarly works |
| **DOI** | Digital Object Identifier, unique ID for academic papers |
| **Co-authorship** | When researchers collaborate on a publication |
| **Edge weight** | Strength of connection (e.g., number of shared papers) |
| **Node** | An entity in the graph (author, keyword, organization, or nation) |
| **ORCID** | Unique persistent identifier for researchers |
| **Focus Mode** | Filter the graph to show only selected nodes and their neighbors |

---

## License

This project is licensed under the MIT License.
