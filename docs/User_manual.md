# Research Relationship Visualization Service - User Manual

## Overview
This MVP service visualizes research relationships by ingesting publication data from OpenAlex or CSV files, then generating interactive network graphs and heatmaps showing collaborations between authors, keywords, organizations, and nations.

## System Architecture
- **Frontend**: Streamlit web interface for user interaction
- **Backend**: FastAPI REST API server
- **Database**: SQLite with SQLAlchemy ORM
- **Visualization**: PyVis for network graphs, Plotly for heatmaps

## Prerequisites
- Python 3.8 or higher
- pip package manager
- 2GB+ free disk space for database
- Modern web browser

## Installation Guide

### Step 1: Project Setup
```bash
# Create project directory
mkdir research-viz-service
cd research-viz-service

# Create Python virtual environment
python -m venv .venv

# Activate virtual environment
# On Linux/Mac:
source .venv/bin/activate
# On Windows:
.venv\Scripts\activate
```

### Step 2: Install Dependencies
```bash
# Copy requirements.txt to your project folder, then:
pip install -r requirements.txt
```

### Step 3: Environment Configuration
```bash
# Copy .env.example to .env
cp .env.example .env

# Edit .env if needed (default settings work for local development)
```

### Step 4: File Structure
Create the following directory structure:
```
research-viz-service/
├── .env
├── requirements.txt
├── app/
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── db.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── crud.py
│   │   ├── connectors_openalex.py
│   │   ├── services_graph.py
│   │   ├── services_heatmap.py
│   │   └── main.py
│   └── frontend/
│       └── streamlit_app.py
```

### Step 5: Start the Services

**Terminal 1 - Start Backend API:**
```bash
# From project root with venv activated
uvicorn app.backend.main:app --reload --port 8000
```
The API will be available at http://localhost:8000
API documentation at http://localhost:8000/docs

