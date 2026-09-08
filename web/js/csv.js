/** Minimal RFC 4180 CSV parser / serializer (pandas-compatible output). */

export function parseCsv(text) {
  const rows = [];
  let row = [], field = "", i = 0, inQuotes = false;
  if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);
  const n = text.length;
  while (i < n) {
    const ch = text[i];
    if (inQuotes) {
      if (ch === '"') {
        if (text[i + 1] === '"') { field += '"'; i += 2; continue; }
        inQuotes = false; i++; continue;
      }
      field += ch; i++; continue;
    }
    if (ch === '"') { inQuotes = true; i++; continue; }
    if (ch === ",") { row.push(field); field = ""; i++; continue; }
    if (ch === "\r") { i++; continue; }
    if (ch === "\n") { row.push(field); rows.push(row); row = []; field = ""; i++; continue; }
    field += ch; i++;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  if (!rows.length) return [];
  const header = rows[0];
  const out = [];
  for (let r = 1; r < rows.length; r++) {
    const vals = rows[r];
    if (vals.length === 1 && vals[0] === "") continue; // blank line
    const obj = {};
    header.forEach((h, idx) => { obj[h] = vals[idx] ?? ""; });
    out.push(obj);
  }
  return out;
}

function esc(v) {
  if (v === null || v === undefined) return "";
  if (typeof v === "boolean") return v ? "True" : "False";
  const s = String(v);
  return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
}

export function toCsv(rows, columns = null) {
  if (!rows.length) return "\n";
  const cols = columns || Object.keys(rows[0]);
  const lines = [cols.map(esc).join(",")];
  for (const r of rows) lines.push(cols.map((c) => esc(r[c])).join(","));
  return lines.join("\n") + "\n";
}

/** pandas-style helpers: empty string == NaN. */
export const isNa = (v) => v === undefined || v === null || v === "" || (typeof v === "number" && Number.isNaN(v));
export const toInt = (v) => { const x = parseInt(v, 10); return Number.isNaN(x) ? null : x; };
