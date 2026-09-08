/**
 * IndexedDB persistence. The Streamlit app is in-memory only; here the
 * dataset survives a refresh, which removes the "export before you close
 * the tab" anxiety. ZIP export/restore is still available for sharing.
 */
const DB_NAME = "relatenta";
const STORE = "kv";

function open() {
  return new Promise((resolve, reject) => {
    if (typeof indexedDB === "undefined") return reject(new Error("IndexedDB unavailable"));
    const req = indexedDB.open(DB_NAME, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE);
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function withStore(mode, fn) {
  const db = await open();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      const os = tx.objectStore(STORE);
      const req = fn(os);
      tx.oncomplete = () => resolve(req && req.result);
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}

export async function saveSnapshot(key, value) {
  try { await withStore("readwrite", (os) => os.put(value, key)); return true; }
  catch (e) { console.warn("persist: save failed", e); return false; }
}

export async function loadSnapshot(key) {
  try { return await withStore("readonly", (os) => os.get(key)); }
  catch (e) { console.warn("persist: load failed", e); return undefined; }
}

export async function clearSnapshot(key) {
  try { await withStore("readwrite", (os) => os.delete(key)); } catch (e) { /* ignore */ }
}

/** Debounced saver so rapid mutations coalesce into one write. */
export function makeAutosave(key, getValue, delay = 800) {
  let timer = null;
  return () => {
    if (timer) clearTimeout(timer);
    timer = setTimeout(() => { timer = null; saveSnapshot(key, getValue()); }, delay);
  };
}
