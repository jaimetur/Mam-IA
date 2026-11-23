// The app's repetitions and reminders: the same cases as tests/test_push_and_web.py (server), so both agree.
// Run with TZ=Europe/Madrid (node --test tests/frontend/ does it through the script below).
import { test } from "node:test";
import assert from "node:assert/strict";
import { occurrences, alarms, expand, conflicts, nextAfter, ruleText, ymd } from "../../src/frontend/app/js/dates.js";

process.env.TZ = "Europe/Madrid";
const MON = "2026-11-23";

test("occurrences", () => {
  const weekly = { freq: "weekly", every: 1, days: [0, 2] };
  assert.deepEqual(occurrences(MON, weekly, MON, "2026-12-06"), ["2026-11-23", "2026-11-25", "2026-11-30", "2026-12-02"]);
  assert.deepEqual(occurrences(MON, { freq: "weekly", every: 2 }, MON, "2026-12-21"), [MON, "2026-12-07", "2026-12-21"]);
  assert.deepEqual(occurrences("2026-01-31", { freq: "monthly", every: 1 }, "2026-01-01", "2026-05-31"), ["2026-01-31", "2026-03-31", "2026-05-31"]);
  assert.deepEqual(occurrences(MON, { freq: "daily", every: 1, until: "2026-11-25" }, MON, "2026-12-02"), [MON, "2026-11-24", "2026-11-25"]);
  assert.deepEqual(occurrences(MON, weekly, MON, "2026-11-29", ["2026-11-25"]), [MON]);
  assert.equal(nextAfter(MON, weekly, MON), "2026-11-25");
  assert.equal(ruleText(weekly), "Los lunes y miércoles");
  assert.equal(ruleText({ freq: "weekly", every: 1, days: [0, 1, 2, 3, 4] }), "De lunes a viernes");
});

test("dates stay local (the old app put events a day late in Spain)", () => {
  assert.equal(ymd(new Date(2026, 10, 23, 0, 0)), "2026-11-23");
  const occ = expand({ e: { title: "Reunión", start: "2026-11-23T10:00" } }, MON, "2026-11-29");
  assert.deepEqual(occ.map((o) => o.day), ["2026-11-23"]);
});

test("alarms of events and tasks", () => {
  const docs = {
    members: { mU: { name: "Lucas" }, mP: { name: "Pablo" } },
    events: {
      e1: { title: "Dentista", start: "2026-11-26T17:30", who: ["mU"], driver: "mP", remind: 60 },
      e2: { title: "Natación", start: "2026-11-23T16:30", repeat: { freq: "weekly", every: 1, days: [0, 2] }, remind: 30 },
      e3: { title: "Excursión", start: "2026-11-27", allDay: true, remind: 1440 },
      e4: { title: "Sin aviso", start: "2026-11-26T10:00" },
    },
    tasks: { t1: { title: "Pagar el comedor", due: "2026-11-24", time: "10:00", remind: 0 }, t2: { title: "Hecha", due: "2026-11-24", remind: 0, done: true } },
  };
  const t0 = new Date(2026, 10, 23, 0, 0).getTime();
  const got = Object.fromEntries(alarms(docs, t0, t0 + 7 * 86400000, null).map((a) => [a.id, a]));
  assert.deepEqual(Object.keys(got).sort(), ["ev:e1:2026-11-26", "ev:e2:2026-11-23", "ev:e2:2026-11-25", "ev:e3:2026-11-27", "tk:t1:2026-11-24"]);
  assert.equal(got["ev:e1:2026-11-26"].at, new Date(2026, 10, 26, 16, 30).getTime());
  assert.equal(got["ev:e1:2026-11-26"].title, "Dentista · Lucas");
  assert.equal(got["ev:e1:2026-11-26"].body, "17:30 · lleva Pablo");
  assert.equal(got["ev:e3:2026-11-27"].at, new Date(2026, 10, 26, 9, 0).getTime());
});

test("two plans at the same time for different kids clash", () => {
  const ev = {
    a: { title: "Natación", start: "2026-11-25T16:30", who: ["mI"], pickup: "mL" },
    b: { title: "Pediatra", start: "2026-11-25T17:00", who: ["mU"] },
    c: { title: "Cena", start: "2026-11-25T21:00", who: ["mU"] },
  };
  const cs = conflicts(expand(ev, MON, "2026-11-29"));
  assert.equal(cs.length, 1);
  assert.deepEqual([cs[0].a.ev.title, cs[0].b.ev.title], ["Natación", "Pediatra"]);
});
