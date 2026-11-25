# Google Play: la app de Android en la tienda y las suscripciones

Mam-IA para Android (`app.mamia.android`) se puede instalar de dos formas:

- **Descarga directa**: el APK que sirve el propio servidor en `/android.apk`. La landing enseña el botón cuando
  `/api/android` dice `available: true`.
- **Google Play**: la tienda. Dentro de la app, la suscripción de la familia se compra con Google Play, porque Play
  no permite cobrar suscripciones digitales de otra forma. En la web se sigue pagando con Stripe.

Con la clave generada por Google, la versión de Play y el APK del servidor tienen firmas distintas: cada una se
actualiza sobre sí misma, no la una sobre la otra. La guía sigue lo que ya funciona en BodyLens.

## 1. La clave de firma (una vez, la creas tú)

```bash
cd ~/PycharmProjects/Mam-IA && tools/android-keystore.sh
```

- Crea `~/mamia-upload.jks`, con la contraseña que elijas.
- Guarda la clave en 4 secretos del repositorio: `ANDROID_KEYSTORE_B64`, `ANDROID_KEYSTORE_PASSWORD`,
  `ANDROID_KEY_ALIAS` y `ANDROID_KEY_PASSWORD`.
- **Guarda el `.jks` y su contraseña en tu gestor de contraseñas.** Si se pierden, ninguna versión nueva se podrá
  instalar encima de las anteriores.

Sin esos secretos, GitHub firma cada compilación con una clave de depuración nueva. La firma cambia en cada versión
y un APK no se instala encima del anterior. El registro de GitHub Actions avisa de cuál se ha usado: la nota
«Android signature» dice `release key` o `DEBUG key`, junto con la huella SHA-256. La huella también se puede ver así:

```bash
apksigner verify --print-certs mamia-android.apk
```

(`apksigner` viene con las build-tools del SDK de Android; `keytool -printcert -jarfile` no ve la firma v2 de los
APK modernos.)

## 2. Compilar y publicar el APK

- Cada cambio en `android/` compila el APK y el AAB y los deja en la pre-release `android-latest` de GitHub
  (`.github/workflows/android.yml`). El AAB es el fichero que se sube a Play.
- Para llevar el APK al servidor:

  ```bash
  tools/deploy-android.sh
  ```

  Lo copia a `<DATA_DIR>/android/` en el NAS. Comprueba después que `https://mamia.jtgcloud.com/api/android` dice
  `"available": true` y que `/android.apk` descarga.
- El icono es el de la marca: `tools/make_icons.py` genera a la vez `assets/branding/` y el icono de Android.

## 3. Play Console: crear la app

- Nombre: **Mam-IA**. Idioma predeterminado: **inglés (en-US)**, como en BodyLens; el español va como traducción. Añade traducciones de la ficha si quieres (la app
  está en 10 idiomas).
- App, **gratis**: las suscripciones son productos dentro de la app.
- Categoría: **Productividad** o **Crianza** (Parenting).
- Contacto: `mamia@jtgcloud.com`, web `https://mamia.jtgcloud.com`.
- Icono de la ficha: `assets/branding/icon-maskable-512.png` (512×512, cuadrado completo: Play redondea las esquinas).
- Imágenes de la ficha, en los 10 idiomas: `assets/play-store/<código de Play>/` (`es-ES`, `en-US`, `ca`, `fr-FR`,
  `it-IT`, `de-DE`, `pt-PT`, `nl-NL`, `zh-CN`, `ja-JP`), con `feature-graphic.png` (1024×500), `phone/` (1080×1920),
  `tablet/` (1440×2560, las mismas para 7" y 10") y `chromebook/` (2880×1620), y los textos de la ficha en ese idioma
  (`title.txt`, `short_description.txt`, `full_description.txt`). Google Play enseña a cada visitante la traducción de
  la ficha en su idioma, con sus capturas; si su idioma no tiene traducción, le enseña la predeterminada (en-US). Las hace
  `tools/play_screenshots.py` con la app real y la familia de ejemplo de `app.demo.play_review`, con la interfaz y los
  textos de la familia en cada idioma. El workflow «📸 Google Play images» las vuelve a hacer y las sube al repositorio
  cada vez que cambian la interfaz, las traducciones o la familia de ejemplo.
- Firma de la app: **clave generada por Google** (Play App Signing), como en BodyLens. `mamia-upload.jks` es solo la
  clave de subida. Por eso la app de Play y el APK del servidor tienen firmas distintas: quien tenga instalada una
  tiene que desinstalarla para pasar a la otra.
- **Protección automática**: desactivada, porque también se reparte el APK directo.
- Requisitos de Play para el AAB: Play Billing 8.0.0 o más moderno y target SDK 36 (ya están en `android/`).
- Verificación de desarrollador de Android: registra el paquete `app.mamia.android`.

## 4. La suscripción

En **Monetizar → Productos → Suscripciones**, crea la suscripción con ID **`mamia`**:

| Plan base | Renovación | Precio | Oferta |
|---|---|---|---|
| `monthly` | Mensual | 2,50 € | Prueba gratis de 7 días (para clientes nuevos) |
| `yearly` | Anual | 25 € | Prueba gratis de 7 días (para clientes nuevos) |

