/**
 * CSV import, ZIP export and ZIP restore — port of app/services_export.py
 * and the _import_csv / _restore_from_zip helpers in streamlit_app.py.
 *
 * File layout and column names are identical, so a ZIP exported here can be
 * restored by the Streamlit app and vice versa.
 */
import { parseCsv, toCsv, isNa, toInt } from "./csv.js";

const truncate = (s, n) => (s == null ? null : String(s).slice(0, n));

export function buildExportFiles(store) {
  const files = {};
  const works = store.works;
  if (works.length) {
    files["works.csv"] = toCsv(works.map((w) => {
      const venue = w.venue_id ? store.getVenue(w.venue_id) : null;
      return {
        id: w.id, doi: w.doi, source_uid: w.source_uid, title: w.title,
        abstract: truncate(w.abstract, 500), year: w.year,
        venue: venue ? venue.name : null, venue_type: venue ? venue.type : null,
        url: w.url, type: w.type, language: w.language, source: w.source,
      };
    }));
  }
  if (store.authors.length) {
    files["authors.csv"] = toCsv(store.authors.map((a) => ({
      id: a.id, display_name: a.display_name, normalized_name: a.normalized_name, orcid: a.orcid,
    })));
  }
  const wa = [];
  for (const r of store.allWorkAuthors()) {
    const work = store.getWork(r.work_id), author = store.getAuthor(r.author_id);
    if (work && author) wa.push({
      work_id: r.work_id, work_title: truncate(work.title, 100), work_doi: work.doi,
      author_id: r.author_id, author_name: author.display_name, position: r.position, corresponding: r.corresponding,
    });
  }
  if (wa.length) files["work_authors.csv"] = toCsv(wa);
  if (store.organizations.length) {
    files["organizations.csv"] = toCsv(store.organizations.map((o) => ({
      id: o.id, name: o.name, country_code: o.country_code, city: o.city,
    })));
  }
  const affs = [];
  for (const aff of store.allWorkAffiliations()) {
    const work = store.getWork(aff.work_id);
    if (!work) continue;
    const author = aff.author_id ? store.getAuthor(aff.author_id) : null;
    const org = aff.org_id ? store.getOrg(aff.org_id) : null;
    affs.push({
      work_id: aff.work_id, work_title: truncate(work.title, 100), work_doi: work.doi,
      author_id: aff.author_id, author_name: author ? author.display_name : null,
      org_id: aff.org_id, org_name: org ? org.name : aff.org_label_raw,
      country_code: aff.country_code, year: aff.year,
    });
  }
  if (affs.length) files["affiliations.csv"] = toCsv(affs);
  if (store.keywords.length) {
    files["keywords.csv"] = toCsv(store.keywords.map((k) => ({
      id: k.id, term_norm: k.term_norm, term_display: k.term_display, vocabulary: k.vocabulary,
    })));
  }
  const wk = [];
  for (const r of store.allWorkKeywords()) {
    const work = store.getWork(r.work_id), kw = store.getKeyword(r.keyword_id);
    if (work && kw) wk.push({
      work_id: r.work_id, work_title: truncate(work.title, 100), keyword_id: r.keyword_id,
      keyword: kw.term_display, weight: r.weight, extractor: r.extractor,
    });
  }
  if (wk.length) files["work_keywords.csv"] = toCsv(wk);
  if (store.venues.length) {
    files["venues.csv"] = toCsv(store.venues.map((v) => ({
      id: v.id, name: v.name, type: v.type, issn: v.issn, publisher: v.publisher,
    })));
  }
  files["metadata.csv"] = toCsv([{
    export_date: new Date().toISOString(),
    total_works: works.length, total_authors: store.authors.length,
    total_organizations: store.organizations.length, total_keywords: store.keywords.length,
    total_venues: store.venues.length,
  }]);
  return files;
}

/** @returns {Promise<Blob>} */
export async function exportZip(store, JSZip) {
  const zip = new JSZip();
  for (const [name, text] of Object.entries(buildExportFiles(store))) zip.file(name, text);
  return zip.generateAsync({ type: "blob", compression: "DEFLATE" });
}

