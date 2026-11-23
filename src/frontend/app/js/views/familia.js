// Familia: the people of the family (with or without an account), invitations to join, and who manages it.
import * as S from "../store.js";
import { api } from "../api.js";
import { html, icon, avatar, on, sheet, toast, confirmSheet, formData, esc } from "../ui.js";
import { ctx } from "../ctx.js";

const COLORS = ["c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8"];

async function reloadFamily(rerender) {
  try { ctx.family = await api("/api/family"); } catch (e) { toast(e.message, { error: true }); }
  rerender && rerender();
}

export function memberSheet(id, defaults = {}) {
  const m = id ? S.get("members", id) : null;
  const used = S.members().map((x) => x.color);
  const v = { name: "", kind: "adult", color: COLORS.find((c) => !used.includes(c)) || "c8", ...defaults, ...(m || {}) };
  const s = sheet(m ? m.name : v.kind === "kid" ? "Nuevo peque" : "Nueva persona", html`<form style="display:grid;gap:14px" autocomplete="off">
    <label class="field"><span>Nombre</span><input type="text" name="name" value="${v.name}" maxlength="40" required autofocus placeholder="Inés"></label>
    <div class="field"><span>Es</span><div class="seg" role="radiogroup">
      <label style="display:contents"><input class="sr" type="radio" name="kind" value="adult" ${v.kind !== "kid" ? "checked" : ""}><button type="button" data-k="adult" aria-pressed="${v.kind !== "kid"}">Adulto</button></label>
      <label style="display:contents"><input class="sr" type="radio" name="kind" value="kid" ${v.kind === "kid" ? "checked" : ""}><button type="button" data-k="kid" aria-pressed="${v.kind === "kid"}">Peque</button></label></div></div>
    <div class="field"><span>Su color</span><div class="swatches">${COLORS.map((c) => html`<button type="button" data-c="${c}" aria-pressed="${c === v.color}" aria-label="Color ${c.slice(1)}" style="background:var(--${c})"></button>`)}</div>
      <input type="hidden" name="color" value="${v.color}"></div>
    ${m && m.userId ? html`<p class="muted" style="margin:0">${icon("user", "xs")} Tiene su propia cuenta.</p>` : ""}
    <div class="foot">${m && !m.userId ? html`<button class="btn danger" type="button" data-del>${icon("trash-2", "sm")}Quitar</button>` : ""}<button class="btn pri" type="submit">Guardar</button></div></form>`);
  const form = s.el.querySelector("form");
  s.el.addEventListener("click", (ev) => {
    const k = ev.target.closest("[data-k]");
    if (k) { form.querySelector(`input[value=${k.dataset.k}]`).checked = true; s.el.querySelectorAll("[data-k]").forEach((b) => b.setAttribute("aria-pressed", b === k)); }
    const c = ev.target.closest("[data-c]");
    if (c) { form.color.value = c.dataset.c; s.el.querySelectorAll("[data-c]").forEach((b) => b.setAttribute("aria-pressed", b === c)); }
  });
  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    const d = formData(form);
    if (!d.name.trim()) return;
    const nid = id || S.newId("m");
    S.put("members", nid, { ...(m || { order: S.members().length }), name: d.name.trim(), kind: d.kind, color: d.color });
    s.close();
  });
  const del = s.el.querySelector("[data-del]");
  if (del) del.addEventListener("click", async () => {
    if (!(await confirmSheet(`Quitar a ${m.name}`, "Sus planes y tareas se quedan, pero sin su nombre.", { yes: "Quitar", danger: true }))) return;
    S.del("members", id);
    s.close();
  });
}

