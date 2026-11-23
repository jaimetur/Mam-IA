# App de Android

La app de Android (`android/`) abre la web de Mam-IA a pantalla completa, como la de BodyLens: es la misma app que en
el navegador, así que cada cambio del servidor se ve en el móvil al momento. Añade lo que una web no puede hacer sola:

- **Avisos a su hora exacta**, aunque el móvil esté en reposo y sin abrir la app. La web le pasa los recordatorios de
  los próximos días (`MamIANative.setAlarms`) y Android los programa; tras reiniciar el móvil o actualizar la app se
  vuelven a programar. Cada aviso tiene los botones **Hecho** y **Posponer 10 min**.
- **Compartir con Mam-IA** desde WhatsApp, el navegador o cualquier app que comparta texto: se abre «Apuntar» con ese
  texto (`/app?apuntar=…`).
- Los enlaces a `https://mamia.jtgcloud.com` (invitaciones, correos) se abren en la app.
- Descargas del servidor, elegir archivos (importar una copia), guardar la copia de la familia en Descargas, botón
  atrás, pantalla de arranque y barras del sistema del color del tema.
- Pago de la suscripción con Stripe dentro de la app (sus páginas de pago no salen al navegador).

La primera vez pide la dirección del servidor (por defecto `https://mamia.jtgcloud.com`); se puede cambiar desde la
pantalla «sin conexión».

## Interfaz con la web (`window.MamIANative`)

| Método | Para qué |
|---|---|
| `setAlarms(json)` | Lista completa de avisos `[{id, at, title, body, path}]` (`at` en milisegundos Unix, `path` como `/app#agenda`). Sustituye a la anterior; máximo 200. |
| `notificationsAllowed()` | `true` si la app puede mostrar notificaciones. |
| `exactAlarmsAllowed()` | `true` si los avisos suenan a su hora exacta (Android 12+ permite quitarlo). |
| `askNotifications()` | Pide el permiso de notificaciones y, si falta, abre el ajuste de alarmas exactas. La página recibe el evento `mamia-notifications` con `{allowed, exact}` (también al volver a la app). |
| `saveFile(nombre, mime, base64)` | Guarda un archivo en Descargas (Android 10+) o lo comparte (Android 9). |
| `appVersion()` | Versión de la app. |
| `changeServer()` | Vuelve a la pantalla para elegir el servidor. |

El botón atrás pregunta antes a la página con `window.mamiaBack()` (si devuelve `true`, la página ha cerrado algo
suyo, como una hoja o un menú). El agente de usuario termina en ` MamIAApp/<versión>`.

## Compilar en local

Hace falta el SDK de Android (Android Studio) y Java 17:

```bash
cd android && gradle assembleDebug
```

El APK queda en `android/app/build/outputs/apk/debug/app-debug.apk`.

## Firma y publicación

El workflow `.github/workflows/android.yml` compila la versión de release en cada cambio de `android/` (en `main` o en
una rama de versión `X.Y.Z`) y la publica en la pre-release continua **`android-latest`** de GitHub como
`mamia-android.apk`. Llamado desde un workflow de release con `release_tag`, adjunta `mamia-android-vX.Y.Z.apk` a esa
release.

Para firmar con una clave propia (necesaria para que las actualizaciones se instalen encima), añade estos secretos al
repositorio; sin ellos se firma con la clave de depuración:

- `ANDROID_KEYSTORE_B64`: el almacén de claves (`.jks`) en base64.
- `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` y `ANDROID_KEY_PASSWORD`.

El número de compilación del workflow (`MAMIA_ANDROID_BUILD`) es el `versionCode` y el último número del
`versionName` (`0.2.<compilación>`); `tools/CreateUpdateRelease.py` cambia la parte `0.2.` en cada release.

## Cómo llega a las familias

- Desde GitHub: la release `android-latest` (o el APK de cada versión).
- Desde el propio servidor: `https://mamia.jtgcloud.com/android.apk` sirve `<DATA_DIR>/android/mamia-android.apk`
  cuando existe; basta con copiar ahí el APK de `android-latest` al desplegar.

Google Play queda para más adelante (requiere cuenta de desarrollador, ficha y política de privacidad, y cobrar la
suscripción con Google Play Billing en lugar de Stripe).
