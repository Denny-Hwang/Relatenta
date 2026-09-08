/**
 * Plotly helpers. plotly.min.js is 4.5 MB, so it is loaded lazily the first
 * time a chart is needed (Heatmaps / Report / Insights) — the Graph tab stays
 * fast on first paint.
 */
let plotlyPromise = null;
export function ensurePlotly() {
  if (window.Plotly) return Promise.resolve(window.Plotly);
  if (!plotlyPromise) {
    plotlyPromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "vendor/plotly.min.js";
      s.onload = () => resolve(window.Plotly);
      s.onerror = () => { plotlyPromise = null; reject(new Error("Failed to load Plotly")); };
      document.head.append(s);
    });
  }
  return plotlyPromise;
}

const BASE_LAYOUT = {
  paper_bgcolor: "rgba(0,0,0,0)",
  plot_bgcolor: "rgba(0,0,0,0)",
  font: { family: "system-ui, -apple-system, Segoe UI, Roboto, 'Noto Sans KR', sans-serif", size: 12, color: "#2c3e50" },
  margin: { l: 40, r: 20, t: 30, b: 40 },
};
const CONFIG = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] };

export async function plot(container, data, layout = {}, config = {}) {
  const Plotly = await ensurePlotly();
  container.classList.add("chart");
  await Plotly.react(container, data, { ...BASE_LAYOUT, ...layout, margin: { ...BASE_LAYOUT.margin, ...(layout.margin || {}) } }, { ...CONFIG, ...config });
  return container;
}

export function barChart(container, x, y, { color = "#4A90E2", xTitle = "", yTitle = "", height = 350, text = null, colors = null, title = "" } = {}) {
  return plot(container, [{ type: "bar", x, y, marker: { color: colors || color }, text, textposition: text ? "outside" : undefined, hovertemplate: "%{x}: %{y}<extra></extra>" }],
    { height, title: title ? { text: title, font: { size: 14 } } : undefined, xaxis: { title: xTitle, automargin: true }, yaxis: { title: yTitle, automargin: true, rangemode: "tozero" } });
}

export function hbarChart(container, labels, values, { color = "#4A90E2", xTitle = "", height = null } = {}) {
  const h = height || Math.max(350, labels.length * 28 + 80);
  return plot(container, [{ type: "bar", orientation: "h", x: values, y: labels, marker: { color }, hovertemplate: "%{y}: %{x}<extra></extra>" }],
    { height: h, margin: { l: 10, r: 20, t: 10, b: 30 }, xaxis: { title: xTitle, rangemode: "tozero" }, yaxis: { autorange: "reversed", automargin: true } });
}

export function heatmapChart(container, z, x, y, { height = null } = {}) {
  const h = height || Math.max(500, y.length * 28 + 200);
  return plot(container, [{ type: "heatmap", z, x, y, colorscale: "Viridis", colorbar: { title: "Weight" }, hovertemplate: "%{y} × %{x}: %{z}<extra></extra>" }],
    { height: h, margin: { l: 10, r: 10, t: 30, b: 80 }, xaxis: { title: "Columns", automargin: true, tickangle: -45 }, yaxis: { title: "Rows", automargin: true, autorange: "reversed" } });
}

export function strategicDiagram(container, themes) {
  const quadrantColors = { Motor: "#2ECC71", Niche: "#3498DB", "Basic & Transversal": "#F39C12", "Emerging or Declining": "#E74C3C" };
  const traces = themes.map((t) => ({
    type: "scatter", mode: "markers+text", x: [t.centrality_norm], y: [t.density_norm],
    marker: { size: Math.max(t.size * 5, 15), color: quadrantColors[t.quadrant] || "#888", opacity: 0.75, line: { width: 2, color: "white" } },
    text: [t.label], textposition: "top center", textfont: { size: 11 }, name: t.quadrant,
    hovertemplate: `<b>${t.label}</b><br>Quadrant: ${t.quadrant}<br>Keywords: ${t.top_keywords.slice(0, 3).join(", ")}<br>Centrality: ${t.centrality_norm.toFixed(2)}<br>Density: ${t.density_norm.toFixed(2)}<br>Papers: ${t.total_papers}<br>Size: ${t.size} keywords<extra></extra>`,
  }));
  const ann = (x, y, text, color) => ({ x, y, text, showarrow: false, font: { size: 12, color } });
  return plot(container, traces, {
    height: 600, showlegend: false, title: { text: "Strategic Diagram (Callon's Centrality-Density)", font: { size: 14 } },
    xaxis: { title: "Centrality (External Cohesion)", range: [-0.05, 1.05] }, yaxis: { title: "Density (Internal Cohesion)", range: [-0.05, 1.05] },
    shapes: [
      { type: "line", x0: 0.5, x1: 0.5, y0: -0.05, y1: 1.05, line: { dash: "dash", color: "rgba(0,0,0,0.25)" } },
      { type: "line", x0: -0.05, x1: 1.05, y0: 0.5, y1: 0.5, line: { dash: "dash", color: "rgba(0,0,0,0.25)" } },
    ],
    annotations: [ann(0.75, 0.95, "MOTOR THEMES", "#2ECC71"), ann(0.25, 0.95, "NICHE THEMES", "#3498DB"), ann(0.75, 0.05, "BASIC & TRANSVERSAL", "#F39C12"), ann(0.25, 0.05, "EMERGING / DECLINING", "#E74C3C")],
  });
}

export function sankeyChart(container, result) {
  const palette = ["#4A90E2", "#F5A623", "#7ED321", "#BD10E0", "#FF6B6B", "#50E3C2", "#9013FE", "#F8E71C", "#D0021B", "#417505"];
  const rgba = ["rgba(74,144,226,0.4)", "rgba(245,166,35,0.4)", "rgba(126,211,33,0.4)", "rgba(189,16,224,0.4)", "rgba(255,107,107,0.4)", "rgba(80,227,194,0.4)", "rgba(144,19,254,0.4)", "rgba(248,231,28,0.4)", "rgba(208,2,27,0.4)", "rgba(65,117,5,0.4)"];
  const idx = new Map(result.nodes.map((n, i) => [n.id, i]));
  const source = [], target = [], value = [], linkColor = [];
  for (const f of result.flows) {
    if (!idx.has(f.source) || !idx.has(f.target)) continue;
    const s = idx.get(f.source);
    source.push(s); target.push(idx.get(f.target)); value.push(Math.max(f.weight, 1));
    linkColor.push(rgba[result.nodes[s].period % rgba.length]);
  }
  const periodLabels = result.periods.map((p) => p.label).join(" -> ");
  return plot(container, [{
    type: "sankey",
    node: { pad: 30, thickness: 25, line: { color: "black", width: 0.5 }, label: result.nodes.map((n) => n.label), color: result.nodes.map((n) => palette[n.period % palette.length]) },
    link: { source, target, value, color: linkColor },
  }], { height: Math.max(500, result.nodes.length * 40), title: { text: `Thematic Evolution: ${periodLabels}`, font: { size: 14 } }, font: { size: 13 }, margin: { l: 10, r: 10, t: 40, b: 10 } });
}
