# Android app

The Android app (`android/`) opens the Mam-IA web app full screen, like BodyLens does: it is the same app as in the
browser, so every server change shows up on the phone immediately. It adds what a web page cannot do on its own:

- **Reminders at their exact time**, even with the phone idle and the app closed. The web app passes it the reminders
  for the coming days (`MamIANative.setAlarms`) and Android schedules them; after a phone restart or an app update they
  are scheduled again. Each reminder has the buttons **Hecho** (Done) and **Posponer 10 min** (Snooze 10 min).
- **Share to Mam-IA** from WhatsApp, the browser or any app that shares text: the «Apuntar» (quick add) screen opens
  with that text (`/app?apuntar=…`).
- Links to `https://mamia.jtgcloud.com` (invitations, emails) open in the app.
- Server downloads, file picking (importing a backup), saving the family backup to Downloads, back button, splash
  screen and system bars in the theme colour.
- Subscription payment with Stripe inside the app (its payment pages do not open in the browser).

The first time, it asks for the server address (`https://mamia.jtgcloud.com` by default); it can be changed from the
«sin conexión» (offline) screen.

## Web interface (`window.MamIANative`)

| Method | Purpose |
|---|---|
| `setAlarms(json)` | Full list of reminders `[{id, at, title, body, path}]` (`at` in Unix milliseconds, `path` like `/app#agenda`). Replaces the previous one; maximum 200. |
| `notificationsAllowed()` | `true` if the app can show notifications. |
| `exactAlarmsAllowed()` | `true` if reminders fire at their exact time (Android 12+ lets the user revoke this). |
| `askNotifications()` | Asks for the notification permission and, if missing, opens the exact alarms setting. The page receives the `mamia-notifications` event with `{allowed, exact}` (also when returning to the app). |
| `saveFile(nombre, mime, base64)` | Saves a file to Downloads (Android 10+) or shares it (Android 9). |
| `appVersion()` | App version. |
| `changeServer()` | Goes back to the screen for choosing the server. |

The back button first asks the page through `window.mamiaBack()` (if it returns `true`, the page has closed something of
its own, such as a sheet or a menu). The user agent ends in ` MamIAApp/<version>`.

## Building locally

You need the Android SDK (Android Studio) and Java 17:

```bash
cd android && gradle assembleDebug
```

The APK ends up at `android/app/build/outputs/apk/debug/app-debug.apk`.

## Signing and publishing

The `.github/workflows/android.yml` workflow builds the release version on every change to `android/` (on `main` or on
a version branch `X.Y.Z`) and publishes it to the rolling **`android-latest`** pre-release on GitHub as
`mamia-android.apk`. When called from a release workflow with `release_tag`, it attaches `mamia-android-vX.Y.Z.apk` to
that release.

To sign with your own key (required for updates to install over the previous version), add these secrets to the
repository; without them it is signed with the debug key:

- `ANDROID_KEYSTORE_B64`: the keystore (`.jks`) in base64.
- `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` and `ANDROID_KEY_PASSWORD`.

The workflow's build number (`MAMIA_ANDROID_BUILD`) is the `versionCode` and the last number of the `versionName`
(`0.2.<build>`); `tools/CreateUpdateRelease.py` changes the `0.2.` part on each release.

## How it reaches families

- From GitHub: the `android-latest` release (or each version's APK).
- From the server itself: `https://mamia.jtgcloud.com/android.apk` serves `<DATA_DIR>/android/mamia-android.apk`
  when it exists; just copy the `android-latest` APK there when deploying.

Google Play comes later (it requires a developer account, a store listing and a privacy policy, and charging the
subscription through Google Play Billing instead of Stripe).
