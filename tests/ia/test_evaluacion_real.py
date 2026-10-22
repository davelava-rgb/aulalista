"""La evaluación práctica real de la sesión de prueba, de punta a punta (PLAN.md §4, fase 9c; decisión 64).

Gasta tokens: el redactor (Opus), la revisión, la corrección si hace falta y la resolución de cada pregunta como un
alumno. Es también la medición del costo de la evaluación. Se corre con:
    pytest -m ia tests/ia/test_evaluacion_real.py -s
Los archivos quedan en la carpeta temporal de la prueba; su ruta sale en la consola.
"""

import asyncio
from datetime import datetime

import pytest

from app import tokens
from app.fichas import verificacion
from app.materiales import comun, evaluacion, laboratorio, lectura
from tests.ia.test_revision_sembrados import curso  # noqa: F401  (curso con una guía y las dos fichas)
from tests.sembrados import laboratorio as laboratorio_sembrado
from tests.unidad.test_lectura import LIMPIA as LECTURA


def _aprobado(carpeta, modulo, contenido):
    ruta = modulo.archivos(carpeta, 1)["contenido"]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    comun.guardar_json(ruta, contenido)
    ahora = datetime.now().isoformat(timespec="seconds")
    comun.actualizar(carpeta, 1, modulo.CLAVE, estado="aprobada", fecha=ahora, aprobada=ahora, desactualizado=False)


@pytest.mark.ia
def test_la_evaluacion_real_sale_sin_fallas_y_mide_su_costo(curso):  # noqa: F811
    verificacion.escribir(curso, 1)
    _aprobado(curso, lectura, LECTURA)
    _aprobado(curso, laboratorio, laboratorio_sembrado.limpio())
    inicio = tokens.lineas("scrum")

    material = asyncio.run(evaluacion.generar(curso, "scrum", 1))

    costo = tokens.total("scrum", sesion="S1", material=evaluacion.CLAVE, desde_linea=inicio)
    rutas = evaluacion.archivos(curso, 1)
    print(f"\nEstado: {material['estado']}. {material.get('resumen', '')}")
    print(f"Costo: {costo['llamadas']} llamadas, {costo['costo_usd']:.2f} USD.")
    print(f"Archivos: {rutas['word'].parent}")
    for p in material.get("problemas", []):
        print(f"  Pendiente: {p}")
    assert material["estado"] in ("verificada", "con pendientes"), material.get("problemas")
    for clave in ("word", "clave", "zip", "excel", "registro"):
        assert rutas[clave].exists(), clave
