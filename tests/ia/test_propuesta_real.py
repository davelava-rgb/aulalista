"""Claude propone la ficha del curso desde un sílabo de verdad. Gasta tokens. Se corre con: pytest -m ia"""

import asyncio

import pymupdf
import pytest

from app.fichas import almacen, flujo
from app.fuentes import convertir

SILABO = [
    "Sílabo del curso",
    "Nombre del curso: Gestión de Inventarios",
    "Sesión 1. Conteo cíclico: cómo planificar y registrar conteos.",
    "Sesión 2. Clasificación ABC: cómo priorizar productos.",
    "Dirigido a: asistentes de almacén con experiencia en Excel.",
    "Docente: Coordinación académica.",
]


@pytest.mark.ia
def test_claude_propone_la_ficha_con_su_origen_y_no_inventa(tmp_path):
    curso = tmp_path / "curso"
    (curso / "fuentes").mkdir(parents=True)
    documento = pymupdf.open()
    pagina = documento.new_page()
    for numero, linea in enumerate(SILABO):
        pagina.insert_text((72, 72 + 24 * numero), linea, fontsize=11)
    documento.save(curso / "fuentes" / "silabo.pdf")
    asyncio.run(convertir.convertir_curso(curso, None))

    resumen = asyncio.run(flujo.proponer(curso, "_sistema", "curso"))
    ficha = almacen.cargar(curso, "curso")
    nombre = ficha["campos"]["curso.nombre"]
    assert nombre["valor"] == "Gestión de Inventarios"
    assert nombre["origen"] == "silabo.pdf" and nombre["estado"] == ""
    assert [s["numero"] for s in almacen.sesiones_del_curso(ficha)] == [1, 2]
    # El sílabo no dice nada de la empresa ficticia: queda por definir o como propuesta, nunca como dato de la fuente.
    empresa = ficha["campos"]["caso.empresa"]
    assert empresa["estado"] in ("falta definir", "propuesto")
    assert resumen["de_las_fuentes"] >= 2
