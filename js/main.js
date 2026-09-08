/**
 * App bootstrap: sidebar (search / ingest / import / export / restore),
 * tab routing, language switching and the demo auto-load.
 * Port of sidebar_data() and main() in streamlit_app.py.
 */
import { app, on, emit, dataChanged, loadPersisted, clearAll, setDemoDismissed } from "./state.js";
import { Store } from "./store.js";
import * as oa from "./openalex.js";
import { buildGraph } from "./graph.js";
import { exportZip, restoreFromZip, importCsv } from "./exporter.js";
import { parseCsv } from "./csv.js";
import { el, $, $$, toast, alertBox, confirmDialog, busy, downloadBlob, escapeHtml, fmt, expander } from "./ui.js";
import { t, getLanguage, setLanguage, applyTranslations } from "./i18n.js";
import { initGraphTab } from "./tabs-graph.js";
import { initHeatmapTab, initReportTab, initInsightsTab, initHowToTab } from "./tabs-analysis.js";

const JSZip = window.JSZip;

// ───────────────────────── tabs ─────────────────────────
function activateTab(name) {
  $$(".tab").forEach((b) => { const on_ = b.dataset.tab === name; b.classList.toggle("active", on_); b.setAttribute("aria-selected", String(on_)); });
  $$(".tab-panel").forEach((p) => { p.hidden = p.id !== `tab-${name}`; });
  try { history.replaceState(null, "", `#${name}`); } catch (e) { /* ignore */ }
  // vis-network needs a resize once its container becomes visible
  if (name === "graph" && app.view) { app.view.network.redraw(); setTimeout(() => app.view && app.view.fit(), 50); }
  window.dispatchEvent(new Event("resize"));
}

// ───────────────────────── sidebar ─────────────────────────
let sidebarSearchQuery = "";
let ingestMaxWorks = 200;

