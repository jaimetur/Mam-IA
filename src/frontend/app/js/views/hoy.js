// Hoy: what comes next, the day of the whole family, what must not be forgotten, tomorrow, dinner and shopping.
import * as S from "../store.js";
import { addDays, expand, longDay, today, cap, hm } from "../dates.js";
import { html, icon, avatar, mclass, on } from "../ui.js";
import { ctx } from "../ctx.js";
import { completeTask, eventEditor, taskEditor } from "../editors.js";
import { openCapture } from "../capture.js";
import { notifyState, askNotifications } from "../notify.js";
import { confetti, evTitle } from "../fun.js";

function greeting(now = new Date()) {
  const h = now.getHours();
  return h < 6 ? "Buenas noches" : h < 14 ? "Buenos días" : h < 21 ? "Buenas tardes" : "Buenas noches";
}

const sky = (now = new Date()) => { const h = now.getHours(); return h < 7 || h >= 21 ? "🌙" : h < 14 ? "☀️" : "🌤️"; };
const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;

const nameOf = (id) => (S.get("members", id) || {}).name || "";

export function evSub(o) {
  const e = o.ev, bits = [];
  const who = (e.who || []).map(nameOf).filter(Boolean);
  if (who.length) bits.push(who.join(", "));
  if (e.driver) bits.push(`lleva ${nameOf(e.driver)}`);
  if (e.pickup) bits.push(`recoge ${nameOf(e.pickup)}`);
  if (e.place) bits.push(e.place);
  if (o.end) bits.push(`hasta las ${o.end}`);
  return bits.join(" · ");
}

export const evColor = (e) => mclass(S.get("members", (e.who || [])[0] || e.driver || e.pickup || ""));

function nextUp(occs, now) {
  const t = hm(now);
  const d = today();
  return occs.find((o) => o.day === d && o.time && (o.end ? o.end > t : o.time >= t))
      || occs.find((o) => o.day > d && o.time);
}

function countdown(o, now) {
  const [h, m] = o.time.split(":").map(Number);
  const start = new Date(now); start.setHours(h, m, 0, 0);
  if (o.day !== today()) return o.day === addDays(today(), 1) ? `Mañana a las ${o.time}` : `${cap(longDay(o.day))} · ${o.time}`;
  const min = Math.round((start - now) / 60000);
  if (min <= 0) return "Ahora";
  if (min < 60) return `Dentro de ${min} min`;
  return `A las ${o.time}`;
}

