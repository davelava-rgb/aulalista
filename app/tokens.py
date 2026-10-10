"""Registro de los tokens que gasta cada llamada al SDK (SPEC §9).

Cada curso tiene su archivo cursos/[curso]/tokens.jsonl, con una línea por llamada.
El costo es la estimación que da el SDK, no la factura.
"""

import json
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import ResultMessage

from app import config

CURSO_SISTEMA = "_sistema"


def _tokens_de_entrada(uso: dict) -> int:
    return (
        uso.get("input_tokens", 0)
        + uso.get("cache_read_input_tokens", 0)
        + uso.get("cache_creation_input_tokens", 0)
    )


def registrar(
    resultado: ResultMessage,
    *,
    curso: str,
    sesion: str,
    material: str,
    etapa: str,
    carpeta_cursos: Path | None = None,
) -> dict:
    """Agrega una línea al registro del curso y la devuelve."""
    uso = resultado.usage or {}
    fila = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "curso": curso,
        "sesion": sesion,
        "material": material,
        "etapa": etapa,
        "modelos": sorted((resultado.model_usage or {}).keys()),
        "tokens_entrada": _tokens_de_entrada(uso),
        "tokens_salida": uso.get("output_tokens", 0),
        "costo_usd": resultado.total_cost_usd or 0.0,
        "uso": uso,
        "duracion_ms": resultado.duration_ms,
        "turnos": resultado.num_turns,
        "error": resultado.is_error,
    }
    ruta = (carpeta_cursos or config.CARPETA_CURSOS) / curso / "tokens.jsonl"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as archivo:
        archivo.write(json.dumps(fila, ensure_ascii=False) + "\n")
    return fila


def lineas(curso: str, carpeta_cursos: Path | None = None) -> int:
    """Cuántas llamadas tiene ya el registro. Marca el inicio de un trabajo para sumar solo lo que gastó."""
    ruta = (carpeta_cursos or config.CARPETA_CURSOS) / curso / "tokens.jsonl"
    if not ruta.exists():
        return 0
    return sum(1 for linea in ruta.read_text(encoding="utf-8").splitlines() if linea.strip())


def total(curso: str, carpeta_cursos: Path | None = None, *, sesion: str | None = None,
          material: str | None = None, desde_linea: int = 0) -> dict:
    """Suma los tokens y el costo estimado de un curso. Con los filtros, solo de una sesión,
    de un material o de las llamadas que siguen a `desde_linea` (por ejemplo, las de una generación)."""
    suma = {"llamadas": 0, "tokens_entrada": 0, "tokens_salida": 0, "costo_usd": 0.0}
    ruta = (carpeta_cursos or config.CARPETA_CURSOS) / curso / "tokens.jsonl"
    if not ruta.exists():
        return suma
    filas = [linea for linea in ruta.read_text(encoding="utf-8").splitlines() if linea.strip()]
    for linea in filas[desde_linea:]:
        fila = json.loads(linea)
        if (sesion is not None and fila["sesion"] != sesion) or (material is not None and fila["material"] != material):
            continue
        suma["llamadas"] += 1
        suma["tokens_entrada"] += fila["tokens_entrada"]
        suma["tokens_salida"] += fila["tokens_salida"]
        suma["costo_usd"] += fila["costo_usd"]
    suma["costo_usd"] = round(suma["costo_usd"], 6)
    return suma
