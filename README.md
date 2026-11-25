# Mam-IA

<p align="center">
  <a href="https://mamia.jtgcloud.com"><img src="https://img.shields.io/badge/Visita_la_web-mamia.jtgcloud.com-C93E66?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Visita la web de Mam-IA: mamia.jtgcloud.com" height="40"></a>
</p>

Mam-IA es la agenda compartida de toda la familia, pensada para las madres que llevan la casa, los peques y el
trabajo a la vez: todo lo que hay que recordar, en un solo sitio y repartido entre la familia.

- **Hoy**: lo siguiente que toca, el día de todos en una línea de tiempo, lo que no se puede olvidar, la cena y la compra.
- **Agenda familiar**: día, semana y mes, un color por persona, planes que se repiten, quién lleva y quién recoge, y
  aviso cuando dos planes chocan.
- **Apuntar en 5 segundos**: escribe o dicta «Dentista Lucas el jueves a las 17:30, lo lleva Pablo» y se rellena solo
  (sin IA).
- **Tareas y rutinas**: con fecha, persona, aviso, repetición y turnos que rotan; y el **reparto** de la carga de la
  semana con sugerencias para equilibrarla.
- **Compras en directo**: listas por tienda y sección, «lo de siempre» en un toque; lo que uno tacha lo ven todos.
- **Menú semanal** con el comedor del cole y las alergias; los ingredientes que faltan van a la compra.
- **Peques**: la ficha de cada uno (cole, horarios, salud, alergias, tallas, contactos, cumpleaños).
- **Avisos que llegan**: alarmas exactas en Android y notificaciones push en el navegador.
- **Familia**: hasta 8 personas; las adultas con su propia cuenta (invitación por correo o por enlace) y los peques como
  perfiles. Funciona sin conexión, con modo oscuro y 4 colores.

Se vende como servicio en **https://mamia.jtgcloud.com**: 2,50 €/mes o 25 €/año por familia, 7 días de prueba, y una
oferta de lanzamiento de 1 año gratis para las 50 primeras familias (código público `LANZAMIENTO`).

## Cómo está hecho

```text
Mam-IA/
  src/backend/app/        servidor FastAPI + SQLite (paquete app)
    core/                 configuración, base de datos, seguridad, cifrado, correo, copias, versión
    accounts/             cuentas, sesiones y contraseñas
    families/             familias, invitaciones, permisos, exportar e importar
    data/                 los datos de cada familia (documentos validados) y su sincronización
    push/                 repeticiones, recordatorios y notificaciones Web Push
    billing/              códigos de promoción, suscripciones con Stripe y modo de solo lectura
    admin/                administración del servidor
    web/                  páginas y ficheros estáticos
  src/frontend/
    landing/              la página pública (/) con los planes y la oferta
    app/                  la app (/app): JavaScript por módulos, sin compilar; PWA con service worker
    accounts/             entrar, alta, unirse, recuperar, cuenta y bienvenida
    admin/                administración del servidor (/admin)
    legal/                privacidad, términos y borrar la cuenta
    common/               tokens de diseño, fuentes, iconos de la interfaz y estilos de las páginas
  assets/branding/        logo e iconos de la marca (favicon, PWA, Apple), servidos en la raíz del sitio
  lang/                   idiomas: catálogo en inglés y una traducción por idioma (lang/README.md)
  android/                app de Android (la web en una ventana nativa, con alarmas exactas): docs/ANDROID.md
  docker/                 imagen y compose de producción y de desarrollo
  tests/                  pytest (servidor) y node --test (app web)
  tools/                  CreateUpdateRelease.py y make_icons.py
```

La app guarda en el dispositivo una copia de los datos de la familia y los cambios que no se han enviado: funciona sin
conexión y se sincroniza al volver la red. Mientras está abierta pregunta al servidor cada pocos segundos, así que lo que
apunta una persona lo ven las demás al momento.

## Desarrollo en local

Con Python 3.12 (el de Homebrew, con Tk para la herramienta de releases):

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[test,dev]"
```

En PyCharm, selecciona `.venv/bin/python` como intérprete del proyecto y ejecuta **runMamIA** (`runMamIA.py`): levanta el
servidor con datos de desarrollo en `data-dev/` y abre `http://127.0.0.1:5173`. Con la base vacía crea la cuenta de
administración `admin@mamia.local` (contraseña inicial `mamia-admin`, se pide cambiarla). En local las familias se dan de
alta sin pagar. Argumentos: `--port 5180`, `--no-browser`, `--reload`, `--host 0.0.0.0` (para abrirla desde el móvil en la
misma red).

Para que el bytecode (`.pyc`) se genere fuera del proyecto, como indica `sitecustomize.py`: con el Python de Homebrew,
cuyo propio `sitecustomize` tiene prioridad, añade un archivo `.pth` al `site-packages` del entorno:

```bash
echo "import sys; sys.pycache_prefix = \"$HOME/development/python_cache/Mam-IA/pycache\"" > .venv/lib/python3.12/site-packages/mamia_pycache_prefix.pth
```

Tests:

```bash
.venv/bin/python -m pytest -q
```

```bash
TZ=Europe/Madrid node --test tests/frontend/*.test.mjs
```

Con Docker (código en caliente): `docker compose -f docker/compose.dev.yml up --build` → `http://localhost:8000`.

## Despliegue

En el NAS, con Docker y el proxy inverso de Synology en `https://mamia.jtgcloud.com`: ver
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). La imagen `jaimetur/mam-ia` la construye GitHub Actions
(`.github/workflows/build_docker.yml`): `:main` con cada push a `main` y `:X.Y.Z` + `:latest` con cada push a una rama de
versión. Los pagos (Stripe) y los códigos de promoción se configuran en **Administración** (`/admin`).

## Publicar una nueva release

Ejecuta `tools/CreateUpdateRelease.py` con el intérprete del proyecto (configuración de ejecución de PyCharm
**CreateUpdateRelease**). La versión y la fecha de la release actual salen de la primera cabecera `## Release:` de
`CHANGELOG.md`.

- **Update Current Release** reescribe esa cabecera y pone la misma versión en `pyproject.toml`, en la caché del service
  worker (`src/frontend/app/sw.js`) y en el `versionName` de Android (`android/app/build.gradle.kts`).
- **Create New Release** crea una rama con el nombre de la nueva versión (`X.Y.Z`), añade un bloque de release vacío al
  principio de `CHANGELOG.md`, actualiza esas versiones, y confirma y sube la rama a `origin` (lo que publica la imagen
  `:X.Y.Z` y `:latest`).

Sin Tk pregunta en el terminal. También acepta `--update VERSION FECHA` y
`--create VERSION FECHA [--dirty commit|carry|discard]`.

## Logo e iconos

`tools/make_icons.py` dibuja el logo y los iconos PNG de la PWA, Apple y el favicon en `assets/branding/` (como BodyLens); el servidor los sirve en la raíz del sitio (`/logo.svg`, `/icon-192.png`…).
Los iconos de la interfaz son de [Lucide](https://lucide.dev) (licencia ISC) y las fuentes, Bricolage Grotesque y
Figtree (SIL Open Font License), se sirven desde el propio servidor.
