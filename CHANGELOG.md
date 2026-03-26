# CHANGELOG

Todas las fechas usan formato `YYYY-MM-DD`.

---

## [0.1.0] - 2026-03-26

Primera version funcional de `Mam-IA` orientada a MVP de interfaz y despliegue.

### Added

- Nueva aplicacion web/PWA `Mam-IA` en `src/`.
- Interfaz moderna y responsive para desktop y movil.
- Selector de temas de color (persistido en localStorage).
- Modulos funcionales:
  - comidas semanales
  - compras
  - tareas familiares compartidas
  - trabajo
  - limpieza
  - viajes
  - ocio
  - agenda escolar
  - citas medicas
  - belleza
  - planes en pareja
  - presupuesto familiar
  - configuracion familiar
- Panel de invitaciones familiares con persistencia local.
- Centro de administracion familiar (nombre de familia, admin, calendario compartido, notificaciones).
- Logo SVG propio en `src/assets/mam-ia-logo.svg`.
- Soporte PWA:
  - `manifest.webmanifest`
  - `service-worker.js`

### Docker

- `docker/Dockerfile` para construir imagen de la app.
- `docker/docker-compose.yml` para produccion (imagen publicada).
- `docker/docker-compose.dev.yml` para desarrollo (build local).
- `docker/.env` parametrizable:
  - nombre de contenedor
  - puertos prod/dev
  - rutas de config y data
  - red Docker dedicada (subred y gateway) para evitar solapes.

### CI/CD

- Workflow manual de GitHub Actions:
  - `.github/workflows/build_docker.yml`
  - construye y publica imagen en Docker Hub (`jaimetur/mam-ia`)
  - ejecucion on-demand (`workflow_dispatch`).

### Changed

- Documentacion principal migrada desde proyecto anterior a `Mam-IA`.

---

## Notas de versionado

- El versionado actual parte desde `0.1.0` como MVP.
- Se recomienda mantener esquema semantico (`MAJOR.MINOR.PATCH`) a partir de aqui.
