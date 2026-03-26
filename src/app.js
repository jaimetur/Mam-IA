const themes = [
  { id: "rosa", label: "Rosa Calido" },
  { id: "lavanda", label: "Lavanda Focus" },
  { id: "aurora", label: "Aurora Fresh" },
  { id: "terracota", label: "Terracota Zen" }
];

const areas = ["comidas", "compras", "familia", "trabajo", "limpieza", "viajes", "ocio", "escolar", "medico", "belleza", "pareja", "finanzas"];
const modules = [
  { id: "inicio", icon: "🏠", title: "Inicio", description: "Resumen diario, prioridades y estado familiar." },
  { id: "calendario", icon: "📅", title: "Calendario", description: "Vista compartida anual, mensual y semanal." },
  { id: "tareas", icon: "✅", title: "Tareas", description: "Asigna tareas, cambia estado y controla carga por miembro." },
  { id: "listas", icon: "🧾", title: "Listas", description: "Listas compartidas con checklist y responsables." },
  { id: "recordatorios", icon: "⏰", title: "Recordatorios", description: "Recordatorios con aviso local y notificaciones web." },
  { id: "planificador", icon: "🧠", title: "Planificador IA", description: "Sugerencias de equilibrio, menu y conflictos de agenda." },
  { id: "config", icon: "⚙", title: "Configuracion", description: "Unidad familiar, miembros, roles e invitaciones." }
];

const K = { theme: "mam-ia-theme", state: "mam-ia-state" };
const today = () => new Date().toISOString().slice(0, 10);
const dayOffset = (n) => {
  const d = new Date();
  d.setDate(d.getDate() + n);
  return d.toISOString().slice(0, 10);
};
const id = (p) => `${p}_${Math.random().toString(36).slice(2, 7)}${Date.now().toString(36).slice(-4)}`;
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

const baseState = {
  family: {
    familyName: "Familia Garcia",
    adminName: "Mama",
    sharedCalendar: true,
    notifications: true,
    members: [
      { id: "m1", name: "Mama", role: "Administradora" },
      { id: "m2", name: "Pareja", role: "Colaborador" },
      { id: "m3", name: "Ines", role: "Miembro" },
      { id: "m4", name: "Lucas", role: "Miembro" }
    ],
    invites: []
  },
  tasks: [
    { id: "t1", title: "Preparar menu semanal", area: "comidas", assigneeId: "m1", dueDate: dayOffset(1), status: "pendiente", priority: "alta" },
    { id: "t2", title: "Comprar fruta y lacteos", area: "compras", assigneeId: "m2", dueDate: dayOffset(0), status: "en-curso", priority: "media" },
    { id: "t3", title: "Revisar deberes de Ines", area: "escolar", assigneeId: "m1", dueDate: dayOffset(0), status: "pendiente", priority: "alta" }
  ],
  lists: [
    { id: "l1", title: "Compra semanal", area: "compras", items: [
      { id: "i1", text: "Pan integral", done: false, assigneeId: "m2" },
      { id: "i2", text: "Leche", done: false, assigneeId: "m2" }
    ] }
  ],
  events: [
    { id: "e1", title: "Pediatra Ines", area: "medico", start: `${dayOffset(1)}T17:00`, end: `${dayOffset(1)}T18:00`, memberIds: ["m1", "m3"] },
    { id: "e2", title: "Reunion trabajo", area: "trabajo", start: `${dayOffset(0)}T10:00`, end: `${dayOffset(0)}T11:00`, memberIds: ["m1"] }
  ],
  reminders: [
    { id: "r1", title: "Preparar mochilas", datetime: `${dayOffset(0)}T20:30`, done: false, notified: false }
  ]
};

function loadState() {
  try {
    const raw = JSON.parse(localStorage.getItem(K.state) || "null");
    if (!raw) return structuredClone(baseState);
    return { ...structuredClone(baseState), ...raw, family: { ...structuredClone(baseState.family), ...(raw.family || {}) } };
  } catch {
    return structuredClone(baseState);
  }
}

