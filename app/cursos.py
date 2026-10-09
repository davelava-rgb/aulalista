"""Carpetas de los cursos: cursos/[curso]/ (SPEC §9)."""

import json
import re
import unicodedata
from pathlib import Path

from app import config
from app.fuentes.convertir import formato_admitido

CARPETAS_RESERVADAS = {"_sistema"}


class ErrorDeCurso(ValueError):
    """Nombre de curso o de archivo no válido."""


def _base() -> Path:
    return config.CARPETA_CURSOS


def identificador(nombre: str) -> str:
    """Convierte el nombre del curso en un nombre de carpeta: sin tildes, espacios ni signos."""
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-z0-9]+", "-", sin_tildes.lower()).strip("-")
    if not texto:
        raise ErrorDeCurso("Escribe un nombre de curso con letras o números.")
    return texto


def crear(nombre: str) -> str:
    nombre = nombre.strip()
    curso = identificador(nombre)
    carpeta = _base() / curso
    if carpeta.exists():
        raise ErrorDeCurso(f"Ya existe un curso con la carpeta «{curso}».")
    (carpeta / "fuentes").mkdir(parents=True)
    (carpeta / "curso.json").write_text(
        json.dumps({"nombre": nombre}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return curso


def carpeta(curso: str) -> Path:
    if curso in CARPETAS_RESERVADAS or not re.fullmatch(r"[a-z0-9-]+", curso):
        raise ErrorDeCurso("Ese curso no existe.")
    ruta = _base() / curso
    if not (ruta / "curso.json").exists():
        raise ErrorDeCurso("Ese curso no existe.")
    return ruta


def nombre(curso: str) -> str:
    return json.loads((carpeta(curso) / "curso.json").read_text(encoding="utf-8"))["nombre"]


def listar() -> list[dict]:
    base = _base()
    if not base.exists():
        return []
    return [
        {"curso": ruta.name, "nombre": nombre(ruta.name)}
        for ruta in sorted(base.iterdir())
        if ruta.name not in CARPETAS_RESERVADAS and (ruta / "curso.json").exists()
    ]


def guardar_fuente(curso: str, nombre_archivo: str, datos: bytes) -> str:
    """Guarda un archivo en fuentes/. Si ya existe uno con ese nombre, lo reemplaza."""
    limpio = Path(nombre_archivo.replace("\\", "/")).name.strip()
    if not limpio or limpio.startswith((".", "~$")):
        raise ErrorDeCurso("El nombre del archivo no es válido.")
    if not formato_admitido(limpio):
        raise ErrorDeCurso(
            f"«{limpio}» no se admite. Usa PDF, Word, PowerPoint (.pptx), Excel (.xlsx) o imagen."
        )
    (carpeta(curso) / "fuentes" / limpio).write_bytes(datos)
    return limpio