export function render(root) {
  const now = new Date();
  const d = today(), tom = addDays(d, 1);
  const occs = expand(S.all("events"), d, addDays(d, 7));
  const todays = occs.filter((o) => o.day === d);
  const tomorrows = occs.filter((o) => o.day === tom);
  const nu = nextUp(occs, now);
  const tasks = S.list("tasks").filter((t) => !t.done && t.due && t.due <= d)
    .sort((a, b) => (a.due + (a.time || "99")).localeCompare(b.due + (b.time || "99")));
  const important = S.list("tasks").filter((t) => !t.done && !t.due && t.prio === "alta").slice(0, 3);
  const meal = S.get("meals", `${d}:cena`), lunch = S.get("meals", `${d}:comida`);
  const shopLists = S.list("lists").filter((l) => l.kind !== "otra").map((l) => l.id);
  const toBuy = S.list("items").filter((i) => !i.done && shopLists.includes(i.list)).length;
  const ms = S.members();
  const first = (ctx.me.name || "").split(" ")[0];
  const fresh = ms.length < 2 && !S.list("events").length && !S.list("tasks").length;
  const ns = notifyState();
  const b = ctx.billing || {};
  const giftEnds = b.plan === "gift" && b.expiry && (b.expiry - Date.now()) < 15 * 86400000 && b.expiry > Date.now();

  root.innerHTML = html`
    <header class="hero">
      <div class="hero-txt"><p class="kicker">${cap(longDay(d))}</p><h1>${greeting(now)}, ${first} <span class="sky" aria-hidden="true">${sky(now)}</span></h1>
        <div class="pills"><a class="pill" href="#agenda"><span aria-hidden="true">📅</span> ${todays.length ? plural(todays.length, "plan hoy", "planes hoy") : "Hoy sin planes"}</a>
          <a class="pill" href="#tareas"><span aria-hidden="true">✅</span> ${tasks.length ? plural(tasks.length, "tarea pendiente", "tareas pendientes") : "Nada pendiente"}</a>
          <a class="pill" href="#compras"><span aria-hidden="true">🛒</span> ${toBuy ? plural(toBuy, "cosa en la compra", "cosas en la compra") : "Compra hecha"}</a></div></div>
      <a class="avs" href="#familia" aria-label="Tu familia">${ms.slice(0, 5).map((m) => avatar(m))}</a>
    </header>
    ${b.readOnly ? html`<div class="banner bad">${icon("lock")}<div><b>Tu familia está en modo solo lectura.</b>
      <span>La suscripción ha terminado: puedes ver y exportar todo, pero no apuntar nada nuevo.</span>
      ${ctx.me && ctx.family.ownerId === ctx.me.id ? html`<a class="btn sm pri" href="/cuenta">Renovar</a>` : html`<span class="muted">Avisa a quien paga la familia.</span>`}</div></div>` : ""}
    ${giftEnds ? html`<div class="banner info">${icon("gift")}<div><span>Tu acceso gratis termina el <b>${new Date(b.expiry).toLocaleDateString("es-ES", { day: "numeric", month: "long" })}</b>.</span>
      <a class="btn sm" href="/cuenta">Elegir un plan</a></div></div>` : ""}
    ${fresh ? html`<section class="card"><h2>Para empezar</h2><div class="steps">
      <button type="button" data-go="#familia">${icon("user-plus")}Añade a tu familia: tu pareja, los peques…</button>
      <button type="button" data-act="capture">${icon("plus")}Apunta lo primero que tengas en la cabeza</button>
      <button type="button" data-act="notify" class="${ns.on ? "done" : ""}">${icon("bell")}Activa los avisos en este móvil</button>
    </div></section>` : ""}
    <div class="cols"><div>
    ${nu ? html`<button class="now" type="button" data-ev="${nu.id}" data-day="${nu.day}"><p class="lbl">${countdown(nu, now)}</p>
      <p class="t">${evTitle(nu.ev)}</p><p class="s">${[nu.time + (nu.end ? ` – ${nu.end}` : ""), evSub(nu)].filter(Boolean).join(" · ")}</p></button>` : ""}
    <section class="card"><h2 class="card-h">Hoy <a href="#agenda">Agenda</a></h2>
      ${todays.length ? html`<ol class="tl">${todays.map((o) => html`<li class="${o.time && (o.end || o.time) < hm(now) ? "past" : ""}">
        <time>${o.time || "Todo el día"}</time>
        <button class="ev ${evColor(o.ev)}" type="button" data-ev="${o.id}" data-day="${o.day}"><b>${evTitle(o.ev)}</b>${evSub(o) ? html`<span>${evSub(o)}</span>` : ""}</button></li>`)}</ol>`
        : html`<p class="empty">Hoy no hay planes apuntados. ${fresh ? "" : "Disfruta del respiro."}</p>`}
    </section>
    <section class="card"><h2 class="card-h"><span>No olvides ${tasks.length ? html`<span class="cnt">${tasks.length}</span>` : ""}</span><a href="#tareas">Tareas</a></h2>
      ${tasks.length || important.length ? html`<div class="list">${[...tasks, ...important].map((t) => html`<div class="row">
        <input class="ck" type="checkbox" aria-label="Hecho: ${t.title}" data-done="${t.id}">
        <button class="txt grow" type="button" data-task="${t.id}"><span class="title">${evTitle(t)}</span>
          <span class="sub">${t.due && t.due < d ? html`<span class="tag late">${t.due === addDays(d, -1) ? "Desde ayer" : "Atrasada"}</span>` : ""}
          ${t.prio === "alta" ? html`<span class="tag hi">Importante</span>` : ""}${t.time ? html`${icon("clock")}${t.time}` : ""}
          ${t.repeat ? icon("repeat") : ""}</span></button>
        ${avatar(S.get("members", t.who), "sm")}</div>`)}</div>`
        : html`<p class="empty">Nada pendiente para hoy. ${icon("sparkles", "xs")}</p>`}
    </section>
    </div><div>
    ${tomorrows.length ? html`<section class="card"><h2 class="card-h">Mañana <span class="muted" style="font-weight:600">${cap(longDay(tom))}</span></h2>
      <div class="daylist">${tomorrows.map((o) => html`<button class="evrow ${evColor(o.ev)}" type="button" data-ev="${o.id}" data-day="${o.day}"><i></i>
        <div><b>${evTitle(o.ev)}</b>${evSub(o) ? html`<span>${evSub(o)}</span>` : ""}</div><time>${o.time || "Todo el día"}</time></button>`)}</div></section>` : ""}
    <div class="duo">
      <a class="mini" href="#menu"><span class="lbl">🍽️ Cena</span><b>${(meal && meal.dish) || "Sin decidir"}</b>
        <span>${lunch && lunch.school ? `Comedor: ${lunch.school}` : "Ver el menú de la semana"}</span></a>
      <a class="mini" href="#compras"><span class="lbl">🛒 Compra</span><b>${toBuy ? `${toBuy} ${toBuy === 1 ? "cosa" : "cosas"}` : "Todo comprado"}</b>
        <span>${toBuy ? "En la lista de la compra" : "Añade lo que falte"}</span></a>
    </div>
    ${!ns.on && !fresh && ns.can ? html`<button class="banner info" type="button" data-act="notify" style="border:0;text-align:left;width:100%">${icon("bell-ring")}
      <div><b>Activa los avisos</b><span>Para que Mam-IA te recuerde los planes y tareas aunque no la tengas abierta.</span></div></button>` : ""}
    </div></div>`;
}

export function bind(root) {
  on(root, "click", "[data-ev]", (el) => eventEditor(el.dataset.ev, { occurrence: el.dataset.day }));
  on(root, "click", "[data-task]", (el) => taskEditor(el.dataset.task));
  on(root, "change", "[data-done]", (el) => { confetti(el); completeTask(el.dataset.done); });
  on(root, "click", "[data-go]", (el) => { location.hash = el.dataset.go; });
  on(root, "click", "[data-act=capture]", () => openCapture());
  on(root, "click", "[data-act=notify]", () => askNotifications());
}
