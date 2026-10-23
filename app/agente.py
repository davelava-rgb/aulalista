"""Único punto de contacto con el Claude Agent SDK (CLAUDE.md)."""

import base64
from pathlib import Path
from collections.abc import AsyncIterable, AsyncIterator, Callable

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


VIDAS_DE_CACHE = ("5m", "1h")   # lo que admite CLAUDE_CODE_PROMPT_CACHE_TTL


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
        "max_turns": datos.get("max_turns", 1),
        "cwd": str(RAIZ),
    }
    if "esfuerzo" in datos:
        valores["effort"] = datos["esfuerzo"]  # «low» a «max»: cuánto razona antes de responder
    if "cache" in datos:
        # Cuánto vive la caché del pedido: «5m» (lo normal) o «1h». La de una hora cuesta más al escribirse y sirve
        # cuando la llamada dura más de cinco minutos y otra llamada va a leer su comienzo después (decisión 68 b).
        # Variable documentada del CLI: CLAUDE_CODE_PROMPT_CACHE_TTL (docs/en/agent-sdk/cost-tracking).
        if datos["cache"] not in VIDAS_DE_CACHE:
            raise ValueError(f"La tarea «{tarea}» tiene cache = «{datos['cache']}»; vale «5m» o «1h».")
        valores["env"]["CLAUDE_CODE_PROMPT_CACHE_TTL"] = datos["cache"]
    valores.update(extra)
    return ClaudeAgentOptions(**valores)


async def ejecutar(
    pedido: str | AsyncIterable[dict], opciones: ClaudeAgentOptions, consulta: Consulta = query
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


ESQUEMA_LINEAS = {
    "type": "object",
    "properties": {"lineas": {"type": "array", "items": {"type": "string"}}},
    "required": ["lineas"],
    "additionalProperties": False,
}

PEDIDO_IMAGEN = (
    "Transcribe todo el texto que se ve en esta imagen, tal cual, en su idioma original. "
    "Una línea de la imagen por elemento de la lista, en orden de lectura. "
    "No corrijas, no traduzcas, no resumas y no agregues nada. "
    "Si la imagen no tiene texto, devuelve una lista vacía."
)


async def leer_imagen(
    imagen: bytes, tipo: str, *, curso: str, etiqueta: str, consulta: Consulta = query
) -> list[str]:
    """Pide a Claude el texto de una imagen o de una página escaneada (SPEC §9).

    El resultado lo revisa el profesor antes de usarlo.
    """
    clave = leer_clave()
    opciones = opciones_base(
        "lectura_imagen",
        clave,
        output_format={"type": "json_schema", "schema": ESQUEMA_LINEAS},
    )

    async def mensajes():
        yield {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": tipo,
                            "data": base64.b64encode(imagen).decode("ascii"),
                        },
                    },
                    {"type": "text", "text": PEDIDO_IMAGEN},
                ],
            },
            "parent_tool_use_id": None,
        }

    _, resultado = await ejecutar(mensajes(), opciones, consulta)
    tokens.registrar(resultado, curso=curso, sesion="-", material=etiqueta, etapa="lectura_imagen")
    if resultado.is_error or not isinstance(resultado.structured_output, dict):
        raise ErrorDeAgente(_describir_error(resultado))
    return [linea for linea in resultado.structured_output["lineas"] if linea.strip()]


async def consultar(
    pedido: str,
    *,
    tarea: str,
    esquema: dict,
    curso: str,
    etapa: str,
    sesion: str = "-",
    material: str = "-",
    cwd=None,
    herramientas: tuple[str, ...] = (),
    servidores: dict | None = None,
    sistema: Path | None = None,
    consulta: Consulta = query,
) -> dict:
    """Pedido con respuesta en JSON validado contra `esquema`.

    Con `sistema`, el mensaje de sistema se lee de ese archivo. Lo que va ahí se guarda en caché y las llamadas
    siguientes con el mismo archivo lo pagan mucho más barato.

    Con `herramientas`, el agente solo puede usar esas (por ejemplo Read y Grep, o una
    herramienta propia «mcp__...» de `servidores`) y todo lo demás queda denegado sin preguntar.
    """
    extra = {"output_format": {"type": "json_schema", "schema": esquema}}
    permitidas = [h for h in herramientas if not h.startswith("mcp__")]
    if herramientas:
        extra.update(tools=permitidas, allowed_tools=list(herramientas), permission_mode="dontAsk")
    if servidores:
        extra["mcp_servers"] = servidores
    if cwd is not None:
        extra["cwd"] = str(cwd)
    if sistema is not None:
        extra["system_prompt"] = {"type": "file", "path": str(sistema)}
    opciones = opciones_base(tarea, leer_clave(), **extra)
    _, resultado = await ejecutar(pedido, opciones, consulta)
    tokens.registrar(resultado, curso=curso, sesion=sesion, material=material, etapa=etapa)
    if resultado.is_error or not isinstance(resultado.structured_output, dict):
        raise ErrorDeAgente(_describir_error(resultado))
    return resultado.structured_output


async def conversar(
    pedido: str,
    *,
    tarea: str,
    curso: str,
    etapa: str,
    sesion: str = "-",
    material: str = "-",
    consulta: Consulta = query,
) -> str:
    """Pedido sin esquema y sin herramientas: devuelve el texto tal como lo leería una persona en un chat.
    Sirve para ejecutar el prompt de un ejercicio como lo haría un alumno (PLAN.md §0, decisión 35)."""
    opciones = opciones_base(tarea, leer_clave())
    texto, resultado = await ejecutar(pedido, opciones, consulta)
    tokens.registrar(resultado, curso=curso, sesion=sesion, material=material, etapa=etapa)
    if resultado.is_error:
        raise ErrorDeAgente(_describir_error(resultado))
    return texto or (resultado.result or "").strip()


async def consultar_con_imagenes(
    pedido: str,
    imagenes: list[tuple[str, bytes]],
    *,
    tarea: str,
    esquema: dict,
    curso: str,
    etapa: str,
    sesion: str = "-",
    material: str = "-",
    sistema: Path | None = None,
    consulta: Consulta = query,
) -> dict:
    """Pedido con imágenes PNG y respuesta en JSON validado contra `esquema`. Mismo envío que leer_imagen:
    cada imagen va precedida de su etiqueta, y el pedido va al final. Sin herramientas. Con `sistema`, como en
    consultar: el mensaje de sistema se lee de ese archivo y se guarda en caché."""
    extra = {"output_format": {"type": "json_schema", "schema": esquema}}
    if sistema is not None:
        extra["system_prompt"] = {"type": "file", "path": str(sistema)}
    opciones = opciones_base(tarea, leer_clave(), **extra)
    contenido = []
    for etiqueta, imagen in imagenes:
        contenido.append({"type": "text", "text": etiqueta})
        contenido.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                      "data": base64.b64encode(imagen).decode("ascii")}})
    contenido.append({"type": "text", "text": pedido})

    async def mensajes():
        yield {"type": "user", "message": {"role": "user", "content": contenido}, "parent_tool_use_id": None}

    _, resultado = await ejecutar(mensajes(), opciones, consulta)
    tokens.registrar(resultado, curso=curso, sesion=sesion, material=material, etapa=etapa)
    if resultado.is_error or not isinstance(resultado.structured_output, dict):
        raise ErrorDeAgente(_describir_error(resultado))
    return resultado.structured_output
