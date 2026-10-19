"""Un solo esquema para todas las correcciones de un material, para que lean la caché (PLAN.md §0, decisión 51)."""

import asyncio

import pytest

from app import agente
from app.materiales import comun, diapositivas, laboratorio, lectura


@pytest.mark.parametrize("modulo, formas", [
    (lectura, {"completa": lectura.ESQUEMA_CORRECCION, "oraciones": comun.ESQUEMA_CAMBIOS}),
    (diapositivas, {"completa": diapositivas.ESQUEMA_CORRECCION,
                    "por_diapositivas": diapositivas.ESQUEMA_POR_DIAPOSITIVAS, "oraciones": comun.ESQUEMA_CAMBIOS}),
    (laboratorio, {"completa": laboratorio.ESQUEMA_CORRECCION,
                   "por_ejercicios": laboratorio.ESQUEMA_CORRECCION_POR_EJERCICIO, "oraciones": comun.ESQUEMA_CAMBIOS}),
])
def test_cada_material_tiene_un_esquema_con_todas_sus_formas_de_corregir(modulo, formas):
    esquema = modulo.ESQUEMA_CORRECCIONES
    assert esquema["required"] == list(formas)
    for forma, parte in formas.items():
        assert esquema["properties"][forma] == {"anyOf": [parte, {"type": "null"}]}


def pedir(monkeypatch, respuesta: dict, forma: str):
    llamadas = []

    async def consultar(pedido, *, esquema, **opciones):
        llamadas.append({"pedido": pedido, "esquema": esquema})
        return respuesta

    monkeypatch.setattr(agente, "consultar", consultar)
    resultado = asyncio.run(comun.consultar_correccion("Corrige esto.", forma, lectura.ESQUEMA_CORRECCIONES,
                                                       tarea="correccion_oraciones"))
    return resultado, llamadas


def test_la_correccion_devuelve_solo_la_parte_pedida(monkeypatch):
    cambios = {"cambios": [], "explicaciones": [], "datos_nuevos": []}
    resultado, llamadas = pedir(monkeypatch, {"completa": None, "oraciones": cambios}, "oraciones")
    assert resultado == cambios
    assert llamadas[0]["esquema"] is lectura.ESQUEMA_CORRECCIONES
    assert llamadas[0]["pedido"] == "Corrige esto.\nLlena solo «oraciones». Deja en null «completa»."


def test_una_correccion_sin_la_parte_pedida_es_un_error(monkeypatch):
    with pytest.raises(agente.ErrorDeAgente, match="no devolvió «oraciones»"):
        pedir(monkeypatch, {"completa": {"lectura": {}}, "oraciones": None}, "oraciones")