function renderSidebar() {
  const host = $("#sidebar-content");
  host.replaceChildren();
  const stats = app.store.stats();
  const isDemo = !app.demoDismissed && stats.works > 0;

  // --- Database summary ---
  const db = el("section", { class: "side-section" }, el("h3", { text: t("sidebar.database") }));
  if (stats.works > 0) {
    if (isDemo) db.append(el("p", { class: "muted small", text: "Example: Geoffrey Hinton" }));
    else db.append(alertBox(`<b>${t("warn.saved_title")}</b><br>${t("warn.saved_body")}`, "info"));
    db.append(el("div", { class: "stat-row" },
      el("span", {}, "Papers ", el("b", { text: fmt(stats.works) })), el("span", {}, "Authors ", el("b", { text: fmt(stats.authors) })),
      el("span", {}, "Orgs ", el("b", { text: fmt(stats.organizations) })), el("span", {}, "Keywords ", el("b", { text: fmt(stats.keywords) }))));
    const exportBtn = el("button", { class: "btn", type: "button", text: t("btn.export_csv") });
    exportBtn.addEventListener("click", async () => {
      try {
        const blob = await exportZip(app.store, JSZip);
        downloadBlob(blob, `relatenta_export_${new Date().toISOString().slice(0, 10).replace(/-/g, "")}.zip`);
      } catch (e) { toast(`Export error: ${escapeHtml(e.message)}`, "error"); }
    });
    const clearBtn = el("button", { class: "btn", type: "button", text: isDemo ? t("btn.start_fresh") : t("btn.clear_all") });
    clearBtn.addEventListener("click", async () => {
      const ok = await confirmDialog(isDemo ? t("confirm.clear_demo") : t("confirm.clear"), { okText: "Confirm" });
      if (!ok) return;
      await clearAll();
      setDemoDismissed(true);
      renderSidebar();
      toast("All data cleared.", "success");
    });
    db.append(el("div", { class: "row", style: { marginTop: ".5rem" } }, exportBtn, clearBtn));
  } else {
    db.append(el("p", { class: "muted small", text: "No data yet. Search and ingest authors below." }));
  }
  host.append(db);

  // --- OpenAlex search ---
  const search = el("section", { class: "side-section" }, el("h3", { text: t("sidebar.search") }));
  const query = el("input", { class: "input", type: "search", placeholder: t("search.placeholder"), value: sidebarSearchQuery, "aria-label": t("search.label") });
  query.addEventListener("input", () => { sidebarSearchQuery = query.value; });
  const searchBtn = el("button", { class: "btn btn-primary", type: "button", text: t("btn.search") });
  const results = el("div", { class: "stack", style: { marginTop: ".5rem" } });
  const doSearch = () => runSearch(query.value, results);
  searchBtn.addEventListener("click", doSearch);
  query.addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); doSearch(); } });
  search.append(el("label", { class: "field" }, el("span", { text: t("search.label") }), query), el("div", { class: "row", style: { marginTop: ".5rem" } }, searchBtn), results);
  host.append(search);
  if (app.searchHits.length) renderSearchHits(results);

  // --- CSV import ---
  const csv = el("section", { class: "side-section" }, el("h3", { text: t("sidebar.csv_import") }));
  const kind = el("select", { class: "input" }, ...["works", "authors", "affiliations", "keywords"].map((k) => el("option", { value: k, text: k })));
  const csvFile = el("input", { class: "input", type: "file", accept: ".csv,text/csv" });
  const csvBtn = el("button", { class: "btn", type: "button", text: t("btn.import_csv"), disabled: true });
  csvFile.addEventListener("change", () => { csvBtn.disabled = !csvFile.files.length; });
  csvBtn.addEventListener("click", async () => {
    const file = csvFile.files[0];
    if (!file) return;
    const b = busy("Importing CSV…");
    try {
      if (!app.demoDismissed) { app.store = new Store(); }
      const rows = parseCsv(await file.text());
      importCsv(app.store, kind.value, rows);
      app.store.recomputeAllEdges();
      setDemoDismissed(true);
      app.searchHits = [];
      await dataChanged();
      toast(`Imported ${rows.length} rows`, "success");
    } catch (e) { toast(`Import failed: ${escapeHtml(e.message)}`, "error"); }
    finally { b.close(); }
  });
  csv.append(el("label", { class: "field" }, el("span", { text: "Data Type" }), kind), el("label", { class: "field", style: { marginTop: ".4rem" } }, el("span", { text: "Upload CSV" }), csvFile), el("div", { class: "row", style: { marginTop: ".4rem" } }, csvBtn));
  host.append(csv);

  // --- ZIP restore ---
  const restore = el("section", { class: "side-section" }, el("h3", { text: t("sidebar.restore") }), el("p", { class: "muted small", text: "Upload a previously exported ZIP to restore data" }));
  const zipFile = el("input", { class: "input", type: "file", accept: ".zip,application/zip" });
  const zipBtn = el("button", { class: "btn", type: "button", text: t("btn.restore"), disabled: true });
  zipFile.addEventListener("change", () => { zipBtn.disabled = !zipFile.files.length; });
  zipBtn.addEventListener("click", async () => {
    const file = zipFile.files[0];
    if (!file) return;
    const b = busy("Restoring data…");
    try {
      const s = new Store();
      const st = await restoreFromZip(s, await file.arrayBuffer(), JSZip);
      app.store = s;
      setDemoDismissed(true);
      app.searchHits = [];
      await dataChanged();
      toast(`Data restored: ${st.works} papers, ${st.authors} authors`, "success");
    } catch (e) { toast(`Restore failed: ${escapeHtml(e.message)}`, "error"); }
    finally { b.close(); }
  });
  restore.append(zipFile, el("div", { class: "row", style: { marginTop: ".4rem" } }, zipBtn));
  host.append(restore);

  // --- settings ---
  const mail = el("input", { class: "input", type: "email", placeholder: "you@example.com", value: oa.getMailto() });
  mail.addEventListener("change", () => { oa.setMailto(mail.value); toast("Saved. OpenAlex requests now use the polite pool.", "success", 2500); });
  host.append(el("section", { class: "side-section" }, expander("Settings", el("label", { class: "field" }, el("span", { text: t("settings.mailto") }), mail, el("span", { class: "muted small", text: "Stored locally; sent to OpenAlex as the mailto parameter for faster, higher-quota access." })))));
}

async function runSearch(q, resultsHost) {
  q = (q || "").trim();
  if (!q) return;
  resultsHost.replaceChildren(el("p", { class: "muted small" }, el("span", { class: "spinner", style: { display: "inline-block", width: "14px", height: "14px", verticalAlign: "middle", marginRight: ".4rem" } }), "Searching OpenAlex…"));
  try {
    const type = oa.detectQueryType(q);
    let hits = [], note = null;
    if (type === "google_scholar") {
      resultsHost.replaceChildren(alertBox("Google Scholar URLs cannot be resolved in the browser version (Scholar blocks cross-origin requests). Please search by name or ORCID instead.", "warning"));
      return;
    }
    if (type === "orcid") {
      const r = await oa.searchAuthorByOrcid(q);
      hits = r.results;
      if (!hits.length) note = alertBox("No author found for this ORCID in OpenAlex or ORCID.org.", "warning");
      else if (r.method === "orcid_name_fallback") note = alertBox("This ORCID is not indexed in OpenAlex. Showing name-based results from ORCID.org — please verify the correct author.", "info");
    } else {
      hits = await oa.searchAuthorsByName(q);
      if (!hits.length) note = alertBox("No authors found. Try a different spelling.", "warning");
    }
    app.searchHits = hits;
    renderSearchHits(resultsHost, note);
  } catch (e) {
    console.error(e);
    resultsHost.replaceChildren(alertBox(`Search failed: ${escapeHtml(e.message)}. ${navigator.onLine ? "" : "You appear to be offline."}`, "error"));
  }
}

