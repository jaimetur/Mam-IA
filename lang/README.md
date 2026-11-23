# Mam-IA translations

Mam-IA is translated from **English**, the base language. You do not need to know Spanish or read any code to help.

| File | What it is |
|---|---|
| `catalog.json` | Every message of Mam-IA in English. |
| `<code>.json` | One file per language: `{"English message": "translation"}`. Now: `ca`, `de`, `fr`, `it`, `ja`, `nl`, `pt`, `zh`. |
| `es.json` | Spanish. Special: the code itself is written in Spanish, so its values are the texts **exactly as in the code** (a list when several share one message). Edit it only when the code changes. |
| `i18n.js` | The translator of the browser (it also fills the language picker, `<select data-lang-picker>`). |

The server (emails and notifications) reads the same files with `src/backend/app/core/i18n.py`.

## Add a language

1. Copy any language file (for example `fr.json`) to `<code>.json`, with the two-letter ISO 639-1 code (`pl`, `sv`…).
2. Replace every value with your translation. Keep the keys (the English messages) unchanged.
3. Add the language to `LANGS` in `src/backend/app/core/i18n.py` (with its own name, e.g. `"pl": "Polski"`) and to
   `LOCALES` in `lang/i18n.js` (its locale for numbers and dates, e.g. `pl: 'pl-PL'`).
4. Run `python3 tools/i18n_check.py <code>` until it prints `OK`.

## Improve a translation

Edit the value in `<code>.json` and run `python3 tools/i18n_check.py <code>`.

## Rules

- `{0}`, `{1}`… are placeholders for names, numbers or dates. Keep every one; you may change their order.
- Some messages are pieces of a sentence (cut around a link or a bold word). Translate them so they read well in
  place, and keep leading or trailing punctuation.
- Keep emoji, prices, product names (Mam-IA, Stripe, WhatsApp, Android…) and codes (LANZAMIENTO, SMTP_HOST…).
- Address the person informally if your language distinguishes (German *du*, French *tu*…).
- A missing translation is shown in English, so a partial file still works.

## Which language is shown

The account's (Settings → Language, also used for its emails and notifications); without a session, the one chosen
in the picker at the foot of the pages (cookie `mamia_lang`); else the browser's; else Spanish.

## For developers: after changing texts in the code

```bash
python3 tools/i18n_extract.py
```

It lists in `lang/new.json` the Spanish texts of the code that have no English message yet. Add each one to
`es.json` as `{"English message": "texto en español"}`, run it again (it rewrites `catalog.json`) and add the
translations; `python3 tools/i18n_check.py` lists what each language is missing. Write whole sentences in the code:
a sentence glued from pieces (`"quedan " + n + " plazas"`) cannot be translated well — use `` `quedan ${n} plazas` ``.
The + button (quick capture) reads Spanish sentences: its parser is not translated.
