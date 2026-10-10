"""El revisor independiente busca errores puestos a propósito en un material (PLAN.md §5.8).

Desde la decisión 12 el revisor hace también la segunda pasada: relleno, vacío, ambigüedad e inconsistencia
son ahora suyos. Se mide y se reporta cuántos detecta.
La prueba exige que el programa compruebe cada prueba citada y que el revisor no marque las oraciones correctas.
Gasta tokens. Se corre con: pytest -m ia tests/ia/test_revisor_sembrados.py -s
"""

import asyncio

import pymupdf
import pytest

from app import config
from app.fichas import almacen
from app.fuentes import convertir
from app.validacion import revisor
from tests.fixtures import fichas as datos

GUIA = [
    "Scrum es un marco de trabajo liviano que ayuda a personas, equipos y organizaciones a generar valor.",
    "Tres Pilares de Scrum: Transparencia, Inspección y Adaptación.",
    "Los artefactos de Scrum y el progreso hacia los objetivos acordados deben inspeccionarse con frecuencia.",
    "El Scrum Team es lo suficientemente pequeño como para seguir siendo ágil.",
]
CORRECTAS = [
    "Scrum es un marco de trabajo liviano.",
    "Scrum ayuda a personas, equipos y organizaciones a generar valor.",
    "Los artefactos de Scrum deben inspeccionarse con frecuencia.",
    "En Comercial Los Volcanes, cada Sprint dura dos semanas.",
    "El Scrum Team es lo suficientemente pequeño como para seguir siendo ágil.",
]
SEMBRADAS = {
    "Scrum tiene cuatro pilares: transparencia, inspección, adaptación y compromiso.": "imprecisión",
    "Los artefactos de Scrum pueden inspeccionarse cuando el equipo lo decida.": "imprecisión",
    "Todos los equipos de una organización deben usar Scrum.": "imprecisión",
    "En la tienda principal, el Sprint del equipo de Ventas dura tres semanas.": "inconsistencia",
    "Este tema es muy importante y conviene tenerlo siempre presente.": "relleno",
    "Marca en el tablero el pedido anterior al último que revisaste.": "ambigüedad",
    "Abre el archivo y copia la tabla en un documento nuevo.": "vacío",
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
def test_el_revisor_encuentra_errores_sembrados_con_pruebas_reales(curso, tmp_path):
    textos = []
    for correcta, sembrada in zip(CORRECTAS + [""], list(SEMBRADAS) + [""]):
        textos += [t for t in (correcta, sembrada) if t]
    oraciones = [{"n": n, "huella": f"h{n}", "texto": t} for n, t in enumerate(textos, start=1)]
    resultado = asyncio.run(revisor.ejecutar(
        oraciones, ronda=1, carpeta=tmp_path / "revisor", carpeta_curso=curso, curso="scrum", sesion=1,
        material="prueba sembrados"))

    marcadas = {h.oracion for h in resultado.hallazgos}
    detectadas = [t for t in SEMBRADAS if t in marcadas]
    falsas = [h for h in resultado.hallazgos if h.oracion in CORRECTAS]
    print(f"\nRevisor: detectó {len(detectadas)} de {len(SEMBRADAS)} errores sembrados.")
    for t in SEMBRADAS:
        print(("  sí  " if t in detectadas else "  no  ") + t)
    print(f"Hallazgos descartados por no tener una prueba real: {len(resultado.descartados)}.")
    for d in resultado.descartados:
        print(f"  - {d['oracion']} · {d['motivo']}")
    assert falsas == [], f"Oraciones correctas marcadas como error: {[(h.oracion, h.explicacion) for h in falsas]}"
    assert len(detectadas) >= len(SEMBRADAS) // 2
    assert all(h.fuente for h in resultado.hallazgos)   # cada hallazgo válido tiene una prueba ubicada