Los ID tienen que ser exactamente esos: la app pide el producto `mamia` y sus planes `monthly` y `yearly`. Una
suscripción cubre a toda la familia.

## 5. La cuenta de servicio (para que el servidor compruebe las compras)

1. En Google Cloud, en el proyecto vinculado a la Play Console: **IAM → Cuentas de servicio → Crear**. Después,
   **Claves → Añadir clave → JSON** y descarga el fichero.
2. En Play Console: **Usuarios y permisos → Invitar**, con el correo de la cuenta de servicio
   (`…@….iam.gserviceaccount.com`). Dale, para la app Mam-IA, «Ver datos financieros» y «Gestionar pedidos y
   suscripciones».
3. En Mam-IA, entra en **Administración → Google Play** y rellena:
   - Paquete: `app.mamia.android`.
   - Suscripción: `mamia`.
   - Pega el **contenido** del JSON.

   Guarda. La clave se guarda cifrada y nunca se vuelve a mostrar: solo se ve su `client_email`.
4. Cuando la app esté publicada, pon allí también el enlace de la ficha
   (`https://play.google.com/store/apps/details?id=app.mamia.android`). La landing mostrará el botón de Google Play.

Mientras no hay cuenta de servicio, la app no ofrece pagar con Google Play: se entra con un código, por invitación o
con una suscripción de la web.

## 6. Contenido de la app (Política → Contenido de la app)

| Sección | Respuesta |
|---|---|
| Política de privacidad | `https://mamia.jtgcloud.com/privacidad` |
| Anuncios | **No** |
| Acceso a la app | Restringido. Da el correo y la contraseña de una **cuenta de prueba con datos inventados**, nunca la tuya. |
| Público objetivo | **18 años o más**: la crean y la usan adultos; los peques son perfiles sin cuenta. |
| Funciones financieras | Ninguna |
| Eliminación de la cuenta | En la app (Tu cuenta → Borrar mi cuenta) y en la web: `https://mamia.jtgcloud.com/borrar-cuenta` |
| Alarmas exactas (`SCHEDULE_EXACT_ALARM`) | Declara que es una app de **calendario y recordatorios**: avisa de planes y tareas a su hora. |

**Clasificación de contenido (IARC):** todas las preguntas, **No**. Los usuarios interactúan: **Sí**, solo dentro de
la familia (comparten agenda, tareas y lista de la compra). Compras digitales: **Sí** (suscripciones).

**Seguridad de los datos:**

- Datos recogidos (todos: recogidos sí, compartidos no):
  - nombre y correo (obligatorios, para la cuenta);
  - los datos de la familia que apunta el usuario (calendario, tareas, notas; opcionales, para el funcionamiento de
    la app);
  - las notas de salud de los peques (alergias, vacunas; opcionales);
  - el historial de compras (el estado de la suscripción).
- Cifrados en tránsito: **Sí**.
- Se pueden borrar: **Sí**.
- No se recogen ubicación, contactos, fotos ni identificadores de publicidad.

## 7. La cuenta de los revisores (Acceso a la app)

Mam-IA solo se usa con la sesión iniciada, así que Google pide unas credenciales de prueba. Se usa una cuenta propia
para los revisores, con una familia de ejemplo: una pareja, dos peques con su ficha, una agenda de esta semana y la
siguiente, tareas y rutinas, la lista de la compra y el menú. Todo es inventado.

Créala y rellénala en el NAS. El script te pide la contraseña la primera vez y no la muestra ni la guarda:

```bash
ssh nas
```

```bash
sudo docker exec -it mamia python -m app.demo.play_review playreview@jtgcloud.com
```

O sin escribir tú la contraseña: se genera una aleatoria y se guarda solo en un fichero del NAS (no se muestra):

```bash
sudo docker exec mamia python -m app.demo.play_review playreview@jtgcloud.com --password-file /data/secrets/playreview.txt
```

```bash
sudo cat /volume1/docker/data/mamia/secrets/playreview.txt
```

- Se puede volver a ejecutar cuando quieras: reescribe los mismos datos con fechas alrededor de hoy (la agenda queda
  al día) y no duplica nada.
- La familia es gratis para siempre, nunca pasa a solo lectura.
- La pareja (`sam@demo.mamia.invalid`) es una cuenta de demostración, sin contraseña: nadie puede entrar con ella.

En Play Console → Contenido de la app → **Acceso a la app**: «Todas o algunas funciones están restringidas» → añade
el correo `playreview@jtgcloud.com`, la contraseña que elegiste y estas instrucciones:

```
Sign in with the email and password above (server: https://mamia.jtgcloud.com).
The account belongs to a sample family with made-up data: agenda, tasks, shopping list, weekly menu and kids' info.
```

## 8. Antes de la primera subida

- Crea la clave (paso 1) y espera a que GitHub compile con ella: el registro de Actions debe decir `release key`.
- Sube `mamia-android.aab` (de la release `android-latest`) a una prueba interna, configura la suscripción y la
  cuenta de servicio, y prueba una compra con una cuenta de prueba de licencias (Configuración → Pruebas de licencia).