**Terminal 2 - Start Frontend:**
```bash
# From project root with venv activated
streamlit run app/frontend/streamlit_app.py
```
The web interface will open automatically (usually at http://localhost:8501)

## Using the Application

### 1. Database Initialization
- Click **"Initialize DB"** button in the sidebar (first time only)
- This creates the SQLite database and tables

### 2. Data Ingestion

#### Option A: OpenAlex Import (Recommended)
1. In sidebar, enter researcher name (e.g., "Geoffrey Hinton")
2. Click **"Search OpenAlex"**
3. Review search results
4. Select authors by their source_id
5. Adjust "Max works" slider (200 is good default)
6. Click **"Ingest Selected"**
7. Wait for completion message

#### Option B: CSV Import
1. Prepare CSV files with proper columns:
   - **works.csv**: `title, doi, year, venue, type, language, keywords`
   - **authors.csv**: `work_title, work_doi, author_name, position`
   - **affiliations.csv**: `work_title, work_doi, author_name, org_name, country_code`
   - **keywords.csv**: `work_title, work_doi, term`
2. Select CSV type in dropdown
3. Upload file
4. Click **"Import CSV"**

### 3. Graph Visualization

Navigate to **Graph** tab:

1. **Select Layer:**
   - `authors`: Co-authorship network
   - `keywords`: Keyword co-occurrence
   - `orgs`: Organization collaborations
   - `nations`: International collaborations

2. **Set Filters:**
   - Year range (e.g., 2015-2024)
   - Minimum edge weight (filters weak connections)
   - Focus author IDs (optional, comma-separated)

3. Click **"Build Graph"**

4. **Interact with Graph:**
   - Drag nodes to rearrange
   - Hover for details
   - Zoom in/out with mouse wheel
   - Click nodes to highlight connections

### 4. Heatmap Analysis

Navigate to **Heatmaps** tab:

1. **Select Type:**
   - `author_keyword`: Shows which authors work on which topics
   - `nation_nation`: Shows collaboration intensity between countries

2. Set year range

3. Click **"Compute Heatmap"**

4. **Interpret Results:**
   - Darker colors = stronger relationships
   - Hover over cells for exact values

### 5. Data Curation

Navigate to **Curation** tab:

**Merge Duplicate Authors:**
1. Enter ID of author to keep
2. Enter ID of author to remove
3. Add reason for merge
4. Click **"Merge"**

This reassigns all works from removed author to kept author.

## CSV Format Examples

### works.csv
```csv
title,doi,year,venue,type,language,keywords
"Deep Learning in Neural Networks",10.1016/j.neunet.2014.09.003,2015,"Neural Networks","journal-article","en","deep learning;neural networks;backpropagation"
"Attention Is All You Need",10.48550/arXiv.1706.03762,2017,"NeurIPS","conference-paper","en","transformers;attention;NLP"
```

### authors.csv
```csv
work_title,work_doi,author_name,position
"Deep Learning in Neural Networks",,Jürgen Schmidhuber,0
"Attention Is All You Need",,Ashish Vaswani,0
"Attention Is All You Need",,Noam Shazeer,1
```

### affiliations.csv
```csv
work_title,work_doi,author_name,org_name,country_code
"Deep Learning in Neural Networks",,Jürgen Schmidhuber,IDSIA,CH
"Attention Is All You Need",,Ashish Vaswani,Google Brain,US
```

### keywords.csv
```csv
work_title,work_doi,term
"Deep Learning in Neural Networks",,artificial intelligence
"Deep Learning in Neural Networks",,machine learning
```

## Tips and Best Practices

### Performance Optimization
- Start with smaller datasets (100-200 papers) for testing
- Use year filters to reduce graph complexity
- Increase edge weight threshold for cleaner visualizations
- For large datasets (1000+ papers), ingestion may take several minutes

### Data Quality
- OpenAlex data is generally high quality but may have duplicates
- Use the merge feature to consolidate duplicate authors
- Verify author affiliations are correctly mapped
- Keywords from OpenAlex are automatically extracted

### Troubleshooting

**Database Issues:**
- If "Initialize DB" fails, delete `app.db` file and try again
- Check file permissions in project directory

**Import Failures:**
- Ensure CSV encoding is UTF-8
- Check for special characters in names
- Verify DOIs are properly formatted (10.xxxx/yyyy)

**Graph Not Displaying:**
- Reduce date range or increase edge weight threshold
- Check browser console for JavaScript errors
- Try refreshing the page

**Slow Performance:**
- Reduce number of works being processed
- Close other browser tabs
- Consider using smaller year ranges

**Backend Connection Errors:**
- Verify backend is running on port 8000
- Check .env file has correct BACKEND_HOST and BACKEND_PORT
- Ensure no firewall blocking local connections

## API Endpoints Reference

### Core Endpoints
- `GET /health` - Service health check
- `POST /init-db` - Initialize database
- `GET /search-authors?q={name}` - Search OpenAlex for authors
- `POST /ingest/openalex` - Import author works from OpenAlex
- `POST /graph` - Generate network graph data
- `POST /heatmap` - Generate heatmap data
- `POST /import/csv` - Import data from CSV
- `POST /curate/merge` - Merge duplicate authors

### API Documentation
Full API documentation with request/response schemas available at:
http://localhost:8000/docs (when backend is running)

## Advanced Features (Future Enhancements)

### Planned Features
- PDF parsing for direct paper import
- LLM-based keyword extraction
- Advanced duplicate detection
- Export functionality (GraphML, GEXF)
- Time-series analysis
- Citation network analysis
- Recommendation system for collaborations

### Extending the Service
The modular architecture allows easy extension:
- Add new connectors in `connectors_*.py`
- Create new visualization services in `services_*.py`
- Extend models in `models.py` for additional metadata
- Add new graph layers by modifying `services_graph.py`

## System Requirements

### Minimum Requirements
- CPU: 2 cores
- RAM: 4GB
- Storage: 5GB free space
- Python: 3.8+
- Internet: Required for OpenAlex import

### Recommended Requirements
- CPU: 4+ cores
- RAM: 8GB+
- Storage: 20GB free space
- Python: 3.10+
- Internet: Broadband for faster imports

## Support and Contributions

### Reporting Issues
When reporting issues, include:
1. Error messages (full traceback)
2. Steps to reproduce
3. Data sample (if applicable)
4. System information (OS, Python version)

### Contributing
- Follow PEP 8 style guide
- Add type hints to new functions
- Include docstrings for public methods
- Test with both small and large datasets

## License and Credits
- OpenAlex data is provided under open license
- This service is an MVP demonstration
- Built with FastAPI, Streamlit, SQLAlchemy, PyVis, and Plotly

## Quick Start Checklist

- [ ] Python 3.8+ installed
- [ ] Virtual environment created and activated
- [ ] Requirements installed via pip
- [ ] .env file created from .env.example
- [ ] File structure created as specified
- [ ] Backend started (uvicorn)
- [ ] Frontend started (streamlit)
- [ ] Database initialized via UI
- [ ] Test data ingested (search and import an author)
- [ ] Graph visualization tested
- [ ] Heatmap generation tested

## Glossary

- **OpenAlex**: Free, open database of scholarly works and authors
- **DOI**: Digital Object Identifier, unique ID for academic papers
- **Co-authorship**: When authors collaborate on a paper
- **Edge weight**: Strength of connection (e.g., number of co-authored papers)
- **Node**: Entity in graph (author, keyword, organization, nation)
- **ORCID**: Unique identifier for researchers
- **Venue**: Publication outlet (journal or conference)