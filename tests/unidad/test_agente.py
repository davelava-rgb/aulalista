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