let S = loadState();
let active = "inicio";
let calMode = "month";
let calDate = new Date();
let selectedList = S.lists[0] ? S.lists[0].id : "";

const themePicker = document.getElementById("theme-picker");
const moduleGrid = document.getElementById("module-grid");
const moduleTitle = document.getElementById("module-title");
const moduleDescription = document.getElementById("module-description");
const moduleContent = document.getElementById("module-content");
const dailySummary = document.getElementById("daily-summary");
const inviteForm = document.getElementById("invite-form");
const inviteListNode = document.getElementById("invite-list");

const save = () => localStorage.setItem(K.state, JSON.stringify(S));
const memberName = (idv) => (S.family.members.find((m) => m.id === idv) || {}).name || "Sin asignar";
const tagOptions = (sel) => areas.map((a) => `<option value="${a}" ${a === sel ? "selected" : ""}>${cap(a)}</option>`).join("");
const memberOptions = (sel = "") => S.family.members.map((m) => `<option value="${m.id}" ${m.id === sel ? "selected" : ""}>${m.name}</option>`).join("");
const eventsByDate = (d) => S.events.filter((e) => e.start.slice(0, 10) === d);

function initTheme() {
  themes.forEach((t) => {
    const o = document.createElement("option");
    o.value = t.id;
    o.textContent = t.label;
    themePicker.appendChild(o);
  });
  const saved = localStorage.getItem(K.theme) || "rosa";
  document.documentElement.dataset.theme = saved;
  themePicker.value = saved;
  themePicker.addEventListener("change", () => {
    document.documentElement.dataset.theme = themePicker.value;
    localStorage.setItem(K.theme, themePicker.value);
  });
}

function renderModules() {
  moduleGrid.innerHTML = modules.map((m) => `
    <button class="module-btn ${m.id === active ? "active" : ""}" data-id="${m.id}" type="button">
      <span>${m.icon}</span><span>${m.title}</span>
    </button>`).join("");
  moduleGrid.querySelectorAll(".module-btn").forEach((b) => b.addEventListener("click", () => {
    active = b.dataset.id;
    renderModules();
    render();
  }));
}

function renderSummary() {
  const d = today();
  const rows = [
    `${S.tasks.filter((t) => t.status !== "hecha" && t.dueDate === d).length} tarea(s) para hoy`,
    `${eventsByDate(d).length} evento(s) para hoy`,
    `${S.reminders.filter((r) => !r.done).length} recordatorio(s) activo(s)`,
    `${S.lists.reduce((acc, l) => acc + l.items.filter((i) => !i.done).length, 0)} item(s) pendientes`
  ];
  dailySummary.innerHTML = rows.map((r) => `<li>${r}</li>`).join("");
}

function renderInvites() {
  inviteListNode.innerHTML = S.family.invites.length
    ? S.family.invites.map((i) => `<li>${i.name} (${i.email}) - Enviado</li>`).join("")
    : "<li>Sin invitaciones enviadas.</li>";
}

function fmtDT(v) {
  const d = new Date(v);
  return `${d.toLocaleDateString("es-ES")} ${d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" })}`;
}

function renderInicio() {
  const hot = S.tasks.filter((t) => t.status !== "hecha").sort((a, b) => a.dueDate.localeCompare(b.dueDate)).slice(0, 5);
  moduleContent.innerHTML = `
    <div class="stat-grid">
      <article class="mini-card"><h3>${S.tasks.filter((t) => t.status !== "hecha").length}</h3><p>Tareas pendientes</p></article>
      <article class="mini-card"><h3>${eventsByDate(today()).length}</h3><p>Eventos de hoy</p></article>
      <article class="mini-card"><h3>${S.reminders.filter((r) => !r.done).length}</h3><p>Recordatorios activos</p></article>
      <article class="mini-card"><h3>${S.family.members.length}</h3><p>Miembros activos</p></article>
    </div>
    <section class="section-card">
      <h3>Prioridades del dia</h3>
      ${hot.length ? hot.map((t) => `<div class="task-row"><div><strong>${t.title}</strong><br><small>${cap(t.area)} | ${memberName(t.assigneeId)} | ${t.dueDate}</small></div><span class="pill">${t.status}</span></div>`).join("") : "<p class='muted'>Sin tareas.</p>"}
    </section>
  `;
}