// ---- CSV import ------------------------------------------------------------

function findWork(store, r) {
  let work = null;
  if (!isNa(r.work_doi)) work = store.findWorkByDoi(String(r.work_doi).toLowerCase());
  if (!work && !isNa(r.work_title)) work = store.findWorkByTitle(String(r.work_title));
  return work;
}

/** Port of _import_csv(db, kind, df). `rows` are objects from parseCsv. */
export function importCsv(store, kind, rows) {
  if (kind === "works") {
    for (const r of rows) {
      const w = {
        id: r.source_uid || r.doi || "",
        doi: isNa(r.doi) ? null : r.doi,
        title: r.title,
        publication_year: isNa(r.year) ? null : toInt(r.year),
        host_venue: { display_name: isNa(r.venue) ? null : r.venue },
        type: isNa(r.type) ? null : r.type,
        language: isNa(r.language) ? null : r.language,
        authorships: [],
        concepts: String(r.keywords || "").split(";").map((t) => t.trim()).filter(Boolean)
          .map((t) => ({ display_name: t, score: 1.0 })),
      };
      store.upsertWorkFromOpenAlex(w);
    }
  } else if (kind === "authors") {
    for (const r of rows) {
      const work = findWork(store, r);
      if (!work) continue;
      const a = store.getOrCreateAuthor(isNa(r.author_name) ? "Unknown" : r.author_name);
      store.addWorkAuthor(work.id, a.id, toInt(r.position) || 0);
    }
  } else if (kind === "affiliations") {
    for (const r of rows) {
      const work = findWork(store, r);
      if (!work) continue;
      const a = store.getOrCreateAuthor(isNa(r.author_name) ? "Unknown" : r.author_name);
      const cc = String(r.country_code || "").toUpperCase() || null;
      const org = store.getOrCreateOrg(isNa(r.org_name) ? "Unknown" : r.org_name, cc);
      store.addWorkAffiliation({
        work_id: work.id, author_id: a.id, org_id: org.id, org_label_raw: org.name,
        year: work.year, country_code: org.country_code,
      });
    }
  } else if (kind === "keywords") {
    for (const r of rows) {
      const work = findWork(store, r);
      if (!work) continue;
      const kw = store.getOrCreateKeyword(String(r.term ?? "").trim());
      store.addWorkKeyword(work.id, kw.id, 1.0, "manual");
    }
  }
  store.version++;
}

/** Port of _restore_from_zip. Resets the store, then loads the CSVs. */
export async function restoreFromZip(store, zipData, JSZip) {
  const zip = await JSZip.loadAsync(zipData);
  const names = Object.keys(zip.files);
  const read = async (n) => parseCsv(await zip.file(n).async("string"));
  store.reset();

  const worksFile = names.find((n) => n.endsWith("works.csv") && !n.includes("work_"));
  if (worksFile) {
    for (const r of await read(worksFile)) {
      store.upsertWorkFromOpenAlex({
        id: r.source_uid || r.doi || "",
        doi: isNa(r.doi) ? null : r.doi,
        title: r.title,
        publication_year: isNa(r.year) ? null : toInt(r.year),
        host_venue: { display_name: isNa(r.venue) ? null : r.venue },
        type: isNa(r.type) ? null : r.type,
        language: isNa(r.language) ? null : r.language,
        authorships: [], concepts: [],
      });
    }
  }
  const waFile = names.find((n) => n.includes("work_authors"));
  if (waFile) importCsv(store, "authors", await read(waFile));
  const affFile = names.find((n) => n.includes("affiliations"));
  if (affFile) importCsv(store, "affiliations", await read(affFile));
  const wkFile = names.find((n) => n.includes("work_keywords"));
  if (wkFile) {
    const rows = await read(wkFile);
    for (const r of rows) if ("keyword" in r && !("term" in r)) r.term = r.keyword;
    importCsv(store, "keywords", rows);
  }
  store.recomputeAllEdges();
  return store.stats();
}
