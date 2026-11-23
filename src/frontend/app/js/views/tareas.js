// Tareas: what is pending (by when), the routines that repeat, what was done, and the load balance of the family.
import * as S from "../store.js";
import { addDays, cap, longDay, relDay, ruleText, today, weekStart } from "../dates.js";
import { html, icon, avatar, mclass, on, toast } from "../ui.js";
import { completeTask, taskEditor, uncompleteTask } from "../editors.js";

const view = { tab: "pend", who: "", period: 7 };

function row(t, d) {
  return html`<div class="row ${t.done ? "is-done" : ""}">
    <input class="ck" type="checkbox" ${t.done ? "checked" : ""} aria-label="Hecho: ${t.title}" data-done="${t.id}">
    <button class="txt grow" type="button" data-task="${t.id}"><span class="title">${t.title}</span>
      <span class="sub">${t.due && !t.done ? (t.due < d ? html`<span class="tag late">${relDay(t.due, d)}</span>` : relDay(t.due, d)) : ""}
      ${t.time ? html`${icon("clock")}${t.time}` : ""}${t.prio === "alta" ? html`<span class="tag hi">Importante</span>` : ""}
      ${t.repeat ? html`${icon("repeat")}${ruleText(t.repeat)}` : ""}${t.rotate ? html`<span class="tag acc">Por turnos</span>` : ""}</span></button>
    ${avatar(S.get("members", t.who), "sm")}</div>`;
}

function group(title, list, d) {
  if (!list.length) return "";
  return html`<section class="card"><h2 class="card-h"><span>${title} <span class="cnt">${list.length}</span></span></h2>
    <div class="list">${list.map((t) => row(t, d))}</div></section>`;
}

function pending(d) {
  let ts = S.list("tasks").filter((t) => !t.done);
  if (view.who) ts = ts.filter((t) => t.who === view.who || (!t.who && view.who === "none"));
  const by = (a, b) => ((a.due || "9999") + (a.time || "99") + a.title).localeCompare((b.due || "9999") + (b.time || "99") + b.title);
  ts.sort(by);
  const wEnd = addDays(weekStart(d), 6);
  const out = [
    group("Atrasadas", ts.filter((t) => t.due && t.due < d), d),
    group("Hoy", ts.filter((t) => t.due === d), d),
    group("Mañana", ts.filter((t) => t.due === addDays(d, 1)), d),
    group("Esta semana", ts.filter((t) => t.due > addDays(d, 1) && t.due <= wEnd), d),
    group("Más adelante", ts.filter((t) => t.due > wEnd), d),
    group("Cuando se pueda", ts.filter((t) => !t.due), d),
  ];
  return ts.length ? out : html`<section class="card"><p class="empty"><b>No hay nada pendiente.</b> Apunta tareas con el botón + o crea una rutina
    (lavadoras, basura, regar…) para que se repita sola.</p></section>`;
}

function routines(d) {
  const ts = S.list("tasks").filter((t) => t.repeat && !t.done).sort((a, b) => a.title.localeCompare(b.title));
  return html`<section class="card"><h2 class="card-h">Rutinas de casa <button class="link" type="button" data-new-routine>${icon("plus", "xs")} Nueva rutina</button></h2>
    ${ts.length ? html`<div class="list">${ts.map((t) => html`<div class="row"><button class="txt grow" type="button" data-task="${t.id}">
      <span class="title">${t.title}</span><span class="sub">${ruleText(t.repeat)} · ${t.due ? `toca ${relDay(t.due, d).toLowerCase()}` : ""}
      ${t.rotate ? ` · por turnos: ${t.rotate.map((id) => (S.get("members", id) || {}).name).filter(Boolean).join(", ")}` : ""}</span></button>
      ${avatar(S.get("members", t.who), "sm")}</div>`)}</div>`
      : html`<p class="empty">Las rutinas se repiten solas y pueden ir por turnos: «Sacar la basura, cada día, por turnos entre Inés y Lucas».</p>`}</section>`;
}

function doneList(d) {
  const recs = S.list("done").filter((r) => r.date >= addDays(d, -14)).sort((a, b) => b.date.localeCompare(a.date));
  if (!recs.length) return html`<section class="card"><p class="empty">Aquí verás lo que se ha hecho en las últimas dos semanas.</p></section>`;
  const days = [...new Set(recs.map((r) => r.date))];
  return days.map((day) => html`<section class="card"><h2 class="card-h">${cap(longDay(day))}</h2><div class="list">
    ${recs.filter((r) => r.date === day).map((r) => html`<div class="row"><span class="grow"><span>${r.title}</span></span>${avatar(S.get("members", r.by), "sm")}</div>`)}</div></section>`);
}