function inviteSheet(memberId, rerender) {
  const m = memberId ? S.get("members", memberId) : null;
  const s = sheet(m ? `Invitar a ${m.name}` : "Invitar a una persona adulta", html`<form style="display:grid;gap:14px" autocomplete="off">
    <p class="muted" style="margin:0">Tendrá su propia cuenta y verá y apuntará lo mismo que tú. No paga nada: la familia ya tiene Mam-IA.</p>
    <label class="field"><span>Su correo (opcional: si no, comparte tú el enlace)</span><input type="email" name="email" maxlength="254" placeholder="pablo@correo.com"></label>
    <div class="foot"><button class="btn pri" type="submit">${icon("user-plus", "sm")}Crear invitación</button></div></form>`);
  s.el.querySelector("form").addEventListener("submit", async (ev) => {
    ev.preventDefault();
    try {
      const r = await api("/api/family/invites", { method: "POST", body: { email: ev.target.email.value.trim(), memberId } });
      const text = `Te invito a organizar la familia con Mam-IA: ${r.link}`;
      s.body.innerHTML = html`<p style="margin:0">${r.sent ? "Le hemos enviado un correo con la invitación. También puedes mandarle este enlace:" : "Mándale este enlace por WhatsApp o como prefieras (vale 14 días):"}</p>
        <input type="text" readonly value="${r.link}" aria-label="Enlace de invitación" data-link>
        <div class="btns"><button class="btn pri" type="button" data-copy>${icon("copy", "sm")}Copiar enlace</button>
        ${navigator.share ? html`<button class="btn" type="button" data-share>${icon("share-2", "sm")}Compartir</button>` : ""}
        <a class="btn" href="https://wa.me/?text=${encodeURIComponent(text)}" target="_blank" rel="noopener">WhatsApp</a></div>`.toString();
      s.body.querySelector("[data-copy]").addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(r.link); toast("Enlace copiado"); }
        catch (e) { const i = s.body.querySelector("[data-link]"); i.select(); }
      });
      const sh = s.body.querySelector("[data-share]");
      if (sh) sh.addEventListener("click", () => navigator.share({ title: "Mam-IA", text, url: r.link }).catch(() => {}));
      reloadFamily(rerender);
    } catch (e) { toast(e.message, { error: true }); }
  });
}

export function render(root) {
  const f = ctx.family;
  const me = ctx.me;
  const admin = me.role === "admin";
  const owner = f.ownerId === me.id;
  const ms = S.members();
  const accounts = f.accounts || [];
  const accOf = (m) => accounts.find((a) => a.memberId === m.id) || (m.userId && accounts.find((a) => a.id === m.userId));
  root.innerHTML = html`
    <header class="head"><div><p class="kicker">${ms.length} de ${f.maxMembers} personas</p><h1>${f.name}</h1></div>
      ${admin ? html`<div class="actions"><button class="btn sm" type="button" data-rename>${icon("pencil", "sm")}Nombre</button></div>` : ""}</header>
    <section class="card"><h2 class="card-h">Personas <span class="btns">
        <button class="btn sm" type="button" data-add="kid">${icon("baby", "sm")}Peque</button>
        <button class="btn sm" type="button" data-add="adult">${icon("plus", "sm")}Adulto</button></span></h2>
      <div class="list">${ms.map((m) => { const a = accOf(m); return html`<div class="row">${avatar(m)}
        <button class="txt grow" type="button" data-member="${m.id}"><span class="title">${m.name}${a && a.id === me.id ? " (tú)" : ""}</span>
          <span class="sub">${m.kind === "kid" ? "Peque" : a ? html`${a.email}${a.owner ? html` · <span class="tag acc">Paga la familia</span>` : a.role === "admin" ? " · administra" : ""}` : "Sin cuenta"}</span></button>
        ${m.kind !== "kid" && !a && admin ? html`<button class="btn sm" type="button" data-invite="${m.id}">${icon("mail", "sm")}Invitar</button>` : ""}
        ${a && admin && a.id !== me.id ? html`<button class="icon-btn ghost" type="button" data-acc="${a.id}" aria-label="Opciones de ${a.name}">${icon("ellipsis")}</button>` : ""}
      </div>`; })}</div>
      ${admin ? html`<button class="btn" type="button" data-invite="">${icon("user-plus", "sm")}Invitar a otra persona adulta</button>` : ""}
    </section>
    ${(f.invites || []).length ? html`<section class="card"><h2>Invitaciones pendientes</h2><div class="list">
      ${f.invites.map((i) => html`<div class="row"><span class="grow"><span>${i.email || (S.get("members", i.memberId) || {}).name || "Enlace sin correo"}</span>
        <span class="sub">Caduca el ${new Date(i.expires).toLocaleDateString("es-ES", { day: "numeric", month: "long" })}</span></span>
        ${admin ? html`<button class="btn sm" type="button" data-uninvite="${i.id}">Anular</button>` : ""}</div>`)}</div></section>` : ""}
    <section class="card"><h2>Cómo funciona</h2>
      <p class="muted" style="margin:0">Las personas adultas pueden tener su propia cuenta para ver y apuntar desde su móvil. Los peques son perfiles:
      sirven para apuntarles planes, tareas y su ficha. Todo se comparte al momento entre los móviles de la familia.</p>
      ${owner ? "" : html`<p class="muted" style="margin:0">La suscripción la gestiona ${(accounts.find((a) => a.owner) || {}).name || "quien paga la familia"}.</p>`}</section>`;
}

