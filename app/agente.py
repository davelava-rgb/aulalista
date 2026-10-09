"""Único punto de contacto con el Claude Agent SDK (CLAUDE.md)."""

from collections.abc import AsyncIterator, Callable

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKError,
    ResultMessage,
    TextBlock,
    query,
)

from app import tokens
from app.config import RAIZ, FaltaClave, leer_clave, leer_tarea  # noqa: F401

Consulta = Callable[..., AsyncIterator]


class ErrorDeAgente(RuntimeError):
    """El SDK terminó con un error."""


def opciones_base(tarea: str, clave: str, **extra) -> ClaudeAgentOptions:
    """Opciones comunes de toda llamada.

    - La clave va en `env`, sin variable de Windows. Se vacían los otros
      medios de acceso para que nunca se use el inicio de sesión del plan Max.
    - `setting_sources=[]` evita cargar la configuración personal del usuario.
    - `tools=[]` deja al agente sin herramientas, salvo que la tarea las pida.
    """
    datos = leer_tarea(tarea)
    valores = {
        "model": datos["modelo"],
        "max_budget_usd": datos["tope_usd"],
        "env": {
            "ANTHROPIC_API_KEY": clave,
            "ANTHROPIC_AUTH_TOKEN": "",
            "CLAUDE_CODE_OAUTH_TOKEN": "",
        },
        "setting_sources": [],
        "tools": [],
        "max_turns": 1,
        "cwd": str(RAIZ),
    }
    valores.update(extra)
    return ClaudeAgentOptions(**valores)


async def ejecutar(
    pedido: str, opciones: ClaudeAgentOptions, consulta: Consulta = query
) -> tuple[str, ResultMessage]:
    """Envía un pedido y devuelve el texto de la respuesta y el resultado final."""
    partes: list[str] = []
    resultado: ResultMessage | None = None
    try:
        async for mensaje in consulta(prompt=pedido, options=opciones):
            if isinstance(mensaje, AssistantMessage):
                partes.extend(b.text for b in mensaje.content if isinstance(b, TextBlock))
            elif isinstance(mensaje, ResultMessage):
                resultado = mensaje
    except ClaudeSDKError as error:
        # Con una clave inválida, el SDK lanza el error en lugar de devolverlo.
        raise ErrorDeAgente(f"Claude no respondió bien ({error}).") from error
    if resultado is None:
        raise ErrorDeAgente("El SDK terminó sin un resultado final.")
    return "".join(partes).strip(), resultado


def _describir_error(resultado: ResultMessage) -> str:
    detalle = "; ".join(resultado.errors or []) or resultado.result or resultado.subtype
    if resultado.api_error_status:
        detalle = f"error {resultado.api_error_status} de la API: {detalle}"
    return f"Claude no respondió bien ({detalle})."


async def probar_conexion(consulta: Consulta = query) -> dict:
    """Envía un pedido corto, registra los tokens y devuelve la respuesta."""
    clave = leer_clave()
    opciones = opciones_base("conexion", clave)
    texto, resultado = await ejecutar(
        "Responde solo con estas dos palabras: Conexión correcta.", opciones, consulta
    )
    fila = tokens.registrar(
        resultado, curso=tokens.CURSO_SISTEMA, sesion="-", material="-", etapa="conexion"
    )
    if resultado.is_error:
        raise ErrorDeAgente(_describir_error(resultado))
    return {
        "texto": texto,
        "modelo": opciones.model,
        "tokens_entrada": fila["tokens_entrada"],
        "tokens_salida": fila["tokens_salida"],
        "costo_usd": fila["costo_usd"],
    }
