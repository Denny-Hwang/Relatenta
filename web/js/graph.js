/**
 * build_graph port — app/services_graph.py.
 * Returns {nodes:[{id,label,type,focus,...}], edges:[{source,target,weight}]}
 * with the same id prefixes (A/K/O/N) as the Python service.
 */

function yearOk(y, yMin, yMax) {
  if (yMin != null && (y == null || y < yMin)) return false;
  if (yMax != null && (y == null || y > yMax)) return false;
  return true;
}

export function buildGraph(store, layer, yearMin = null, yearMax = null, edgeMinWeight = 0.0, focusIds = null, focusOnly = false) {
  const nodes = [], edges = [];
  const focus = focusIds && focusIds.length ? focusIds : null;
  const focusSet = new Set(focus || []);

  const worksInRange = store.works.filter((w) => yearOk(w.year, yearMin, yearMax));

  if (layer === "authors") {
    let authorIds = new Set();
    const authorsInRange = () => {
      const s = new Set();
      for (const w of worksInRange) for (const r of store.authorsOfWork(w.id)) s.add(r.author_id);
      return s;
    };
    if (focus) {
      const valid = focus.filter((id) => store.getAuthor(id));
      if (!valid.length) return { nodes: [], edges: [] };
      if (focusOnly) {
        valid.forEach((id) => authorIds.add(id));
        for (const e of store.coauthorEdges) {
          if (e.weight < edgeMinWeight) continue;
          if (valid.includes(e.a_id)) authorIds.add(e.b_id);
          if (valid.includes(e.b_id)) authorIds.add(e.a_id);
        }
        if (yearMin != null || yearMax != null) {
          const inRange = authorsInRange();
          const filtered = new Set([...authorIds].filter((id) => inRange.has(id)));
          valid.forEach((id) => filtered.add(id));
          authorIds = filtered;
        }
      } else {
        authorIds = authorsInRange();
        valid.forEach((id) => authorIds.add(id));
      }
    } else {
      authorIds = authorsInRange();
    }
    const added = new Set();
    for (const aId of authorIds) {
      const a = store.getAuthor(aId);
      if (!a) continue;
      const isFocus = focusSet.has(aId);
      nodes.push({ id: "A" + a.id, label: a.display_name, type: isFocus ? "focus_author" : "author", focus: isFocus });
      added.add(a.id);
    }
    for (const e of store.coauthorEdges) {
      if (e.weight >= edgeMinWeight && added.has(e.a_id) && added.has(e.b_id)) {
        edges.push({ source: "A" + e.a_id, target: "A" + e.b_id, weight: e.weight });
      }
    }
  } else if (layer === "keywords") {
    const kwCounts = new Map();
    const edgesMap = new Map();
    let addedKw = new Set();
    const workToKws = [];
    for (const w of worksInRange) {
      const s = new Set(store.keywordsOfWork(w.id).map((r) => r.keyword_id));
      if (s.size) workToKws.push(s);
    }
    const tally = (kwsSet, addNodes) => {
      const sorted = [...kwsSet].sort((a, b) => a - b);
      for (const k of sorted) {
        kwCounts.set(k, (kwCounts.get(k) || 0) + 1);
        if (addNodes) addedKw.add(k);
      }
      for (let i = 0; i < sorted.length; i++) for (let j = i + 1; j < sorted.length; j++) {
        const key = sorted[i] + "|" + sorted[j];
        edgesMap.set(key, (edgesMap.get(key) || 0) + 1);
      }
    };
    if (focus) {
      const valid = focus.filter((id) => store.getKeyword(id));
      if (!valid.length) return { nodes: [], edges: [] };
      if (focusOnly) {
        const related = new Set(valid);
        for (const s of workToKws) {
          if (valid.some((f) => s.has(f))) {
            s.forEach((k) => related.add(k));
            tally(s, false);
          }
        }
        addedKw = related;
      } else {
        for (const s of workToKws) tally(s, true);
      }
    } else {
      for (const s of workToKws) tally(s, true);
    }
    for (const kid of addedKw) {
      const k = store.getKeyword(kid);
      if (!k) continue;
      const isFocus = focusSet.has(kid);
      nodes.push({ id: "K" + kid, label: k.term_display, type: isFocus ? "focus_keyword" : "keyword", count: kwCounts.get(kid) || 0, focus: isFocus });
    }
    for (const [key, w] of edgesMap) {
      const [k1, k2] = key.split("|").map(Number);
      if (w >= edgeMinWeight && addedKw.has(k1) && addedKw.has(k2)) {
        edges.push({ source: "K" + k1, target: "K" + k2, weight: w });
      }
    }
  } else if (layer === "orgs") {
    let orgIds = new Set();
    const orgsInRange = () => {
      const s = new Set();
      for (const w of worksInRange) for (const r of store.affiliationsOfWork(w.id)) if (r.org_id) s.add(r.org_id);
      return s;
    };
    if (focus) {
      const valid = focus.filter((id) => store.getOrg(id));
      if (!valid.length) return { nodes: [], edges: [] };
      if (focusOnly) {
        orgIds = new Set(valid);
        for (const e of store.orgEdges) {
          if (e.weight < edgeMinWeight) continue;
          if (valid.includes(e.org1_id)) orgIds.add(e.org2_id);
          if (valid.includes(e.org2_id)) orgIds.add(e.org1_id);
        }
      } else {
        orgIds = orgsInRange();
        valid.forEach((id) => orgIds.add(id));
      }
    } else {
      orgIds = orgsInRange();
    }
    const added = new Set();
    for (const oid of [...orgIds].sort((a, b) => a - b)) {
      const org = store.getOrg(oid);
      if (!org) continue;
      const isFocus = focusSet.has(oid);
      nodes.push({ id: "O" + oid, label: org.name, type: isFocus ? "focus_org" : "org", country: org.country_code, focus: isFocus });
      added.add(oid);
    }
    for (const e of store.orgEdges) {
      if (e.weight >= edgeMinWeight && added.has(e.org1_id) && added.has(e.org2_id)) {
        edges.push({ source: "O" + e.org1_id, target: "O" + e.org2_id, weight: e.weight });
      }
    }
  } else if (layer === "nations") {
    let nations;
    const nationsInRange = () => {
      const s = new Set();
      for (const w of worksInRange) for (const r of store.affiliationsOfWork(w.id)) if (r.country_code) s.add(r.country_code);
      return s;
    };
    const focusCodes = (focus || []).filter((f) => typeof f === "string" && f.length === 2).map((f) => f.toUpperCase());
    if (focus) {
      if (!focusCodes.length) return { nodes: [], edges: [] };
      if (focusOnly) {
        nations = new Set(focusCodes);
        for (const e of store.nationEdges) {
          if (e.weight < edgeMinWeight) continue;
          if (focusCodes.includes(e.n1)) nations.add(e.n2);
          if (focusCodes.includes(e.n2)) nations.add(e.n1);
        }
      } else {
        nations = nationsInRange();
        focusCodes.forEach((c) => nations.add(c));
      }
    } else {
      nations = nationsInRange();
    }
    const focusStr = new Set((focus || []).filter((f) => typeof f === "string"));
    for (const n of [...nations].sort()) {
      const isFocus = focusStr.has(n);
      nodes.push({ id: "N" + n, label: n, type: isFocus ? "focus_nation" : "nation", focus: isFocus });
    }
    for (const e of store.nationEdges) {
      if (e.weight >= edgeMinWeight && nations.has(e.n1) && nations.has(e.n2)) {
        edges.push({ source: "N" + e.n1, target: "N" + e.n2, weight: e.weight });
      }
    }
  } else {
    return { nodes: [], edges: [] };
  }
  return { nodes, edges };
}

/** Port of _color_graph_by_community: tags nodes with community_<id> type. */
export function colorGraphByCommunity(graphJson, partition, layer) {
  const prefix = { authors: "A", keywords: "K", orgs: "O", nations: "N" }[layer] || "";
  for (const node of graphJson.nodes) {
    let key = node.id;
    if (prefix && key.startsWith(prefix)) {
      const rest = key.slice(prefix.length);
      const asInt = parseInt(rest, 10);
      key = String(asInt) === rest ? asInt : rest;
    }
    const comm = partition.has ? (partition.get(key) ?? 0) : (partition[key] ?? 0);
    node.community = comm;
    node.type = "community_" + comm;
  }
  return graphJson;
}
