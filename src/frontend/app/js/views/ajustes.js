// Más (every section) and Ajustes (look, reminders on the device and by email, copies, account, about).
import * as S from "../store.js";
import { api } from "../api.js";
import { html, icon, on, toast, confirmSheet } from "../ui.js";
import { ctx } from "../ctx.js";
import { askNotifications, notifyState, testNotification } from "../notify.js";
import { importOld, hasOldData } from "../legacy.js";

export function renderMore(root) {
  const tiles = [
    ["#menu", "utensils", "Menú", "Comidas y cenas de la semana"],
    ["#peques", "baby", "Peques", "Ficha, horarios, salud y tallas"],
    ["#familia", "users", "Familia", "Personas e invitaciones"],
    ["#reparto", "scale", "Reparto", "Quién hace qué en casa"],
    ["#ajustes", "settings", "Ajustes", "Aspecto, avisos y copias"],
    ["/cuenta", "user", "Tu cuenta", "Contraseña y suscripción"],
  ];
  root.innerHTML = html`<header class="head"><div><p class="kicker">${ctx.family.name}</p><h1>Más</h1></div></header>
    <div class="tiles">${tiles.map(([href, i, t, s]) => html`<a class="tile" href="${href}">${icon(i)}<b>${t}</b><span>${s}</span></a>`)}</div>
    <section class="card"><h2>Muy pronto</h2><p class="muted" style="margin:0">Casa (mantenimiento y vencimientos), Salud, Dinero, Viajes y la IA de
      Mam-IA: leer la circular del cole desde una foto, proponer el menú y prepararte el resumen del domingo.</p></section>`;
}

const ACCENTS = [["rosa", "#C93E66"], ["lavanda", "#6B4FC0"], ["menta", "#0E7C6B"], ["coral", "#B9481F"]];

export function applyLook(theme, accent) {
  const r = document.documentElement;
  if (theme && theme !== "auto") r.dataset.theme = theme; else delete r.dataset.theme;
  if (accent && accent !== "rosa") r.dataset.accent = accent; else delete r.dataset.accent;
  try { localStorage.setItem("mamia:look", JSON.stringify({ theme, accent })); } catch (e) { /* private window */ }
  const bg = getComputedStyle(document.body).backgroundColor;
  const meta = document.getElementById("theme-color");
  if (meta && bg) meta.content = bg;
}

export function render(root) {
  const me = ctx.me;
  const ns = notifyState();
  const v = ctx.version || {};
  root.innerHTML = html`<header class="head"><div><p class="kicker">${me.email}</p><h1>Ajustes</h1></div></header>
    <section class="card"><h2>Aspecto</h2>
      <div class="seg" role="group" aria-label="Tema">${[["auto", "Automático"], ["light", "Claro"], ["dark", "Oscuro"]].map(([k, l]) => html`
        <button type="button" data-theme="${k}" aria-pressed="${me.theme === k}">${l}</button>`)}</div>
      <div class="field"><span>Color</span><div class="swatches">${ACCENTS.map(([k, c]) => html`<button type="button" data-accent="${k}" aria-pressed="${me.accent === k}" aria-label="${k}" style="background:${c}"></button>`)}</div></div>
    </section>
    <section class="card"><h2>Avisos en este ${ns.native ? "móvil" : "dispositivo"}</h2>
      ${ns.on ? html`<p class="muted" style="margin:0">${icon("circle-check", "xs")} Activados. Te avisaremos de los planes y tareas con aviso.</p>
        <div class="btns"><button class="btn sm" type="button" data-test>${icon("bell", "sm")}Probar un aviso</button></div>`
        : ns.can ? html`<p class="muted" style="margin:0">${ns.denied ? "Has bloqueado los avisos: permítelos en los ajustes del navegador." : "Actívalos para que Mam-IA te recuerde lo que toca aunque no la tengas abierta."}</p>
          <div class="btns"><button class="btn pri" type="button" data-notify>${icon("bell-ring", "sm")}Activar los avisos</button></div>`
        : html`<p class="muted" style="margin:0">Este navegador no puede mostrar avisos. En iPhone, añade Mam-IA a la pantalla de inicio (Compartir → Añadir a pantalla de inicio) y ábrela desde ahí. En Android, instala la app.</p>`}
    </section>
    <section class="card"><h2>Avisos por correo</h2>
      <p class="muted" style="margin:0">Te llegan a ${me.email} (lo cambias en Tu cuenta).</p>
      <label class="switch"><span>Recordatorios de planes y tareas<span class="sub" style="display:block;font-weight:400;font-size:13px;color:var(--ink2)">Cuando toca el aviso de algo tuyo o de toda la familia</span></span>
        <input type="checkbox" data-mail="mailReminders" ${me.mailReminders !== false ? "checked" : ""}></label>
      <label class="switch"><span>Resumen del día<span class="sub" style="display:block;font-weight:400;font-size:13px;color:var(--ink2)">Cada mañana a partir de las 7: planes, tareas, pendientes y menú</span></span>
        <input type="checkbox" data-mail="mailDigest" ${me.mailDigest ? "checked" : ""}></label>
    </section>
    <section class="card"><h2>Copia de seguridad</h2>
      <p class="muted" style="margin:0">Descarga todos los datos de la familia en un archivo. El servidor además hace una copia cada noche.</p>
      <div class="btns"><button class="btn" type="button" data-export>${icon("download", "sm")}Descargar una copia</button>
        ${me.role === "admin" ? html`<label class="btn" style="cursor:pointer">${icon("upload", "sm")}Importar una copia<input type="file" accept="application/json,.json" data-import hidden></label>` : ""}</div>
      ${hasOldData() && me.role === "admin" ? html`<div class="banner info">${icon("refresh-cw")}<div><span>En este navegador hay datos de la versión anterior de Mam-IA.</span>
        <button class="btn sm" type="button" data-legacy>Traerlos a la familia</button></div></div>` : ""}
    </section>
    <section class="card"><h2>Cuenta</h2><div class="list">
      <a class="row" href="/cuenta" style="text-decoration:none;color:inherit">${icon("user")}<span class="grow"><span>Tu cuenta</span><span class="sub">Nombre, correo, contraseña y suscripción</span></span>${icon("chevron-right", "sm")}</a>
      ${me.isAdmin ? html`<a class="row" href="/admin" style="text-decoration:none;color:inherit">${icon("shield-check")}<span class="grow"><span>Administración del servidor</span></span>${icon("chevron-right", "sm")}</a>` : ""}
      <button class="row" type="button" data-logout style="border:0;background:none;padding:6px 2px;color:var(--bad);font-weight:700">${icon("log-out")}Cerrar sesión</button></div></section>
    <section class="card"><h2>Acerca de Mam-IA</h2><p class="muted" style="margin:0">Versión ${v.version || "—"}${v.build && v.build !== "dev" ? ` (${v.build.slice(0, 7)})` : ""} ·
      <a href="/privacidad">Privacidad</a> · <a href="/terminos">Términos</a> · Ayuda: <span style="user-select:all">mamia@jtgcloud.com</span></p></section>`;
}

