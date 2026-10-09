"""Control de Word, PowerPoint y Excel instalados (CLAUDE.md: solo desde este archivo).

Cada función abre una instancia nueva y propia de la aplicación, sin tocar
las ventanas que el profesor tenga abiertas, y la cierra al terminar. La excepción es PowerPoint, que se explica abajo.
"""

import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

import pythoncom
import win32com.client

FORMATO_PDF_WORD = 17  # wdExportFormatPDF


class ErrorDeOffice(RuntimeError):
    """Office no pudo abrir o convertir un archivo."""


EJECUTABLES = {
    "Word.Application": "WINWORD.EXE",
    "Excel.Application": "EXCEL.EXE",
    "PowerPoint.Application": "POWERPNT.EXE",
}
ESPERA_CIERRE_S = 10


def procesos(ejecutable: str) -> set[int]:
    """Números de proceso (PID) de un programa en ejecución."""
    salida = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {ejecutable}", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW,
    ).stdout
    return {
        int(linea.split('","')[1])
        for linea in salida.splitlines()
        if linea.lower().startswith(f'"{ejecutable.lower()}"')
    }


def proceso_activo(ejecutable: str) -> bool:
    return bool(procesos(ejecutable))


def _esperar_cierre(pids: set[int], ejecutable: str) -> None:
    """Espera a que los procesos propios terminen. Si no terminan, los cierra a la fuerza."""
    limite = time.monotonic() + ESPERA_CIERRE_S
    while pids & procesos(ejecutable) and time.monotonic() < limite:
        time.sleep(0.25)
    for pid in pids & procesos(ejecutable):
        subprocess.run(
            ["taskkill", "/PID", str(pid), "/F"],
            capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW,
        )


@contextmanager
def _aplicacion(nombre: str, *, ocultar: bool = True, cerrar: bool = True):
    ejecutable = EJECUTABLES[nombre]
    antes = procesos(ejecutable)
    pythoncom.CoInitialize()
    app = None
    propios: set[int] = set()
    try:
        try:
            app = win32com.client.DispatchEx(nombre)
        except Exception as error:
            raise ErrorDeOffice(f"No se pudo abrir {nombre}: {error}") from error
        propios = procesos(ejecutable) - antes
        if ocultar:
            app.Visible = False
        try:
            app.DisplayAlerts = 0
        except Exception:
            pass
        yield app
    finally:
        if app is not None and cerrar:
            try:
                app.Quit()
            except Exception:
                pass  # Office suele cortar la conexión al cerrarse: no es un error.
        app = None
        pythoncom.CoUninitialize()
        if cerrar and propios:
            _esperar_cierre(propios, ejecutable)


@contextmanager
def abrir_word():
    with _aplicacion("Word.Application") as app:
        yield app


@contextmanager
def abrir_excel():
    with _aplicacion("Excel.Application") as app:
        yield app


@contextmanager
def abrir_powerpoint():
    # PowerPoint no permite ocultar la aplicación. Cada presentación se abre sin ventana.
    # Solo admite una instancia: si el profesor ya lo tiene abierto, se usa la suya
    # y no se cierra, para no cerrarle su trabajo.
    ya_abierto = proceso_activo("POWERPNT.EXE")
    with _aplicacion("PowerPoint.Application", ocultar=False, cerrar=not ya_abierto) as app:
        yield app


def word_a_pdf(origen: Path, destino: Path) -> Path:
    """Convierte un Word a PDF con el Word instalado, para conservar las páginas reales."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with abrir_word() as word:
        documento = word.Documents.Open(
            str(origen.resolve()), ConfirmConversions=False, ReadOnly=True, AddToRecentFiles=False
        )
        try:
            documento.ExportAsFixedFormat(str(destino.resolve()), FORMATO_PDF_WORD)
        except Exception as error:
            raise ErrorDeOffice(f"Word no pudo convertir {origen.name} a PDF: {error}") from error
        finally:
            documento.Close(False)
    return destino
