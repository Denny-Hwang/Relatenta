/**
 * Small undirected weighted graph + algorithms that replace the NetworkX
 * calls used by app/services_insight.py: Louvain community detection,
 * modularity, density, BFS shortest paths, all shortest paths.
 */

export class UGraph {
  constructor() { this.adj = new Map(); }
  addNode(n) { if (!this.adj.has(n)) this.adj.set(n, new Map()); }
  addEdge(u, v, w = 1) {
    this.addNode(u); this.addNode(v);
    this.adj.get(u).set(v, w);
    this.adj.get(v).set(u, w);
  }
  has(n) { return this.adj.has(n); }
  hasEdge(u, v) { return this.adj.has(u) && this.adj.get(u).has(v); }
  weight(u, v) { return this.adj.get(u)?.get(v) ?? null; }
  nodes() { return [...this.adj.keys()]; }
  neighbors(n) { return this.adj.has(n) ? [...this.adj.get(n).keys()].filter((x) => x !== n) : []; }
  degree(n) { return this.adj.has(n) ? this.adj.get(n).size : 0; }
  numNodes() { return this.adj.size; }
  numEdges() { return countEdges(this); }
  /** Weighted degree (sum of incident edge weights; self-loops count twice like NetworkX). */
  strength(n) { let s = 0; for (const [v, w] of this.adj.get(n) || []) s += v === n ? 2 * w : w; return s; }
  totalWeight() { let m = 0; for (const [u, nb] of this.adj) for (const [v, w] of nb) m += u === v ? 2 * w : w; return m / 2; }
  subgraph(nodeSet) {
    const s = new Set(nodeSet);
    const g = new UGraph();
    for (const n of s) if (this.adj.has(n)) g.addNode(n);
    for (const u of s) for (const [v, w] of this.adj.get(u) || []) if (s.has(v)) g.addEdge(u, v, w);
    return g;
  }
}

function countEdges(g) {
  let twice = 0, loops = 0;
  for (const [u, nb] of g.adj) for (const v of nb.keys()) { if (u === v) loops++; else twice++; }
  return twice / 2 + loops;
}

export function density(g) {
  const n = g.numNodes();
  if (n <= 1) return 0;
  return (2 * countEdges(g)) / (n * (n - 1));
}

