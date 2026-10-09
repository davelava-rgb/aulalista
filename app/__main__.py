"""Inicia AulaLista y abre la página en el navegador: python -m app"""

import threading
import webbrowser

import uvicorn

DIRECCION = "127.0.0.1"
PUERTO = 8765


def main() -> None:
    url = f"http://{DIRECCION}:{PUERTO}/"
    threading.Timer(1.5, webbrowser.open, args=[url]).start()
    print(f"AulaLista está en {url}. Para cerrarla, pulsa Ctrl+C.")
    uvicorn.run("app.servidor:app", host=DIRECCION, port=PUERTO)


if __name__ == "__main__":
    main()
