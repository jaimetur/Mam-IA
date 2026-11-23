// The editors shared by several screens: events, tasks (and completing them), and the member pickers.
import * as S from "./store.js";
import { addDays, nextAfter, today, weekday, WEEKDAYS, cap } from "./dates.js";
import { html, icon, sheet, toast, confirmSheet, formData, mclass } from "./ui.js";
import { ctx } from "./ctx.js";

export const CATS = [["casa", "Casa"], ["peques", "Peques"], ["cole", "Cole"], ["salud", "Salud"], ["trabajo", "Trabajo"],
  ["compras", "Compras"], ["comidas", "Comidas"], ["ocio", "Ocio"], ["pareja", "Pareja"], ["yo", "Para mí"],
  ["papeleo", "Papeleo"], ["otros", "Otros"]];
export const REMINDS = [["", "Sin aviso"], ["0", "A la hora"], ["10", "10 min antes"], ["30", "30 min antes"],
  ["60", "1 hora antes"], ["120", "2 horas antes"], ["1440", "El día antes"]];

const opt = (v, label, sel) => html`<option value="${v}" ${String(sel ?? "") === String(v) ? "selected" : ""}>${label}</option>`;

export function memberSelect(name, sel, { none = "Nadie", kinds = null } = {}) {
  const ms = S.members().filter((m) => !kinds || kinds.includes(m.kind));
  return html`<select name="${name}">${opt("", none, sel)}${ms.map((m) => opt(m.id, m.name, sel))}</select>`;
}

export function memberChecks(name, selected = [], { label = "" } = {}) {
  return html`<div class="chips" role="group" aria-label="${label}">${S.members().map((m) => html`
    <label class="chip ${mclass(m)}" style="cursor:pointer"><input type="checkbox" data-multi name="${name}" value="${m.id}"
      ${selected.includes(m.id) ? "checked" : ""} style="accent-color:var(--mc);margin:0"><span>${m.name}</span></label>`)}</div>`;
}

function repeatFields(rule, dayHint) {
  const freq = rule ? rule.freq : "";
  const days = rule && rule.days ? rule.days : [weekday(dayHint || today())];
  return html`<div class="field"><span>Se repite</span>
      <select name="freq" data-freq>${opt("", "No se repite", freq)}${opt("daily", "Cada día", freq)}${opt("weekly", "Cada semana", freq)}
      ${opt("monthly", "Cada mes", freq)}${opt("yearly", "Cada año", freq)}</select></div>
    <div class="chips" data-days ${freq === "weekly" ? "" : "hidden"} role="group" aria-label="Días de la semana">
      ${WEEKDAYS.map((d, i) => html`<label class="chip" style="cursor:pointer"><input type="checkbox" data-multi name="days" value="${i}" ${days.includes(i) ? "checked" : ""} style="margin:0">${cap(d.slice(0, 3))}</label>`)}
    </div>
    <div class="field" data-until ${freq ? "" : "hidden"}><span>Hasta (opcional)</span><input type="date" name="until" value="${(rule && rule.until) || ""}"></div>`;
}

function wireRepeat(el) {
  const f = el.querySelector("[data-freq]");
  const sync = () => {
    el.querySelector("[data-days]").hidden = f.value !== "weekly";
    el.querySelector("[data-until]").hidden = !f.value;
  };
  f.addEventListener("change", sync);
}

function ruleFrom(d) {
  if (!d.freq) return null;
  const r = { freq: d.freq, every: 1 };
  if (d.freq === "weekly") r.days = (d.days || []).map(Number).sort();
  if (d.until) r.until = d.until;
  return r;
}

// ---------- events ----------