/** Deterministic PRNG (mulberry32) so Louvain results are reproducible. */
export function seededRandom(seed = 42) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function shuffle(arr, rnd) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(rnd() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

/**
 * Louvain community detection (Blondel et al. 2008), mirroring
 * networkx.algorithms.community.louvain_communities (resolution, threshold).
 * Returns an array of Sets of original node ids.
 */
export function louvainCommunities(g, resolution = 1, threshold = 1e-7, seed = 42) {
  const rnd = seededRandom(seed);
  const nodes = g.nodes();
  if (!nodes.length) return [];
  const m = g.totalWeight();
  if (m === 0) return nodes.map((n) => new Set([n]));

  // Working (aggregated) graph as index-based adjacency: adj[i] = Map<j, weight>.
  const idxOf = new Map(nodes.map((n, i) => [n, i]));
  let adj = nodes.map((n) => {
    const row = new Map();
    for (const [v, w] of g.adj.get(n)) row.set(idxOf.get(v), w);
    return row;
  });
  // partition[k] = index of the super-node that original node k currently belongs to
  const partition = nodes.map((_, i) => i);
  let currentQ = modularityIdx(adj, adj.map((_, i) => i), m, resolution);

  for (let level = 0; level < 100; level++) {
    const strength = adj.map((row, i) => { let s = 0; for (const [j, w] of row) s += i === j ? 2 * w : w; return s; });
    const community = adj.map((_, i) => i);
    const tot = strength.slice();
    let improved = true, moved = false;
    while (improved) {
      improved = false;
      for (const i of shuffle(adj.map((_, k) => k), rnd)) {
        const ci = community[i];
        const ki = strength[i];
        const w2c = new Map();
        for (const [j, w] of adj[i]) { if (j === i) continue; const cj = community[j]; w2c.set(cj, (w2c.get(cj) || 0) + w); }
        tot[ci] -= ki;
        const removeCost = -(w2c.get(ci) || 0) / m + (resolution * tot[ci] * ki) / (2 * m * m);
        let best = ci, bestGain = 0;
        for (const [cj, wij] of w2c) {
          const gain = removeCost + wij / m - (resolution * tot[cj] * ki) / (2 * m * m);
          if (gain > bestGain) { bestGain = gain; best = cj; }
        }
        tot[best] += ki;
        if (best !== ci) { community[i] = best; improved = true; moved = true; }
      }
    }
    if (!moved) break;
    const q = modularityIdx(adj, community, m, resolution);
    if (q - currentQ <= threshold) break;
    currentQ = q;

    // Relabel communities densely and aggregate into the next-level graph.
    const relabel = new Map();
    for (const c of community) if (!relabel.has(c)) relabel.set(c, relabel.size);
    const newAdj = Array.from({ length: relabel.size }, () => new Map());
    for (let i = 0; i < adj.length; i++) {
      const ci = relabel.get(community[i]);
      for (const [j, w] of adj[i]) {
        const cj = relabel.get(community[j]);
        // Every non-loop edge is visited twice (i->j, j->i): add half each time
        // so the aggregated weight equals the summed original weight.
        const add = i === j ? w : w / 2;
        newAdj[ci].set(cj, (newAdj[ci].get(cj) || 0) + add);
      }
    }
    // Off-diagonal entries were accumulated from both endpoints (half + half per
    // edge in each direction) which yields the right symmetric total already.
    for (let k = 0; k < partition.length; k++) partition[k] = relabel.get(community[partition[k]]);
    adj = newAdj;
  }

  const groups = new Map();
  nodes.forEach((node, i) => {
    const c = partition[i];
    if (!groups.has(c)) groups.set(c, new Set());
    groups.get(c).add(node);
  });
  return [...groups.values()];
}

function modularityIdx(adj, community, m, resolution) {
  const inW = new Map(), tot = new Map();
  for (let i = 0; i < adj.length; i++) {
    const ci = community[i];
    let s = 0;
    for (const [j, w] of adj[i]) {
      const ww = i === j ? 2 * w : w;
      s += ww;
      if (community[j] === ci) inW.set(ci, (inW.get(ci) || 0) + ww);
    }
    tot.set(ci, (tot.get(ci) || 0) + s);
  }
  let q = 0;
  for (const [c, t] of tot) q += (inW.get(c) || 0) / (2 * m) - resolution * (t / (2 * m)) ** 2;
  return q;
}

/** networkx.community.modularity for undirected weighted graphs. */
export function modularity(g, communities, resolution = 1) {
  const m = g.totalWeight();
  if (m === 0) return 0;
  let q = 0;
  for (const comm of communities) {
    const s = comm instanceof Set ? comm : new Set(comm);
    let lc = 0, dc = 0;
    for (const u of s) {
      dc += g.strength(u);
      for (const [v, w] of g.adj.get(u) || []) if (s.has(v)) lc += u === v ? 2 * w : w;
    }
    lc /= 2;
    q += lc / m - resolution * (dc / (2 * m)) ** 2;
  }
  return q;
}

/** BFS shortest path (unweighted hops, like nx.shortest_path without weight). */
export function shortestPath(g, source, target) {
  if (!g.has(source) || !g.has(target)) return null;
  if (source === target) return [source];
  const prev = new Map([[source, null]]);
  const queue = [source];
  let head = 0;
  while (head < queue.length) {
    const u = queue[head++];
    for (const v of g.neighbors(u)) {
      if (prev.has(v)) continue;
      prev.set(v, u);
      if (v === target) {
        const path = [v];
        let cur = u;
        while (cur !== null) { path.push(cur); cur = prev.get(cur); }
        return path.reverse();
      }
      queue.push(v);
    }
  }
  return null;
}

export function shortestPathLength(g, source, target) {
  const p = shortestPath(g, source, target);
  return p ? p.length - 1 : -1;
}

/** All shortest paths between two nodes (capped to `limit` results). */
export function allShortestPaths(g, source, target, limit = 50) {
  if (!g.has(source) || !g.has(target)) return [];
  const dist = new Map([[source, 0]]);
  const preds = new Map([[source, []]]);
  const queue = [source];
  let head = 0;
  while (head < queue.length) {
    const u = queue[head++];
    if (u === target) break;
    for (const v of g.neighbors(u)) {
      if (!dist.has(v)) { dist.set(v, dist.get(u) + 1); preds.set(v, [u]); queue.push(v); }
      else if (dist.get(v) === dist.get(u) + 1) preds.get(v).push(u);
    }
  }
  if (!dist.has(target)) return [];
  const out = [];
  const walk = (node, acc) => {
    if (out.length >= limit) return;
    if (node === source) { out.push([source, ...acc]); return; }
    for (const p of preds.get(node)) walk(p, [node, ...acc]);
  };
  walk(target, []);
  return out;
}
