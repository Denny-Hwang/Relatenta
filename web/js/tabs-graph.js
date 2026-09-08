/** Graph tab — port of graph_tab() + _render_focus_picker() + empty state. */
import { app, on } from "./state.js";
import { buildGraph } from "./graph.js";
import { mountNetworkView } from "./network-view.js";
import { el, alertBox, expander, multiSelect, toast } from "./ui.js";
import { t } from "./i18n.js";

const NATION_CHOICES = [
  ["US", "United States"], ["GB", "United Kingdom"], ["DE", "Germany"], ["FR", "France"], ["CN", "China"], ["JP", "Japan"],
  ["KR", "South Korea"], ["CA", "Canada"], ["AU", "Australia"], ["IN", "India"], ["IT", "Italy"], ["ES", "Spain"],
  ["NL", "Netherlands"], ["CH", "Switzerland"], ["SE", "Sweden"], ["BR", "Brazil"], ["RU", "Russia"], ["SG", "Singapore"],
];
export const SUGGESTED_RESEARCHERS = ["Yoshua Bengio", "Yann LeCun", "Fei-Fei Li"];

/** Focus picker options for a layer (port of _render_focus_picker). */
export function focusOptions(store, layer) {
  const byLabel = (a, b) => a.label.localeCompare(b.label);
  if (layer === "authors") return store.authors.map((a) => ({ value: a.id, label: `${a.display_name}  (id ${a.id})` })).sort(byLabel);
  if (layer === "keywords") return store.keywords.map((k) => ({ value: k.id, label: `${k.term_display}  (id ${k.id})` })).sort(byLabel);
  if (layer === "orgs") return store.organizations.map((o) => ({ value: o.id, label: `${o.name} (${o.country_code || "N/A"})  (id ${o.id})` })).sort(byLabel);
  if (layer === "nations") {
    const names = new Map(NATION_CHOICES);
    const codes = new Set(NATION_CHOICES.map((c) => c[0]));
    for (const r of store.allWorkAffiliations()) if (r.country_code) codes.add(r.country_code);
    return [...codes].map((c) => ({ value: c, label: `${names.get(c) || c} (${c})` })).sort(byLabel);
  }
  return [];
}

export function renderEmptyState(container, { onSuggest }) {
  container.replaceChildren(el("div", { class: "empty-state card" },
    el("h3", { text: t("empty.title") }),
    el("p", { html: t("empty.body") }),
    el("div", { class: "chips", style: { justifyContent: "center" } }, ...SUGGESTED_RESEARCHERS.map((name) =>
      el("button", { class: "btn suggest-chip", type: "button", text: name, onClick: () => onSuggest(name) }))),
    el("p", { class: "muted small", text: t("empty.tip") })));
}

