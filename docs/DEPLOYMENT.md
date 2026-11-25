# Deploying Mam-IA on the NAS

Mam-IA runs in a Docker container on the NAS (Synology) and is published at **https://mamia.jtgcloud.com** through the
DSM reverse proxy, like BodyLens.

## 1. Stack folder

On the NAS, create the stack folder (for example `/volume1/docker/stacks/mamia`) and the data folder
(`/volume1/docker/data/mamia`). Copy into the stack folder:

- `docker/compose.yml`
- `docker/.env.example`, named `.env`, and fill it in:
  - `PUBLIC_URL=https://mamia.jtgcloud.com`
  - `MAMIA_ADMIN_EMAIL` (your email: it will be the administration account, with your family free forever) and a
    temporary `MAMIA_ADMIN_PASSWORD` (you are asked to change it on first sign-in).
  - `HOST_DATA_DIR`, `PUID` and `PGID` (a user or group with write permission on the data folder; on Synology
    `1034:65544` = docker_limited:docker_users).
  - Outgoing email (`SMTP_*`, or later in Administration → Business → Email, which overrides the `.env`): **without it
    accounts cannot be created**, because every sign-up confirms its address with a 6-digit code. It also sends
    invitations, forgotten passwords, reminders and the daily summary, and account and subscription notices.
    «Send me a test email» in Administration → Business → Email checks it.
  - `OPEN_SIGNUP` empty on the public server (families join by paying, with a code or by invitation).

## 2. Start

```bash
cd /volume1/docker/stacks/mamia
docker compose pull
docker compose up -d
```

The app listens on `APP_PORT` (5071 by default, the one the NAS proxy rule already uses). Check `http://<NAS IP>:5071/healthz` → `{"ok": true}`.

To update to the latest published version (`:latest`, from the most recent version branch):

```bash
docker compose pull && docker compose up -d
```

## 3. Reverse proxy and certificate

In DSM → Panel de control → Portal de inicio de sesión → Avanzado → Proxy inverso, create a rule:

| Source | Destination |
| --- | --- |
| HTTPS · `mamia.jtgcloud.com` · 443 | HTTP · `localhost` · 5071 |

In «Encabezado personalizado» add WebSocket (optional) and check that the `mamia.jtgcloud.com` certificate (Let's
Encrypt) is assigned to that rule in Seguridad → Certificado. The DNS for `mamia.jtgcloud.com` must point to the NAS,
like the one for `bodylens.jtgcloud.com`.

## 4. Payments (Stripe)

1. In the Stripe dashboard, create a restricted secret key or use the secret key (`sk_live_…`; `sk_test_…` for testing).
2. Go to `https://mamia.jtgcloud.com/admin` → **Business → Payments · Stripe** and paste it: Mam-IA creates the product
   «Mam-IA (familia)» and the prices of €2.50/month and €25/year.
3. In Stripe → Desarrolladores → Webhooks, add the endpoint that Administration shows
   (`https://mamia.jtgcloud.com/api/web/webhook`) with the events `checkout.session.completed` and
   `customer.subscription.*`, and paste its signing secret (`whsec_…`) into Administration.
4. Enable the Stripe customer portal (Configuración → Facturación → Portal de clientes), which is used to change the
   card and view invoices.

Without Stripe configured, families can only join with a promo code or by invitation.

## 5. Launch offer and codes

By default the public code `LANZAMIENTO` (alias `LAUNCH`) exists: 1 free year for the first 50 families, shown on the
home page with the places left. It is changed in Administration → Business → Subscriptions and codes (duration, expiry
date, maximum number of families, whether it is public).

## 6. Backups

The server copies the database every night at 03:30 to `HOST_DATA_DIR/backups/` and keeps the last 30
(`BACKUP_KEEP`). One can also be made on the spot from Administration. It is also worth including `HOST_DATA_DIR` in
Hyper Backup.

## 7. Android app

GitHub Actions builds the APK on every change to `android/` and publishes it to the `android-latest` pre-release. The
address `https://mamia.jtgcloud.com/android.apk` serves `HOST_DATA_DIR/android/mamia-android.apk` if it exists and,
otherwise, redirects to the GitHub one. Details in [ANDROID.md](ANDROID.md).

## 8. The previous version

The first Mam-IA was a static page (nginx) at `mamia.jaimetur.cloud`. This version replaces it: the old container can
be stopped. Anyone who had the old PWA installed on the same domain receives a retirement service worker that clears
the cache and loads the new app. The old version's data lived only in each browser: it can be brought over from
Settings → «Copia de seguridad» (Backup) if the new app is opened in the same browser and domain.