function startWeek(ref) {
  const d = new Date(ref);
  const wd = (d.getDay() + 6) % 7;
  d.setDate(d.getDate() - wd);
  d.setHours(0, 0, 0, 0);
  return d;
}

function calLabel() {
  if (calMode === "year") return `${calDate.getFullYear()}`;
  if (calMode === "month") return calDate.toLocaleDateString("es-ES", { month: "long", year: "numeric" });
  const a = startWeek(calDate);
  const b = new Date(a);
  b.setDate(a.getDate() + 6);
  return `${a.toLocaleDateString("es-ES")} - ${b.toLocaleDateString("es-ES")}`;
}

function calMove(step) {
  if (calMode === "year") calDate.setFullYear(calDate.getFullYear() + step);
  if (calMode === "month") calDate.setMonth(calDate.getMonth() + step);
  if (calMode === "week") calDate.setDate(calDate.getDate() + step * 7);
  render();
}

function renderCalCanvas() {
  if (calMode === "year") {
    const y = calDate.getFullYear();
    return `<div class="year-grid">${Array.from({ length: 12 }, (_, m) => {
      const c = S.events.filter((e) => {
        const d = new Date(e.start);
        return d.getFullYear() === y && d.getMonth() === m;
      }).length;
      return `<div class="year-cell"><strong>${new Date(y, m, 1).toLocaleDateString("es-ES", { month: "long" })}</strong><span>${c} evento(s)</span></div>`;
    }).join("")}</div>`;
  }
  if (calMode === "week") {
    const s = startWeek(calDate);
    return `<div class="week-grid">${Array.from({ length: 7 }, (_, i) => {
      const d = new Date(s);
      d.setDate(s.getDate() + i);
      const k = d.toISOString().slice(0, 10);
      const ev = eventsByDate(k);
      return `<div class="week-day"><strong>${d.toLocaleDateString("es-ES", { weekday: "short", day: "2-digit", month: "2-digit" })}</strong>${ev.length ? ev.map((e) => `<p>${e.start.slice(11, 16)} ${e.title}</p>`).join("") : "<p class='muted'>Sin eventos</p>"}</div>`;
    }).join("")}</div>`;
  }
  const y = calDate.getFullYear();
  const m = calDate.getMonth();
  const first = new Date(y, m, 1);
  const pad = (first.getDay() + 6) % 7;
  const dim = new Date(y, m + 1, 0).getDate();
  const cells = [];
  for (let i = 0; i < pad; i += 1) cells.push("<div class='month-day empty'></div>");
  for (let d = 1; d <= dim; d += 1) {
    const k = `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
    cells.push(`<div class="month-day"><strong>${d}</strong><small>${eventsByDate(k).length} ev.</small></div>`);
  }
  return `<div class="month-grid">${cells.join("")}</div>`;
}

function renderCalendario() {
  moduleContent.innerHTML = `
    <section class="section-card">
      <div class="calendar-tools">
        <div class="segmented">
          <button type="button" data-v="year" class="${calMode === "year" ? "active" : ""}">Anual</button>
          <button type="button" data-v="month" class="${calMode === "month" ? "active" : ""}">Mensual</button>
          <button type="button" data-v="week" class="${calMode === "week" ? "active" : ""}">Semanal</button>
        </div>
        <div class="calendar-nav">
          <button type="button" id="cprev">Anterior</button>
          <strong>${calLabel()}</strong>
          <button type="button" id="cnext">Siguiente</button>
        </div>
      </div>
      <div id="cal-canvas">${renderCalCanvas()}</div>
    </section>
    <section class="section-card">
      <h3>Nuevo evento compartido</h3>
      <form id="event-form" class="grid-form">
        <input id="ev-title" type="text" placeholder="Titulo del evento" required>
        <select id="ev-area">${tagOptions("familia")}</select>
        <input id="ev-start" type="datetime-local" required>
        <input id="ev-end" type="datetime-local" required>
        <select id="ev-member">${memberOptions()}</select>
        <button class="btn-primary" type="submit">Guardar evento</button>
      </form>
    </section>
  `;
  moduleContent.querySelectorAll(".segmented button").forEach((b) => b.addEventListener("click", () => { calMode = b.dataset.v; render(); }));
  moduleContent.querySelector("#cprev").addEventListener("click", () => calMove(-1));
  moduleContent.querySelector("#cnext").addEventListener("click", () => calMove(1));
  moduleContent.querySelector("#event-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const t = moduleContent.querySelector("#ev-title").value.trim();
    const a = moduleContent.querySelector("#ev-area").value;
    const s = moduleContent.querySelector("#ev-start").value;
    const en = moduleContent.querySelector("#ev-end").value;
    const m = moduleContent.querySelector("#ev-member").value;
    if (!t || !s || !en || en <= s) return;
    S.events.unshift({ id: id("e"), title: t, area: a, start: s, end: en, memberIds: [m] });
    save();
    render();
  });
}

function renderTareas() {
  moduleContent.innerHTML = `
    <section class="section-card">
      <h3>Nueva tarea</h3>
      <form id="task-form" class="grid-form">
        <input id="ta-title" type="text" placeholder="Tarea a realizar" required>
        <select id="ta-area">${tagOptions("familia")}</select>
        <select id="ta-member">${memberOptions()}</select>
        <input id="ta-date" type="date" required>
        <select id="ta-pri">
          <option value="alta">Prioridad alta</option>
          <option value="media">Prioridad media</option>
          <option value="baja">Prioridad baja</option>
        </select>
        <button class="btn-primary" type="submit">Guardar tarea</button>
      </form>
    </section>
    <section class="kanban">
      ${["pendiente", "en-curso", "hecha"].map((st) => {
        const t = S.tasks.filter((x) => x.status === st);
        return `<article class="kanban-col"><h3>${cap(st)} (${t.length})</h3>${t.length ? t.map((x) => `
          <div class="kanban-item">
            <strong>${x.title}</strong>
            <small>${cap(x.area)} | ${memberName(x.assigneeId)} | ${x.dueDate}</small>
            <div class="task-actions">
              <select data-id="${x.id}" class="task-state">
                <option value="pendiente" ${x.status === "pendiente" ? "selected" : ""}>Pendiente</option>
                <option value="en-curso" ${x.status === "en-curso" ? "selected" : ""}>En curso</option>
                <option value="hecha" ${x.status === "hecha" ? "selected" : ""}>Hecha</option>
              </select>
              <button type="button" class="task-delete" data-id="${x.id}">Eliminar</button>
            </div>
          </div>`).join("") : "<p class='muted'>Sin tareas</p>"}</article>`;
      }).join("")}
    </section>
  `;

  moduleContent.querySelector("#task-form").addEventListener("submit", (e) => {
    e.preventDefault();
    S.tasks.unshift({
      id: id("t"),
      title: moduleContent.querySelector("#ta-title").value.trim(),
      area: moduleContent.querySelector("#ta-area").value,
      assigneeId: moduleContent.querySelector("#ta-member").value,
      dueDate: moduleContent.querySelector("#ta-date").value,
      status: "pendiente",
      priority: moduleContent.querySelector("#ta-pri").value
    });
    save();
    render();
  });

  moduleContent.querySelectorAll(".task-state").forEach((s) => s.addEventListener("change", () => {
    const t = S.tasks.find((x) => x.id === s.dataset.id);
    if (!t) return;
    t.status = s.value;
    save();
    render();
  }));

  moduleContent.querySelectorAll(".task-delete").forEach((b) => b.addEventListener("click", () => {
    S.tasks = S.tasks.filter((x) => x.id !== b.dataset.id);
    save();
    render();
  }));
}

function renderListas() {
  if (!selectedList && S.lists.length) selectedList = S.lists[0].id;
  const list = S.lists.find((l) => l.id === selectedList);
  moduleContent.innerHTML = `
    <section class="section-card">
      <h3>Nueva lista compartida</h3>
      <form id="list-form" class="grid-form compact">
        <input id="li-title" type="text" placeholder="Nombre de la lista" required>
        <select id="li-area">${tagOptions("compras")}</select>
        <button class="btn-primary" type="submit">Crear lista</button>
      </form>
      <div class="chip-row">${S.lists.map((l) => `<button type="button" class="chip ${l.id === selectedList ? "active" : ""}" data-id="${l.id}">${l.title}</button>`).join("")}</div>
    </section>
    <section class="section-card">
      ${list ? `
      <h3>${list.title}</h3>
      <form id="item-form" class="grid-form compact">
        <input id="it-text" type="text" placeholder="Nuevo item" required>
        <select id="it-member">${memberOptions()}</select>
        <button class="btn-primary" type="submit">Anadir</button>
      </form>
      <div class="checklist">${list.items.length ? list.items.map((it) => `
        <label class="check-row">
          <input type="checkbox" class="item-toggle" data-l="${list.id}" data-i="${it.id}" ${it.done ? "checked" : ""}>
          <span class="${it.done ? "done" : ""}">${it.text} <small>(${memberName(it.assigneeId)})</small></span>
        </label>`).join("") : "<p class='muted'>Lista vacia.</p>"}</div>` : "<p class='muted'>Crea una lista para empezar.</p>"}
    </section>
  `;

  moduleContent.querySelector("#list-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const nl = { id: id("l"), title: moduleContent.querySelector("#li-title").value.trim(), area: moduleContent.querySelector("#li-area").value, items: [] };
    S.lists.unshift(nl);
    selectedList = nl.id;
    save();
    render();
  });
  moduleContent.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => { selectedList = c.dataset.id; render(); }));

  const iForm = moduleContent.querySelector("#item-form");
  if (iForm) {
    iForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const l = S.lists.find((x) => x.id === selectedList);
      if (!l) return;
      l.items.push({ id: id("i"), text: moduleContent.querySelector("#it-text").value.trim(), done: false, assigneeId: moduleContent.querySelector("#it-member").value });
      save();
      render();
    });
  }
  moduleContent.querySelectorAll(".item-toggle").forEach((t) => t.addEventListener("change", () => {
    const l = S.lists.find((x) => x.id === t.dataset.l);
    if (!l) return;
    const it = l.items.find((x) => x.id === t.dataset.i);
    if (!it) return;
    it.done = t.checked;
    save();
  }));
}

function renderRecordatorios() {
  moduleContent.innerHTML = `
    <section class="section-card">
      <h3>Nuevo recordatorio</h3>
      <form id="rem-form" class="grid-form compact">
        <input id="re-title" type="text" placeholder="Titulo del recordatorio" required>
        <input id="re-dt" type="datetime-local" required>
        <button class="btn-primary" type="submit">Guardar</button>
      </form>
      <button id="notify-perm" type="button" class="btn-secondary">Activar notificaciones</button>
    </section>
    <section class="section-card">
      <h3>Recordatorios</h3>
      ${S.reminders.length ? S.reminders.map((r) => `
        <div class="task-row">
          <div><strong>${r.title}</strong><br><small>${fmtDT(r.datetime)}</small></div>
          <div class="inline-actions">
            <button type="button" class="mark-rem" data-id="${r.id}">${r.done ? "Reabrir" : "Hecho"}</button>
            <button type="button" class="task-delete" data-id="${r.id}">Eliminar</button>
          </div>
        </div>`).join("") : "<p class='muted'>No hay recordatorios.</p>"}
    </section>
  `;
  moduleContent.querySelector("#rem-form").addEventListener("submit", (e) => {
    e.preventDefault();
    S.reminders.unshift({ id: id("r"), title: moduleContent.querySelector("#re-title").value.trim(), datetime: moduleContent.querySelector("#re-dt").value, done: false, notified: false });
    save();
    render();
  });
  moduleContent.querySelector("#notify-perm").addEventListener("click", async () => {
    if (!("Notification" in window)) return alert("Tu navegador no soporta notificaciones.");
    await Notification.requestPermission();
  });
  moduleContent.querySelectorAll(".mark-rem").forEach((b) => b.addEventListener("click", () => {
    const r = S.reminders.find((x) => x.id === b.dataset.id);
    if (!r) return;
    r.done = !r.done;
    if (!r.done) r.notified = false;
    save();
    render();
  }));
  moduleContent.querySelectorAll(".task-delete").forEach((b) => b.addEventListener("click", () => {
    S.reminders = S.reminders.filter((x) => x.id !== b.dataset.id);
    save();
    render();
  }));
}

function detectConflicts() {
  const out = [];
  const sorted = [...S.events].sort((a, b) => a.start.localeCompare(b.start));
  for (let i = 0; i < sorted.length - 1; i += 1) {
    const a = sorted[i];
    const b = sorted[i + 1];
    if (a.end > b.start && a.memberIds.some((m) => b.memberIds.includes(m))) {
      out.push(`${a.title} solapa con ${b.title}`);
    }
  }
  return out;
}

function renderPlanificador() {
  const load = S.family.members.map((m) => ({ name: m.name, pending: S.tasks.filter((t) => t.assigneeId === m.id && t.status !== "hecha").length })).sort((a, b) => b.pending - a.pending);
  const conf = detectConflicts();
  const max = load[0] || { name: "N/A", pending: 0 };
  const min = load[load.length - 1] || { name: "N/A", pending: 0 };
  moduleContent.innerHTML = `
    <section class="section-card">
      <h3>Analisis de equilibrio familiar</h3>
      <div class="suggestion-grid">
        <article><h4>Carga por miembro</h4>${load.map((x) => `<p>${x.name}: ${x.pending} tareas pendientes</p>`).join("")}</article>
        <article><h4>Conflictos de agenda</h4>${conf.length ? conf.map((x) => `<p>${x}</p>`).join("") : "<p>Sin conflictos detectados.</p>"}</article>
        <article><h4>Sugerencia de menu semanal</h4>
          <p>Lunes: legumbres</p><p>Martes: pollo + verduras</p><p>Miercoles: pasta integral</p>
          <p>Jueves: pescado</p><p>Viernes: tortilla</p><p>Sabado/Domingo: plan familiar</p>
        </article>
      </div>
    </section>
    <section class="section-card">
      <h3>Acciones recomendadas</h3>
      <div class="task-row"><div><strong>Reequilibrar tareas</strong><br><small>Mover 1 tarea de ${max.name} a ${min.name}.</small></div><span class="pill">Balance</span></div>
      <div class="task-row"><div><strong>Reservar autocuidado</strong><br><small>Bloquea 45 min para descanso personal.</small></div><span class="pill">Bienestar</span></div>
      <div class="task-row"><div><strong>Compra anticipada</strong><br><small>Preparar compra para 4 dias y reducir urgencias.</small></div><span class="pill">Organizacion</span></div>
    </section>
  `;
}

function renderConfig() {
  moduleContent.innerHTML = `
    <section class="section-card">
      <h3>Unidad familiar</h3>
      <form id="fam-form" class="grid-form">
        <input id="fa-name" type="text" value="${S.family.familyName}" required>
        <input id="fa-admin" type="text" value="${S.family.adminName}" required>
        <label class="inline-check"><input id="fa-cal" type="checkbox" ${S.family.sharedCalendar ? "checked" : ""}> Calendario compartido</label>
        <label class="inline-check"><input id="fa-not" type="checkbox" ${S.family.notifications ? "checked" : ""}> Notificaciones</label>
        <button class="btn-primary" type="submit">Guardar ajustes</button>
      </form>
    </section>
    <section class="section-card">
      <h3>Miembros y roles</h3>
      <form id="mem-form" class="grid-form compact">
        <input id="me-name" type="text" placeholder="Nombre de miembro" required>
        <select id="me-role"><option>Administradora</option><option>Colaborador</option><option>Miembro</option></select>
        <button class="btn-primary" type="submit">Anadir miembro</button>
      </form>
      <div class="member-list">${S.family.members.map((m) => `<div class="member-chip">${m.name} <small>${m.role}</small> <button class="chip-close" type="button" data-id="${m.id}">x</button></div>`).join("")}</div>
    </section>
  `;
  moduleContent.querySelector("#fam-form").addEventListener("submit", (e) => {
    e.preventDefault();
    S.family.familyName = moduleContent.querySelector("#fa-name").value.trim();
    S.family.adminName = moduleContent.querySelector("#fa-admin").value.trim();
    S.family.sharedCalendar = moduleContent.querySelector("#fa-cal").checked;
    S.family.notifications = moduleContent.querySelector("#fa-not").checked;
    save();
    render();
  });
  moduleContent.querySelector("#mem-form").addEventListener("submit", (e) => {
    e.preventDefault();
    S.family.members.push({ id: id("m"), name: moduleContent.querySelector("#me-name").value.trim(), role: moduleContent.querySelector("#me-role").value });
    save();
    render();
  });
  moduleContent.querySelectorAll(".chip-close").forEach((b) => b.addEventListener("click", () => {
    const mid = b.dataset.id;
    S.family.members = S.family.members.filter((m) => m.id !== mid);
    S.tasks = S.tasks.filter((t) => t.assigneeId !== mid);
    S.events = S.events.map((e) => ({ ...e, memberIds: e.memberIds.filter((m) => m !== mid) }));
    S.lists.forEach((l) => { l.items = l.items.map((it) => (it.assigneeId === mid ? { ...it, assigneeId: "" } : it)); });
    save();
    render();
  }));
}

function checkReminders() {
  if (!S.family.notifications) return;
  let changed = false;
  const now = Date.now();
  S.reminders.forEach((r) => {
    if (r.done || r.notified) return;
    const due = new Date(r.datetime).getTime();
    if (!Number.isNaN(due) && due <= now) {
      r.notified = true;
      changed = true;
      if ("Notification" in window && Notification.permission === "granted") {
        new Notification(`Mam-IA: ${r.title}`);
      }
    }
  });
  if (changed) {
    save();
    if (active === "recordatorios") render();
  }
}

function render() {
  const m = modules.find((x) => x.id === active);
  moduleTitle.textContent = `${m.icon} ${m.title}`;
  moduleDescription.textContent = m.description;
  moduleContent.innerHTML = "";
  if (active === "inicio") renderInicio();
  if (active === "calendario") renderCalendario();
  if (active === "tareas") renderTareas();
  if (active === "listas") renderListas();
  if (active === "recordatorios") renderRecordatorios();
  if (active === "planificador") renderPlanificador();
  if (active === "config") renderConfig();
  renderSummary();
  renderInvites();
}

function initInvites() {
  inviteForm.addEventListener("submit", (e) => {
    e.preventDefault();
    const nameInput = document.getElementById("invite-name");
    const emailInput = document.getElementById("invite-email");
    S.family.invites.unshift({ id: id("inv"), name: nameInput.value.trim(), email: emailInput.value.trim(), sentAt: new Date().toISOString() });
    save();
    nameInput.value = "";
    emailInput.value = "";
    renderInvites();
  });
}

function registerServiceWorker() {
  if (window.location.hostname === "mamia.jaimetur.cloud" || window.location.port === "5071") return;
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("./service-worker.js").catch(() => {});
}

initTheme();
renderModules();
render();
initInvites();
registerServiceWorker();
checkReminders();
setInterval(checkReminders, 30000);
