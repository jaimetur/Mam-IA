// node --test tests/frontend — the quick-capture parser and the local dates of the app (src/frontend/app/js).
import { test } from "node:test";
import assert from "node:assert/strict";
import { parse } from "../../src/frontend/app/js/parse.js";

const M = [{ id: "mL", name: "Laura" }, { id: "mP", name: "Pablo" }, { id: "mI", name: "Inés" }, { id: "mU", name: "Lucas" }];
const REF = "2026-11-23";   // a Monday

test("event with person, day, time and driver", () => {
  const r = parse("Dentista Lucas el jueves a las 17:30, lo lleva Pablo", M, REF);
  assert.equal(r.kind, "event");
  assert.equal(r.title, "Dentista");
  assert.equal(r.date, "2026-11-26");
  assert.equal(r.time, "17:30");
  assert.deepEqual(r.who, ["mU"]);
  assert.equal(r.driver, "mP");
  assert.equal(r.cat, "salud");
  assert.equal(r.remind, 60);
});

test("what is left of the sentence makes a clean title", () => {
  const r = parse("Cumple de Vega el sábado a las 17:30, lo lleva Pablo y recoge Laura", M, REF);
  assert.equal(r.title, "Cumple de Vega");
  assert.equal(r.date, "2026-11-28");
  assert.equal(r.driver, "mP");
  assert.equal(r.pickup, "mL");
});

test("spoken times: five and a half in the afternoon", () => {
  assert.equal(parse("pediatra Inés mañana a las 5 y media", M, REF).time, "17:30");
  assert.equal(parse("reunión a las 9 de la mañana", M, REF).time, "09:00");
  assert.equal(parse("cena a las nueve de la noche", M, REF).time, "21:00");
  assert.equal(parse("excursión 26/11", M, REF).date, "2026-11-26");
  assert.equal(parse("cumple de Vega el 5 de diciembre", M, REF).date, "2026-12-05");
  assert.equal(parse("revisión el 3 de enero", M, REF).date, "2027-01-03");
  assert.equal(parse("mañana a las 10 llamar", M, REF).date, "2026-11-24");
  assert.equal(parse("el lunes reunión a las 18", M, REF).date, "2026-11-30");
});

test("repeating activity", () => {
  const r = parse("Natación Inés todos los lunes y miércoles a las 16:30", M, REF);
  assert.equal(r.kind, "event");
  assert.deepEqual(r.repeat, { freq: "weekly", every: 1, days: [0, 2] });
  assert.equal(r.date, "2026-11-23");
  assert.equal(r.title, "Natación");
  assert.deepEqual(r.who, ["mI"]);
});

test("shopping and reminders", () => {
  const s = parse("comprar leche, pan y 2 yogures", M, REF);
  assert.equal(s.kind, "shop");
  assert.deepEqual(s.items, ["Leche", "Pan", "2 yogures"]);
  const r = parse("recuérdame llamar al seguro mañana a las 10", M, REF);
  assert.equal(r.kind, "reminder");
  assert.equal(r.title, "Llamar al seguro");
  assert.equal(r.date, "2026-11-24");
  assert.equal(r.time, "10:00");
  assert.equal(r.remind, 0);
  const t = parse("tengo que firmar la autorización de la excursión", M, REF);
  assert.equal(t.kind, "task");
  assert.equal(t.title, "Firmar la autorización de la excursión");
});
