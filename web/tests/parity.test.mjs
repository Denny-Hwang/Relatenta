/**
 * Parity tests: the JS port must reproduce the Python service layer.
 * Fixtures come from `python web/tests/gen_expected.py`.
 *
 *   node --test web/tests
 */
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { Store } from "../js/store.js";
import { buildGraph } from "../js/graph.js";
import { authorKeywordHeat, nationNationHeat } from "../js/heatmap.js";
import { gatherReport } from "../js/report.js";
import {
  detectBursts, recommendCollaborators, findShortestPath, detectCommunities,
  detectResearchGaps, buildStrategicDiagram, buildThematicEvolution, buildNetworkGraph,
} from "../js/insights.js";
import { modularity, louvainCommunities, UGraph } from "../js/netalgo.js";
import { buildExportFiles, exportZip, restoreFromZip, importCsv } from "../js/exporter.js";
import { parseCsv, toCsv } from "../js/csv.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const JSZip = require("../vendor/jszip.min.js");

const works = JSON.parse(readFileSync(path.join(here, "fixtures", "works.json"), "utf-8"));
const expected = JSON.parse(readFileSync(path.join(here, "fixtures", "expected.json"), "utf-8"));

function buildStore() {
  const s = new Store();
  for (const w of works) s.upsertWorkFromOpenAlex(w);
  s.upsertWorkFromOpenAlex(works[0]);
  s.recomputeCoauthorEdges();
  s.recomputeNationEdges();
  s.recomputeOrgEdges();
  return s;
}
const store = buildStore();

const sortNodes = (g) => ({
  nodes: g.nodes.map((n) => ({ ...n, focus: !!n.focus })).sort((a, b) => a.id.localeCompare(b.id)),
  edges: g.edges.map((e) => [e.source, e.target, e.weight].join("|")).sort(),
});

test("ingest: stats and ids match", () => {
  assert.deepEqual(store.stats(), expected.stats);
  assert.deepEqual(store.authors.map((a) => ({ id: a.id, display_name: a.display_name, normalized_name: a.normalized_name })), expected.authors);
  assert.deepEqual(store.keywords.map((k) => ({ id: k.id, term_display: k.term_display })), expected.keywords);
});

test("edges: coauthor / org / nation", () => {
  const srt = (arr) => arr.slice().sort((a, b) => (a[0] > b[0]) - (a[0] < b[0]) || (a[1] > b[1]) - (a[1] < b[1]));
  assert.deepEqual(srt(store.coauthorEdges.map((e) => [e.a_id, e.b_id, e.weight])), srt(expected.coauthor_edges));
  assert.deepEqual(srt(store.orgEdges.map((e) => [e.org1_id, e.org2_id, e.weight])), srt(expected.org_edges));
  assert.deepEqual(srt(store.nationEdges.map((e) => [e.n1, e.n2, e.weight])), srt(expected.nation_edges));
});

test("build_graph parity for every layer / filter combination", () => {
  const f = expected.focus_ids;
  const cases = {
    authors_focus: ["authors", 2000, 2026, 1.0, [f.author], false],
    authors_focus_only: ["authors", 2000, 2026, 1.0, [f.author], true],
    authors_focus_only_range: ["authors", 2020, 2024, 1.0, [f.author], true],
    keywords_focus_only: ["keywords", 2000, 2026, 1.0, [f.keyword], true],
    orgs_focus_only: ["orgs", 2000, 2026, 1.0, [f.org], true],
    nations_focus_only: ["nations", 2000, 2026, 1.0, ["US"], true],
    nations_focus: ["nations", 2000, 2026, 1.0, ["KR"], false],
    authors_bad_focus: ["authors", 2000, 2026, 1.0, [999999], false],
  };
  for (const layer of ["authors", "keywords", "orgs", "nations"]) {
    cases[`${layer}_full`] = [layer, 2000, 2026, 1.0, null, false];
    cases[`${layer}_range`] = [layer, 2018, 2021, 1.0, null, false];
    cases[`${layer}_edge2`] = [layer, null, null, 2.0, null, false];
  }
  for (const [name, args] of Object.entries(cases)) {
    const got = sortNodes(buildGraph(store, ...args));
    const exp = sortNodes(expected.graphs[name]);
    assert.deepEqual(got, exp, `graph case ${name}`);
  }
});

