/**
 * Research insight analyses — port of app/services_insight.py.
 * Community detection, burst detection, collaborator recommendation,
 * shortest path, research gaps, strategic diagram, thematic evolution.
 */
import { UGraph, louvainCommunities, modularity, density, shortestPath, shortestPathLength, allShortestPaths } from "./netalgo.js";

/** Python-compatible round(): exact .5 ties round half-to-even (2.125 -> 2.12). */
const round = (x, d) => {
  const f = 10 ** d;
  const scaled = x * f;
  const isTie = Number.isInteger(scaled * 2) && !Number.isInteger(scaled);
  if (isTie) {
    const fl = Math.floor(scaled);
    return (fl % 2 === 0 ? fl : fl + 1) / f;
  }
  return Math.round(scaled) / f;
};

function worksInRange(store, yearMin, yearMax) {
  return store.works.filter((w) => {
    if (yearMin != null && (w.year == null || w.year < yearMin)) return false;
    if (yearMax != null && (w.year == null || w.year > yearMax)) return false;
    return true;
  });
}

/** Port of _build_nx_graph. Year filters apply to the keywords layer only (as in Python). */
export function buildNetworkGraph(store, layer, yearMin = null, yearMax = null, minWeight = 0.0) {
  const G = new UGraph();
  if (layer === "authors") {
    for (const e of store.coauthorEdges) if (e.weight >= minWeight) G.addEdge(e.a_id, e.b_id, e.weight);
  } else if (layer === "keywords") {
    const edgeMap = new Map();
    for (const w of worksInRange(store, yearMin, yearMax)) {
      const kws = [...new Set(store.keywordsOfWork(w.id).map((r) => r.keyword_id))].sort((a, b) => a - b);
      for (let i = 0; i < kws.length; i++) for (let j = i + 1; j < kws.length; j++) {
        const key = kws[i] + "|" + kws[j];
        edgeMap.set(key, (edgeMap.get(key) || 0) + 1);
      }
    }
    for (const [key, w] of edgeMap) {
      if (w >= minWeight) { const [k1, k2] = key.split("|").map(Number); G.addEdge(k1, k2, w); }
    }
  } else if (layer === "orgs") {
    for (const e of store.orgEdges) if (e.weight >= minWeight) G.addEdge(e.org1_id, e.org2_id, e.weight);
  } else if (layer === "nations") {
    for (const e of store.nationEdges) if (e.weight >= minWeight) G.addEdge(e.n1, e.n2, e.weight);
  }
  return G;
}

export function nodeLabel(store, layer, nodeId) {
  if (layer === "authors") return store.getAuthor(nodeId)?.display_name ?? String(nodeId);
  if (layer === "keywords") return store.getKeyword(nodeId)?.term_display ?? String(nodeId);
  if (layer === "orgs") return store.getOrg(nodeId)?.name ?? String(nodeId);
  return String(nodeId);
}

function keywordPaperCounts(store, yearMin, yearMax) {
  const cnt = new Map();
  for (const w of worksInRange(store, yearMin, yearMax)) {
    for (const r of store.keywordsOfWork(w.id)) cnt.set(r.keyword_id, (cnt.get(r.keyword_id) || 0) + 1);
  }
  return cnt;
}

// ── F1: Community Detection ──────────────────────────────────────────────
export function detectCommunities(store, layer = "authors", resolution = 1.0, yearMin = null, yearMax = null) {
  const G = buildNetworkGraph(store, layer, yearMin, yearMax);
  if (G.numNodes() < 2) {
    return { communities: {}, partition: new Map(), modularity: 0, num_communities: 0, message: "Not enough nodes for community detection." };
  }
  const sets = louvainCommunities(G, resolution);
  const partition = new Map();
  const communities = {};
  sets.forEach((set, idx) => {
    const members = [...set];
    members.forEach((n) => partition.set(n, idx));
    const sub = G.subgraph(members);
    const dens = sub.numNodes() > 1 ? density(sub) : 0;
    let label = `Community ${idx}`;
    if (members.length) {
      let top = members[0], topDeg = -1;
      for (const n of members) { const d = sub.degree(n); if (d > topDeg) { topDeg = d; top = n; } }
      label = nodeLabel(store, layer, top);
    }
    communities[idx] = {
      nodes: members.map((n) => nodeLabel(store, layer, n)),
      node_ids: members, size: sub.numNodes(), density: round(dens, 3), label,
    };
  });
  return { communities, partition, modularity: round(modularity(G, sets), 4), num_communities: sets.length };
}

