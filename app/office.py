"""Control de Word, PowerPoint y Excel instalados (CLAUDE.md: solo desde este archivo).

Cada función abre una instancia nueva y propia de la aplicación, sin tocar
las ventanas que el profesor tenga abiertas, y la cierra al terminar. La excepción es PowerPoint, que se explica abajo.
"""

import subprocess
import time
from contextlib import contextmanager
from dataclasses import dataclass
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
        # tasklist escribe en la codificación de la consola de Windows, no en UTF-8.
        capture_output=True, text=True, encoding="oem", errors="replace", creationflags=subprocess.CREATE_NO_WINDOW,
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


ESTADISTICA_PAGINAS = 2  # wdStatisticPages


def contar_paginas_word(ruta: Path) -> int:
    """Páginas del Word tal como las cuenta el Word instalado."""
    with abrir_word() as word:
        documento = word.Documents.Open(
            str(ruta.resolve()), ConfirmConversions=False, ReadOnly=True, AddToRecentFiles=False
        )
        try:
            documento.Repaginate()
            return int(documento.ComputeStatistics(ESTADISTICA_PAGINAS))
        except Exception as error:
            raise ErrorDeOffice(f"Word no pudo contar las páginas de {ruta.name}: {error}") from error
        finally:
            documento.Close(False)


def recalcular_excel(ruta: Path) -> Path:
    """Abre un Excel con el Excel instalado, calcula sus fórmulas y lo guarda. Así el archivo trae los valores
    calculados y una figura muestra lo mismo que ve el alumno al abrirlo (SKILL.md, «Imágenes»)."""
    with abrir_excel() as excel:
        libro = excel.Workbooks.Open(str(ruta.resolve()), UpdateLinks=0, ReadOnly=False, AddToMru=False)
        try:
            excel.CalculateFull()
            libro.Save()
        except Exception as error:
            raise ErrorDeOffice(f"Excel no pudo calcular {ruta.name}: {error}") from error
        finally:
            libro.Close(False)
    return ruta


# ---------- Diapositivas: desbordes medidos con PowerPoint ----------

PUNTOS_POR_CM = 72 / 2.54
TOLERANCIA_PT = 2   # medio milímetro: PowerPoint redondea la medida del texto


@dataclass
class Desborde:
    diapositiva: int
    texto: str          # el comienzo del texto que no cabe, o «tabla» si es una tabla
    sobra_cm: float
    es_tabla: bool = False


@dataclass
class Medicion:
    diapositivas: int
    desbordes: list[Desborde]
    imagenes: list[Path]


def medir_diapositivas(ruta: Path, carpeta_imagenes: Path | None = None) -> Medicion:
    """Mide con el PowerPoint instalado si algún texto se sale de su recuadro o de la diapositiva,
    y guarda una imagen de cada diapositiva (SKILL.md: «Revisa en una imagen de cada diapositiva…»)."""
    imagenes = []
    if carpeta_imagenes is not None:
        carpeta_imagenes.mkdir(parents=True, exist_ok=True)
        for vieja in carpeta_imagenes.glob("*.png"):
            vieja.unlink(missing_ok=True)
    with abrir_powerpoint() as powerpoint:
        try:
            # ReadOnly, Untitled, WithWindow: sin ventana, para no tocar lo que el profesor tenga abierto.
            presentacion = powerpoint.Presentations.Open(str(ruta.resolve()), True, False, False)
        except Exception as error:
            raise ErrorDeOffice(f"PowerPoint no pudo abrir {ruta.name}: {error}") from error
        try:
            alto_diapositiva = presentacion.PageSetup.SlideHeight
            ancho_diapositiva = presentacion.PageSetup.SlideWidth
            desbordes = []
            total = presentacion.Slides.Count
            for numero in range(1, total + 1):
                diapositiva = presentacion.Slides(numero)
                for figura in diapositiva.Shapes:
                    sobra = 0.0
                    if figura.HasTable:
                        sobra = max(figura.Top + figura.Height - alto_diapositiva,
                                    figura.Left + figura.Width - ancho_diapositiva)
                        if sobra > TOLERANCIA_PT:
                            desbordes.append(Desborde(numero, "tabla", round(sobra / PUNTOS_POR_CM, 1), es_tabla=True))
                        continue
                    if not figura.HasTextFrame or not figura.TextFrame.HasText:
                        continue
                    marco = figura.TextFrame
                    texto = marco.TextRange
                    disponible = figura.Height - marco.MarginTop - marco.MarginBottom
                    sobra = max(texto.BoundHeight - disponible, figura.Top + figura.Height - alto_diapositiva)
                    if sobra > TOLERANCIA_PT:
                        desbordes.append(Desborde(numero, " ".join(texto.Text.split())[:200],
                                                  round(sobra / PUNTOS_POR_CM, 1)))
                if carpeta_imagenes is not None:
                    imagen = carpeta_imagenes / f"diapositiva_{numero:02d}.png"
                    diapositiva.Export(str(imagen.resolve()), "PNG", 1280, 720)
                    imagenes.append(imagen)
        except ErrorDeOffice:
            raise
        except Exception as error:
            raise ErrorDeOffice(f"PowerPoint no pudo medir {ruta.name}: {error}") from error
        finally:
            presentacion.Close()
    return Medicion(diapositivas=total, desbordes=desbordes, imagenes=imagenes)
