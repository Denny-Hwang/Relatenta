/**
 * In-memory relational store — a faithful port of app/models.py + app/crud.py.
 *
 * Tables mirror the SQLAlchemy schema (same column names, same integer
 * auto-increment ids starting at 1) so that graph node ids ("A12", "K3"…),
 * CSV exports and ZIP restores stay interchangeable with the Streamlit app.
 *
 * Relations (work_authors, work_affiliations, work_keywords) are kept as
 * Map<work_id, row[]> so per-work lookups and "clear relations of work X"
 * are O(1), which is what the upsert path needs.
 */

function norm(s) {
  return String(s ?? "").trim().toLowerCase();
}

export class Store {
  constructor() {
    this.reset();
  }

  reset() {
    this.works = [];
    this.authors = [];
    this.organizations = [];
    this.venues = [];
    this.keywords = [];
    /** @type {Map<number, Array<{work_id:number, author_id:number, position:number, corresponding:boolean}>>} */
    this.workAuthors = new Map();
    /** @type {Map<number, Array<{id:number, work_id:number, author_id:number|null, org_id:number|null, org_label_raw:string|null, year:number|null, country_code:string|null}>>} */
    this.workAffiliations = new Map();
    /** @type {Map<number, Array<{work_id:number, keyword_id:number, weight:number, extractor:string|null}>>} */
    this.workKeywords = new Map();
    this.coauthorEdges = []; // {a_id, b_id, weight, evidence_count}
    this.orgEdges = []; // {org1_id, org2_id, weight}
    this.nationEdges = []; // {n1, n2, weight}
    this._seq = { works: 0, authors: 0, organizations: 0, venues: 0, keywords: 0, affiliations: 0 };
    this._byId = {
      works: new Map(), authors: new Map(), organizations: new Map(), venues: new Map(), keywords: new Map(),
    };
    this._authorsByNorm = new Map();
    this._keywordsByNorm = new Map();
    this._orgsByName = new Map();
    this._venuesByName = new Map();
    this._worksByDoi = new Map();
    this._worksBySourceUid = new Map();
    this.version = 0;
  }

  // ---- lookups -----------------------------------------------------------
  getWork(id) { return this._byId.works.get(id) || null; }
  getAuthor(id) { return this._byId.authors.get(id) || null; }
  getOrg(id) { return this._byId.organizations.get(id) || null; }
  getVenue(id) { return this._byId.venues.get(id) || null; }
  getKeyword(id) { return this._byId.keywords.get(id) || null; }

  authorsOfWork(workId) { return this.workAuthors.get(workId) || []; }
  affiliationsOfWork(workId) { return this.workAffiliations.get(workId) || []; }
  keywordsOfWork(workId) { return this.workKeywords.get(workId) || []; }

  *allWorkAuthors() { for (const rows of this.workAuthors.values()) yield* rows; }
  *allWorkAffiliations() { for (const rows of this.workAffiliations.values()) yield* rows; }
  *allWorkKeywords() { for (const rows of this.workKeywords.values()) yield* rows; }

  findWorkByDoi(doi) { return this._worksByDoi.get(doi) || null; }
  findWorkByTitle(title) { return this.works.find((w) => w.title === title) || null; }

  stats() {
    return {
      works: this.works.length,
      authors: this.authors.length,
      organizations: this.organizations.length,
      keywords: this.keywords.length,
      venues: this.venues.length,
    };
  }

  yearRange() {
    let mn = null, mx = null;
    for (const w of this.works) {
      if (w.year == null) continue;
      if (mn == null || w.year < mn) mn = w.year;
      if (mx == null || w.year > mx) mx = w.year;
    }
    return [mn, mx];
  }

  // ---- get_or_create ------------------------------------------------------
  getOrCreateVenue(name, vtype, issn, publisher) {
    if (!name) return null;
    const hit = this._venuesByName.get(name);
    if (hit) return hit;
    const obj = { id: ++this._seq.venues, name, type: vtype ?? null, issn: issn ?? null, publisher: publisher ?? null };
    this.venues.push(obj);
    this._byId.venues.set(obj.id, obj);
    this._venuesByName.set(name, obj);
    return obj;
  }

