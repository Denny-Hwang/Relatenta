/**
 * OpenAlex client — port of app/connectors_openalex.py using fetch().
 *
 * Differences from the Python connector (both forced by running in a browser):
 *  - Google Scholar profile resolution is not available (no CORS, bot blocking).
 *  - The orcid.org HTML-scrape fallback is dropped; the ORCID public API
 *    (pub.orcid.org, CORS-enabled) is still used to resolve a name.
 */
export const OPENALEX = "https://api.openalex.org";
const ORCID_RE = /\d{4}-\d{4}-\d{4}-\d{3}[\dX]/;

let mailto = "";
try { mailto = (localStorage.getItem("relatenta.mailto") || "").trim(); } catch (e) { /* ignore */ }
export function getMailto() { return mailto; }
export function setMailto(v) {
  mailto = (v || "").trim();
  try { localStorage.setItem("relatenta.mailto", mailto); } catch (e) { /* ignore */ }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** GET with retry + exponential backoff (mirrors urllib3 Retry: 4 retries, 0.5s factor). */
export async function getJson(url, params = {}, { retries = 4, backoff = 500, timeout = 30000, signal } = {}) {
  const u = new URL(url);
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null) u.searchParams.set(k, v);
  if (mailto && !u.searchParams.has("mailto") && u.hostname.endsWith("openalex.org")) u.searchParams.set("mailto", mailto);
  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeout);
    if (signal) signal.addEventListener("abort", () => ctrl.abort(), { once: true });
    try {
      const res = await fetch(u.toString(), { signal: ctrl.signal, headers: { Accept: "application/json" } });
      clearTimeout(timer);
      if (res.ok) return await res.json();
      if ([429, 500, 502, 503, 504].includes(res.status) && attempt < retries) {
        const ra = parseFloat(res.headers.get("Retry-After"));
        await sleep(Number.isFinite(ra) ? ra * 1000 : backoff * 2 ** attempt);
        continue;
      }
      const err = new Error(`HTTP ${res.status} for ${u.pathname}`);
      err.status = res.status;
      throw err;
    } catch (e) {
      clearTimeout(timer);
      lastErr = e;
      if (e.status || (signal && signal.aborted) || attempt >= retries) throw e;
      await sleep(backoff * 2 ** attempt);
    }
  }
  throw lastErr;
}

export function formatAuthorResult(item) {
  const stats = item.summary_stats || {};
  const info = {
    id: item.id,
    display_name: item.display_name,
    works_count: item.works_count || 0,
    cited_by_count: item.cited_by_count || 0,
    orcid: item.orcid || null,
    last_known_institution: null,
    institution_country: null,
    institution_type: null,
    top_concepts: [],
    works_api_url: item.works_api_url,
    h_index: stats.h_index || 0,
    i10_index: stats.i10_index || 0,
  };
  // last_known_institution was replaced by last_known_institutions (list) in 2024.
  const inst = item.last_known_institution || (item.last_known_institutions || [])[0] || (item.affiliations || [])[0]?.institution;
  if (inst && typeof inst === "object") {
    info.last_known_institution = inst.display_name || null;
    info.institution_country = inst.country_code || null;
    info.institution_type = inst.type || null;
  }
  const concepts = item.x_concepts || (item.topics || []).map((tp) => ({ display_name: tp.display_name, score: (tp.count || 0) / Math.max(item.works_count || 1, 1) }));
  if (concepts.length) {
    info.top_concepts = concepts.slice().sort((a, b) => (b.score || 0) - (a.score || 0)).slice(0, 3)
      .map((c) => ({ name: c.display_name, score: c.score || 0 }));
  }
  return info;
}

export function detectQueryType(query) {
  const q = query.trim();
  if (q.includes("scholar.google.")) return "google_scholar";
  if (q.includes("orcid.org/")) return "orcid";
  if (new RegExp("^" + ORCID_RE.source + "$").test(q)) return "orcid";
  return "name";
}

export async function searchAuthorsByName(name, perPage = 25) {
  const data = await getJson(`${OPENALEX}/authors`, { search: name, per_page: perPage });
  return (data.results || []).map(formatAuthorResult);
}

export async function searchAuthorByOrcid(input) {
  let q = input.trim();
  if (q.includes("orcid.org/")) q = q.split("orcid.org/").pop().trim().replace(/\/+$/, "");
  const m = q.match(ORCID_RE);
  if (!m) return { results: [], method: "orcid" };
  const orcid = m[0];
  try {
    const item = await getJson(`${OPENALEX}/authors/orcid:${orcid}`);
    if (item && item.id) return { results: [formatAuthorResult(item)], method: "orcid" };
  } catch (e) { /* fall through */ }
  try {
    const data = await getJson(`${OPENALEX}/authors`, { filter: `orcid:${orcid}` });
    const results = (data.results || []).map(formatAuthorResult);
    if (results.length) return { results, method: "orcid" };
  } catch (e) { /* fall through */ }
  const name = await resolveOrcidName(orcid);
  if (name) return { results: await searchAuthorsByName(name), method: "orcid_name_fallback" };
  return { results: [], method: "orcid" };
}

async function resolveOrcidName(orcid) {
  try {
    const data = await getJson(`https://pub.orcid.org/v3.0/${orcid}/personal-details`, {}, { retries: 1, timeout: 15000 });
    const n = data.name || {};
    const full = `${n["given-names"]?.value || ""} ${n["family-name"]?.value || ""}`.trim();
    if (full) return full;
  } catch (e) { /* ignore */ }
  return null;
}

/** Fetch an author's works (sorted by citations), page by page. */
export async function listAuthorWorks(authorId, perPage = 200, maxPages = 3, onProgress = null, signal = null) {
  let filter = authorId.startsWith("https://") ? authorId.split("/").pop() : authorId;
  if (!filter.startsWith("A")) filter = "A" + filter.replace(/A/g, "");
  const works = [];
  for (let page = 1; page <= maxPages; page++) {
    const data = await getJson(`${OPENALEX}/works`, {
      filter: `author.id:${filter}`, per_page: perPage, page, sort: "cited_by_count:desc",
    }, { timeout: 60000, signal });
    const results = data.results || [];
    works.push(...results);
    if (onProgress) onProgress(works.length, data.meta?.count ?? null);
    if (results.length < perPage) break;
  }
  return works;
}
