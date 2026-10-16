"""Inicia AulaLista y abre la página en el navegador: python -m app"""

import socket
import sys
import threading
import webbrowser

import uvicorn

DIRECCION = "127.0.0.1"
PUERTO = 8765

AVISO_PUERTO_OCUPADO = (
    "AulaLista ya está abierta en otra ventana, o otro programa usa el puerto {puerto}.\n"
    "Cierra esa ventana (Ctrl+C) y vuelve a iniciar. Si sigues en la versión anterior, "
    "las páginas nuevas pueden fallar con «Internal Server Error»."
)


def puerto_libre(direccion: str = DIRECCION, puerto: int = PUERTO) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as prueba:
        try:
            prueba.bind((direccion, puerto))
        except OSError:
            return False
    return True


def main() -> None:
    url = f"http://{DIRECCION}:{PUERTO}/"
    # Sin esta prueba, el navegador abría la versión vieja que seguía corriendo.
    if not puerto_libre():
        print(AVISO_PUERTO_OCUPADO.format(puerto=PUERTO))
        sys.exit(1)
    threading.Timer(1.5, webbrowser.open, args=[url]).start()
    print(f"AulaLista está en {url}. Para cerrarla, pulsa Ctrl+C.")
    uvicorn.run("app.servidor:app", host=DIRECCION, port=PUERTO)


if __name__ == "__main__":
    main()
