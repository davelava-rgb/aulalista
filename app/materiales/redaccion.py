"""Redacción de los materiales con una parte común por sesión (PLAN.md §0, decisión 74 b).

Cada redacción escribía de 30 000 a 39 000 tokens de caché y ninguna los leía: es una sola llamada por material.
Lo que no cambia entre los materiales de una sesión (las reglas comunes de la skill, las fichas, el tono, las
fuentes, la referencia, las páginas o los pasajes elegidos y la lectura aprobada) va ahora en el mensaje de sistema,
en un archivo igual para los cinco materiales, y el pedido lleva solo la sección de la skill del material, su formato
y su tarea. El SDK manda el esquema antes del mensaje de sistema (decisión 51), así que hay un solo esquema de
redacción con una parte por material, y la tarea `redaccion` pide caché de una hora: la segunda redacción de la
sesión lee la parte común en lugar de escribirla, si llega dentro de la hora.
"""

from pathlib import Path

from app import skill
from app.fichas import almacen, referencia, verificacion
from app.materiales import comun, estilo
from app.materiales.contenido import (ESQUEMA_ACTIVIDAD, ESQUEMA_DIAPOSITIVAS, ESQUEMA_EVALUACION, ESQUEMA_LABORATORIO,
                                      ESQUEMA_LECTURA, Lectura)

# Las secciones de la skill que todo redactor recibe; la de su material va en el pedido.
SECCIONES_COMUNES = ("Reglas comunes", "Paso 3 · Vocabulario de la sesión")

ESQUEMA_REDACCION = comun.esquema_de_correcciones(
    lectura=ESQUEMA_LECTURA, diapositivas=ESQUEMA_DIAPOSITIVAS, laboratorio=ESQUEMA_LABORATORIO,
    actividad=ESQUEMA_ACTIVIDAD, evaluacion=ESQUEMA_EVALUACION)
PARTES = tuple(ESQUEMA_REDACCION["properties"])

ARCHIVO_DE_SISTEMA = "sistema_redaccion.txt"


def ruta_del_sistema(carpeta_curso: Path, sesion: int) -> Path:
    """Un archivo por sesión, fuera de las carpetas de cada material: es el mismo para los cinco."""
    return almacen.carpeta_sesion(carpeta_curso, sesion) / "materiales" / comun.TRABAJO / ARCHIVO_DE_SISTEMA


def fuentes_de_la_sesion(carpeta_curso: Path, sesion: int) -> tuple[list[str] | None, list[str] | None]:
    """Las páginas de la referencia de la sesión (decisión 53) o, si no las hay, los pasajes que elige el programa
    (decisión 68 c). Los cinco redactores reciben lo mismo: así la parte común es la misma."""
    ficha = almacen.cargar(carpeta_curso, "sesion", sesion)
    paginas = referencia.paginas(carpeta_curso, ficha)
    pasajes = None if paginas else referencia.pasajes_elegidos(carpeta_curso, sesion, referencia.textos_de_la_sesion(ficha))
    return paginas, pasajes


def partes_de_la_lectura(contenido: Lectura) -> list[tuple[str, list[str]]]:
    """La lectura por partes, con su nombre: idea central, cada bloque, «Aplícalo así» y «Cuidado con»."""
    partes = [("Idea central", list(contenido.idea_central))]
    for b in contenido.bloques:
        filas = [" | ".join(f) for f in b.tabla.filas] if b.tabla else []
        tabla = ([b.tabla.titulo, " | ".join(b.tabla.encabezados)] if b.tabla else []) + filas
        partes.append((b.subtitulo, [*b.parrafos, b.ejemplo.titulo, *b.ejemplo.parrafos, *tabla]))
    partes.append(("Aplícalo así", [*contenido.aplicalo.parrafos, *contenido.aplicalo.plantilla]))
    partes.append(("Cuidado con", list(contenido.cuidado)))
    return partes


def texto_de_la_lectura(contenido: Lectura) -> str:
    lineas = []
    for nombre, textos in partes_de_la_lectura(contenido):
        lineas += [f"[{nombre}]", *[t for t in textos if t], ""]
    lineas.append("PASAJES DE LAS FUENTES QUE USÓ LA LECTURA (fuente · ubicación · texto):")
    lineas += [f"- {p.fuente} · {p.ubicacion} · {p.texto}" for p in contenido.pasajes] or ["- (ninguno)"]
    return "\n".join(lineas)


