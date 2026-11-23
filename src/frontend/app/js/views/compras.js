// Compras: shared lists by shop, ordered by aisle, "lo de siempre" in one tap, and live ticking from the shop.
import * as S from "../store.js";
import { html, icon, on, sheet, toast, confirmSheet, formData } from "../ui.js";
import { ctx } from "../ctx.js";
import { fold } from "../parse.js";

export const SECTIONS = ["Fruta y verdura", "Carne y pescado", "Lácteos y huevos", "Panadería", "Despensa", "Congelados",
  "Bebidas", "Droguería", "Higiene", "Bebé", "Farmacia", "Otros"];
const GUESS = [
  ["Fruta y verdura", /\b(fruta|manzana|platano|naranja|mandarina|pera|uva|fresa|kiwi|melon|sandia|limon|aguacate|tomate|lechuga|cebolla|ajo|patata|zanahoria|calabacin|calabaza|pimiento|berenjena|pepino|espinaca|brocoli|coliflor|judia|puerro|seta|champinon|verdura|ensalada|perejil)/],
  ["Carne y pescado", /\b(pollo|carne|ternera|cerdo|lomo|filete|hamburguesa|salchicha|chorizo|jamon|pavo|pescado|merluza|salmon|atun fresco|bacalao|gamba|langostino|calamar|sepia|mejillon|dorada|lubina)/],
  ["Lácteos y huevos", /\b(leche|yogur|queso|mantequilla|nata|huevo|kefir|batido)/],
  ["Panadería", /\b(pan|barra|baguette|bolleria|croissant|magdalena|tostada|bimbo|picos)/],
  ["Despensa", /\b(arroz|pasta|macarron|espagueti|fideo|lenteja|garbanzo|alubia|harina|azucar|sal|aceite|vinagre|tomate frito|atun|conserva|cereal|galleta|cafe|cola cao|cacao|infusion|te|chocolate|mermelada|miel|especia|caldo|legumbre|frutos secos|pipas|patatas fritas)/],
  ["Congelados", /\b(congelad|helado|pizza|guisante|croqueta|varitas)/],
  ["Bebidas", /\b(agua|zumo|refresco|cerveza|vino|coca|fanta|bebida|tonica|gaseosa)/],
  ["Droguería", /\b(detergente|suavizante|lejia|friegasuelos|lavavajillas|bayeta|estropajo|bolsa de basura|bolsas de basura|papel de cocina|papel de aluminio|film|limpiador|amoniaco|pastilla)/],
  ["Higiene", /\b(papel higienico|gel|champu|pasta de dientes|cepillo|desodorante|compresa|tampon|crema|colonia|maquinilla|algodon|toallita|panuelo|jabon)/],
  ["Bebé", /\b(panal|potito|leche de continuacion|biberon|chupete|toallitas de bebe)/],
  ["Farmacia", /\b(ibuprofeno|paracetamol|dalsy|apiretal|termometro|tirita|suero|vitamina|jarabe|medicina|receta)/],
];

export function guessSection(text) {
  const f = fold(text);
  for (const [s, rx] of GUESS) if (rx.test(f)) return s;
  return "Otros";
}

/** "2 leches" → {text: "Leches", qty: "2"}; "leche x2" → {text: "Leche", qty: "2"}. */
export function splitQty(raw) {
  let text = raw.trim(), qty = "";
  let m = text.match(/^(\d+(?:[.,]\d+)?\s*(?:kg|g|gr|l|litros?|ml|paquetes?|botes?|latas?|docenas?|bolsas?|cajas?)?)\s+(?:de\s+)?(.+)$/i);
  if (m) { qty = m[1]; text = m[2]; }
  m = text.match(/^(.+?)\s*[x×]\s*(\d+)$/i);
  if (m) { text = m[1]; qty = m[2]; }
  return { text: text.charAt(0).toUpperCase() + text.slice(1), qty };
}

const view = { list: null };

export function shopLists() {
  return S.list("lists").filter((l) => l.kind !== "otra").sort((a, b) => (a.order ?? 99) - (b.order ?? 99));
}

export function addItem(listId, raw, extra = {}) {
  const { text, qty } = splitQty(raw);
  if (!text) return null;
  const same = S.list("items").find((i) => i.list === listId && !i.done && fold(i.text) === fold(text));
  if (same) return same.id;
  const id = S.newId("i");
  S.put("items", id, { list: listId, text, qty: qty || null, section: guessSection(text), done: false, by: ctx.myMember,
                       src: "manual", order: Date.now() % 100000, ...extra });
  return id;
}

function liveNote(items) {
  const now = Date.now();
  const others = items.map((i) => ({ i, m: S.meta("items", i.id) }))
    .filter(({ m }) => m && m.by && m.by !== ctx.me.id && now - Date.parse(m.at) < 3 * 60000);
  if (!others.length) return "";
  const acc = (ctx.family.accounts || []).find((a) => a.id === others[0].m.by);
  return html`<div class="live"><span class="pulse"></span>${acc ? acc.name.split(" ")[0] : "Alguien"} está tachando ahora mismo</div>`;
}

