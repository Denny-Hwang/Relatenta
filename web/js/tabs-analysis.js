/** Heatmaps, Report, Insights and How-to tabs. */
import { app, on } from "./state.js";
import { authorKeywordHeat, nationNationHeat } from "./heatmap.js";
import { gatherReport } from "./report.js";
import { buildGraph, colorGraphByCommunity } from "./graph.js";
import {
  detectCommunities, detectBursts, recommendCollaborators, findShortestPath,
  detectResearchGaps, buildStrategicDiagram, buildThematicEvolution,
} from "./insights.js";
import { mountNetworkView } from "./network-view.js";
import { heatmapChart, barChart, hbarChart, strategicDiagram, sankeyChart } from "./charts.js";
import { el, alertBox, metric, dataTable, expander, escapeHtml, fmt, busy, toast } from "./ui.js";
import { renderEmptyState } from "./tabs-graph.js";
import { t } from "./i18n.js";

const yearInputs = (store) => {
  const [mn, mx] = store.yearRange();
  const yearMin = el("input", { class: "input", type: "number", value: mn ?? 2000, step: 1 });
  const yearMax = el("input", { class: "input", type: "number", value: mx ?? new Date().getFullYear(), step: 1 });
  const val = (i) => (i.value === "" ? null : parseInt(i.value, 10));
  return { yearMin, yearMax, values: () => [val(yearMin), val(yearMax)] };
};
const field = (label, ...ctrl) => el("label", { class: "field" }, el("span", { text: label }), ...ctrl);
const rangeField = (label, min, max, step, value) => {
  const input = el("input", { type: "range", min, max, step, value });
  const out = el("span", { class: "range-val", text: String(value) });
  input.addEventListener("input", () => { out.textContent = input.value; });
  return { node: field(label, input, out), value: () => parseFloat(input.value) };
};
const runAsync = async (label, fn) => {
  const b = busy(label);
  try { await new Promise((r) => setTimeout(r, 20)); return await fn(); }
  catch (e) { console.error(e); toast(`Error: ${escapeHtml(e.message)}`, "error"); }
  finally { b.close(); }
};

// ─────────────────────────── Heatmaps ───────────────────────────
export function initHeatmapTab(panel, { onSuggest }) {
  function render() {
    panel.replaceChildren();
    if (!app.store.works.length) { renderEmptyState(panel, { onSuggest }); return; }
    const kind = el("select", { class: "input" }, el("option", { value: "author_keyword", text: "Author × Keyword" }), el("option", { value: "nation_nation", text: "Nation × Nation" }));
    const yr = yearInputs(app.store);
    const btn = el("button", { class: "btn btn-primary", type: "button", text: t("btn.compute_heatmap") });
    const out = el("div");
    btn.addEventListener("click", () => runAsync("Computing heatmap…", async () => {
      const [ym, yx] = yr.values();
      const hm = kind.value === "author_keyword" ? authorKeywordHeat(app.store, ym, yx) : nationNationHeat(app.store);
      if (!hm.data.length) { out.replaceChildren(alertBox("No data available for the selected parameters", "warning")); return; }
      const chart = el("div");
      out.replaceChildren(chart);
      await heatmapChart(chart, hm.data, hm.cols.map((c) => c.label), hm.rows.map((r) => r.label));
    }));
    panel.append(el("h2", { text: "Heatmaps" }),
      el("div", { class: "controls" }, field("Kind", kind), field("Year min", yr.yearMin), field("Year max", yr.yearMax)),
      el("div", { class: "row" }, btn), out);
  }
  on("data", render); on("lang", render); render();
}

