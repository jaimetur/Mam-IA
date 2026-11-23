// Helpers of the account pages: calls to the API (with the app's header), messages and the look of the account.
(function () {
  try {
    var look = JSON.parse(localStorage.getItem("mamia:look") || "{}");
    if (look.theme && look.theme !== "auto") document.documentElement.dataset.theme = look.theme;
    if (look.accent && look.accent !== "rosa") document.documentElement.dataset.accent = look.accent;
  } catch (e) { /* private window */ }
  if (/MamIAApp\//.test(navigator.userAgent)) document.documentElement.classList.add("inapp");   // the Android app
  // the language, at the foot of every account page (lang/i18n.js fills it in)
  document.addEventListener("DOMContentLoaded", () => {
    const main = document.querySelector("main.wrap");
    if (!main || main.querySelector("select[data-lang-picker]")) return;
    const p = document.createElement("p");
    p.className = "small center langrow";
    p.innerHTML = '<label class="langpick" aria-label="Idioma">🌐 <select data-lang-picker></select></label>';
    main.appendChild(p);
    if (window.miLangPicker) window.miLangPicker(p.querySelector("select"));
  });
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
  /** Ask for the code emailed to confirm an address. `started` is the API's answer ({verify, email, minutes}); the
      form `form` is hidden meanwhile. Resolves with the answer of /api/web/verify, or null to go back to the form. */
  askCode(form, started) {
    return new Promise((resolve) => {
      const box = document.createElement("form");
      box.className = "codestep";
      box.setAttribute("autocomplete", "off");
      box.innerHTML = '<p class="lead"></p>' +
        '<label class="field"><span>Código de 6 cifras</span><input name="code" inputmode="numeric" autocomplete="one-time-code" maxlength="7" required></label>' +
        '<p class="msg err" hidden role="alert"></p>' +
        '<button class="btn pri" type="submit">Confirmar mi correo</button>' +
        '<p class="small center"><button type="button" class="linkbtn" data-resend>Enviar otro código</button> · ' +
        '<button type="button" class="linkbtn" data-back>Cambiar el correo</button></p>';
      const lead = box.querySelector(".lead"), b = document.createElement("b"), m = box.querySelector(".msg");
      b.textContent = started.email;
      lead.append("Te hemos enviado un código a ", b, `. Escríbelo aquí para confirmar que es tu correo (vale ${started.minutes || 30} minutos). Si no lo ves, mira en la carpeta de spam.`);
      form.hidden = true;
      form.after(box);
      box.code.focus();
      const close = (value) => { box.remove(); form.hidden = false; resolve(value); };
      box.querySelector("[data-back]").addEventListener("click", () => close(null));
      box.querySelector("[data-resend]").addEventListener("click", async () => {
        try { await M.api("/api/web/verify/resend", { method: "POST", body: { id: started.verify } }); M.msg(m, "Te hemos enviado otro código.", "ok"); }
        catch (err) { M.msg(m, err.message); }
      });
      box.addEventListener("submit", async (e) => {
        e.preventDefault();
        const go = box.querySelector("button[type=submit]");
        M.msg(m, "");
        M.busy(go, true, "Comprobando…");
        try { const r = await M.api("/api/web/verify", { method: "POST", body: { id: started.verify, code: box.code.value } }); box.remove(); resolve(r); }
        catch (err) { M.msg(m, err.message); M.busy(go, false); }
      });
    });
  },
};
