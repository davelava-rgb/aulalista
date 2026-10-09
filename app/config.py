"""Rutas del proyecto, clave de API y modelos por tarea."""

import tomllib
from pathlib import Path

from dotenv import dotenv_values

RAIZ = Path(__file__).resolve().parent.parent
RUTA_ENV = RAIZ / ".env"
RUTA_MODELOS = RAIZ / "config" / "modelos.toml"
CARPETA_CURSOS = RAIZ / "cursos"


class FaltaClave(RuntimeError):
    """El archivo .env no tiene la clave de API."""


def leer_clave(ruta_env: Path | None = None) -> str:
    """Lee la clave solo del archivo .env.

    No mira las variables de Windows: la clave nunca se define ahí (SPEC §9).
    """
    ruta_env = ruta_env or RUTA_ENV
    valores = dotenv_values(ruta_env) if ruta_env.exists() else {}
    clave = (valores.get("ANTHROPIC_API_KEY") or "").strip()
    if not clave:
        raise FaltaClave(
            "No hay clave de API en el archivo .env. "
            "Copia .env.example como .env y escribe tu clave en ANTHROPIC_API_KEY."
        )
    return clave


def leer_tarea(nombre: str, ruta_modelos: Path | None = None) -> dict:
    """Devuelve el modelo y el tope de gasto de una tarea."""
    ruta_modelos = ruta_modelos or RUTA_MODELOS
    with open(ruta_modelos, "rb") as archivo:
        tareas = tomllib.load(archivo)
    if nombre not in tareas:
        raise KeyError(f"La tarea '{nombre}' no está en {ruta_modelos.name}.")
    return tareas[nombre]
