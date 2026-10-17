"""Formato de cada entrega (SPEC §8 y SKILL.md «Formato de cada entrega»).

Siete puntos, siempre en el mismo orden. «Decisiones pendientes» aparece solo si hay alguna.
Cada material arma sus líneas y este módulo les da la forma común.
"""

PREGUNTA = "¿Apruebas este material para pasar a la siguiente etapa?"
TITULOS = {
    "archivos": "Archivos",
    "probe": "Qué probé",
    "valide": "Qué validé",
    "pendientes": "Decisiones pendientes",
    "no_pude": "Qué no pude probar",
    "decidi": "Qué decidí por mi cuenta",
}


def componer(*, archivos: list[str], probe: list[str], valide: list[str], pendientes: list[str],
             no_pude: list[str], decidi: list[str]) -> dict:
    partes = {"archivos": archivos, "probe": probe, "valide": valide, "pendientes": pendientes,
              "no_pude": no_pude, "decidi": decidi}
    secciones = [{"clave": clave, "titulo": TITULOS[clave], "lineas": list(lineas)}
                 for clave, lineas in partes.items() if lineas or clave != "pendientes"]
    return {"secciones": secciones, "pregunta": PREGUNTA}