// ─────────────────────────── Report ───────────────────────────
export function initReportTab(panel, { onSuggest }) {
  let reportName = "";
  function render() {
    panel.replaceChildren();
    if (!app.store.works.length) { renderEmptyState(panel, { onSuggest }); return; }
    const nameInput = el("input", { class: "input", type: "text", placeholder: "e.g., Geoffrey Hinton", value: reportName });
    nameInput.addEventListener("input", () => { reportName = nameInput.value; });
    const genBtn = el("button", { class: "btn btn-primary", type: "button", text: t("btn.generate_report") });
    const body = el("div");
    genBtn.addEventListener("click", () => runAsync("Analyzing data…", async () => {
      app.reportData = gatherReport(app.store);
      await renderReport(body);
    }));
    panel.append(el("h2", { text: "Analytic Report" }),
      el("div", { class: "controls no-print" }, field("Report name (used in PDF filename)", nameInput)),
      el("div", { class: "row no-print" }, genBtn), body);
    if (app.reportData) renderReport(body);
    else body.append(el("p", { class: "muted", html: `Click <b>${t("btn.generate_report")}</b> to analyze your data.` }));
  }

  async function renderReport(body) {
    const rpt = app.reportData;
    body.replaceChildren();
    const yearLabel = rpt.year_min && rpt.year_max ? `${rpt.year_min} – ${rpt.year_max}` : "";
    body.append(
      el("div", { class: "print-only" }, el("h1", { text: "Relatenta — Analytic Report" }), el("p", { class: "muted", text: `${reportName ? reportName + " · " : ""}Generated ${new Date().toLocaleString()}` })),
      el("h3", { text: "Summary" }),
      el("div", { class: "metrics" }, metric("Papers", rpt.n_works), metric("Authors", rpt.n_authors), metric("Organizations", rpt.n_orgs), metric("Keywords", rpt.n_keywords), metric("Venues", rpt.n_venues)),
      yearLabel ? el("p", { class: "muted small", text: `Publication years: ${yearLabel}` }) : null,
      el("hr", { class: "divider" }));

    const charts = [];
    const section = (title, height) => { const c = el("div"); charts.push(c); return el("div", { class: "card" }, el("h3", { text: title }), c); };
    const pending = [];
    if (rpt.pub_trend.length) {
      const c = el("div");
      body.append(el("div", { class: "card" }, el("h3", { text: "Publication Trend" }), c));
      pending.push(barChart(c, rpt.pub_trend.map((p) => p.year), rpt.pub_trend.map((p) => p.count), { xTitle: "Year", yTitle: "Papers" }));
    }
    const g2 = el("div", { class: "grid-2" });
    if (rpt.top_authors.length) {
      const c = el("div"); g2.append(el("div", { class: "card" }, el("h3", { text: "Top Authors" }), c));
      const top = rpt.top_authors.slice(0, 15);
      pending.push(hbarChart(c, top.map((a) => a.name), top.map((a) => a.papers), { xTitle: "Papers" }));
    }
    if (rpt.top_keywords.length) {
      const c = el("div"); g2.append(el("div", { class: "card" }, el("h3", { text: "Top Research Topics" }), c));
      const top = rpt.top_keywords.slice(0, 15);
      pending.push(hbarChart(c, top.map((k) => k.term), top.map((k) => k.count), { color: "#F5A623", xTitle: "Occurrences" }));
    }
    body.append(g2);
    const g3 = el("div", { class: "grid-2" });
    if (rpt.country_dist.length) {
      const c = el("div"); g3.append(el("div", { class: "card" }, el("h3", { text: "Country Distribution" }), c));
      pending.push(barChart(c, rpt.country_dist.map((x) => x.country), rpt.country_dist.map((x) => x.papers), { color: "#7ED321", xTitle: "Country", yTitle: "Papers" }));
    }
    if (rpt.top_venues.length) {
      const c = el("div"); g3.append(el("div", { class: "card" }, el("h3", { text: "Top Venues" }), c));
      pending.push(hbarChart(c, rpt.top_venues.map((v) => v.venue), rpt.top_venues.map((v) => v.papers), { color: "#BD10E0", xTitle: "Papers" }));
    }
    body.append(g3);
    const g4 = el("div", { class: "grid-2" });
    if (rpt.top_collabs.length) {
      const c = el("div"); g4.append(el("div", { class: "card" }, el("h3", { text: "Strongest Collaborations" }), c));
      const top = rpt.top_collabs.slice(0, 10);
      pending.push(hbarChart(c, top.map((x) => `${x.author_a}  &  ${x.author_b}`), top.map((x) => x.papers), { xTitle: "Co-authored Papers", height: Math.max(300, top.length * 35 + 80) }));
    }
    if (rpt.top_kw_pairs.length) {
      const c = el("div"); g4.append(el("div", { class: "card" }, el("h3", { text: "Topic Co-occurrence" }), c));
      const top = rpt.top_kw_pairs.slice(0, 10);
      pending.push(hbarChart(c, top.map((x) => `${x.keyword_a}  &  ${x.keyword_b}`), top.map((x) => x.co_occurrences), { color: "#F5A623", xTitle: "Co-occurrences", height: Math.max(300, top.length * 35 + 80) }));
    }
    body.append(g4);

    if (rpt.highlight_works.length) {
      body.append(el("div", { class: "card" }, el("h3", { text: "Highlight Papers" }), el("p", { class: "muted small", text: "Top cited papers in your dataset" }),
        ...rpt.highlight_works.slice(0, 10).map((w, i) => el("div", { class: "paper" },
          el("div", { class: "paper-title" }, `${i + 1}. `, w.link ? el("a", { href: w.link, target: "_blank", rel: "noopener", text: w.title }) : w.title, w.year ? ` (${w.year})` : ""),
          el("div", { class: "paper-meta", text: w.authors }),
          el("div", { class: "paper-meta", html: `${w.venue ? `<i>${escapeHtml(w.venue)}</i>  —  ` : ""}${w.cited_by_count ? `<b>${fmt(w.cited_by_count)} citations</b>` : "Citations: N/A"}` })))));
    }
    if (rpt.graph_nodes.length && rpt.graph_edges.length) {
      const host = el("div");
      body.append(el("div", { class: "card" }, el("h3", { text: "Collaboration Network" }), el("p", { class: "muted small", text: "Top co-author connections (strongest collaborations)" }), host));
      const g = {
        nodes: rpt.graph_nodes.map((n) => ({ id: "A" + n.id, label: n.label, type: "author" })),
        edges: rpt.graph_edges.map((e) => ({ source: "A" + e.a, target: "A" + e.b, weight: e.weight })),
      };
      mountNetworkView(host, g, { height: 480, store: app.store, layer: "authors", settings: { physics_iterations: 150 } });
    }
    const pdfBtn = el("button", { class: "btn btn-primary", type: "button", text: t("btn.download_pdf") });
    pdfBtn.addEventListener("click", () => printReport());
    body.append(el("div", { class: "card no-print" }, el("h3", { text: "Download Report" }),
      el("p", { class: "muted small", text: "Opens the browser print dialog — choose “Save as PDF”. Charts and Korean/CJK text render with the browser's own fonts." }),
      pdfBtn));
    await Promise.all(pending);
  }

  function printReport() {
    const safe = reportName.trim().replace(/[^\w\s-]/g, "_").trim().replace(/\s+/g, "_");
    const prevTitle = document.title;
    document.title = safe ? `Relatenta_report_${safe}` : `Relatenta_report_${new Date().toISOString().slice(0, 16).replace(/[-:T]/g, "").slice(0, 13)}`;
    panel.classList.add("printing");
    const restore = () => { panel.classList.remove("printing"); document.title = prevTitle; window.removeEventListener("afterprint", restore); };
    window.addEventListener("afterprint", restore);
    setTimeout(() => window.print(), 100);
  }
  on("data", render); on("lang", render); render();
}

