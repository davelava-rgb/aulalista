"""Escribe verificacion.json al confirmar la ficha de la sesión (SKILL.md, «Preparación»).

El formato está al inicio de .claude/skills/material-de-clase/scripts/verificar.py.
Este archivo es la base de la sesión. Cada material agrega después su nombre, sus
límites y su carpeta de práctica.
"""

import json
import re
from pathlib import Path

from app.fichas import almacen
from app.fuentes import convertir

PATRON_LAMINA = r"lámina (\d+)"
NO_SON_FRASES = {"tiempos", "puntajes", "relleno", "emojis", "lenguaje publicitario"}
NUNCA_POR_OMISION = ["objetivos de aprendizaje", "requisitos previos", "glosario", "glosarios"]


def fuentes_utilizables(carpeta_curso: Path) -> list[str]:
    """Fuentes que un material puede citar: convertidas y, si las leyó la IA, revisadas por el profesor."""
    return [
        archivo for archivo, entrada in convertir.leer_indice(carpeta_curso).items()
        if entrada["estado"] == convertir.CONVERTIDA and (not entrada["revisar"] or entrada["revisada"])
    ]


def _tiene_numero_impreso(carpeta_curso: Path, archivo: str) -> bool:
    return any(p.get("numero_impreso") is not None for p in convertir.leer_pasajes(carpeta_curso, archivo))


def nunca_se_incluye(ficha_curso: dict) -> list[str]:
    """Frases que el verificador busca. Tiempos, puntajes, emojis, relleno y lenguaje publicitario
    ya tienen sus propias revisiones."""
    texto = almacen.valor(ficha_curso, "materiales.nunca").strip()
    if not texto:
        return list(NUNCA_POR_OMISION)
    frases = []
    for parte in re.split(r",|;|\by\b|\n", texto.lower()):
        frase = parte.strip(" .:-")
        if frase.startswith("por defecto"):
            frase = frase.partition(":")[2].strip()
        if frase and frase not in NO_SON_FRASES:
            frases.append(frase)
            if frase.endswith("s") and " " not in frase:
                frases.append(frase[:-1])  # «glosarios» también busca «glosario»
    return list(dict.fromkeys(frases))


def construir(carpeta_curso: Path, sesion: int) -> dict:
    ficha_curso = almacen.cargar(carpeta_curso, "curso")
    ficha_sesion = almacen.cargar(carpeta_curso, "sesion", sesion)
    fuentes = []
    for archivo in fuentes_utilizables(carpeta_curso):
        fuente = {"nombre": archivo, "texto": f"../../fuentes_texto/{archivo}.jsonl", "norma": False}
        if _tiene_numero_impreso(carpeta_curso, archivo):
            fuente["referencias"] = {"patron": PATRON_LAMINA, "indice": "numero_impreso"}
        fuentes.append(fuente)
    datos_fijos, _ = almacen.datos_fijos(ficha_curso)
    return {
        "sesion": sesion,
        "material": "sesión",
        "fuentes": fuentes,
        "textos_permitidos": ["../../ficha_del_curso.md", "ficha_de_la_sesion.md"],
        "datos_fijos": datos_fijos,
        "vocabulario": [
            {"concepto": c["concepto"], "orden": c["orden"], "variantes": c["variantes"]}
            for c in almacen.vocabulario(ficha_sesion)
        ],
        "nunca_se_incluye": nunca_se_incluye(ficha_curso),
        "permitidos": ["notas del profesor"],
        "carpeta_practica": None,
        "limites": {},
    }


def escribir(carpeta_curso: Path, sesion: int) -> Path:
    ruta = almacen.carpeta_sesion(carpeta_curso, sesion) / "verificacion.json"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(construir(carpeta_curso, sesion), ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta
