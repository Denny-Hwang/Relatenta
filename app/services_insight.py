"""
Research Insight Analysis — Community detection, burst detection, collaborator
recommendation, shortest path, research gap detection, strategic diagram,
and thematic evolution.

All functions take a SQLAlchemy Session and return structured data dicts.
No external API or ML model dependencies.
"""
from collections import defaultdict
from itertools import combinations
from typing import Any, Dict, List, Optional

import networkx as nx
from networkx.algorithms.community import louvain_communities
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models


# ── helpers ──────────────────────────────────────────────────────────────

def _build_nx_graph(db: Session, layer: str,
                    year_min: int | None = None,
                    year_max: int | None = None,
                    min_weight: float = 0.0) -> nx.Graph:
    """Build a NetworkX undirected graph from existing edge tables."""
    G = nx.Graph()

    if layer == "authors":
        edges = db.execute(select(models.CoauthorEdge)).scalars().all()
        for e in edges:
            if e.weight >= min_weight:
                G.add_edge(e.a_id, e.b_id, weight=e.weight)

    elif layer == "keywords":
        # Build from co-occurrence in works (year-filtered)
        wq = select(models.Work.id)
        if year_min is not None:
            wq = wq.where(models.Work.year >= year_min)
        if year_max is not None:
            wq = wq.where(models.Work.year <= year_max)
        work_ids = db.execute(wq).scalars().all()

        edge_map: dict[tuple, float] = defaultdict(float)
        for wid in work_ids:
            kws = sorted(set(
                db.execute(
                    select(models.WorkKeyword.keyword_id)
                    .where(models.WorkKeyword.work_id == wid)
                ).scalars().all()
            ))
            for k1, k2 in combinations(kws, 2):
                edge_map[(k1, k2)] += 1.0

        for (k1, k2), w in edge_map.items():
            if w >= min_weight:
                G.add_edge(k1, k2, weight=w)

    elif layer == "orgs":
        edges = db.execute(select(models.OrgEdge)).scalars().all()
        for e in edges:
            if e.weight >= min_weight:
                G.add_edge(e.org1_id, e.org2_id, weight=e.weight)

    elif layer == "nations":
        edges = db.execute(select(models.NationEdge)).scalars().all()
        for e in edges:
            if e.weight >= min_weight:
                G.add_edge(e.n1, e.n2, weight=e.weight)

    return G


def _node_label(db: Session, layer: str, node_id) -> str:
    """Get human-readable label for a node."""
    if layer == "authors":
        a = db.get(models.Author, node_id)
        return a.display_name if a else str(node_id)
    elif layer == "keywords":
        k = db.get(models.Keyword, node_id)
        return k.term_display if k else str(node_id)
    elif layer == "orgs":
        o = db.get(models.Organization, node_id)
        return o.name if o else str(node_id)
    elif layer == "nations":
        return str(node_id)
    return str(node_id)


# ── F1: Community Detection ─────────────────────────────────────────────

def detect_communities(db: Session, layer: str = "authors",
                       resolution: float = 1.0,
                       year_min: int | None = None,
                       year_max: int | None = None) -> Dict[str, Any]:
    """Detect communities using Louvain algorithm (NetworkX built-in)."""
    G = _build_nx_graph(db, layer, year_min, year_max)

    if G.number_of_nodes() < 2:
        return {"communities": {}, "partition": {}, "modularity": 0.0,
                "num_communities": 0, "message": "Not enough nodes for community detection."}

    # louvain_communities returns list of frozensets
    community_sets = louvain_communities(G, resolution=resolution, seed=42)

    # Build partition dict: node_id -> community_id
    partition: dict = {}
    communities: dict = {}
    for idx, comm_set in enumerate(community_sets):
        members = list(comm_set)
        partition.update({n: idx for n in members})

        # Subgraph density
        sub = G.subgraph(members)
        n_nodes = sub.number_of_nodes()
        density = nx.density(sub) if n_nodes > 1 else 0.0

        # Top label: most connected node
        if members:
            member_degrees = {n: sub.degree(n) for n in members}
            top_node = max(member_degrees, key=member_degrees.get)
            label = _node_label(db, layer, top_node)
        else:
            label = f"Community {idx}"

        communities[idx] = {
            "nodes": [_node_label(db, layer, n) for n in members],
            "node_ids": members,
            "size": n_nodes,
            "density": round(density, 3),
            "label": label,
        }

    modularity = nx.community.modularity(G, community_sets)

    return {
        "communities": communities,
        "partition": partition,
        "modularity": round(modularity, 4),
        "num_communities": len(community_sets),
    }