// ─────────────────────────── Insights ───────────────────────────
export function initInsightsTab(panel, { onSuggest }) {
  let analysis = "community";
  let view = null;
  const ANALYSES = [
    ["community", "Community Detection"], ["burst", "Emerging Topics (Burst Detection)"], ["recommend", "Collaborator Recommendation"],
    ["path", "Shortest Path (Networking Path)"], ["gap", "Research Gap Detection"], ["strategic", "Strategic Diagram"], ["evolution", "Thematic Evolution"],
  ];
  const authorOptions = () => app.store.authors.slice().sort((a, b) => a.display_name.localeCompare(b.display_name))
    .map((a) => el("option", { value: a.id, text: `${a.display_name} (ID: ${a.id})` }));

  function render() {
    if (view) { view.destroy(); view = null; }
    panel.replaceChildren();
    if (!app.store.works.length) { renderEmptyState(panel, { onSuggest }); return; }
    const sel = el("select", { class: "input" }, ...ANALYSES.map(([v, l]) => el("option", { value: v, text: l, selected: v === analysis || null })));
    const body = el("div");
    sel.addEventListener("change", () => { analysis = sel.value; renderAnalysis(body); });
    panel.append(el("h2", { text: "Research Insights" }),
      el("p", { class: "muted", text: "Discover hidden patterns, emerging topics, collaboration opportunities, and research gaps." }),
      el("div", { class: "controls" }, field("Select Analysis", sel)), body);
    renderAnalysis(body);
  }

  function renderAnalysis(body) {
    if (view) { view.destroy(); view = null; }
    body.replaceChildren();
    const out = el("div");
    const store = app.store;
    if (analysis === "community") {
      const layer = el("select", { class: "input" }, ...["authors", "keywords", "orgs", "nations"].map((l) => el("option", { value: l, text: l })));
      const res = rangeField("Resolution (higher = more communities)", 0.5, 3.0, 0.1, 1.0);
      const yr = yearInputs(store);
      const btn = el("button", { class: "btn btn-primary", type: "button", text: "Detect Communities" });
      btn.addEventListener("click", () => runAsync("Detecting communities…", async () => {
        const [ym, yx] = yr.values();
        const result = detectCommunities(store, layer.value, res.value(), ym, yx);
        out.replaceChildren();
        if (result.message) { out.append(alertBox(result.message, "warning")); return; }
        if (!result.num_communities) { out.append(alertBox("No communities detected. Try ingesting more data.", "info")); return; }
        out.append(alertBox(`Found <b>${result.num_communities}</b> communities (Modularity: ${result.modularity})`, "success"));
        out.append(dataTable(Object.entries(result.communities).map(([cid, info]) => ({
          Community: +cid, Label: info.label, Size: info.size, Density: info.density, "Members (top 5)": info.nodes.slice(0, 5).join(", "),
        }))));
        const g = buildGraph(store, layer.value, ym, yx);
        if (g.nodes.length) {
          colorGraphByCommunity(g, result.partition, layer.value);
          const host = el("div");
          out.append(host);
          if (view) view.destroy();
          view = mountNetworkView(host, g, { store, layer: layer.value });
        }
      }));
      body.append(el("h3", { text: "Community Detection" }), el("p", { class: "muted small", text: "Identify research communities/clusters within the network using the Louvain algorithm." }),
        el("div", { class: "controls" }, field("Network Layer", layer), res.node, field("Year Min", yr.yearMin), field("Year Max", yr.yearMax)), el("div", { class: "row" }, btn), out);
    } else if (analysis === "burst") {
      const win = rangeField("Detection Window (years)", 2, 5, 1, 3);
      const minP = el("input", { class: "input", type: "number", min: 2, max: 50, value: 3 });
      const btn = el("button", { class: "btn btn-primary", type: "button", text: "Detect Emerging Topics" });
      btn.addEventListener("click", () => runAsync("Analyzing keyword trends…", async () => {
        const results = detectBursts(store, win.value(), +minP.value);
        out.replaceChildren();
        if (!results.length) { out.append(alertBox("Not enough temporal data for burst detection.", "info")); return; }
        const nb = results.filter((r) => r.status === "burst").length, ng = results.filter((r) => r.status === "growing").length;
        out.append(alertBox(`Found <b>${nb}</b> bursting and <b>${ng}</b> growing topics`, "success"));
        const top = results.slice(0, 15);
        const colors = { burst: "#FF4444", growing: "#FFA500", stable: "#4A90E2", declining: "#888888" };
        const chart = el("div");
        out.append(chart);
        const spark = (tr) => { const m = Math.max(...tr, 1); return tr.map((v) => "▁▂▃▅▆▇"[Math.min(Math.floor((v / m) * 5), 5)]).join(" "); };
        out.append(dataTable(results.slice(0, 30).map((r) => ({
          Keyword: r.keyword, Status: r.status.toUpperCase(), "Burst Score": r.burst_score, "Baseline Avg": r.baseline_avg, "Recent Avg": r.recent_avg, "Total Papers": r.total_papers, Trend: spark(r.trend),
        }))));
        await barChart(chart, top.map((r) => r.keyword), top.map((r) => r.burst_score), { title: "Top 15 Keywords by Burst Score", xTitle: "Keyword", yTitle: "Burst Score", height: 450, text: top.map((r) => r.status.toUpperCase()), colors: top.map((r) => colors[r.status] || "#4A90E2") });
      }));
      body.append(el("h3", { text: "Emerging Topics (Burst Detection)" }), el("p", { class: "muted small", text: "Identify keywords experiencing sudden growth — indicating emerging research fronts." }),
        el("div", { class: "controls" }, win.node, field("Min Papers Threshold", minP)), el("div", { class: "row" }, btn), out);
    } else if (analysis === "recommend") {
      if (!store.authors.length) { body.append(alertBox("No authors in database.", "info")); return; }
      const author = el("select", { class: "input" }, ...authorOptions());
      const topN = rangeField("Number of Recommendations", 5, 20, 1, 10);
      const btn = el("button", { class: "btn btn-primary", type: "button", text: "Find Collaborators" });
      btn.addEventListener("click", () => runAsync("Analyzing research interests and network…", async () => {
        const results = recommendCollaborators(store, +author.value, topN.value());
        out.replaceChildren();
        if (!results.length) { out.append(alertBox("No recommendations found. The author may need more published works with keywords.", "info")); return; }
        out.append(alertBox(`Found <b>${results.length}</b> potential collaborators`, "success"));
        results.forEach((r, i) => {
          const content = el("div", {},
            el("div", { class: "metrics" }, metric("Similarity Score", r.score.toFixed(2)), metric("Keyword Overlap (Jaccard)", r.jaccard_similarity.toFixed(2)), metric("Common Neighbors", r.common_neighbors)),
            r.shared_keywords.length ? el("p", { html: `<b>Shared Keywords:</b> ${escapeHtml(r.shared_keywords.join(", "))}` }) : null,
            r.unique_keywords.length ? el("p", { html: `<b>Their Unique Expertise:</b> ${escapeHtml(r.unique_keywords.join(", "))}` }) : null,
            r.common_neighbor_names.length ? el("p", { html: `<b>Common Co-authors:</b> ${escapeHtml(r.common_neighbor_names.join(", "))}` }) : null,
            el("p", { html: `<b>Network Distance:</b> ${r.path_length > 0 ? `${r.path_length} steps` : "Not connected"}` }));
          out.append(expander(`#${i + 1} — ${r.author_name} (Score: ${r.score})`, content, i === 0));
        });
      }));
      body.append(el("h3", { text: "Collaborator Recommendation" }), el("p", { class: "muted small", text: "Find potential collaborators based on keyword overlap and network proximity." }),
        el("div", { class: "controls" }, field("Select Target Author", author), topN.node), el("div", { class: "row" }, btn), out);
    } else if (analysis === "path") {
      if (store.authors.length < 2) { body.append(alertBox("Need at least 2 authors in database.", "info")); return; }
      const src = el("select", { class: "input" }, ...authorOptions());
      const tgt = el("select", { class: "input" }, ...authorOptions());
      tgt.selectedIndex = Math.min(1, tgt.options.length - 1);
      const btn = el("button", { class: "btn btn-primary", type: "button", text: "Find Path" });
      btn.addEventListener("click", () => runAsync("Searching collaboration network…", async () => {
        out.replaceChildren();
        if (src.value === tgt.value) { out.append(alertBox("Please select two different authors.", "warning")); return; }
        const result = findShortestPath(store, +src.value, +tgt.value);
        if (!result.path_exists) { out.append(alertBox(result.message || "No path found.", "warning")); return; }
        out.append(alertBox(`Path found! <b>${result.path_length}</b> steps`, "success"));
        const viz = el("div", { class: "path-viz" });
        result.path.forEach((p, i) => {
          if (i > 0) viz.append(el("span", { class: "path-arrow", text: `—(${p.shared_papers ?? "?"} papers)→` }));
          viz.append(el("span", { class: "path-node", text: p.name }));
        });
        out.append(viz);
        out.append(dataTable(result.path.map((p, i) => ({ Step: i, Author: p.name, "Shared Papers": i > 0 ? p.shared_papers ?? "-" : "", "Connection Weight": i > 0 ? p.connection_weight ?? "-" : "" }))));
        if (result.alternative_paths && result.alternative_paths.length) {
          out.append(el("p", { html: `<b>${result.alternative_paths.length} alternative path(s) found</b>` }));
          result.alternative_paths.forEach((alt, j) => out.append(el("p", { class: "muted small", text: `Alt ${j + 1}: ${alt.map((p) => p.name).join(" -> ")}` })));
        }
        // Show the path on the network
        const g = buildGraph(store, "authors", null, null, 1.0, result.path.map((p) => p.node_id), true);
        if (g.nodes.length) {
          const onPath = new Set(result.path.map((p) => "A" + p.node_id));
          for (const n of g.nodes) n.type = onPath.has(n.id) ? "focus_author" : "author";
          const host = el("div");
          out.append(el("h4", { text: "Path in the co-author network" }), host);
          if (view) view.destroy();
          view = mountNetworkView(host, g, { store, layer: "authors", height: 520 });
        }
      }));
      body.append(el("h3", { text: "Shortest Path Analysis" }), el("p", { class: "muted small", text: "Find the shortest collaboration path between two researchers." }),
        el("div", { class: "controls" }, field("Source Author", src), field("Target Author", tgt)), el("div", { class: "row" }, btn), out);
    } else if (analysis === "gap") {
      const minKw = el("input", { class: "input", type: "number", min: 2, max: 20, value: 3 });
      const topN = rangeField("Number of Gaps", 5, 30, 1, 15);
      const yr = yearInputs(store);
      const btn = el("button", { class: "btn btn-primary", type: "button", text: "Detect Research Gaps" });
      btn.addEventListener("click", () => runAsync("Analyzing keyword network structure…", async () => {
        const [ym, yx] = yr.values();
        const results = detectResearchGaps(store, ym, yx, +minKw.value, topN.value());
        out.replaceChildren();
        if (!results.length) { out.append(alertBox("Not enough keyword diversity for gap detection. Try ingesting more data.", "info")); return; }
        out.append(alertBox(`Found <b>${results.length}</b> research gaps`, "success"));
        results.forEach((gap, i) => {
          const ca = gap.community_a, cb = gap.community_b;
          const content = el("div", {},
            el("div", { class: "metrics" }, metric("Gap Score", gap.gap_score), metric("Inter-community Edges", gap.inter_edges), metric("Rank Score", gap.rank_score)),
            el("p", { html: `<b>Cluster A (${ca.size} keywords):</b> ${escapeHtml(ca.top_keywords.join(", "))}` }),
            el("p", { html: `<b>Cluster B (${cb.size} keywords):</b> ${escapeHtml(cb.top_keywords.join(", "))}` }),
            gap.potential_bridges.length ? el("p", { html: `<b>Weak Bridge Keywords:</b> ${escapeHtml(gap.potential_bridges.join(", "))}` }) : null,
            alertBox(`<b>Opportunity:</b> ${escapeHtml(gap.suggestion)}`, "info"));
          out.append(expander(`Gap #${i + 1} — ${ca.top_keywords.slice(0, 2).join(" / ")} vs ${cb.top_keywords.slice(0, 2).join(" / ")} (Score: ${gap.gap_score})`, content, i === 0));
        });
      }));
      body.append(el("h3", { text: "Research Gap Detection" }), el("p", { class: "muted small", text: "Find structural holes in the keyword network — under-explored research areas between active clusters." }),
        el("div", { class: "controls" }, field("Min Papers per Keyword", minKw), topN.node, field("Year Min", yr.yearMin), field("Year Max", yr.yearMax)), el("div", { class: "row" }, btn), out);
    } else if (analysis === "strategic") {
      const minKw = el("input", { class: "input", type: "number", min: 2, max: 20, value: 3 });
      const yr = yearInputs(store);
      const btn = el("button", { class: "btn btn-primary", type: "button", text: "Build Strategic Diagram" });
      btn.addEventListener("click", () => runAsync("Computing centrality and density…", async () => {
        const [ym, yx] = yr.values();
        const result = buildStrategicDiagram(store, ym, yx, +minKw.value);
        out.replaceChildren();
        if (result.message) { out.append(alertBox(result.message, "warning")); return; }
        if (!result.themes.length) { out.append(alertBox("Not enough data for strategic diagram.", "info")); return; }
        const chart = el("div");
        out.append(chart, dataTable(result.themes.map((th) => ({
          Theme: th.label, Quadrant: th.quadrant, Centrality: Math.round(th.centrality_norm * 100) / 100, Density: Math.round(th.density_norm * 100) / 100,
          Keywords: th.size, Papers: th.total_papers, "Top Keywords": th.top_keywords.slice(0, 5).join(", "),
        }))));
        await strategicDiagram(chart, result.themes);
      }));
      body.append(el("h3", { text: "Strategic Diagram" }), el("p", { class: "muted small", text: "Callon's centrality-density map classifying research themes as Motor / Niche / Emerging / Basic." }),
        el("div", { class: "controls" }, field("Min Papers per Keyword", minKw), field("Year Min", yr.yearMin), field("Year Max", yr.yearMax)), el("div", { class: "row" }, btn), out);
    } else if (analysis === "evolution") {
      const nPeriods = rangeField("Number of Time Periods", 2, 5, 1, 3);
      const minKw = el("input", { class: "input", type: "number", min: 1, max: 10, value: 2 });
      const btn = el("button", { class: "btn btn-primary", type: "button", text: "Build Thematic Evolution" });
      btn.addEventListener("click", () => runAsync("Analyzing temporal keyword clusters…", async () => {
        const result = buildThematicEvolution(store, nPeriods.value(), +minKw.value);
        out.replaceChildren();
        if (result.message) { out.append(alertBox(result.message, "warning")); return; }
        if (!result.flows.length) { out.append(alertBox("Not enough temporal data for thematic evolution analysis.", "info")); return; }
        const chart = el("div");
        out.append(chart);
        if (result.events.length) {
          const icons = { emergence: "🌱", disappearance: "💨", merge: "🔀", split: "🔱" };
          out.append(el("h4", { text: "Evolution Events" }), ...result.events.map((evt) => el("div", { class: "event", html: `${icons[evt.type] || "📌"} <b>${evt.type[0].toUpperCase() + evt.type.slice(1)}</b> (${escapeHtml(evt.period)}): ${escapeHtml(evt.description)}` })));
        }
        out.append(el("h4", { text: "Period Details" }), ...result.nodes.map((n) => el("p", { class: "muted small", html: `<b>[${escapeHtml(result.periods[n.period].label)}]</b> ${escapeHtml(n.label)} — ${n.size} papers, keywords: ${escapeHtml((n.keywords || []).join(", "))}` })));
        await sankeyChart(chart, result);
      }));
      body.append(el("h3", { text: "Thematic Evolution" }), el("p", { class: "muted small", text: "Visualize how research themes evolve, merge, split, or disappear over time." }),
        el("div", { class: "controls" }, nPeriods.node, field("Min Papers per Keyword", minKw)), el("div", { class: "row" }, btn), out);
    }
  }
  on("data", render); on("lang", render); render();
}