  getOrCreateAuthor(displayName, normalizedName = null, orcid = null) {
    const n = norm(normalizedName || displayName);
    const hit = this._authorsByNorm.get(n);
    if (hit) return hit;
    const obj = { id: ++this._seq.authors, display_name: displayName, normalized_name: n, orcid: orcid ?? null };
    this.authors.push(obj);
    this._byId.authors.set(obj.id, obj);
    this._authorsByNorm.set(n, obj);
    return obj;
  }

  getOrCreateKeyword(term, display = null, vocab = null) {
    const n = norm(term);
    const hit = this._keywordsByNorm.get(n);
    if (hit) return hit;
    const obj = { id: ++this._seq.keywords, term_norm: n, term_display: display || term, vocabulary: vocab ?? null };
    this.keywords.push(obj);
    this._byId.keywords.set(obj.id, obj);
    this._keywordsByNorm.set(n, obj);
    return obj;
  }

  getOrCreateOrg(name, country = null, city = null) {
    const hit = this._orgsByName.get(name);
    if (hit) return hit;
    const obj = { id: ++this._seq.organizations, name, country_code: country ?? null, city: city ?? null };
    this.organizations.push(obj);
    this._byId.organizations.set(obj.id, obj);
    this._orgsByName.set(name, obj);
    return obj;
  }

  // ---- relations ----------------------------------------------------------
  addWorkAuthor(workId, authorId, position = 0, corresponding = false) {
    let rows = this.workAuthors.get(workId);
    if (!rows) { rows = []; this.workAuthors.set(workId, rows); }
    // composite PK (work_id, author_id): SQLAlchemy would raise on duplicate;
    // we keep the first occurrence (same visible outcome for edge counts).
    if (rows.some((r) => r.author_id === authorId)) return;
    rows.push({ work_id: workId, author_id: authorId, position, corresponding });
  }

  addWorkAffiliation({ work_id, author_id = null, org_id = null, org_label_raw = null, year = null, country_code = null }) {
    let rows = this.workAffiliations.get(work_id);
    if (!rows) { rows = []; this.workAffiliations.set(work_id, rows); }
    rows.push({ id: ++this._seq.affiliations, work_id, author_id, org_id, org_label_raw, year, country_code });
  }

  addWorkKeyword(workId, keywordId, weight = 1.0, extractor = null) {
    let rows = this.workKeywords.get(workId);
    if (!rows) { rows = []; this.workKeywords.set(workId, rows); }
    if (rows.some((r) => r.keyword_id === keywordId)) return;
    rows.push({ work_id: workId, keyword_id: keywordId, weight, extractor });
  }

  clearWorkRelations(workId) {
    this.workAuthors.delete(workId);
    this.workAffiliations.delete(workId);
    this.workKeywords.delete(workId);
  }

