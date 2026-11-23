# CHANGELOG

Todas las fechas usan formato `YYYY-MM-DD`.

---

## Release: v0.2.0
### Release Date: 2026-11-23
#### ⚠️ Cambios incompatibles:
- **De una página en el navegador a un servicio con servidor propio.** Los datos ya no viven solo en el navegador: cada familia tiene su cuenta en el servidor de Mam-IA (FastAPI + SQLite en Docker, en el NAS) y se comparten al momento entre todos sus móviles. La imagen de Docker ahora es el servidor (antes, nginx con ficheros estáticos) y escucha en el puerto 8000. Los datos de la versión anterior se pueden traer desde Ajustes si se abre la app nueva en el mismo navegador.
- Dominio de producción: `https://mamia.jtgcloud.com`.

#### 🌟 Novedades:
- **Interfaz nueva, primero para el móvil**: navegación inferior, botón «+» siempre a mano y menú lateral en el ordenador.
- **Hoy**: lo siguiente que toca con su cuenta atrás, el día de toda la familia, lo que no se puede olvidar, mañana, la cena y la compra.
- **Agenda familiar** de día, semana y mes: un color por persona, filtros, planes que se repiten, quién lleva y quién recoge, planes de varios días y aviso cuando dos planes chocan.
- **Apuntar en 5 segundos**: escribe o dicta en lenguaje normal («Dentista Lucas el jueves a las 17:30, lo lleva Pablo», «comprar leche y pan», «recuérdame pagar el comedor mañana a las 10») y se convierte en plan, tarea, recordatorio o compra, sin IA.
- **Tareas y rutinas**: fecha, hora, persona, aviso, importancia, repetición y turnos que rotan; apartados de pendientes, rutinas, hechas y **reparto de la carga** con sugerencias para equilibrarla.
- **Compras en directo**: listas por tienda ordenadas por sección, cantidades, «lo de siempre» en un toque y aviso de quién está tachando ahora mismo.
- **Menú semanal** con el comedor del cole y las alergias de la familia; los ingredientes que faltan pasan a la compra y se puede repetir la semana anterior.
- **Peques**: ficha de cada niño (cole, horarios y extraescolares, alergias, salud, pediatra, tallas, contactos, cumpleaños) y sus próximos planes.
- **Familia**: hasta 8 personas; las adultas con su propia cuenta (invitación por correo o enlace para WhatsApp), los peques como perfiles, permisos de administración y pasar la familia a otra persona.
- **Avisos**: notificaciones push en el navegador (con botón «Hecho» en las tareas) y alarmas exactas en la app de Android.
- **App de Android** (`android/`): la web a pantalla completa con alarmas exactas aunque el móvil esté en reposo, notificaciones con «Hecho» y «Posponer 10 min», y «Compartir con Mam-IA» desde otras apps. El APK lo compila GitHub Actions.
- **Funciona sin conexión** (PWA instalable con iconos PNG y maskable) y se sincroniza al volver la red.
- **Suscripción por familia**: 2,50 €/mes o 25 €/año con 7 días de prueba (Stripe: tarjeta, Google Pay o Apple Pay), cambio de plan, cancelación y modo de solo lectura al terminar.
- **Oferta de lanzamiento**: 1 año gratis para las 50 primeras familias con el código `LANZAMIENTO`, con las plazas que quedan en la página de inicio.
- **Página de inicio** nueva con las funciones, los planes, la oferta y las preguntas frecuentes, y páginas de privacidad, términos y cómo borrar la cuenta.
- **Cuentas**: alta, entrar, contraseña olvidada por correo, cambiar nombre, correo y contraseña, y borrar la cuenta o la familia entera.
- **Administración** del servidor (`/admin`): familias y su acceso, dar acceso gratis, códigos de promoción, Stripe y copias de seguridad.
- Aspecto: modo claro, oscuro o automático y 4 colores (rosa, lavanda, menta y coral). Logo nuevo.
- Copia de seguridad: descargar e importar los datos de la familia, y copia automática del servidor cada noche (se guardan 30).

#### 🚀 Mejoras:
- `tools/CreateUpdateRelease.py` pone la versión también en `pyproject.toml` y en el `versionName` de Android, y la caché del service worker está ahora en `src/frontend/app/sw.js`.
- GitHub Actions pasa los tests y publica la imagen `jaimetur/mam-ia` con cada push (`:main`, y `:X.Y.Z` + `:latest` en las ramas de versión).
- Las fuentes y los iconos se sirven desde el propio servidor (sin Google Fonts ni CDN): más privacidad y funcionan sin conexión.
- `runMamIA.py` levanta el servidor completo en local con datos de desarrollo.

#### 🐛 Correcciones:
- La semana de la agenda ponía cada evento un día más tarde en España, y «hoy» cambiaba a medianoche en hora UTC: ahora todas las fechas son locales.
- Los recordatorios no avisaban en el móvil (solo con la pestaña abierta, y Android no permite `new Notification()`).
- Quitar a una persona borraba todas sus tareas: ahora se quedan, a su nombre.
- Los títulos y nombres podían inyectar HTML en la página: todo lo que escribe la familia se escapa y el servidor valida cada dato.
- Las invitaciones se marcaban como «Enviado» sin enviar nada: ahora llega un correo o un enlace para compartir.
- Los choques de la agenda solo se buscaban entre planes seguidos.
- La PWA antigua guardaba la página para siempre: un service worker de retirada la limpia y carga la app nueva.

#### 📚 Documentación:
- README nuevo, guía de despliegue en el NAS (`docs/DEPLOYMENT.md`) y de la app de Android (`docs/ANDROID.md`).

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
