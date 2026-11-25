# CHANGELOG

All dates use the `YYYY-MM-DD` format.

---

## Release: v0.2.0
### Release Date: 2026-11-23
#### ⚠️ Breaking Changes:
- **From a single browser page to a service with its own server.** Data no longer lives only in the browser: each family has an account on the Mam-IA server (FastAPI + SQLite in Docker, on the NAS) and it is shared instantly across all their phones. The Docker image is now the server (it used to be nginx serving static files) and listens on port 8000. Data from the previous version can be brought over from Settings by opening the new app in the same browser.
- Production domain: `https://mamia.jtgcloud.com`.

#### 🌟 New Features:
- **New mobile-first interface**: bottom navigation, an always-at-hand «+» button and a side menu on desktop.
- **Today**: what comes next with its countdown, the whole family's day, what must not be forgotten, tomorrow, dinner and the shopping.
- **Family calendar** by day, week and month: one colour per person, filters, repeating plans, who drops off and who picks up, multi-day plans and a warning when two plans clash.
- **Jot things down in 5 seconds**: type or dictate in plain language («Dentista Lucas el jueves a las 17:30, lo lleva Pablo» (Lucas's dentist on Thursday at 17:30, Pablo takes him), «comprar leche y pan» (buy milk and bread), «recuérdame pagar el comedor mañana a las 10» (remind me to pay for school lunches tomorrow at 10)) and it becomes a plan, task, reminder or shopping item, without AI.
- **Tasks and routines**: date, time, person, reminder, importance, repetition and rotating turns; sections for pending, routines, done and **load sharing** with suggestions to balance it.
- **Live shopping**: lists per store sorted by section, quantities, «the usual» in one tap and a notice of who is ticking items off right now.
- **Weekly meals** with the school canteen and the family's allergies; missing ingredients go to the shopping list and the previous week can be repeated.
- **Kids**: a profile for each child (school, timetables and after-school activities, allergies, health, paediatrician, sizes, contacts, birthdays) and their upcoming plans.
- **Family**: up to 8 people; adults with their own account (invitation by email or a link for WhatsApp), kids as profiles, admin permissions and handing the family over to someone else.
- **Notices**: push notifications in the browser (with a «Done» button on tasks) and exact alarms in the Android app.
- **Android app** (`android/`): the web app full screen with exact alarms even when the phone is idle, notifications with «Done» and «Snooze 10 min», and «Share with Mam-IA» from other apps. The APK is built by GitHub Actions.
- **Works offline** (installable PWA with PNG and maskable icons) and syncs when the network returns.
- **Per-family subscription**: €2.50/month or €25/year with a 7-day trial (Stripe: card, Google Pay or Apple Pay), plan changes, cancellation and read-only mode when it ends.
- **Launch offer**: 1 free year for the first 50 families with the code `LANZAMIENTO`, with the remaining spots shown on the home page.
- **New home page** with the features, the plans, the offer and the FAQ, plus privacy and terms pages and how to delete your account.
- **Accounts**: sign up, sign in, forgotten password by email, change name, email and password, and delete the account or the whole family.
- **Administration** of the server (`/admin`): families and their access, granting free access, promo codes, Stripe and backups.
- Look: light, dark or automatic mode and 4 colours (pink, lavender, mint and coral). New logo.
- Backup: download and import the family's data, and an automatic server backup every night (30 are kept).
- **Email required and confirmed at sign-up**: each new account confirms its address with a 6-digit code (valid for 30 minutes, 5 attempts, another can be requested). Also when joining a family with a link that was not sent to that email, and when changing the account email (with a notice to the previous address).
- **Google Play**, as in BodyLens: from the Android app the family's subscription is paid through Google Play (after confirming the email), renewed, restored and managed there; the server verifies each purchase with Google. It is configured in Administration → Google Play (package, product, service account and store listing link). Guide in `docs/PLAY_STORE.md`.
- **Android app always signed with the same key** (`tools/android-keystore.sh`), with the brand icon (heart and spark on the gradient), and each build also publishes the AAB for Google Play. The landing page shows the app icon and the download button only when the server has the APK (`/api/android`; `tools/deploy-android.sh` copies it to the NAS), and the Google Play button once it is published.
- **Mam-IA in 10 languages**, the same as BodyLens: Spanish, English, Catalan, French, Italian, German, Portuguese, Dutch, Chinese and Japanese. The app, pages, emails and notices come out in each person's language (chosen in Settings or with the footer selector; otherwise, the browser's). Everything lives in `lang/`, with English as the base language so anyone can translate (`lang/README.md`).
- **Automatic emails**, as in BodyLens: reminders of plans and tasks to whoever they concern (with «Mark as done» on tasks), a daily summary every morning (optional), welcome, someone joins the family, you are removed from it or it is handed over to you, password change, account or family deleted, a notice to the administration of each new family, and subscription notices (free access ends in 7 days and tomorrow, the family goes read-only, a payment failed). Every automatic email carries a link to stop receiving it, and in Settings → Email notices you choose them.

#### 🚀 Enhancements:
- `tools/CreateUpdateRelease.py` also sets the version in `pyproject.toml` and in Android's `versionName`, and the service worker cache is now in `src/frontend/app/sw.js`.
- GitHub Actions runs the tests and publishes the `jaimetur/mam-ia` image with every push (`:main`, and `:X.Y.Z` + `:latest` on version branches).
- Fonts and icons are served from the server itself (no Google Fonts or CDN): more privacy and they work offline.
- `runMamIA.py` starts the full server locally with development data; emails are written to the console (`SMTP_HOST=log`).
- **Redesigned desktop interface**: it uses the full width (it used to sit in a narrow strip), larger text and cards, the Calendar week as a 7-column board and the month with the plans inside, Tasks and Shopping in columns, Meals as a week, a side menu with colours, a Today header with a gradient and a day summary, emojis on plans and tasks, and confetti when a task is finished.
- The logo and brand icons are in `assets/branding/` (as in BodyLens) and served at the site root (`/logo.svg`, `/icon-192.png`…); `tools/make_icons.py` generates them there.
- Administration → Email: the SMTP server is configured from the web (it takes precedence over `.env`; the password is stored encrypted) and checked with a test email.
- The sign-in screen has a «Home page» button (on mobile, «Web») to go back to the website, as in BodyLens; it does not appear inside the Android app, which has no landing page.

#### 🐛 Bug fixes:
- The calendar week showed each event one day late in Spain, and «today» changed at midnight UTC: all dates are now local.
- Reminders did not notify on mobile (only with the tab open, and Android does not allow `new Notification()`).
- Removing a person deleted all their tasks: they now stay, under their name.
- Titles and names could inject HTML into the page: everything the family types is escaped and the server validates every field.
- Invitations were marked as «Sent» without sending anything: now an email or a link to share is produced.
- Calendar clashes were only looked for between consecutive plans.
- The old PWA cached the page forever: a retirement service worker cleans it up and loads the new app.
- On iPhone, tapping a field zoomed the page and it could be dragged beyond the screen edges: it no longer zooms or bounces.

#### 📚 Documentation:
- New README, deployment guide for the NAS (`docs/DEPLOYMENT.md`) and for the Android app (`docs/ANDROID.md`).

#### 📱 Google Play (es-ES):
Mam-IA se renueva por completo: ahora es una app con una cuenta para toda la familia.
• Hoy: lo siguiente que toca, la cena y la compra de un vistazo
• Agenda familiar con un color por persona
• Apunta en 5 segundos escribiendo o dictando
• Tareas, rutinas y reparto de la carga
• Compras en directo y menú semanal
• Ficha de cada peque
• Avisos y alarmas exactas
• 10 idiomas

#### 📱 Google Play (en-US):
Mam-IA has been rebuilt: it is now an app with one account for the whole family.
• Today: what's next, dinner and shopping at a glance
• Family calendar with a colour per person
• Add things in 5 seconds by typing or speaking
• Tasks, routines and a fair share of the load
• Live shopping lists and a weekly menu
• A profile for each child
• Reminders and exact alarms
• 10 languages

#### 📱 Google Play (ca):
Mam-IA es renova del tot: ara és una app amb un compte per a tota la família.
• Avui: el que toca, el sopar i la compra d'un cop d'ull
• Agenda familiar amb un color per persona
• Apunta-ho en 5 segons escrivint o dictant
• Tasques, rutines i repartiment de la càrrega
• Compres en directe i menú setmanal
• Fitxa de cada petit
• Avisos i alarmes exactes
• 10 idiomes

#### 📱 Google Play (de-DE):
Mam-IA ist komplett neu: jetzt eine App mit einem Konto für die ganze Familie.
• Heute: was als Nächstes ansteht, Abendessen und Einkauf auf einen Blick
• Familienkalender mit einer Farbe pro Person
• In 5 Sekunden eintragen, getippt oder diktiert
• Aufgaben, Routinen und eine faire Verteilung
• Einkaufslisten in Echtzeit und Wochenmenü
• Ein Profil für jedes Kind
• Erinnerungen und genaue Alarme
• 10 Sprachen

#### 📱 Google Play (fr-FR):
Mam-IA fait peau neuve : c'est maintenant une app avec un compte pour toute la famille.
• Aujourd'hui : la suite, le dîner et les courses en un coup d'œil
• Agenda familial avec une couleur par personne
• Notez en 5 secondes, à l'écrit ou à la voix
• Tâches, routines et répartition de la charge
• Courses en direct et menu de la semaine
• Une fiche pour chaque enfant
• Rappels et alarmes précises
• 10 langues

#### 📱 Google Play (it-IT):
Mam-IA si rinnova del tutto: ora è un'app con un account per tutta la famiglia.
• Oggi: cosa viene dopo, la cena e la spesa a colpo d'occhio
• Agenda di famiglia con un colore per persona
• Annota in 5 secondi scrivendo o dettando
• Compiti, routine e divisione del carico
• Spesa in tempo reale e menù settimanale
• Una scheda per ogni bambino
• Promemoria e sveglie precise
• 10 lingue

#### 📱 Google Play (ja-JP):
Mam-IA を全面的に刷新しました。家族みんなで1つのアカウントを使うアプリになりました。
• 今日：次の予定、夕食、買い物がひと目でわかる
• 一人ずつ色分けした家族カレンダー
• 入力や音声で5秒で登録
• タスク、ルーティン、家事の分担
• リアルタイムの買い物リストと週間献立
• 子どもごとのプロフィール
• リマインダーと正確なアラーム
• 10言語に対応

#### 📱 Google Play (nl-NL):
Mam-IA is helemaal vernieuwd: nu een app met één account voor het hele gezin.
• Vandaag: wat er nu komt, het avondeten en de boodschappen in één oogopslag
• Gezinsagenda met een kleur per persoon
• In 5 seconden noteren, typen of inspreken
• Taken, routines en een eerlijke verdeling
• Live boodschappenlijsten en weekmenu
• Een profiel voor elk kind
• Herinneringen en exacte alarmen
• 10 talen

#### 📱 Google Play (pt-PT):
A Mam-IA foi totalmente renovada: agora é uma app com uma conta para toda a família.
• Hoje: o que vem a seguir, o jantar e as compras num relance
• Agenda familiar com uma cor por pessoa
• Aponte em 5 segundos, a escrever ou a ditar
• Tarefas, rotinas e divisão da carga
• Compras em tempo real e ementa semanal
• Ficha de cada criança
• Avisos e alarmes exatos
• 10 idiomas

#### 📱 Google Play (zh-CN):
Mam-IA 全面焕新：现在是全家共用一个账户的应用。
• 今天：接下来的安排、晚餐和购物一目了然
• 家庭日程，每人一种颜色
• 打字或语音，5 秒记下
• 任务、日常安排和家务分工
• 实时购物清单和每周菜单
• 每个孩子的资料卡
• 提醒和准时闹钟
• 支持 10 种语言

---

## Release: v0.1.0
### Release Date: 2026-03-26
First working version of `Mam-IA`, aimed at an interface and deployment MVP.

#### 🌟 New Features:
- New `Mam-IA` web/PWA application in `src/`.
- Modern, responsive interface for desktop and mobile.
- Colour theme selector (persisted in localStorage).
- Functional modules:
  - weekly meals
  - shopping
  - shared family tasks
  - work
  - cleaning
  - trips
  - leisure
  - school calendar
  - medical appointments
  - beauty
  - couple plans
  - family budget
  - family settings
- Family invitations panel with local persistence.
- Family administration centre (family name, admin, shared calendar, notifications).
- Own SVG logo in `src/assets/mam-ia-logo.svg`.
- PWA support:
  - `manifest.webmanifest`
  - `service-worker.js`
- `runMamIA.py` launcher to start the web interface from PyCharm with the interpreter configured in the project and open it automatically in the browser.
- `tools/CreateUpdateRelease.py` tool and its PyCharm run configuration (**CreateUpdateRelease**) to update the current release or to create, commit and push a new release branch to `origin`.

#### 🐳 Docker:
- `docker/Dockerfile` to build the app image.
- `docker/docker-compose.yml` for production (published image).
- `docker/docker-compose.dev.yml` for development (local build).
- Configurable `docker/.env`:
  - container name
  - prod/dev ports
  - config and data paths
  - dedicated Docker network (subnet and gateway) to avoid overlaps.

#### ⚙️ CI/CD:
- Manual GitHub Actions workflow:
  - `.github/workflows/build_docker.yml`
  - builds and publishes the image to Docker Hub (`jaimetur/mam-ia`)
  - on-demand execution (`workflow_dispatch`).

#### 🚀 Enhancements:
- The local PyCharm configuration (`.idea/`) is excluded from version control.
- The service worker cache carries the release version (`mam-ia-vX.Y.Z`): each new release replaces the files that browsers and the installed PWA keep in cache.

#### 📚 Documentation:
- Main documentation migrated from the previous project to `Mam-IA`.
- Local run documentation updated with the use of the PyCharm launcher and its optional arguments.
- README: creating the local virtual environment (`.venv`) and using the release tool.
- CHANGELOG with the `## Release:` / `### Release Date:` header used by the release tool.

---

## Versioning notes

- The current versioning starts from `0.1.0` as an MVP.
- Keeping a semantic scheme (`MAJOR.MINOR.PATCH`) from here on is recommended.
