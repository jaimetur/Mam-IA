const THEMES = [
  { id: "calma", label: "Calma coral", color: "#eb6a8a" },
  { id: "brisa", label: "Brisa fresca", color: "#1ab89e" },
  { id: "atardecer", label: "Atardecer suave", color: "#dc6b5f" },
  { id: "noche-clara", label: "Noche clara", color: "#7a6ff0" }
];

const MODULES = [
  {
    id: "comidas", icon: "🍲", title: "Comidas", kicker: "Nutricion semanal",
    summary: "Menus de la semana, batch cooking y control de favoritos.",
    description: "Planifica desayunos, comidas, cenas y meriendas con listas rapidas y equilibrio entre ahorro, tiempo y variedad.",
    meta: ["7 dias cerrados", "Batch cooking", "Favoritos"],
    cards: [
      { title: "Menu listo para hoy", text: "Crema de calabaza, pollo al horno y yogur con fruta." },
      { title: "Preparado de domingo", text: "Bases cocinadas para 3 cenas y 2 tupper de trabajo." }
    ],
    timeline: [
      { time: "08:00", title: "Desayuno escolar", text: "Tostadas, fruta y leche para Alba y Leo.", status: "success", statusText: "Listo" },
      { time: "14:00", title: "Comida familiar", text: "Lentejas rapidas y ensalada crujiente.", status: "info", statusText: "Programado" },
      { time: "21:00", title: "Cena ligera", text: "Tortilla francesa y tomate aliñado.", status: "warning", statusText: "Pendiente compra" }
    ],
    boards: [{ title: "Despensa inteligente", items: ["3 cenas con verduras congeladas", "2 desayunos con avena y fruta", "Stock de arroz y pasta al 70%"] }]
  },
  {
    id: "compras", icon: "🛒", title: "Compras", kicker: "Casa y reposicion",
    summary: "Lista compartida por pasillos, tienda y prioridad.",
    description: "Gestiona supermercado, farmacia, bazar y compras online con prioridad, presupuesto y quien se encarga.",
    meta: ["42 EUR previstos", "12 productos", "2 tiendas"],
    cards: [
      { title: "Compra de hoy", text: "Supermercado + farmacia en una sola ruta." },
      { title: "Ahorro", text: "Comparador rapido entre marcas y articulos recurrentes." }
    ],
    timeline: [
      { time: "17:30", title: "Supermercado", text: "Leche, fruta, pescado y productos de limpieza.", status: "info", statusText: "Ruta optimizada" },
      { time: "18:10", title: "Farmacia", text: "Vitamina D infantil y protector solar.", status: "success", statusText: "Recordatorio activo" }
    ],
    boards: [{ title: "Lista compartida", items: ["Leo añadio cereales", "Marta marco detergente urgente", "Pareja asignada a bebidas y pañales"] }]
  },
  {
    id: "familia", icon: "👨‍👩‍👧‍👦", title: "Familia", kicker: "Tareas y calendarios",
    summary: "Tableros familiares con tareas, recados y eventos sincronizados.",
    description: "Coordina calendarios, responsabilidades, deberes y mensajes rapidos entre todos los miembros de la unidad familiar.",
    meta: ["5 miembros", "3 listas", "Calendario comun"],
    cards: [
      { title: "Responsables del dia", text: "Pareja: recoger compra. Alba: mochila. Leo: ordenar juguetes." },
      { title: "Calendario compartido", text: "Eventos visibles por color, persona y categoria." }
    ],
    timeline: [
      { time: "16:00", title: "Recoger del cole", text: "Abuela pasa por Alba y Leo.", status: "success", statusText: "Confirmado" },
      { time: "19:00", title: "Reunion familiar express", text: "Reparto de tareas de fin de semana.", status: "info", statusText: "15 min" }
    ],
    boards: [{ title: "Listas compartidas", items: ["Cosas del cole", "Recados del barrio", "Tareas del sabado"] }]
  },
  {
    id: "trabajo", icon: "💼", title: "Trabajo", kicker: "Bloques de foco",
    summary: "Agenda laboral integrada con tiempos de concentracion y recados.",
    description: "Agrupa reuniones, entregas, llamadas y trabajo profundo para equilibrar vida profesional y familiar.",
    meta: ["2 reuniones", "1 entrega", "Bloques de foco"],
    cards: [
      { title: "Foco matinal", text: "90 minutos reservados para tareas de alta energia." },
      { title: "Buffer realista", text: "Separacion entre trabajo, recados y tiempo de familia." }
    ],
    timeline: [
      { time: "09:30", title: "Trabajo profundo", text: "Preparar propuesta para cliente.", status: "success", statusText: "Protegido" },
      { time: "12:30", title: "Llamada de seguimiento", text: "Revisar hitos semanales.", status: "info", statusText: "30 min" }
    ],
    boards: [{ title: "Prioridades laborales", items: ["Propuesta cliente Delta", "Responder 5 correos clave", "Cerrar planning del viernes"] }]
  },
  {
    id: "limpieza", icon: "🧽", title: "Limpieza", kicker: "Hogar ordenado",
    summary: "Rutinas de casa con tareas asignadas y rotacion por miembros.",
    description: "Convierte la limpieza en un sistema claro: frecuencia, responsable, nivel de esfuerzo y recordatorios.",
    meta: ["8 tareas", "Rotacion semanal", "Checklist rapido"],
    cards: [
      { title: "Rutina de 20 minutos", text: "Cocina, ropa y salon antes de la cena." },
      { title: "Delegacion", text: "Cada miembro tiene tareas visibles y medibles." }
    ],
    timeline: [
      { time: "18:45", title: "Cocina y encimeras", text: "Asignado a pareja.", status: "success", statusText: "Asignado" },
      { time: "19:10", title: "Juguetes y salon", text: "Responsables: Alba y Leo.", status: "warning", statusText: "Supervision" }
    ],
    boards: [{ title: "Tareas por zona", items: ["Baños lunes", "Dormitorios miercoles", "Nevera primer domingo"] }]
  },
  {
    id: "viajes", icon: "✈️", title: "Escapadas", kicker: "Viajes y salidas",
    summary: "Planea fines de semana, maletas, presupuesto y reservas.",
    description: "Organiza escapadas familiares o en pareja con lista de equipaje, documentos, reservas y actividades.",
    meta: ["2 ideas", "Presupuesto", "Checklist viaje"],
    cards: [
      { title: "Proxima escapada", text: "Casa rural de dos noches con ruta facil para peques." },
      { title: "Maletas listas", text: "Plantillas segun edad, clima y tipo de viaje." }
    ],
    timeline: [{ time: "Viernes", title: "Salida a las 18:30", text: "Recoger maletas, snacks y cargadores.", status: "info", statusText: "Preparacion" }],
    boards: [{ title: "Checklist viaje", items: ["Medicacion", "Documentos", "Entretenimiento para coche"] }]
  },
  {
    id: "ocio", icon: "🎈", title: "Ocio", kicker: "Tiempo personal y familiar",
    summary: "Ideas de ocio, tiempo de pareja y autocuidado sin culpa.",
    description: "Reserva espacios reales para ocio, descanso, planes con amigas, tiempo con la pareja y actividades con los peques.",
    meta: ["4 planes", "1 cita pareja", "Autocuidado"],
    cards: [
      { title: "Tiempo para ti", text: "Bloque protegido para lectura, paseo o descanso." },
      { title: "Tiempo en pareja", text: "Cena sencilla en casa y noche sin pantallas." }
    ],
    timeline: [
      { time: "20:30", title: "Noche de peli", text: "Sesion familiar con cena rapida.", status: "success", statusText: "Reservado" },
      { time: "Sabado", title: "Plan en pareja", text: "Desayuno fuera y paseo sin prisas.", status: "info", statusText: "Confirmar canguro" }
    ],
    boards: [{ title: "Banco de planes", items: ["Parque + picnic", "Manualidades", "Museo infantil", "Spa en casa"] }]
  },
  {
    id: "agenda", icon: "📅", title: "Agendas", kicker: "Citas y recordatorios",
    summary: "Medico, peluqueria, estetica, manicura y gestiones personales.",
    description: "Centraliza citas medicas, escolares, belleza y tramites personales con avisos, documentos y desplazamientos.",
    meta: ["6 citas", "Avisos activos", "Todo en uno"],
    cards: [
      { title: "Medico", text: "Vacunas, revisiones y especialistas de toda la familia." },
      { title: "Belleza y cuidado", text: "Peluqueria, estetica y manicura con tiempos de traslado." }
    ],
    timeline: [
      { time: "11:00", title: "Dentista infantil", text: "Leo con radiografia de control.", status: "info", statusText: "Documento adjunto" },
      { time: "17:00", title: "Peluqueria", text: "Corte y color con recordatorio de 45 min.", status: "warning", statusText: "Confirmar" }
    ],
    boards: [{ title: "Proximas citas", items: ["Pediatra", "Tutoria escolar", "Estetica viernes", "Manicura mensual"] }]
  },
  {
    id: "escuela", icon: "🎒", title: "Escuela", kicker: "Cole y actividades",
    summary: "Deberes, excursiones, reuniones y material escolar.",
    description: "Lleva el control de tareas escolares, tutorias, notas, material, uniformes y actividades extraescolares.",
    meta: ["2 extraescolares", "3 deberes", "1 circular"],
    cards: [
      { title: "Mochilas sin estres", text: "Checklist por hijo con dias especiales y comedor." },
      { title: "Comunicacion colegio", text: "Circulares, pagos y excursiones reunidos." }
    ],
    timeline: [
      { time: "08:45", title: "Clase de natacion", text: "Bañador y gorro preparados para Alba.", status: "success", statusText: "Preparado" },
      { time: "18:00", title: "Deberes guiados", text: "20 min de lectura y mates con Leo.", status: "info", statusText: "Rutina" }
    ],
    boards: [{ title: "Pendientes escolares", items: ["Firmar circular", "Comprar cartulina", "Pago excursion", "Tutoria martes"] }]
  },
  {
    id: "configuracion", icon: "⚙️", title: "Configuracion", kicker: "Unidad familiar",
    summary: "Alta de familia, roles, permisos, invitaciones y personalizacion.",
    description: "Administra la unidad familiar desde un unico lugar: miembros, permisos, notificaciones, temas, calendarios y listas compartidas.",
    meta: ["Roles", "Permisos", "Invitaciones"],
    cards: [
      { title: "Familia configurable", text: "Madre admin, pareja colaborador, hijos con tareas simples y abuelos invitados." },
      { title: "Todo desde ajustes", text: "Temas, avisos, calendarios, privacidad y sincronizacion." }
    ],
    timeline: [{ time: "Ahora", title: "Invitaciones pendientes", text: "2 miembros aun no aceptan.", status: "warning", statusText: "Seguimiento" }],
    boards: [{ title: "Acciones clave", items: ["Crear roles", "Activar avisos", "Compartir calendarios", "Elegir tema"] }]
  }
];

