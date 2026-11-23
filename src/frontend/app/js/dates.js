// Dates always in local time ("YYYY-MM-DD" and "HH:MM" strings), never through toISOString (UTC): the old app put
// every event a day late in Spain because of that. Repetitions and reminders follow the same rules as the server
// (src/backend/app/push/recur.py); both are tested with the same cases.

export const WEEKDAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
export const WD_SHORT = ["L", "M", "X", "J", "V", "S", "D"];
export const MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
export const ALL_DAY_HOUR = 9;

const pad = (n) => String(n).padStart(2, "0");

export function ymd(d) { return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; }
export function hm(d) { return `${pad(d.getHours())}:${pad(d.getMinutes())}`; }
export function parse(s) {
  const [y, m, d] = s.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}
export function at(day, time) {
  const d = parse(day);
  const [h, m] = (time || `${ALL_DAY_HOUR}:00`).split(":").map(Number);
  d.setHours(h, m, 0, 0);
  return d;
}
export function today(now = new Date()) { return ymd(now); }
export function addDays(s, n) { const d = parse(s); d.setDate(d.getDate() + n); return ymd(d); }
export function diffDays(a, b) { return Math.round((parse(a) - parse(b)) / 86400000); }
/** Monday = 0 … Sunday = 6. */
export function weekday(s) { return (parse(s).getDay() + 6) % 7; }
export function weekStart(s) { return addDays(s, -weekday(s)); }
export function monthStart(s) { return s.slice(0, 8) + "01"; }
export function addMonths(s, n) {
  const d = parse(s);
  const t = new Date(d.getFullYear(), d.getMonth() + n, 1);
  const last = new Date(t.getFullYear(), t.getMonth() + 1, 0).getDate();
  t.setDate(Math.min(d.getDate(), last));
  return ymd(t);
}

/** "lunes 23 de noviembre", "Hoy", "Mañana"… */
export function longDay(s, ref = today()) {
  const d = parse(s);
  return `${WEEKDAYS[weekday(s)]} ${d.getDate()} de ${MONTHS[d.getMonth()]}`;
}
export function relDay(s, ref = today()) {
  const n = diffDays(s, ref);
  if (n === 0) return "Hoy";
  if (n === 1) return "Mañana";
  if (n === -1) return "Ayer";
  if (n > 1 && n < 7) return cap(WEEKDAYS[weekday(s)]);
  const d = parse(s);
  return `${WD_SHORT[weekday(s)]} ${d.getDate()} ${MONTHS[d.getMonth()].slice(0, 3)}`;
}
export const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

// ---------- repetitions ----------

export function occursOn(start, rule, day) {
  if (day < start) return false;
  if (!rule) return day === start;
  if (rule.until && day > rule.until) return false;
  const every = Math.max(1, rule.every || 1);
  if (rule.freq === "daily") return diffDays(day, start) % every === 0;
  if (rule.freq === "weekly") {
    const days = rule.days && rule.days.length ? rule.days : [weekday(start)];
    if (!days.includes(weekday(day))) return false;
    return Math.floor(diffDays(day, weekStart(start)) / 7) % every === 0;
  }
  const a = parse(start), b = parse(day);
  if (rule.freq === "monthly") {
    const months = (b.getFullYear() - a.getFullYear()) * 12 + b.getMonth() - a.getMonth();
    return b.getDate() === a.getDate() && months % every === 0;
  }
  if (rule.freq === "yearly") {
    return b.getMonth() === a.getMonth() && b.getDate() === a.getDate() && (b.getFullYear() - a.getFullYear()) % every === 0;
  }
  return false;
}

/** Days between first and last (both included) on which it happens. */
export function occurrences(start, rule, first, last, skip = []) {
  const out = [];
  let d = first > start ? first : start;
  while (d <= last) {
    if (occursOn(start, rule, d) && !skip.includes(d)) out.push(d);
    d = addDays(d, 1);
  }
  return out;
}

/** The next day after `day` on which a repeating task is due (for rolling it forward when done). */
export function nextAfter(start, rule, day) {
  if (!rule) return null;
  let d = addDays(day, 1);
  for (let i = 0; i < 800; i++, d = addDays(d, 1)) {
    if (rule.until && d > rule.until) return null;
    if (occursOn(start, rule, d)) return d;
  }
  return null;
}

export function ruleText(rule) {
  if (!rule) return "";
  const n = rule.every || 1;
  let t;
  if (rule.freq === "daily") t = n === 1 ? "Cada día" : `Cada ${n} días`;
  else if (rule.freq === "weekly") {
    const ds = [...(rule.days || [])].sort();
    const plural = (d) => (d >= 5 ? WEEKDAYS[d] + "s" : WEEKDAYS[d]);
    const names = ds.map(plural);
    const list = names.length > 1 ? names.slice(0, -1).join(", ") + " y " + names[names.length - 1] : names[0];
    if (ds.length === 7) t = n === 1 ? "Cada día" : `Cada ${n} semanas, todos los días`;
    else if (ds.join() === "0,1,2,3,4") t = n === 1 ? "De lunes a viernes" : `Cada ${n} semanas, de lunes a viernes`;
    else if (!list) t = n === 1 ? "Cada semana" : `Cada ${n} semanas`;
    else t = n === 1 ? `Los ${list}` : `Cada ${n} semanas: ${list}`;
  } else if (rule.freq === "monthly") t = n === 1 ? "Cada mes" : `Cada ${n} meses`;
  else t = n === 1 ? "Cada año" : `Cada ${n} años`;
  return rule.until ? `${t}, hasta el ${parse(rule.until).getDate()} de ${MONTHS[parse(rule.until).getMonth()]}` : t;
}