export function render(root) {
  const lists = shopLists();
  if (!view.list || !lists.find((l) => l.id === view.list)) view.list = lists[0] ? lists[0].id : null;
  const items = S.list("items").filter((i) => i.list === view.list);
  const todo = items.filter((i) => !i.done), done = items.filter((i) => i.done);
  const bySection = SECTIONS.map((s) => [s, todo.filter((i) => (i.section || "Otros") === s).sort((a, b) => (a.order || 0) - (b.order || 0))])
    .filter(([, l]) => l.length);
  const extra = todo.filter((i) => !SECTIONS.includes(i.section || "Otros"));
  if (extra.length) bySection.push(["Otros", extra]);
  const count = (id) => S.list("items").filter((i) => i.list === id && !i.done).length;
  root.innerHTML = html`
    <header class="head"><div><p class="kicker">Lista compartida</p><h1>Compras</h1></div>
      <div class="actions"><button class="btn sm" type="button" data-staples>${icon("repeat", "sm")}Lo de siempre</button></div></header>
    <div class="chips scroll" role="group" aria-label="Listas">
      ${lists.map((l) => html`<button class="chip" type="button" data-list="${l.id}" aria-pressed="${l.id === view.list}">${l.name} · ${count(l.id)}</button>`)}
      <button class="chip" type="button" data-newlist>${icon("plus")}Lista</button></div>
    ${view.list ? html`
    <form class="add-row" data-add autocomplete="off"><input type="text" name="t" placeholder="Añadir: leche, 2 kg de naranjas…" aria-label="Añadir a la lista" maxlength="120">
      <button class="btn pri" type="submit" aria-label="Añadir">${icon("plus")}</button></form>
    ${liveNote(items)}
    ${todo.length ? html`<section class="card">${bySection.map(([s, l]) => html`<p class="sec-h">${s}</p><div class="list">
      ${l.map((i) => html`<div class="row"><input class="ck" type="checkbox" aria-label="Comprado: ${i.text}" data-tick="${i.id}">
        <button class="txt grow" type="button" data-item="${i.id}"><span class="title">${i.qty ? html`<b>${i.qty}</b> ` : ""}${i.text}
          ${i.src === "menu" ? html` <span class="from">del menú</span>` : ""}</span>${i.note ? html`<span class="sub">${i.note}</span>` : ""}</button></div>`)}</div>`)}
      </section>` : html`<section class="card"><p class="empty"><b>La lista está vacía.</b> Añade lo que falte, o pulsa «Lo de siempre».</p></section>`}
    ${done.length ? html`<section class="card"><h2 class="card-h">En el carro <span class="cnt">${done.length}</span>
      <button class="link" type="button" data-clear>Quitar lo comprado</button></h2><div class="list">
      ${done.map((i) => html`<div class="row is-done"><input class="ck" type="checkbox" checked aria-label="Comprado: ${i.text}" data-tick="${i.id}">
        <span class="grow"><span class="title">${i.qty ? `${i.qty} ` : ""}${i.text}</span></span></div>`)}</div></section>` : ""}
    <p class="muted" style="text-align:center;margin:4px 0 0"><button class="link" type="button" data-editlist>Cambiar el nombre o borrar «${(lists.find((l) => l.id === view.list) || {}).name}»</button></p>`
    : html`<section class="card"><p class="empty">Crea tu primera lista de la compra.</p></section>`}`;
}

function staplesSheet() {
  const draw = () => {
    const st = S.list("staples").sort((a, b) => a.text.localeCompare(b.text));
    const inList = new Set(S.list("items").filter((i) => i.list === view.list && !i.done).map((i) => fold(i.text)));
    return html`<p class="muted" style="margin:0">Marca lo que haga falta esta vez y añádelo de golpe.</p>
      <form data-st style="display:grid;gap:10px"><div class="list">${st.map((s) => html`<label class="row" style="cursor:pointer">
        <input class="ck" type="checkbox" name="pick" data-multi value="${s.id}" ${inList.has(fold(s.text)) ? "disabled checked" : ""}>
        <span class="grow"><span>${s.text}</span><span class="sub">${s.section || "Otros"}${inList.has(fold(s.text)) ? " · ya está en la lista" : ""}</span></span>
        <button class="icon-btn ghost" type="button" data-rm="${s.id}" aria-label="Quitar ${s.text} de lo de siempre">${icon("x", "sm")}</button></label>`)}</div>
        <button class="btn pri" type="submit">Añadir a la lista</button></form>
      <form class="add-row" data-newst autocomplete="off"><input type="text" name="t" placeholder="Algo que compras siempre" maxlength="120" aria-label="Nuevo de siempre">
        <button class="btn" type="submit">Guardar</button></form>`;
  };
  const s = sheet("Lo de siempre", draw());
  const redraw = () => { s.body.innerHTML = draw(); };
  s.el.addEventListener("submit", (ev) => {
    ev.preventDefault();
    if (ev.target.matches("[data-st]")) {
      const picks = formData(ev.target).pick || [];
      picks.forEach((id) => { const st = S.get("staples", id); if (st) addItem(view.list, st.text, { section: st.section || guessSection(st.text), src: "siempre" }); });
      s.close();
      if (picks.length) toast(`${picks.length} ${picks.length === 1 ? "cosa añadida" : "cosas añadidas"} a la lista`);
    } else if (ev.target.matches("[data-newst]")) {
      const t = ev.target.t.value.trim();
      if (!t) return;
      S.put("staples", S.newId("s"), { text: splitQty(t).text, section: guessSection(t), list: view.list });
      redraw();
    }
  });
  s.el.addEventListener("click", (ev) => {
    const rm = ev.target.closest("[data-rm]");
    if (rm) { ev.preventDefault(); S.del("staples", rm.dataset.rm); redraw(); }
  });
}

