import re
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


_FORMA = re.compile(r"Llena solo «(\w+)»")


def en_forma(salida, prompt, options):
    """Una corrección o una redacción pide una sola parte del esquema común (decisiones 51 y 74). Si la prueba da
    solo esa parte, se pone en su lugar y las demás quedan en null, como las devuelve Claude. Las diapositivas traen
    una lista «diapositivas», que no es la parte: también se envuelven."""
    forma = _FORMA.search(prompt) if isinstance(prompt, str) else None
    if forma is None or not isinstance(salida, dict) or isinstance(salida.get(forma[1]), dict):
        return salida
    return {f: salida if f == forma[1] else None for f in options.output_format["schema"]["properties"]}


def texto_del_redactor(llamada) -> str:
    """Todo lo que lee el redactor: el mensaje de sistema (la parte común de la sesión, decisión 74 b) y el pedido."""
    sistema = llamada["options"].system_prompt
    comun = Path(sistema["path"]).read_text(encoding="utf-8") if isinstance(sistema, dict) else (sistema or "")
    return comun + "\n" + llamada["prompt"]


def consulta_en_secuencia(*salidas):
    """Reemplaza a query() y devuelve una respuesta en JSON distinta en cada llamada."""
    llamadas = []
    pendientes = list(salidas)

    async def consulta(*, prompt, options):
        llamadas.append({"prompt": prompt, "options": options})
        salida = pendientes.pop(0)
        salida = salida(prompt) if callable(salida) else salida
        yield resultado_simulado(structured_output=en_forma(salida, prompt, options))

    consulta.llamadas = llamadas
    return consulta
