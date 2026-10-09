"""Herramientas propias que el agente puede llamar (en el SDK, «herramientas MCP»).

buscar_en_fuentes: busca pasajes en las fuentes del curso y en las fichas. La primera pasada
la usa cuando ninguno de los pasajes que eligió el programa sirve (PLAN.md §5.2).
"""

from claude_agent_sdk import create_sdk_mcp_server, tool

from app.validacion.pasajes import Corpus

SERVIDOR = "aulalista"
BUSCAR = f"mcp__{SERVIDOR}__buscar_en_fuentes"
RESULTADOS = 5


def formatear(resultados: list[dict]) -> str:
    if not resultados:
        return "No hay pasajes."
    return "\n".join(f"- ({r['fuente']} · {r['ubicacion']}) {r['texto']}" for r in resultados)


def servidor_de_busqueda(corpus: Corpus):
    """Servidor con la herramienta de búsqueda sobre un corpus. Devuelve (servidor, uso)."""
    uso = {"busquedas": 0}

    @tool("buscar_en_fuentes",
          "Busca en las fuentes del curso y en las fichas los pasajes más parecidos a un texto. "
          "Devuelve cada pasaje con su fuente y su ubicación, tal como están escritos.",
          {"texto": str})
    async def buscar_en_fuentes(argumentos):
        uso["busquedas"] += 1
        return {"content": [{"type": "text", "text": formatear(corpus.buscar(argumentos["texto"], RESULTADOS))}]}

    return create_sdk_mcp_server(name=SERVIDOR, tools=[buscar_en_fuentes]), uso