# ── F2: Burst Detection ─────────────────────────────────────────────────

def detect_bursts(db: Session, window_years: int = 3,
                  min_papers: int = 3) -> List[Dict[str, Any]]:
    """Detect keywords with sudden growth (emerging research fronts)."""
    # Get per-keyword per-year counts
    wq = select(models.WorkKeyword.keyword_id, models.Work.year).join(
        models.Work, models.WorkKeyword.work_id == models.Work.id
    ).where(models.Work.year.isnot(None))

    rows = db.execute(wq).all()
    if not rows:
        return []

    kw_year_counts: dict[int, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for kid, year in rows:
        kw_year_counts[kid][year] += 1

    all_years = sorted(set(y for _, y in rows))
    if len(all_years) < 2:
        return []

    max_year = max(all_years)
    window_start = max_year - window_years + 1

    results = []
    for kid, year_counts in kw_year_counts.items():
        total = sum(year_counts.values())
        if total < min_papers:
            continue

        # Baseline: average before window
        baseline_years = [y for y in all_years if y < window_start]
        recent_years = [y for y in all_years if y >= window_start]

        baseline_avg = (sum(year_counts.get(y, 0) for y in baseline_years) /
                        max(len(baseline_years), 1))
        recent_avg = (sum(year_counts.get(y, 0) for y in recent_years) /
                      max(len(recent_years), 1))

        burst_score = (recent_avg - baseline_avg) / max(baseline_avg, 0.5)

        # Trend: yearly counts across all years
        trend = [year_counts.get(y, 0) for y in all_years]

        # Classify status
        if burst_score > 2.0:
            status = "burst"
        elif burst_score > 0.5:
            status = "growing"
        elif burst_score > -0.3:
            status = "stable"
        else:
            status = "declining"

        kw = db.get(models.Keyword, kid)
        results.append({
            "keyword_id": kid,
            "keyword": kw.term_display if kw else str(kid),
            "burst_score": round(burst_score, 2),
            "baseline_avg": round(baseline_avg, 2),
            "recent_avg": round(recent_avg, 2),
            "total_papers": total,
            "trend": trend,
            "years": all_years,
            "status": status,
        })

    results.sort(key=lambda x: x["burst_score"], reverse=True)
    return results


# ── F3: Collaborator Recommendation ─────────────────────────────────────

def recommend_collaborators(db: Session, author_id: int,
                            top_n: int = 10) -> List[Dict[str, Any]]:
    """Suggest potential collaborators based on keyword overlap and network proximity."""
    G = _build_nx_graph(db, "authors")

    if author_id not in G:
        return []

    # Target author's keywords
    target_works = db.execute(
        select(models.WorkAuthor.work_id)
        .where(models.WorkAuthor.author_id == author_id)
    ).scalars().all()

    target_keywords = set()
    for wid in target_works:
        kws = db.execute(
            select(models.WorkKeyword.keyword_id)
            .where(models.WorkKeyword.work_id == wid)
        ).scalars().all()
        target_keywords.update(kws)

    if not target_keywords:
        return []

    # Existing co-authors (exclude from recommendations)
    existing_coauthors = set(G.neighbors(author_id))
    existing_coauthors.add(author_id)

    # All other authors
    all_authors = set(
        db.execute(select(models.Author.id)).scalars().all()
    )
    candidates = all_authors - existing_coauthors

    # Pre-compute target's neighbors for common-neighbor scoring
    target_neighbors = set(G.neighbors(author_id))
    max_neighbors = max(len(target_neighbors), 1)

    results = []
    for cand_id in candidates:
        # Candidate's keywords
        cand_works = db.execute(
            select(models.WorkAuthor.work_id)
            .where(models.WorkAuthor.author_id == cand_id)
        ).scalars().all()

        cand_keywords = set()
        for wid in cand_works:
            kws = db.execute(
                select(models.WorkKeyword.keyword_id)
                .where(models.WorkKeyword.work_id == wid)
            ).scalars().all()
            cand_keywords.update(kws)

        if not cand_keywords:
            continue

        # Jaccard similarity
        intersection = target_keywords & cand_keywords
        union = target_keywords | cand_keywords
        jaccard = len(intersection) / len(union) if union else 0

        if jaccard < 0.05:
            continue

        # Common neighbors
        cand_neighbors = set(G.neighbors(cand_id)) if cand_id in G else set()
        common_neighbors = target_neighbors & cand_neighbors
        common_neighbor_score = len(common_neighbors) / max_neighbors

        # Complementarity: candidate's unique keywords
        unique_kws = cand_keywords - target_keywords
        complementarity = len(unique_kws) / len(union) if union else 0

        score = 0.5 * jaccard + 0.3 * common_neighbor_score + 0.2 * complementarity

        # Shortest path
        try:
            path_len = nx.shortest_path_length(G, author_id, cand_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            path_len = -1  # disconnected

        # Get labels
        shared_kw_labels = [_node_label(db, "keywords", k) for k in list(intersection)[:5]]
        unique_kw_labels = [_node_label(db, "keywords", k) for k in list(unique_kws)[:5]]
        common_nb_names = [_node_label(db, "authors", n) for n in list(common_neighbors)[:5]]

        results.append({
            "author_id": cand_id,
            "author_name": _node_label(db, "authors", cand_id),
            "score": round(score, 3),
            "jaccard_similarity": round(jaccard, 3),
            "common_neighbors": len(common_neighbors),
            "common_neighbor_names": common_nb_names,
            "shared_keywords": shared_kw_labels,
            "unique_keywords": unique_kw_labels,
            "path_length": path_len,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]


# ── F4: Shortest Path Analysis ──────────────────────────────────────────

def find_shortest_path(db: Session, source_id: int, target_id: int,
                       layer: str = "authors") -> Dict[str, Any]:
    """Find shortest collaboration path between two nodes."""
    G = _build_nx_graph(db, layer)

    if source_id not in G or target_id not in G:
        missing = []
        if source_id not in G:
            missing.append(_node_label(db, layer, source_id))
        if target_id not in G:
            missing.append(_node_label(db, layer, target_id))
        return {
            "path_exists": False,
            "message": f"Node(s) not found in network: {', '.join(missing)}",
            "path_length": -1,
            "path": [],
        }

    try:
        path_nodes = nx.shortest_path(G, source_id, target_id)
    except nx.NetworkXNoPath:
        return {
            "path_exists": False,
            "message": "No collaboration path found between these nodes.",
            "path_length": -1,
            "path": [],
        }

    # Build detailed path
    path_details = []
    for i, node_id in enumerate(path_nodes):
        entry = {
            "node_id": node_id,
            "name": _node_label(db, layer, node_id),
        }
        if i > 0:
            prev_id = path_nodes[i - 1]
            edge_data = G.get_edge_data(prev_id, node_id)
            entry["connection_weight"] = edge_data.get("weight", 1) if edge_data else 1

            # For authors, get shared papers
            if layer == "authors":
                prev_works = set(db.execute(
                    select(models.WorkAuthor.work_id)
                    .where(models.WorkAuthor.author_id == prev_id)
                ).scalars().all())
                curr_works = set(db.execute(
                    select(models.WorkAuthor.work_id)
                    .where(models.WorkAuthor.author_id == node_id)
                ).scalars().all())
                shared = prev_works & curr_works
                entry["shared_papers"] = len(shared)

        path_details.append(entry)

    # Alternative paths (up to 5)
    alt_paths = []
    try:
        all_paths = list(nx.all_shortest_paths(G, source_id, target_id))
        for alt in all_paths[1:5]:
            alt_paths.append([
                {"node_id": n, "name": _node_label(db, layer, n)} for n in alt
            ])
    except nx.NetworkXNoPath:
        pass

    return {
        "path_exists": True,
        "path_length": len(path_nodes) - 1,
        "path": path_details,
        "alternative_paths": alt_paths,
    }


# ── F5: Research Gap Detection ──────────────────────────────────────────

def detect_research_gaps(db: Session,
                         year_min: int | None = None,
                         year_max: int | None = None,
                         min_keyword_count: int = 3,
                         top_n: int = 15) -> List[Dict[str, Any]]:
    """Find structural holes in keyword co-occurrence network."""
    G = _build_nx_graph(db, "keywords", year_min, year_max)

    if G.number_of_nodes() < 4:
        return []

    # Filter low-count keywords
    # Count papers per keyword
    kw_paper_count: dict[int, int] = defaultdict(int)
    wq = select(models.WorkKeyword.keyword_id, models.Work.id).join(
        models.Work, models.WorkKeyword.work_id == models.Work.id
    )
    if year_min is not None:
        wq = wq.where(models.Work.year >= year_min)
    if year_max is not None:
        wq = wq.where(models.Work.year <= year_max)

    for kid, _ in db.execute(wq).all():
        kw_paper_count[kid] += 1

    nodes_to_keep = {n for n in G.nodes() if kw_paper_count.get(n, 0) >= min_keyword_count}
    G = G.subgraph(nodes_to_keep).copy()

    if G.number_of_nodes() < 4:
        return []

    # Community detection on keyword network
    comm_sets = louvain_communities(G, resolution=1.0, seed=42)
    if len(comm_sets) < 2:
        return []

    partition = {}
    comm_keywords: dict[int, list] = {}
    for idx, cs in enumerate(comm_sets):
        for n in cs:
            partition[n] = idx
        # Top keywords by degree
        sub = G.subgraph(cs)
        sorted_nodes = sorted(cs, key=lambda n: sub.degree(n), reverse=True)
        comm_keywords[idx] = sorted_nodes

    # Analyze inter-community gaps
    gaps = []
    for ci, cj in combinations(range(len(comm_sets)), 2):
        nodes_i = comm_sets[ci]
        nodes_j = comm_sets[cj]

        # Intra-community density
        sub_i = G.subgraph(nodes_i)
        sub_j = G.subgraph(nodes_j)
        density_i = nx.density(sub_i) if len(nodes_i) > 1 else 0
        density_j = nx.density(sub_j) if len(nodes_j) > 1 else 0
        intra_density_avg = (density_i + density_j) / 2

        # Inter-community edges
        inter_edges = 0
        inter_weight = 0.0
        for u in nodes_i:
            for v in nodes_j:
                if G.has_edge(u, v):
                    inter_edges += 1
                    inter_weight += G[u][v].get("weight", 1)

        max_inter = len(nodes_i) * len(nodes_j)
        inter_density = inter_edges / max_inter if max_inter > 0 else 0

        if intra_density_avg == 0:
            continue

        gap_score = (intra_density_avg - inter_density) / intra_density_avg

        # Only report substantial gaps
        if gap_score < 0.3:
            continue

        # Find bridge keywords (weakly connecting both communities)
        bridges = []
        for u in nodes_i:
            for v in nodes_j:
                if G.has_edge(u, v) and G[u][v].get("weight", 1) <= 2:
                    bridges.append(_node_label(db, "keywords", u))
                    bridges.append(_node_label(db, "keywords", v))
        bridges = list(set(bridges))[:5]

        top_kw_i = [_node_label(db, "keywords", n) for n in comm_keywords[ci][:3]]
        top_kw_j = [_node_label(db, "keywords", n) for n in comm_keywords[cj][:3]]

        size_product = len(nodes_i) * len(nodes_j)

        gaps.append({
            "community_a": {"id": ci, "top_keywords": top_kw_i, "size": len(nodes_i)},
            "community_b": {"id": cj, "top_keywords": top_kw_j, "size": len(nodes_j)},
            "gap_score": round(gap_score, 3),
            "inter_edges": inter_edges,
            "inter_weight": round(inter_weight, 1),
            "potential_bridges": bridges,
            "suggestion": f"{' / '.join(top_kw_i[:2])} + {' / '.join(top_kw_j[:2])}: active individually but rarely combined",
            "rank_score": round(gap_score * min(size_product, 100), 2),
        })

    gaps.sort(key=lambda x: x["rank_score"], reverse=True)
    return gaps[:top_n]


# ── F6: Strategic Diagram ───────────────────────────────────────────────

def build_strategic_diagram(db: Session,
                            year_min: int | None = None,
                            year_max: int | None = None,
                            min_keyword_count: int = 3) -> Dict[str, Any]:
    """Build Callon's centrality-density strategic diagram for keyword clusters."""
    G = _build_nx_graph(db, "keywords", year_min, year_max)

    if G.number_of_nodes() < 4:
        return {"themes": [], "median_centrality": 0, "median_density": 0}

    # Filter by min keyword count
    kw_paper_count: dict[int, int] = defaultdict(int)
    wq = select(models.WorkKeyword.keyword_id, models.Work.id).join(
        models.Work, models.WorkKeyword.work_id == models.Work.id
    )
    if year_min is not None:
        wq = wq.where(models.Work.year >= year_min)
    if year_max is not None:
        wq = wq.where(models.Work.year <= year_max)

    for kid, _ in db.execute(wq).all():
        kw_paper_count[kid] += 1

    nodes_to_keep = {n for n in G.nodes() if kw_paper_count.get(n, 0) >= min_keyword_count}
    G = G.subgraph(nodes_to_keep).copy()

    if G.number_of_nodes() < 4:
        return {"themes": [], "median_centrality": 0, "median_density": 0}

    # Community detection
    comm_sets = louvain_communities(G, resolution=1.0, seed=42)

    if len(comm_sets) < 2:
        return {"themes": [], "median_centrality": 0, "median_density": 0,
                "message": "Only one community found — network too uniform."}

    themes = []
    for idx, comm_set in enumerate(comm_sets):
        nodes = list(comm_set)
        sub = G.subgraph(nodes)

        # Density: internal cohesion
        density = nx.density(sub) if len(nodes) > 1 else 0.0

        # Centrality: sum of external edge weights
        external_weight = 0.0
        other_nodes = set(G.nodes()) - comm_set
        for u in nodes:
            for v in other_nodes:
                if G.has_edge(u, v):
                    external_weight += G[u][v].get("weight", 1)

        max_external = len(nodes) * len(other_nodes)
        centrality = external_weight / max_external if max_external > 0 else 0

        # Top keywords
        sorted_nodes = sorted(nodes, key=lambda n: sub.degree(n), reverse=True)
        top_kws = [_node_label(db, "keywords", n) for n in sorted_nodes[:5]]

        # Total papers for this cluster
        total_papers = sum(kw_paper_count.get(n, 0) for n in nodes)

        themes.append({
            "cluster_id": idx,
            "label": " / ".join(top_kws[:2]),
            "top_keywords": top_kws,
            "centrality": centrality,
            "density": density,
            "size": len(nodes),
            "total_papers": total_papers,
        })

    # Normalize centrality and density to 0-1
    all_c = [t["centrality"] for t in themes]
    all_d = [t["density"] for t in themes]
    max_c, min_c = max(all_c), min(all_c)
    max_d, min_d = max(all_d), min(all_d)

    for t in themes:
        t["centrality_norm"] = ((t["centrality"] - min_c) / (max_c - min_c)
                                if max_c > min_c else 0.5)
        t["density_norm"] = ((t["density"] - min_d) / (max_d - min_d)
                             if max_d > min_d else 0.5)

        # Classify quadrant
        if t["centrality_norm"] >= 0.5 and t["density_norm"] >= 0.5:
            t["quadrant"] = "Motor"
        elif t["centrality_norm"] < 0.5 and t["density_norm"] >= 0.5:
            t["quadrant"] = "Niche"
        elif t["centrality_norm"] >= 0.5 and t["density_norm"] < 0.5:
            t["quadrant"] = "Basic & Transversal"
        else:
            t["quadrant"] = "Emerging or Declining"

    median_c = sorted(all_c)[len(all_c) // 2] if all_c else 0
    median_d = sorted(all_d)[len(all_d) // 2] if all_d else 0

    return {
        "themes": themes,
        "median_centrality": median_c,
        "median_density": median_d,
    }


# ── F7: Thematic Evolution ──────────────────────────────────────────────

def build_thematic_evolution(db: Session, n_periods: int = 3,
                             min_keyword_count: int = 2) -> Dict[str, Any]:
    """Show how keyword clusters evolve across time periods."""
    # Get year range
    from sqlalchemy import func as sqlfunc
    year_min_val = db.execute(select(sqlfunc.min(models.Work.year)).where(
        models.Work.year.isnot(None)
    )).scalar()
    year_max_val = db.execute(select(sqlfunc.max(models.Work.year)).where(
        models.Work.year.isnot(None)
    )).scalar()

    if year_min_val is None or year_max_val is None or year_min_val == year_max_val:
        return {"periods": [], "nodes": [], "flows": [], "events": [],
                "message": "Not enough temporal data for thematic evolution."}

    # Divide into periods
    span = year_max_val - year_min_val + 1
    period_size = max(span // n_periods, 1)
    periods = []
    for i in range(n_periods):
        start = year_min_val + i * period_size
        end = start + period_size - 1 if i < n_periods - 1 else year_max_val
        periods.append({"label": f"{start}-{end}", "start": start, "end": end})

    # For each period, build keyword graph and detect communities
    period_communities: list[list[set]] = []
    period_kw_counts: list[dict[int, int]] = []

    for p in periods:
        G = _build_nx_graph(db, "keywords", p["start"], p["end"])

        # Count papers per keyword in this period
        kw_counts: dict[int, int] = defaultdict(int)
        wq = select(models.WorkKeyword.keyword_id, models.Work.id).join(
            models.Work, models.WorkKeyword.work_id == models.Work.id
        ).where(models.Work.year >= p["start"], models.Work.year <= p["end"])

        for kid, _ in db.execute(wq).all():
            kw_counts[kid] += 1

        # Filter
        keep = {n for n in G.nodes() if kw_counts.get(n, 0) >= min_keyword_count}
        G = G.subgraph(keep).copy()

        if G.number_of_nodes() >= 2:
            comms = louvain_communities(G, resolution=1.0, seed=42)
        else:
            comms = [frozenset(G.nodes())] if G.number_of_nodes() > 0 else []

        period_communities.append([set(c) for c in comms])
        period_kw_counts.append(kw_counts)

    # Build nodes for Sankey
    sankey_nodes = []
    for pi, comms in enumerate(period_communities):
        for ci, comm in enumerate(comms):
            sorted_kws = sorted(comm, key=lambda n: period_kw_counts[pi].get(n, 0), reverse=True)
            top_labels = [_node_label(db, "keywords", n) for n in sorted_kws[:2]]
            size = sum(period_kw_counts[pi].get(n, 0) for n in comm)
            sankey_nodes.append({
                "id": f"P{pi}_C{ci}",
                "label": " / ".join(top_labels) if top_labels else f"Cluster {ci}",
                "period": pi,
                "size": size,
                "keywords": [_node_label(db, "keywords", n) for n in sorted_kws[:5]],
                "keyword_ids": list(comm),
            })

    # Build flows between consecutive periods
    flows = []
    events = []
    for pi in range(len(periods) - 1):
        comms_curr = period_communities[pi]
        comms_next = period_communities[pi + 1]

        successor_map: dict[int, list] = defaultdict(list)
        predecessor_map: dict[int, list] = defaultdict(list)

        for ci, comm_c in enumerate(comms_curr):
            for ni, comm_n in enumerate(comms_next):
                overlap = comm_c & comm_n
                union = comm_c | comm_n
                if overlap and union:
                    overlap_ratio = len(overlap) / len(union)
                    if overlap_ratio >= 0.05:
                        weight = len(overlap)
                        flows.append({
                            "source": f"P{pi}_C{ci}",
                            "target": f"P{pi+1}_C{ni}",
                            "weight": weight,
                            "overlap": round(overlap_ratio, 3),
                        })
                        successor_map[ci].append(ni)
                        predecessor_map[ni].append(ci)

        # Detect evolution events
        for ci in range(len(comms_curr)):
            successors = successor_map.get(ci, [])
            if len(successors) == 0:
                top_kw = _node_label(db, "keywords", next(iter(comms_curr[ci]))) if comms_curr[ci] else "?"
                events.append({
                    "type": "disappearance",
                    "period": f"{periods[pi]['label']} -> {periods[pi+1]['label']}",
                    "description": f"'{top_kw}' cluster disappeared",
                })
            elif len(successors) > 1:
                top_kw = _node_label(db, "keywords", next(iter(comms_curr[ci]))) if comms_curr[ci] else "?"
                events.append({
                    "type": "split",
                    "period": f"{periods[pi]['label']} -> {periods[pi+1]['label']}",
                    "description": f"'{top_kw}' cluster split into {len(successors)} clusters",
                })

        for ni in range(len(comms_next)):
            predecessors = predecessor_map.get(ni, [])
            if len(predecessors) == 0:
                top_kw = _node_label(db, "keywords", next(iter(comms_next[ni]))) if comms_next[ni] else "?"
                events.append({
                    "type": "emergence",
                    "period": f"{periods[pi]['label']} -> {periods[pi+1]['label']}",
                    "description": f"'{top_kw}' cluster emerged as new theme",
                })
            elif len(predecessors) > 1:
                top_kw = _node_label(db, "keywords", next(iter(comms_next[ni]))) if comms_next[ni] else "?"
                events.append({
                    "type": "merge",
                    "period": f"{periods[pi]['label']} -> {periods[pi+1]['label']}",
                    "description": f"{len(predecessors)} clusters merged into '{top_kw}'",
                })

    return {
        "periods": periods,
        "nodes": sankey_nodes,
        "flows": flows,
        "events": events,
    }
