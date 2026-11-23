// Start-up of the app: the signed-in account, the family's data, the screens and the bridges (service worker,
// Android app, shared text and reminders done from a notification).
import * as S from "./store.js";
import { api } from "./api.js";
import { ctx, setMe } from "./ctx.js";
import { html, icon, closeTopSheet, closeAllSheets, toast } from "./ui.js";
import { openCapture } from "./capture.js";
import { completeTask } from "./editors.js";
import { initNotify, syncNativeAlarms } from "./notify.js";
import * as hoy from "./views/hoy.js";
import * as agenda from "./views/agenda.js";
import * as tareas from "./views/tareas.js";
import * as compras from "./views/compras.js";
import * as menu from "./views/menu.js";
import * as peques from "./views/peques.js";
import * as familia from "./views/familia.js";
import * as ajustes from "./views/ajustes.js";

const ROUTES = {
  hoy: { title: "Hoy", icon: "house", view: hoy },
  agenda: { title: "Agenda", icon: "calendar-days", view: agenda },
  tareas: { title: "Tareas", icon: "list-checks", view: tareas },
  compras: { title: "Compras", icon: "shopping-cart", view: compras },
  menu: { title: "Menú", icon: "utensils", view: menu, parent: "mas" },
  peques: { title: "Peques", icon: "baby", view: peques, parent: "mas" },
  familia: { title: "Familia", icon: "users", view: familia, parent: "mas" },
  reparto: { title: "Reparto", icon: "scale", view: tareas, parent: "tareas", before: () => tareas.setTab("reparto") },
  ajustes: { title: "Ajustes", icon: "settings", view: ajustes, parent: "mas" },
  mas: { title: "Más", icon: "layout-grid", view: { render: ajustes.renderMore, bind: () => {} } },
};
const TABS = ["hoy", "agenda", "tareas", "compras", "mas"];
const SIDE = ["hoy", "agenda", "tareas", "compras", "menu", "peques", "familia", "reparto"];

let current = null, page = null;

function route() {
  const name = (location.hash || "#hoy").slice(1).split("?")[0];
  return ROUTES[name] ? name : "hoy";
}

function navLinks() {
  const cur = route();
  const active = (k) => k === cur || ROUTES[cur].parent === k;
  document.getElementById("tabs").innerHTML = html`${TABS.map((k) => html`<a href="#${k}" ${active(k) ? html`aria-current="page"` : ""}>${icon(ROUTES[k].icon)}${ROUTES[k].title}</a>`)}`;
  document.getElementById("side-links").innerHTML = html`<button class="new" type="button" data-capture>${icon("plus")}Apuntar</button>
    ${SIDE.map((k) => html`<a class="link" href="#${k}" ${k === cur ? html`aria-current="page"` : ""}><span class="sico s-${k}">${icon(ROUTES[k].icon)}</span>${ROUTES[k].title}</a>`)}
    <hr><a class="link" href="#ajustes" ${cur === "ajustes" ? html`aria-current="page"` : ""}><span class="sico">${icon("settings")}</span>Ajustes</a>
    <a class="link" href="/cuenta"><span class="sico">${icon("user")}</span>Tu cuenta</a>`;
}

/** Draw the current screen again, keeping what is being typed in a field marked data-keep. */
function redraw() {
  if (!page || !current) return;
  const a = document.activeElement;
  const keep = a && page.contains(a) && a.dataset && a.dataset.keep
    ? { k: a.dataset.keep, v: a.value, s: a.selectionStart, e: a.selectionEnd } : null;
  ROUTES[current].view.render(page);
  if (keep) {
    const b = page.querySelector(`[data-keep="${keep.k}"]`);
    if (b) { b.value = keep.v; b.focus({ preventScroll: true }); try { b.setSelectionRange(keep.s, keep.e); } catch (e) { /* not text */ } }
  }
}