// ── F2: Burst Detection ──────────────────────────────────────────────────
export function detectBursts(store, windowYears = 3, minPapers = 3) {
  const rows = [];
  for (const w of store.works) {
    if (w.year == null) continue;
    for (const r of store.keywordsOfWork(w.id)) rows.push([r.keyword_id, w.year]);
  }
  if (!rows.length) return [];
  const kwYear = new Map();
  for (const [kid, year] of rows) {
    if (!kwYear.has(kid)) kwYear.set(kid, new Map());
    const m = kwYear.get(kid);
    m.set(year, (m.get(year) || 0) + 1);
  }
  const allYears = [...new Set(rows.map((r) => r[1]))].sort((a, b) => a - b);
  if (allYears.length < 2) return [];
  const maxYear = allYears[allYears.length - 1];
  const windowStart = maxYear - windowYears + 1;
  const baselineYears = allYears.filter((y) => y < windowStart);
  const recentYears = allYears.filter((y) => y >= windowStart);
  const results = [];
  for (const [kid, yc] of kwYear) {
    let total = 0; for (const v of yc.values()) total += v;
    if (total < minPapers) continue;
    const sum = (ys) => ys.reduce((s, y) => s + (yc.get(y) || 0), 0);
    const baselineAvg = sum(baselineYears) / Math.max(baselineYears.length, 1);
    const recentAvg = sum(recentYears) / Math.max(recentYears.length, 1);
    const burst = (recentAvg - baselineAvg) / Math.max(baselineAvg, 0.5);
    const trend = allYears.map((y) => yc.get(y) || 0);
    let status;
    if (burst > 2.0) status = "burst"; else if (burst > 0.5) status = "growing"; else if (burst > -0.3) status = "stable"; else status = "declining";
    results.push({
      keyword_id: kid, keyword: store.getKeyword(kid)?.term_display ?? String(kid),
      burst_score: round(burst, 2), baseline_avg: round(baselineAvg, 2), recent_avg: round(recentAvg, 2),
      total_papers: total, trend, years: allYears, status,
    });
  }
  results.sort((a, b) => b.burst_score - a.burst_score);
  return results;
}

// ── F3: Collaborator Recommendation ──────────────────────────────────────
export function recommendCollaborators(store, authorId, topN = 10) {
  const G = buildNetworkGraph(store, "authors");
  if (!G.has(authorId)) return [];
  const authorKeywords = new Map();
  for (const w of store.works) {
    const kws = store.keywordsOfWork(w.id);
    if (!kws.length) continue;
    for (const wa of store.authorsOfWork(w.id)) {
      if (!authorKeywords.has(wa.author_id)) authorKeywords.set(wa.author_id, new Set());
      const s = authorKeywords.get(wa.author_id);
      for (const k of kws) s.add(k.keyword_id);
    }
  }
  const target = authorKeywords.get(authorId);
  if (!target || !target.size) return [];
  const targetNeighbors = new Set(G.neighbors(authorId));
  const excluded = new Set(targetNeighbors); excluded.add(authorId);
  const maxNeighbors = Math.max(targetNeighbors.size, 1);
  const results = [];
  for (const a of store.authors) {
    const cand = a.id;
    if (excluded.has(cand)) continue;
    const ck = authorKeywords.get(cand);
    if (!ck || !ck.size) continue;
    const inter = [...target].filter((k) => ck.has(k));
    const union = new Set([...target, ...ck]);
    const jaccard = union.size ? inter.length / union.size : 0;
    if (jaccard < 0.05) continue;
    const candNeighbors = new Set(G.has(cand) ? G.neighbors(cand) : []);
    const common = [...targetNeighbors].filter((n) => candNeighbors.has(n));
    const cnScore = common.length / maxNeighbors;
    const unique = [...ck].filter((k) => !target.has(k));
    const complementarity = union.size ? unique.length / union.size : 0;
    const score = 0.5 * jaccard + 0.3 * cnScore + 0.2 * complementarity;
    const pathLen = G.has(cand) ? shortestPathLength(G, authorId, cand) : -1;
    results.push({
      author_id: cand, author_name: nodeLabel(store, "authors", cand), score: round(score, 3),
      jaccard_similarity: round(jaccard, 3), common_neighbors: common.length,
      common_neighbor_names: common.slice(0, 5).map((n) => nodeLabel(store, "authors", n)),
      shared_keywords: inter.slice(0, 5).map((k) => nodeLabel(store, "keywords", k)),
      unique_keywords: unique.slice(0, 5).map((k) => nodeLabel(store, "keywords", k)),
      path_length: pathLen,
    });
  }
  results.sort((a, b) => b.score - a.score);
  return results.slice(0, topN);
}

