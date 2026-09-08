/**
 * Interactive network view — the centrepiece of the site.
 *
 * Replaces PyVis (which was only a thin wrapper around vis-network) with a
 * direct vis-network integration so the graph lives in the page instead of an
 * iframe. Same physics (Barnes-Hut), colours and sizing rules as the Streamlit
 * app, plus the interactions a static host can afford natively:
 *
 *   - hover tooltip with degree / weight, neighbour highlighting on click
 *   - inspector panel: selected node details, neighbours sorted by weight,
 *     papers for author nodes, "focus" shortcuts
 *   - find-and-zoom search, fit, physics toggle, freeze after stabilisation
 *   - stabilisation progress bar, large-graph performance mode
 *   - legend, fullscreen, PNG export, keyboard shortcuts (SPACE / F / ESC)
 */
import { el, escapeHtml, toast } from "./ui.js";

export const COMMUNITY_PALETTE = [
  { background: "#FF6B6B", border: "#CC5555" }, { background: "#4ECDC4", border: "#3AA89E" },
  { background: "#45B7D1", border: "#2D8FA6" }, { background: "#96CEB4", border: "#6DA88E" },
  { background: "#FFEAA7", border: "#D4C07A" }, { background: "#DDA0DD", border: "#B27DB2" },
  { background: "#98D8C8", border: "#6FB3A3" }, { background: "#F7DC6F", border: "#C8B24A" },
  { background: "#BB8FCE", border: "#9568A5" }, { background: "#85C1E9", border: "#5A9ABD" },
  { background: "#F1948A", border: "#C36C64" }, { background: "#82E0AA", border: "#5AB882" },
  { background: "#F8C471", border: "#CA9B4D" }, { background: "#AED6F1", border: "#82ADC6" },
  { background: "#D7BDE2", border: "#AD95B8" },
];

export const TYPE_COLORS = {
  author: { background: "#4A90E2", border: "#2E5C8A" },
  focus_author: { background: "#FF6B6B", border: "#CC5555" },
  keyword: { background: "#F5A623", border: "#C17F00" },
  focus_keyword: { background: "#FF6B6B", border: "#CC5555" },
  org: { background: "#7ED321", border: "#5A9E00" },
  focus_org: { background: "#FF6B6B", border: "#CC5555" },
  nation: { background: "#BD10E0", border: "#8B0AA8" },
  focus_nation: { background: "#FF6B6B", border: "#CC5555" },
};
const TYPE_LABELS = { author: "Author", keyword: "Keyword", org: "Organization", nation: "Nation" };

export function colorFor(type) {
  if (type && type.startsWith("community_")) return COMMUNITY_PALETTE[parseInt(type.slice(10), 10) % COMMUNITY_PALETTE.length];
  return TYPE_COLORS[type] || { background: "#9013FE", border: "#6609AC" };
}

const DEFAULT_SETTINGS = {
  node_size_range: [15, 40],
  font_size_range: [10, 16],
  edge_width_range: [0.5, 4.0],
  physics_iterations: 200,
  auto_stop_physics: true,
  solver: "barnesHut",
};

const LARGE_GRAPH = 600; // nodes — beyond this we trade eye-candy for frame rate

/**
 * Mount an interactive graph into `container`.
 * @param {HTMLElement} container
 * @param {{nodes:Array, edges:Array}} graphJson
 * @param {object} options { settings, store, layer, onFocus(nodeId), height }
 * @returns {{ destroy():void, network:any, fit():void, selectNode(id):void }}
 */
