/** Port of app/services_heatmap.py. */

function inRange(y, yMin, yMax) {
  if (yMin != null && (y == null || y < yMin)) return false;
  if (yMax != null && (y == null || y > yMax)) return false;
  return true;
}

export function authorKeywordHeat(store, yearMin = null, yearMax = null) {
  const ak = new Map(), authorTot = new Map(), kwTot = new Map();
  for (const w of store.works) {
    if (!inRange(w.year, yearMin, yearMax)) continue;
    const authors = new Set(store.authorsOfWork(w.id).map((r) => r.author_id));
    const kws = new Set(store.keywordsOfWork(w.id).map((r) => r.keyword_id));
    if (!authors.size || !kws.size) continue;
    for (const a of authors) for (const k of kws) {
      const key = a + "|" + k;
      ak.set(key, (ak.get(key) || 0) + 1);
      authorTot.set(a, (authorTot.get(a) || 0) + 1);
      kwTot.set(k, (kwTot.get(k) || 0) + 1);
    }
  }
  const topN = (m) => [...m.entries()].sort((x, y) => y[1] - x[1]).slice(0, 30).map((e) => e[0]);
  const topAuthors = topN(authorTot), topKeywords = topN(kwTot);
  const rows = topAuthors.map((a) => ({ id: a, label: store.getAuthor(a)?.display_name ?? "A" + a }));
  const cols = topKeywords.map((k) => ({ id: k, label: store.getKeyword(k)?.term_display ?? "K" + k }));
  const data = topAuthors.map((a) => topKeywords.map((k) => ak.get(a + "|" + k) || 0));
  return { rows, cols, data };
}

export function nationNationHeat(store) {
  const edges = store.nationEdges;
  const nations = [...new Set(edges.flatMap((e) => [e.n1, e.n2]))].sort();
  const idx = new Map(nations.map((n, i) => [n, i]));
  const m = nations.map(() => nations.map(() => 0));
  for (const e of edges) {
    const i = idx.get(e.n1), j = idx.get(e.n2);
    m[i][j] += e.weight;
    m[j][i] += e.weight;
  }
  const rc = nations.map((n, i) => ({ id: i, label: n }));
  return { rows: rc, cols: rc.map((x) => ({ ...x })), data: m };
}