export function initGraphTab(panel, { onSuggest }) {
  let currentLayer = "authors";
  let focusPicker = null;
  let focusSelected = [];
  let focusOnly = false;

  const yearRangeDefaults = () => {
    const [mn, mx] = app.store.yearRange();
    return [mn ?? 2000, mx ?? new Date().getFullYear()];
  };

  function render() {
    if (app.view) { app.view.destroy(); app.view = null; }
    panel.replaceChildren();
    if (!app.store.works.length) { renderEmptyState(panel, { onSuggest }); return; }

    const [dMin, dMax] = yearRangeDefaults();
    const layerSel = el("select", { class: "input" }, ...[["authors", "Authors"], ["keywords", "Keywords"], ["orgs", "Organizations"], ["nations", "Nations"]].map(([v, l]) => el("option", { value: v, text: l, selected: v === currentLayer || null })));
    const yearMin = el("input", { class: "input", type: "number", value: dMin, step: 1 });
    const yearMax = el("input", { class: "input", type: "number", value: dMax, step: 1 });
    const edgeMin = el("input", { type: "range", min: 0, max: 10, step: 0.5, value: 1 });
    const edgeVal = el("span", { class: "range-val", text: "1.0" });
    edgeMin.addEventListener("input", () => { edgeVal.textContent = parseFloat(edgeMin.value).toFixed(1); });

    const focusHost = el("div", { class: "field" });
    const modeHost = el("div", { class: "radio-row", hidden: true });
    const modeFull = el("input", { type: "radio", name: "focus-mode", value: "full", checked: !focusOnly || null });
    const modeOnly = el("input", { type: "radio", name: "focus-mode", value: "only", checked: focusOnly || null });
    modeHost.append(el("label", {}, modeFull, " Full Network (highlight)"), el("label", {}, modeOnly, " Focus Only (isolate)"));
    modeFull.addEventListener("change", () => { focusOnly = false; });
    modeOnly.addEventListener("change", () => { focusOnly = true; });

    const buildFocusPicker = () => {
      const opts = focusOptions(app.store, currentLayer);
      focusHost.replaceChildren(el("span", { text: `Focus ${currentLayer} (optional)` }));
      if (!opts.length) { focusHost.append(el("span", { class: "muted small", text: `No ${currentLayer} available yet — ingest data first.` })); focusPicker = null; return; }
      focusPicker = multiSelect(opts, {
        placeholder: `Type a name to filter ${currentLayer}…`, selected: new Set(focusSelected),
        onChange: (sel) => { focusSelected = sel; modeHost.hidden = !sel.length; },
      });
      focusHost.append(focusPicker, el("span", { class: "muted small", text: "Leave empty to render the full network. Pick one or more nodes to focus the view." }));
      modeHost.hidden = !focusSelected.length;
    };
    layerSel.addEventListener("change", () => { currentLayer = layerSel.value; focusSelected = []; buildFocusPicker(); });
    buildFocusPicker();

    // Visualization controls (port of the "Visualization Controls" expander)
    const num = (v, min, max, step = 1) => el("input", { class: "input", type: "number", value: v, min, max, step });
    const nodeMin = num(15, 5, 100), nodeMax = num(40, 5, 100);
    const fontMin = num(10, 8, 24), fontMax = num(16, 8, 24);
    const edgeWMin = num(0.5, 0.1, 10, 0.1), edgeWMax = num(4.0, 0.1, 10, 0.1);
    const physIter = el("input", { type: "range", min: 50, max: 500, step: 10, value: 200 });
    const physVal = el("span", { class: "range-val", text: "200" });
    physIter.addEventListener("input", () => { physVal.textContent = physIter.value; });
    const autoStop = el("input", { type: "checkbox", checked: true });
    const solver = el("select", { class: "input" }, el("option", { value: "barnesHut", text: "Barnes-Hut (default)" }), el("option", { value: "forceAtlas2Based", text: "ForceAtlas2" }));
    const vizControls = expander("Visualization Controls", el("div", { class: "controls" },
      el("label", { class: "field" }, el("span", { text: "Node size range" }), el("div", { class: "row" }, nodeMin, nodeMax)),
      el("label", { class: "field" }, el("span", { text: "Font size range" }), el("div", { class: "row" }, fontMin, fontMax)),
      el("label", { class: "field" }, el("span", { text: "Edge width range" }), el("div", { class: "row" }, edgeWMin, edgeWMax)),
      el("label", { class: "field" }, el("span", { text: "Physics iterations" }), physIter, physVal),
      el("label", { class: "field" }, el("span", { text: "Layout solver" }), solver),
      el("label", { class: "checkbox" }, autoStop, " Auto-stop physics")));

    const buildBtn = el("button", { class: "btn btn-primary", type: "button", text: t("btn.build_graph") });
    const status = el("div");
    const viewHost = el("div", { class: "netview-host" });

    const build = () => {
      const ym = yearMin.value === "" ? null : parseInt(yearMin.value, 10);
      const yx = yearMax.value === "" ? null : parseInt(yearMax.value, 10);
      const focus = focusSelected.length ? focusSelected : null;
      let g;
      try {
        g = buildGraph(app.store, currentLayer, ym, yx, parseFloat(edgeMin.value), focus, focus ? focusOnly : false);
      } catch (e) {
        status.replaceChildren(alertBox(`Error building graph: ${e.message}`, "error"));
        return;
      }
      if (!g.nodes.length) {
        status.replaceChildren(alertBox("No nodes found. Try lowering edge weight or widening the year range.", "warning"));
        if (app.view) { app.view.destroy(); app.view = null; }
        app.builtGraph = null;
        return;
      }
      app.builtGraph = g;
      app.builtGraphSettings = {
        node_size_range: [+nodeMin.value, +nodeMax.value], font_size_range: [+fontMin.value, +fontMax.value],
        edge_width_range: [+edgeWMin.value, +edgeWMax.value], physics_iterations: +physIter.value,
        auto_stop_physics: autoStop.checked, solver: solver.value,
      };
      showGraph(g, app.builtGraphSettings);
    };
    const showGraph = (g, settings) => {
      status.replaceChildren(alertBox(`Graph: <b>${g.nodes.length}</b> nodes, <b>${g.edges.length}</b> edges`, "success"),
        el("p", { class: "muted small", text: t("graph.controls") }));
      if (app.view) app.view.destroy();
      app.view = mountNetworkView(viewHost, g, {
        settings, store: app.store, layer: currentLayer,
        onFocus: (id) => {
          const raw = id.slice(1);
          const key = currentLayer === "nations" ? raw : parseInt(raw, 10);
          if (!focusSelected.includes(key)) focusSelected = [...focusSelected, key];
          buildFocusPicker();
          toast("Added to focus. Rebuilding…", "info", 1500);
          build();
        },
      });
      viewHost.scrollIntoView({ behavior: "smooth", block: "nearest" });
    };
    buildBtn.addEventListener("click", build);

    const banner = (!app.demoDismissed) ? alertBox(t("demo.banner"), "info") : null;
    if (banner) panel.append(banner);
    panel.append(
      el("h2", { text: t("graph.title") }),
      el("div", { class: "controls" },
        el("label", { class: "field" }, el("span", { text: "Layer" }), layerSel),
        el("label", { class: "field" }, el("span", { text: "Year min" }), yearMin),
        el("label", { class: "field" }, el("span", { text: "Year max" }), yearMax),
        el("label", { class: "field" }, el("span", { text: "Edge weight min" }), edgeMin, edgeVal)),
      focusHost, modeHost, vizControls,
      el("div", { class: "row", style: { marginTop: ".75rem" } }, buildBtn),
      status, viewHost);

    // Pre-built graph from demo / ingest: show immediately (as Streamlit does)
    if (app.builtGraph && app.builtGraph.nodes.length) showGraph(app.builtGraph, app.builtGraphSettings || {});
  }

  on("data", () => { currentLayer = "authors"; focusSelected = []; render(); });
  on("lang", render);
  render();
  return { render };
}
