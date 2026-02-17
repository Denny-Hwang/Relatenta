from fastapi import FastAPI, Depends, Query, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from typing import List, Optional
from .db import get_db, init_db, list_actors, delete_actor_db, get_actor_stats
from sqlalchemy.orm import Session
from sqlalchemy import select
from .schemas import AuthorHit, IngestRequest, GraphRequest, GraphResponse, HeatmapRequest, CSVImportRequest
from . import connectors_openalex as oa
from . import crud
from . import models
from .services_graph import build_graph
from .services_heatmap import author_keyword_heat, nation_nation_heat
from .services_export import export_actor_to_csv
import pandas as pd
import io
from datetime import datetime

app = FastAPI(title="Reatenta")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============= Actor Management Endpoints =============

@app.get("/actors")
def get_actors():
    """List all available actor databases with statistics."""
    actors = list_actors()
    # Add stats for each actor
    for actor in actors:
        stats = get_actor_stats(actor["name"])
        actor.update(stats)
    return {"actors": actors}

@app.post("/actors/{actor_name}/init")
def init_actor_db(actor_name: str):
    """Initialize a new actor database."""
    if not actor_name or len(actor_name) < 2:
        raise HTTPException(status_code=400, detail="Actor name must be at least 2 characters")
    
    init_db(actor_name)
    return {"status": "initialized", "actor": actor_name}

@app.delete("/actors/{actor_name}")
def delete_actor(actor_name: str):
    """Delete an actor's database."""
    if actor_name == "default":
        raise HTTPException(status_code=400, detail="Cannot delete default actor")
    
    success = delete_actor_db(actor_name)
    if success:
        return {"status": "deleted", "actor": actor_name}
    else:
        raise HTTPException(status_code=404, detail="Actor not found")

@app.get("/actors/{actor_name}/stats")
def get_actor_statistics(actor_name: str):
    """Get detailed statistics for an actor."""
    stats = get_actor_stats(actor_name)
    if not stats["exists"]:
        raise HTTPException(status_code=404, detail="Actor database not found")
    return stats