function balance(d) {
  const from = addDays(d, -(view.period - 1));
  const recs = S.list("done").filter((r) => r.date >= from);
  const ms = S.members();
  const counts = ms.map((m) => ({ m, n: recs.filter((r) => r.by === m.id).length })).sort((a, b) => b.n - a.n);
  const total = recs.length;
  const max = Math.max(1, ...counts.map((c) => c.n));
  const top = counts[0];
  const adults = counts.filter((c) => c.m.kind !== "kid");
  const low = adults[adults.length - 1];
  const share = top && total ? Math.round((top.n * 100) / total) : 0;
  const movable = top && low && top.m.id !== low.m.id && share >= 50
    ? S.list("tasks").filter((t) => !t.done && t.who === top.m.id && !t.rotate).slice(0, 3) : [];
  return html`<section class="card"><h2 class="card-h">Tareas hechas
      <span class="seg" role="group" aria-label="Periodo" style="width:auto">${[[7, "7 días"], [30, "30 días"]].map(([k, l]) => html`
        <button type="button" data-period="${k}" aria-pressed="${view.period === k}">${l}</button>`)}</span></h2>
    ${total ? html`<div class="bars">${counts.map((c) => html`<div class="bar ${mclass(c.m)}">${avatar(c.m, "sm")}
      <span class="track"><span class="fill" style="width:${Math.round((c.n * 100) / max)}%"></span></span><b>${c.n}</b></div>`)}</div>
      <p class="muted" style="margin:0">${top.m.name} ha hecho el ${share} % de las tareas ${view.period === 7 ? "de esta semana" : "del último mes"}.</p>`
      : html`<p class="empty">Cuando la familia vaya marcando tareas como hechas, aquí verás quién hace qué.</p>`}</section>
    ${movable.length ? html`<section class="card"><h2>Para equilibrar</h2>
      <p class="muted" style="margin:0">Estas tareas de ${top.m.name} podrían pasar a ${low.m.name}:</p>
      <div class="list">${movable.map((t) => html`<div class="row"><span class="grow"><span>${t.title}</span>
        <span class="sub">${t.due ? relDay(t.due, d) : "Sin fecha"}</span></span>
        <button class="btn sm" type="button" data-move="${t.id}" data-to="${low.m.id}">Pasar a ${low.m.name}</button></div>`)}</div></section>` : ""}`;
}

export function render(root) {
  const d = today();
  const ms = S.members();
  const tabs = [["pend", "Pendientes"], ["rut", "Rutinas"], ["hechas", "Hechas"], ["reparto", "Reparto"]];
  root.innerHTML = html`
    <header class="head"><div><p class="kicker">Lo que hay que hacer</p><h1>Tareas</h1></div>
      <div class="actions"><button class="btn sm pri" type="button" data-new>${icon("plus", "sm")}Tarea</button></div></header>
    <div class="seg" role="group" aria-label="Apartado">${tabs.map(([k, l]) => html`<button type="button" data-tab="${k}" aria-pressed="${view.tab === k}">${l}</button>`)}</div>
    ${view.tab === "pend" && ms.length > 1 ? html`<div class="chips scroll" role="group" aria-label="Filtrar por persona">
      <button class="chip" type="button" data-who="" aria-pressed="${!view.who}">Todos</button>
      ${ms.map((m) => html`<button class="chip ${mclass(m)}" type="button" data-who="${m.id}" aria-pressed="${view.who === m.id}"><i class="dot"></i>${m.name}</button>`)}
      <button class="chip" type="button" data-who="none" aria-pressed="${view.who === "none"}">Sin asignar</button></div>` : ""}
    ${view.tab === "pend" ? pending(d) : view.tab === "rut" ? routines(d) : view.tab === "hechas" ? doneList(d) : balance(d)}`;
}

export function bind(root, rerender) {
  on(root, "click", "[data-tab]", (el) => { view.tab = el.dataset.tab; rerender(); });
  on(root, "click", "[data-who]", (el) => { view.who = el.dataset.who; rerender(); });
  on(root, "click", "[data-period]", (el) => { view.period = Number(el.dataset.period); rerender(); });
  on(root, "click", "[data-task]", (el) => taskEditor(el.dataset.task));
  on(root, "click", "[data-new]", () => taskEditor(null, view.who && view.who !== "none" ? { who: view.who } : {}));
  on(root, "click", "[data-new-routine]", () => taskEditor(null, { repeat: { freq: "weekly", every: 1 } }));
  on(root, "change", "[data-done]", (el) => (el.checked ? completeTask(el.dataset.done) : uncompleteTask(el.dataset.done)));
  on(root, "click", "[data-move]", (el) => {
    const to = S.get("members", el.dataset.to);
    S.patch("tasks", el.dataset.move, { who: el.dataset.to });
    toast(`Ahora es de ${to ? to.name : "otra persona"}`);
  });
}

export function setTab(t) { view.tab = t; }