const STATE = {
  activeModule: MODULES[0].id,
  theme: localStorage.getItem("mamia-theme") || THEMES[0].id,
  familyMode: false,
  invitations: [
    { name: "Carlos", email: "carlos@familia.es", status: "Aceptada" },
    { name: "Abuela Ana", email: "ana@familia.es", status: "Pendiente" }
  ],
  members: [
    { name: "Marta", role: "Madre y administradora", badge: "MA" },
    { name: "Carlos", role: "Pareja y colaborador", badge: "CA" },
    { name: "Alba", role: "Hija, tareas visuales", badge: "AL" },
    { name: "Leo", role: "Hijo, rutinas guiadas", badge: "LE" },
    { name: "Ana", role: "Abuela invitada", badge: "AN" }
  ]
};

const $ = (selector) => document.querySelector(selector);

function renderThemePicker() {
  const picker = $("#theme-picker");
  picker.innerHTML = THEMES.map((theme) => `<option value="${theme.id}">${theme.label}</option>`).join("");
  picker.value = STATE.theme;
}

function applyTheme(themeId) {
  STATE.theme = themeId;
  document.documentElement.dataset.theme = themeId === "calma" ? "" : themeId;
  localStorage.setItem("mamia-theme", themeId);
  const theme = THEMES.find((item) => item.id === themeId) || THEMES[0];
  document.querySelector('meta[name="theme-color"]').setAttribute("content", theme.color);
}

