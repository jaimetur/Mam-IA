# Mam-IA

Mam-IA es una app web/PWA para organizacion familiar, pensada para madres con muchas areas que coordinar en el dia a dia:

- planificacion de comidas semanales
- listas de compra
- tareas compartidas familiares
- organizacion de trabajo
- limpieza del hogar con asignaciones
- escapadas y viajes
- ocio y autocuidado
- agenda escolar
- citas medicas
- citas de peluqueria, estetica y manicura
- planes en pareja
- presupuesto familiar
- configuracion de unidad familiar e invitaciones

## Estado actual del proyecto

Version funcional de interfaz moderna y responsive (desktop + movil) con:

- botones grandes e iconos visuales
- selector de tema de colores
- persistencia local de tema, invitaciones y configuracion familiar
- logo propio de Mam-IA
- soporte PWA (manifest + service worker)
- despliegue con Docker en modo produccion y desarrollo
- workflow manual de GitHub Actions para publicar imagen en Docker Hub

## Estructura

```text
Mam-IA/
  runMamIA.py
  tools/
    CreateUpdateRelease.py
  tests/
    test_create_update_release.py
  src/
    index.html
    styles.css
    app.js
    manifest.webmanifest
    service-worker.js
    assets/
      mam-ia-logo.svg
  docker/
    Dockerfile
    .env
    docker-compose.yml
    docker-compose.dev.yml
  .github/
    workflows/
      build_docker.yml
```

## Entorno virtual local

La app no necesita paquetes externos: el lanzador y la herramienta de releases
solo usan la biblioteca estandar de Python. El entorno virtual del proyecto es
`.venv` (excluido de Git), creado con Python 3.12 (con Tk, para la ventana de la
herramienta de releases):

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
```

En PyCharm, selecciona `.venv/bin/python` como interprete del proyecto.

Para que el bytecode (`.pyc`) se genere fuera del proyecto, como indica
`sitecustomize.py`: con el Python de Homebrew, cuyo propio `sitecustomize`
tiene prioridad, anade un archivo `.pth` al `site-packages` del entorno:

```bash
echo "import sys; sys.pycache_prefix = \"$HOME/development/python_cache/Mam-IA/pycache\"" > .venv/lib/python3.12/site-packages/mamia_pycache_prefix.pth
```

Tests:

```bash
.venv/bin/python -m unittest discover -s tests
```

## Ejecucion local rapida (sin Docker)

Desde PyCharm, ejecuta `runMamIA.py`. PyCharm usara el interprete que tengas
configurado para el proyecto, levantara el servidor y abrira la interfaz en el
navegador.

Abrir: `http://127.0.0.1:5173`

Puedes añadir argumentos a la configuracion de ejecucion de PyCharm para no
abrir el navegador automaticamente o elegir otro puerto:

```bash
--no-browser --port 5180
```

Como alternativa, puedes usar el servidor estatico de Python directamente:

```bash
cd src
python -m http.server 5173
```

Abrir: `http://localhost:5173`

## Docker

### 1) Configurar variables

Editar `docker/.env` segun tu entorno:

- `APP_IMAGE` para produccion
- `APP_PORT` para produccion (ejemplo: 5078)
- `APP_PORT_DEV` para desarrollo (ejemplo: 5071)
- `APP_CONFIG_DIR` y `APP_DATA_DIR`
- `DOCKER_SUBNET` y `DOCKER_GATEWAY` si hay conflictos de red

### 2) Levantar produccion

```bash
cd docker
docker compose pull
docker compose up -d
```

Abrir: `http://<IP_SERVIDOR>:APP_PORT`

### 3) Levantar desarrollo (con build)

```bash
cd docker
docker compose -f docker-compose.dev.yml up -d --build
```

Abrir: `http://<IP_SERVIDOR>:APP_PORT_DEV`

## Publicar imagen en Docker Hub (manual)

```bash
docker login
docker build -f docker/Dockerfile -t jaimetur/mam-ia:latest .
docker push jaimetur/mam-ia:latest
```

## Publicar imagen en Docker Hub (automatica con GitHub Actions)

Workflow: `.github/workflows/build_docker.yml`

Trigger:
- `workflow_dispatch` (on demand desde Actions)

Secrets requeridos en GitHub:
- `DOCHERHUB_USERNAME`
- `DOCKERHUB_PASSWORD`

Imagen publicada:
- `jaimetur/mam-ia:latest`
- tags por rama y sha

## Publicar una nueva release

Ejecuta `tools/CreateUpdateRelease.py` con el interprete del proyecto
(configuracion de ejecucion de PyCharm **CreateUpdateRelease**). La version y la
fecha de la release actual salen de la primera cabecera `## Release:` de
`CHANGELOG.md`.

- **Update Current Release** reescribe esa cabecera y pone la misma version en
  el nombre de la cache del service worker (`src/service-worker.js`).
- **Create New Release** crea una rama con el nombre de la nueva version
  (`X.Y.Z`), anade un bloque de release vacio al principio de `CHANGELOG.md`,
  actualiza la version del service worker, y confirma y sube la rama a `origin`.

Sin Tk pregunta en el terminal. Tambien acepta
`--update VERSION FECHA` y `--create VERSION FECHA [--dirty commit|carry|discard]`.

## Configuracion familiar (UI)

Desde el modulo `Configuracion familiar` puedes gestionar:

- nombre de unidad familiar
- administradora principal
- calendario compartido on/off
- notificaciones on/off
- visualizacion de miembros y roles
- invitaciones por email desde panel lateral

## Notas

- Proyecto en evolucion activa.
- El backend actualmente es frontend-first (estado en localStorage).
- La siguiente fase prevista incluye autenticacion y sincronizacion multiusuario real.
