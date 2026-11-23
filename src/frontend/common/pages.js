// Helpers of the account pages: calls to the API (with the app's header), messages and the look of the account.
(function () {
  try {
    var look = JSON.parse(localStorage.getItem("mamia:look") || "{}");
    if (look.theme && look.theme !== "auto") document.documentElement.dataset.theme = look.theme;
    if (look.accent && look.accent !== "rosa") document.documentElement.dataset.accent = look.accent;
  } catch (e) { /* private window */ }
})();

window.M = {
  async api(path, opts) {
    opts = opts || {};
    const init = { method: opts.method || "GET", credentials: "same-origin", headers: {} };
    if (init.method !== "GET") init.headers["x-mamia"] = "1";
    if (opts.body !== undefined) { init.headers["content-type"] = "application/json"; init.body = JSON.stringify(opts.body); }
    let res;
    try { res = await fetch(path, init); } catch (e) { throw new Error("No hay conexión. Inténtalo otra vez."); }
    let data = null;
    try { data = await res.json(); } catch (e) { /* empty */ }
    if (!res.ok) {
      const d = data && data.detail;
      const err = new Error(typeof d === "string" ? d : res.status === 422 ? "Revisa los datos." : "Algo ha fallado (" + res.status + ").");
      err.status = res.status;
      throw err;
    }
    return data;
  },
  msg(el, text, kind) {
    if (!el) return;
    el.textContent = text || "";
    el.className = "msg " + (kind || "err");
    el.hidden = !text;
  },
  q(name) { return new URLSearchParams(location.search).get(name); },
  /** Where to go after signing in: the "next" asked for, only within this site. */
  next(def) {
    const n = new URLSearchParams(location.search).get("next");
    return n && n.startsWith("/") && !n.startsWith("//") ? n : def || "/app";
  },
  euros(cents) { return (cents / 100).toLocaleString("es-ES", { minimumFractionDigits: cents % 100 ? 2 : 0 }) + " €"; },
  busy(btn, on, text) {
    if (!btn) return;
    if (on) { btn.dataset.label = btn.textContent; btn.textContent = text || "Un momento…"; btn.disabled = true; }
    else { btn.textContent = btn.dataset.label || btn.textContent; btn.disabled = false; }
  },
};
