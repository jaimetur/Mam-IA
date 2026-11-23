// Agenda: day, week or month of the whole family, filtered by person, with the clashes of the week.
import * as S from "../store.js";
import { addDays, addMonths, cap, conflicts, expand, longDay, monthStart, MONTHS, parse, today, WD_SHORT, weekStart, weekday } from "../dates.js";
import { html, icon, mclass, on } from "../ui.js";
import { eventEditor } from "../editors.js";
import { evColor, evSub } from "./hoy.js";

const view = { mode: "week", day: today(), who: "" };

function filtered(occs) {
  if (!view.who) return occs;
  return occs.filter((o) => (o.ev.who || []).includes(view.who) || o.ev.driver === view.who || o.ev.pickup === view.who);
}

function dots(list) {
  const ids = [];
  for (const o of list) { const c = evColor(o.ev); if (!ids.includes(c)) ids.push(c); }
  return html`<span class="dots">${ids.slice(0, 4).map((c) => html`<i class="${c}"></i>`)}</span>`;
}

function dayList(occs, day) {
  const list = occs.filter((o) => o.day === day);
  return html`<section class="card"><h2 class="card-h">${cap(longDay(day))}
      <button class="link" type="button" data-new="${day}">${icon("plus", "xs")} Añadir</button></h2>
    ${list.length ? html`<div class="daylist">${list.map((o) => html`<button class="evrow ${evColor(o.ev)}" type="button" data-ev="${o.id}" data-day="${o.day}"><i></i>
      <div><b>${o.ev.title}</b><span>${o.ev.repeat ? icon("repeat", "xs") : ""}${evSub(o)}</span></div>
      <time>${o.cont ? "Sigue" : o.time || "Todo el día"}</time></button>`)}</div>` : html`<p class="empty">Nada apuntado.</p>`}</section>`;
}

function clashes(occs) {
  const name = (id) => (S.get("members", id) || {}).name || "";
  const cs = conflicts(occs).filter((c) => c.a.day >= today());
  if (!cs.length) return "";
  return html`${cs.slice(0, 3).map((c) => html`<div class="banner warn">${icon("triangle-alert")}<div>
    <b>${cap(longDay(c.a.day))} a las ${c.a.time}: dos planes a la vez</b>
    <span>${c.a.ev.title} y ${c.b.ev.title}${c.shared.length ? ` (${c.shared.map(name).join(", ")})` : ""}. ¿Quién lleva a cada uno?</span>
    <span class="btns"><button class="btn sm" type="button" data-ev="${c.a.id}" data-day="${c.a.day}">Ver ${c.a.ev.title}</button>
      <button class="btn sm" type="button" data-ev="${c.b.id}" data-day="${c.b.day}">Ver ${c.b.ev.title}</button></span></div></div>`)}`;
}

export function render(root) {
  const d = today();
  const ms = S.members();
  let title, body, range;
  if (view.mode === "month") {
    const m0 = monthStart(view.day), first = weekStart(m0);
    const last = addDays(weekStart(addDays(addMonths(m0, 1), -1)), 6);
    range = [first, last];
    const occs = filtered(expand(S.all("events"), first, last));
    const pm = parse(m0);
    title = `${cap(MONTHS[pm.getMonth()])} ${pm.getFullYear()}`;
    const cells = [];
    for (let x = first; x <= last; x = addDays(x, 1)) cells.push(x);
    body = html`<section class="card"><div class="month">${WD_SHORT.map((w) => html`<span class="wd">${w}</span>`)}
      ${cells.map((x) => html`<button type="button" data-pick="${x}" class="${x.slice(0, 7) !== m0.slice(0, 7) ? "out" : ""} ${x === d ? "today" : ""}"
        aria-pressed="${x === view.day}"><b>${parse(x).getDate()}</b>${dots(occs.filter((o) => o.day === x))}</button>`)}</div></section>
      ${dayList(occs, view.day)}${clashes(occs)}`;
  } else if (view.mode === "week") {
    const w0 = weekStart(view.day);
    range = [w0, addDays(w0, 6)];
    const occs = filtered(expand(S.all("events"), w0, addDays(w0, 6)));
    const a = parse(w0), b = parse(addDays(w0, 6));
    title = a.getMonth() === b.getMonth() ? `${a.getDate()} – ${b.getDate()} de ${MONTHS[b.getMonth()]}` : `${a.getDate()} ${MONTHS[a.getMonth()].slice(0, 3)} – ${b.getDate()} ${MONTHS[b.getMonth()].slice(0, 3)}`;
    const days = [0, 1, 2, 3, 4, 5, 6].map((i) => addDays(w0, i));
    body = html`<div class="week">${days.map((x) => html`<button type="button" data-pick="${x}" class="${x === d ? "today" : ""}" aria-pressed="${x === view.day}">
        <small>${WD_SHORT[weekday(x)]}</small><b>${parse(x).getDate()}</b>${dots(occs.filter((o) => o.day === x))}</button>`)}</div>
      ${clashes(occs)}${dayList(occs, view.day)}
      ${days.filter((x) => x > view.day && occs.some((o) => o.day === x)).slice(0, 3).map((x) => dayList(occs, x))}`;
  } else {
    range = [view.day, view.day];
    const occs = filtered(expand(S.all("events"), view.day, view.day));
    title = cap(longDay(view.day));
    body = html`${clashes(occs)}${dayList(occs, view.day)}`;
  }
  root.innerHTML = html`
    <header class="head"><div><p class="kicker">Agenda de la familia</p><h1>Agenda</h1></div>
      <div class="actions"><button class="btn sm" type="button" data-today ${range[0] <= d && d <= range[1] && view.day === d ? "disabled" : ""}>Hoy</button></div></header>
    <div class="seg" role="group" aria-label="Vista">${[["day", "Día"], ["week", "Semana"], ["month", "Mes"]].map(([k, l]) => html`
      <button type="button" data-mode="${k}" aria-pressed="${view.mode === k}">${l}</button>`)}</div>
    <div class="nav-row"><button class="icon-btn" type="button" data-step="-1" aria-label="Anterior">${icon("chevron-left")}</button>
      <h2>${title}</h2><button class="icon-btn" type="button" data-step="1" aria-label="Siguiente">${icon("chevron-right")}</button></div>
    ${ms.length > 1 ? html`<div class="chips scroll" role="group" aria-label="Filtrar por persona">
      <button class="chip" type="button" data-who="" aria-pressed="${!view.who}">Todos</button>
      ${ms.map((m) => html`<button class="chip ${mclass(m)}" type="button" data-who="${m.id}" aria-pressed="${view.who === m.id}"><i class="dot"></i>${m.name}</button>`)}</div>` : ""}
    ${body}`;
}

export function bind(root, rerender) {
  on(root, "click", "[data-mode]", (el) => { view.mode = el.dataset.mode; rerender(); });
  on(root, "click", "[data-step]", (el) => {
    const n = Number(el.dataset.step);
    view.day = view.mode === "month" ? addMonths(view.day, n) : addDays(view.day, view.mode === "week" ? 7 * n : n);
    rerender();
  });
  on(root, "click", "[data-today]", () => { view.day = today(); rerender(); });
  on(root, "click", "[data-pick]", (el) => { view.day = el.dataset.pick; rerender(); });
  on(root, "click", "[data-who]", (el) => { view.who = el.dataset.who; rerender(); });
  on(root, "click", "[data-ev]", (el) => eventEditor(el.dataset.ev, { occurrence: el.dataset.day }));
  on(root, "click", "[data-new]", (el) => eventEditor(null, { start: `${el.dataset.new}T17:00` }));
}

export const selectedDay = () => view.day;
