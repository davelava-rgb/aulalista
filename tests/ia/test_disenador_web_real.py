"""El agente diseñador escribe una página real que pasa los controles de la decisión 57 f y el recorrido en el
navegador (PLAN.md §4, fases 8c y 8d).

Gasta tokens de Opus: es también la medición del costo del diseño. Se corre con:
    pytest -m ia tests/ia/test_disenador_web_real.py -s
La página queda en la carpeta temporal de la prueba; su ruta sale en la consola.
"""

import asyncio

import pytest

from app import agente, tokens
from app.materiales import actividad, comun, lectura, navegador
from app.materiales.contenido import Actividad
from tests.ia.test_revision_sembrados import curso  # noqa: F401  (curso con una guía y las dos fichas)
from tests.sembrados.actividad import LIMPIA
from tests.unidad.test_lectura import LIMPIA as LECTURA


@pytest.mark.ia
def test_el_disenador_entrega_una_pagina_que_pasa_los_controles(curso):  # noqa: F811
    contenido_lectura = lectura.archivos(curso, 1)["contenido"]
    contenido_lectura.parent.mkdir(parents=True, exist_ok=True)
    comun.guardar_json(contenido_lectura, LECTURA)
    rutas = actividad.archivos(curso, 1)
    trabajo = actividad._Trabajo(curso, "scrum", 1, rutas, agente.query)
    trabajo.contenido = Actividad.model_validate(LIMPIA)
    trabajo.navegador = navegador.disponible()   # fase 8d: también el recorrido en el navegador
    inicio = tokens.lineas("scrum")

    asyncio.run(trabajo.disenar())

    costo = tokens.total("scrum", sesion="S1", material=actividad.CLAVE, desde_linea=inicio)
    print(f"\nDiseño: {trabajo.diseno.get('estado')}, {trabajo.diseno.get('arreglos')} arreglos. "
          f"Costo: {costo['llamadas']} llamadas, {costo['costo_usd']:.2f} USD.")
    print(f"Página: {rutas['pagina']}")
    for p in trabajo.diseno.get("problemas", []):
        print(f"  {p}")
    for l in trabajo.diseno.get("navegador", []):
        print(f"  {l}")
    assert trabajo.diseno["estado"] == "diseñada"
    assert rutas["pagina"].exists()
