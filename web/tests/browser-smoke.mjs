/**
 * Browser smoke test for the static site: serves web/ on a local port, drives
 * it in headless Chromium with the OpenAlex API mocked (fixtures/works.json),
 * and exercises every tab, the network view, export/restore and persistence.
 *
 *   npm i playwright && npx playwright install --with-deps chromium
 *   node web/tests/browser-smoke.mjs
 *
 * Env: CHROME=/path/to/chromium (optional), SHOTS=dir to save screenshots.
 */
import { createServer } from "node:http";
import { readFileSync, existsSync, mkdirSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const webRoot = path.resolve(here, "..");
const works = JSON.parse(readFileSync(path.join(here, "fixtures", "works.json"), "utf-8"));
const shots = process.env.SHOTS || "";
if (shots) mkdirSync(shots, { recursive: true });
const shot = async (page, name, opts = {}) => { if (shots) await page.screenshot({ path: path.join(shots, name), ...opts }); };

const MIME = { ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json", ".png": "image/png", ".svg": "image/svg+xml" };
const server = createServer((req, res) => {
  let p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  if (p.endsWith("/")) p += "index.html";
  const file = path.join(webRoot, p);
  if (!file.startsWith(webRoot) || !existsSync(file) || statSync(file).isDirectory()) { res.writeHead(404); res.end("not found"); return; }
  res.writeHead(200, { "Content-Type": MIME[path.extname(file)] || "application/octet-stream" });
  res.end(readFileSync(file));
});
await new Promise((r) => server.listen(0, "127.0.0.1", r));
const BASE = `http://127.0.0.1:${server.address().port}/`;

const { chromium } = await import("playwright");
const browser = await chromium.launch({ executablePath: process.env.CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1400, height: 900 } });
const page = await ctx.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push("pageerror: " + e.message));
page.on("console", (m) => { if (m.type() === "error") errors.push("console: " + m.text()); });

await page.route("https://api.openalex.org/**", async (route) => {
  const url = new URL(route.request().url());
  if (url.pathname === "/authors") {
    const q = url.searchParams.get("search") || "";
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ results: [
      { id: "https://openalex.org/A123", display_name: q || "Geoffrey Hinton", works_count: 60, cited_by_count: 1000, orcid: null,
        last_known_institutions: [{ display_name: "University of Toronto", country_code: "CA", type: "education" }],
        summary_stats: { h_index: 42, i10_index: 100 }, x_concepts: [{ display_name: "Machine learning", score: 0.9 }] },
      { id: "https://openalex.org/A456", display_name: q + " (other)", works_count: 3, cited_by_count: 5, summary_stats: { h_index: 1 } },
    ] }) });
  }
  if (url.pathname === "/works") return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ meta: { count: works.length }, results: works }) });
  return route.fulfill({ status: 404, body: "{}" });
});

const step = async (name, fn) => {
  try { await fn(); console.log("ok   -", name); }
  catch (e) { const msg = e.message.split("\n").filter((l) => l.trim()).slice(0, 3).join(" | "); console.log("FAIL -", name, "::", msg); errors.push(name + ": " + msg); await shot(page, `fail-${name.replace(/\W+/g, "_")}.png`); }
};

await page.goto(BASE, { waitUntil: "load" });

await step("demo loads and graph renders", async () => {
  await page.waitForSelector(".netview-wrap canvas", { timeout: 20000 });
  await page.waitForFunction(() => window.__relatenta && window.__relatenta.store.works.length === 60);
  await page.waitForSelector(".netview-progress", { state: "hidden", timeout: 20000 });
  if (document_has(await page.evaluate(() => document.body.innerText), /\bnull\b/)) throw new Error("stray 'null' text rendered");
  await shot(page, "01-graph.png");
});
function document_has(text, re) { return re.test(text); }

await step("sidebar stats + demo banner", async () => {
  const txt = await page.locator("#sidebar-content").innerText();
  if (!/Papers\s*60/.test(txt)) throw new Error("sidebar stats missing");
  if (!(await page.locator("#tab-graph .alert-info").count())) throw new Error("demo banner missing");
});

await step("find node opens inspector with neighbours and papers", async () => {
  await page.fill(".netview-search", "Alice Kim");
  await page.press(".netview-search", "Enter");
  await page.waitForSelector(".netview-inspector:not([hidden])", { timeout: 5000 });
  await page.waitForTimeout(200);
  const t = await page.locator(".netview-inspector").innerText();
  if (!t.includes("Alice Kim") || !/neighbours/i.test(t) || !/papers/i.test(t)) throw new Error("inspector content: " + t.slice(0, 120));
  await shot(page, "02-inspector.png");
  await page.keyboard.press("Escape");
  await page.waitForSelector(".netview-inspector", { state: "hidden" });
});

await step("toolbar + keyboard shortcuts", async () => {
  await page.click(".netview-canvas");
  await page.keyboard.press("Space");
  const label = await page.locator(".netview-toolbar button").first().innerText();
  if (!/Physics/.test(label)) throw new Error("physics button label: " + label);
  await page.keyboard.press("f");
  await page.click(".netview-toolbar button:has-text('Labels')");
});

await step("keywords layer + focus only", async () => {
  await page.selectOption("#tab-graph select.input >> nth=0", "keywords");
  await page.fill("#tab-graph .ms input[type=search]", "Machine");
  await page.click("#tab-graph .ms-item >> nth=0");
  await page.waitForTimeout(250);
  await page.check("input[name=focus-mode][value=only]");
  await page.click("#tab-graph button.btn-primary");
  await page.waitForFunction(() => /Graph: /.test(document.querySelector("#tab-graph .alert-success")?.textContent || ""));
  await page.waitForSelector(".netview-progress", { state: "hidden", timeout: 20000 });
  const legend = await page.locator("#tab-graph .netview-legend").innerText();
  if (!/Focus Keyword/.test(legend)) throw new Error("legend: " + legend);
  await shot(page, "03-keywords-focus.png");
});

