// "Apuntar": the "+" button. Write (or dictate) anything and it becomes an event, a task, a reminder or shopping.
import * as S from "./store.js";
import { parse } from "./parse.js";
import { cap, longDay, ruleText, today } from "./dates.js";
import { html, icon, sheet, toast, avatar } from "./ui.js";
import { ctx } from "./ctx.js";
import { eventEditor, taskEditor, CATS } from "./editors.js";
import { addItem, shopLists } from "./views/compras.js";

const KINDS = [["event", "Plan", "calendar-days"], ["task", "Tarea", "list-checks"], ["reminder", "Recordatorio", "bell"], ["shop", "Compra", "shopping-cart"]];
const name = (id) => (S.get("members", id) || {}).name || "";

function preview(r, kind) {
  if (!r.title && !r.items.length) return html`<p class="muted" style="margin:0">Ejemplos: «Dentista Lucas el jueves a las 17:30, lo lleva Pablo» ·
    «Comprar leche y pan» · «Recuérdame pagar el comedor el día 1» · «Natación Inés los lunes y miércoles a las 16:30»</p>`;
  if (kind === "shop") return html`<dl class="parsed"><dt>A la compra</dt><dd>${r.items.length ? r.items.join(", ") : r.title}</dd></dl>`;
  const rows = [["Qué", r.title]];
  if (r.date) rows.push(["Cuándo", cap(longDay(r.date)) + (r.time ? ` · ${r.time}` : kind === "event" ? " · todo el día" : "")]);
  if (r.repeat) rows.push(["Se repite", ruleText(r.repeat)]);
  if (r.who.length) rows.push(["Para", html`${r.who.map((id) => html`${avatar(S.get("members", id), "sm")} ${name(id)} `)}`]);
  if (r.driver) rows.push(["Lleva", html`${avatar(S.get("members", r.driver), "sm")} ${name(r.driver)}`]);
  if (r.pickup) rows.push(["Recoge", html`${avatar(S.get("members", r.pickup), "sm")} ${name(r.pickup)}`]);
  if (r.remind != null || kind === "reminder") rows.push(["Aviso", r.remind ? (r.remind >= 1440 ? "El día antes" : r.remind >= 60 ? `${r.remind / 60} h antes` : `${r.remind} min antes`) : "A la hora"]);
  if (r.cat) rows.push(["Tipo", (CATS.find(([k]) => k === r.cat) || [0, r.cat])[1]]);
  return html`<p class="lbl">Lo he entendido así</p><dl class="parsed">${rows.map(([k, v]) => html`<dt>${k}</dt><dd>${v}</dd>`)}</dl>`;
}

function save(r, kind) {
  if (kind === "shop") {
    const list = (shopLists()[0] || {}).id;
    if (!list) { toast("Crea antes una lista de la compra.", { error: true }); return false; }
    const items = r.items.length ? r.items : [r.title];
    items.forEach((t) => addItem(list, t));
    toast(`${items.length === 1 ? items[0] : items.length + " cosas"} a la compra`, { action: "Ver", onAction: () => { location.hash = "#compras"; } });
    return true;
  }
  if (!r.title) return false;
  if (kind === "event") {
    const id = S.newId("e");
    const data = { title: r.title, start: r.time ? `${r.date || today()}T${r.time}` : r.date || today(), allDay: !r.time,
                   who: r.who, driver: r.driver, pickup: r.pickup, repeat: r.repeat, remind: r.remind ?? (r.time ? 60 : 0), cat: r.cat };
    S.put("events", id, data);
    toast("Plan apuntado", { action: "Deshacer", onAction: () => S.del("events", id) });
  } else {
    const id = S.newId("t");
    const data = { title: r.title, who: r.who[0] || null, due: r.date || (kind === "reminder" ? today() : null), time: r.time,
                   remind: kind === "reminder" ? r.remind ?? 0 : r.remind, repeat: r.repeat, cat: r.cat, prio: "normal" };
    if (data.repeat && !data.due) data.due = today();
    S.put("tasks", id, data);
    toast(kind === "reminder" ? "Te lo recordaré" : "Tarea apuntada", { action: "Deshacer", onAction: () => S.del("tasks", id) });
  }
  return true;
}

export function openCapture(text = "") {
  let forced = null;
  const s = sheet("Apuntar", html`
    <div class="chips" role="group" aria-label="Qué es">${KINDS.map(([k, l, i]) => html`<button class="chip" type="button" data-kind="${k}" aria-pressed="false">${icon(i)}${l}</button>`)}</div>
    <div class="say"><textarea name="say" maxlength="500" placeholder="Escribe o dicta lo que tengas en la cabeza" aria-label="Lo que quieres apuntar" autofocus></textarea>
      <button class="mic" type="button" data-mic aria-label="Dictar" hidden>${icon("mic")}</button></div>
    <div data-preview></div>
    <div class="foot"><button class="btn" type="button" data-more>Más detalles</button><button class="btn pri" type="button" data-save>Guardar</button></div>`);
  const ta = s.el.querySelector("textarea");
  const pv = s.el.querySelector("[data-preview]");
  ta.value = text;
  let r = null, kind = "task";
  const update = () => {
    r = parse(ta.value, S.members(), today());
    kind = forced || r.kind;
    s.el.querySelectorAll("[data-kind]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.kind === kind && !!ta.value.trim()));
    pv.innerHTML = preview(r, kind);
  };
  ta.addEventListener("input", update);
  ta.addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); if (save(r, kind)) s.close(); } });
  s.el.querySelectorAll("[data-kind]").forEach((b) => b.addEventListener("click", () => { forced = b.dataset.kind; update(); ta.focus(); }));
  s.el.querySelector("[data-save]").addEventListener("click", () => { if (save(r, kind)) s.close(); else ta.focus(); });
  s.el.querySelector("[data-more]").addEventListener("click", () => {
    s.close();
    if (kind === "event") eventEditor(null, { title: r.title, start: r.time ? `${r.date || today()}T${r.time}` : r.date || today(), allDay: !r.time,
      who: r.who, driver: r.driver, pickup: r.pickup, repeat: r.repeat, remind: r.remind, cat: r.cat });
    else if (kind === "shop") location.hash = "#compras";
    else taskEditor(null, { title: r.title, who: r.who[0], due: r.date, time: r.time, repeat: r.repeat, remind: kind === "reminder" ? r.remind ?? 0 : r.remind, cat: r.cat });
  });
  // dictation where the browser can (Chrome); everywhere else the keyboard's own microphone works
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const mic = s.el.querySelector("[data-mic]");
  if (SR) {
    mic.hidden = false;
    let rec = null;
    mic.addEventListener("click", () => {
      if (rec) { rec.stop(); return; }
      rec = new SR();
      rec.lang = "es-ES"; rec.interimResults = true;
      const base = ta.value ? ta.value.trim() + " " : "";
      rec.onresult = (e) => { ta.value = base + [...e.results].map((x) => x[0].transcript).join(""); update(); };
      rec.onend = () => { rec = null; mic.classList.remove("on"); };
      rec.onerror = () => toast("No te he entendido. Prueba otra vez o escríbelo.", { error: true });
      mic.classList.add("on");
      rec.start();
    });
  }
  update();
  return s;
}