  // ---- upsert_work_from_openalex -----------------------------------------
  upsertWorkFromOpenAlex(w) {
    const doi = w.doi ? String(w.doi).toLowerCase() : null;
    const sourceUid = w.id || null;
    const title = w.title || "(untitled)";

    let abstract = null;
    if (typeof w.abstract === "string") {
      abstract = w.abstract;
    } else if ("abstract_inverted_index" in w) {
      const inv = w.abstract_inverted_index || {};
      const tokens = [];
      for (const [word, poss] of Object.entries(inv)) for (const pos of poss) tokens.push([pos, word]);
      tokens.sort((a, b) => a[0] - b[0]);
      abstract = tokens.length ? tokens.map((t) => t[1]).join(" ") : null;
    }

    let year = null;
    if (w.publication_year) year = parseInt(w.publication_year, 10);

    let venueName = null, venueType = null, issn = null, publisher = null;
    if (w.host_venue) {
      const hv = w.host_venue;
      venueName = hv.display_name ?? null;
      issn = Array.isArray(hv.issn) ? (hv.issn.length ? hv.issn[0] : null) : (hv.issn ?? null);
      venueType = hv.type ?? null;
      publisher = hv.publisher ?? null;
    }
    // Newer OpenAlex payloads carry the venue under primary_location.source;
    // host_venue was removed from the API in 2023. Fall back so venues still
    // populate for fresh ingests (the Streamlit app silently lost them).
    if (!venueName && w.primary_location && w.primary_location.source) {
      const src = w.primary_location.source;
      venueName = src.display_name ?? null;
      issn = src.issn_l ?? (Array.isArray(src.issn) ? src.issn[0] : null) ?? null;
      venueType = src.type ?? null;
      publisher = src.host_organization_name ?? null;
    }
    const venue = venueName ? this.getOrCreateVenue(venueName, venueType, issn, publisher) : null;

    let url = null;
    const pl = w.primary_location || {};
    if (pl && typeof pl === "object") {
      const src = pl.source || {};
      if (src && typeof src === "object") url = src.url ?? null;
      if (!url) url = pl.landing_page_url ?? null;
    }
    if (!url) {
      const boa = w.best_oa_location || {};
      if (boa && typeof boa === "object") url = boa.url ?? boa.landing_page_url ?? null;
    }

    let existing = null;
    if (doi) existing = this._worksByDoi.get(doi) || null;
    if (!existing && sourceUid) {
      const cand = this._worksBySourceUid.get(sourceUid);
      if (cand && cand.source === "OpenAlex") existing = cand;
    }

    const rawJson = trimRawJson(w);
    let work;
    if (existing) {
      work = existing;
      Object.assign(work, {
        title, abstract, year, venue_id: venue ? venue.id : null, url,
        type: w.type ?? null, language: w.language ?? null, raw_json: rawJson,
      });
      this.clearWorkRelations(work.id);
    } else {
      work = {
        id: ++this._seq.works, doi, source_uid: sourceUid, title, abstract, year,
        venue_id: venue ? venue.id : null, url, type: w.type ?? null, language: w.language ?? null,
        source: "OpenAlex", raw_json: rawJson,
      };
      this.works.push(work);
      this._byId.works.set(work.id, work);
      if (doi) this._worksByDoi.set(doi, work);
      if (sourceUid) this._worksBySourceUid.set(sourceUid, work);
    }

    (w.authorships || []).forEach((auth, idx) => {
      const a = auth.author || {};
      const aDisplay = a.display_name || "Unknown";
      const aOrcid = a.orcid ?? null;
      const author = this.getOrCreateAuthor(aDisplay, null, aOrcid);
      this.addWorkAuthor(work.id, author.id, idx, false);
      const insts = auth.institutions || [];
      for (const inst of insts) {
        const orgName = inst.display_name ?? null;
        const country = inst.country_code || "";
        const org = orgName ? this.getOrCreateOrg(orgName, country) : null;
        this.addWorkAffiliation({
          work_id: work.id, author_id: author.id, org_id: org ? org.id : null,
          org_label_raw: orgName, year, country_code: country || null,
        });
      }
    });

    for (const c of (w.concepts || [])) {
      const kw = this.getOrCreateKeyword(c.display_name || "", c.display_name ?? null, "openalex_concept");
      this.addWorkKeyword(work.id, kw.id, parseFloat(c.score ?? 1.0) || 1.0, "openalex");
    }
    this.version++;
    return work;
  }

  // ---- edge recomputation --------------------------------------------------
  recomputeCoauthorEdges() {
    const pairs = new Map();
    for (const w of this.works) {
      const ids = [...new Set(this.authorsOfWork(w.id).map((r) => r.author_id))].sort((a, b) => a - b);
      for (let i = 0; i < ids.length; i++) {
        for (let j = i + 1; j < ids.length; j++) {
          const key = ids[i] + "|" + ids[j];
          pairs.set(key, (pairs.get(key) || 0) + 1);
        }
      }
    }
    this.coauthorEdges = [];
    for (const [key, w] of pairs) {
      const [a, b] = key.split("|").map(Number);
      this.coauthorEdges.push({ a_id: a, b_id: b, weight: w, evidence_count: w });
    }
    this.version++;
  }

  recomputeOrgEdges() {
    const pairs = new Map();
    for (const w of this.works) {
      const orgs = [...new Set(this.affiliationsOfWork(w.id).map((r) => r.org_id).filter((o) => o))].sort((a, b) => a - b);
      for (let i = 0; i < orgs.length; i++) {
        for (let j = i + 1; j < orgs.length; j++) {
          const key = orgs[i] + "|" + orgs[j];
          pairs.set(key, (pairs.get(key) || 0) + 1);
        }
      }
    }
    this.orgEdges = [];
    for (const [key, w] of pairs) {
      const [o1, o2] = key.split("|").map(Number);
      this.orgEdges.push({ org1_id: o1, org2_id: o2, weight: w });
    }
    this.version++;
  }

