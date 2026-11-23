// Peques: the card of each child, with what a mother always needs at hand (school, activities, health, sizes,
// contacts and birthdays), and their next plans.
import * as S from "../store.js";
import { addDays, expand, parse, relDay, today } from "../dates.js";
import { html, icon, avatar, on, sheet, formData, toast, confirmSheet } from "../ui.js";
import { eventEditor } from "../editors.js";
import { memberSheet } from "./familia.js";

export const KID_FIELDS = [
  ["school", "Cole", "CEIP Los Almendros"], ["course", "Curso", "3.º B"], ["teacher", "Tutora o tutor", "Marta · tutoria3b@cole.es"],
  ["schedule", "Horario y extraescolares", "Cole de 9:00 a 16:00 · Natación L y X 16:30"],
  ["allergies", "Alergias", "Frutos secos"], ["health", "Salud y medicación", "Ventolín si tose de noche"],
  ["doctor", "Pediatra", "Dra. Ruiz · C. S. Las Delicias"], ["clothes", "Talla de ropa", "8-9 años"],
  ["shoes", "Talla de calzado", "32"], ["contacts", "Contactos (canguro, otros padres…)", "Ana (madre de Vega) 600 000 000"],
  ["notes", "Notas", "Lo que haya que recordar"],
];

function age(b) {
  if (!b) return null;
  const n = parse(today()), d = parse(b);
  let y = n.getFullYear() - d.getFullYear();
  if (n.getMonth() < d.getMonth() || (n.getMonth() === d.getMonth() && n.getDate() < d.getDate())) y--;
  return y >= 0 ? (y === 0 ? "Menos de un año" : `${y} ${y === 1 ? "año" : "años"}`) : null;
}

function nextBirthday(b) {
  if (!b) return null;
  const t = today();
  let next = `${t.slice(0, 4)}${b.slice(4)}`;
  if (next < t) next = `${Number(t.slice(0, 4)) + 1}${b.slice(4)}`;
  return next;
}

export function render(root) {
  const kids = S.members().filter((m) => m.kind === "kid");
  const d = today();
  const occs = expand(S.all("events"), d, addDays(d, 30));
  root.innerHTML = html`
    <header class="head"><div><p class="kicker">Lo que siempre hay que tener a mano</p><h1>Peques</h1></div>
      <div class="actions"><button class="btn sm pri" type="button" data-addkid>${icon("plus", "sm")}Peque</button></div></header>
    ${kids.length ? kids.map((k) => {
      const i = k.info || {};
      const mine = occs.filter((o) => (o.ev.who || []).includes(k.id)).slice(0, 3);
      const bd = nextBirthday(k.birthday);
      return html`<section class="card">
        <div class="row">${avatar(k, "lg")}<div class="grow"><b style="font:800 20px var(--f-display)">${k.name}</b>
          <span class="muted">${[age(k.birthday), [i.school, i.course].filter(Boolean).join(" · ")].filter(Boolean).join(" · ")}</span></div>
          <button class="btn sm" type="button" data-edit="${k.id}">${icon("pencil", "sm")}Ficha</button></div>
        ${i.allergies ? html`<span class="alert-chip">${icon("triangle-alert", "xs")}Alergia: ${i.allergies}</span>` : ""}
        <dl class="kv">${KID_FIELDS.filter(([key]) => !["school", "course", "allergies", "notes"].includes(key) && i[key]).map(([key, label]) => html`<dt>${label}</dt><dd>${i[key]}</dd>`)}
          ${bd ? html`<dt>Cumpleaños</dt><dd>${relDay(bd, d)}${bd === d ? " 🎂" : ""}</dd>` : ""}</dl>
        ${mine.length ? html`<div class="daylist">${mine.map((o) => html`<button class="evrow ${"m" + (k.color || "c8").slice(1)}" type="button" data-ev="${o.id}" data-day="${o.day}"><i></i>
          <div><b>${o.ev.title}</b><span>${relDay(o.day, d)}</span></div><time>${o.time || ""}</time></button>`)}</div>` : ""}
      </section>`;
    }) : html`<section class="card"><p class="empty"><b>Añade a tus peques</b> para tener a mano su cole, horarios, alergias, tallas y contactos,
      y para apuntarles planes («natación Inés los lunes»).</p><div class="btns"><button class="btn pri" type="button" data-addkid>${icon("plus", "sm")}Añadir un peque</button></div></section>`}`;
}

export function kidSheet(id) {
  const k = S.get("members", id);
  if (!k) return;
  const i = k.info || {};
  const s = sheet(`Ficha de ${k.name}`, html`<form style="display:grid;gap:12px" autocomplete="off">
    <label class="field"><span>Cumpleaños</span><input type="date" name="birthday" value="${k.birthday || ""}"></label>
    ${KID_FIELDS.map(([key, label, ph]) => key === "notes" || key === "schedule" || key === "contacts" || key === "health"
      ? html`<label class="field"><span>${label}</span><textarea name="${key}" maxlength="1000" placeholder="${ph}">${i[key] || ""}</textarea></label>`
      : html`<label class="field"><span>${label}</span><input type="text" name="${key}" value="${i[key] || ""}" maxlength="200" placeholder="${ph}"></label>`)}
    <div class="foot"><button class="btn" type="button" data-person>Nombre y color</button><button class="btn pri" type="submit">Guardar</button></div></form>`, { wide: true });
  s.el.querySelector("form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const d = formData(ev.target);
    const info = {};
    KID_FIELDS.forEach(([key]) => { if ((d[key] || "").trim()) info[key] = d[key].trim(); });
    S.put("members", id, { ...k, birthday: d.birthday || null, info });
    s.close();
    toast("Ficha guardada");
  });
  s.el.querySelector("[data-person]").addEventListener("click", () => { s.close(); memberSheet(id); });
}

export function bind(root) {
  on(root, "click", "[data-addkid]", () => memberSheet(null, { kind: "kid" }));
  on(root, "click", "[data-edit]", (el) => kidSheet(el.dataset.edit));
  on(root, "click", "[data-ev]", (el) => eventEditor(el.dataset.ev, { occurrence: el.dataset.day }));
}