function renderHeroStats() {
  const stats = [
    { value: "14", label: "tareas del dia" },
    { value: "6", label: "citas activas" },
    { value: "5", label: "miembros conectados" },
    { value: "4", label: "planes de ocio" }
  ];
  $("#hero-stats").innerHTML = stats.map((stat) => `<article class="stat-chip"><strong>${stat.value}</strong><span>${stat.label}</span></article>`).join("");
}

function renderFocusCards() {
  const cards = [
    { icon: "⏱️", title: "Rutina del dia", text: STATE.familyMode ? "Vista compartida con tareas visibles para toda la familia." : "Tu panel muestra primero lo urgente y despues lo importante." },
    { icon: "💗", title: "Cuidado personal", text: "Incluye citas, descanso, manicura, peluqueria y espacios para ti." },
    { icon: "🏡", title: "Casa al dia", text: "Compras, limpieza, menus y recados en un solo flujo." },
    { icon: "🧠", title: "Menos carga mental", text: "Recordatorios, roles y calendarios compartidos para no llevarlo todo sola." }
  ];
  $("#focus-cards").innerHTML = cards.map((card) => `<article class="focus-card"><div class="icon-badge">${card.icon}</div><h3>${card.title}</h3><p>${card.text}</p></article>`).join("");
}

