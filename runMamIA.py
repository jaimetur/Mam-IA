"""Inicia la interfaz web local de Mam-IA desde PyCharm."""

from __future__ import annotations

import argparse
import functools
import http.server
import socketserver
import webbrowser
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
WEB_DIR = PROJECT_DIR / "src"


class MamIAServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Abre Mam-IA en un servidor local.")
    parser.add_argument("--port", type=int, default=5173, help="Puerto local (por defecto: 5173).")
    parser.add_argument("--no-browser", action="store_true", help="No abre el navegador automáticamente.")
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    if not WEB_DIR.is_dir():
        raise SystemExit(f"No se encuentra la interfaz web en: {WEB_DIR}")

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(WEB_DIR))
    with MamIAServer(("127.0.0.1", args.port), handler) as server:
        host, port = server.server_address
        url = f"http://{host}:{port}"
        print(f"Mam-IA está disponible en {url}")
        print("Pulsa Ctrl+C para detener el servidor.")

        if not args.no_browser:
            webbrowser.open(url)

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")


if __name__ == "__main__":
    main()
