// Quick capture without AI: understands everyday Spanish like
//   "Dentista Lucas el jueves a las 17:30, lo lleva Pablo"   → event on Thursday 17:30 for Lucas, Pablo drives
//   "comprar leche y pan"                                     → two shopping items
//   "recuérdame llamar al seguro mañana a las 10"             → task tomorrow at 10:00 with a reminder
//   "natación Inés todos los lunes y miércoles a las 16:30"   → repeating event
// parse(text, members, todayStr) returns { kind, title, date, time, allDay, who, driver, pickup, repeat, remind,
// items, cat }. Pure function (tested in tests/frontend/parse.test.mjs).
import { addDays, addMonths, weekday } from "./dates.js";

const DAYS = { lunes: 0, martes: 1, miercoles: 2, jueves: 3, viernes: 4, sabado: 5, domingo: 6 };
const MONTHS = { enero: 1, febrero: 2, marzo: 3, abril: 4, mayo: 5, junio: 6, julio: 7, agosto: 8, septiembre: 9, setiembre: 9, octubre: 10, noviembre: 11, diciembre: 12 };
const NUM = { una: 1, uno: 1, dos: 2, tres: 3, cuatro: 4, cinco: 5, seis: 6, siete: 7, ocho: 8, nueve: 9, diez: 10, once: 11, doce: 12 };
const CATS = [
  ["salud", /\b(dentista|pediatra|medic[oa]|doctor[a]?|vacuna|revision|analisis|hospital|centro de salud|farmacia|oculista|fisio|logopeda|psicolog)/],
  ["cole", /\b(cole|colegio|escuela|guarderia|instituto|tutor[a]?|excursion|reunion de padres|deberes|examen|extraescolar|ampa|clase)/],
  ["ocio", /\b(cumple|cumpleanos|fiesta|cine|parque|piscina|natacion|futbol|baloncesto|ballet|danza|musica|teatro|zoo|merienda|partido|entrenamiento)/],
  ["trabajo", /\b(reunion|trabajo|oficina|cliente|llamada de trabajo|presentacion|entrega)/],
  ["papeleo", /\b(seguro|banco|hacienda|declaracion|renta|recibo|factura|itv|dni|pasaporte|ayuntamiento|notaria|gestoria|matricula|beca)/],
  ["casa", /\b(lavadora|limpiar|limpieza|tender|planchar|basura|fontanero|electricista|caldera|reparar|ordenar|aspirar|fregar)/],
  ["pareja", /\b(cena romantica|aniversario|cita con|plan en pareja)/],
  ["yo", /\b(peluqueria|manicura|depilacion|yoga|pilates|gimnasio|masaje|estetica|para mi)/],
];
const SHOP = /^(comprar|compra|anade a la compra|apunta en la compra|hay que comprar|falta|faltan|nos falta|nos faltan)\b/;
const REMIND = /^(recuerdame|recordarme|recordatorio|acuerdate de|que no se me olvide|no olvidar|no olvides)\b/;
const TASK = /^(tengo que|hay que|toca|pendiente|tarea)\b/;

export const fold = (s) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");

function cleanTitle(s) {
  s = s.replace(/\s+([,.;:])/g, "$1").replace(/\s{2,}/g, " ");
  // what is left at the ends once the date, time and people are taken out: commas and little words
  for (let i = 0, prev = null; i < 5 && s !== prev; i++) {
    prev = s;
    s = s.replace(/^[\s,.;:-]+|[\s,.;:-]+$/g, "").replace(/\s+(el|la|los|las|de|a|en|para|con|y|e)$/i, "").replace(/^(y|e)\s+/i, "");
  }
  return s.charAt(0).toUpperCase() + s.slice(1);
}

/** Remove the matched piece (by position in the folded text) from both the original and the folded text. */
function cut(st, m) {
  const i = m.index, j = m.index + m[0].length;
  st.orig = st.orig.slice(0, i) + " ".repeat(j - i) + st.orig.slice(j);
  st.f = st.f.slice(0, i) + " ".repeat(j - i) + st.f.slice(j);
}

