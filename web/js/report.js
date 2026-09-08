/** Port of app/services_report.py — gather_report(db). */

export function gatherReport(store) {
  const n_works = store.works.length, n_authors = store.authors.length, n_orgs = store.organizations.length;
  const n_keywords = store.keywords.length, n_venues = store.venues.length;
  const [year_min, year_max] = store.yearRange();

  const yearCounts = new Map();
  for (const w of store.works) if (w.year != null) yearCounts.set(w.year, (yearCounts.get(w.year) || 0) + 1);
  const pub_trend = [...yearCounts.entries()].sort((a, b) => a[0] - b[0]).map(([year, count]) => ({ year, count }));

  const byCountDesc = (m) => [...m.entries()].sort((a, b) => b[1] - a[1]);

  const authorCnt = new Map();
  for (const r of store.allWorkAuthors()) authorCnt.set(r.author_id, (authorCnt.get(r.author_id) || 0) + 1);
  const top_authors = byCountDesc(authorCnt).slice(0, 20).map(([id, papers]) => ({ name: store.getAuthor(id)?.display_name, papers }));

  const kwCnt = new Map();
  for (const r of store.allWorkKeywords()) kwCnt.set(r.keyword_id, (kwCnt.get(r.keyword_id) || 0) + 1);
  const top_keywords = byCountDesc(kwCnt).slice(0, 20).map(([id, count]) => ({ term: store.getKeyword(id)?.term_display, count }));

  const ccWorks = new Map();
  for (const r of store.allWorkAffiliations()) {
    if (!r.country_code) continue;
    if (!ccWorks.has(r.country_code)) ccWorks.set(r.country_code, new Set());
    ccWorks.get(r.country_code).add(r.work_id);
  }
  const country_dist = [...ccWorks.entries()].map(([cc, s]) => [cc, s.size]).sort((a, b) => b[1] - a[1]).slice(0, 20)
    .map(([country, papers]) => ({ country, papers }));

  const top_collabs = [...store.coauthorEdges].sort((a, b) => b.weight - a.weight).slice(0, 15).flatMap((e) => {
    const a = store.getAuthor(e.a_id), b = store.getAuthor(e.b_id);
    return a && b ? [{ author_a: a.display_name, author_b: b.display_name, weight: e.weight, papers: e.evidence_count }] : [];
  });

  const pairCnt = new Map();
  for (const w of store.works) {
    const kws = [...new Set(store.keywordsOfWork(w.id).map((r) => r.keyword_id))].sort((a, b) => a - b);
    for (let i = 0; i < kws.length; i++) for (let j = i + 1; j < kws.length; j++) {
      const key = kws[i] + "|" + kws[j];
      pairCnt.set(key, (pairCnt.get(key) || 0) + 1);
    }
  }
  const top_kw_pairs = byCountDesc(pairCnt).slice(0, 15).flatMap(([key, cnt]) => {
    const [k1, k2] = key.split("|").map(Number);
    const a = store.getKeyword(k1), b = store.getKeyword(k2);
    return a && b ? [{ keyword_a: a.term_display, keyword_b: b.term_display, co_occurrences: cnt }] : [];
  });

  const venueCnt = new Map();
  for (const w of store.works) if (w.venue_id) venueCnt.set(w.venue_id, (venueCnt.get(w.venue_id) || 0) + 1);
  const top_venues = byCountDesc(venueCnt).slice(0, 15).map(([id, papers]) => ({ venue: store.getVenue(id)?.name, papers }));

  const scored = store.works.map((w) => {
    const cited = (w.raw_json && typeof w.raw_json === "object" ? w.raw_json.cited_by_count : 0) || 0;
    const doiLink = w.doi ? "https://doi.org/" + w.doi.replace(/^https?:\/\/doi\.org\//, "") : null;
    const names = [...store.authorsOfWork(w.id)].sort((a, b) => a.position - b.position)
      .map((r) => store.getAuthor(r.author_id)?.display_name).filter(Boolean);
    let authors = names.slice(0, 5).join(", ");
    if (names.length > 5) authors += ` et al. (${names.length} authors)`;
    const venue = w.venue_id ? (store.getVenue(w.venue_id)?.name || "") : "";
    return { title: w.title, year: w.year, cited_by_count: cited, doi: w.doi, link: doiLink || w.url, authors, venue };
  });
  scored.sort((a, b) => b.cited_by_count - a.cited_by_count);
  const highlight_works = scored.slice(0, 15);

  const graphEdges = [...store.coauthorEdges].sort((a, b) => b.weight - a.weight).slice(0, 40);
  const nodeSet = new Set();
  const graph_edges = graphEdges.map((e) => { nodeSet.add(e.a_id); nodeSet.add(e.b_id); return { a: e.a_id, b: e.b_id, weight: e.weight }; });
  const graph_nodes = [...nodeSet].flatMap((id) => { const a = store.getAuthor(id); return a ? [{ id, label: a.display_name }] : []; });

  return {
    n_works, n_authors, n_orgs, n_keywords, n_venues, year_min, year_max, pub_trend, top_authors, top_keywords,
    country_dist, top_collabs, top_kw_pairs, top_venues, highlight_works, graph_nodes, graph_edges,
  };
}