function mount() {
  const name = route();
  const r = ROUTES[name];
  if (r.before) r.before();
  else if (name === "tareas" && current === "reparto") tareas.setTab("pend");
  closeAllSheets();
  const view = document.getElementById("view");
  page = document.createElement("div");
  page.className = "page";
  page.dataset.route = name;   // each screen has its own sticker in the header (app.css)
  view.replaceChildren(page);
  current = name;
  r.view.render(page);
  r.view.bind(page, redraw);
  navLinks();
  document.title = `${r.title} · Mam-IA`;
  window.scrollTo(0, 0);
}

function handleQuery() {
  const q = new URLSearchParams(location.search);
  const text = q.get("apuntar");
  const done = q.get("hecho");
  if (text || done) history.replaceState(null, "", "/app" + location.hash);
  if (text) setTimeout(() => openCapture(text), 200);
  if (done && done.startsWith("tk:")) {
    const [, id, due] = done.split(":");
    const t = S.get("tasks", id);
    if (t && !t.done && t.due === due) completeTask(id);
  }
}

async function loadMe() {
  try {
    const r = await api("/api/me");
    try { localStorage.setItem("mamia:me", JSON.stringify(r)); } catch (e) { /* private */ }
    return r;
  } catch (e) {
    const cached = localStorage.getItem("mamia:me");
    if (e.status === 0 && cached) return JSON.parse(cached);   // offline: start with what we knew
    throw e;
  }
}

async function start() {
  let me;
  try { me = await loadMe(); } catch (e) {
    document.getElementById("view").innerHTML = html`<section class="card"><p>${e.message}</p><a class="btn" href="/entrar">Entrar</a></section>`;
    return;
  }
  setMe(me);
  ajustes.applyLook(me.user.theme, me.user.accent);
  S.status.readOnly = !!(me.billing && me.billing.readOnly);
  api("/api/version").then((v) => { ctx.version = v; }).catch(() => {});
  const first = S.init(me.user.familyId);
  mount();
  window.addEventListener("hashchange", mount);
  let alarmTimer = null;
  const net = document.getElementById("net");
  const showNet = () => {
    const n = S.pendingCount();
    const off = !S.status.online;
    net.hidden = !off && !n;
    if (!net.hidden) net.innerHTML = html`${icon(off ? "wifi-off" : "refresh-cw")}${off ? "Sin conexión" : "Guardando"}${n ? ` · ${n} ${n === 1 ? "cambio" : "cambios"} por enviar` : " · lo apuntado se guarda aquí"}`;
  };
  setInterval(showNet, 2000);
  window.addEventListener("online", showNet);
  window.addEventListener("offline", showNet);
  S.subscribe(() => {
    showNet();
    redraw();
    clearTimeout(alarmTimer);
    alarmTimer = setTimeout(syncNativeAlarms, 1500);
  });
  first.then(() => { handleQuery(); syncNativeAlarms(); });
  document.getElementById("fab").addEventListener("click", () => openCapture());
  document.getElementById("side-links").addEventListener("click", (e) => { if (e.target.closest("[data-capture]")) openCapture(); });
  document.addEventListener("keydown", (e) => {
    const typing = /input|textarea|select/i.test((document.activeElement || {}).tagName || "");
    if (!typing && (e.key === "n" || e.key === "+") && !e.metaKey && !e.ctrlKey) { e.preventDefault(); openCapture(); }
  });
  window.addEventListener("mamia-error", (e) => toast(e.detail, { error: true, ms: 6000 }));
  window.addEventListener("mamia-redraw", redraw);
  // the Android back button: close a sheet, else go back to Hoy, else leave the app
  window.mamiaBack = () => {
    if (closeTopSheet()) return true;
    if (current !== "hoy") { location.hash = "#hoy"; return true; }
    return false;
  };
  setInterval(async () => {   // the family and the subscription can change from other devices
    if (document.hidden) return;
    try { const r = await api("/api/me"); setMe(r); S.status.readOnly = !!r.billing.readOnly; } catch (e) { /* offline */ }
  }, 5 * 60000);
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {});
  initNotify();
}

start();
