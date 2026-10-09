"""Lee las reglas de la skill material-de-clase para dárselas al agente redactor.

No se usa la carga de skills del SDK: con setting_sources=["project"] el SDK también carga el
CLAUDE.md de AulaLista, que trata de cómo construir el software y no le sirve al redactor
(comprobado el 2026-10-08). Aquí se toman solo las secciones que necesita cada material.
La skill sigue siendo la única fuente de las reglas.
"""

import re

from app.config import RAIZ

RUTA = RAIZ / ".claude" / "skills" / "material-de-clase" / "SKILL.md"


def secciones(*titulos: str) -> str:
    """Devuelve las secciones «## Título» pedidas, completas y en el orden pedido."""
    texto = RUTA.read_text(encoding="utf-8")
    partes = re.split(r"(?m)^(?=## )", texto)
    encontradas = []
    for titulo in titulos:
        seccion = next((p for p in partes if p.startswith(f"## {titulo}")), None)
        if seccion is None:
            raise KeyError(f"SKILL.md no tiene la sección «{titulo}».")
        encontradas.append(seccion.strip())
    return "\n\n".join(encontradas)


def subseccion(titulo: str) -> str:
    """Devuelve una subsección «### Título» completa, hasta el siguiente «### » o «## »."""
    texto = RUTA.read_text(encoding="utf-8")
    coincidencia = re.search(rf"(?ms)^### {re.escape(titulo)}.*?(?=^##)", texto + "\n##")
    if coincidencia is None:
        raise KeyError(f"SKILL.md no tiene la subsección «{titulo}».")
    return coincidencia.group(0).strip()