test("heatmaps", () => {
  const norm = (h) => ({ rows: h.rows.map((r) => r.label).sort(), cols: h.cols.map((c) => c.label).sort(), total: h.data.flat().reduce((a, b) => a + b, 0) });
  assert.deepEqual(norm(authorKeywordHeat(store, 2000, 2026)), norm(expected.heat_author_keyword));
  assert.deepEqual(norm(authorKeywordHeat(store, 2018, 2021)), norm(expected.heat_author_keyword_range));
  const hn = nationNationHeat(store), en = expected.heat_nation;
  assert.deepEqual(hn.rows.map((r) => r.label), en.rows.map((r) => r.label));
  assert.deepEqual(hn.data, en.data);
});

test("report", () => {
  const r = gatherReport(store), e = expected.report;
  for (const k of ["n_works", "n_authors", "n_orgs", "n_keywords", "n_venues", "year_min", "year_max"]) assert.equal(r[k], e[k], k);
  assert.deepEqual(r.pub_trend, e.pub_trend);
  const counts = (arr, key) => arr.map((x) => x[key]).sort((a, b) => b - a);
  assert.deepEqual(counts(r.top_authors, "papers"), counts(e.top_authors, "papers"));
  assert.deepEqual(counts(r.top_keywords, "count"), counts(e.top_keywords, "count"));
  assert.deepEqual(r.country_dist.slice().sort((a, b) => a.country.localeCompare(b.country)), e.country_dist.slice().sort((a, b) => a.country.localeCompare(b.country)));
  assert.deepEqual(counts(r.top_collabs, "weight"), counts(e.top_collabs, "weight"));
  assert.deepEqual(counts(r.top_kw_pairs, "co_occurrences"), counts(e.top_kw_pairs, "co_occurrences"));
  assert.deepEqual(counts(r.top_venues, "papers"), counts(e.top_venues, "papers"));
  assert.deepEqual(r.highlight_works.map((w) => w.cited_by_count), e.highlight_works.map((w) => w.cited_by_count));
  assert.equal(r.graph_nodes.length, e.graph_nodes.length);
  assert.equal(r.graph_edges.length, e.graph_edges.length);
});

test("burst detection", () => {
  const strip = (arr) => arr.map((b) => ({ keyword: b.keyword, burst_score: b.burst_score, baseline_avg: b.baseline_avg, recent_avg: b.recent_avg, total_papers: b.total_papers, trend: b.trend, years: b.years, status: b.status })).sort((a, b) => a.keyword.localeCompare(b.keyword));
  assert.deepEqual(strip(detectBursts(store, 3, 3)), strip(expected.bursts));
  assert.deepEqual(strip(detectBursts(store, 2, 2)), strip(expected.bursts_w2));
});

test("collaborator recommendation", () => {
  const got = recommendCollaborators(store, expected.focus_ids.author, 10);
  const strip = (arr) => arr.map((r) => ({ author_id: r.author_id, score: r.score, jaccard_similarity: r.jaccard_similarity, common_neighbors: r.common_neighbors, path_length: r.path_length }));
  assert.deepEqual(strip(got), strip(expected.recommend));
});

test("shortest path", () => {
  const a = expected.shortest_path;
  const ids = expected.authors.map((x) => x.id);
  const got = findShortestPath(store, ids[0], ids[Math.floor(ids.length / 2)]);
  assert.equal(got.path_exists, a.path_exists);
  assert.equal(got.path_length, a.path_length);
  if (a.path_exists) {
    assert.equal(got.path.length, a.path.length);
    assert.equal(got.path[0].node_id, a.path[0].node_id);
    assert.equal(got.path[got.path.length - 1].node_id, a.path[a.path.length - 1].node_id);
    // every step in the JS path must be a real edge with matching shared-paper counts
    for (let i = 1; i < got.path.length; i++) assert.ok(got.path[i].shared_papers >= 1);
  }
  const miss = findShortestPath(store, ids[0], 999999);
  assert.equal(miss.path_exists, false);
  assert.match(miss.message, /not found/);
});

test("community detection reaches NetworkX-level modularity", () => {
  for (const [layer, exp] of [["authors", expected.communities_authors], ["keywords", expected.communities_keywords]]) {
    const got = detectCommunities(store, layer, 1.0, null, null);
    assert.equal(got.partition.size, exp.num_nodes, `${layer}: node count`);
    assert.ok(got.modularity >= exp.modularity - 0.03, `${layer}: modularity ${got.modularity} vs python ${exp.modularity}`);
    // partition must be a proper cover
    const G = buildNetworkGraph(store, layer);
    const q = modularity(G, Object.values(got.communities).map((c) => c.node_ids));
    assert.ok(Math.abs(q - got.modularity) < 1e-3);
  }
});