// ── F4: Shortest Path ────────────────────────────────────────────────────
export function findShortestPath(store, sourceId, targetId, layer = "authors") {
  const G = buildNetworkGraph(store, layer);
  if (!G.has(sourceId) || !G.has(targetId)) {
    const missing = [];
    if (!G.has(sourceId)) missing.push(nodeLabel(store, layer, sourceId));
    if (!G.has(targetId)) missing.push(nodeLabel(store, layer, targetId));
    return { path_exists: false, message: `Node(s) not found in network: ${missing.join(", ")}`, path_length: -1, path: [] };
  }
  const pathNodes = shortestPath(G, sourceId, targetId);
  if (!pathNodes) return { path_exists: false, message: "No collaboration path found between these nodes.", path_length: -1, path: [] };
  const worksOf = (aid) => {
    const s = new Set();
    for (const w of store.works) if (store.authorsOfWork(w.id).some((r) => r.author_id === aid)) s.add(w.id);
    return s;
  };
  const path = pathNodes.map((nodeId, i) => {
    const entry = { node_id: nodeId, name: nodeLabel(store, layer, nodeId) };
    if (i > 0) {
      const prev = pathNodes[i - 1];
      entry.connection_weight = G.weight(prev, nodeId) ?? 1;
      if (layer === "authors") {
        const pw = worksOf(prev), cw = worksOf(nodeId);
        entry.shared_papers = [...pw].filter((x) => cw.has(x)).length;
      }
    }
    return entry;
  });
  const alternative_paths = allShortestPaths(G, sourceId, targetId, 5).slice(1, 5)
    .map((alt) => alt.map((n) => ({ node_id: n, name: nodeLabel(store, layer, n) })));
  return { path_exists: true, path_length: pathNodes.length - 1, path, alternative_paths };
}

// ── F5: Research Gap Detection ───────────────────────────────────────────
export function detectResearchGaps(store, yearMin = null, yearMax = null, minKeywordCount = 3, topN = 15) {
  let G = buildNetworkGraph(store, "keywords", yearMin, yearMax);
  if (G.numNodes() < 4) return [];
  const kwCount = keywordPaperCounts(store, yearMin, yearMax);
  G = G.subgraph(G.nodes().filter((n) => (kwCount.get(n) || 0) >= minKeywordCount));
  if (G.numNodes() < 4) return [];
  const commSets = louvainCommunities(G, 1.0);
  if (commSets.length < 2) return [];
  const commKeywords = commSets.map((cs) => {
    const sub = G.subgraph(cs);
    return [...cs].sort((a, b) => sub.degree(b) - sub.degree(a));
  });
  const gaps = [];
  for (let ci = 0; ci < commSets.length; ci++) for (let cj = ci + 1; cj < commSets.length; cj++) {
    const ni = commSets[ci], nj = commSets[cj];
    const di = ni.size > 1 ? density(G.subgraph(ni)) : 0;
    const dj = nj.size > 1 ? density(G.subgraph(nj)) : 0;
    const intraAvg = (di + dj) / 2;
    let interEdges = 0, interWeight = 0;
    const bridges = new Set();
    for (const u of ni) for (const v of nj) {
      if (G.hasEdge(u, v)) {
        interEdges++;
        const w = G.weight(u, v) ?? 1;
        interWeight += w;
        if (w <= 2) { bridges.add(nodeLabel(store, "keywords", u)); bridges.add(nodeLabel(store, "keywords", v)); }
      }
    }
    const maxInter = ni.size * nj.size;
    const interDensity = maxInter > 0 ? interEdges / maxInter : 0;
    if (intraAvg === 0) continue;
    const gapScore = (intraAvg - interDensity) / intraAvg;
    if (gapScore < 0.3) continue;
    const topI = commKeywords[ci].slice(0, 3).map((n) => nodeLabel(store, "keywords", n));
    const topJ = commKeywords[cj].slice(0, 3).map((n) => nodeLabel(store, "keywords", n));
    const sizeProduct = ni.size * nj.size;
    gaps.push({
      community_a: { id: ci, top_keywords: topI, size: ni.size },
      community_b: { id: cj, top_keywords: topJ, size: nj.size },
      gap_score: round(gapScore, 3), inter_edges: interEdges, inter_weight: round(interWeight, 1),
      potential_bridges: [...bridges].slice(0, 5),
      suggestion: `${topI.slice(0, 2).join(" / ")} + ${topJ.slice(0, 2).join(" / ")}: active individually but rarely combined`,
      rank_score: round(gapScore * Math.min(sizeProduct, 100), 2),
    });
  }
  gaps.sort((a, b) => b.rank_score - a.rank_score);
  return gaps.slice(0, topN);
}