function renderSearchHits(host, note = null) {
  host.replaceChildren();
  if (note) host.append(note);
  if (!app.searchHits.length) return;
  const selected = new Set();
  host.append(el("h4", { text: "Search Results" }), el("p", { class: "muted small", text: "Tick the correct person(s), then ingest." }));
  const ingestBtn = el("button", { class: "btn btn-primary btn-block", type: "button", text: t("btn.ingest_selected"), disabled: true });
  app.searchHits.forEach((hit, idx) => {
    const sid = hit.id.startsWith("http") ? hit.id.split("/").pop() : hit.id;
    const cb = el("input", { type: "checkbox" });
    cb.addEventListener("change", () => { if (cb.checked) selected.add(sid); else selected.delete(sid); ingestBtn.disabled = !selected.size; });
    const topics = (hit.top_concepts || []).map((c) => `${c.name} (${Math.round((c.score || 0) * 100)}%)`).join(", ");
    const details = el("div", { hidden: idx >= 3 },
      el("div", { class: "hit-meta" },
        el("span", { html: `<b>Papers:</b> ${fmt(hit.works_count)}` }), el("span", { html: `<b>Citations:</b> ${fmt(hit.cited_by_count)}` }),
        el("span", { html: `<b>H-index:</b> ${hit.h_index ?? "N/A"}` }), hit.orcid ? el("span", { html: `<b>ORCID:</b> ${escapeHtml(hit.orcid.replace("https://orcid.org/", ""))}` }) : null),
      el("div", { class: "small", html: `<b>Institution:</b> ${escapeHtml(hit.last_known_institution || "N/A")}${hit.institution_country ? ` (${escapeHtml(hit.institution_country)})` : ""}` }),
      topics ? el("div", { class: "hit-topics small", html: `<b>Research Topics:</b> ${escapeHtml(topics)}` }) : null,
      el("div", { class: "small muted", html: `ID: <code>${escapeHtml(sid)}</code>` }));
    const name = el("span", { class: "hit-name", text: hit.display_name || "Unknown" });
    const toggle = el("button", { class: "btn btn-sm", type: "button", text: idx >= 3 ? "▸" : "▾", "aria-label": "Toggle details" });
    toggle.addEventListener("click", () => { details.hidden = !details.hidden; toggle.textContent = details.hidden ? "▸" : "▾"; });
    host.append(el("div", { class: "hit" }, el("label", { class: "hit-head" }, cb, el("span", { class: "grow" }, name, el("span", { class: "muted small", text: ` · ${escapeHtml(hit.last_known_institution || "")} · ${fmt(hit.works_count)} papers` })), toggle), details));
  });
  const max = el("input", { type: "range", min: 50, max: 600, step: 50, value: ingestMaxWorks });
  const maxVal = el("span", { class: "range-val", text: String(ingestMaxWorks) });
  max.addEventListener("input", () => { maxVal.textContent = max.value; ingestMaxWorks = +max.value; });
  host.append(el("label", { class: "field", style: { marginTop: ".5rem" } }, el("span", { text: t("ingest.max_works") }), max, maxVal), ingestBtn);
  ingestBtn.addEventListener("click", () => ingestAuthors([...selected], ingestMaxWorks));
}