@app.get("/actors/{actor_name}/export")
def export_actor_data(actor_name: str, format: str = Query("csv", enum=["csv"])):
    """Export actor's database as CSV files (zipped)."""
    try:
        # Generate CSV data
        zip_buffer = export_actor_to_csv(actor_name)
        
        # Return as downloadable file
        return StreamingResponse(
            io.BytesIO(zip_buffer),
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename={actor_name}_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============= Actor-Specific Data Endpoints =============

@app.get("/health")
def health():
    return {"ok": True, "multi_actor": True}

@app.get("/search-authors", response_model=List[AuthorHit])
def search_authors(q: str = Query(..., min_length=2)):
    """Search authors from OpenAlex (not actor-specific)."""
    hits = oa.search_authors_by_name(q)
    return [AuthorHit(
        source_id=h["id"].split("/")[-1] if h["id"].startswith("http") else h["id"],
        display_name=h["display_name"],
        works_count=h["works_count"],
        last_known_institution=h["last_known_institution"],
    ) for h in hits]

@app.get("/{actor_name}/search-local-authors")
def search_local_authors(actor_name: str, q: str = Query(..., min_length=2)):
    """Search for authors within a specific actor's database."""
    with get_db(actor_name) as db:
        from sqlalchemy import func
        authors = db.execute(
            select(models.Author.id, models.Author.display_name)
            .where(func.lower(models.Author.display_name).contains(q.lower()))
            .order_by(models.Author.display_name)
            .limit(15)
        ).all()
        
        return {
            "authors": [
                {"id": author_id, "name": name} 
                for author_id, name in authors
            ]
        }

@app.get("/{actor_name}/search-local-keywords")
def search_local_keywords(actor_name: str, q: str = Query(..., min_length=2)):
    """Search for keywords within a specific actor's database."""
    with get_db(actor_name) as db:
        from sqlalchemy import func
        keywords = db.execute(
            select(models.Keyword.id, models.Keyword.term_display)
            .where(func.lower(models.Keyword.term_display).contains(q.lower()))
            .order_by(models.Keyword.term_display)
            .limit(15)
        ).all()
        
        return {
            "keywords": [
                {"id": keyword_id, "term": term} 
                for keyword_id, term in keywords
            ]
        }

@app.get("/{actor_name}/search-local-orgs")
def search_local_orgs(actor_name: str, q: str = Query(..., min_length=2)):
    """Search for organizations within a specific actor's database."""
    with get_db(actor_name) as db:
        from sqlalchemy import func
        orgs = db.execute(
            select(models.Organization.id, models.Organization.name, models.Organization.country_code)
            .where(func.lower(models.Organization.name).contains(q.lower()))
            .order_by(models.Organization.name)
            .limit(15)
        ).all()
        
        return {
            "organizations": [
                {"id": org_id, "name": name, "country": country or "N/A"} 
                for org_id, name, country in orgs
            ]
        }

@app.post("/{actor_name}/validate-authors")
def validate_authors(actor_name: str, author_ids: List[int] = Body(...)):
    """Validate author IDs and return their names."""
    with get_db(actor_name) as db:
        results = []
        for author_id in author_ids:
            author = db.get(models.Author, author_id)
            if author:
                results.append({"id": author_id, "name": author.display_name, "exists": True})
            else:
                results.append({"id": author_id, "name": None, "exists": False})
        return {"authors": results}

@app.post("/{actor_name}/validate-keywords")
def validate_keywords(actor_name: str, keyword_ids: List[int] = Body(...)):
    """Validate keyword IDs and return their terms."""
    with get_db(actor_name) as db:
        results = []
        for keyword_id in keyword_ids:
            keyword = db.get(models.Keyword, keyword_id)
            if keyword:
                results.append({"id": keyword_id, "term": keyword.term_display, "exists": True})
            else:
                results.append({"id": keyword_id, "term": None, "exists": False})
        return {"keywords": results}

@app.post("/{actor_name}/validate-orgs")
def validate_orgs(actor_name: str, org_ids: List[int] = Body(...)):
    """Validate organization IDs and return their names."""
    with get_db(actor_name) as db:
        results = []
        for org_id in org_ids:
            org = db.get(models.Organization, org_id)
            if org:
                results.append({"id": org_id, "name": org.name, "exists": True})
            else:
                results.append({"id": org_id, "name": None, "exists": False})
        return {"organizations": results}

@app.post("/{actor_name}/ingest/openalex")
def ingest_openalex(actor_name: str, req: IngestRequest):
    """Ingest data from OpenAlex for a specific actor."""
    with get_db(actor_name) as db:
        # init if needed
        init_db(actor_name)
        total = 0
        for author_id in req.author_source_ids:
            works = oa.list_author_works(author_id, per_page=200, max_pages=max(1, req.max_works // 200))
            for w in works:
                crud.upsert_work_from_openalex(db, w)
                total += 1
        # recompute edges
        crud.recompute_coauthor_edges(db)
        crud.recompute_nation_edges(db)
        try:
            crud.recompute_org_edges(db)
        except AttributeError:
            pass
    return {"ingested_works": total, "actor": actor_name}

@app.post("/{actor_name}/graph", response_model=GraphResponse)
def graph(actor_name: str, req: GraphRequest = Body(...)):
    """Generate graph for a specific actor."""
    with get_db(actor_name) as db:
        # Handle the focus_only parameter safely
        focus_only = getattr(req, 'focus_only', False)
        
        # Handle focus_ids with backward compatibility and type flexibility
        focus_ids = None
        if hasattr(req, 'focus_ids') and req.focus_ids:
            # For nations (string country codes)
            focus_ids = req.focus_ids
        elif hasattr(req, 'focus_int_ids') and req.focus_int_ids:
            # For authors, keywords, orgs (integer IDs)
            focus_ids = req.focus_int_ids
        elif hasattr(req, 'focus_author_ids') and req.focus_author_ids:
            # Backward compatibility
            focus_ids = req.focus_author_ids
        
        print(f"DEBUG: Building graph with layer={req.layer}, focus_only={focus_only}, focus_ids={focus_ids}")
        
        g = build_graph(
            db, 
            req.layer, 
            req.year_min, 
            req.year_max, 
            req.edge_min_weight, 
            focus_ids, 
            focus_only
        )
    return GraphResponse(nodes=g["nodes"], edges=g["edges"])

@app.post("/{actor_name}/heatmap")
def heatmap(actor_name: str, req: HeatmapRequest = Body(...)):
    """Generate heatmap for a specific actor."""
    with get_db(actor_name) as db:
        if req.kind == "author_keyword":
            return author_keyword_heat(db, req.year_min, req.year_max)
        elif req.kind == "nation_nation":
            return nation_nation_heat(db, req.year_min, req.year_max)
        else:
            return {"rows": [], "cols": [], "data": []}

@app.post("/{actor_name}/import/csv")
def import_csv(actor_name: str, req: CSVImportRequest):
    """Import CSV data for a specific actor."""
    with get_db(actor_name) as db:
        init_db(actor_name)
        df = pd.read_csv(io.StringIO(req.csv_text))
        
        if req.kind == "works":
            for _, r in df.iterrows():
                w = {
                    "id": r.get("source_uid") or r.get("doi") or "",
                    "doi": r.get("doi"),
                    "title": r.get("title"),
                    "publication_year": int(r["year"]) if not pd.isna(r.get("year")) else None,
                    "host_venue": {"display_name": r.get("venue")},
                    "type": r.get("type"),
                    "language": r.get("language"),
                    "authorships": [],
                    "concepts": [{"display_name": t.strip(), "score": 1.0} for t in str(r.get("keywords") or "").split(";") if t.strip()],
                }
                crud.upsert_work_from_openalex(db, w)
                
        elif req.kind == "authors":
            for _, r in df.iterrows():
                work = None
                if not pd.isna(r.get("work_doi")):
                    work = db.execute(select(models.Work).where(models.Work.doi == str(r.get("work_doi")).lower())).scalar_one_or_none()
                if not work and not pd.isna(r.get("work_title")):
                    work = db.execute(select(models.Work).where(models.Work.title == str(r.get("work_title")))).scalar_one_or_none()
                if not work:
                    continue
                a = crud.get_or_create_author(db, r.get("author_name", "Unknown"))
                db.add(models.WorkAuthor(work_id=work.id, author_id=a.id, position=int(r.get("position") or 0)))
                
        elif req.kind == "affiliations":
            for _, r in df.iterrows():
                work = None
                if not pd.isna(r.get("work_doi")):
                    work = db.execute(select(models.Work).where(models.Work.doi == str(r.get("work_doi")).lower())).scalar_one_or_none()
                if not work and not pd.isna(r.get("work_title")):
                    work = db.execute(select(models.Work).where(models.Work.title == str(r.get("work_title")))).scalar_one_or_none()
                if not work:
                    continue
                a = crud.get_or_create_author(db, r.get("author_name", "Unknown"))
                org = crud.get_or_create_org(db, r.get("org_name", "Unknown"), country=str(r.get("country_code") or "").upper() or None)
                db.add(models.WorkAffiliation(work_id=work.id, author_id=a.id, org_id=org.id, org_label_raw=org.name, country_code=org.country_code))
                
        elif req.kind == "keywords":
            for _, r in df.iterrows():
                work = None
                if not pd.isna(r.get("work_doi")):
                    work = db.execute(select(models.Work).where(models.Work.doi == str(r.get("work_doi")).lower())).scalar_one_or_none()
                if not work and not pd.isna(r.get("work_title")):
                    work = db.execute(select(models.Work).where(models.Work.title == str(r.get("work_title")))).scalar_one_or_none()
                if not work:
                    continue
                kw = crud.get_or_create_keyword(db, r.get("term", "").strip())
                db.add(models.WorkKeyword(work_id=work.id, keyword_id=kw.id, weight=1.0, extractor="manual"))
        
        # recompute edges
        crud.recompute_coauthor_edges(db)
        crud.recompute_nation_edges(db)
        try:
            crud.recompute_org_edges(db)
        except AttributeError:
            pass
            
    return {"status": "ok", "rows": len(df), "actor": actor_name}