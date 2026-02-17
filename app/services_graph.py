from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_
from typing import Dict, Any, List, Optional
from . import models

def build_graph(db: Session, layer: str, year_min: int | None, year_max: int | None, edge_min_weight: float = 0.0, focus_ids: Optional[List[int]] = None, focus_only: bool = False) -> Dict[str, Any]:
    nodes, edges = [], []

    if layer == "authors":
        # nodes: authors; edges: coauthor_edges
        author_ids: set[int] = set()
        
        if focus_ids:
            # Validate focus author IDs exist in database
            valid_focus_ids = []
            for focus_id in focus_ids:
                author = db.get(models.Author, focus_id)
                if author:
                    valid_focus_ids.append(focus_id)
            
            if not valid_focus_ids:
                # No valid focus IDs found, return empty graph
                return {"nodes": [], "edges": []}
            
            if focus_only:
                # Focus Only Mode: Show only focus authors and their direct collaborators
                author_ids.update(valid_focus_ids)
                
                # Add direct coauthors of focus authors
                coauthor_ids = set()
                for focus_id in valid_focus_ids:
                    # Get coauthors from coauthor edges (both directions)
                    coauthor_edges_a = db.execute(
                        select(models.CoauthorEdge.b_id)
                        .where(models.CoauthorEdge.a_id == focus_id, models.CoauthorEdge.weight >= edge_min_weight)
                    ).scalars().all()
                    coauthor_edges_b = db.execute(
                        select(models.CoauthorEdge.a_id)
                        .where(models.CoauthorEdge.b_id == focus_id, models.CoauthorEdge.weight >= edge_min_weight)
                    ).scalars().all()
                    coauthor_ids.update(coauthor_edges_a)
                    coauthor_ids.update(coauthor_edges_b)
                
                # Add coauthors to the author set
                author_ids.update(coauthor_ids)
                
                # Filter by year if specified
                if year_min is not None or year_max is not None:
                    # Keep only authors who have works in the specified year range
                    year_filtered_authors = set()
                    q = select(models.WorkAuthor.author_id).join(models.Work).where(models.WorkAuthor.author_id.in_(author_ids))
                    if year_min is not None: q = q.where(models.Work.year >= year_min)
                    if year_max is not None: q = q.where(models.Work.year <= year_max)
                    year_filtered_authors.update(db.execute(q).scalars().all())
                    
                    # Always keep the focus authors even if they don't have works in year range
                    year_filtered_authors.update(valid_focus_ids)
                    author_ids = year_filtered_authors
                    
            else:
                # Full Network Mode: Show all authors but highlight focus authors
                # Get all authors filtered by year
                q = select(models.WorkAuthor.author_id).join(models.Work).where(True)
                if year_min is not None: q = q.where(models.Work.year >= year_min)
                if year_max is not None: q = q.where(models.Work.year <= year_max)
                author_ids.update(set(db.execute(q).scalars().all()))
                
                # Ensure focus authors are included even if not in year range
                author_ids.update(valid_focus_ids)
        
        else:
            # No focus specified, get all authors filtered by year
            q = select(models.WorkAuthor.author_id).join(models.Work).where(True)
            if year_min is not None: q = q.where(models.Work.year >= year_min)
            if year_max is not None: q = q.where(models.Work.year <= year_max)
            author_ids.update(set(db.execute(q).scalars().all()))

        # Create nodes for all authors in our set
        added_node_ids = set()
        for a_id in author_ids:
            a = db.get(models.Author, a_id)
            if a:
                # Mark focus authors differently if specified
                node_type = "author"
                if focus_ids and a_id in focus_ids:
                    node_type = "focus_author"
                
                nodes.append({
                    "id": f"A{a.id}", 
                    "label": a.display_name, 
                    "type": node_type,
                    "focus": a_id in (focus_ids or [])
                })
                added_node_ids.add(a.id)

        # Only add edges between nodes that actually exist in our graph
        for ce in db.execute(select(models.CoauthorEdge).where(models.CoauthorEdge.weight >= edge_min_weight)).scalars().all():
            # Only include edge if both authors are in our node set
            if ce.a_id in added_node_ids and ce.b_id in added_node_ids:
                edges.append({"source": f"A{ce.a_id}", "target": f"A{ce.b_id}", "weight": ce.weight})

    elif layer == "keywords":
        # nodes: keywords; edges: co-occurrence from same work
        from collections import defaultdict
        kw_counts = defaultdict(int)
        # filter works by year
        wq = select(models.Work.id)
        if year_min is not None: wq = wq.where(models.Work.year >= year_min)
        if year_max is not None: wq = wq.where(models.Work.year <= year_max)
        work_ids = db.execute(wq).scalars().all()

        from itertools import combinations
        edges_map = defaultdict(int)
        added_keyword_ids = set()
        
        if focus_ids:
            # Validate focus keyword IDs
            valid_focus_ids = []
            for focus_id in focus_ids:
                keyword = db.get(models.Keyword, focus_id)
                if keyword:
                    valid_focus_ids.append(focus_id)
            
            if not valid_focus_ids:
                return {"nodes": [], "edges": []}
            
            if focus_only:
                # Focus Only Mode: Show only focus keywords and their co-occurring keywords
                focus_related_keywords = set(valid_focus_ids)
                
                # Find keywords that co-occur with focus keywords
                for wid in work_ids:
                    kws = db.execute(select(models.WorkKeyword.keyword_id).where(models.WorkKeyword.work_id == wid)).scalars().all()
                    kws_set = set(kws)
                    
                    # If this work contains any focus keywords, include all its keywords
                    if kws_set.intersection(valid_focus_ids):
                        focus_related_keywords.update(kws_set)
                        for k in kws:
                            kw_counts[k] += 1
                        for k1, k2 in combinations(sorted(kws), 2):
                            edges_map[(k1, k2)] += 1
                
                added_keyword_ids = focus_related_keywords
            else:
                # Full Network Mode: Show all keywords but highlight focus keywords
                for wid in work_ids:
                    kws = db.execute(select(models.WorkKeyword.keyword_id).where(models.WorkKeyword.work_id == wid)).scalars().all()
                    kws = sorted(set(kws))
                    for k in kws:
                        kw_counts[k] += 1
                        added_keyword_ids.add(k)
                    for k1, k2 in combinations(kws, 2):
                        edges_map[(k1, k2)] += 1
        else:
            # No focus specified
            for wid in work_ids:
                kws = db.execute(select(models.WorkKeyword.keyword_id).where(models.WorkKeyword.work_id == wid)).scalars().all()
                kws = sorted(set(kws))
                for k in kws:
                    kw_counts[k] += 1
                    added_keyword_ids.add(k)
                for k1, k2 in combinations(kws, 2):
                    edges_map[(k1, k2)] += 1

        for kid in added_keyword_ids:
            k = db.get(models.Keyword, kid)
            if k:
                # Mark focus keywords differently
                node_type = "keyword"
                if focus_ids and kid in focus_ids:
                    node_type = "focus_keyword"
                
                nodes.append({
                    "id": f"K{kid}", 
                    "label": k.term_display, 
                    "type": node_type, 
                    "count": kw_counts[kid],
                    "focus": kid in (focus_ids or [])
                })

        for (k1, k2), w in edges_map.items():
            if w >= edge_min_weight and k1 in added_keyword_ids and k2 in added_keyword_ids:
                edges.append({"source": f"K{k1}", "target": f"K{k2}", "weight": float(w)})

    elif layer == "orgs":
        # nodes: organizations; edges: org_edges
        org_ids = set()
        
        if focus_ids:
            # Validate focus org IDs
            valid_focus_ids = []
            for focus_id in focus_ids:
                org = db.get(models.Organization, focus_id)
                if org:
                    valid_focus_ids.append(focus_id)
            
            if not valid_focus_ids:
                return {"nodes": [], "edges": []}
            
            if focus_only:
                # Focus Only Mode: Show focus orgs and their direct collaborators
                focus_related_orgs = set(valid_focus_ids)
                
                # Find orgs that collaborate with focus orgs
                for e in db.execute(select(models.OrgEdge).where(models.OrgEdge.weight >= edge_min_weight)).scalars().all():
                    if e.org1_id in valid_focus_ids:
                        focus_related_orgs.add(e.org2_id)
                    if e.org2_id in valid_focus_ids:
                        focus_related_orgs.add(e.org1_id)
                
                org_ids = focus_related_orgs
            else:
                # Full Network Mode: Show all orgs but highlight focus orgs
                # Get all orgs mentioned in affiliations filtered by year
                aq = select(models.WorkAffiliation.org_id).join(models.Work).where(models.WorkAffiliation.org_id.isnot(None))
                if year_min is not None: aq = aq.where(models.Work.year >= year_min)
                if year_max is not None: aq = aq.where(models.Work.year <= year_max)
                org_ids.update(db.execute(aq).scalars().all())
                
                # Ensure focus orgs are included
                org_ids.update(valid_focus_ids)
        else:
            # No focus specified
            # Get all orgs mentioned in affiliations filtered by year
            aq = select(models.WorkAffiliation.org_id).join(models.Work).where(models.WorkAffiliation.org_id.isnot(None))
            if year_min is not None: aq = aq.where(models.Work.year >= year_min)
            if year_max is not None: aq = aq.where(models.Work.year <= year_max)
            org_ids.update(db.execute(aq).scalars().all())

        added_org_ids = set()
        for oid in sorted(set(org_ids)):
            org = db.get(models.Organization, oid)
            if org:
                # Mark focus orgs differently
                node_type = "org"
                if focus_ids and oid in focus_ids:
                    node_type = "focus_org"
                
                nodes.append({
                    "id": f"O{oid}", 
                    "label": org.name, 
                    "type": node_type, 
                    "country": org.country_code,
                    "focus": oid in (focus_ids or [])
                })
                added_org_ids.add(oid)

        for e in db.execute(select(models.OrgEdge).where(models.OrgEdge.weight >= edge_min_weight)).scalars().all():
            # Only add edge if both organizations are in our node set
            if e.org1_id in added_org_ids and e.org2_id in added_org_ids:
                edges.append({"source": f"O{e.org1_id}", "target": f"O{e.org2_id}", "weight": e.weight})

    elif layer == "nations":
        # nodes: nations present; edges: nation_edges
        
        if focus_ids:
            # For nations, extract string country codes from focus_ids
            valid_focus_codes = []
            for focus_id in focus_ids:
                if isinstance(focus_id, str) and len(focus_id) == 2:
                    valid_focus_codes.append(focus_id.upper())
            
            if not valid_focus_codes:
                # If no valid country codes found, show empty graph
                return {"nodes": [], "edges": []}
            
            if focus_only:
                # Focus Only Mode: Show focus nations and their direct collaborators
                focus_related_nations = set(valid_focus_codes)
                
                # Find nations that collaborate with focus nations
                for e in db.execute(select(models.NationEdge).where(models.NationEdge.weight >= edge_min_weight)).scalars().all():
                    if e.n1 in valid_focus_codes:
                        focus_related_nations.add(e.n2)
                    if e.n2 in valid_focus_codes:
                        focus_related_nations.add(e.n1)
                
                nations = focus_related_nations
            else:
                # Full Network Mode: Show all nations but highlight focus nations
                # Collect nations from affiliations, filtered by year
                nq = select(models.WorkAffiliation.country_code).join(models.Work).where(models.WorkAffiliation.country_code.isnot(None))
                if year_min is not None: nq = nq.where(models.Work.year >= year_min)
                if year_max is not None: nq = nq.where(models.Work.year <= year_max)
                nations = set(db.execute(nq).scalars().all())
                
                # Ensure focus nations are included
                nations.update(valid_focus_codes)
        else:
            # No focus specified
            # collect nations from affiliations, filtered by year
            nq = select(models.WorkAffiliation.country_code).join(models.Work).where(models.WorkAffiliation.country_code.isnot(None))
            if year_min is not None: nq = nq.where(models.Work.year >= year_min)
            if year_max is not None: nq = nq.where(models.Work.year <= year_max)
            nations = set(db.execute(nq).scalars().all())
        
        for n in sorted(nations):
            # Mark focus nations differently
            node_type = "nation"
            is_focus = focus_ids and n in [fid for fid in focus_ids if isinstance(fid, str)]
            if is_focus:
                node_type = "focus_nation"
            
            nodes.append({
                "id": f"N{n}", 
                "label": n, 
                "type": node_type,
                "focus": is_focus
            })
            
        for e in db.execute(select(models.NationEdge).where(models.NationEdge.weight >= edge_min_weight)).scalars().all():
            # Only add edge if both nations are in our node set
            if e.n1 in nations and e.n2 in nations:
                edges.append({"source": f"N{e.n1}", "target": f"N{e.n2}", "weight": e.weight})
    else:
        return {"nodes": [], "edges": []}

    return {"nodes": nodes, "edges": edges}