function renderModules() {
  $("#module-grid").innerHTML = MODULES.map((module) => `
    <button class="module-btn ${module.id === STATE.activeModule ? "active" : ""}" type="button" data-module="${module.id}">
      <div class="icon-badge">${module.icon}</div>
      <div>
        <div class="module-chip">${module.kicker}</div>
        <h3>${module.title}</h3>
        <p>${module.summary}</p>
      </div>
    </button>
  `).join("");
  document.querySelectorAll(".module-btn").forEach((button) => {
    button.addEventListener("click", () => {
      STATE.activeModule = button.dataset.module;
      renderModules();
      renderModuleDetail();
    });
  });
}

function renderModuleDetail() {
  const module = MODULES.find((item) => item.id === STATE.activeModule);
  if (!module) return;
  $("#module-kicker").textContent = module.kicker;
  $("#module-title").textContent = `${module.icon} ${module.title}`;
  $("#module-description").textContent = module.description;
  $("#module-meta").innerHTML = module.meta.map((item) => `<span>${item}</span>`).join("");
  const cardsMarkup = module.cards.map((card) => `<article class="detail-card"><h3>${card.title}</h3><p>${card.text}</p></article>`).join("");
  const timelineMarkup = module.timeline.map((item) => `
    <article class="timeline-item">
      <div class="timeline-item-header">
        <div><div class="tag">${item.time}</div><h3>${item.title}</h3></div>
        <span class="status-pill ${item.status}">${item.statusText}</span>
      </div>
      <p>${item.text}</p>
    </article>
  `).join("");
  const boardsMarkup = module.boards.map((board) => `
    <article class="mini-board-card">
      <h3>${board.title}</h3>
      <ul>${board.items.map((item) => `<li><span>${item}</span><span class="tag">ok</span></li>`).join("")}</ul>
    </article>
  `).join("");
  $("#module-content").innerHTML = `
    <section class="detail-grid">${cardsMarkup}</section>
    <section>
      <div class="section-heading compact"><div><span class="eyebrow">Linea de accion</span><h2>Que pasa en este modulo</h2></div></div>
      <div class="timeline-list">${timelineMarkup}</div>
    </section>
    <section>
      <div class="section-heading compact"><div><span class="eyebrow">Listas inteligentes</span><h2>Apoyo operativo</h2></div></div>
      <div class="mini-board">${boardsMarkup}</div>
    </section>
    <p class="footer-note">Mam-IA esta pensada como PWA responsive para uso web y movil, con accion rapida, iconos grandes y datos compartidos por la familia.</p>
  `;
}

