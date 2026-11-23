# CHANGELOG

Todas las fechas usan formato `YYYY-MM-DD`.

---

## Release: v0.1.0
### Release Date: 2026-03-26
Primera version funcional de `Mam-IA` orientada a MVP de interfaz y despliegue.

#### 🌟 Novedades:
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
- Lanzador `runMamIA.py` para iniciar la interfaz web desde PyCharm con el intérprete configurado en el proyecto y abrirla automáticamente en el navegador.
- Herramienta `tools/CreateUpdateRelease.py` y su configuración de ejecución de PyCharm (**CreateUpdateRelease**) para actualizar la release actual o crear, confirmar y subir a `origin` una nueva rama de release.

#### 🐳 Docker:
- `docker/Dockerfile` para construir imagen de la app.
- `docker/docker-compose.yml` para produccion (imagen publicada).
- `docker/docker-compose.dev.yml` para desarrollo (build local).
- `docker/.env` parametrizable:
  - nombre de contenedor
  - puertos prod/dev
  - rutas de config y data
  - red Docker dedicada (subred y gateway) para evitar solapes.

#### ⚙️ CI/CD:
- Workflow manual de GitHub Actions:
  - `.github/workflows/build_docker.yml`
  - construye y publica imagen en Docker Hub (`jaimetur/mam-ia`)
  - ejecucion on-demand (`workflow_dispatch`).

#### 🚀 Mejoras:
- La configuración local de PyCharm (`.idea/`) queda excluida del control de versiones.
- La caché del service worker lleva la versión de la release (`mam-ia-vX.Y.Z`): cada release nueva sustituye los archivos que guardan en caché los navegadores y la PWA instalada.

#### 📚 Documentación:
- Documentacion principal migrada desde proyecto anterior a `Mam-IA`.
- Documentación de ejecución local actualizada con el uso del lanzador de PyCharm y sus argumentos opcionales.
- README: creación del entorno virtual local (`.venv`) y uso de la herramienta de releases.
- CHANGELOG con la cabecera `## Release:` / `### Release Date:` que usa la herramienta de releases.

---

## Notas de versionado

- El versionado actual parte desde `0.1.0` como MVP.
- Se recomienda mantener esquema semantico (`MAJOR.MINOR.PATCH`) a partir de aqui.