def lectura_aprobada(carpeta_curso: Path, sesion: int) -> Lectura | None:
    """La lectura aprobada de la sesión, si la sesión la produce y está aprobada con su contenido guardado."""
    from app.materiales import lectura  # aquí, para no importar en círculo

    ficha = almacen.cargar(carpeta_curso, "sesion", sesion)
    if lectura.CLAVE not in almacen.materiales_de_la_sesion(ficha):
        return None
    rutas = lectura.archivos(carpeta_curso, sesion)
    if lectura.estado(carpeta_curso, sesion).get("estado") != "aprobada" or not rutas["contenido"].exists():
        return None
    return Lectura.model_validate(comun.leer_json(rutas["contenido"]))


def sistema(carpeta_curso: Path, sesion: int, paginas: list[str] | None = None, pasajes: list[str] | None = None,
            con_lectura: bool = True) -> str:
    """La parte común de la redacción de la sesión. `con_lectura=False` la deja fuera: la lectura no recibe la
    lectura anterior cuando se genera de nuevo."""
    ficha = almacen.cargar(carpeta_curso, "sesion", sesion)
    fuentes = verificacion.fuentes_utilizables(carpeta_curso)
    tramos, excluir = referencia.interpretar(carpeta_curso, ficha)[0], referencia.exclusiones(ficha)
    partes = [
        "REGLAS COMUNES DE LA SKILL (son obligatorias; las reglas de tu material van en el pedido):",
        skill.secciones(*SECCIONES_COMUNES),
        "",
        "FICHA DEL CURSO (confirmada):", almacen.texto_para_materiales(carpeta_curso, "curso"),
        "FICHA DE LA SESIÓN (confirmada):", almacen.texto_para_materiales(carpeta_curso, "sesion", sesion),
        estilo.guia_de_tono(carpeta_curso),
        "FUENTES DEL CURSO que puedes citar (archivos .jsonl, un pasaje por línea con su ubicación):",
        *([f"- {f}" for f in fuentes] or ["- (ninguna: no cites fuentes)"]),
    ]
    if tramos:
        partes += ["", "MATERIAL DE REFERENCIA DE LA SESIÓN (en los .jsonl, cada pasaje trae su «pagina»):",
                   *[f"- {t.describir()}" for t in tramos],
                   "EXCLUSIONES (no las uses):",
                   *([f"- {e}" for e in excluir] or ["- Ninguna: usa todo el material de referencia."])]
    contenido = lectura_aprobada(carpeta_curso, sesion) if con_lectura else None
    if contenido is not None:
        partes += ["", "LECTURA APROBADA POR EL PROFESOR, parte por parte y en su orden. El pedido dice qué hacer con ella:",
                   texto_de_la_lectura(contenido)]
    partes += referencia.texto_de_paginas(paginas) if paginas else referencia.texto_de_pasajes(pasajes or [])
    return "\n".join(partes)


def reglas_del_material(secciones: tuple[str, ...]) -> str:
    """Las secciones de la skill propias del material, para el pedido. Las comunes ya están en el sistema."""
    propias = [s for s in secciones if s not in SECCIONES_COMUNES]
    return "REGLAS DE LA SKILL PARA ESTE MATERIAL (son obligatorias):\n" + skill.secciones(*propias)


DONDE_ESTAN_LAS_FUENTES = ("Las páginas o los pasajes de las fuentes están en tu contexto, ya copiados. Toma de ahí los que "
                           "uses, con su fuente y su ubicación tal cual. No tienes herramientas.")


async def redactar(parte: str, pedido: str, carpeta_curso: Path, numero: int, *, paginas: list[str] | None = None,
                   pasajes: list[str] | None = None, con_lectura: bool = True, **opciones) -> dict:
    """Pide la redacción de una parte del esquema único, con la parte común en el mensaje de sistema, y devuelve
    solo esa parte. `numero` es el de la sesión; `opciones` son las de `agente.consultar` (curso, sesion como «S1»,
    material, etapa, consulta…)."""
    if parte not in PARTES:
        raise ValueError(f"«{parte}» no es un material del esquema de redacción.")
    ruta = comun.escribir_sistema(ruta_del_sistema(carpeta_curso, numero),
                                  sistema(carpeta_curso, numero, paginas, pasajes, con_lectura))
    return await comun.consultar_parte(pedido, parte, ESQUEMA_REDACCION, tarea="redaccion", sistema=ruta, **opciones)