async function saveLook(changes) {
  Object.assign(ctx.me, changes);
  applyLook(ctx.me.theme, ctx.me.accent);
  try { await api("/api/me", { method: "PUT", body: changes }); } catch (e) { toast(e.message, { error: true }); }
}

async function exportCopy() {
  try {
    const res = await api("/api/family/export", { raw: true });
    const text = await res.text();
    const name = `mamia-${new Date().toISOString().slice(0, 10)}.json`;
    if (ctx.native && ctx.native.saveFile) {
      ctx.native.saveFile(name, "application/json", btoa(unescape(encodeURIComponent(text))));
      return;
    }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([text], { type: "application/json" }));
    a.download = name;
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 5000);
  } catch (e) { toast(e.message, { error: true }); }
}

export function bind(root, rerender) {
  on(root, "click", "[data-theme]", (el) => { saveLook({ theme: el.dataset.theme }); rerender(); });
  on(root, "click", "[data-accent]", (el) => { saveLook({ accent: el.dataset.accent }); rerender(); });
  on(root, "click", "[data-notify]", () => askNotifications().then(rerender));
  on(root, "click", "[data-test]", () => testNotification());
  on(root, "change", "[data-mail]", async (el) => {
    const key = el.dataset.mail, value = el.checked;
    try {
      const r = await api("/api/me", { method: "PUT", body: { [key]: value } });
      Object.assign(ctx.me, r.user);
      toast(value ? "Te los enviaremos por correo" : "Ya no te los enviaremos por correo");
    } catch (e) { el.checked = !value; toast(e.message, { error: true }); }
  });
  on(root, "click", "[data-export]", () => exportCopy());
  on(root, "click", "[data-legacy]", async () => { const n = importOld(); toast(n ? `Traídos ${n} datos de la versión anterior` : "No había nada que traer"); rerender(); });
  on(root, "change", "[data-import]", async (el) => {
    const f = el.files[0];
    if (!f) return;
    try {
      const data = JSON.parse(await f.text());
      if (!(await confirmSheet("Importar una copia", `Se añadirán ${(data.docs || []).length} datos a la familia (lo que tenga el mismo identificador se sustituye).`, { yes: "Importar" }))) return;
      const r = await api("/api/family/import", { method: "POST", body: { docs: data.docs || [] } });
      toast(`Importados ${r.imported}${r.skipped ? `, ${r.skipped} no válidos` : ""}`);
      S.sync();
    } catch (e) { toast(e.message || "Ese archivo no es una copia de Mam-IA.", { error: true }); }
    el.value = "";
  });
  on(root, "click", "[data-logout]", async () => {
    try { await api("/api/logout", { method: "POST" }); } catch (e) { /* signed out anyway */ }
    S.forget();
    location.href = "/entrar";
  });
}