// ─────────────────────────── How to use ───────────────────────────
export function initHowToTab(panel) {
  panel.classList.add("howto");
  panel.innerHTML = `
    <h2>How to Use</h2>
    <p>Welcome to <b>Relatenta</b> — a research relationship visualization service. This version runs entirely in your browser: the only network traffic is to the public OpenAlex API.</p>
    <details class="expander" open><summary>Quick Start</summary><div>
      <ol>
        <li><b>Search for a researcher</b> in the left sidebar (e.g., "Geoffrey Hinton") or paste an ORCID.</li>
        <li><b>Review the search results</b> — check institution, H-index, and topics to pick the right person.</li>
        <li><b>Select one or more authors</b> and click "Ingest Selected".</li>
        <li><b>Go to the Graph tab</b> — pick a layer and click "Build Graph".</li>
      </ol>
      <p class="muted small">Your dataset is saved in this browser (IndexedDB) and survives refreshes. Use "Export CSV" to share it or load it into the Streamlit app.</p>
    </div></details>
    <details class="expander"><summary>Graph Layers</summary><div>
      <table><thead><tr><th>Layer</th><th>Nodes</th><th>Edges</th><th>Use Case</th></tr></thead><tbody>
        <tr><td><b>Authors</b></td><td>Researchers</td><td>Co-authored papers</td><td>Collaboration network</td></tr>
        <tr><td><b>Keywords</b></td><td>Topics</td><td>Papers with both topics</td><td>Research landscape</td></tr>
        <tr><td><b>Organizations</b></td><td>Institutions</td><td>Joint publications</td><td>Partnership analysis</td></tr>
        <tr><td><b>Nations</b></td><td>Countries</td><td>International co-authorships</td><td>Global patterns</td></tr>
      </tbody></table>
    </div></details>
    <details class="expander"><summary>Graph Controls</summary><div>
      <ul>
        <li>Drag to pan the view, scroll to zoom, drag a node to move it.</li>
        <li><b>Hover</b> a node or edge for details; <b>click</b> a node to highlight its neighbours and open the inspector (neighbours, papers, "Focus on this node").</li>
        <li><b>Double-click</b> a node to zoom to it. Use the <b>Find node</b> box to jump by name.</li>
        <li><kbd>Space</kbd> toggles the physics simulation, <kbd>F</kbd> fits the graph, <kbd>Esc</kbd> clears the selection.</li>
        <li>Toolbar: freeze/resume physics, fit, toggle labels, download PNG, fullscreen.</li>
        <li>Use <b>Focus Mode</b> to highlight or isolate specific nodes; <b>Visualization Controls</b> tune sizes, edge widths, physics and the layout solver.</li>
      </ul>
    </div></details>
    <details class="expander"><summary>Insights</summary><div>
      <ul>
        <li><b>Community Detection</b> — Louvain clustering, colour-coded on the interactive graph.</li>
        <li><b>Emerging Topics</b> — burst detection on keyword usage over time.</li>
        <li><b>Collaborator Recommendation</b> — keyword overlap + network proximity.</li>
        <li><b>Shortest Path</b> — networking path between two researchers, drawn on the graph.</li>
        <li><b>Research Gap Detection</b>, <b>Strategic Diagram</b>, <b>Thematic Evolution</b> — structural analyses of the keyword network.</li>
      </ul>
    </div></details>
    <details class="expander"><summary>Data Persistence &amp; Compatibility</summary><div>
      <p>Data lives in your browser only. <b>Export CSV</b> downloads a ZIP with all tables; <b>Restore from Export</b> loads one back. The ZIP format is identical to the Streamlit app's, so files can be exchanged in both directions.</p>
      <p>Not available in the static version: Google Scholar URL lookup (needs a server) and shared Postgres storage.</p>
    </div></details>`;
}
