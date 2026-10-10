"""La revisión del contenido busca errores puestos a propósito y no marca las paráfrasis (PLAN.md §0, decisión 22).

Mide cuántos errores sembrados detecta y exige que no marque las oraciones correctas, aunque digan lo
mismo que la fuente con otras palabras. Gasta tokens. Se corre con:
    pytest -m ia tests/ia/test_revision_sembrados.py -s
"""

import asyncio

import pymupdf
import pytest

from app import config
from app.fichas import almacen
from app.fuentes import convertir
from app.validacion import pasada2, revision
from app.validacion.pasajes import Corpus
from tests.fixtures import fichas as datos

GUIA = [
    "Scrum es un marco de trabajo liviano que ayuda a personas, equipos y organizaciones a generar valor.",
    "Tres Pilares de Scrum: Transparencia, Inspección y Adaptación.",
    "Los artefactos de Scrum y el progreso hacia los objetivos acordados deben inspeccionarse con frecuencia.",
    "El Scrum Team es lo suficientemente pequeño como para seguir siendo ágil.",
]
# Dicen lo mismo que la guía con otras palabras: no son errores.
PARAFRASIS = [
    "Scrum es un marco liviano que ayuda a generar valor a personas, equipos y organizaciones.",
    "Scrum se apoya en tres pilares: transparencia, inspección y adaptación.",
    "Los artefactos y el avance hacia los objetivos deben revisarse con frecuencia.",
    "En Comercial Los Volcanes, cada Sprint dura dos semanas.",
]
SEMBRADAS = {
    "Scrum tiene cuatro pilares: transparencia, inspección, adaptación y compromiso.": "contradice la fuente",
    "Los artefactos de Scrum pueden inspeccionarse cuando el equipo lo decida.": "contradice la fuente",
    "En la tienda principal, cada Sprint dura tres semanas.": "inconsistencia",
    "Scrum fue creado en 2005 por la Universidad de Oxford.": "dato inventado",
    "Marca en el tablero el pedido anterior al último que revisaste.": "ambigüedad",
}


@pytest.fixture
def curso(tmp_path, monkeypatch):
    """Curso con una guía y las dos fichas. La clave sigue saliendo del .env real."""
    monkeypatch.setattr(config, "CARPETA_CURSOS", tmp_path / "cursos")
    carpeta = tmp_path / "cursos" / "scrum"
    (carpeta / "fuentes").mkdir(parents=True)
    documento = pymupdf.open()
    pagina = documento.new_page()
    for numero, linea in enumerate(GUIA):
        pagina.insert_textbox(pymupdf.Rect(72, 72 + 60 * numero, 520, 130 + 60 * numero), linea, fontsize=10)
    documento.save(carpeta / "fuentes" / "guia.pdf")
    asyncio.run(convertir.convertir_curso(carpeta, None))
    almacen.guardar(carpeta, "curso", None, datos.ficha("curso", datos.CURSO, confirmada=True))
    almacen.guardar(carpeta, "sesion", 1, datos.ficha("sesion", datos.SESION, confirmada=True))
    return carpeta


@pytest.mark.ia
def test_la_revision_encuentra_errores_sembrados_y_respeta_las_parafrasis(curso):
    sembradas = list(SEMBRADAS)
    bloques = [pasada2.Bloque("Qué es Scrum", [PARAFRASIS[0], sembradas[3], PARAFRASIS[1], sembradas[0]]),
               pasada2.Bloque("Inspección", [PARAFRASIS[2], sembradas[1], sembradas[4]]),
               pasada2.Bloque("El caso", [PARAFRASIS[3], sembradas[2]])]
    resultado = asyncio.run(revision.ejecutar(
        bloques, corpus=Corpus.del_curso(curso, 1), curso="scrum", sesion=1, material="prueba sembrados",
        nombre_material="Lectura", etapa="prueba sembrados"))

    marcadas = {e.oracion for e in resultado.errores}
    detectadas = [t for t in SEMBRADAS if t in marcadas]
    falsas = [e for e in resultado.errores if e.oracion in PARAFRASIS]
    print(f"\nRevisión: detectó {len(detectadas)} de {len(SEMBRADAS)} errores sembrados.")
    for t in SEMBRADAS:
        print(("  sí  " if t in detectadas else "  no  ") + t)
    print(f"Errores descartados por no tener una prueba real: {len(resultado.descartados)}.")
    assert falsas == [], f"Paráfrasis marcadas como error: {[(e.oracion, e.explicacion) for e in falsas]}"
    assert len(detectadas) >= len(SEMBRADAS) // 2 + 1
