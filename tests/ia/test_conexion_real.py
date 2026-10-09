"""Llama a Claude de verdad. Gasta tokens. Se corre con: pytest -m ia"""

import asyncio

import pytest

from app import agente


@pytest.mark.ia
def test_conexion_real_devuelve_texto_y_tokens():
    respuesta = asyncio.run(agente.probar_conexion())
    assert respuesta["texto"]
    assert respuesta["tokens_entrada"] > 0
    assert respuesta["tokens_salida"] > 0