function itemSheet(id) {
  const i = S.get("items", id);
  if (!i) return;
  const s = sheet("Editar", html`<form style="display:grid;gap:14px">
    <label class="field"><span>Qué</span><input type="text" name="text" value="${i.text}" maxlength="120" required></label>
    <div class="grid2"><label class="field"><span>Cantidad</span><input type="text" name="qty" value="${i.qty || ""}" maxlength="20"></label>
      <label class="field"><span>Sección</span><select name="section">${SECTIONS.map((x) => html`<option ${x === (i.section || "Otros") ? "selected" : ""}>${x}</option>`)}</select></label></div>
    <label class="field"><span>Nota</span><input type="text" name="note" value="${i.note || ""}" maxlength="120" placeholder="Marca, la sin lactosa…"></label>
    <label class="field"><span>Lista</span><select name="list">${shopLists().map((l) => html`<option value="${l.id}" ${l.id === i.list ? "selected" : ""}>${l.name}</option>`)}</select></label>
    <div class="foot"><button class="btn danger" type="button" data-del>${icon("trash-2", "sm")}Quitar</button><button class="btn pri" type="submit">Guardar</button></div></form>`);
  s.el.querySelector("form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const d = formData(ev.target);
    S.put("items", id, { ...i, text: d.text.trim(), qty: d.qty.trim() || null, section: d.section, note: d.note.trim() || null, list: d.list });
    s.close();
  });
  s.el.querySelector("[data-del]").addEventListener("click", () => { S.del("items", id); s.close(); toast("Quitado", { action: "Deshacer", onAction: () => S.put("items", id, i) }); });
}

function listSheet(id) {
  const l = id ? S.get("lists", id) : null;
  const s = sheet(l ? "Lista" : "Nueva lista", html`<form style="display:grid;gap:14px">
    <label class="field"><span>Nombre</span><input type="text" name="name" value="${l ? l.name : ""}" maxlength="60" required placeholder="Súper, Farmacia, Para el cole…" autofocus></label>
    <div class="foot">${l ? html`<button class="btn danger" type="button" data-del>${icon("trash-2", "sm")}Borrar la lista</button>` : ""}<button class="btn pri" type="submit">Guardar</button></div></form>`);
  s.el.querySelector("form").addEventListener("submit", (ev) => {
    ev.preventDefault();
    const name = ev.target.name.value.trim();
    if (!name) return;
    const nid = id || S.newId("l");
    S.put("lists", nid, { ...(l || { kind: "compra", order: shopLists().length }), name });
    view.list = nid;
    s.close();
  });
  const del = s.el.querySelector("[data-del]");
  if (del) del.addEventListener("click", async () => {
    if (!(await confirmSheet("Borrar la lista", `Se borrará «${l.name}» con todo lo que tiene.`, { yes: "Borrar", danger: true }))) return;
    S.list("items").filter((i) => i.list === id).forEach((i) => S.del("items", i.id));
    S.del("lists", id);
    view.list = null;
    s.close();
  });
}

export function bind(root, rerender) {
  on(root, "click", "[data-list]", (el) => { view.list = el.dataset.list; rerender(); });
  on(root, "click", "[data-newlist]", () => listSheet(null));
  on(root, "click", "[data-editlist]", () => listSheet(view.list));
  on(root, "click", "[data-staples]", () => staplesSheet());
  on(root, "click", "[data-item]", (el) => itemSheet(el.dataset.item));
  on(root, "change", "[data-tick]", (el) => {
    const i = S.get("items", el.dataset.tick);
    if (i) S.put("items", el.dataset.tick, { ...i, done: el.checked, by: ctx.myMember });
  });
  on(root, "click", "[data-clear]", () => {
    const done = S.list("items").filter((i) => i.list === view.list && i.done);
    done.forEach((i) => S.del("items", i.id));
    toast(`${done.length} quitadas de la lista`, { action: "Deshacer", onAction: () => done.forEach(({ id, ...d }) => S.put("items", id, d)) });
  });
  root.addEventListener("submit", (ev) => {
    if (!ev.target.matches("[data-add]")) return;
    ev.preventDefault();
    const input = ev.target.t;
    const parts = input.value.split(/,|\n/).map((x) => x.trim()).filter(Boolean);
    parts.forEach((p) => addItem(view.list, p));
    input.value = "";
    input.focus();
  });
}