function hour(h, m, part) {
  h = Number(h); m = Number(m || 0);
  if (part && /tarde|noche/.test(part) && h < 12) h += 12;
  if (part && /mediodia/.test(part) && h < 6) h += 12;
  if (!part && h >= 1 && h <= 7) h += 12;          // "a las 5" is five in the afternoon in a family agenda
  if (h > 23 || m > 59) return null;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function findTime(st) {
  const rx = [
    /\b(?:a las|a la|sobre las|hacia las|desde las)\s+(\d{1,2})(?:[:.h](\d{2}))?\s*(?:h\b|horas?\b)?(\s*(?:y media|y cuarto|menos cuarto))?(\s*de la (?:manana|tarde|noche)|\s*del mediodia)?/,
    /\b(\d{1,2})[:.](\d{2})\s*(?:h\b)?()(\s*de la (?:manana|tarde|noche))?/,
    /\b(\d{1,2})\s*h\b()()(\s*de la (?:manana|tarde|noche))?/,
    /\b(?:a las|a la)\s+(una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce)()(\s*(?:y media|y cuarto|menos cuarto))?(\s*de la (?:manana|tarde|noche)|\s*del mediodia)?/,
  ];
  for (const r of rx) {
    const m = st.f.match(r);
    if (!m) continue;
    let h = NUM[m[1]] ?? m[1], min = m[2] || "0";
    const frac = (m[3] || "").trim();
    if (frac === "y media") min = 30;
    else if (frac === "y cuarto") min = 15;
    else if (frac === "menos cuarto") { h = Number(h) - 1; min = 45; }
    const t = hour(h, min, (m[4] || "").trim());
    if (t) { cut(st, m); return t; }
  }
  const part = st.f.match(/\b(por la manana|a mediodia|por la tarde|por la noche|a primera hora)\b/);
  if (part) {
    cut(st, part);
    return { "por la manana": "10:00", "a mediodia": "13:30", "por la tarde": "17:00", "por la noche": "21:00", "a primera hora": "08:30" }[part[1]];
  }
  return null;
}

function findDate(st, ref) {
  let m;
  if ((m = st.f.match(/\bpasado manana\b/))) { cut(st, m); return addDays(ref, 2); }
  if ((m = st.f.match(/\b(hoy|esta tarde|esta noche|esta manana)\b/))) { cut(st, m); return ref; }
  // "por la mañana", "de la mañana" and "esta mañana" were taken before (time of day, today)
  if ((m = st.f.match(/\bmanana\b/))) { cut(st, m); return addDays(ref, 1); }
  if ((m = st.f.match(/\b(?:el\s+|este\s+)?(?:(?:proximo|siguiente)\s+)?(lunes|martes|miercoles|jueves|viernes|sabado|domingo)(?:\s+que viene|\s+proximo)?\b/))) {
    cut(st, m);
    // the next one from tomorrow on ("el lunes" said on a Monday is next week's)
    const n = (DAYS[m[1]] - weekday(ref) + 7) % 7 || 7;
    return addDays(ref, n);
  }
  if ((m = st.f.match(/\b(?:el\s+)?(?:dia\s+)?(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)(?:\s+de\s+(\d{4}))?\b/))) {
    cut(st, m);
    return dateFrom(ref, Number(m[1]), MONTHS[m[2]], m[3] && Number(m[3]));
  }
  if ((m = st.f.match(/\b(\d{1,2})\/(\d{1,2})(?:\/(\d{2,4}))?\b/))) {
    cut(st, m);
    return dateFrom(ref, Number(m[1]), Number(m[2]), m[3] && Number(m[3].length === 2 ? "20" + m[3] : m[3]));
  }
  if ((m = st.f.match(/\b(?:el\s+)?dia\s+(\d{1,2})\b/))) {
    cut(st, m);
    const d = Number(m[1]);
    const day = ref.slice(0, 8) + String(d).padStart(2, "0");
    return d >= Number(ref.slice(8)) ? day : addMonths(day, 1);
  }
  if ((m = st.f.match(/\b(?:dentro de|en)\s+(\d+|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)\s+(dias?|semanas?)\b/))) {
    cut(st, m);
    const n = Number(NUM[m[1]] ?? m[1]);
    return addDays(ref, m[2].startsWith("semana") ? n * 7 : n);
  }
  if ((m = st.f.match(/\b(este fin de semana|el fin de semana)\b/))) {
    cut(st, m);
    return addDays(ref, (5 - weekday(ref) + 7) % 7);
  }
  return null;
}

function dateFrom(ref, d, mo, y) {
  const ry = Number(ref.slice(0, 4));
  let year = y || ry;
  const s = (yy) => `${yy}-${String(mo).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
  if (mo < 1 || mo > 12 || d < 1 || d > 31) return null;
  if (!y && s(year) < ref) year += 1;
  return s(year);
}

function findRepeat(st) {
  let m;
  if ((m = st.f.match(/\b(?:todos los dias|cada dia|a diario|diariamente)\b/))) { cut(st, m); return { freq: "daily", every: 1 }; }
  if ((m = st.f.match(/\bde lunes a viernes\b|\bentre semana\b|\btodos los dias laborables\b/))) { cut(st, m); return { freq: "weekly", every: 1, days: [0, 1, 2, 3, 4] }; }
  m = st.f.match(/\b(?:todos los|todas las|cada|los)\s+((?:(?:lunes|martes|miercoles|jueves|viernes|sabados?|domingos?)(?:\s*,\s*|\s+y\s+|\s+)?)+)/);
  if (m && (/\b(todos|todas|cada)\b/.test(m[0]) || /,|\sy\s/.test(m[1]))) {
    const days = [...new Set(m[1].match(/lunes|martes|miercoles|jueves|viernes|sabado|domingo/g).map((d) => DAYS[d]))].sort();
    cut(st, m);
    return { freq: "weekly", every: 1, days };
  }
  if ((m = st.f.match(/\b(?:cada semana|todas las semanas|semanalmente)\b/))) { cut(st, m); return { freq: "weekly", every: 1 }; }
  if ((m = st.f.match(/\bcada (dos|2|tres|3) semanas\b/))) { cut(st, m); return { freq: "weekly", every: Number(NUM[m[1]] ?? m[1]) }; }
  if ((m = st.f.match(/\b(?:cada mes|todos los meses|mensualmente)\b/))) { cut(st, m); return { freq: "monthly", every: 1 }; }
  if ((m = st.f.match(/\b(?:cada ano|todos los anos|anualmente)\b/))) { cut(st, m); return { freq: "yearly", every: 1 }; }
  return null;
}

function findPeople(st, members) {
  const out = { who: [], driver: null, pickup: null };
  const byName = members.map((m) => ({ m, n: fold(m.name).trim() })).filter((x) => x.n).sort((a, b) => b.n.length - a.n.length);
  const rx = (n) => new RegExp(`\\b${n.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`);
  for (const { m, n } of byName) {
    let mm;
    const drive = st.f.match(new RegExp(`\\b(?:lo lleva|la lleva|los lleva|las lleva|lleva|llevara|que lo lleve|que la lleve|que los lleve|le lleva|llevar(?:la|lo|los|las)?)\\s+${rx(n).source.slice(2)}`));
    if (drive) { out.driver = m.id; cut(st, drive); continue; }
    const pick = st.f.match(new RegExp(`\\b(?:lo recoge|la recoge|los recoge|las recoge|recoge|que lo recoja|que la recoja|que los recoja|recogera)\\s+${rx(n).source.slice(2)}`));
    if (pick) { out.pickup = m.id; cut(st, pick); continue; }
    if ((mm = st.f.match(new RegExp(`\\b(?:para|de|con)\\s+${rx(n).source.slice(2)}`)))) { out.who.push(m.id); cut(st, mm); continue; }
    if ((mm = st.f.match(rx(n)))) { out.who.push(m.id); cut(st, mm); }
  }
  // "lo llevo yo" / "recojo yo"
  return out;
}

function findRemind(st) {
  const m = st.f.match(/\b(?:avisame|avisa(?:me)?|recuerdamelo)\s+(?:(\d+|una|media|un)\s*(minutos?|min|horas?|h|dias?)\s+antes|el dia antes|la vispera)\b/);
  if (!m) return null;
  cut(st, m);
  if (!m[1]) return 1440;
  const n = m[1] === "media" ? 0.5 : m[1] === "un" || m[1] === "una" ? 1 : Number(m[1]);
  return Math.round(/^h/.test(m[2]) ? n * 60 : /^d/.test(m[2]) ? n * 1440 : n);
}

export function guessCat(f) {
  for (const [cat, rx] of CATS) if (rx.test(f)) return cat;
  return null;
}

export function parse(text, members = [], ref) {
  const orig = String(text || "").replace(/\s+/g, " ").trim();
  const st = { orig, f: fold(orig) };
  const out = { kind: "task", title: "", date: null, time: null, allDay: false, who: [], driver: null, pickup: null,
                repeat: null, remind: null, items: [], cat: guessCat(st.f) };
  if (!orig) return out;
  let m;
  if ((m = st.f.match(SHOP))) {
    cut(st, m);
    out.kind = "shop";
    out.items = st.orig.split(/,|\by\b|\be\b|;|\n/).map((s) => cleanTitle(s.replace(/^\s*(de|del|unas?|unos?)\s+/i, ""))).filter(Boolean);
    out.title = out.items.join(", ");
    return out;
  }
  const remindWord = st.f.match(REMIND);
  if (remindWord) cut(st, remindWord);
  const taskWord = !remindWord && st.f.match(TASK);
  if (taskWord) cut(st, taskWord);
  out.repeat = findRepeat(st);
  out.time = findTime(st);
  out.date = findDate(st, ref);
  out.remind = findRemind(st);
  Object.assign(out, findPeople(st, members));
  if (out.repeat && !out.date) {
    out.date = ref;
    if (out.repeat.days && out.repeat.days.length) {   // the first of those days from today
      for (let i = 0; i < 7; i++) if (out.repeat.days.includes(weekday(addDays(ref, i)))) { out.date = addDays(ref, i); break; }
    }
  }
  if (remindWord) {
    out.kind = "reminder";
    if (out.remind == null) out.remind = 0;
    if (!out.date) out.date = out.time && out.time < new Date().toTimeString().slice(0, 5) ? addDays(ref, 1) : ref;
  } else if (taskWord) {
    out.kind = "task";
  } else if (out.time || out.driver || out.pickup || (out.date && out.cat && out.cat !== "casa" && out.cat !== "papeleo")) {
    out.kind = "event";
    if (!out.time) out.allDay = true;
  }
  if (out.kind === "event" && out.remind == null) out.remind = out.allDay ? 0 : 60;
  out.title = cleanTitle(st.orig.replace(/\s+,/g, ",")) || (out.who.length ? "Plan" : "");
  return out;
}
