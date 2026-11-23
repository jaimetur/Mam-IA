# ROADMAP - Mam-IA

Referencia histórica: ver [CHANGELOG.md](./CHANGELOG.md)

---

## v0.2.x - Base compartida (hecho en v0.2.0)

- Servidor propio (FastAPI + SQLite en Docker) con cuentas, familias, invitaciones y permisos.
- Interfaz nueva para el móvil: Hoy, Agenda, Tareas y rutinas, Compras, Menú, Peques, Familia y Ajustes.
- Apuntar en lenguaje natural sin IA, avisos push y alarmas nativas en Android, modo sin conexión.
- Suscripción por familia con Stripe, oferta de lanzamiento y administración.
- Pendiente de esta fase: probar la app de Android en dispositivos reales y publicar su primer APK firmado.

## v0.3.x - La casa y los peques

- Casa: mantenimiento y vencimientos (ITV, seguros, revisión de la caldera), recibos y garantías.
- Enlace de calendario (ICS) para ver la agenda en Google o Apple Calendar.
- Avisos por correo antes de que termine el acceso gratis o la suscripción.
- Widget de «Hoy» en Android y atajos.
- Traducción al inglés (los textos ya están preparados).

## v0.4.x - Mam-IA con IA (opcional, API de Claude)

- Apuntar con frases libres o por voz, y foto de una circular del cole convertida en planes y tareas.
- Menú semanal sugerido según gustos, alergias y comedor.
- Resumen del domingo: la semana que viene, choques y lo que falta por organizar.
- Salud de la familia, Dinero (presupuesto y recibos), Viajes (maletas con plantilla) y Para mí.

## v1.0.0 - Versión estable

- App en Google Play (con Google Play Billing) y revisión de la PWA en iPhone.
- Suite de tests de extremo a extremo y observabilidad básica.
- Revisión legal de los textos de privacidad y términos.

---

## Prioridades técnicas transversales

- Accesibilidad (teclado, contraste, lectores de pantalla).
- Rendimiento en móviles de gama media y baja.
- Privacidad: datos de menores tratados como sensibles, sin terceros salvo Stripe y el correo.
