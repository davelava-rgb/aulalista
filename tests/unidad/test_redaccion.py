"""Decisión 74 b: la parte común de la redacción va en el mensaje de sistema, igual para los cinco materiales, con un
solo esquema de redacción y caché de una hora."""

import asyncio
from pathlib import Path

import pytest

from app.materiales import actividad, diapositivas, evaluacion, laboratorio, lectura, redaccion
from app.materiales.contenido import (ESQUEMA_ACTIVIDAD, ESQUEMA_DIAPOSITIVAS, ESQUEMA_EVALUACION, ESQUEMA_LABORATORIO,
                                      ESQUEMA_LECTURA)
from tests.conftest import consulta_en_secuencia
from tests.unidad.test_diapositivas import con_lectura  # noqa: F401
from tests.unidad.test_lectura import sesion  # noqa: F401


def test_el_esquema_de_redaccion_tiene_una_parte_por_material():
    assert redaccion.PARTES == ("lectura", "diapositivas", "laboratorio", "actividad", "evaluacion")
    assert redaccion.PARTES == (lectura.CLAVE, diapositivas.CLAVE, laboratorio.CLAVE, actividad.CLAVE, evaluacion.CLAVE)
    partes = redaccion.ESQUEMA_REDACCION["properties"]
    for clave, esquema in [("lectura", ESQUEMA_LECTURA), ("diapositivas", ESQUEMA_DIAPOSITIVAS),
                           ("laboratorio", ESQUEMA_LABORATORIO), ("actividad", ESQUEMA_ACTIVIDAD),
                           ("evaluacion", ESQUEMA_EVALUACION)]:
        assert partes[clave]["anyOf"] == [esquema, {"type": "null"}]
    assert redaccion.ESQUEMA_REDACCION["required"] == list(redaccion.PARTES)


def test_la_parte_comun_es_la_misma_para_los_cinco_materiales_y_lo_propio_va_en_el_pedido(con_lectura):  # noqa: F811
    paginas, pasajes = redaccion.fuentes_de_la_sesion(con_lectura, 1)
    comun = redaccion.sistema(con_lectura, 1, paginas, pasajes)
    for texto in ("## Reglas comunes", "## Paso 3 · Vocabulario de la sesión", "FICHA DEL CURSO (confirmada):",
                  "FICHA DE LA SESIÓN (confirmada):", "FUENTES DEL CURSO", "LECTURA APROBADA POR EL PROFESOR",
                  "Los pilares de Scrum son tres.", "PASAJES DE LAS FUENTES DEL CURSO, elegidos por AulaLista"):
        assert texto in comun, texto
    # Las secciones propias de cada material no van en la parte común.
    for seccion in ("## Material 1 · Lectura", "## Material 2 · Diapositivas", "## Material 3 · Laboratorio",
                    "## Actividad web", "## Material 6 · Evaluación"):
        assert seccion not in comun, seccion
    contenido_lectura = redaccion.lectura_aprobada(con_lectura, 1)
    pedidos = {
        "## Material 1 · Lectura": lectura.pedido_de_redaccion(con_lectura, 1, paginas, pasajes),
        "## Material 2 · Diapositivas": diapositivas.pedido_de_redaccion(con_lectura, 1, contenido_lectura, paginas, pasajes),
        "## Material 3 · Laboratorio": laboratorio.pedido_de_redaccion(con_lectura, 1, paginas, pasajes),
        "## Actividad web": actividad.pedido_de_redaccion(con_lectura, 1, pasajes),
        "## Material 6 · Evaluación": evaluacion.pedido_de_redaccion(con_lectura, 1, pasajes),
    }
    for seccion, pedido in pedidos.items():
        assert pedido.startswith("REGLAS DE LA SKILL PARA ESTE MATERIAL") and seccion in pedido, seccion
        assert "## Reglas comunes" not in pedido and "FICHA DEL CURSO" not in pedido and "TAREA:" in pedido, seccion
        assert "Los pilares de Scrum son tres." not in pedido, seccion     # la lectura va solo en la parte común


def test_la_lectura_no_recibe_la_lectura_anterior_y_los_demas_si(con_lectura):  # noqa: F811
    sin = redaccion.sistema(con_lectura, 1, con_lectura=False)
    con = redaccion.sistema(con_lectura, 1)
    assert "LECTURA APROBADA" not in sin and "LECTURA APROBADA" in con
    # Lo único que cambia es el bloque de la lectura: lo de antes y lo de después es igual.
    antes = con.split("\nLECTURA APROBADA")[0]
    despues = "\nPASAJES DE LAS FUENTES DEL CURSO" + con.split("\nPASAJES DE LAS FUENTES DEL CURSO", 1)[1]
    assert sin == antes + despues


def test_redactar_manda_el_esquema_unico_el_archivo_comun_y_pide_una_sola_parte(sesion):  # noqa: F811
    consulta = consulta_en_secuencia({"idea_central": ["Una idea."]})
    datos = asyncio.run(redaccion.redactar("lectura", "PEDIDO PROPIO", sesion, 1, con_lectura=False, curso="scrum",
                                           sesion="S1", material="lectura", etapa="redacción", consulta=consulta))
    assert datos == {"idea_central": ["Una idea."]}
    llamada = consulta.llamadas[0]
    opciones = llamada["options"]
    assert opciones.output_format["schema"] == redaccion.ESQUEMA_REDACCION
    assert opciones.model == "claude-opus-5-5" and opciones.tools == []
    assert opciones.env["CLAUDE_CODE_PROMPT_CACHE_TTL"] == "1h"         # la segunda redacción de la sesión la lee
    ruta = Path(opciones.system_prompt["path"])
    assert ruta == redaccion.ruta_del_sistema(sesion, 1) and ruta.name == "sistema_redaccion.txt"
    assert ruta.parent.name == "_trabajo"                                # uno por sesión, no por material
    assert "FICHA DE LA SESIÓN (confirmada):" in ruta.read_text(encoding="utf-8")
    assert llamada["prompt"].startswith("PEDIDO PROPIO")
    assert "Llena solo «lectura». Deja en null «diapositivas», «laboratorio», «actividad», «evaluacion»." in llamada["prompt"]


def test_los_cinco_redactores_escriben_el_mismo_archivo_de_sistema(con_lectura):  # noqa: F811
    """Generar la lectura y después las diapositivas usa el mismo archivo: así la segunda lee la caché de la primera.
    La lectura es la única que no lleva la lectura aprobada (se genera antes)."""
    from tests.unidad.test_diapositivas import LIMPIAS, generar
    _, consulta = generar(con_lectura, LIMPIAS)
    ruta = Path(consulta.llamadas[0]["options"].system_prompt["path"])
    assert ruta == redaccion.ruta_del_sistema(con_lectura, 1)
    assert ruta.read_text(encoding="utf-8") == redaccion.sistema(con_lectura, 1, *redaccion.fuentes_de_la_sesion(con_lectura, 1))


def test_una_parte_desconocida_se_rechaza(sesion):  # noqa: F811
    with pytest.raises(ValueError, match="practica"):
        asyncio.run(redaccion.redactar("practica", "x", sesion, 1))