// ── F6: Strategic Diagram ────────────────────────────────────────────────
export function buildStrategicDiagram(store, yearMin = null, yearMax = null, minKeywordCount = 3) {
  const empty = { themes: [], median_centrality: 0, median_density: 0 };
  let G = buildNetworkGraph(store, "keywords", yearMin, yearMax);
  if (G.numNodes() < 4) return empty;
  const kwCount = keywordPaperCounts(store, yearMin, yearMax);
  G = G.subgraph(G.nodes().filter((n) => (kwCount.get(n) || 0) >= minKeywordCount));
  if (G.numNodes() < 4) return empty;
  const commSets = louvainCommunities(G, 1.0);
  if (commSets.length < 2) return { ...empty, message: "Only one community found — network too uniform." };
  const allNodes = G.nodes();
  const themes = commSets.map((set, idx) => {
    const nodes = [...set];
    const sub = G.subgraph(nodes);
    const dens = nodes.length > 1 ? density(sub) : 0;
    let external = 0;
    const others = allNodes.filter((n) => !set.has(n));
    for (const u of nodes) for (const v of others) if (G.hasEdge(u, v)) external += G.weight(u, v) ?? 1;
    const maxExternal = nodes.length * others.length;
    const centrality = maxExternal > 0 ? external / maxExternal : 0;
    const sorted = nodes.slice().sort((a, b) => sub.degree(b) - sub.degree(a));
    const topKws = sorted.slice(0, 5).map((n) => nodeLabel(store, "keywords", n));
    const totalPapers = nodes.reduce((s, n) => s + (kwCount.get(n) || 0), 0);
    return { cluster_id: idx, label: topKws.slice(0, 2).join(" / "), top_keywords: topKws, centrality, density: dens, size: nodes.length, total_papers: totalPapers };
  });
  const allC = themes.map((t) => t.centrality), allD = themes.map((t) => t.density);
  const maxC = Math.max(...allC), minC = Math.min(...allC), maxD = Math.max(...allD), minD = Math.min(...allD);
  for (const t of themes) {
    t.centrality_norm = maxC > minC ? (t.centrality - minC) / (maxC - minC) : 0.5;
    t.density_norm = maxD > minD ? (t.density - minD) / (maxD - minD) : 0.5;
    if (t.centrality_norm >= 0.5 && t.density_norm >= 0.5) t.quadrant = "Motor";
    else if (t.centrality_norm < 0.5 && t.density_norm >= 0.5) t.quadrant = "Niche";
    else if (t.centrality_norm >= 0.5 && t.density_norm < 0.5) t.quadrant = "Basic & Transversal";
    else t.quadrant = "Emerging or Declining";
  }
  const med = (arr) => { const s = arr.slice().sort((a, b) => a - b); return s.length ? s[Math.floor(s.length / 2)] : 0; };
  return { themes, median_centrality: med(allC), median_density: med(allD) };
}

