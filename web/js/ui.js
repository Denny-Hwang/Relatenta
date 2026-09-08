/** Tiny DOM helpers shared by the tabs. */

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k === "text") node.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2).toLowerCase(), v);
    else if (k === "style" && typeof v === "object") Object.assign(node.style, v);
    else if (k === "dataset") Object.assign(node.dataset, v);
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const c of children.flat()) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

export function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

export function fmt(n) { return typeof n === "number" ? n.toLocaleString() : String(n ?? ""); }

/** Toast notifications (info / success / warning / error). */
export function toast(message, kind = "info", ms = 4000) {
  let host = $("#toast-host");
  if (!host) { host = el("div", { id: "toast-host" }); document.body.append(host); }
  const node = el("div", { class: `toast toast-${kind}`, role: "status", html: message });
  host.append(node);
  requestAnimationFrame(() => node.classList.add("show"));
  const remove = () => { node.classList.remove("show"); setTimeout(() => node.remove(), 300); };
  if (ms > 0) setTimeout(remove, ms);
  node.addEventListener("click", remove);
  return node;
}

/** Inline alert box (like st.info / st.warning). */
export function alertBox(message, kind = "info") {
  return el("div", { class: `alert alert-${kind}`, html: message });
}

export function metric(label, value) {
  return el("div", { class: "metric" }, el("div", { class: "metric-value", text: fmt(value) }), el("div", { class: "metric-label", text: label }));
}

/** Simple data table from an array of objects. */
export function dataTable(rows, columns = null, { maxRows = 500 } = {}) {
  if (!rows.length) return el("p", { class: "muted", text: "No rows." });
  const cols = columns || Object.keys(rows[0]);
  const thead = el("thead", {}, el("tr", {}, ...cols.map((c) => el("th", { text: c }))));
  const tbody = el("tbody", {}, ...rows.slice(0, maxRows).map((r) => el("tr", {}, ...cols.map((c) => {
    const v = r[c];
    return el("td", { text: typeof v === "number" ? (Number.isInteger(v) ? String(v) : v.toFixed(3).replace(/\.?0+$/, "")) : String(v ?? "") });
  }))));
  return el("div", { class: "table-wrap" }, el("table", { class: "data-table" }, thead, tbody));
}

/** Modal confirm dialog returning a promise<boolean>. */
export function confirmDialog(message, { okText = "Confirm", cancelText = "Cancel", danger = true } = {}) {
  return new Promise((resolve) => {
    const overlay = el("div", { class: "modal-overlay" });
    const ok = el("button", { class: danger ? "btn btn-danger" : "btn btn-primary", text: okText });
    const cancel = el("button", { class: "btn", text: cancelText });
    const box = el("div", { class: "modal", role: "dialog", "aria-modal": "true" },
      el("p", { html: message }), el("div", { class: "modal-actions" }, cancel, ok));
    overlay.append(box);
    document.body.append(overlay);
    const done = (v) => { overlay.remove(); resolve(v); };
    ok.addEventListener("click", () => done(true));
    cancel.addEventListener("click", () => done(false));
    overlay.addEventListener("click", (e) => { if (e.target === overlay) done(false); });
    ok.focus();
  });
}

/** Busy overlay with a message, returns a handle with .update(msg) and .close(). */
export function busy(message) {
  const label = el("div", { class: "busy-label", text: message });
  const bar = el("div", { class: "busy-bar" }, el("div", { class: "busy-bar-fill" }));
  const overlay = el("div", { class: "busy-overlay" }, el("div", { class: "busy-box" }, el("div", { class: "spinner" }), label, bar));
  document.body.append(overlay);
  return {
    update(msg, fraction = null) {
      label.textContent = msg;
      const fill = bar.firstChild;
      if (fraction == null) { bar.hidden = true; } else { bar.hidden = false; fill.style.width = `${Math.round(fraction * 100)}%`; }
    },
    close() { overlay.remove(); },
  };
}

/** Save a Blob to the user's disk. */
export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = el("a", { href: url, download: filename });
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

/** Collapsible section (like st.expander). */
export function expander(title, content, open = false) {
  const d = el("details", { class: "expander", open: open || null }, el("summary", { text: title }));
  d.append(...(Array.isArray(content) ? content : [content]));
  return d;
}

/** Searchable multi-select: a text filter above a scrollable checkbox list. */
export function multiSelect(options, { placeholder = "Type to filter…", selected = new Set(), onChange = null, maxVisible = 200 } = {}) {
  const chosen = new Set(selected);
  const input = el("input", { type: "search", class: "input", placeholder });
  const list = el("div", { class: "ms-list" });
  const chips = el("div", { class: "ms-chips" });
  const render = () => {
    const q = input.value.trim().toLowerCase();
    list.replaceChildren();
    let shown = 0;
    for (const o of options) {
      if (q && !o.label.toLowerCase().includes(q)) continue;
      if (shown++ >= maxVisible) { list.append(el("div", { class: "muted small", text: `… ${options.length - maxVisible} more, refine your filter` })); break; }
      const cb = el("input", { type: "checkbox", checked: chosen.has(o.value) || null });
      cb.addEventListener("change", () => { if (cb.checked) chosen.add(o.value); else chosen.delete(o.value); renderChips(); onChange && onChange([...chosen]); });
      list.append(el("label", { class: "ms-item" }, cb, el("span", { text: o.label })));
    }
    if (!shown) list.append(el("div", { class: "muted small", text: "No matches." }));
  };
  const renderChips = () => {
    chips.replaceChildren(...[...chosen].map((v) => {
      const o = options.find((x) => x.value === v);
      const chip = el("span", { class: "chip" }, o ? o.label : String(v), el("button", { class: "chip-x", type: "button", "aria-label": "remove", text: "×" }));
      chip.lastChild.addEventListener("click", () => { chosen.delete(v); render(); renderChips(); onChange && onChange([...chosen]); });
      return chip;
    }));
  };
  input.addEventListener("input", render);
  render(); renderChips();
  const root = el("div", { class: "ms" }, input, chips, list);
  // Keep the option list open while the user interacts with it: mousedown on
  // the list must not steal focus from the filter input (which would hide the
  // list before the click lands).
  list.addEventListener("mousedown", (e) => { if (e.target.tagName !== "INPUT") e.preventDefault(); });
  input.addEventListener("focus", () => root.classList.add("open"));
  // Collapse a moment after focus leaves the widget (deferred so a click that
  // moves focus elsewhere completes before the layout shifts).
  root.addEventListener("focusout", () => setTimeout(() => { if (!root.contains(document.activeElement)) root.classList.remove("open"); }, 150));
  root.getSelected = () => [...chosen];
  root.clear = () => { chosen.clear(); render(); renderChips(); };
  return root;
}
