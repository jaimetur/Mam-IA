// The family's data on this device: a copy of the server's documents, the changes not sent yet, and the sync.
// Works offline: every change is applied here at once, kept in localStorage and sent when there is a connection.
// While the app is visible it asks the server for news every few seconds, so what one person ticks off the rest see.
import { api } from "./api.js";

const POLL_MS = 5000;
let key = null;
let state = { rev: 0, docs: {}, meta: {}, pending: [] };
const listeners = new Set();
let pushing = false, pulling = false, timer = null, dirtySoon = null;
export const status = { online: navigator.onLine, syncing: false, readOnly: false, lastError: null, ready: false };

function save() {
  try { localStorage.setItem(key, JSON.stringify(state)); } catch (e) { /* full or blocked: the server still has it */ }
}

function emit() {
  if (dirtySoon) return;
  dirtySoon = requestAnimationFrame(() => { dirtySoon = null; listeners.forEach((f) => f()); });
}

export function subscribe(fn) { listeners.add(fn); return () => listeners.delete(fn); }

export function init(familyId) {
  key = `mamia:fam:${familyId}`;
  try { state = { rev: 0, docs: {}, meta: {}, pending: [], ...JSON.parse(localStorage.getItem(key) || "{}") }; } catch (e) { /* new */ }
  status.ready = state.rev > 0;
  window.addEventListener("online", () => { status.online = true; emit(); sync(); });
  window.addEventListener("offline", () => { status.online = false; emit(); });
  document.addEventListener("visibilitychange", () => { if (!document.hidden) sync(); });
  timer = setInterval(() => { if (!document.hidden) pull(); }, POLL_MS);
  return sync();
}

// ---------- reading ----------
export const all = (c) => state.docs[c] || {};
export const get = (c, id) => (state.docs[c] || {})[id] || null;
export const list = (c) => Object.entries(all(c)).map(([id, d]) => ({ id, ...d }));
export const meta = (c, id) => (state.meta[c] || {})[id] || null;
export const docs = () => state.docs;
export const pendingCount = () => state.pending.length;

export function members() {
  return list("members").sort((a, b) => (a.order ?? 99) - (b.order ?? 99) || a.name.localeCompare(b.name));
}

// ---------- writing ----------
export function newId(prefix = "") {
  const a = new Uint8Array(9);
  crypto.getRandomValues(a);
  return prefix + btoa(String.fromCharCode(...a)).replace(/\+/g, "x").replace(/\//g, "y").replace(/=/g, "");
}

function local(c, id, data) {
  state.docs[c] ||= {};
  if (data === null) delete state.docs[c][id];
  else state.docs[c][id] = data;
}

/** Save a document (the whole of it). */
export function put(c, id, data) {
  if (status.readOnly) {
    window.dispatchEvent(new CustomEvent("mamia-error", { detail: "Tu familia está en modo solo lectura: renueva la suscripción en Cuenta para seguir apuntando." }));
    return;
  }
  local(c, id, data);
  state.pending = state.pending.filter((p) => !(p.c === c && p.id === id));
  state.pending.push({ c, id, data });
  save(); emit();
  clearTimeout(put._t);
  put._t = setTimeout(push, 250);
}
export const patch = (c, id, changes) => put(c, id, { ...(get(c, id) || {}), ...changes });
export const del = (c, id) => put(c, id, null);

// ---------- sync ----------
export async function sync() {
  await push();
  await pull();
}

export async function pull() {
  if (pulling || !key) return;
  pulling = true;
  try {
    const r = await api(`/api/sync?since=${state.rev}`);
    const waiting = new Set(state.pending.map((p) => p.c + "\n" + p.id));
    if (r.full) {   // first download: start from the server's copy (keeping what is waiting to be sent)
      const keep = state.pending.map((p) => [p.c, p.id, p.data]);
      state.docs = {}; state.meta = {};
      keep.forEach(([c, id, d]) => local(c, id, d));
    }
    for (const d of r.docs) {
      (state.meta[d.c] ||= {})[d.id] = { at: d.at, by: d.by };
      if (waiting.has(d.c + "\n" + d.id)) continue;   // a change of ours is on its way: it wins
      local(d.c, d.id, d.data);
    }
    const changed = r.docs.length > 0 || r.full;
    state.rev = r.rev;
    status.online = true; status.lastError = null; status.ready = true;
    save();
    if (changed) emit();
  } catch (e) {
    if (e.status === 0) status.online = false;
    status.lastError = e.message;
  } finally {
    pulling = false;
  }
}

export async function push() {
  if (pushing || !state.pending.length || !key) return;
  pushing = true; status.syncing = true;
  const batch = state.pending.slice(0, 400);
  try {
    const r = await api("/api/sync", { method: "POST", body: { changes: batch } });
    const errors = [];
    for (const res of r.results) {
      const sent = batch.find((p) => p.c === res.c && p.id === res.id);
      const now = state.pending.find((p) => p.c === res.c && p.id === res.id);
      if (now === sent) state.pending = state.pending.filter((p) => p !== sent);   // not changed again meanwhile
      if (now === sent) local(res.c, res.id, res.ok ? res.data : res.data ?? null);
      if (!res.ok) errors.push(res.error);
    }
    status.online = true; status.readOnly = false;
    save(); emit();
    if (errors.length) window.dispatchEvent(new CustomEvent("mamia-error", { detail: errors[0] }));
  } catch (e) {
    if (e.status === 402) {   // read-only family: what was not sent cannot be kept
      status.readOnly = true;
      state.pending = []; state.rev = 0; save();
      window.dispatchEvent(new CustomEvent("mamia-error", { detail: e.message }));
    } else if (e.status === 0) {
      status.online = false;
    } else if (e.status >= 400 && e.status < 500) {
      state.pending = state.pending.filter((p) => !batch.includes(p));
      save();
      window.dispatchEvent(new CustomEvent("mamia-error", { detail: e.message }));
    }
  } finally {
    pushing = false; status.syncing = false;
    emit();
  }
  if (state.pending.length && status.online && !status.readOnly) setTimeout(push, 1500);
}

/** Forget the local copy (signing out). */
export function forget() {
  clearInterval(timer);
  try { Object.keys(localStorage).filter((k) => k.startsWith("mamia:fam:")).forEach((k) => localStorage.removeItem(k)); } catch (e) { /* ignore */ }
}