export function eventEditor(id, defaults = {}) {
  const e = id ? S.get("events", id) : null;
  const v = { title: "", start: `${today()}T17:00`, allDay: false, who: [], remind: 60, cat: "", ...defaults, ...(e || {}) };
  const day = v.start.slice(0, 10), time = v.start.length > 10 ? v.start.slice(11, 16) : "";
  const endTime = v.end && v.end.length > 10 ? v.end.slice(11, 16) : "";
  const endDay = v.end ? v.end.slice(0, 10) : "";
  const s = sheet(e ? "Editar plan" : "Nuevo plan", html`
    <form class="ed" style="display:grid;gap:14px" autocomplete="off">
      <label class="field"><span>Qué</span><input type="text" name="title" value="${v.title}" maxlength="120" required placeholder="Dentista, cumple, reunión…" autofocus></label>
      <label class="switch">Todo el día<input type="checkbox" name="allDay" ${v.allDay || !time ? "checked" : ""}></label>
      <div class="grid2"><label class="field"><span>Día</span><input type="date" name="day" value="${day}" required></label>
        <label class="field" data-timed><span>Hora</span><input type="time" name="time" value="${time || "17:00"}"></label></div>
      <div class="grid2" data-timed><label class="field"><span>Termina</span><input type="time" name="endTime" value="${endTime}"></label>
        <label class="field"><span>Último día (si dura varios)</span><input type="date" name="endDay" value="${endDay !== day ? endDay : ""}"></label></div>
      <div class="field"><span>Para quién</span>${memberChecks("who", v.who || [], { label: "Para quién" })}</div>
      <div class="grid2"><label class="field"><span>Lleva</span>${memberSelect("driver", v.driver, { kinds: ["adult"] })}</label>
        <label class="field"><span>Recoge</span>${memberSelect("pickup", v.pickup, { kinds: ["adult"] })}</label></div>
      <label class="field"><span>Dónde</span><input type="text" name="place" value="${v.place || ""}" maxlength="120" placeholder="Opcional"></label>
      ${repeatFields(v.repeat, day)}
      <div class="grid2"><label class="field"><span>Aviso</span><select name="remind">${REMINDS.map(([k, l]) => opt(k, l, v.remind ?? ""))}</select></label>
        <label class="field"><span>Tipo</span><select name="cat">${opt("", "—", v.cat)}${CATS.map(([k, l]) => opt(k, l, v.cat))}</select></label></div>
      <label class="field"><span>Notas</span><textarea name="notes" maxlength="4000" placeholder="Lo que haya que llevar, teléfonos…">${v.notes || ""}</textarea></label>
      <div class="foot">${e ? html`<button class="btn danger" type="button" data-del>${icon("trash-2", "sm")}Borrar</button>` : ""}
        <button class="btn pri" type="submit">Guardar</button></div>
    </form>`);
  const form = s.el.querySelector("form");
  const timed = () => s.el.querySelectorAll("[data-timed]").forEach((x) => { x.hidden = form.allDay.checked; });
  form.allDay.addEventListener("change", timed); timed();
  wireRepeat(s.el);
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const d = formData(form);
    if (!d.title.trim()) return;
    const start = d.allDay ? d.day : `${d.day}T${d.time || "09:00"}`;
    let end = null;
    if (d.endDay && d.endDay > d.day) end = d.allDay ? d.endDay : `${d.endDay}T${d.endTime || d.time || "09:00"}`;
    else if (!d.allDay && d.endTime && d.endTime > (d.time || "")) end = `${d.day}T${d.endTime}`;
    const data = { title: d.title.trim(), start, allDay: d.allDay, who: d.who, driver: d.driver || null, pickup: d.pickup || null,
                   place: d.place, notes: d.notes, cat: d.cat || null, repeat: ruleFrom(d), remind: d.remind === "" ? null : Number(d.remind) };
    if (end) data.end = end;
    if (e && e.exdates) data.exdates = e.exdates;
    const nid = id || S.newId("e");
    S.put("events", nid, data);
    s.close();
    toast(id ? "Plan guardado" : "Plan apuntado", { action: id ? null : "Deshacer", onAction: () => S.del("events", nid) });
  });
  const del = s.el.querySelector("[data-del]");
  if (del) del.addEventListener("click", async () => {
    if (e.repeat && defaults.occurrence) {
      const only = await confirmSheet("Borrar un plan que se repite", `¿Borro solo el del ${defaults.occurrence} o todos?`, { yes: "Solo ese día", no: "Todos" });
      if (only) { S.patch("events", id, { exdates: [...(e.exdates || []), defaults.occurrence] }); s.close(); return; }
    } else if (!(await confirmSheet("Borrar el plan", `¿Borro «${e.title}»?`, { yes: "Borrar", danger: true }))) return;
    S.del("events", id);
    s.close();
    toast("Plan borrado", { action: "Deshacer", onAction: () => S.put("events", id, e) });
  });
  return s;
}

// ---------- tasks ----------