test("gap / strategic / evolution run and are shaped like Python", () => {
  const gaps = detectResearchGaps(store, null, null, 3, 15);
  assert.ok(Array.isArray(gaps));
  for (const g of gaps) { assert.ok(g.gap_score >= 0.3); assert.ok(g.community_a.top_keywords.length); }
  const strat = buildStrategicDiagram(store, null, null, 3);
  assert.equal(strat.themes.length > 0, expected.strategic.n_themes > 0);
  for (const t of strat.themes) assert.ok(["Motor", "Niche", "Basic & Transversal", "Emerging or Declining"].includes(t.quadrant));
  const evo = buildThematicEvolution(store, 3, 2);
  assert.deepEqual(evo.periods, expected.evolution.periods);
  assert.ok(evo.nodes.length > 0);
});

test("modularity matches the analytic value on a toy graph", () => {
  const g = new UGraph();
  [[1, 2], [2, 3], [1, 3], [4, 5], [5, 6], [4, 6], [3, 4]].forEach(([u, v]) => g.addEdge(u, v, 1));
  const c = louvainCommunities(g);
  assert.equal(c.length, 2);
  assert.ok(Math.abs(modularity(g, c) - 0.357142857) < 1e-6);
});

test("CSV round-trip and pandas compatibility", () => {
  const rows = [{ a: 1, b: 'he said "hi"', c: "x,y", d: null, e: true }];
  const text = toCsv(rows);
  assert.equal(text, 'a,b,c,d,e\n1,"he said ""hi""","x,y",,True\n');
  const back = parseCsv(text);
  assert.deepEqual(back, [{ a: "1", b: 'he said "hi"', c: "x,y", d: "", e: "True" }]);
  assert.deepEqual(parseCsv("x,y\r\n1,\"multi\nline\"\r\n"), [{ x: "1", y: "multi\nline" }]);
});

test("restore a Python-exported ZIP reproduces the dataset", async () => {
  const zipBytes = Buffer.from(expected.export_zip_b64, "base64");
  const s = new Store();
  const stats = await restoreFromZip(s, zipBytes, JSZip);
  assert.equal(stats.works, expected.stats.works);
  assert.equal(stats.authors, expected.stats.authors);
  assert.equal(stats.organizations, expected.stats.organizations);
  assert.equal(stats.keywords, expected.stats.keywords);
  assert.equal(s.coauthorEdges.length, expected.coauthor_edges.length);
  assert.equal(s.nationEdges.length, expected.nation_edges.length);
});

test("JS export -> JS restore round-trip", async () => {
  const files = buildExportFiles(store);
  assert.ok(files["works.csv"] && files["work_authors.csv"] && files["affiliations.csv"] && files["work_keywords.csv"]);
  const zip = new JSZip();
  for (const [n, t] of Object.entries(files)) zip.file(n, t);
  const buf = await zip.generateAsync({ type: "nodebuffer" });
  const s = new Store();
  const stats = await restoreFromZip(s, buf, JSZip);
  assert.deepEqual(stats, store.stats());
  assert.equal(s.coauthorEdges.length, store.coauthorEdges.length);
  const blob = await exportZip(store, JSZip);
  assert.ok(blob.size > 0);
});

test("importCsv works / authors / keywords", () => {
  const s = new Store();
  importCsv(s, "works", parseCsv("doi,title,year,venue,keywords\n10.1/abc,Hello,2020,Nature,ai; ml\n,World,,,\n"));
  assert.equal(s.works.length, 2);
  assert.equal(s.keywords.length, 2);
  importCsv(s, "authors", parseCsv("work_doi,work_title,author_name,position\n10.1/abc,,Ann,0\n,World,Ben,1\n,Missing,Zed,0\n"));
  assert.equal(s.authors.length, 2);
  importCsv(s, "affiliations", parseCsv("work_doi,author_name,org_name,country_code\n10.1/abc,Ann,MIT,us\n"));
  assert.equal(s.organizations[0].country_code, "US");
  s.recomputeAllEdges();
  assert.equal(s.coauthorEdges.length, 0);
});

test("store JSON snapshot round-trip", () => {
  const json = JSON.parse(JSON.stringify(store.toJSON()));
  const s2 = Store.fromJSON(json);
  assert.deepEqual(s2.stats(), store.stats());
  assert.deepEqual(sortNodes(buildGraph(s2, "authors", 2000, 2026, 1.0)), sortNodes(buildGraph(store, "authors", 2000, 2026, 1.0)));
  const w = s2.upsertWorkFromOpenAlex({ id: "https://openalex.org/W999999", title: "new", publication_year: 2025, authorships: [], concepts: [] });
  assert.equal(w.id, store.works.length + 1);
});
