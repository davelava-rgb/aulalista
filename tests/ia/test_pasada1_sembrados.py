"""La primera pasada marca los errores de significado puestos a propósito (PLAN.md §5.8).
Gasta tokens. Se corre con: pytest -m ia"""

import asyncio

import pytest

from app.validacion import pasada1
from app.validacion.pasajes import Corpus, Fuente

GUIA = Fuente("guia.pdf", [
    {"texto": "Scrum es un marco de trabajo liviano que ayuda a personas, equipos y organizaciones a generar valor.",
     "ubicacion": "página 24 · número impreso 43"},
    {"texto": "Tres Pilares de Scrum • Transparencia • Inspección • Adaptación", "ubicacion": "página 35 · número impreso 54"},
    {"texto": "Los artefactos de Scrum y el progreso hacia los objetivos acordados deben inspeccionarse con frecuencia "
              "y con diligencia para detectar variaciones o problemas potencialmente indeseables.",
     "ubicacion": "página 37 · número impreso 56"},
    {"texto": "El Scrum Team es lo suficientemente pequeño como para seguir siendo ágil.", "ubicacion": "página 54 · número impreso 73"},
])
FICHA = Fuente("ficha del curso", [
    {"texto": "Duración de cada Sprint: dos semanas", "ubicacion": "Cifras, reglas y nombres que deben repetirse igual"},
    {"texto": "Comercial Los Volcanes, venta minorista", "ubicacion": "Empresa o institución ficticia y rubro"},
])

ERRORES = [
    "Scrum tiene cuatro pilares: transparencia, inspección, adaptación y compromiso.",          # cantidad
    "Los artefactos de Scrum pueden inspeccionarse con frecuencia para detectar problemas.",   # «debe» → «puede»
    "Todos los equipos de una organización deben usar Scrum.",                                 # generalización sin fuente
    "Una situación contradice un aspecto del manifiesto solo cuando valora más su segundo elemento.",  # regla sin «en este curso»
    "Scrum fue creado en 1990 por un comité de bancos europeos.",                              # sin fuente
    "En Comercial Los Volcanes, cada Sprint dura tres semanas.",                               # dato del caso distinto
]
CORRECTAS = [
    "Scrum tiene tres pilares: transparencia, inspección y adaptación.",
    "Los artefactos de Scrum deben inspeccionarse con frecuencia y con diligencia.",
    "En este curso, una situación contradice un aspecto solo cuando valora más su segundo elemento.",
    "En Comercial Los Volcanes, cada Sprint dura dos semanas.",
]


@pytest.mark.ia
def test_la_primera_pasada_marca_cada_error_sembrado_y_aprueba_lo_correcto():
    textos = ERRORES + CORRECTAS
    oraciones = [{"n": n, "huella": f"h{n}", "seccion": "S1_Lectura.docx · Pilares", "texto": t}
                 for n, t in enumerate(textos, start=1)]
    resultado = asyncio.run(pasada1.ejecutar(
        oraciones, titulos=set(), corpus=Corpus([GUIA, FICHA]), anteriores={},
        curso="_sistema", sesion=1, material="prueba sembrados"))
    veredictos = {o["texto"]: resultado.filas[o["huella"]] for o in oraciones}
    sin_marcar = [t for t in ERRORES if veredictos[t]["veredicto"] == "coincide"]
    rechazadas = [(t, veredictos[t]["veredicto"], veredictos[t]["motivo"]) for t in CORRECTAS
                  if veredictos[t]["veredicto"] != "coincide"]
    assert sin_marcar == [], f"Errores que la pasada no marcó: {sin_marcar}"
    assert rechazadas == [], f"Oraciones correctas marcadas como error: {rechazadas}"