  recomputeNationEdges() {
    const pairs = new Map();
    for (const w of this.works) {
      const nations = [...new Set(this.affiliationsOfWork(w.id).map((r) => r.country_code).filter((n) => n))].sort();
      for (let i = 0; i < nations.length; i++) {
        for (let j = i + 1; j < nations.length; j++) {
          const key = nations[i] + "|" + nations[j];
          pairs.set(key, (pairs.get(key) || 0) + 1);
        }
      }
    }
    this.nationEdges = [];
    for (const [key, w] of pairs) {
      const [n1, n2] = key.split("|");
      this.nationEdges.push({ n1, n2, weight: w });
    }
    this.version++;
  }

  recomputeAllEdges() {
    this.recomputeCoauthorEdges();
    this.recomputeNationEdges();
    this.recomputeOrgEdges();
  }

  // ---- (de)serialisation for IndexedDB ------------------------------------
  toJSON() {
    return {
      schema: 1,
      seq: { ...this._seq },
      works: this.works,
      authors: this.authors,
      organizations: this.organizations,
      venues: this.venues,
      keywords: this.keywords,
      work_authors: [...this.allWorkAuthors()],
      work_affiliations: [...this.allWorkAffiliations()],
      work_keywords: [...this.allWorkKeywords()],
      coauthor_edges: this.coauthorEdges,
      org_edges: this.orgEdges,
      nation_edges: this.nationEdges,
    };
  }

  static fromJSON(data) {
    const s = new Store();
    if (!data || data.schema !== 1) return s;
    for (const w of data.works || []) {
      s.works.push(w); s._byId.works.set(w.id, w);
      if (w.doi) s._worksByDoi.set(w.doi, w);
      if (w.source_uid) s._worksBySourceUid.set(w.source_uid, w);
    }
    for (const a of data.authors || []) { s.authors.push(a); s._byId.authors.set(a.id, a); s._authorsByNorm.set(a.normalized_name, a); }
    for (const o of data.organizations || []) { s.organizations.push(o); s._byId.organizations.set(o.id, o); s._orgsByName.set(o.name, o); }
    for (const v of data.venues || []) { s.venues.push(v); s._byId.venues.set(v.id, v); s._venuesByName.set(v.name, v); }
    for (const k of data.keywords || []) { s.keywords.push(k); s._byId.keywords.set(k.id, k); s._keywordsByNorm.set(k.term_norm, k); }
    for (const r of data.work_authors || []) s.addWorkAuthor(r.work_id, r.author_id, r.position, r.corresponding);
    for (const r of data.work_affiliations || []) {
      let rows = s.workAffiliations.get(r.work_id);
      if (!rows) { rows = []; s.workAffiliations.set(r.work_id, rows); }
      rows.push({ ...r });
    }
    for (const r of data.work_keywords || []) s.addWorkKeyword(r.work_id, r.keyword_id, r.weight, r.extractor);
    s.coauthorEdges = data.coauthor_edges || [];
    s.orgEdges = data.org_edges || [];
    s.nationEdges = data.nation_edges || [];
    s._seq = { ...s._seq, ...(data.seq || {}) };
    // Defensive: make sure sequences are never behind the max id present.
    const maxId = (arr) => arr.reduce((m, x) => Math.max(m, x.id || 0), 0);
    s._seq.works = Math.max(s._seq.works, maxId(s.works));
    s._seq.authors = Math.max(s._seq.authors, maxId(s.authors));
    s._seq.organizations = Math.max(s._seq.organizations, maxId(s.organizations));
    s._seq.venues = Math.max(s._seq.venues, maxId(s.venues));
    s._seq.keywords = Math.max(s._seq.keywords, maxId(s.keywords));
    s._seq.affiliations = Math.max(s._seq.affiliations, maxId([...s.allWorkAffiliations()]));
    return s;
  }
}

/** Keep the fields the app reads back (cited_by_count etc.), drop the bulky inverted index. */
function trimRawJson(w) {
  if (!w || typeof w !== "object") return null;
  const { abstract_inverted_index, ...rest } = w; // eslint-disable-line no-unused-vars
  return rest;
}
