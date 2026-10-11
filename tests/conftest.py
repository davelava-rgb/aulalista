import sys
from pathlib import Path

import pytest
from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from app import config  # noqa: E402


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    """Aísla las pruebas: .env y carpeta de cursos en una carpeta temporal."""
    ruta_env = tmp_path / ".env"
    carpeta_cursos = tmp_path / "cursos"
    monkeypatch.setattr(config, "RUTA_ENV", ruta_env)
    monkeypatch.setattr(config, "CARPETA_CURSOS", carpeta_cursos)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    return {"env": ruta_env, "cursos": carpeta_cursos}


def resultado_simulado(**cambios) -> ResultMessage:
    valores = {
        "subtype": "success",
        "duration_ms": 900,
        "duration_api_ms": 800,
        "is_error": False,
        "num_turns": 1,
        "session_id": "sesion-de-prueba",
        "total_cost_usd": 0.0012,
        "usage": {
            "input_tokens": 10,
            "cache_read_input_tokens": 100,
            "cache_creation_input_tokens": 5,
            "output_tokens": 7,
        },
        "model_usage": {"claude-haiku-4-5-20251001": {}},
        "result": "Conexión correcta.",
    }
    valores.update(cambios)
    return ResultMessage(**valores)


def consulta_simulada(texto="Conexión correcta.", **cambios):
    """Reemplaza a query() del SDK: no llama a Claude ni gasta tokens."""
    llamadas = []

    async def consulta(*, prompt, options):
        llamadas.append({"prompt": prompt, "options": options})
        yield AssistantMessage(content=[TextBlock(text=texto)], model="claude-haiku-4-5-20251001")
        yield resultado_simulado(**cambios)

    consulta.llamadas = llamadas
    return consulta


def consulta_en_secuencia(*salidas):
    """Reemplaza a query() y devuelve una respuesta en JSON distinta en cada llamada."""
    llamadas = []
    pendientes = list(salidas)

    async def consulta(*, prompt, options):
        llamadas.append({"prompt": prompt, "options": options})
        salida = pendientes.pop(0)
        yield resultado_simulado(structured_output=salida(prompt) if callable(salida) else salida)

    consulta.llamadas = llamadas
    return consulta