function renderDailySummary() {
  const items = [
    { title: "Mochilas listas", text: "Ropa de natacion y autorizacion firmada.", time: "07:40" },
    { title: "Compra inteligente", text: "Supermercado y farmacia en la misma ruta.", time: "17:30" },
    { title: "Dentista de Leo", text: "Llevar tarjeta sanitaria y radiografia.", time: "11:00" },
    { title: "Cena en pareja", text: "Bloqueada despues de acostar a los peques.", time: "21:30" }
  ];
  $("#daily-summary").innerHTML = items.map((item) => `<li class="summary-item"><div><strong>${item.title}</strong><span>${item.text}</span></div><div class="summary-time">${item.time}</div></li>`).join("");
}

function renderMembers() {
  $("#family-members").innerHTML = STATE.members.map((member) => `
    <article class="family-member">
      <div class="avatar-cluster">
        <div class="avatar">${member.badge}</div>
        <div><strong>${member.name}</strong><span>${member.role}</span></div>
      </div>
      <span class="tag">Activo</span>
    </article>
  `).join("");
}

function renderInvitations() {
  $("#invite-list").innerHTML = STATE.invitations.map((invite) => `<li class="invite-item"><div><strong>${invite.name}</strong><span>${invite.email}</span></div><div class="invite-status">${invite.status}</div></li>`).join("");
}

function renderSettings() {
  const cards = [
    { title: "Unidad familiar", text: "Crear, editar y eliminar miembros." },
    { title: "Permisos", text: "Roles para madre, pareja, hijos y abuelos." },
    { title: "Avisos", text: "Push, recordatorios y resúmenes diarios." },
    { title: "Temas", text: "Paletas suaves y visuales para cada estilo." }
  ];
  $("#settings-cards").innerHTML = cards.map((card) => `<article class="setting-card"><strong>${card.title}</strong><p>${card.text}</p></article>`).join("");
}

function bindEvents() {
  $("#theme-picker").addEventListener("change", (event) => applyTheme(event.target.value));
  $("#family-mode-toggle").addEventListener("click", () => {
    STATE.familyMode = !STATE.familyMode;
    $("#family-mode-toggle").textContent = STATE.familyMode ? "Vista personal" : "Vista familiar";
    renderFocusCards();
  });
  $("#invite-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const nameField = $("#invite-name");
    const emailField = $("#invite-email");
    STATE.invitations.unshift({ name: nameField.value.trim(), email: emailField.value.trim(), status: "Pendiente" });
    renderInvitations();
    event.target.reset();
  });
}

function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => navigator.serviceWorker.register("./service-worker.js").catch(() => {}));
  }
}

function init() {
  renderThemePicker();
  applyTheme(STATE.theme);
  renderHeroStats();
  renderFocusCards();
  renderModules();
  renderModuleDetail();
  renderDailySummary();
  renderMembers();
  renderInvitations();
  renderSettings();
  bindEvents();
  registerServiceWorker();
}

init();
