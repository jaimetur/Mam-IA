// Menú: lunch and dinner of the week, with what the kids eat at school and the family's allergies; the ingredients
// that are missing go to the shopping list in one tap.
import * as S from "../store.js";
import { addDays, cap, parse, today, MONTHS, WEEKDAYS, weekStart } from "../dates.js";
import { html, icon, on, sheet, toast, formData } from "../ui.js";
import { addItem, shopLists } from "./compras.js";
import { fold } from "../parse.js";

const view = { week: weekStart(today()) };

const mealId = (day, slot) => `${day}:${slot}`;

function allergies() {
  return S.members().filter((m) => m.info && m.info.allergies).map((m) => ({ m, a: m.info.allergies }));
}

function missing(days) {
  const lists = shopLists();
  if (!lists.length) return { list: null, items: [] };
  const list = lists[0].id;
  const have = new Set(S.list("items").filter((i) => i.list === list && !i.done).map((i) => fold(i.text)));
  const seen = new Set(), out = [];
  for (const d of days) for (const slot of ["comida", "cena"]) {
    const m = S.get("meals", mealId(d, slot));
    for (const ing of (m && m.ingredients) || []) {
      const k = fold(ing);
      if (!have.has(k) && !seen.has(k)) { seen.add(k); out.push(ing); }
    }
  }
  return { list, items: out };
}

export function render(root) {
  const d = today();
  const days = [0, 1, 2, 3, 4, 5, 6].map((i) => addDays(view.week, i));
  const a = parse(days[0]), b = parse(days[6]);
  const miss = missing(days.filter((x) => x >= d));
  const al = allergies();
  root.innerHTML = html`
    <header class="head"><div><p class="kicker">${a.getDate()} – ${b.getDate()} de ${MONTHS[b.getMonth()]}</p><h1>Menú de la semana</h1></div>
      <div class="actions"><button class="icon-btn" type="button" data-step="-1" aria-label="Semana anterior">${icon("chevron-left")}</button>
        <button class="icon-btn" type="button" data-step="1" aria-label="Semana siguiente">${icon("chevron-right")}</button></div></header>
    ${al.length ? html`<div class="chips">${al.map(({ m, a }) => html`<span class="alert-chip">${icon("triangle-alert", "xs")}${m.name}: ${a}</span>`)}</div>` : ""}
    <section class="card">${days.map((x) => {
      const c = S.get("meals", mealId(x, "comida")), n = S.get("meals", mealId(x, "cena"));
      return html`<div class="menu-day ${x === d ? "today" : ""}"><b>${cap(WEEKDAYS[(parse(x).getDay() + 6) % 7].slice(0, 3))} ${parse(x).getDate()}</b>
        <div class="slots">
          <button class="slot" type="button" data-slot="${mealId(x, "comida")}"><small>Comida${c && c.school ? " · comedor" : ""}</small>
            ${c && (c.dish || c.school) ? html`<span>${c.dish || ""}${c.dish && c.school ? " · " : ""}${c.school ? html`<span class="muted">Cole: ${c.school}</span>` : ""}</span>` : html`<span class="ph">Añadir</span>`}</button>
          <button class="slot" type="button" data-slot="${mealId(x, "cena")}"><small>Cena</small>
            ${n && n.dish ? html`<span>${n.dish}</span>` : html`<span class="ph">Añadir</span>`}</button>
        </div></div>`;
    })}</section>
    <section class="card"><h2 class="card-h">${miss.items.length ? `Faltan ${miss.items.length} ingredientes` : "Ingredientes"}</h2>
      ${miss.items.length ? html`<p class="muted" style="margin:0">${miss.items.slice(0, 8).join(", ")}${miss.items.length > 8 ? ` y ${miss.items.length - 8} más` : ""}</p>
        <div class="btns"><button class="btn pri" type="button" data-tolist>${icon("shopping-cart", "sm")}Añadir a la compra</button></div>`
        : html`<p class="empty">Apunta los ingredientes de cada plato y Mam-IA te dirá cuáles faltan en la lista de la compra.</p>`}
      <div class="btns"><button class="btn sm" type="button" data-copy>${icon("copy", "sm")}Repetir el menú de la semana pasada</button></div>
    </section>`;
  root._miss = miss;
}

function slotSheet(id) {
  const [day, slot] = id.split(":");
  const m = S.get("meals", id) || {};
  const s = sheet(`${cap(WEEKDAYS[(parse(day).getDay() + 6) % 7])} · ${slot === "cena" ? "Cena" : "Comida"}`, html`<form style="display:grid;gap:14px" autocomplete="off">
    <label class="field"><span>Plato</span><input type="text" name="dish" value="${m.dish || ""}" maxlength="120" placeholder="Crema de calabaza y tortilla" autofocus></label>
    ${slot === "comida" ? html`<label class="field"><span>Lo que comen en el comedor (para no repetir en la cena)</span>
      <input type="text" name="school" value="${m.school || ""}" maxlength="120" placeholder="Macarrones con tomate"></label>` : ""}
    <label class="field"><span>Ingredientes (separados por comas)</span><textarea name="ing" maxlength="1800" placeholder="calabaza, puerro, huevos, patatas">${(m.ingredients || []).join(", ")}</textarea></label>
    <div class="foot">${m.dish || m.school ? html`<button class="btn danger" type="button" data-del>${icon("trash-2", "sm")}Vaciar</button>` : ""}<button class="btn pri" type="submit">Guardar</button></div></form>`);
  s.el.querySelector("form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const d = formData(ev.target);
    const ingredients = (d.ing || "").split(/,|\n/).map((x) => x.trim()).filter(Boolean).slice(0, 30).map((x) => x.slice(0, 60));
    if (!d.dish.trim() && !(d.school || "").trim() && !ingredients.length) S.del("meals", id);
    else S.put("meals", id, { date: day, slot, dish: d.dish.trim() || null, school: (d.school || "").trim() || null, ingredients });
    s.close();
  });
  const del = s.el.querySelector("[data-del]");
  if (del) del.addEventListener("click", () => { S.del("meals", id); s.close(); });
}

export function bind(root, rerender) {
  on(root, "click", "[data-step]", (el) => { view.week = addDays(view.week, 7 * Number(el.dataset.step)); rerender(); });
  on(root, "click", "[data-slot]", (el) => slotSheet(el.dataset.slot));
  on(root, "click", "[data-tolist]", () => {
    const miss = root._miss;
    if (!miss || !miss.list) return;
    miss.items.forEach((x) => addItem(miss.list, x, { src: "menu" }));
    toast(`${miss.items.length} ingredientes añadidos a la compra`, { action: "Ver", onAction: () => { location.hash = "#compras"; } });
  });
  on(root, "click", "[data-copy]", () => {
    let n = 0;
    for (let i = 0; i < 7; i++) for (const slot of ["comida", "cena"]) {
      const from = S.get("meals", mealId(addDays(view.week, i - 7), slot));
      const to = mealId(addDays(view.week, i), slot);
      if (from && !S.get("meals", to)) { S.put("meals", to, { ...from, date: addDays(view.week, i) }); n++; }
    }
    toast(n ? `Copiados ${n} platos de la semana pasada` : "No hay nada que copiar (o esta semana ya está hecha)");
  });
}
