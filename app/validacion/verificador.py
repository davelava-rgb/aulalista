"""Puente entre AulaLista y el programa verificador de la skill.

El verificador es un programa aparte (.claude/skills/material-de-clase/scripts/verificar.py).
AulaLista lo importa para no gastar tiempo en abrir otro proceso, y le agrega a la base de la
sesión el nombre, los límites y la carpeta de práctica de cada material.
"""

import importlib.util
import json
import sys
from pathlib import Path

import openpyxl

from app.config import RAIZ

RUTA = RAIZ / ".claude" / "skills" / "material-de-clase" / "scripts" / "verificar.py"


def _cargar():
    if "verificar" in sys.modules:
        return sys.modules["verificar"]
    especificacion = importlib.util.spec_from_file_location("verificar", RUTA)
    modulo = importlib.util.module_from_spec(especificacion)
    sys.modules["verificar"] = modulo
    especificacion.loader.exec_module(modulo)
    return modulo


verificar = _cargar()

# Límites de cada material (SPEC §4 y SKILL.md). Los demás se agregan en sus etapas.
LIMITES = {
    "Lectura": {"paginas_max": 6},
}


def configuracion_del_material(carpeta_sesion: Path, material: str, carpeta_practica: str | None = None) -> Path:
    """Copia la base de la sesión con los datos del material. Queda junto a la base, para que
    las rutas relativas sigan valiendo."""
    base = json.loads((carpeta_sesion / "verificacion.json").read_text(encoding="utf-8"))
    base.update(material=material, limites=LIMITES.get(material, {}), carpeta_practica=carpeta_practica)
    ruta = carpeta_sesion / f"verificacion_{material.lower().replace(' ', '_')}.json"
    ruta.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta


def ejecutar(configuracion: Path, archivos: list[Path], salida_excel: Path, explicaciones: dict | None = None,
             contar_paginas=None):
    """Corre el verificador, escribe el Excel y su copia en JSON, y anota en «Cómo se resolvió»
    la explicación de cada aviso que se mantuvo."""
    opciones = {"contar_paginas": contar_paginas} if contar_paginas else {}
    resultado = verificar.verificar(configuracion, archivos, **opciones)
    verificar.escribir_excel(resultado, salida_excel)
    verificar.escribir_json(resultado, salida_excel.with_suffix(".json"))
    if explicaciones:
        anotar_explicaciones(salida_excel, explicaciones)
    return resultado


def clave_de_hallazgo(regla: str, oracion: str) -> str:
    return f"{regla}\n{oracion}"


def anotar_explicaciones(salida_excel: Path, explicaciones: dict) -> None:
    libro = openpyxl.load_workbook(salida_excel)
    hoja = libro["Hallazgos"]
    for fila in hoja.iter_rows(min_row=2):
        clave = clave_de_hallazgo(fila[3].value or "", fila[2].value or "")
        if clave in explicaciones:
            fila[5].value = explicaciones[clave]
    libro.save(salida_excel)
