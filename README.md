# Mam-IA

[Leer en español](README_ES.md)

<p align="center">
  <a href="https://mamia.jtgcloud.com"><img src="https://img.shields.io/badge/Visit_the_website-mamia.jtgcloud.com-C93E66?style=for-the-badge&labelColor=2B1622&logo=googlechrome&logoColor=white" alt="Visit the Mam-IA website: mamia.jtgcloud.com" height="40"></a>
  &nbsp;
  <a href="https://mamia.jtgcloud.com/app"><img src="https://img.shields.io/badge/Open_the_app-mamia.jtgcloud.com%2Fapp-FFE39B?style=for-the-badge&labelColor=2B1622&logo=pwa&logoColor=white" alt="Open the Mam-IA app: mamia.jtgcloud.com/app" height="40"></a>
</p>

Mam-IA is the shared organiser for the whole family, made for mothers who run the household, the kids and their jobs
all at once: everything there is to remember, in one place and shared across the family.

- **Today**: what comes next, everyone's day on a timeline, what must not be forgotten, dinner and the shopping.
- **Family calendar**: day, week and month views, one colour per person, repeating plans, who drops off and who picks
  up, and a warning when two plans clash.
- **Jot it down in 5 seconds**: type or dictate «Dentista Lucas el jueves a las 17:30, lo lleva Pablo» (Lucas's dentist
  on Thursday at 17:30, Pablo takes him) and it fills itself in (no AI).
- **Tasks and routines**: with a date, person, reminder, repetition and rotating turns; and the **split** of the
  week's workload, with suggestions to balance it.
- **Live shopping**: lists by shop and section, "the usual" in one tap; what one person ticks off, everyone sees.
- **Weekly meals** with the school canteen menu and allergies; missing ingredients go onto the shopping list.
- **Kids**: each child's profile (school, schedules, health, allergies, sizes, contacts, birthdays).
- **Reminders that arrive**: exact alarms on Android and push notifications in the browser.
- **Family**: up to 8 people; the adults with their own account (invitation by email or by link) and the kids as
  profiles. Works offline, with dark mode and 4 colours.

It is sold as a service at **https://mamia.jtgcloud.com**: €2.50/month or €25/year per family, a 7-day trial, and a
launch offer of 1 free year for the first 50 families (public code `LANZAMIENTO`).

## How it is built

```text
Mam-IA/
  src/backend/app/        FastAPI + SQLite server (package app)
    core/                 settings, database, security, encryption, email, backups, version
    accounts/             accounts, sessions and passwords
    families/             families, invitations, permissions, export and import
    data/                 each family's data (validated documents) and its sync
    push/                 repeats, reminders and Web Push notifications
    billing/              promotion codes, Stripe and Google Play subscriptions and read-only mode
    admin/                server administration and the Business dashboard
    web/                  pages and static files
  src/frontend/
    landing/              the public page (/) with the plans and the offer
    app/                  the app (/app): JavaScript modules, no build step; PWA with a service worker
    accounts/             sign in, sign up, join, password reset, account and welcome
    admin/                server administration (/admin)
    legal/                privacy, terms and account deletion
    common/               design tokens, fonts, interface icons and page styles
  assets/branding/        brand logo and icons (favicon, PWA, Apple), served at the site root
  lang/                   languages: English catalog and one translation per language (lang/README.md)
  android/                Android app (the web app in a native window, with exact alarms): docs/ANDROID.md
  docker/                 production and development image and compose files
  tests/                  pytest (server) and node --test (web app)
  tools/                  CreateUpdateRelease.py, make_icons.py, play_screenshots.py and play_publish.py
```

The app keeps a copy of the family's data on the device, plus any changes not yet sent: it works offline and syncs when
the network returns. While open it polls the server every few seconds, so what one person adds, the others see
immediately.

## Local development

With Python 3.12 (the Homebrew one, with Tk for the release tool):

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[test,dev]"
```

In PyCharm, select `.venv/bin/python` as the project interpreter and run **runMamIA** (`runMamIA.py`): it starts the
server with development data in `data-dev/` and opens `http://127.0.0.1:5173`. With an empty database it creates the
administration account `admin@mamia.local` (initial password `mamia-admin`, you are asked to change it). Locally,
families can sign up without paying. Arguments: `--port 5180`, `--no-browser`, `--reload`, `--host 0.0.0.0` (to open it
from a phone on the same network).

To have the bytecode (`.pyc`) generated outside the project, as `sitecustomize.py` intends: with the Homebrew Python,
whose own `sitecustomize` takes precedence, add a `.pth` file to the environment's `site-packages`:

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

With Docker (hot reload): `docker compose -f docker/compose.dev.yml up --build` → `http://localhost:8000`.

## Deployment

On the NAS, with Docker and the Synology reverse proxy at `https://mamia.jtgcloud.com`: see
[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). The `jaimetur/mam-ia` image is built by GitHub Actions
(`.github/workflows/build_docker.yml`): `:main` on every push to `main`, and `:X.Y.Z` + `:latest` on every push to a
version branch. Payments (Stripe and Google Play), promo codes and email are configured under **Administration →
Business** (`/admin#negocio`), which also shows the figures: families, subscriptions, revenue and downloads.

## Publishing a new release

Run `tools/CreateUpdateRelease.py` with the project interpreter (PyCharm run configuration **CreateUpdateRelease**).
The current release's version and date come from the first `## Release:` heading in `CHANGELOG.md`.

- **Update Current Release** rewrites that heading and sets the same version in `pyproject.toml`, in the service worker
  cache (`src/frontend/app/sw.js`) and in the Android `versionName` (`android/app/build.gradle.kts`).
- **Create New Release** creates a branch named after the new version (`X.Y.Z`), adds an empty release block at the top
  of `CHANGELOG.md`, updates those versions, and commits and pushes the branch to `origin` (which publishes the
  `:X.Y.Z` and `:latest` image).

Without Tk it asks in the terminal. It also accepts `--update VERSION DATE` and
`--create VERSION DATE [--dirty commit|carry|discard]`.

## Logo and icons

`tools/make_icons.py` draws the logo and the PNG icons for the PWA, Apple and the favicon into `assets/branding/` (like BodyLens); the server serves them at the site root (`/logo.svg`, `/icon-192.png`…).
The interface icons are from [Lucide](https://lucide.dev) (ISC licence), and the fonts, Bricolage Grotesque and
Figtree (SIL Open Font License), are served from the server itself.
