"""Fase 8d: la página del alumno recorrida en un navegador real, sin IA (PLAN.md §5.7).

La referencia es una página que diseñó Opus en la fase 8c (tests/fixtures/actividad_referencia.html). Cada error
sembrado se le agrega con un trozo de HTML, CSS o JavaScript. Playwright tarda unos segundos por página.
"""

import asyncio
import copy
import json
from pathlib import Path

import pytest

from app.materiales import actividad, disenador_web, navegador
from app.materiales.contenido import Actividad
from tests.conftest import consulta_en_secuencia
from tests.sembrados.actividad import LIMPIA
from tests.unidad.test_actividad import SIN_ERRORES, lectura_aprobada
from tests.unidad.test_lectura import sesion  # noqa: F401

pytestmark = pytest.mark.skipif(not navegador.disponible(), reason="Playwright o su navegador no están instalados.")

REFERENCIA = (Path(__file__).resolve().parents[1] / "fixtures" / "actividad_referencia.html").read_text(encoding="utf-8")
DATOS = disenador_web.datos_de_la_pagina(Actividad.model_validate(LIMPIA), "scrum", 1, "Scrum Master con IA",
                                         actividad.NOTA_DEL_PUNTAJE)


def probar(tmp_path, html_: str) -> navegador.Informe:
    ruta = tmp_path / "pagina.html"
    ruta.write_text(disenador_web.armar(html_, DATOS), encoding="utf-8")
    return navegador.probar(ruta, DATOS, tmp_path / "capturas")


def con(trozo: str, donde: str = "</head>") -> str:
    """La referencia con un trozo agregado antes de `donde`."""
    assert REFERENCIA.count(donde) == 1
    return REFERENCIA.replace(donde, trozo + donde)


def test_la_referencia_pasa_el_recorrido_completo(tmp_path):
    informe = probar(tmp_path, REFERENCIA)
    assert informe.fallas == []
    assert informe.lineas[0] == "Computadora, modo claro: recorrido con todas las respuestas correctas, puntaje 100 de 100."
    assert informe.lineas[1] == "Celular, modo oscuro: recorrido con todas las respuestas incorrectas, puntaje 0 de 100."
    assert "la recarga recupera el avance" in informe.lineas[-1]


SEMBRADOS = [
    ("boton de 30 px", con("<style>[data-accion=\"comprobar\"]{min-height:30px!important;height:30px!important;"
                          "padding:0 8px!important;line-height:1!important}</style>"),
     "controles de menos de 44 px de alto"),
    ("desborde en celular", con('<div style="width:600px;height:1px"></div>', "</body>"), "se desborda"),
    ("error de JavaScript", con("<script>document.addEventListener('click', function () { null.x; });</script>",
                                "</body>"), "error de JavaScript"),
    ("puntaje mal sumado", con("<script>setInterval(function () { document.querySelectorAll('[data-puntaje]')"
                               ".forEach(function (e) { e.textContent = '7'; }); }, 30);</script>", "</body>"),
     "el puntaje dice 7"),
    ("avance que no se recupera", con("<script>Storage.prototype.setItem = function () {};</script>", "<style>"),
     "al recargar la página no se recupera el avance"),
]


@pytest.mark.parametrize("ident, html_, esperado", SEMBRADOS, ids=[s[0] for s in SEMBRADOS])
def test_cada_error_sembrado_de_la_pagina_lo_encuentra_el_navegador(tmp_path, ident, html_, esperado):
    informe = probar(tmp_path, html_)
    assert any(esperado in f for f in informe.fallas), informe.fallas
    assert informe.capturas and informe.capturas[0].exists()


# ---------- El recorrido dentro del diseño ----------

def disenar(sesion, *disenos):  # noqa: F811
    lectura_aprobada(sesion)
    consulta = consulta_en_secuencia(copy.deepcopy(LIMPIA), SIN_ERRORES, *disenos)
    material = asyncio.run(actividad.generar(sesion, "scrum", 1, consulta=consulta, probar_en_navegador=True))
    return material, consulta


def test_la_entrega_dice_lo_que_reviso_el_navegador(sesion):  # noqa: F811
    material, _ = disenar(sesion, {"html": REFERENCIA, "notas": ""})
    assert material["estado"] == "verificada", material["problemas"]
    texto = json.dumps(material["entrega"], ensure_ascii=False)
    assert "Recorrí la página en un navegador, sin conexión, como un alumno:" in texto
    assert "Celular, modo oscuro: recorrido con todas las respuestas incorrectas, puntaje 0 de 100." in texto
    assert "No recorrí la página" not in texto


def test_una_falla_del_navegador_vuelve_al_disenador_con_su_captura(sesion):  # noqa: F811
    chico = "<style>[data-accion=\"comprobar\"]{height:30px!important;min-height:30px!important;padding:0!important}</style>"
    arreglo = {"cambios": [{"buscar": chico, "reemplazar": ""}], "notas": "Botón de 44 px."}
    material, consulta = disenar(sesion, {"html": con(chico), "notas": ""}, arreglo)
    assert material["estado"] == "verificada" and material["diseno"]["arreglos"] == 1
    assert not isinstance(consulta.llamadas[3]["prompt"], str)   # el arreglo va con imágenes
    assert actividad.archivos(sesion, 1)["pagina"].exists()


def test_por_omision_la_generacion_recorre_la_pagina(sesion):  # noqa: F811
    """La generación corre dentro de asyncio: ahí la API síncrona de Playwright fallaba y la página se entregaba sin
    recorrer, como si Playwright no estuviera instalado."""
    lectura_aprobada(sesion)
    consulta = consulta_en_secuencia(copy.deepcopy(LIMPIA), SIN_ERRORES, {"html": REFERENCIA, "notas": ""})
    material = asyncio.run(actividad.generar(sesion, "scrum", 1, consulta=consulta))
    assert material["diseno"]["navegador"], material["diseno"]
    assert "Recorrí la página en un navegador" in json.dumps(material["entrega"], ensure_ascii=False)