function accountSheet(userId, rerender) {
  const a = (ctx.family.accounts || []).find((x) => x.id === userId);
  if (!a) return;
  const owner = ctx.family.ownerId === ctx.me.id;
  const s = sheet(a.name, html`<div class="btns" style="display:grid;gap:8px">
    <button class="btn" type="button" data-role="${a.role === "admin" ? "member" : "admin"}">${a.role === "admin" ? "Quitar permiso para administrar la familia" : "Permitir que administre la familia"}</button>
    ${owner ? html`<button class="btn" type="button" data-transfer>Pasarle la familia (pagará la suscripción)</button>` : ""}
    <button class="btn danger" type="button" data-remove>Quitar su cuenta de la familia</button></div>`);
  const act = async (fn) => { try { ctx.family = await fn(); s.close(); rerender(); } catch (e) { toast(e.message, { error: true }); } };
  s.el.querySelector("[data-role]").addEventListener("click", (ev) => act(() => api(`/api/family/accounts/${userId}`, { method: "PUT", body: { role: ev.currentTarget.dataset.role } })));
  const tr = s.el.querySelector("[data-transfer]");
  if (tr) tr.addEventListener("click", async () => {
    if (!(await confirmSheet("Pasar la familia", `${a.name} será quien gestione y pague la suscripción. Tú seguirás en la familia.`, { yes: "Pasar la familia" }))) return;
    act(() => api("/api/family/transfer", { method: "POST", body: { userId } }));
  });
  s.el.querySelector("[data-remove]").addEventListener("click", async () => {
    if (!(await confirmSheet(`Quitar la cuenta de ${a.name}`, "Ya no podrá entrar. Seguirá en la familia como persona sin cuenta, con sus planes y tareas.", { yes: "Quitar la cuenta", danger: true }))) return;
    act(() => api(`/api/family/accounts/${userId}`, { method: "DELETE" }));
  });
}

export function bind(root, rerender) {
  on(root, "click", "[data-add]", (el) => memberSheet(null, { kind: el.dataset.add }));
  on(root, "click", "[data-member]", (el) => {
    const m = S.get("members", el.dataset.member);
    if (m && m.kind === "kid") import("./peques.js").then((p) => p.kidSheet(el.dataset.member));
    else memberSheet(el.dataset.member);
  });
  on(root, "click", "[data-invite]", (el) => inviteSheet(el.dataset.invite || null, rerender));
  on(root, "click", "[data-uninvite]", async (el) => {
    try { ctx.family = await api(`/api/family/invites/${el.dataset.uninvite}`, { method: "DELETE" }); rerender(); } catch (e) { toast(e.message, { error: true }); }
  });
  on(root, "click", "[data-acc]", (el) => accountSheet(Number(el.dataset.acc), rerender));
  on(root, "click", "[data-rename]", () => {
    const s = sheet("Nombre de la familia", html`<form style="display:grid;gap:14px"><label class="field"><span>Nombre</span>
      <input type="text" name="name" value="${ctx.family.name}" maxlength="60" required autofocus></label>
      <div class="foot"><button class="btn pri" type="submit">Guardar</button></div></form>`);
    s.el.querySelector("form").addEventListener("submit", async (ev) => {
      ev.preventDefault();
      try { ctx.family = await api("/api/family", { method: "PUT", body: { name: ev.target.name.value } }); s.close(); rerender(); }
      catch (e) { toast(e.message, { error: true }); }
    });
  });
}

export const refresh = reloadFamily;
export { esc };