await step("visualization controls + ForceAtlas2 solver", async () => {
  await page.click("#tab-graph details.expander summary");
  await page.selectOption("#tab-graph details.expander select", "forceAtlas2Based");
  await page.click("#tab-graph button.btn-primary");
  await page.waitForSelector(".netview-progress", { state: "hidden", timeout: 20000 });
});

await step("heatmap tab", async () => {
  await page.click(".tab[data-tab=heatmaps]");
  await page.click("#tab-heatmaps button.btn-primary");
  await page.waitForSelector("#tab-heatmaps .js-plotly-plot", { timeout: 30000 });
  await shot(page, "04-heatmap.png");
});

await step("report tab", async () => {
  await page.click(".tab[data-tab=report]");
  await page.click("#tab-report button.btn-primary");
  await page.waitForSelector("#tab-report .js-plotly-plot", { timeout: 30000 });
  await page.waitForSelector("#tab-report .netview-wrap canvas", { timeout: 20000 });
  const cnt = await page.locator("#tab-report .js-plotly-plot").count();
  if (cnt < 5) throw new Error("expected >=5 charts, got " + cnt);
  await shot(page, "05-report.png", { fullPage: true });
});

await step("insights: community detection", async () => {
  await page.click(".tab[data-tab=insights]");
  await page.click("#tab-insights button.btn-primary");
  await page.waitForSelector("#tab-insights .alert-success", { timeout: 20000 });
  await page.waitForSelector("#tab-insights .netview-wrap canvas", { timeout: 20000 });
  const legend = await page.locator("#tab-insights .netview-legend").innerText();
  if (!/Community/.test(legend)) throw new Error("legend: " + legend);
  await shot(page, "06-communities.png");
});

for (const [key, expectSel] of [
  ["burst", ".js-plotly-plot"], ["recommend", ".expander"], ["path", ".path-viz"],
  ["gap", ":is(.expander, .alert-success, .alert-info, .alert-warning)"],
  ["strategic", ":is(.js-plotly-plot, .alert-warning, .alert-info)"],
  ["evolution", ":is(.js-plotly-plot, .alert-warning, .alert-info)"],
]) {
  await step(`insights: ${key}`, async () => {
    await page.selectOption("#tab-insights select.input >> nth=0", key);
    await page.click("#tab-insights button.btn-primary");
    await page.waitForSelector(`#tab-insights ${expectSel}`, { timeout: 30000 });
    await shot(page, `07-${key}.png`);
  });
}

await step("export ZIP, clear, restore", async () => {
  await page.click(".tab[data-tab=graph]");
  const [dl] = await Promise.all([page.waitForEvent("download"), page.click("#sidebar-content button:has-text('Export CSV')")]);
  const zipPath = await dl.path();
  if (readFileSync(zipPath).length < 1000) throw new Error("zip too small");
  await page.click("#sidebar-content button:has-text('Start Fresh')");
  await page.click(".modal button.btn-danger");
  await page.waitForFunction(() => window.__relatenta.store.works.length === 0);
  await page.waitForSelector("#tab-graph .empty-state");
  await shot(page, "08-empty.png");
  await page.setInputFiles("#sidebar-content input[type=file][accept*=zip]", zipPath);
  await page.click("#sidebar-content button:has-text('Restore Data')");
  await page.waitForFunction(() => window.__relatenta.store.works.length === 60, null, { timeout: 15000 });
});

await step("dataset persists across reload (IndexedDB)", async () => {
  await page.reload({ waitUntil: "load" });
  await page.waitForFunction(() => window.__relatenta && window.__relatenta.store.works.length === 60, null, { timeout: 15000 });
  await page.waitForSelector(".netview-wrap canvas", { timeout: 20000 });
});

await step("search + ingest flow", async () => {
  await page.fill("#sidebar-content input[type=search]", "Geoffrey Hinton");
  await page.click("#sidebar-content button:has-text('Search')");
  await page.waitForSelector("#sidebar-content .hit", { timeout: 10000 });
  await page.check("#sidebar-content .hit >> nth=0 >> input[type=checkbox]");
  await page.click("#sidebar-content button:has-text('Ingest Selected')");
  await page.waitForFunction(() => window.__relatenta.store.works.length === 60, null, { timeout: 20000 });
  await page.waitForSelector("#tab-graph .netview-wrap canvas", { timeout: 20000 });
  await shot(page, "09-after-ingest.png");
});

await step("language toggle", async () => {
  await page.selectOption("#lang-select", "ko");
  if (!(await page.locator(".tabs").innerText()).includes("그래프")) throw new Error("korean tabs missing");
  await shot(page, "10-korean.png");
  await page.selectOption("#lang-select", "en");
});

await step("mobile layout", async () => {
  await page.setViewportSize({ width: 390, height: 800 });
  await page.reload({ waitUntil: "load" });
  await page.waitForSelector(".netview-wrap canvas", { timeout: 20000 });
  if (!(await page.locator("#sidebar.collapsed").count())) throw new Error("sidebar should be collapsed on mobile");
  await page.click("#sidebar-toggle");
  await shot(page, "11-mobile.png");
});

console.log(errors.length ? `\n${errors.length} error(s):\n - ${errors.join("\n - ")}` : "\nall browser checks passed");
await browser.close();
server.close();
process.exit(errors.length ? 1 : 0);