// ── F7: Thematic Evolution ───────────────────────────────────────────────
export function buildThematicEvolution(store, nPeriods = 3, minKeywordCount = 2) {
  const [yMin, yMax] = store.yearRange();
  if (yMin == null || yMax == null || yMin === yMax) {
    return { periods: [], nodes: [], flows: [], events: [], message: "Not enough temporal data for thematic evolution." };
  }
  const span = yMax - yMin + 1;
  const periodSize = Math.max(Math.floor(span / nPeriods), 1);
  const periods = [];
  for (let i = 0; i < nPeriods; i++) {
    const start = yMin + i * periodSize;
    const end = i < nPeriods - 1 ? start + periodSize - 1 : yMax;
    periods.push({ label: `${start}-${end}`, start, end });
  }
  const periodComms = [], periodCounts = [];
  for (const p of periods) {
    let G = buildNetworkGraph(store, "keywords", p.start, p.end);
    const cnt = keywordPaperCounts(store, p.start, p.end);
    G = G.subgraph(G.nodes().filter((n) => (cnt.get(n) || 0) >= minKeywordCount));
    let comms;
    if (G.numNodes() >= 2) comms = louvainCommunities(G, 1.0);
    else comms = G.numNodes() > 0 ? [new Set(G.nodes())] : [];
    periodComms.push(comms.map((c) => new Set(c)));
    periodCounts.push(cnt);
  }
  const nodes = [];
  periodComms.forEach((comms, pi) => {
    comms.forEach((comm, ci) => {
      const sorted = [...comm].sort((a, b) => (periodCounts[pi].get(b) || 0) - (periodCounts[pi].get(a) || 0));
      const top = sorted.slice(0, 2).map((n) => nodeLabel(store, "keywords", n));
      nodes.push({
        id: `P${pi}_C${ci}`, label: top.length ? top.join(" / ") : `Cluster ${ci}`, period: pi,
        size: [...comm].reduce((s, n) => s + (periodCounts[pi].get(n) || 0), 0),
        keywords: sorted.slice(0, 5).map((n) => nodeLabel(store, "keywords", n)), keyword_ids: [...comm],
      });
    });
  });
  const flows = [], events = [];
  for (let pi = 0; pi < periods.length - 1; pi++) {
    const cur = periodComms[pi], nxt = periodComms[pi + 1];
    const succ = new Map(), pred = new Map();
    cur.forEach((cc, ci) => nxt.forEach((cn, ni) => {
      const overlap = [...cc].filter((k) => cn.has(k)).length;
      const union = new Set([...cc, ...cn]).size;
      if (overlap && union) {
        const ratio = overlap / union;
        if (ratio >= 0.05) {
          flows.push({ source: `P${pi}_C${ci}`, target: `P${pi + 1}_C${ni}`, weight: overlap, overlap: round(ratio, 3) });
          if (!succ.has(ci)) succ.set(ci, []); succ.get(ci).push(ni);
          if (!pred.has(ni)) pred.set(ni, []); pred.get(ni).push(ci);
        }
      }
    }));
    const per = `${periods[pi].label} -> ${periods[pi + 1].label}`;
    const first = (set) => (set.size ? nodeLabel(store, "keywords", set.values().next().value) : "?");
    cur.forEach((cc, ci) => {
      const s = succ.get(ci) || [];
      if (!s.length) events.push({ type: "disappearance", period: per, description: `'${first(cc)}' cluster disappeared` });
      else if (s.length > 1) events.push({ type: "split", period: per, description: `'${first(cc)}' cluster split into ${s.length} clusters` });
    });
    nxt.forEach((cn, ni) => {
      const p = pred.get(ni) || [];
      if (!p.length) events.push({ type: "emergence", period: per, description: `'${first(cn)}' cluster emerged as new theme` });
      else if (p.length > 1) events.push({ type: "merge", period: per, description: `${p.length} clusters merged into '${first(cn)}'` });
    });
  }
  return { periods, nodes, flows, events };
}
