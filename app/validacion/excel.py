"""Completa el Excel de verificación que escribe el verificador (PLAN.md §5.6).

- Hoja Oraciones: Tipo de oración, Pasaje de la fuente, Fuente y Veredicto, de la primera pasada.
- Hoja Hallazgos: además de los hallazgos actuales del verificador, cada problema que se envió
  a corrección en una vuelta anterior, con cómo se resolvió.
"""

from pathlib import Path

import openpyxl
from openpyxl.styles import Alignment, Font


def _estilo(fila) -> None:
    for celda in fila:
        celda.font = Font(name="Arial", size=10)
        celda.alignment = Alignment(wrap_text=True, vertical="top")


def llenar_oraciones(ruta: Path, oraciones: list[dict], filas_por_huella: dict[str, dict]) -> int:
    """oraciones: filas del verificador con n y huella. Devuelve cuántas filas quedaron llenas."""
    libro = openpyxl.load_workbook(ruta)
    hoja = libro["Oraciones"]
    por_numero = {o["n"]: filas_por_huella.get(o["huella"]) for o in oraciones}
    llenas = 0
    for fila in hoja.iter_rows(min_row=2):
        datos = por_numero.get(fila[0].value)
        if not datos:
            continue
        fila[4].value = datos["tipo"]
        fila[5].value = datos["pasaje"]
        fila[6].value = datos["fuente"] or fila[6].value
        fila[7].value = datos["veredicto"]
        llenas += 1
    libro.save(ruta)
    return llenas


def anotar_reglas(ruta: Path, reglas: tuple[str, ...], nota: str) -> None:
    """«Cómo se resolvió» en la hoja Hallazgos para los avisos de estas reglas que no tienen nota todavía."""
    libro = openpyxl.load_workbook(ruta)
    for fila in libro["Hallazgos"].iter_rows(min_row=2):
        if fila[0].value == "AVISO" and fila[3].value in reglas and not fila[5].value:
            fila[5].value = nota
    libro.save(ruta)


def llenar_revisor(ruta: Path, por_numero: dict[int, str]) -> None:
    """Columna «Revisor independiente» de la hoja Oraciones, una nota por fila (PLAN.md §5.6)."""
    libro = openpyxl.load_workbook(ruta)
    for fila in libro["Oraciones"].iter_rows(min_row=2):
        if fila[0].value in por_numero:
            fila[8].value = por_numero[fila[0].value]
    libro.save(ruta)


def agregar_historial(ruta: Path, historial: list[dict]) -> None:
    """historial: [{nivel, seccion, oracion, regla, detalle, resolucion}]"""
    if not historial:
        return
    libro = openpyxl.load_workbook(ruta)
    hoja = libro["Hallazgos"]
    for h in historial:
        hoja.append([h["nivel"], h["seccion"], h["oracion"], h["regla"], h["detalle"], h["resolucion"]])
        _estilo(hoja[hoja.max_row])
    libro.save(ruta)


def llenar_segunda_pasada(ruta: Path, filas: list[list[str]]) -> None:
    """Hoja Segunda pasada: un bloque por fila, con las cuatro preguntas de la skill."""
    libro = openpyxl.load_workbook(ruta)
    hoja = libro["Segunda pasada"]
    for fila in filas:
        hoja.append(fila)
        _estilo(hoja[hoja.max_row])
    libro.save(ruta)
