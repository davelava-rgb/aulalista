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


SIN_COMPARAR = {c: "no aplica" for c in ("numero", "termino", "cantidades", "orden", "quien", "obligacion", "generalizacion")}


def pasada(especiales: dict | None = None):
    """Respuesta simulada de la primera pasada: lee las oraciones del pedido y las aprueba,
    salvo las que tienen una respuesta especial (por texto de la oración)."""
    import re as _re
    especiales = especiales or {}

    def responder(prompt):
        oraciones = []
        for n, texto in _re.findall(r"^\[(\d+)\] Sección: .*? \| Oración: (.*)$", prompt, _re.M):
            base = {"n": int(n), "tipo": "sin afirmación", "fuente": "", "pasaje": "", "veredicto": "coincide",
                    "motivo": "Sin afirmación.", "comparacion": dict(SIN_COMPARAR)}
            oraciones.append({**base, **especiales.get(texto, {})})
        return {"oraciones": oraciones}

    return responder



def segunda(defectos: list | None = None, lista_no: list | None = None):
    """Respuesta simulada de la segunda pasada: responde las cuatro preguntas de los bloques pedidos."""
    import re as _re

    def responder(prompt):
        linea = prompt.rstrip().splitlines()[-1]
        nombres = _re.findall(r"\[([^\]]+)\]", linea)
        bloques = [{"bloque": n, "que_puede_hacer": "Aplicar el concepto.", "que_necesita": "Está en el bloque.",
                    "dos_lecturas": "Ninguna", "si_no_sale": "No aplica."} for n in nombres]
        return {"bloques": bloques, "defectos": defectos or [], "lista": lista_no or []}

    return responder
