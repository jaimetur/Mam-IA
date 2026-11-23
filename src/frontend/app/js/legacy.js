// Bring the data of the first Mam-IA (kept only in the browser, key "mam-ia-state") into the family.
import * as S from "./store.js";

const KEY = "mam-ia-state";
const AREA = { comidas: "comidas", compras: "compras", familia: "casa", trabajo: "trabajo", limpieza: "casa", viajes: "ocio",
  ocio: "ocio", escolar: "cole", medico: "salud", belleza: "yo", pareja: "pareja", finanzas: "papeleo" };

function old() {
  try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch (e) { return null; }
}

export const hasOldData = () => {
  const o = old();
  return !!(o && !o.imported && ((o.tasks || []).length || (o.events || []).length || (o.lists || []).length));
};

/** Returns how many things were brought. The old data is marked as imported (not deleted). */
export function importOld() {
  const o = old();
  if (!o || o.imported) return 0;
  let n = 0;
  const mid = {};
  const mine = S.members();
  for (const m of (o.family && o.family.members) || []) {
    const same = mine.find((x) => x.name.toLowerCase() === String(m.name || "").toLowerCase());
    if (same) { mid[m.id] = same.id; continue; }
    if (S.members().length >= 8 || !m.name) continue;
    const id = S.newId("m");
    S.put("members", id, { name: String(m.name).slice(0, 40), kind: /miembro/i.test(m.role || "") ? "kid" : "adult", color: `c${(S.members().length % 8) + 1}` });
    mid[m.id] = id; n++;
  }
  for (const t of o.tasks || []) {
    if (!t.title) continue;
    S.put("tasks", S.newId("t"), { title: String(t.title).slice(0, 160), who: mid[t.assigneeId] || null, due: t.dueDate || null,
      done: t.status === "hecha", prio: t.priority === "alta" ? "alta" : "normal", cat: AREA[t.area] || null });
    n++;
  }
  for (const e of o.events || []) {
    if (!e.title || !e.start) continue;
    S.put("events", S.newId("e"), { title: String(e.title).slice(0, 120), start: e.start.slice(0, 16), end: e.end ? e.end.slice(0, 16) : null,
      who: (e.memberIds || []).map((x) => mid[x]).filter(Boolean), cat: AREA[e.area] || null, remind: 60 });
    n++;
  }
  for (const l of o.lists || []) {
    const lid = S.newId("l");
    S.put("lists", lid, { name: String(l.title || "Lista").slice(0, 60), kind: "compra" });
    for (const it of l.items || []) {
      if (!it.text) continue;
      S.put("items", S.newId("i"), { list: lid, text: String(it.text).slice(0, 120), done: !!it.done, section: "Otros", src: "manual" });
      n++;
    }
  }
  for (const r of o.reminders || []) {
    if (!r.title || !r.datetime) continue;
    S.put("tasks", S.newId("t"), { title: String(r.title).slice(0, 160), due: r.datetime.slice(0, 10), time: r.datetime.slice(11, 16) || null, remind: 0, done: !!r.done });
    n++;
  }
  try { localStorage.setItem(KEY, JSON.stringify({ ...o, imported: true })); } catch (e) { /* ignore */ }
  return n;
}