async function ingestAuthors(authorIds, maxWorks) {
  const b = busy(t("ingest.progress"));
  try {
    if (!app.demoDismissed) app.store = new Store();
    let total = 0;
    const pages = Math.max(1, Math.floor(maxWorks / 200));
    for (let i = 0; i < authorIds.length; i++) {
      const id = authorIds[i];
      b.update(`${t("ingest.progress")} (${i + 1}/${authorIds.length})`, null);
      const works = await oa.listAuthorWorks(id, 200, pages, (n, count) => b.update(`${t("ingest.progress")} ${n}${count ? " / " + Math.min(count, maxWorks) : ""} works (${i + 1}/${authorIds.length})`, count ? Math.min(1, n / Math.min(count, maxWorks)) : null));
      for (const w of works) { app.store.upsertWorkFromOpenAlex(w); total++; }
    }
    b.update("Computing collaboration edges…", null);
    await new Promise((r) => setTimeout(r, 10));
    app.store.recomputeAllEdges();
    setDemoDismissed(true);
    app.searchHits = [];
    await dataChanged();
    // Pre-build the co-author graph like the demo does, so the Graph tab shows something immediately
    const [mn, mx] = app.store.yearRange();
    app.builtGraph = buildGraph(app.store, "authors", mn, mx, 1.0, null, false);
    emit("data", app.store);
    activateTab("graph");
    toast(`Ingested ${total} works`, "success");
  } catch (e) {
    console.error(e);
    toast(`Ingest failed: ${escapeHtml(e.message)}`, "error", 8000);
  } finally { b.close(); }
}

// ───────────────────────── demo ─────────────────────────
async function loadDemoData() {
  try {
    const hits = await oa.searchAuthorsByName("Geoffrey Hinton", 1);
    if (!hits.length) return false;
    const works = await oa.listAuthorWorks(hits[0].id, 200, 1);
    if (!works.length) return false;
    const s = new Store();
    for (const w of works) s.upsertWorkFromOpenAlex(w);
    s.recomputeAllEdges();
    app.store = s;
    const [mn, mx] = s.yearRange();
    await dataChanged();
    app.builtGraph = buildGraph(s, "authors", mn ?? 2000, mx ?? 2026, 1.0, null, false);
    emit("data", s);
    return true;
  } catch (e) {
    console.warn("demo load failed", e);
    return false;
  }
}

// ───────────────────────── bootstrap ─────────────────────────
async function main() {
  // Language
  const langSel = $("#lang-select");
  langSel.value = getLanguage();
  document.documentElement.lang = getLanguage();
  applyTranslations();
  langSel.addEventListener("change", () => { setLanguage(langSel.value); document.documentElement.lang = langSel.value; applyTranslations(); renderSidebar(); emit("lang"); });

  // Sidebar toggle (mobile + desktop collapse)
  const sidebar = $("#sidebar"), backdrop = $("#sidebar-backdrop"), toggle = $("#sidebar-toggle");
  const mobile = () => window.matchMedia("(max-width: 900px)").matches;
  const setSidebar = (open) => { sidebar.classList.toggle("collapsed", !open); toggle.setAttribute("aria-expanded", String(open)); backdrop.hidden = !(open && mobile()); };
  toggle.addEventListener("click", () => setSidebar(sidebar.classList.contains("collapsed")));
  backdrop.addEventListener("click", () => setSidebar(false));
  setSidebar(!mobile());

  // Tabs
  $$(".tab").forEach((b) => b.addEventListener("click", () => activateTab(b.dataset.tab)));
  const onSuggest = (name) => { sidebarSearchQuery = name; renderSidebar(); setSidebar(true); const input = $("#sidebar-content input[type=search]"); input.value = name; runSearch(name, input.closest("section").querySelector(".stack")); };
  initGraphTab($("#tab-graph"), { onSuggest });
  initHeatmapTab($("#tab-heatmaps"), { onSuggest });
  initReportTab($("#tab-report"), { onSuggest });
  initInsightsTab($("#tab-insights"), { onSuggest });
  initHowToTab($("#tab-howto"));
  on("data", renderSidebar);

  // Restore persisted data, else auto-load the demo (as the Streamlit app does)
  const restored = await loadPersisted();
  if (restored) {
    const [mn, mx] = app.store.yearRange();
    app.builtGraph = buildGraph(app.store, "authors", mn, mx, 1.0, null, false);
    emit("data", app.store);
  } else if (!app.demoDismissed) {
    const b = busy(t("demo.loading"));
    const ok = await loadDemoData();
    b.close();
    if (!ok) { setDemoDismissed(true); toast(t("demo.failed"), "warning", 8000); emit("data", app.store); }
  } else {
    emit("data", app.store);
  }
  const hash = (location.hash || "").slice(1);
  if (["graph", "heatmaps", "report", "insights", "howto"].includes(hash)) activateTab(hash);
  window.__relatenta = app; // handy for debugging / tests
}

main().catch((e) => { console.error(e); toast(`Startup error: ${escapeHtml(e.message)}`, "error", 0); });
