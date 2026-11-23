// Small UI toolkit: escaped HTML templates, icons, toasts, sheets and confirmations.
// Every value put into a template is escaped unless it comes from html`` or raw() (no HTML injection from data).

class Raw { constructor(s) { this.s = s; } toString() { return this.s; } }
export const raw = (s) => new Raw(String(s));

const ESC = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
export const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ESC[c]);

function flat(v) {
  if (v === null || v === undefined || v === false) return "";
  if (v instanceof Raw) return v.s;
  if (Array.isArray(v)) return v.map(flat).join("");
  return esc(v);
}

export function html(strings, ...vals) {
  let out = strings[0];
  vals.forEach((v, i) => { out += flat(v) + strings[i + 1]; });
  return new Raw(out);
}

export const icon = (name, cls = "") => raw(`<svg class="ic ${cls}" aria-hidden="true"><use href="/static/common/icons.svg#i-${name}"/></svg>`);

export function set(el, tpl) { el.innerHTML = flat(tpl); }

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

/** Delegated events: on(root, "click", "[data-act]", (el, ev) => …). */
export function on(root, type, sel, fn) {
  root.addEventListener(type, (ev) => {
    const el = ev.target.closest(sel);
    if (el && root.contains(el)) fn(el, ev);
  });
}

// ---------- toast ----------
export function toast(msg, { action, onAction, error = false, ms = 4200 } = {}) {
  const box = document.getElementById("toast");
  const t = document.createElement("div");
  t.className = "t" + (error ? " err" : "");
  t.innerHTML = flat(html`<span>${msg}</span>${action ? html`<button type="button">${action}</button>` : ""}`);
  if (action) t.querySelector("button").addEventListener("click", () => { t.remove(); onAction && onAction(); });
  box.appendChild(t);
  setTimeout(() => t.remove(), ms);
}

// ---------- sheets ----------
let sheetStack = [];

/** Open a sheet (bottom sheet on phones, dialog on wide screens). Returns { el, close }. */
export function sheet(title, body, { onClose, wide = false } = {}) {
  const root = document.getElementById("sheet-root");
  const scrim = document.createElement("div");
  scrim.className = "scrim";
  const el = document.createElement("section");
  el.className = "sheet";
  el.setAttribute("role", "dialog");
  el.setAttribute("aria-modal", "true");
  el.setAttribute("aria-label", title);
  if (wide) el.style.width = "min(720px, calc(100vw - 40px))";
  el.innerHTML = flat(html`<span class="grab" aria-hidden="true"></span>
    <div class="sh-head"><h2>${title}</h2><button class="icon-btn ghost" type="button" data-close aria-label="Cerrar">${icon("x")}</button></div>
    <div class="sh-body" style="display:grid;gap:14px">${body}</div>`);
  root.append(scrim, el);
  const prevFocus = document.activeElement;
  const close = () => {
    scrim.remove(); el.remove();
    sheetStack = sheetStack.filter((s) => s.el !== el);
    document.body.style.overflow = sheetStack.length ? "hidden" : "";
    if (prevFocus && prevFocus.focus) prevFocus.focus({ preventScroll: true });
    onClose && onClose();
  };
  scrim.addEventListener("click", close);
  el.querySelector("[data-close]").addEventListener("click", close);
  el.addEventListener("keydown", (e) => { if (e.key === "Escape") { e.stopPropagation(); close(); } });
  sheetStack.push({ el, close });
  document.body.style.overflow = "hidden";
  setTimeout(() => { const f = el.querySelector("[autofocus], input, textarea, select"); (f || el).focus({ preventScroll: true }); }, 30);
  return { el, close, body: el.querySelector(".sh-body") };
}

/** Close the top sheet; true if there was one (the Android back button asks this first). */
export function closeTopSheet() {
  const s = sheetStack[sheetStack.length - 1];
  if (!s) return false;
  s.close();
  return true;
}

export function closeAllSheets() { while (closeTopSheet()) { /* empty */ } }

/** A confirmation built into the page (no browser dialogs). Resolves true/false. */
export function confirmSheet(title, text, { yes = "Sí", no = "Cancelar", danger = false } = {}) {
  return new Promise((resolve) => {
    let answered = false;
    const s = sheet(title, html`<p style="margin:0">${text}</p>
      <div class="btns"><button class="btn ${danger ? "danger" : "pri"}" type="button" data-yes>${yes}</button>
      <button class="btn" type="button" data-no>${no}</button></div>`, { onClose: () => { if (!answered) resolve(false); } });
    s.el.querySelector("[data-yes]").addEventListener("click", () => { answered = true; s.close(); resolve(true); });
    s.el.querySelector("[data-no]").addEventListener("click", () => { answered = true; s.close(); resolve(false); });
  });
}

/** Initials for an avatar. */
export function initials(name) {
  const p = String(name || "?").trim().split(/\s+/);
  return (p.length > 1 ? p[0][0] + p[1][0] : p[0].slice(0, 2)).toUpperCase();
}

export const avatar = (m, cls = "") => m
  ? html`<span class="av ${cls} m${String(m.color || "c8").slice(1)}" title="${m.name}">${initials(m.name)}</span>`
  : "";

export const mclass = (m) => (m ? "m" + String(m.color || "c8").slice(1) : "m8");

/** Read a form's fields as an object (by name). */
export function formData(form) {
  const out = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "checkbox") {
      if (el.dataset.multi !== undefined) { (out[el.name] ||= []); if (el.checked) out[el.name].push(el.value); }
      else out[el.name] = el.checked;
    } else if (el.type === "radio") { if (el.checked) out[el.name] = el.value; }
    else out[el.name] = el.value;
  }
  return out;
}
