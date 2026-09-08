/** Shared application state + persistence glue (replaces st.session_state). */
import { Store } from "./store.js";
import { saveSnapshot, loadSnapshot, clearSnapshot } from "./persist.js";

const SNAPSHOT_KEY = "dataset";
const DEMO_FLAG = "relatenta.demoDismissed";

export const app = {
  store: new Store(),
  demoDismissed: false,
  builtGraph: null,
  builtGraphSettings: null,
  view: null,
  searchHits: [],
  reportData: null,
  listeners: new Map(),
};

try { app.demoDismissed = localStorage.getItem(DEMO_FLAG) === "1"; } catch (e) { /* ignore */ }

export function setDemoDismissed(v) {
  app.demoDismissed = v;
  try { localStorage.setItem(DEMO_FLAG, v ? "1" : "0"); } catch (e) { /* ignore */ }
}

export function on(evt, fn) {
  if (!app.listeners.has(evt)) app.listeners.set(evt, new Set());
  app.listeners.get(evt).add(fn);
  return () => app.listeners.get(evt).delete(fn);
}
export function emit(evt, payload) {
  for (const fn of app.listeners.get(evt) || []) { try { fn(payload); } catch (e) { console.error(e); } }
}

/** Persist the dataset to IndexedDB and notify listeners. */
export async function dataChanged({ persist = true } = {}) {
  app.builtGraph = null;
  app.builtGraphSettings = null;
  app.reportData = null;
  emit("data", app.store);
  if (persist) await saveSnapshot(SNAPSHOT_KEY, app.store.toJSON());
}

export async function loadPersisted() {
  const data = await loadSnapshot(SNAPSHOT_KEY);
  if (data && data.schema === 1 && (data.works || []).length) {
    app.store = Store.fromJSON(data);
    return true;
  }
  return false;
}

export async function clearAll() {
  app.store = new Store();
  app.searchHits = [];
  await clearSnapshot(SNAPSHOT_KEY);
  await dataChanged({ persist: false });
}

export function replaceStore(store) {
  app.store = store;
  return dataChanged();
}
