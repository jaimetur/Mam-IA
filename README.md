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
