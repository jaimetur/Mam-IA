// Service worker of Mam-IA: the app opens without a connection (the shell and its files are kept), and the
// reminders sent by the server (Web Push) are shown with a "Hecho" button for tasks.
// CACHE_NAME carries the release (tools/CreateUpdateRelease.py); BUILD is filled in by the server with the build.
const CACHE_NAME = "mam-ia-v0.2.0";
const BUILD = "{{v}}";
const CACHE = `${CACHE_NAME}-${BUILD}`;
const DEV = BUILD.endsWith("-dev");
const SHELL = ["/app", "/static/common/tokens.css", "/static/common/fonts/fonts.css", "/static/common/icons.svg",
  "/static/common/logo.svg", "/static/app/app.css"];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => {}).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;
  if (req.mode === "navigate") {
    if (url.pathname !== "/app") return;
    // the app page: always the newest one, the kept copy only without a connection
    event.respondWith(fetch(req).then((res) => {
      if (res.ok && !res.redirected) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put("/app", copy)); }
      return res;
    }).catch(() => caches.match("/app")));
    return;
  }
  if (url.pathname.startsWith("/static/")) {
    if (DEV) {   // running from the repository: always the file as it is now, the copy only offline
      event.respondWith(fetch(req).then((res) => { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); return res; })
        .catch(() => caches.match(req, { ignoreSearch: true })));
      return;
    }
    // files: the kept copy at once, refreshed in the background (a new release brings a new cache)
    event.respondWith(caches.open(CACHE).then(async (c) => {
      const hit = await c.match(req, { ignoreSearch: true });
      const net = fetch(req).then((res) => { if (res.ok) c.put(req, res.clone()); return res; }).catch(() => hit);
      return hit || net;
    }));
  }
});

self.addEventListener("push", (event) => {
  let d = {};
  try { d = event.data.json(); } catch (e) { d = { title: "Mam-IA", body: event.data ? event.data.text() : "" }; }
  const actions = d.id && d.id.startsWith("tk:") ? [{ action: "hecho", title: "Hecho" }] : [];
  event.waitUntil(self.registration.showNotification(d.title || "Mam-IA", {
    body: d.body || "", tag: d.tag || d.id, icon: "/static/common/icons/icon-192.png", badge: "/static/common/icons/favicon-32.png",
    data: { path: d.path || "/app", id: d.id || "" }, actions, renotify: true,
  }));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const { path, id } = event.notification.data || {};
  const target = event.action === "hecho" && id ? `/app?hecho=${encodeURIComponent(id)}` : path || "/app";
  event.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
    const open = list.find((c) => new URL(c.url).pathname === "/app");
    if (open && event.action !== "hecho") { open.navigate(target).catch(() => {}); return open.focus(); }
    return self.clients.openWindow(target);
  }));
});
