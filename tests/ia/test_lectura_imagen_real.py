"""Claude lee el texto de una imagen de verdad. Gasta tokens. Se corre con: pytest -m ia"""

import asyncio

import pytest

from app import agente
from tests.fixtures import fuentes


@pytest.mark.ia
def test_claude_transcribe_una_imagen_tal_cual(tmp_path):
    imagen = fuentes.imagen(tmp_path / "f.png", "Fecha de referencia: 5 de octubre de 2026").read_bytes()
    lineas = asyncio.run(agente.leer_imagen(imagen, "image/png", curso="_sistema", etiqueta="prueba ia"))
    assert lineas == ["Fecha de referencia: 5 de octubre de 2026"]
