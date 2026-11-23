// The playful touches: an emoji for each kind of plan or task, and a little confetti when something gets done.
import { html } from "./ui.js";

export const CAT_EMOJI = {
  casa: "🏠", peques: "🧸", cole: "🎒", salud: "🩺", trabajo: "💼", compras: "🛍️", comidas: "🍽️", ocio: "🎉",
  pareja: "💞", yo: "🧘", papeleo: "📄", otros: "✨",
};

/** An emoji for a plan or task: from its title when it says what it is (swimming, a birthday…), else from its
    category (so plans look alive from the start). */
export function emojiOf(item) {
  const t = ((item && item.title) || "").toLowerCase();
  const guess = [
    [/cumple|fiesta|celebra/, "🎂"], [/natación|piscina|nadar/, "🏊"], [/fútbol|futbol|partido|baloncesto|deporte|entreno/, "⚽"],
    [/dentista|médic|medic|pediatra|vacuna|hospital|cita/, "🩺"], [/cole|colegio|excursión|excursion|tutor|clase/, "🎒"],
    [/reunión|reunion|trabajo|oficina|llamada/, "💼"], [/compra|super|mercado/, "🛒"], [/cena|comida|desayuno|restaurante/, "🍽️"],
    [/inglés|ingles|música|musica|piano|baile|danza|ballet/, "🎵"], [/yoga|gimnasio|gym|correr/, "🧘"], [/viaje|vuelo|tren|vacaciones/, "✈️"],
    [/pagar|recibo|banco|seguro|itv|papeles|firmar/, "📄"], [/basura|limpiar|lavadora|plancha|casa/, "🧹"],
  ].find(([re]) => re.test(t));
  return guess ? guess[1] : (item && CAT_EMOJI[item.cat]) || "";
}

/** The title of a plan or task with its emoji in front. What the family writes is never translated (data-noi18n). */
export const evTitle = (item) => {
  const e = emojiOf(item);
  return html`${e ? html`<span class="emo" aria-hidden="true">${e}</span>` : ""}<span data-noi18n>${item.title}</span>`;
};

const COLORS = ["#E8577D", "#7B61D6", "#16A085", "#F08A4B", "#F5C542", "#4F9DE8"];

/** A small burst of confetti from an element (respecting "reduce motion"). */
export function confetti(from) {
  if (!from || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const r = from.getBoundingClientRect();
  const x = r.left + r.width / 2, y = r.top + r.height / 2;
  const layer = document.createElement("div");
  layer.className = "confetti";
  layer.setAttribute("aria-hidden", "true");
  for (let i = 0; i < 18; i++) {
    const p = document.createElement("i");
    const a = (Math.PI * 2 * i) / 18 + Math.random() * 0.4;
    const d = 40 + Math.random() * 50;
    p.style.cssText = `left:${x}px;top:${y}px;background:${COLORS[i % COLORS.length]};--dx:${Math.cos(a) * d}px;--dy:${Math.sin(a) * d - 30}px;--rot:${Math.random() * 540}deg`;
    layer.appendChild(p);
  }
  document.body.appendChild(layer);
  setTimeout(() => layer.remove(), 900);
}
