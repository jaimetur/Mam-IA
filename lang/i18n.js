/* Mam-IA · idiomas (lang/i18n.js; adaptado del de BodyLens).
 * La interfaz está escrita en español y se traduce aquí, en el navegador, con el diccionario del idioma elegido
 * (window.MI_I18N = {"texto en español": "traducción"}, que carga antes /lang/<idioma>.js a partir de
 * lang/<idioma>.json). Así las páginas no se tocan: se traducen los textos visibles (y title, placeholder,
 * aria-label, alt) según van apareciendo. Los textos con partes variables están como patrón: «{0} planes» → «{0} plans».
 * Números y fechas: lo que la app pide en 'es-ES' sale con el formato del idioma elegido. */
(function () {
  'use strict';
  var LANG = window.MI_LANG || 'es';
  var LOCALES = { en: 'en-GB', es: 'es-ES', ca: 'ca-ES', fr: 'fr-FR', it: 'it-IT', de: 'de-DE', pt: 'pt-PT', nl: 'nl-NL', zh: 'zh-CN', ja: 'ja-JP' };
  var LOC = LOCALES[LANG] || 'es-ES';
  window.MI_LOCALE = LOC;
  try { document.documentElement.lang = LANG; } catch (e) {}

  // ---- choosing the language: every <select data-lang-picker> (the pages; the app calls miLangPicker itself) ----
  window.miLangPicker = function (sel) {
    if (!sel || sel.getAttribute('data-filled')) return;
    var L = window.MI_LANGS || {};
    sel.setAttribute('data-filled', '1');
    sel.setAttribute('data-noi18n', '');   // each language keeps its own name
    sel.innerHTML = '';
    Object.keys(L).forEach(function (k) {
      var o = document.createElement('option');
      o.value = k; o.textContent = L[k]; o.selected = k === LANG;
      sel.appendChild(o);
    });
    sel.addEventListener('change', function () {
      var v = sel.value, done = function () { location.reload(); };
      document.cookie = 'mamia_lang=' + v + '; path=/; max-age=31536000; samesite=lax';
      try {   // signed in: the account keeps it (emails and notifications in that language too)
        fetch('/api/me', { method: 'PUT', credentials: 'same-origin', headers: { 'x-mamia': '1', 'content-type': 'application/json' },
          body: JSON.stringify({ lang: v }) }).then(done, done);
      } catch (e) { done(); }
    });
  };
  document.addEventListener('DOMContentLoaded', function () {
    [].forEach.call(document.querySelectorAll('select[data-lang-picker]'), window.miLangPicker);
  });
  var D = window.MI_I18N || {};
  if (!Object.keys(D).length) { window.miT = function (s) { return s; }; return; }

  // ---- números y fechas ----
  function swap(loc) { return (loc === 'es-ES' || loc === 'es') ? LOC : loc; }
  [[Number.prototype, 'toLocaleString'], [Date.prototype, 'toLocaleString'], [Date.prototype, 'toLocaleDateString'],
   [Date.prototype, 'toLocaleTimeString']].forEach(function (p) {
    var f = p[0][p[1]];
    p[0][p[1]] = function (loc) { var a = Array.prototype.slice.call(arguments); a[0] = swap(loc); return f.apply(this, a); };
  });
  ['NumberFormat', 'DateTimeFormat'].forEach(function (n) {
    var F = Intl[n];
    var W = function (loc, opt) { return new F(swap(loc), opt); };
    W.prototype = F.prototype; W.supportedLocalesOf = F.supportedLocalesOf;
    Intl[n] = W;
  });

  // ---- diccionario ----
  var EDGE = /^([\s ·—–\-:,;|.]*)([\s\S]*?)([\s ·—–\-:,;|]*)$/;   // por delante también «. »
  var LETTER = /[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]/;
  var PAT = [];
  Object.keys(D).forEach(function (k) {
    if (k.indexOf('{0}') < 0) return;
    var nums = [];
    var src = k.replace(/[.*+?^$()|[\]\\]/g, '\\$&').replace(/\\?\{(\d)\\?\}|\{(\d)\}/g, function (_, a, b) {
      nums.push(a || b); return '([\\s\\S]*?)';
    });
    // short patterns («en {0}», «{0} de {1}») never take in several sentences or «a · b» parts, and with two parts or
    // more each part is a figure (see figure(): «21 de 30», «el 19 nov»), so a text of the person («Sopa de
    // pescado») is not translated piece by piece
    var weak = (k.replace(/\{\d\}/g, '').match(/[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]/g) || []).length <= 3 ? nums.length : 0;
    try { PAT.push({ re: new RegExp('^' + src + '$'), tr: D[k], nums: nums, len: k.length, weak: weak, dot: k.indexOf('·') >= 0 }); } catch (e) {}
  });
  PAT.sort(function (a, b) { return b.len - a.len; });

  // meses y días sueltos («19 nov», «Lunes»): con los nombres del idioma (Intl)
  var WORDS = {};
  (function () {
    function names(loc, opt, n, f) {
      var out = [];
      for (var i = 0; i < n; i++) { try { out.push(new (Intl.DateTimeFormat)(loc, opt).format(f(i))); } catch (e) { out.push(''); } }
      return out;
    }
    var mon = function (i) { return new Date(Date.UTC(2021, i, 15, 12)); };
    var day = function (i) { return new Date(Date.UTC(2021, 1, 1 + i, 12)); };   // 1 feb 2021 = lunes
    var es = {
      long: ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'],
      short: ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'],
      days: ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'],
      dshort: ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']
    };
    var t = {
      long: names(LOC, { month: 'long', timeZone: 'UTC' }, 12, mon),
      short: names(LOC, { month: 'short', timeZone: 'UTC' }, 12, mon).map(function (s) { return s.replace(/\.$/, ''); }),
      days: names(LOC, { weekday: 'long', timeZone: 'UTC' }, 7, day),
      dshort: names(LOC, { weekday: 'short', timeZone: 'UTC' }, 7, day).map(function (s) { return s.replace(/\.$/, ''); })
    };
    ['long', 'short', 'days'].forEach(function (g) { es[g].forEach(function (w, i) { if (t[g][i]) WORDS[w] = t[g][i]; }); });
    WORDS['sept'] = t.short[8]; WORDS['sábados'] = t.days[5]; WORDS['domingos'] = t.days[6];
    es.dshort.forEach(function (w, i) { if (!WORDS[w] && t.dshort[i]) WORDS[w] = t.dshort[i]; });
  })();
  var WRE = new RegExp('(^|[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ])(' + Object.keys(WORDS).sort(function (a, b) { return b.length - a.length; })
    .join('|') + ')(?=$|[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ])', 'gi');
  function cap(src, w) { return src[0] === src[0].toUpperCase() && src[0] !== src[0].toLowerCase() ? w.charAt(0).toUpperCase() + w.slice(1) : w; }
  function words(s) {
    if (LANG === 'es') return null;   // the page is written in Spanish: its dates stay as they are («20 de noviembre»)
    // solo en textos con cifras («19 nov», «lun 3») o que son una de esas palabras
    if (!/\d/.test(s) && !WORDS[s.toLowerCase()]) return null;
    var ch = false;
    var r = s.replace(WRE, function (m, pre, w) { var x = WORDS[w.toLowerCase()]; if (!x) return m; ch = true; return pre + cap(w, x); });
    if (!ch) return null;
    // «19 de noviembre de 2026»: el «de» solo se queda en los idiomas que también lo usan
    if (!/^(pt|ca)$/.test(LANG)) r = r.replace(/(\d{1,2}) de (?=\S)/g, '$1 ').replace(/ de (?=\d{4})/g, ' ');
    return r;
  }

  // a part of a short pattern: a figure with its unit, a date or a day («52,5 h», «19 nov», «lunes»)
  function figure(x) {
    return (/\d/.test(x) || WORDS[x.trim().toLowerCase()]) &&
      (x.match(/[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{4,}/g) || []).every(function (w) { return WORDS[w.toLowerCase()]; });
  }
  function datede(s) { var d = /(^|\D)\d{1,2} de ([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)/.exec(s); return !!(d && WORDS[d[2].toLowerCase()]); }   // «3 de marzo»
  function core(s, depth) {
    var v = D[s];
    if (typeof v === 'string') return v;
    for (var i = 0; i < PAT.length; i++) {
      var p = PAT[i], m = p.re.exec(s);
      // a part never takes in «a · b» pieces the pattern does not have (they are translated one by one)
      if (!m || (!p.dot && m.slice(1).some(function (x) { return x.indexOf(' · ') >= 0; })) || (p.weak && (m.slice(1).some(function (x) { return /[.;:!?]\s|[·|]/.test(x); }) ||
                            (p.weak > 1 && (!m.slice(1).every(figure) || datede(s)))))) continue;
      return p.tr.replace(/\{(\d)\}/g, function (_, n) {
        var j = p.nums.indexOf(n), val = j >= 0 ? m[j + 1] : '';
        return depth < 2 ? T(val, depth + 1) : val;
      });
    }
    return null;
  }

  var cache = new Map();
  function T(text, depth) {
    depth = depth || 0;
    if (!text || !LETTER.test(text)) return text;
    var hit = cache.get(text);
    if (hit !== undefined) return hit;
    var norm = text.replace(/[\s ]+/g, ' ');
    var m = EDGE.exec(norm), pre = m[1], c = m[2], suf = m[3];
    var r = core(c, depth);
    if (r == null && /[·|]/.test(c)) {   // «a · b · c»: por partes
      var parts = c.split(/(\s*[·|]\s*)/), ch = false;
      for (var i = 0; i < parts.length; i += 2) { var t = T(parts[i], depth + 1); if (t !== parts[i]) { parts[i] = t; ch = true; } }
      if (ch) r = parts.join('');
    }
    if (r == null && depth < 3) {   // varias frases en un mismo texto: frase a frase
      var fr = c.split(/(?<=[.;:!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡(«])/);
      if (fr.length > 1) {   // de cada punto, el tramo de frases más largo que esté en el diccionario
        var outp = [], ch2 = false, i = 0;
        while (i < fr.length) {
          var hit2 = null, k = fr.length;
          for (; k > i; k--) {
            var seg = fr.slice(i, k).join(' '), m2 = EDGE.exec(seg);
            var t3 = (k - i > 1) ? core(m2[2], depth + 1) : null;
            if (t3 == null && k - i === 1) { var t4 = T(seg, depth + 1); if (t4 !== seg) t3 = t4; else t3 = null; if (t3 != null) { hit2 = t3; break; } }
            else if (t3 != null) { hit2 = m2[1] + t3 + m2[3]; break; }
          }
          if (hit2 != null) { outp.push(hit2); ch2 = true; i = k; } else { outp.push(fr[i]); i++; }
        }
        if (ch2) r = outp.join(' ');
      }
    }
    if (r == null && depth > 0 && /, /.test(c)) {   // a list inside a translated text («gratitud, alegría»): only if every item is known
      var items = c.split(', '), all = true;
      for (var q = 0; q < items.length && all; q++) { var ti = T(items[q], depth + 1); if (ti === items[q]) all = false; else items[q] = ti; }
      if (all) r = items.join(', ');
    }
    if (r == null) r = words(c);
    var out = r == null ? text : pre + r + suf;
    if (cache.size > 20000) cache.clear();
    cache.set(text, out);
    return out;
  }
  window.miT = function (s) { return T(String(s)); };
  // weekday initials of the calendars (the app's «L M X J V S D»), Monday first
  if (LANG !== 'es') window.MI_DS = names0(LOC, { weekday: 'narrow', timeZone: 'UTC' });
  function names0(loc, opt) {
    var out = [];
    for (var i = 0; i < 7; i++) { try { out.push(new (Intl.DateTimeFormat)(loc, opt).format(new Date(Date.UTC(2021, 1, 1 + i, 12)))); } catch (e) { return null; } }
    return out;
  }

  // ---- la página ----
  var SKIP = { SCRIPT: 1, STYLE: 1, TEXTAREA: 1, CODE: 1, PRE: 1, NOSCRIPT: 1 };
  var ATTRS = ['title', 'placeholder', 'aria-label', 'alt'];
  var seen = new WeakMap();
  function skip(el) {
    for (var e = el; e && e.nodeType === 1; e = e.parentNode) {
      if (SKIP[e.nodeName] || e.hasAttribute('data-noi18n') || e.isContentEditable) return true;
    }
    return false;
  }
  function doText(n) {
    var v = n.data;
    if (seen.get(n) === v || !LETTER.test(v)) return;
    var p = n.parentNode;
    if (!p || skip(p)) { seen.set(n, v); return; }
    var t = T(v);
    if (t !== v) n.data = t;
    seen.set(n, n.data);
  }
  function doAttr(el, a) {
    var v = el.getAttribute(a);
    if (!v || !LETTER.test(v)) return;
    var t = T(v);
    if (t !== v) el.setAttribute(a, t);
  }
  function doEl(el) {
    for (var i = 0; i < ATTRS.length; i++) if (el.hasAttribute(ATTRS[i])) doAttr(el, ATTRS[i]);
    if (el.nodeName === 'INPUT' && /^(button|submit|reset)$/i.test(el.type) && el.value) { var t = T(el.value); if (t !== el.value) el.value = t; }
  }
  function walk(root) {
    if (!root) return;
    if (root.nodeType === 3) { doText(root); return; }
    if (root.nodeType !== 1 && root.nodeType !== 11) return;
    if (root.nodeType === 1) { if (SKIP[root.nodeName]) { if (root.nodeName === 'TEXTAREA') doEl(root); return; } doEl(root); }
    var w = document.createTreeWalker(root, 5 /* elementos y textos */), n;
    while ((n = w.nextNode())) {
      if (n.nodeType === 3) doText(n);
      else if (SKIP[n.nodeName]) { if (n.nodeName === 'TEXTAREA') doEl(n); /* sus textos los descarta doText */ } else doEl(n);
    }
  }
  new MutationObserver(function (ms) {
    for (var i = 0; i < ms.length; i++) {
      var m = ms[i];
      if (m.type === 'childList') { for (var j = 0; j < m.addedNodes.length; j++) walk(m.addedNodes[j]); }
      else if (m.type === 'characterData') doText(m.target);
      else if (m.type === 'attributes') doAttr(m.target, m.attributeName);
    }
  }).observe(document.documentElement, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  document.addEventListener('DOMContentLoaded', function () { walk(document.documentElement); });

  // avisos del navegador
  ['alert', 'confirm', 'prompt'].forEach(function (n) {
    var f = window[n];
    if (typeof f !== 'function') return;
    window[n] = function (msg) {
      var a = Array.prototype.slice.call(arguments);
      if (msg != null) a[0] = String(msg).split('\n').map(function (l) { return T(l); }).join('\n');
      return f.apply(window, a);
    };
  });
})();
