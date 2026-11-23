"""Start Mam-IA on this computer (server + web app) from PyCharm, with development settings, and open it.

The data goes to ./data-dev (not in Git). With an empty database it creates the administrator account
admin@mamia.local with the password «mamia-admin» (asked to be changed on entering). New families can sign up without
paying (OPEN_SIGNUP), since Stripe is not configured locally. Emails are not sent: they are written to the console
(SMTP_HOST=log), sign-up codes included.
"""

from __future__ import annotations

import argparse
import os
import sys
import threading
import webbrowser
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent
DEV_DEFAULTS = {
    "DATA_DIR": str(PROJECT_DIR / "data-dev"),
    "COOKIE_SECURE": "0",
    "OPEN_SIGNUP": "1",
    "MAMIA_ADMIN_EMAIL": "admin@mamia.local",
    "MAMIA_ADMIN_PASSWORD": "mamia-admin",
    "MAMIA_ADMIN_NAME": "Administración",
    "SMTP_HOST": "log",
    "SMTP_FROM": "mamia@mamia.local",
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Abre Mam-IA en un servidor local.")
    parser.add_argument("--port", type=int, default=5173, help="Puerto local (por defecto: 5173).")
    parser.add_argument("--host", default="127.0.0.1", help="Dirección (0.0.0.0 para abrirla desde el móvil en la misma red).")
    parser.add_argument("--no-browser", action="store_true", help="No abre el navegador automáticamente.")
    parser.add_argument("--reload", action="store_true", help="Reinicia el servidor al cambiar el código.")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    for key, value in DEV_DEFAULTS.items():
        os.environ.setdefault(key, value)
    sys.path.insert(0, str(PROJECT_DIR / "src" / "backend"))
    try:
        import uvicorn
    except ImportError:
        raise SystemExit("Faltan las dependencias del servidor: pip install -e \".[test]\" en el entorno del proyecto.")
    url = f"http://{'127.0.0.1' if args.host == '0.0.0.0' else args.host}:{args.port}"
    os.environ.setdefault("PUBLIC_URL", url)   # the links in the emails
    print(f"Mam-IA está disponible en {url}  (datos en {os.environ['DATA_DIR']})")
    print(f"Administración: {os.environ['MAMIA_ADMIN_EMAIL']} · contraseña inicial «{os.environ['MAMIA_ADMIN_PASSWORD']}»")
    print("Pulsa Ctrl+C para detener el servidor.")
    if not args.no_browser:
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run("app.main:app", host=args.host, port=args.port, reload=args.reload,
                reload_dirs=[str(PROJECT_DIR / "src" / "backend")] if args.reload else None, log_level="info")


if __name__ == "__main__":
    main()
