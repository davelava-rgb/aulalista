import asyncio

import pytest

from app import agente, tokens
from tests.conftest import consulta_simulada


def test_opciones_usan_la_clave_del_env_y_ningun_otro_acceso():
    opciones = agente.opciones_base("conexion", "sk-ant-de-prueba")
    assert opciones.env["ANTHROPIC_API_KEY"] == "sk-ant-de-prueba"
    # Vacíos para que nunca se use el inicio de sesión del plan Max (PLAN.md §0, decisión 3).
    assert opciones.env["ANTHROPIC_AUTH_TOKEN"] == ""
    assert opciones.env["CLAUDE_CODE_OAUTH_TOKEN"] == ""


def test_opciones_no_cargan_configuracion_personal_ni_herramientas():
    opciones = agente.opciones_base("conexion", "k")
    assert opciones.setting_sources == []
    assert opciones.tools == []


def test_opciones_toman_modelo_y_tope_de_la_tarea():
    opciones = agente.opciones_base("conexion", "k")
    assert opciones.model == "claude-haiku-4-5-20251001"
    assert opciones.max_budget_usd == 0.05


def test_probar_conexion_devuelve_texto_y_registra_tokens(entorno):
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    consulta = consulta_simulada()

    respuesta = asyncio.run(agente.probar_conexion(consulta))

    assert respuesta["texto"] == "Conexión correcta."
    assert respuesta["tokens_entrada"] == 115
    assert respuesta["tokens_salida"] == 7
    assert consulta.llamadas[0]["options"].env["ANTHROPIC_API_KEY"] == "sk-ant-de-prueba"
    assert tokens.total(tokens.CURSO_SISTEMA)["llamadas"] == 1


def test_sin_clave_no_llama_a_claude(entorno):
    consulta = consulta_simulada()
    with pytest.raises(agente.FaltaClave):
        asyncio.run(agente.probar_conexion(consulta))
    assert consulta.llamadas == []


def test_clave_invalida_se_avisa_con_mensaje(entorno):
    # Así responde el SDK real a una clave falsa: lanza ResultError.
    from claude_agent_sdk import ResultError

    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-falsa\n", encoding="utf-8")

    async def consulta(*, prompt, options):
        raise ResultError("Invalid API key · Fix external API key")
        yield

    with pytest.raises(agente.ErrorDeAgente, match="Invalid API key"):
        asyncio.run(agente.probar_conexion(consulta))


def test_error_del_sdk_se_avisa_y_se_registra(entorno):
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    consulta = consulta_simulada(
        texto="", subtype="error_during_execution", is_error=True,
        errors=["invalid x-api-key"], api_error_status=401,
    )
    with pytest.raises(agente.ErrorDeAgente, match="401"):
        asyncio.run(agente.probar_conexion(consulta))
    assert tokens.total(tokens.CURSO_SISTEMA)["llamadas"] == 1


# ---------- Decisión 68 b: caché de una hora por tarea ----------

def test_el_diseno_pide_la_cache_de_una_hora():
    assert agente.opciones_base("diseno", "k").env["CLAUDE_CODE_PROMPT_CACHE_TTL"] == "1h"


def test_sin_cache_en_la_tarea_no_se_toca_la_variable():
    assert "CLAUDE_CODE_PROMPT_CACHE_TTL" not in agente.opciones_base("conexion", "k").env


def test_una_vida_de_cache_desconocida_se_rechaza(tmp_path, monkeypatch):
    from app import config
    ruta = tmp_path / "modelos.toml"
    ruta.write_text('[rara]\nmodelo = "m"\ntope_usd = 0.01\ncache = "2h"\n', encoding="utf-8")
    monkeypatch.setattr(config, "RUTA_MODELOS", ruta)
    with pytest.raises(ValueError, match="5m"):
        agente.opciones_base("rara", "k")


# ---------- Decisión 74 a: caché apagada en las tareas de una sola llamada que nadie relee ----------

def test_una_tarea_con_cache_no_apaga_la_cache_y_no_pide_vida():
    env = agente.opciones_base("revision_visual", "k").env
    assert env["DISABLE_PROMPT_CACHING"] == "1"
    assert "CLAUDE_CODE_PROMPT_CACHE_TTL" not in env


def test_las_tareas_de_una_sola_llamada_apagan_la_cache_y_la_redaccion_pide_una_hora():
    from app.config import leer_tarea
    for tarea in ("revision_visual", "ejecucion", "comparacion_ejecucion", "revision_ejercicios", "lectura_imagen", "conexion"):
        assert leer_tarea(tarea).get("cache") == "no", tarea
    assert leer_tarea("redaccion").get("cache") == "1h"
    # Las que otra llamada relee siguen con caché: las correcciones comparten su mensaje de sistema (decisión 43).
    for tarea in ("correccion", "correccion_oraciones", "revision", "diseno", "arreglo_diseno", "fichas", "completar_ficha"):
        assert leer_tarea(tarea).get("cache") != "no", tarea


def test_una_tarea_con_cache_de_cinco_minutos_no_apaga_la_cache():
    env = agente.opciones_base("correccion", "k").env
    assert "DISABLE_PROMPT_CACHING" not in env


# ---------- Decisión 68 e: esfuerzo bajo en el diseño y medio en la redacción ----------

def test_el_esfuerzo_de_cada_tarea():
    esperado = {"diseno": "low", "arreglo_diseno": "low", "redaccion": "medium", "revision": "medium"}
    for tarea, esfuerzo in esperado.items():
        assert agente.opciones_base(tarea, "k").effort == esfuerzo, tarea
    assert agente.opciones_base("redaccion", "k").max_turns == 5   # sin herramientas, no hacen falta 40 turnos


# ---------- Decisión 68 f: AULALISTA_SIN_IA detiene toda llamada real ----------

def test_con_la_variable_puesta_ninguna_llamada_real_sale(entorno, monkeypatch):
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    monkeypatch.setenv(agente.SIN_IA, "1")
    with pytest.raises(agente.ErrorDeAgente, match="AULALISTA_SIN_IA está puesta"):
        asyncio.run(agente.probar_conexion())            # usaría query() de verdad: se detiene antes
    assert tokens.total(tokens.CURSO_SISTEMA)["llamadas"] == 0
    # Una consulta simulada (las pruebas) sigue funcionando con la variable puesta.
    respuesta = asyncio.run(agente.probar_conexion(consulta=consulta_simulada()))
    assert respuesta["texto"] == "Conexión correcta."


def test_la_variable_vacia_o_en_cero_no_detiene_nada(monkeypatch):
    for valor in ("", "0", "no"):
        monkeypatch.setenv(agente.SIN_IA, valor)
        assert agente.sin_ia() is False
    monkeypatch.delenv(agente.SIN_IA)
    assert agente.sin_ia() is False
