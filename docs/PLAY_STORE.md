# Google Play: la app de Android en la tienda y las suscripciones

Mam-IA para Android (`app.mamia.android`) se puede instalar de dos formas:

- **Descarga directa**: el APK que sirve el propio servidor en `/android.apk`. La landing enseña el botón cuando
  `/api/android` dice `available: true`.
- **Google Play**: la tienda. Dentro de la app, la suscripción de la familia se compra con Google Play, porque Play
  no permite cobrar suscripciones digitales de otra forma. En la web se sigue pagando con Stripe.

Los dos caminos usan la misma clave de firma, así que el APK del servidor y el de Play se pueden actualizar el uno
sobre el otro. La guía sigue lo que ya funciona en BodyLens.

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

- Nombre: **Mam-IA**. Idioma predeterminado: **español (España)**. Añade traducciones de la ficha si quieres (la app
  está en 10 idiomas).
- App, **gratis**: las suscripciones son productos dentro de la app.
- Categoría: **Productividad** o **Crianza** (Parenting).
- Contacto: `mamia@jtgcloud.com`, web `https://mamia.jtgcloud.com`.
- Icono de la ficha: `assets/branding/icon-maskable-512.png` (512×512, cuadrado completo: Play redondea las esquinas).
- Firma de la app: «Usar mi propia clave». Exporta `mamia-upload.jks` con la herramienta PEPK de Google, para que el
  APK del servidor y el de Play compartan firma.
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

## 7. Antes de la primera subida

- Crea la clave (paso 1) y espera a que GitHub compile con ella: el registro de Actions debe decir `release key`.
- Sube `mamia-android.aab` (de la release `android-latest`) a una prueba interna, configura la suscripción y la
  cuenta de servicio, y prueba una compra con una cuenta de prueba de licencias (Configuración → Pruebas de licencia).
