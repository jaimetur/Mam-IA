// Reminders that reach the phone: in the Android app, exact native alarms set through its bridge (MamIANative);
// in the browser, Web Push from the server (the service worker shows them).
import * as S from "./store.js";
import { api } from "./api.js";
import { alarms } from "./dates.js";
import { ctx } from "./ctx.js";
import { toast } from "./ui.js";

const DAYS_AHEAD = 14;
let pushOn = false;

export function notifyState() {
  const n = ctx.native;
  if (n) {
    let on = false;
    try { on = !!n.notificationsAllowed(); } catch (e) { /* old app */ }
    return { can: true, on, native: true };
  }
  const can = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  return { can, on: can && Notification.permission === "granted" && pushOn, native: false, denied: can && Notification.permission === "denied" };
}

function b64ToBytes(s) {
  const pad = "=".repeat((4 - (s.length % 4)) % 4);
  const raw = atob((s + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

async function webSubscribe() {
  const reg = await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    const { key } = await api("/api/push/key");
    sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToBytes(key) });
  }
  const j = sub.toJSON();
  await api("/api/push/subscribe", { method: "POST", body: { endpoint: j.endpoint, keys: j.keys } });
  pushOn = true;
}

/** Turn the reminders on in this device (asks the system for permission). */
export async function askNotifications() {
  const n = ctx.native;
  if (n) {
    try { n.askNotifications(); } catch (e) { toast("Actualiza la app de Android para activar los avisos.", { error: true }); }
    return;
  }
  const st = notifyState();
  if (!st.can) {
    toast("Este navegador no puede mostrar avisos. En iPhone, añade Mam-IA a la pantalla de inicio y ábrela desde ahí.", { error: true, ms: 7000 });
    return;
  }
  const perm = await Notification.requestPermission();
  if (perm !== "granted") { toast("Sin permiso para avisar. Puedes darlo en los ajustes del navegador.", { error: true }); return; }
  try {
    await webSubscribe();
    toast("Avisos activados en este dispositivo");
    window.dispatchEvent(new Event("mamia-redraw"));
  } catch (e) { toast(e.message || "No se han podido activar los avisos.", { error: true }); }
}

export async function testNotification() {
  if (ctx.native) {
    try {
      ctx.native.setAlarms(JSON.stringify([{ id: "prueba", at: Date.now() + 5000, title: "Mam-IA", body: "Así te avisaremos de lo que toca.", path: "/app" },
        ...currentAlarms()]));
      toast("En 5 segundos te llega un aviso de prueba");
    } catch (e) { toast("No se ha podido programar el aviso.", { error: true }); }
    return;
  }
  try { await api("/api/push/test", { method: "POST" }); toast("Aviso de prueba enviado"); }
  catch (e) { toast(e.message, { error: true }); }
}

function currentAlarms() {
  const now = Date.now();
  return alarms(S.docs(), now, now + DAYS_AHEAD * 86400000, ctx.myMember).slice(0, 200);
}

let lastSent = "";
/** Give the Android app the alarms of the next two weeks (it replaces the ones it had). */
export function syncNativeAlarms() {
  if (!ctx.native) return;
  const json = JSON.stringify(currentAlarms());
  if (json === lastSent) return;
  lastSent = json;
  try { ctx.native.setAlarms(json); } catch (e) { /* old app */ }
}

export async function initNotify() {
  if (ctx.native) {
    window.addEventListener("mamia-notifications", () => window.dispatchEvent(new Event("mamia-redraw")));
    return;
  }
  if (!("serviceWorker" in navigator)) return;
  try {
    const reg = await navigator.serviceWorker.ready;
    const sub = reg.pushManager && (await reg.pushManager.getSubscription());
    if (sub && Notification.permission === "granted") {
      pushOn = true;
      const j = sub.toJSON();   // tell the server again (the account may have changed on this device)
      api("/api/push/subscribe", { method: "POST", body: { endpoint: j.endpoint, keys: j.keys } }).catch(() => {});
    }
  } catch (e) { /* no push here */ }
}