export function taskEditor(id, defaults = {}) {
  const t = id ? S.get("tasks", id) : null;
  const v = { title: "", due: today(), prio: "normal", ...defaults, ...(t || {}) };
  const s = sheet(t ? "Editar tarea" : "Nueva tarea", html`
    <form style="display:grid;gap:14px" autocomplete="off">
      <label class="field"><span>Qué hay que hacer</span><input type="text" name="title" value="${v.title}" maxlength="160" required autofocus placeholder="Firmar la autorización, poner lavadora…"></label>
      <label class="field"><span>Quién</span>${memberSelect("who", v.who, { none: "Cualquiera" })}</label>
      <div class="grid2"><label class="field"><span>Para cuándo</span><input type="date" name="due" value="${v.due || ""}"></label>
        <label class="field"><span>Hora (opcional)</span><input type="time" name="time" value="${v.time || ""}"></label></div>
      <div class="grid2"><label class="field"><span>Aviso</span><select name="remind">${REMINDS.map(([k, l]) => opt(k, l, v.remind ?? ""))}</select></label>
        <label class="field"><span>Importancia</span><select name="prio">${opt("normal", "Normal", v.prio)}${opt("alta", "Importante", v.prio)}</select></label></div>
      ${repeatFields(v.repeat, v.due)}
      <div class="field" data-rot ${v.repeat ? "" : "hidden"}><span>Turnos: se pasa a la siguiente persona cada vez que se hace</span>
        ${memberChecks("rotate", v.rotate || [], { label: "Turnos" })}</div>
      <label class="field"><span>Tipo</span><select name="cat">${opt("", "—", v.cat)}${CATS.map(([k, l]) => opt(k, l, v.cat))}</select></label>
      <label class="field"><span>Notas</span><textarea name="notes" maxlength="4000">${v.notes || ""}</textarea></label>
      <div class="foot">${t ? html`<button class="btn danger" type="button" data-del>${icon("trash-2", "sm")}Borrar</button>` : ""}
        <button class="btn pri" type="submit">Guardar</button></div>
    </form>`);
  const form = s.el.querySelector("form");
  wireRepeat(s.el);
  form.freq.addEventListener("change", () => { s.el.querySelector("[data-rot]").hidden = !form.freq.value; });
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const d = formData(form);
    if (!d.title.trim()) return;
    const rule = ruleFrom(d);
    const data = { ...(t || {}), title: d.title.trim(), who: d.who || null, due: d.due || null, time: d.time || null,
                   remind: d.remind === "" ? null : Number(d.remind), prio: d.prio, repeat: rule,
                   rotate: rule && d.rotate && d.rotate.length > 1 ? d.rotate : null, cat: d.cat || null, notes: d.notes };
    if (data.rotate && !data.rotate.includes(data.who)) data.who = data.rotate[0];
    if (rule && !data.due) data.due = today();
    const nid = id || S.newId("t");
    S.put("tasks", nid, data);
    s.close();
    toast(id ? "Tarea guardada" : "Tarea apuntada", { action: id ? null : "Deshacer", onAction: () => S.del("tasks", nid) });
  });
  const del = s.el.querySelector("[data-del]");
  if (del) del.addEventListener("click", async () => {
    if (!(await confirmSheet("Borrar la tarea", `¿Borro «${t.title}»${t.repeat ? " y sus repeticiones" : ""}?`, { yes: "Borrar", danger: true }))) return;
    S.del("tasks", id);
    s.close();
    toast("Tarea borrada", { action: "Deshacer", onAction: () => S.put("tasks", id, t) });
  });
  return s;
}

/** Tick a task off. A repeating one moves to its next day (and to the next person when it has turns); every time a
 *  task is done a "done" record is kept for the load balance. */
export function completeTask(id, { silent = false } = {}) {
  const t = S.get("tasks", id);
  if (!t) return;
  const by = t.who || ctx.myMember || null;
  const doneId = S.newId("d");
  S.put("done", doneId, { task: id, title: t.title, by, date: today(), cat: t.cat || null });
  if (t.repeat) {
    const base = t.due || today();
    let next = nextAfter(base, t.repeat, base);
    while (next && next <= today()) next = nextAfter(base, t.repeat, next);   // an overdue one jumps to the future
    let who = t.who;
    if (t.rotate && t.rotate.length > 1) who = t.rotate[(t.rotate.indexOf(t.who) + 1) % t.rotate.length];
    if (next) S.put("tasks", id, { ...t, due: next, who: who || null });
    else S.put("tasks", id, { ...t, done: true, doneAt: new Date().toISOString(), doneBy: by });
  } else {
    S.put("tasks", id, { ...t, done: true, doneAt: new Date().toISOString(), doneBy: by });
  }
  if (!silent) toast(t.repeat ? "Hecho. Vuelve a tocar más adelante" : "¡Hecho!", {
    action: "Deshacer", onAction: () => { S.put("tasks", id, t); S.del("done", doneId); },
  });
}

export function uncompleteTask(id) {
  const t = S.get("tasks", id);
  if (!t) return;
  const { done, doneAt, doneBy, ...rest } = t;
  S.put("tasks", id, rest);
  const rec = S.list("done").filter((d) => d.task === id).sort((a, b) => b.date.localeCompare(a.date))[0];
  if (rec) S.del("done", rec.id);
}

export const dueLabel = (t, ref = today()) => {
  if (!t.due) return null;
  if (t.due < ref) return { late: true, text: t.due === addDays(ref, -1) ? "Ayer" : "Atrasada" };
  return null;
};
