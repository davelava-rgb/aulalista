"""Decisión 68 b: con cache = "1h" en la tarea, la caché sobrevive más de cinco minutos.

Llama a Claude de verdad, con Haiku, dos veces y espera seis minutos entre las dos. Gasta centavos y tarda unos
siete minutos. Se corre aparte: pytest -m ia tests/ia/test_cache_1h.py
"""

import asyncio
import time

import pytest

from app import agente, config, tokens

ESPERA_SEGUNDOS = 6 * 60
ESQUEMA = {"type": "object", "properties": {"respuesta": {"type": "string"}}, "required": ["respuesta"],
           "additionalProperties": False}
FRASE = ("La gobernanza de los datos de una entidad decide quién aprueba cada dato, quién lo cuida y quién responde "
         "por su calidad. ")
MODELOS = """[prueba_cache]
modelo = "claude-haiku-4-5-20251001"
tope_usd = 0.05
max_turns = 3
cache = "1h"
"""


@pytest.fixture
def tarea_de_prueba(tmp_path, monkeypatch):
    ruta = tmp_path / "modelos.toml"
    ruta.write_text(MODELOS, encoding="utf-8")
    monkeypatch.setattr(config, "RUTA_MODELOS", ruta)
    sistema = tmp_path / "sistema.txt"
    # Unas 4 500 palabras: más que el mínimo que la API guarda en caché para Haiku. La hora hace único el contexto:
    # así la primera llamada siempre escribe la caché y no lee la de una corrida anterior.
    encabezado = f"CONTEXTO DE PRUEBA, SOLO PARA MEDIR LA CACHÉ. Corrida de las {time.strftime('%H:%M:%S')}.\n"
    sistema.write_text(encabezado + FRASE * 250, encoding="utf-8")
    return sistema


async def _llamar(sistema, numero: int) -> dict:
    opciones = agente.opciones_base("prueba_cache", config.leer_clave(),
                                    system_prompt={"type": "file", "path": str(sistema)},
                                    output_format={"type": "json_schema", "schema": ESQUEMA})
    _, resultado = await agente.ejecutar("Responde solo con la palabra: listo.", opciones)
    fila = tokens.registrar(resultado, curso=tokens.CURSO_SISTEMA, sesion="-", material="prueba ia",
                            etapa=f"prueba cache 1h · llamada {numero}")
    assert not resultado.is_error, resultado.result
    return fila["uso"]


@pytest.mark.ia
def test_la_cache_de_una_hora_sobrevive_seis_minutos(tarea_de_prueba):
    primera = asyncio.run(_llamar(tarea_de_prueba, 1))
    escritas = primera.get("cache_creation", {}).get("ephemeral_1h_input_tokens", 0)
    assert escritas > 2000, f"La primera llamada no escribió caché de una hora: {primera}"

    time.sleep(ESPERA_SEGUNDOS)

    segunda = asyncio.run(_llamar(tarea_de_prueba, 2))
    leidas = segunda.get("cache_read_input_tokens", 0)
    assert leidas >= escritas * 0.9, f"La segunda llamada no leyó la caché: {segunda}"
