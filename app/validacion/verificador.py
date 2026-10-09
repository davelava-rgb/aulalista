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


def _comparable(texto: str) -> str:
    return " ".join(verificar.normalizar(verificar.literal(texto or "")).strip(" .,;:\"'").split())


def clave_de_hallazgo(regla: str, oracion: str) -> str:
    """Clave tolerante: no cambia por mayúsculas, tildes, comillas, espacios ni el punto final."""
    return f"{_comparable(regla)}\n{_comparable(oracion)}"


def buscar_explicacion(regla: str, oracion: str, explicaciones: dict) -> str | None:
    """Explicación de un aviso, aunque la IA haya copiado la oración con pequeñas diferencias
    o solo una parte de ella."""
    clave = clave_de_hallazgo(regla, oracion)
    if clave in explicaciones:
        return explicaciones[clave]
    regla_buscada, oracion_buscada = clave.split("\n", 1)
    for otra, explicacion in explicaciones.items():
        regla_otra, oracion_otra = otra.split("\n", 1)
        # La IA a veces copia la regla con su nivel o con la línea entera del problema.
        if regla_buscada and regla_buscada in regla_otra and oracion_otra and oracion_buscada and (
                oracion_otra in oracion_buscada or oracion_buscada in oracion_otra):
            return explicacion
    return None


def anotar_explicaciones(salida_excel: Path, explicaciones: dict) -> None:
    libro = openpyxl.load_workbook(salida_excel)
    hoja = libro["Hallazgos"]
    for fila in hoja.iter_rows(min_row=2):
        explicacion = buscar_explicacion(fila[3].value or "", fila[2].value or "", explicaciones)
        if explicacion:
            fila[5].value = explicacion
    libro.save(salida_excel)