// ---------- events of a day ----------

/** The occurrences of the events between two days: [{ev, id, day, time, end}] sorted by day and time. */
export function expand(events, first, last) {
  const out = [];
  for (const [id, e] of Object.entries(events)) {
    if (!e.start) continue;
    const start = e.start.slice(0, 10);
    const span = e.end && !e.repeat ? Math.max(0, diffDays(e.end.slice(0, 10), start)) : 0;
    const days = e.repeat
      ? occurrences(start, e.repeat, first, last, e.exdates || [])
      : (start <= last && addDays(start, span) >= first ? [start] : []);
    for (const day of days) {
      const time = e.allDay || e.start.length === 10 ? null : e.start.slice(11, 16);
      const end = e.end && e.end.length > 10 ? e.end.slice(11, 16) : null;
      // events of several days show on each of their days
      for (let k = 0; k <= span; k++) {
        const d = addDays(day, k);
        if (d >= first && d <= last) out.push({ ev: e, id, day: d, time: k === 0 ? time : null, end, cont: k > 0 });
      }
    }
  }
  return out.sort((a, b) => (a.day + (a.time || "")).localeCompare(b.day + (b.time || "")));
}

function minutes(t) { const [h, m] = t.split(":").map(Number); return h * 60 + m; }

/** Plans of the same day at the same time that involve the same person (as attendee, driver or pickup). */
export function conflicts(occs) {
  const out = [];
  const timed = occs.filter((o) => o.time);
  for (let i = 0; i < timed.length; i++) {
    for (let j = i + 1; j < timed.length; j++) {
      const a = timed[i], b = timed[j];
      if (a.day !== b.day) continue;
      const aEnd = a.end ? minutes(a.end) : minutes(a.time) + 60;
      const bEnd = b.end ? minutes(b.end) : minutes(b.time) + 60;
      if (!(minutes(a.time) < bEnd && minutes(b.time) < aEnd)) continue;
      const people = (o) => new Set([...(o.ev.who || []), o.ev.driver, o.ev.pickup].filter(Boolean));
      const pa = people(a), pb = people(b);
      const shared = [...pa].filter((x) => pb.has(x));
      // two plans of different kids at the same time also clash when nobody is set to take each one
      const needsTwo = !shared.length && pa.size && pb.size && !(a.ev.driver && b.ev.driver && a.ev.driver !== b.ev.driver);
      if (shared.length || needsTwo) out.push({ a, b, shared });
    }
  }
  return out;
}

// ---------- reminders (Android alarms; the server sends the same ones by Web Push) ----------

export function alarms(docs, fromMs, toMs, myMember) {
  const members = docs.members || {};
  const name = (id) => (members[id] || {}).name || "";
  const out = [];
  const lo = ymd(new Date(fromMs - 15 * 86400000)), hi = ymd(new Date(toMs + 15 * 86400000));
  const mine = (who) => !myMember || !who.length || who.includes(myMember)
    || !who.some((w) => members[w] && members[w].userId);   // nobody with an account: everyone is told
  for (const [id, e] of Object.entries(docs.events || {})) {
    if (e.remind == null || !e.start) continue;
    const start = e.start.slice(0, 10);
    const time = e.allDay || e.start.length === 10 ? null : e.start.slice(11, 16);
    for (const day of occurrences(start, e.repeat || null, lo, hi, e.exdates || [])) {
      const t = at(day, time).getTime() - e.remind * 60000;
      if (t <= fromMs || t > toMs) continue;
      const who = [...new Set([...(e.who || []), e.driver, e.pickup].filter(Boolean))];
      if (!mine(who)) continue;
      const bits = [time || "Todo el día"];
      if (e.driver) bits.push(`lleva ${name(e.driver)}`);
      if (e.pickup) bits.push(`recoge ${name(e.pickup)}`);
      if (e.place) bits.push(e.place);
      const names = (e.who || []).map(name).filter(Boolean);
      out.push({ id: `ev:${id}:${day}`, at: t, title: e.title + (names.length ? " · " + names.join(", ") : ""),
                 body: bits.join(" · "), path: "/app#agenda" });
    }
  }
  for (const [id, t] of Object.entries(docs.tasks || {})) {
    if (t.remind == null || t.done || !t.due) continue;
    const when = at(t.due, t.time).getTime() - t.remind * 60000;
    if (when <= fromMs || when > toMs) continue;
    if (!mine(t.who ? [t.who] : [])) continue;
    out.push({ id: `tk:${id}:${t.due}`, at: when, title: t.title,
               body: (t.time || "Hoy") + (t.who && name(t.who) ? ` · ${name(t.who)}` : ""), path: "/app#tareas" });
  }
  return out.sort((a, b) => a.at - b.at);
}
