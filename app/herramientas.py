"""Herramientas propias que el agente puede llamar (en el SDK, «herramientas MCP»).

buscar_en_fuentes: busca pasajes en las fuentes del curso y en las fichas. La primera pasada
la usa cuando ninguno de los pasajes que eligió el programa sirve (PLAN.md §5.2).

Herramientas del revisor independiente (PLAN.md §5.4): listar, leer y buscar, solo dentro de su
carpeta de trabajo. No hay herramienta para escribir, y ninguna lee fuera de esa carpeta.
"""

import re
from pathlib import Path

from claude_agent_sdk import create_sdk_mcp_server, tool

from app.validacion.pasajes import Corpus, normal

SERVIDOR = "aulalista"
BUSCAR = f"mcp__{SERVIDOR}__buscar_en_fuentes"
RESULTADOS = 5

SERVIDOR_REVISOR = "carpeta_del_revisor"
LISTAR = f"mcp__{SERVIDOR_REVISOR}__listar_archivos"
LEER = f"mcp__{SERVIDOR_REVISOR}__leer_archivo"
BUSCAR_TEXTO = f"mcp__{SERVIDOR_REVISOR}__buscar_texto"
BUSCAR_PARECIDO = f"mcp__{SERVIDOR_REVISOR}__buscar_en_fuentes"
HERRAMIENTAS_REVISOR = (LISTAR, LEER, BUSCAR_TEXTO, BUSCAR_PARECIDO)
LINEAS_MAX = 300
COINCIDENCIAS_MAX = 40


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


# ---------- Carpeta del revisor independiente ----------

def _texto(mensaje: str) -> dict:
    return {"content": [{"type": "text", "text": mensaje}]}


def dentro_de(carpeta: Path, relativa: str) -> Path | None:
    """La ruta pedida, solo si queda dentro de la carpeta. Si sale de ella, None."""
    base = carpeta.resolve()
    ruta = (base / relativa).resolve()
    return ruta if ruta.is_relative_to(base) and ruta.is_file() else None


def listar(carpeta: Path) -> str:
    base = carpeta.resolve()
    return "\n".join(sorted(str(r.relative_to(base)).replace("\\", "/") for r in base.rglob("*") if r.is_file()))


def leer(carpeta: Path, archivo: str, desde: int, cantidad: int) -> str:
    ruta = dentro_de(carpeta, archivo)
    if ruta is None:
        return f"No existe «{archivo}» en tu carpeta. Usa listar_archivos."
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    desde = max(1, desde)
    cantidad = max(1, min(cantidad, LINEAS_MAX))
    parte = lineas[desde - 1:desde - 1 + cantidad]
    if not parte:
        return f"«{archivo}» tiene {len(lineas)} líneas."
    return "\n".join(f"{desde + i}: {linea}" for i, linea in enumerate(parte))


def buscar_texto(carpeta: Path, patron: str) -> str:
    """Como grep: líneas que contienen el patrón, sin distinguir mayúsculas ni tildes."""
    try:
        expresion = re.compile(normal(patron))
    except re.error:
        expresion = re.compile(re.escape(normal(patron)))
    base = carpeta.resolve()
    encontradas = []
    for ruta in sorted(base.rglob("*")):
        if not ruta.is_file():
            continue
        nombre = str(ruta.relative_to(base)).replace("\\", "/")
        for numero, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
            if expresion.search(normal(linea)):
                encontradas.append(f"{nombre}:{numero}: {linea}")
                if len(encontradas) == COINCIDENCIAS_MAX:
                    return "\n".join(encontradas + [f"(se muestran las primeras {COINCIDENCIAS_MAX})"])
    return "\n".join(encontradas) or "Sin coincidencias."


def servidor_del_revisor(carpeta: Path, corpus: Corpus):
    """Herramientas de solo lectura sobre la carpeta del revisor. Devuelve (servidor, uso)."""
    uso = {"llamadas": 0}

    @tool("listar_archivos", "Lista los archivos de tu carpeta de trabajo.", {})
    async def listar_archivos(_argumentos):
        uso["llamadas"] += 1
        return _texto(listar(carpeta))

    @tool("leer_archivo",
          f"Lee un archivo de tu carpeta. «desde» es la primera línea (empieza en 1) y «cantidad» "
          f"el número de líneas, {LINEAS_MAX} como máximo.",
          {"archivo": str, "desde": int, "cantidad": int})
    async def leer_archivo(argumentos):
        uso["llamadas"] += 1
        return _texto(leer(carpeta, argumentos["archivo"], argumentos["desde"], argumentos["cantidad"]))

    @tool("buscar_texto",
          "Busca un texto o una expresión regular en todos los archivos de tu carpeta, sin distinguir "
          "mayúsculas ni tildes. Devuelve archivo, número de línea y línea.",
          {"patron": str})
    async def buscar(argumentos):
        uso["llamadas"] += 1
        return _texto(buscar_texto(carpeta, argumentos["patron"]))

    @tool("buscar_en_fuentes",
          "Busca en las fuentes y en las fichas los pasajes más parecidos a un texto, aunque no tengan "
          "las mismas palabras. Devuelve cada pasaje con su fuente y su ubicación.",
          {"texto": str})
    async def parecidos(argumentos):
        uso["llamadas"] += 1
        return _texto(formatear(corpus.buscar(argumentos["texto"], RESULTADOS)))

    servidor = create_sdk_mcp_server(name=SERVIDOR_REVISOR, tools=[listar_archivos, leer_archivo, buscar, parecidos])
    return servidor, uso
