# Despliegue de Mam-IA en el NAS

Mam-IA corre en un contenedor Docker en el NAS (Synology) y se publica en **https://mamia.jtgcloud.com** con el proxy
inverso de DSM, igual que BodyLens.

## 1. Carpeta del stack

En el NAS, crea la carpeta del stack (por ejemplo `/volume1/docker/stacks/mamia`) y la de datos
(`/volume1/docker/data/mamia`). Copia a la del stack:

- `docker/compose.yml`
- `docker/.env.example`, con el nombre `.env`, y rellénalo:
  - `PUBLIC_URL=https://mamia.jtgcloud.com`
  - `MAMIA_ADMIN_EMAIL` (tu correo: será la cuenta de administración, con tu familia gratis para siempre) y una
    `MAMIA_ADMIN_PASSWORD` provisional (se pide cambiarla al entrar la primera vez).
  - `HOST_DATA_DIR`, `PUID` y `PGID` (un usuario o grupo con permiso de escritura en la carpeta de datos; en Synology
    `1034:65544` = docker_limited:docker_users).
  - El correo saliente (`SMTP_*`, o después en Administración → Correo, que manda sobre el `.env`): **sin él no se
    pueden crear cuentas**, porque cada alta confirma su dirección con un código de 6 cifras. También envía las
    invitaciones, las contraseñas olvidadas, los recordatorios y el resumen del día, y los avisos de la cuenta y de
    la suscripción. «Enviarme un correo de prueba» en Administración → Correo lo comprueba.
  - `OPEN_SIGNUP` vacío en el servidor público (las familias entran pagando, con un código o por invitación).

## 2. Arrancar

```bash
cd /volume1/docker/stacks/mamia
docker compose pull
docker compose up -d
```

La app escucha en `APP_PORT` (5071 por defecto, el que ya usa la regla del proxy del NAS). Comprueba `http://<IP del NAS>:5071/healthz` → `{"ok": true}`.

Para actualizar a la última versión publicada (`:latest`, la de la rama de versión más reciente):

```bash
docker compose pull && docker compose up -d
```

## 3. Proxy inverso y certificado

En DSM → Panel de control → Portal de inicio de sesión → Avanzado → Proxy inverso, crea una regla:

| Origen | Destino |
| --- | --- |
| HTTPS · `mamia.jtgcloud.com` · 443 | HTTP · `localhost` · 5071 |

En «Encabezado personalizado» añade WebSocket (no es obligatorio) y comprueba que el certificado de
`mamia.jtgcloud.com` (Let's Encrypt) está asignado a esa regla en Seguridad → Certificado. El DNS de
`mamia.jtgcloud.com` debe apuntar al NAS, como el de `bodylens.jtgcloud.com`.

## 4. Pagos (Stripe)

1. En el panel de Stripe, crea una clave secreta restringida o usa la secreta (`sk_live_…`; `sk_test_…` para probar).
2. Entra en `https://mamia.jtgcloud.com/admin` → **Pagos con Stripe** y pégala: Mam-IA crea el producto «Mam-IA
   (familia)» y los precios de 2,50 €/mes y 25 €/año.
3. En Stripe → Desarrolladores → Webhooks, añade el punto de conexión que muestra Administración
   (`https://mamia.jtgcloud.com/api/web/webhook`) con los eventos `checkout.session.completed` y
   `customer.subscription.*`, y pega su secreto de firma (`whsec_…`) en Administración.
4. Activa el portal de clientes de Stripe (Configuración → Facturación → Portal de clientes), que se usa para cambiar
   la tarjeta y ver las facturas.

Sin Stripe configurado, solo se puede entrar con un código de promoción o por invitación.

## 5. Oferta de lanzamiento y códigos

Por defecto existe el código público `LANZAMIENTO` (alias `LAUNCH`): 1 año gratis para las 50 primeras familias, que se
muestra en la página de inicio con las plazas que quedan. Se cambia en Administración → Códigos de promoción (duración,
fecha de caducidad, número máximo de familias, si es público).

## 6. Copias de seguridad

El servidor copia la base de datos cada noche a las 03:30 en `HOST_DATA_DIR/backups/` y guarda las 30 últimas
(`BACKUP_KEEP`). También se puede hacer una al momento desde Administración. Además, conviene incluir `HOST_DATA_DIR`
en Hyper Backup.

## 7. App de Android

GitHub Actions compila el APK con cada cambio en `android/` y lo publica en la pre-release `android-latest`. La
dirección `https://mamia.jtgcloud.com/android.apk` sirve `HOST_DATA_DIR/android/mamia-android.apk` si existe y, si no,
redirige al de GitHub. Detalles en [ANDROID.md](ANDROID.md).

## 8. La versión anterior

La primera Mam-IA era una página estática (nginx) en `mamia.jaimetur.cloud`. Esta versión la sustituye: el contenedor
antiguo se puede parar. Quien tuviera instalada la PWA antigua en el mismo dominio recibe un service worker de retirada
que limpia la caché y carga la app nueva. Los datos de la versión antigua solo estaban en cada navegador: se pueden
traer desde Ajustes → Copia de seguridad si se abre la app nueva en el mismo navegador y dominio.
