# ROADMAP - Mam-IA

Referencia historica: ver [CHANGELOG.md](./CHANGELOG.md)

---

## v0.2.x - Producto usable en familia real (corto plazo)

- Persistencia real con backend (API + base de datos).
- Gestion de cuentas familiares con login y roles:
  - administradora
  - colaborador
  - miembro
- CRUD completo de tareas y eventos por modulo.
- Calendario compartido mensual/semanal con filtros por miembro.
- Recordatorios basicos de tareas/citas.
- Exportacion/backup de datos familiares.

## v0.3.x - Colaboracion y sincronizacion (medio plazo)

- Sincronizacion multi-dispositivo en tiempo real.
- Invitaciones reales por email con token.
- Notificaciones push web/mobile.
- Comentarios y estado por tarea (pendiente/en curso/hecha).
- Plantillas reutilizables:
  - menu semanal
  - rutina de limpieza
  - lista de compra tipo
- Vista de carga familiar por miembro (equilibrio de tareas).

## v0.4.x - Inteligencia y automatizacion (medio-largo plazo)

- Sugerencias de planificacion con IA:
  - menu semanal segun preferencias/restricciones
  - reparto de tareas equilibrado
  - ventanas de tiempo libre recomendadas
- Priorizacion automatica por urgencia y contexto.
- Deteccion de conflictos de agenda.
- Resumen semanal automatico con alertas clave.

## v1.0.0 - Version estable (largo plazo)

- Apps moviles nativas (Android/iOS) o wrapper robusto PWA.
- Integraciones externas:
  - Google Calendar / Apple Calendar (opcional)
  - proveedores de compra (opcional)
- Seguridad reforzada:
  - cifrado de datos sensibles
  - auditoria de accesos
- Observabilidad y metricas de uso anonimas.
- Suite de tests (unitarios, integracion y e2e) con CI completo.

---

## Prioridades tecnicas transversales

- Mejorar accesibilidad (teclado, contraste, lectores de pantalla).
- Mejorar rendimiento en movil de gama media/baja.
- Internacionalizacion (ES/EN en primera fase).
- Documentacion tecnica y de usuario alineada por version.
