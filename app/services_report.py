"""
Analytic Report — gather statistics from the in-memory database.
"""
from collections import defaultdict, Counter
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from . import models


def gather_report(db: Session) -> dict:
    """Return a dict with all analytic data needed for the report."""

    # --- basic counts ---
    n_works = db.execute(select(func.count(models.Work.id))).scalar() or 0
    n_authors = db.execute(select(func.count(models.Author.id))).scalar() or 0
    n_orgs = db.execute(select(func.count(models.Organization.id))).scalar() or 0
    n_keywords = db.execute(select(func.count(models.Keyword.id))).scalar() or 0
    n_venues = db.execute(select(func.count(models.Venue.id))).scalar() or 0

    # --- year range ---
    year_min = db.execute(select(func.min(models.Work.year))).scalar()
    year_max = db.execute(select(func.max(models.Work.year))).scalar()

    # --- publication trend (papers per year) ---
    year_rows = db.execute(
        select(models.Work.year, func.count(models.Work.id))
        .where(models.Work.year.isnot(None))
        .group_by(models.Work.year)
        .order_by(models.Work.year)
    ).all()
    pub_trend = [{"year": y, "count": c} for y, c in year_rows]

    # --- top authors by paper count ---
    author_rows = db.execute(
        select(
            models.Author.display_name,
            func.count(models.WorkAuthor.work_id).label("cnt"),
        )
        .join(models.WorkAuthor, models.Author.id == models.WorkAuthor.author_id)
        .group_by(models.Author.id)
        .order_by(func.count(models.WorkAuthor.work_id).desc())
        .limit(20)
    ).all()
    top_authors = [{"name": name, "papers": cnt} for name, cnt in author_rows]

    # --- top keywords ---
    kw_rows = db.execute(
        select(
            models.Keyword.term_display,
            func.count(models.WorkKeyword.work_id).label("cnt"),
        )
        .join(models.WorkKeyword, models.Keyword.id == models.WorkKeyword.keyword_id)
        .group_by(models.Keyword.id)
        .order_by(func.count(models.WorkKeyword.work_id).desc())
        .limit(20)
    ).all()
    top_keywords = [{"term": t, "count": c} for t, c in kw_rows]

    # --- country distribution ---
    country_rows = db.execute(
        select(
            models.WorkAffiliation.country_code,
            func.count(func.distinct(models.WorkAffiliation.work_id)).label("cnt"),
        )
        .where(models.WorkAffiliation.country_code.isnot(None))
        .group_by(models.WorkAffiliation.country_code)
        .order_by(func.count(func.distinct(models.WorkAffiliation.work_id)).desc())
        .limit(20)
    ).all()
    country_dist = [{"country": cc, "papers": cnt} for cc, cnt in country_rows]

    # --- top collaborator pairs ---
    collab_rows = db.execute(
        select(models.CoauthorEdge)
        .order_by(models.CoauthorEdge.weight.desc())
        .limit(15)
    ).scalars().all()
    top_collabs = []
    for e in collab_rows:
        a = db.get(models.Author, e.a_id)
        b = db.get(models.Author, e.b_id)
        if a and b:
            top_collabs.append({
                "author_a": a.display_name,
                "author_b": b.display_name,
                "weight": e.weight,
                "papers": e.evidence_count,
            })

    # --- keyword co-occurrence top pairs ---
    # reuse work_keywords to compute top co-occurring keyword pairs
    work_ids = db.execute(select(models.Work.id)).scalars().all()
    kw_pair_counter: Counter = Counter()
    for wid in work_ids:
        kws = db.execute(
            select(models.WorkKeyword.keyword_id)
            .where(models.WorkKeyword.work_id == wid)
        ).scalars().all()
        kws = sorted(set(kws))
        for i in range(len(kws)):
            for j in range(i + 1, len(kws)):
                kw_pair_counter[(kws[i], kws[j])] += 1

    top_kw_pairs = []
    for (k1, k2), cnt in kw_pair_counter.most_common(15):
        kw1 = db.get(models.Keyword, k1)
        kw2 = db.get(models.Keyword, k2)
        if kw1 and kw2:
            top_kw_pairs.append({
                "keyword_a": kw1.term_display,
                "keyword_b": kw2.term_display,
                "co_occurrences": cnt,
            })

    # --- venue distribution ---
    venue_rows = db.execute(
        select(
            models.Venue.name,
            func.count(models.Work.id).label("cnt"),
        )
        .join(models.Work, models.Venue.id == models.Work.venue_id)
        .group_by(models.Venue.id)
        .order_by(func.count(models.Work.id).desc())
        .limit(15)
    ).all()
    top_venues = [{"venue": v, "papers": c} for v, c in venue_rows]

    # --- highlight works (top cited papers) ---
    all_works = db.execute(select(models.Work)).scalars().all()
    scored_works = []
    for w in all_works:
        cited = 0
        if w.raw_json and isinstance(w.raw_json, dict):
            cited = w.raw_json.get("cited_by_count", 0) or 0
        doi_link = f"https://doi.org/{w.doi}" if w.doi else None
        link = doi_link or w.url
        # gather author names for this work
        wa_rows = db.execute(
            select(models.Author.display_name)
            .join(models.WorkAuthor, models.Author.id == models.WorkAuthor.author_id)
            .where(models.WorkAuthor.work_id == w.id)
            .order_by(models.WorkAuthor.position)
        ).scalars().all()
        authors_str = ", ".join(wa_rows[:5])
        if len(wa_rows) > 5:
            authors_str += f" et al. ({len(wa_rows)} authors)"
        # venue name
        venue_name = ""
        if w.venue:
            venue_name = w.venue.name
        scored_works.append({
            "title": w.title,
            "year": w.year,
            "cited_by_count": cited,
            "doi": w.doi,
            "link": link,
            "authors": authors_str,
            "venue": venue_name,
        })
    scored_works.sort(key=lambda x: x["cited_by_count"], reverse=True)
    highlight_works = scored_works[:15]

    # --- graph data for network visualization ---
    # Collect top coauthor edges for a simplified graph
    graph_edges = db.execute(
        select(models.CoauthorEdge)
        .order_by(models.CoauthorEdge.weight.desc())
        .limit(40)
    ).scalars().all()
    graph_nodes_set: set[int] = set()
    graph_edge_list = []
    for e in graph_edges:
        graph_nodes_set.add(e.a_id)
        graph_nodes_set.add(e.b_id)
        graph_edge_list.append({"a": e.a_id, "b": e.b_id, "weight": e.weight})
    graph_node_list = []
    for nid in graph_nodes_set:
        a = db.get(models.Author, nid)
        if a:
            graph_node_list.append({"id": nid, "label": a.display_name})

    return {
        "n_works": n_works,
        "n_authors": n_authors,
        "n_orgs": n_orgs,
        "n_keywords": n_keywords,
        "n_venues": n_venues,
        "year_min": year_min,
        "year_max": year_max,
        "pub_trend": pub_trend,
        "top_authors": top_authors,
        "top_keywords": top_keywords,
        "country_dist": country_dist,
        "top_collabs": top_collabs,
        "top_kw_pairs": top_kw_pairs,
        "top_venues": top_venues,
        "highlight_works": highlight_works,
        "graph_nodes": graph_node_list,
        "graph_edges": graph_edge_list,
    }