export function mountNetworkView(container, graphJson, { settings = {}, store = null, layer = null, onFocus = null, height = 700 } = {}) {
  const vis = window.vis;
  if (!vis || !vis.Network) throw new Error("vis-network not loaded");
  const cfg = { ...DEFAULT_SETTINGS, ...settings };
  const [sizeMin, sizeMax] = cfg.node_size_range;
  const [fontMin, fontMax] = cfg.font_size_range;
  const [edgeMin, edgeMax] = cfg.edge_width_range;
  const isLarge = graphJson.nodes.length > LARGE_GRAPH;

  // ---- derive degree / neighbour maps ----------------------------------
  const degree = new Map();
  const neighbours = new Map(); // id -> [{id, weight}]
  for (const e of graphJson.edges) {
    degree.set(e.source, (degree.get(e.source) || 0) + 1);
    degree.set(e.target, (degree.get(e.target) || 0) + 1);
    if (!neighbours.has(e.source)) neighbours.set(e.source, []);
    if (!neighbours.has(e.target)) neighbours.set(e.target, []);
    neighbours.get(e.source).push({ id: e.target, weight: +e.weight || 1 });
    neighbours.get(e.target).push({ id: e.source, weight: +e.weight || 1 });
  }
  const maxDeg = Math.max(1, ...degree.values());
  const weights = graphJson.edges.map((e) => +e.weight || 1);
  const maxW = weights.length ? Math.max(...weights) : 1;
  const nodeById = new Map(graphJson.nodes.map((n) => [n.id, n]));

  const baseNodes = graphJson.nodes.map((n) => {
    const deg = degree.get(n.id) || 0;
    const ratio = deg / maxDeg;
    let size = sizeMin + ratio * (sizeMax - sizeMin);
    let font = fontMin + ratio * (fontMax - fontMin);
    if (n.type && n.type.startsWith("focus_")) { size = Math.max(size, sizeMin + 10); font = Math.max(font, fontMin + 4); }
    const c = colorFor(n.type);
    const label = n.label ?? n.id;
    return {
      id: n.id,
      label: label.length > 30 ? label.slice(0, 30) + "…" : label,
      size, shape: "dot",
      color: { background: c.background, border: c.border, highlight: { background: c.border, border: "#FFD700" }, hover: { background: c.background, border: "#FFD700" } },
      font: { size: Math.round(font), color: "#ffffff", strokeWidth: isLarge ? 0 : 3, strokeColor: "#000000" },
      borderWidth: n.type && n.type.startsWith("focus_") ? 3 : 2,
      _deg: deg, _type: n.type, _fullLabel: label,
    };
  });
  const baseEdges = graphJson.edges.map((e, i) => {
    const w = +e.weight || 1;
    const r = w / maxW;
    return {
      id: `e${i}`, from: e.source, to: e.target, value: w,
      width: edgeMin + r * (edgeMax - edgeMin),
      color: { color: `rgba(255,255,255,${(0.2 + r * 0.4).toFixed(2)})`, highlight: "rgba(255,215,0,0.9)", hover: "rgba(255,215,0,0.7)" },
      _w: w,
    };
  });

  const nodes = new vis.DataSet(baseNodes);
  const edges = new vis.DataSet(baseEdges);

  // ---- DOM ---------------------------------------------------------------
  container.replaceChildren();
  container.classList.add("netview");
  const canvasHost = el("div", { class: "netview-canvas", style: { height: `${height}px` } });
  const toolbar = el("div", { class: "netview-toolbar" });
  const searchInput = el("input", { type: "search", class: "input netview-search", placeholder: "Find node…", "aria-label": "Find node" });
  const searchList = el("datalist", { id: `nv-datalist-${Math.random().toString(36).slice(2, 8)}` });
  graphJson.nodes.slice(0, 2000).forEach((n) => searchList.append(el("option", { value: n.label ?? n.id })));
  searchInput.setAttribute("list", searchList.id);
  const btn = (label, title, handler) => el("button", { class: "btn btn-sm", type: "button", title, onClick: handler, text: label });
  const physicsBtn = btn("⏸ Physics", "Toggle physics simulation (SPACE)", () => togglePhysics());
  const fitBtn = btn("⤢ Fit", "Fit graph to view (F)", () => fit());
  const fsBtn = btn("⛶ Fullscreen", "Toggle fullscreen", () => toggleFullscreen());
  const pngBtn = btn("⬇ PNG", "Download the current view as PNG", () => exportPng());
  const labelsBtn = btn("🏷 Labels", "Toggle labels", () => toggleLabels());
  const stats = el("span", { class: "netview-stats muted small", text: `${graphJson.nodes.length} nodes · ${graphJson.edges.length} edges` });
  toolbar.append(searchInput, searchList, physicsBtn, fitBtn, labelsBtn, pngBtn, fsBtn, stats);

  const progress = el("div", { class: "netview-progress" }, el("div", { class: "netview-progress-fill" }), el("span", { class: "netview-progress-text", text: "Stabilizing layout…" }));
  const legend = el("div", { class: "netview-legend" });
  const help = el("div", { class: "netview-help" },
    el("div", { text: "🖱️ Drag to pan · scroll to zoom" }),
    el("div", { text: "📌 Click a node to highlight neighbours" }),
    el("div", { text: "⌨️ SPACE physics · F fit · ESC clear" }));
  const inspector = el("aside", { class: "netview-inspector", hidden: true });
  const tooltip = el("div", { class: "netview-tooltip", hidden: true });
  const wrap = el("div", { class: "netview-wrap" }, canvasHost, progress, legend, help, tooltip, inspector);
  container.append(toolbar, wrap);

  renderLegend();

  // ---- vis-network ---------------------------------------------------------
  const physics = cfg.solver === "forceAtlas2Based"
    ? { solver: "forceAtlas2Based", forceAtlas2Based: { gravitationalConstant: -60, centralGravity: 0.01, springLength: 120, springConstant: 0.08, damping: 0.6, avoidOverlap: 0.4 } }
    : { solver: "barnesHut", barnesHut: { gravitationalConstant: -15000, centralGravity: 0.3, springLength: 150, springConstant: 0.04, damping: 0.95, avoidOverlap: 0.5 } };
  const options = {
    nodes: { shadow: isLarge ? false : { enabled: true, size: 10, x: 3, y: 3 }, borderWidthSelected: 3, scaling: { min: sizeMin, max: sizeMax } },
    edges: { smooth: isLarge ? false : { type: "continuous" }, selectionWidth: 3, hoverWidth: 1.5 },
    physics: {
      enabled: true,
      ...physics,
      stabilization: { enabled: true, iterations: cfg.physics_iterations, updateInterval: 25, fit: true },
      minVelocity: 0.75, maxVelocity: 30,
    },
    interaction: {
      hover: true, hoverConnectedEdges: true, navigationButtons: !isLarge, keyboard: { enabled: false },
      zoomView: true, dragView: true, tooltipDelay: 100, multiselect: true, hideEdgesOnDrag: isLarge, hideEdgesOnZoom: isLarge,
    },
    layout: { improvedLayout: !isLarge, randomSeed: 42 },
  };
  const network = new vis.Network(canvasHost, { nodes, edges }, options);

  let physicsOn = true;
  let labelsOn = true;
  let selected = null;
  let autoStopTimer = null;

  network.on("stabilizationProgress", (p) => {
    progress.hidden = false;
    progress.firstChild.style.width = `${Math.round((p.iterations / p.total) * 100)}%`;
  });
  network.once("stabilizationIterationsDone", () => {
    progress.hidden = true;
    network.fit({ animation: { duration: 400, easingFunction: "easeInOutQuad" } });
    if (cfg.auto_stop_physics) {
      autoStopTimer = setTimeout(() => setPhysics(false), isLarge ? 500 : 5000);
    }
  });

  // ---- interactions -----------------------------------------------------------
  network.on("hoverNode", (params) => {
    const n = nodes.get(params.node);
    if (!n) return;
    const pos = params.event.center || { x: params.pointer.DOM.x, y: params.pointer.DOM.y };
    showTooltip(tooltipHtml(n), pos);
  });
  network.on("blurNode", hideTooltip);
  network.on("hoverEdge", (params) => {
    const e = edges.get(params.edge);
    if (!e) return;
    const a = nodeById.get(e.from), b = nodeById.get(e.to);
    showTooltip(`<b>${escapeHtml(a?.label ?? e.from)}</b> ↔ <b>${escapeHtml(b?.label ?? e.to)}</b><br>Connection strength: ${(+e._w).toFixed(2)}`, params.event.center || params.pointer.DOM);
  });
  network.on("blurEdge", hideTooltip);
  network.on("dragStart", hideTooltip);
  network.on("zoom", hideTooltip);
  network.on("click", (params) => {
    hideTooltip();
    if (params.nodes.length) selectNode(params.nodes[0]);
    else clearSelection();
  });
  network.on("doubleClick", (params) => {
    if (params.nodes.length) {
      network.focus(params.nodes[0], { scale: 1.4, animation: { duration: 500, easingFunction: "easeInOutQuad" } });
    }
  });

  const onKey = (e) => {
    if (!container.isConnected) { window.removeEventListener("keydown", onKey); return; }
    const tag = (e.target && e.target.tagName) || "";
    if (["INPUT", "TEXTAREA", "SELECT"].includes(tag)) return;
    if (!isVisible(container)) return;
    if (e.code === "Space") { e.preventDefault(); togglePhysics(); }
    else if (e.key === "f" || e.key === "F") { fit(); }
    else if (e.key === "Escape") { clearSelection(); }
  };
  window.addEventListener("keydown", onKey);

  searchInput.addEventListener("change", () => findNode(searchInput.value));
  searchInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") { e.preventDefault(); findNode(searchInput.value); }
    else if (e.key === "Escape") { clearSelection(); searchInput.blur(); }
  });
  // Chromium consumes Escape when the datalist popup is open and instead fires
  // "search" once the field is cleared — treat that as "clear selection" too.
  searchInput.addEventListener("search", () => { if (!searchInput.value) { clearSelection(); searchInput.blur(); } });

  // ---- helpers -------------------------------------------------------------------
  function isVisible(node) { return !!(node.offsetWidth || node.offsetHeight || node.getClientRects().length); }

  function tooltipHtml(n) {
    const meta = nodeById.get(n.id) || {};
    const type = (n._type || "").replace(/^focus_/, "");
    const lines = [`<b>${escapeHtml(n._fullLabel)}</b>`];
    if (type.startsWith("community_")) lines.push(`Community: ${type.slice(10)}`);
    else lines.push(`Type: ${TYPE_LABELS[type] || type}${n._type?.startsWith("focus_") ? " (focus)" : ""}`);
    lines.push(`Connections: ${n._deg}`);
    if (meta.count != null) lines.push(`Papers: ${meta.count}`);
    if (meta.country) lines.push(`Country: ${escapeHtml(meta.country)}`);
    lines.push(`<span class="muted">ID: ${escapeHtml(n.id)}</span>`);
    return lines.join("<br>");
  }
  function showTooltip(html, pos) {
    tooltip.innerHTML = html;
    tooltip.hidden = false;
    const rect = wrap.getBoundingClientRect();
    let x = pos.x, y = pos.y;
    // DOM pointer coordinates are relative to the canvas; event.center is page-relative
    if (pos.x > rect.width || pos.y > rect.height) { x = pos.x - rect.left; y = pos.y - rect.top; }
    tooltip.style.left = `${Math.min(x + 14, rect.width - tooltip.offsetWidth - 8)}px`;
    tooltip.style.top = `${Math.min(y + 14, rect.height - tooltip.offsetHeight - 8)}px`;
  }
  function hideTooltip() { tooltip.hidden = true; }

  function setPhysics(on) {
    physicsOn = on;
    network.setOptions({ physics: { enabled: on } });
    physicsBtn.textContent = on ? "⏸ Physics" : "▶ Physics";
    physicsBtn.classList.toggle("active", on);
  }
  function togglePhysics() { if (autoStopTimer) { clearTimeout(autoStopTimer); autoStopTimer = null; } setPhysics(!physicsOn); }
  function fit() { network.fit({ animation: { duration: 500, easingFunction: "easeInOutQuad" } }); }
  function toggleLabels() {
    labelsOn = !labelsOn;
    nodes.update(baseNodes.map((n) => ({ id: n.id, font: { ...n.font, size: labelsOn ? n.font.size : 0 } })));
    labelsBtn.classList.toggle("active", !labelsOn);
  }
  function toggleFullscreen() {
    if (document.fullscreenElement === wrap) document.exitFullscreen();
    else wrap.requestFullscreen?.().catch(() => toast("Fullscreen not available", "warning"));
  }
  document.addEventListener("fullscreenchange", () => {
    canvasHost.style.height = document.fullscreenElement === wrap ? "100vh" : `${height}px`;
    network.redraw();
    setTimeout(fit, 50);
  });
  function exportPng() {
    const canvas = canvasHost.querySelector("canvas");
    if (!canvas) return;
    // vis-network draws on a transparent canvas; composite onto the dark background
    const out = document.createElement("canvas");
    out.width = canvas.width; out.height = canvas.height;
    const ctx = out.getContext("2d");
    ctx.fillStyle = "#222222"; ctx.fillRect(0, 0, out.width, out.height);
    ctx.drawImage(canvas, 0, 0);
    const a = document.createElement("a");
    a.download = `relatenta_graph_${new Date().toISOString().slice(0, 10)}.png`;
    a.href = out.toDataURL("image/png");
    a.click();
  }
  function findNode(query) {
    const q = (query || "").trim().toLowerCase();
    if (!q) return;
    const hit = graphJson.nodes.find((n) => (n.label ?? n.id).toLowerCase() === q) || graphJson.nodes.find((n) => (n.label ?? n.id).toLowerCase().includes(q));
    if (!hit) { toast(`No node matching “${escapeHtml(query)}”`, "warning"); return; }
    selectNode(hit.id);
    network.focus(hit.id, { scale: 1.3, animation: { duration: 500, easingFunction: "easeInOutQuad" } });
  }

  function selectNode(id) {
    selected = id;
    const nb = new Set((neighbours.get(id) || []).map((x) => x.id));
    nb.add(id);
    if (!isLarge) {
      nodes.update(baseNodes.map((n) => nb.has(n.id)
        ? { id: n.id, color: n.color, font: { ...n.font, size: labelsOn ? n.font.size : 0 }, opacity: 1 }
        : { id: n.id, color: { background: "rgba(120,120,120,0.25)", border: "rgba(120,120,120,0.3)" }, font: { ...n.font, color: "rgba(255,255,255,0.25)", strokeWidth: 0, size: labelsOn ? n.font.size : 0 } }));
      edges.update(baseEdges.map((e) => (e.from === id || e.to === id)
        ? { id: e.id, color: { color: "rgba(255,215,0,0.85)", highlight: "rgba(255,215,0,0.95)" }, width: Math.max(e.width, 1.5) }
        : { id: e.id, color: { color: "rgba(255,255,255,0.06)" }, width: e.width }));
    }
    network.selectNodes([id]);
    renderInspector(id);
  }
  function clearSelection() {
    if (selected === null && inspector.hidden) return;
    selected = null;
    if (!isLarge) {
      nodes.update(baseNodes.map((n) => ({ id: n.id, color: n.color, font: { ...n.font, size: labelsOn ? n.font.size : 0 } })));
      edges.update(baseEdges.map((e) => ({ id: e.id, color: e.color, width: e.width })));
    }
    network.unselectAll();
    inspector.hidden = true;
  }

  function renderInspector(id) {
    const meta = nodeById.get(id) || { id, label: id };
    const n = nodes.get(id);
    const nbs = (neighbours.get(id) || []).slice().sort((a, b) => b.weight - a.weight);
    const type = (meta.type || "").replace(/^focus_/, "");
    const closeBtn = el("button", { class: "btn btn-sm inspector-close", type: "button", "aria-label": "Close", text: "×", onClick: clearSelection });
    const head = el("div", { class: "inspector-head" },
      el("span", { class: "swatch", style: { background: colorFor(meta.type).background } }),
      el("h4", { text: meta.label ?? id }), closeBtn);
    const facts = el("dl", { class: "inspector-facts" });
    const fact = (k, v) => facts.append(el("dt", { text: k }), el("dd", { html: v }));
    fact("Type", type.startsWith("community_") ? `Community ${type.slice(10)}` : (TYPE_LABELS[type] || type));
    fact("Connections", String(n?._deg ?? 0));
    if (meta.count != null) fact("Papers", String(meta.count));
    if (meta.country) fact("Country", escapeHtml(meta.country));
    fact("ID", `<code>${escapeHtml(id)}</code>`);

    const nbList = el("ul", { class: "inspector-list" }, ...nbs.slice(0, 25).map((x) => {
      const nm = nodeById.get(x.id);
      const li = el("li", {}, el("a", { href: "#", text: nm?.label ?? x.id, onClick: (e) => { e.preventDefault(); selectNode(x.id); network.focus(x.id, { scale: 1.2, animation: true }); } }),
        el("span", { class: "muted small", text: ` ${x.weight}` }));
      return li;
    }));
    if (nbs.length > 25) nbList.append(el("li", { class: "muted small", text: `… ${nbs.length - 25} more` }));

    const actions = el("div", { class: "inspector-actions" });
    if (onFocus) actions.append(el("button", { class: "btn btn-sm btn-primary", type: "button", text: "Focus on this node", onClick: () => onFocus(id, meta) }));
    actions.append(el("button", { class: "btn btn-sm", type: "button", text: "Zoom to", onClick: () => network.focus(id, { scale: 1.5, animation: true }) }));

    inspector.replaceChildren(head, facts, actions, el("h5", { text: `Neighbours (${nbs.length})` }), nbList);

    // Author nodes: list the underlying papers (from the store) — a real value-add over PyVis.
    if (store && layer === "authors" && id.startsWith("A")) {
      const aid = parseInt(id.slice(1), 10);
      const papers = store.works.filter((w) => store.authorsOfWork(w.id).some((r) => r.author_id === aid))
        .sort((a, b) => (b.year || 0) - (a.year || 0)).slice(0, 15);
      if (papers.length) {
        inspector.append(el("h5", { text: `Papers (${papers.length}${papers.length === 15 ? "+" : ""})` }),
          el("ul", { class: "inspector-list" }, ...papers.map((w) => {
            const link = w.doi ? "https://doi.org/" + w.doi.replace(/^https?:\/\/doi\.org\//, "") : w.url;
            return el("li", {}, link ? el("a", { href: link, target: "_blank", rel: "noopener", text: w.title }) : el("span", { text: w.title }), el("span", { class: "muted small", text: w.year ? ` (${w.year})` : "" }));
          })));
      }
    }
    inspector.hidden = false;
  }

  function renderLegend() {
    const types = new Set(graphJson.nodes.map((n) => n.type || "default"));
    const items = [];
    const seenComm = new Set();
    for (const t of types) {
      if (t.startsWith("community_")) { seenComm.add(parseInt(t.slice(10), 10)); continue; }
      const base = t.replace(/^focus_/, "");
      items.push([t.startsWith("focus_") ? `Focus ${TYPE_LABELS[base] || base}` : (TYPE_LABELS[base] || base), colorFor(t).background]);
    }
    [...seenComm].sort((a, b) => a - b).slice(0, 15).forEach((c) => items.push([`Community ${c}`, colorFor("community_" + c).background]));
    legend.replaceChildren(...items.map(([label, color]) => el("span", { class: "legend-item" }, el("span", { class: "swatch", style: { background: color } }), label)));
    legend.hidden = !items.length;
    if (isLarge) legend.append(el("span", { class: "legend-item muted", text: "performance mode" }));
  }

  return {
    network, nodes, edges,
    fit, selectNode, clearSelection, setPhysics,
    destroy() {
      window.removeEventListener("keydown", onKey);
      if (autoStopTimer) clearTimeout(autoStopTimer);
      network.destroy();
      container.replaceChildren();
    },
  };
}
