"""Material 2 · Diapositivas: redacción desde la lectura aprobada, PowerPoint, validación en dos pasadas y entrega.

Flujo (el mismo de la lectura, PLAN.md §0, decisión 22):
1. Comprueba las dos fichas confirmadas y la lectura aprobada: las diapositivas salen de ella (SKILL.md, Paso 4).
2. El agente resume la lectura en diapositivas: mismo orden, mismos ejemplos, sin contenido nuevo.
3. El programa comprueba la estructura: de 14 a 18 diapositivas y el orden de los bloques de la lectura.
4. El generador crea el PowerPoint 16:9 con el diseño común y las notas del profesor.
5. Primera pasada: PowerPoint mide si algún texto se sale de su recuadro y guarda una imagen de cada diapositiva.
   El verificador revisa el texto, las notas y el número de diapositivas. Sus fallas se corrigen hasta
   VUELTAS_DEL_VERIFICADOR veces.
6. Segunda pasada: la revisión del contenido compara cada frase con la lectura aprobada y, si cita una fuente
   del curso, con esa fuente (SPEC §7). Una sola corrección y la confirmación de lo que cambió.
7. Entrega en el formato del SPEC §8. El profesor la aprueba desde la página.

Sin lectura en la sesión (PLAN.md §0, decisión 26), los pasos 1, 2, 3 y 6 cambian: las diapositivas salen del material
de referencia y de las fichas, el programa comprueba que las diapositivas de cada bloque vayan juntas y la revisión las
compara con las fuentes y las fichas, como a la lectura.
"""

import asyncio
import json
import re
import shutil
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from app import agente, entrega, office, skill, tokens
from app.fichas import almacen, verificacion
from app.materiales import comun, estilo, lectura
from app.materiales import pptx as generador
from app.materiales.contenido import ESQUEMA_DIAPOSITIVAS, Diapositivas, Lectura
from app.validacion import excel, pasada2, revision, revisor, verificador
from app.validacion.pasajes import Corpus, Fuente, normal

MATERIAL = "Diapositivas"
CLAVE = "diapositivas"
VUELTAS_DEL_VERIFICADOR = comun.VUELTAS_DEL_VERIFICADOR
FIJAS = 4                                   # portada, idea central, «Aplícalo así» y «Cuidado con»
LIMITES = verificador.LIMITES[MATERIAL]
FUENTE_LECTURA = "lectura aprobada"        # así se llama la lectura entre las fuentes de la revisión
SECCIONES_DE_LA_SKILL = ("Reglas comunes", "Paso 3 · Vocabulario de la sesión", "Material 2 · Diapositivas")
# «bloque» y «tipo» ordenan y dan forma a las diapositivas: una corrección por oraciones no los toca.
CAMPOS_QUE_NO_SE_CORRIGEN = comun.CAMPOS_QUE_NO_SE_CORRIGEN | {"bloque", "tipo"}
ESQUEMA_CORRECCION = comun.esquema_de_correccion(CLAVE, ESQUEMA_DIAPOSITIVAS)


class NoSePuedeEmpezar(RuntimeError):
    """Faltan las fichas confirmadas o la lectura aprobada."""


class NoSePuedeRevisar(RuntimeError):
    """El revisor independiente opcional necesita unas diapositivas generadas sin fallas abiertas."""


class NoSePuedeAprobar(RuntimeError):
    """Las diapositivas tienen fallas abiertas, están desactualizadas o no se generaron."""


def archivos(carpeta_curso: Path, sesion: int) -> dict[str, Path]:
    carpeta = lectura.carpeta_materiales(carpeta_curso, sesion)
    return {
        "pptx": carpeta / f"S{sesion}_Diapositivas.pptx",
        "excel": carpeta / f"S{sesion}_Diapositivas_Verificacion.xlsx",
        "entrega": carpeta / f"S{sesion}_Diapositivas_Entrega.md",
        "imagenes": carpeta / CLAVE / "imagenes",
        "revision": carpeta / CLAVE / "revisor",
        "contenido": carpeta / CLAVE / "contenido.json",
        "explicaciones": carpeta / CLAVE / "explicaciones.json",
    }


def _estado(carpeta_curso: Path, sesion: int) -> dict:
    return comun.estado(carpeta_curso, sesion, CLAVE)


def _actualizar(carpeta_curso: Path, sesion: int, **cambios) -> dict:
    return comun.actualizar(carpeta_curso, sesion, CLAVE, **cambios)


def _avance(carpeta_curso: Path, sesion: int, texto: str) -> None:
    comun.avance(carpeta_curso, sesion, CLAVE, texto)


def estado(carpeta_curso: Path, sesion: int) -> dict:
    """El estado guardado. Si la lectura se generó de nuevo después de estas diapositivas, quedan desactualizadas:
    cada material usa el anterior como fuente (SKILL.md, Paso 4)."""
    material = _estado(carpeta_curso, sesion)
    usada = material.get("lectura_fecha")
    if usada and usada != lectura.estado(carpeta_curso, sesion).get("fecha"):
        return {**material, "desactualizado": True}
    return material


def gasto_de_la_corrida(carpeta_curso: Path, curso: str, sesion: int) -> dict | None:
    return comun.gasto_de_la_corrida(carpeta_curso, curso, sesion, CLAVE)


def marcar_detenida(carpeta_curso: Path, sesion: int) -> bool:
    return comun.marcar_detenida(carpeta_curso, sesion, CLAVE)


def usa_lectura(carpeta_curso: Path, sesion: int) -> bool:
    """Si la sesión produce la lectura, las diapositivas salen de ella. Si no, de la referencia y de las fichas
    (PLAN.md §0, decisión 26)."""
    return lectura.CLAVE in almacen.materiales_de_la_sesion(almacen.cargar(carpeta_curso, "sesion", sesion))


def _lectura_lista(carpeta_curso: Path, sesion: int) -> list[str]:
    material = lectura.estado(carpeta_curso, sesion)
    if material.get("estado") != "aprobada":
        return ["Aprueba primero la lectura: las diapositivas salen de ella."]
    if material.get("desactualizado"):
        return ["La lectura está desactualizada: genérala y apruébala de nuevo."]
    if not lectura.archivos(carpeta_curso, sesion)["contenido"].exists():
        return ["No encuentro el contenido de la lectura aprobada. Genérala de nuevo."]
    return []


def faltan(carpeta_curso: Path, sesion: int) -> dict[str, list[str]]:
    """Lo que falta para generar las diapositivas: en «ficha», lo que se completa en la ficha de la sesión;
    en «otros», la lectura aprobada si la sesión la produce (SKILL.md, Paso 4, y PLAN.md §0, decisión 26)."""
    ficha = almacen.faltantes_para(carpeta_curso, sesion, CLAVE)
    otros = _lectura_lista(carpeta_curso, sesion) if not ficha and usa_lectura(carpeta_curso, sesion) else []
    return {"ficha": ficha, "otros": otros}


def lectura_aprobada(carpeta_curso: Path, sesion: int) -> Lectura:
    return Lectura.model_validate(comun.leer_json(lectura.archivos(carpeta_curso, sesion)["contenido"]))


# ---------- La lectura como fuente ----------

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


def fuente_de_la_lectura(contenido: Lectura) -> Fuente:
    """La lectura aprobada como una fuente más de la revisión: cada oración es un pasaje con su parte."""
    separar = verificador.verificar.separar_oraciones
    return Fuente(FUENTE_LECTURA, [{"texto": o, "ubicacion": nombre}
                                   for nombre, textos in partes_de_la_lectura(contenido)
                                   for t in textos if t for o in separar(t)])


def _texto_de_la_lectura(contenido: Lectura) -> str:
    lineas = []
    for nombre, textos in partes_de_la_lectura(contenido):
        lineas += [f"[{nombre}]", *[t for t in textos if t], ""]
    lineas.append("PASAJES DE LAS FUENTES QUE USÓ LA LECTURA (fuente · ubicación · texto):")
    lineas += [f"- {p.fuente} · {p.ubicacion} · {p.texto}" for p in contenido.pasajes] or ["- (ninguno)"]
    return "\n".join(lineas)


# ---------- Pedidos al agente ----------

def _contexto(carpeta_curso: Path, sesion: int, contenido_lectura: Lectura | None) -> str:
    ficha_curso = almacen.texto_para_materiales(carpeta_curso, "curso")
    ficha_sesion = almacen.ruta_ficha(carpeta_curso, "sesion", sesion, ".md").read_text(encoding="utf-8")
    fuentes = verificacion.fuentes_utilizables(carpeta_curso)
    partes = [
        "REGLAS DE LA SKILL (son obligatorias):",
        skill.secciones(*SECCIONES_DE_LA_SKILL),
        "",
        "FICHA DEL CURSO (confirmada):", ficha_curso,
        "FICHA DE LA SESIÓN (confirmada):", ficha_sesion,
        estilo.guia_de_tono(carpeta_curso),
    ]
    if contenido_lectura is not None:
        return "\n".join(partes + [
            "LECTURA APROBADA POR EL PROFESOR. Es la fuente de las diapositivas, parte por parte y en este orden:",
            _texto_de_la_lectura(contenido_lectura),
            "",
            "FUENTES DEL CURSO (archivos .jsonl de esta carpeta, un pasaje por línea con su ubicación). Úsalas solo para",
            "copiar el pasaje de una frase que cita una fuente:",
            *([f"- {f}" for f in fuentes] or ["- (ninguna)"]),
        ])
    tramos, excluir = lectura._referencia(carpeta_curso, sesion)
    referencia_ = [
        "", "MATERIAL DE REFERENCIA DE LA SESIÓN (en los .jsonl, cada pasaje trae su «pagina»):",
        *[f"- {t.describir()}" for t in tramos],
        "EXCLUSIONES (no las uses):",
        *([f"- {e}" for e in excluir] or ["- Ninguna: usa todo el material de referencia."]),
    ] if tramos else []
    return "\n".join(partes + [
        "ESTA SESIÓN NO TIENE LECTURA. Las diapositivas salen del material de referencia y de las fichas.",
        "FUENTES DEL CURSO que puedes citar (archivos .jsonl de esta carpeta, un pasaje por línea con su ubicación):",
        *([f"- {f}" for f in fuentes] or ["- (ninguna: no cites fuentes)"]),
        *referencia_,
    ])


FORMATO_COMUN = f"""
CÓMO ENTREGAR LAS DIAPOSITIVAS
- Devuelve solo los datos del esquema. Un programa crea el PowerPoint 16:9 con el diseño común: la portada con
  el curso y la sesión, los títulos «Idea central», «Aplícalo así» y «Cuidado con», los recuadros y las notas.
- En total van de {LIMITES['diapositivas_min']} a {LIMITES['diapositivas_max']} diapositivas. El programa pone {FIJAS} fijas
  (portada, idea central, «Aplícalo así» y «Cuidado con»), así que «diapositivas» trae de
  {LIMITES['diapositivas_min'] - FIJAS} a {LIMITES['diapositivas_max'] - FIJAS}.
{{orden}}
- tipo y lo que lleva cada uno (deja vacío lo que el tipo no usa y «tabla» en null si no es una tabla):
  - «frases»: de 1 a 5 frases cortas.
  - «pasos»: pasos numerados, uno por frase.
  - «columnas»: dos columnas comparativas, cada una con su título y sus frases.
  - «tabla»: una tabla de 4 columnas y 6 filas como máximo; en «frases», una línea de introducción o nada.
  - «ejemplo»: un ejemplo en un recuadro legible a distancia.
- Frases cortas, no párrafos: una idea por frase, que se lea de un vistazo.
{{contenido}}
- notas: en todas, también en la portada, la idea central, «Aplícalo así» y «Cuidado con». En «destacar», qué
  destacar; en «preguntar», qué preguntar al grupo. Las notas tampoco agregan contenido sin fuente.
{{cierre}}
- Sin diapositivas de relleno como «Preguntas» o «Gracias».
{{pasajes}}
- Usa los nombres del vocabulario de la sesión tal cual y en su orden. No uses sus variantes.
- Usa comillas solo para copiar texto tal cual de una fuente.
- Si una regla es propia del curso, escribe «en este curso».
"""

CON_LECTURA = {
    "orden": ("- diapositivas: una por concepto y una idea por diapositiva, en el orden de la lectura. En «bloque» copia\n"
              "  tal cual el subtítulo del bloque de la lectura al que pertenece. Cada bloque de la lectura tiene al menos\n"
              "  una diapositiva."),
    "contenido": ("- Los ejemplos son los mismos de la lectura. Si uno no cabe, divídelo en dos diapositivas o muestra una\n"
                  "  parte y remite a la lectura en las notas.\n"
                  "- No agregues contenido que la lectura no tenga. Las diapositivas resumen la lectura; no la amplían."),
    "cierre": ("- idea_central.frases: de 1 a 3 frases que resumen la idea central de la lectura.\n"
               "- aplicalo.plantilla: la técnica o plantilla de «Aplícalo así» de la lectura, una línea por elemento.\n"
               "  aplicalo.frases: de 0 a 2 frases de introducción.\n"
               "- cuidado.riesgos: los riesgos de «Cuidado con» de la lectura, de 1 a 3."),
    "pasajes": (f"- pasajes: para cada frase que dice algo del tema, «oracion» con la frase, «fuente» «{FUENTE_LECTURA}», en\n"
                "  «ubicacion» la parte de la lectura (por ejemplo, el subtítulo del bloque) y en «texto» la oración de la\n"
                "  lectura copiada tal cual. Si una frase cita una fuente del curso, agrega también el pasaje copiado de esa\n"
                "  fuente con su ubicación.\n"
                "- decisiones: una entrada por punto, con «texto» y «tipo»:\n"
                "  - «sin fuente»: afirmas algo del tema que la lectura no dice. Copia la frase. El profesor decide si queda.\n"
                "  - «decisión»: te apartas de la lectura en algo que cambia lo que ve el alumno: omites un tema, cambias el\n"
                "    orden o divides un ejemplo.\n"
                "  - «nota»: solo describes lo que hiciste sin apartarte de la lectura."),
}
SIN_LECTURA = {
    "orden": ("- diapositivas: una por concepto y una idea por diapositiva. Si la ficha de la sesión trae bloques de temas,\n"
              "  síguelos en su orden y escribe en «bloque» el nombre de cada uno. Si no, agrupa los temas del material de\n"
              "  referencia en bloques, en el orden de la referencia, y dales un nombre corto. Las diapositivas de un mismo\n"
              "  bloque van juntas."),
    "contenido": ("- Cubre los temas del material de referencia, menos las exclusiones, o los temas de la ficha si no hay\n"
                  "  referencia. Usa el ejemplo y el caso de las fichas. Si un ejemplo no cabe, divídelo en dos diapositivas.\n"
                  "- Para afirmar algo de una fuente, apóyate en su pasaje: di lo mismo, con sus palabras o con otras más claras."),
    "cierre": ("- idea_central.frases: de 1 a 3 frases con la idea central de la sesión.\n"
               "- aplicalo.plantilla: el contenido de «Aplícalo así» de la ficha de la sesión, como técnica o plantilla lista\n"
               "  para usar, una línea por elemento. aplicalo.frases: de 0 a 2 frases de introducción.\n"
               "- cuidado.riesgos: los riesgos de «Cuidado con» de la ficha de la sesión, de 1 a 3."),
    "pasajes": ("- pasajes: los pasajes de las fuentes que usaste, para que la revisión los compare: «oracion» de las\n"
                "  diapositivas que sostiene, la fuente, la ubicación y en «texto» el pasaje copiado de la fuente, de 40\n"
                "  palabras como máximo.\n"
                "- decisiones: una entrada por punto, con «texto» y «tipo»:\n"
                "  - «sin fuente»: afirmas algo del tema que no está en ninguna fuente ni ficha. Copia la frase.\n"
                "  - «decisión»: te apartas de las fichas o de las fuentes, o eliges algo que cambia lo que ve el alumno.\n"
                "  - «nota»: solo describes lo que hiciste sin apartarte de las fichas ni de las fuentes."),
}


def instrucciones_de_formato(con_lectura: bool) -> str:
    return FORMATO_COMUN.format(**(CON_LECTURA if con_lectura else SIN_LECTURA))


REGLAS_PROPIAS_CON_LECTURA = """EN LAS DIAPOSITIVAS
- La fuente de las diapositivas es la lectura aprobada. Si una frase dice algo que la lectura no dice, elimínala o
  reescríbela con lo que dice la lectura.
- Las diapositivas no agregan datos del caso: deja «datos_nuevos» vacío.
- Un texto que no cabe en su recuadro (FALLA · desborde) se arregla con frases más cortas, con menos frases o
  dividiendo la diapositiva en dos, sin pasar del total de diapositivas.
"""
REGLAS_PROPIAS_SIN_LECTURA = """EN LAS DIAPOSITIVAS
- Esta sesión no tiene lectura: las diapositivas salen del material de referencia y de las fichas.
- Un texto que no cabe en su recuadro (FALLA · desborde) se arregla con frases más cortas, con menos frases o
  dividiendo la diapositiva en dos, sin pasar del total de diapositivas.
"""


def pedido_de_redaccion(carpeta_curso: Path, sesion: int, contenido_lectura: Lectura | None) -> str:
    if contenido_lectura is not None:
        tarea = ["TAREA: prepara las diapositivas de la sesión a partir de la lectura aprobada. Actúa como diseñador",
                 "instruccional y diseñador de materiales. Resume cada parte de la lectura en frases cortas, en su orden."]
    else:
        tarea = ["TAREA: prepara las diapositivas de la sesión a partir del material de referencia y de las fichas.",
                 "Actúa como diseñador instruccional y diseñador de materiales.",
                 "Antes de redactar, busca con Grep en las fuentes y lee con Read los pasajes que vas a usar.",
                 "Si la sesión tiene material de referencia, lee sus páginas y no uses las exclusiones.",
                 "No afirmes sobre el contenido de una fuente nada que no esté en un pasaje copiado."]
    return "\n".join([
        _contexto(carpeta_curso, sesion, contenido_lectura),
        instrucciones_de_formato(contenido_lectura is not None),
        *tarea,
        "Antes de entregar, revisa cada diapositiva: qué puede hacer el alumno con ella y qué frase tiene dos lecturas.",
    ])


def _pedido_con_problemas(carpeta_curso, sesion, contenido_lectura, datos, problemas, como_entregar) -> str:
    con_lectura = contenido_lectura is not None
    return "\n".join([
        _contexto(carpeta_curso, sesion, contenido_lectura),
        instrucciones_de_formato(con_lectura),
        comun.REGLAS_DE_CORRECCION,
        REGLAS_PROPIAS_CON_LECTURA if con_lectura else REGLAS_PROPIAS_SIN_LECTURA,
        *como_entregar,
        "",
        "DIAPOSITIVAS ACTUALES:",
        json.dumps(datos, ensure_ascii=False),
        "",
        "PROBLEMAS QUE ENCONTRÓ LA VALIDACIÓN:",
        *[f"- {p}" for p in problemas],
    ])


def pedido_de_cambios(carpeta_curso, sesion, contenido_lectura, datos: dict, problemas: list[str]) -> str:
    """Corrección barata: devuelve solo las frases que cambian."""
    return _pedido_con_problemas(carpeta_curso, sesion, contenido_lectura, datos, problemas, [
        "CÓMO ENTREGAR LA CORRECCIÓN",
        "- En «cambios», una entrada por frase que cambias: «oracion» copiada tal cual de las diapositivas y «nueva»",
        "  con el texto nuevo. Para eliminar una frase, deja «nueva» vacío. No devuelvas las frases que no cambian.",
    ])


def pedido_de_correccion(carpeta_curso, sesion, contenido_lectura, datos: dict, problemas: list[str]) -> str:
    """Corrección completa: para problemas de estructura, de cantidad o de espacio, que no son de una frase."""
    return _pedido_con_problemas(carpeta_curso, sesion, contenido_lectura, datos, problemas,
                                 ["Devuelve las diapositivas completas con el mismo esquema."])


# ---------- Estructura: cantidad y orden ----------

def _clave_de_bloque(texto: str) -> str:
    return re.sub(r"[^\w ]", "", normal(texto)).strip()


def _validar(datos: dict, contenido_lectura: Lectura | None) -> tuple[Diapositivas | None, list[str]]:
    """Cantidad de diapositivas y orden: el de los bloques de la lectura o, sin lectura, cada bloque junto."""
    try:
        contenido = Diapositivas.model_validate(datos)
    except ValidationError as error:
        return None, [f"FALLA · estructura · {'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()]
    problemas = []
    minimo, maximo = LIMITES["diapositivas_min"], LIMITES["diapositivas_max"]
    if not minimo <= contenido.total <= maximo:
        problemas.append(f"FALLA · estructura · diapositivas: hay {contenido.total} con las {FIJAS} fijas; "
                         f"deben ser de {minimo} a {maximo}.")
    if contenido_lectura is None:
        problemas += _bloques_juntos(contenido)
    else:
        problemas += _orden_de_la_lectura(contenido, contenido_lectura)
    return (None if problemas else contenido), problemas


def _bloques_juntos(contenido: Diapositivas) -> list[str]:
    """Sin lectura (decisión 26): las diapositivas de un bloque no se separan."""
    problemas, vistos, actual = [], set(), None
    for numero, d in enumerate(contenido.diapositivas, start=3):
        clave = _clave_de_bloque(d.bloque)
        if clave != actual and clave in vistos:
            problemas.append(f"FALLA · estructura · diapositiva {numero} («{d.titulo}»): las diapositivas del bloque "
                             f"«{d.bloque}» no van juntas.")
        vistos.add(clave)
        actual = clave
    return problemas


def _orden_de_la_lectura(contenido: Diapositivas, contenido_lectura: Lectura) -> list[str]:
    problemas = []
    orden = [_clave_de_bloque(b.subtitulo) for b in contenido_lectura.bloques]
    anterior = 0
    for numero, d in enumerate(contenido.diapositivas, start=3):
        clave = _clave_de_bloque(d.bloque)
        if clave not in orden:
            problemas.append(f"FALLA · estructura · diapositiva {numero} («{d.titulo}»): su bloque «{d.bloque}» no es un "
                             "bloque de la lectura. Copia el subtítulo tal cual.")
            continue
        posicion = orden.index(clave)
        if posicion < anterior:
            problemas.append(f"FALLA · estructura · diapositiva {numero} («{d.titulo}»): no sigue el orden de la lectura.")
        anterior = max(anterior, posicion)
    usados = {_clave_de_bloque(d.bloque) for d in contenido.diapositivas}
    for b in contenido_lectura.bloques:
        if _clave_de_bloque(b.subtitulo) not in usados:
            problemas.append(f"FALLA · estructura · el bloque «{b.subtitulo}» de la lectura no tiene diapositivas.")
    return problemas


def titulos(contenido: Diapositivas) -> list[str]:
    """El título de cada diapositiva, en orden (la portada lleva el nombre «Portada»)."""
    return ["Portada", "Idea central", *[d.titulo for d in contenido.diapositivas], "Aplícalo así", "Cuidado con"]


def desbordes_como_hallazgos(medicion: office.Medicion, contenido: Diapositivas, nombre: str) -> list:
    """Cada texto que no cabe es una FALLA del documento: se arregla con una corrección completa."""
    nombres = titulos(contenido)
    hallazgos = []
    for d in medicion.desbordes:
        titulo = nombres[d.diapositiva - 1] if d.diapositiva <= len(nombres) else ""
        que = "La tabla se sale de la diapositiva" if d.es_tabla else f"El texto «{d.texto[:80]}» no cabe en su recuadro"
        hallazgos.append(verificador.verificar.Hallazgo(
            nivel="FALLA", seccion=f"{nombre} · diapositiva {d.diapositiva}", oracion="", regla="desborde",
            detalle=f"Diapositiva {d.diapositiva} («{titulo}»): {que}; sobran {d.sobra_cm:.1f} cm. Medido con PowerPoint."))
    return hallazgos


# ---------- Generación ----------

class _Trabajo:
    """Lo que se acumula mientras se generan las diapositivas."""

    def __init__(self, carpeta_curso, curso, sesion, rutas, consulta, medir):
        self.carpeta_curso, self.curso, self.sesion, self.rutas = carpeta_curso, curso, sesion, rutas
        self.consulta = consulta
        self._medir = medir or office.medir_diapositivas
        self.carpeta_sesion = almacen.carpeta_sesion(carpeta_curso, sesion)
        self.identidad = estilo.desde_ficha(carpeta_curso)
        self.portada = replace(lectura._portada(carpeta_curso, sesion), material=MATERIAL)
        # Sin lectura en la sesión, la base son el material de referencia y las fichas (decisión 26).
        self.lectura = lectura_aprobada(carpeta_curso, sesion) if usa_lectura(carpeta_curso, sesion) else None
        self.datos_agregados: list[str] = []
        self.comun = {"curso": curso, "sesion": f"S{sesion}", "material": CLAVE, "cwd": carpeta_curso / "fuentes_texto",
                      "herramientas": ("Read", "Grep", "Glob"), "consulta": consulta}
        self.datos: dict = {}
        self.contenido: Diapositivas | None = None
        self.explicaciones: dict[str, str] = {}
        self.historial: list[dict] = []
        self.correcciones = {"verificador": 0, "revisión": 0}
        self.resultado = None
        self.medicion: office.Medicion | None = None
        self.fallas: list[str] = []
        self.descartados: list[dict] = []
        self.vuelta = 0

    def avance(self, texto: str) -> None:
        _avance(self.carpeta_curso, self.sesion, texto)

    def corpus(self) -> Corpus:
        extras = [fuente_de_la_lectura(self.lectura)] if self.lectura is not None else []
        return Corpus.del_curso(self.carpeta_curso, self.sesion, extras=extras)

    async def verificar(self) -> bool:
        """Genera el PowerPoint, lo mide y corre el verificador. Corrige sus fallas hasta VUELTAS_DEL_VERIFICADOR
        veces. Devuelve True si quedó sin fallas ni avisos por explicar."""
        for intento in range(VUELTAS_DEL_VERIFICADOR + 1):
            self.vuelta += 1
            contenido, problemas = _validar(self.datos, self.lectura)
            completa = bool(problemas)
            comun.guardar_json(self.rutas["contenido"], self.datos)
            if contenido is not None:
                self.contenido = contenido
                generador.generar_diapositivas(contenido, self.identidad, self.portada, self.rutas["pptx"])
                self.medicion = self._medir(self.rutas["pptx"], self.rutas["imagenes"])
                configuracion = verificador.configuracion_del_material(self.carpeta_sesion, MATERIAL)
                self.resultado = verificador.ejecutar(
                    configuracion, [self.rutas["pptx"]], self.rutas["excel"], self.explicaciones,
                    hallazgos_extra=desbordes_como_hallazgos(self.medicion, contenido, self.rutas["pptx"].name))
                if comun.explicar_literales(self.resultado, self.explicaciones, self.corpus()):
                    comun.guardar_json(self.rutas["explicaciones"], self.explicaciones)
                    verificador.anotar_explicaciones(self.rutas["excel"], self.explicaciones)
                excel.anotar_reglas(self.rutas["excel"], comun.AVISOS_INFORMATIVOS, comun.NOTA_INFORMATIVA)
                fallas, avisos = comun.hallazgos_abiertos(self.resultado, self.explicaciones)
                self.avance(f"Verificador y medición con PowerPoint, vuelta {self.vuelta}: {self.resultado.resumen()}.")
                problemas = [comun.texto_de(h) for h in fallas + avisos]
                completa = any(not h.oracion for h in fallas)   # cantidad, notas y desbordes: del documento entero
                self.historial += comun.historial(fallas + avisos, self.vuelta)
            self.fallas = problemas
            if not problemas:
                return True
            if intento == VUELTAS_DEL_VERIFICADOR:
                self.avance(f"Quedan {len(problemas)} fallas después de {VUELTAS_DEL_VERIFICADOR} correcciones. "
                            "No se pueden aprobar las diapositivas con fallas.")
                return False
            self.correcciones["verificador"] += len(problemas)
            await self.corregir(problemas, completa)
        return False

    async def revisar(self, bloques: list[pasada2.Bloque], etapa: str) -> revision.Resultado:
        resultado = await revision.ejecutar(
            bloques, corpus=self.corpus(), anclas=[p.model_dump() for p in self.contenido.pasajes],
            curso=self.curso, sesion=self.sesion, material=CLAVE, nombre_material=MATERIAL, etapa=etapa,
            indicaciones=INDICACIONES_DE_REVISION if self.lectura is not None else INDICACIONES_SIN_LECTURA,
            consulta=self.consulta)
        self.descartados += resultado.descartados
        return resultado

    async def corregir(self, problemas: list[str], completa: bool) -> None:
        vuelta = self.vuelta
        if completa:
            self.avance(f"Corrigiendo las diapositivas completas: {comun.cuantos(len(problemas), 'problema')}.")
            respuesta = await agente.consultar(
                pedido_de_correccion(self.carpeta_curso, self.sesion, self.lectura, self.datos, problemas),
                tarea="correccion", esquema=ESQUEMA_CORRECCION, etapa=f"corrección completa {vuelta}", **self.comun)
            self.datos = respuesta[CLAVE]
        else:
            self.avance(f"Corrigiendo {comun.cuantos(len(problemas), 'problema')}.")
            respuesta = await agente.consultar(
                pedido_de_cambios(self.carpeta_curso, self.sesion, self.lectura, self.datos, problemas),
                tarea="correccion_oraciones", esquema=comun.ESQUEMA_CAMBIOS, etapa=f"corrección {vuelta}", **self.comun)
            self.datos, no_encontradas = comun.aplicar_cambios(self.datos, respuesta["cambios"], CAMPOS_QUE_NO_SE_CORRIGEN)
            if no_encontradas:
                self.avance(f"{comun.cuantos(len(no_encontradas), 'frase')} a cambiar no se encontraron.")
        for e in respuesta["explicaciones"]:
            self.explicaciones[verificador.clave_de_hallazgo(e["regla"], e["oracion"])] = e["explicacion"]
        comun.guardar_json(self.rutas["explicaciones"], self.explicaciones)
        if respuesta.get("datos_nuevos") and self.lectura is not None:
            self.avance("La corrección propuso datos nuevos del caso. No se agregan: las diapositivas salen de la lectura.")
        elif respuesta.get("datos_nuevos"):
            # Sin lectura, las diapositivas son el primer material: un dato del caso que falta va a la ficha del curso.
            nuevos = almacen.agregar_datos_fijos(self.carpeta_curso, respuesta["datos_nuevos"], f"Diapositivas S{self.sesion}")
            if nuevos:
                self.datos_agregados += nuevos
                for numero in almacen.sesiones_confirmadas(self.carpeta_curso):
                    verificacion.escribir(self.carpeta_curso, numero)
                self.avance(f"Datos nuevos del caso agregados a la ficha del curso: {len(nuevos)}.")


INDICACIONES_DE_REVISION = (
    f"La fuente de este material es la lectura aprobada (en los pasajes, «{FUENTE_LECTURA}»). Las diapositivas la "
    "resumen en frases cortas: resumir o decir lo mismo con otras palabras no es un error. Es «dato inventado» una "
    "afirmación sobre el tema que la lectura no dice, aunque esté en otra fuente del curso: las diapositivas no "
    "agregan contenido. Una frase que cita una fuente del curso se compara también con esa fuente. Las notas del "
    "profesor («Qué destacar», «Qué preguntar al grupo») se revisan igual; una pregunta al grupo no es una afirmación.")


INDICACIONES_SIN_LECTURA = (
    "Esta sesión no tiene lectura: las diapositivas salen del material de referencia y de las fichas. Una frase corta "
    "que resume una fuente no es un error. Las notas del profesor («Qué destacar», «Qué preguntar al grupo») se revisan "
    "igual; una pregunta al grupo no es una afirmación.")


def bloques_de(contenido: Diapositivas) -> list[pasada2.Bloque]:
    """Las diapositivas por bloque de la lectura, con sus notas: la revisión trabaja bloque por bloque."""
    separar = verificador.verificar.separar_oraciones

    def oraciones(*textos):
        return [o for t in textos if t for o in separar(t)]

    def notas(n):
        return (f"Qué destacar: {n.destacar}", f"Qué preguntar al grupo: {n.preguntar}")

    bloques = [pasada2.Bloque("Portada e idea central", oraciones(
        *notas(contenido.portada.notas), *contenido.idea_central.frases, *notas(contenido.idea_central.notas)))]
    por_bloque: dict[str, list[str]] = {}
    for d in contenido.diapositivas:
        textos = [d.titulo, *d.frases]
        for c in d.columnas:
            textos += [c.titulo, *c.frases]
        if d.tabla:
            textos += [" | ".join(f) for f in d.tabla.filas]
        por_bloque.setdefault(d.bloque, []).extend(oraciones(*textos, *notas(d.notas)))
    bloques += [pasada2.Bloque(f"Diapositivas de «{nombre}»", lista) for nombre, lista in por_bloque.items()]
    a, c = contenido.aplicalo, contenido.cuidado
    bloques.append(pasada2.Bloque("Aplícalo así", oraciones(*a.frases, *a.plantilla, *notas(a.notas))))
    bloques.append(pasada2.Bloque("Cuidado con", oraciones(*c.riesgos, *notas(c.notas))))
    return bloques


def _limpiar(rutas: dict[str, Path]) -> None:
    """Borra lo que dejó la generación anterior. Un archivo abierto en PowerPoint puede negar el borrado:
    se deja y la generación lo reescribe."""
    for ruta in (rutas["pptx"], rutas["excel"], rutas["excel"].with_suffix(".json"), rutas["entrega"],
                 rutas["contenido"], rutas["explicaciones"]):
        try:
            ruta.unlink(missing_ok=True)
        except OSError:
            pass
    shutil.rmtree(rutas["revision"], ignore_errors=True)
    shutil.rmtree(rutas["imagenes"], ignore_errors=True)


async def generar(carpeta_curso: Path, curso: str, sesion: int, consulta=agente.query, medir=None) -> dict:
    """`medir` reemplaza a PowerPoint en las pruebas: recibe el .pptx y la carpeta de imágenes."""
    pendiente = faltan(carpeta_curso, sesion)
    if pendiente["ficha"] or pendiente["otros"]:
        raise NoSePuedeEmpezar("No se pueden generar las diapositivas. "
                               + " ".join(pendiente["ficha"] + pendiente["otros"]))
    rutas = archivos(carpeta_curso, sesion)
    rutas["contenido"].parent.mkdir(parents=True, exist_ok=True)
    _actualizar(carpeta_curso, sesion, estado="trabajando", previo="", avance=[], error="", desactualizado=False,
                entrega={}, aprobada="", revisor={}, corrida_desde=tokens.lineas(curso),
                lectura_fecha=lectura.estado(carpeta_curso, sesion).get("fecha", "") if usa_lectura(carpeta_curso, sesion) else "")
    try:
        return await _generar(carpeta_curso, curso, sesion, rutas, consulta, medir)
    except asyncio.CancelledError:
        marcar_detenida(carpeta_curso, sesion)
        raise
    except Exception as error:
        _actualizar(carpeta_curso, sesion, estado="error", error=str(error))
        raise


async def _generar(carpeta_curso, curso, sesion, rutas, consulta, medir) -> dict:
    inicio = tokens.lineas(curso)
    # Antes de gastar tokens: la skill tiene todo lo que se usará y la configuración del verificador se lee.
    skill.comprobar(secciones=SECCIONES_DE_LA_SKILL + pasada2.SECCIONES_DE_LA_SKILL + revisor.SECCIONES_DE_LA_SKILL,
                    subsecciones=revisor.SUBSECCIONES_DE_LA_SKILL)
    trabajo = _Trabajo(carpeta_curso, curso, sesion, rutas, consulta, medir)
    verificador.verificar.leer_configuracion(verificador.configuracion_del_material(trabajo.carpeta_sesion, MATERIAL))
    _limpiar(rutas)

    trabajo.avance("Leyendo la lectura aprobada y preparando las diapositivas.")
    trabajo.datos = await agente.consultar(pedido_de_redaccion(carpeta_curso, sesion, trabajo.lectura), tarea="redaccion",
                                           esquema=ESQUEMA_DIAPOSITIVAS, etapa="redacción", **trabajo.comun)

    errores: list[revision.Error] = []
    revisados = 0
    if await trabajo.verificar():
        errores, revisados = await comun.revisar_y_corregir(trabajo, bloques_de)

    pendientes = [e for e in errores if e.estado == "pendiente"]
    final = trabajo.contenido
    decisiones = final.decisiones if final else []
    sin_fuente = [f"Afirmación sin fuente: {d.texto}" for d in decisiones if d.tipo == "sin fuente"]
    estado_final = "con fallas" if trabajo.fallas else ("con pendientes" if pendientes or sin_fuente else "verificada")
    if trabajo.resultado is not None:
        excel.solo_hallazgos(rutas["excel"])
        excel.agregar_historial(rutas["excel"], [
            {**h, "resolucion": f"Enviado a corrección en la vuelta {h['vuelta']}." + ("" if trabajo.fallas else " Resuelto.")}
            for h in trabajo.historial] + comun.filas_de_revision(errores, trabajo.descartados, rutas["pptx"].name)
            + comun.filas_de_decisiones(decisiones, rutas["pptx"].name))
    hallazgos = trabajo.resultado.hallazgos if trabajo.resultado else []
    medicion = trabajo.medicion
    material = _actualizar(
        carpeta_curso, sesion,
        estado=estado_final,
        resumen=trabajo.resultado.resumen() if trabajo.resultado else "",
        problemas=trabajo.fallas + [e.describir() for e in pendientes] + sin_fuente,
        correcciones=trabajo.correcciones,
        revision={"bloques": revisados, "errores": len(errores), "corregidos": sum(e.estado == "corregido" for e in errores),
                  "pendientes": len(pendientes), "descartados": len(trabajo.descartados)},
        avisos_de_diseno=trabajo.identidad.avisos,
        avisos_explicados=sum(1 for h in hallazgos if h.nivel == "AVISO" and h.regla not in comun.AVISOS_INFORMATIVOS),
        avisos_informativos=sum(1 for h in hallazgos if h.nivel == "AVISO" and h.regla in comun.AVISOS_INFORMATIVOS),
        diapositivas=final.total if final else 0,
        medidas=medicion.diapositivas if medicion else 0,
        desbordes=len(medicion.desbordes) if medicion else 0,
        imagenes=len(medicion.imagenes) if medicion else 0,
        decisiones=[d.model_dump() for d in decisiones],
        base="lectura" if trabajo.lectura is not None else "fuentes",
        referencia=[t.describir() for t in lectura._referencia(carpeta_curso, sesion)[0]] if trabajo.lectura is None else [],
        datos_agregados=trabajo.datos_agregados,
        archivos={"pptx": rutas["pptx"].name, "excel": rutas["excel"].name, "entrega": rutas["entrega"].name},
        carpeta_imagenes=str(rutas["imagenes"].relative_to(carpeta_curso)),
        costo=tokens.total(curso, sesion=f"S{sesion}", material=CLAVE, desde_linea=inicio),
        fecha=datetime.now().isoformat(timespec="seconds"),
    )
    _escribir_entrega(carpeta_curso, sesion, material)
    trabajo.avance({"verificada": "Diapositivas listas para tu aprobación.",
                    "con pendientes": f"Diapositivas listas, con {comun.cuantos(len(pendientes) + len(sin_fuente), 'pendiente')} "
                                      "para que decidas.",
                    "con fallas": "Las diapositivas quedaron con fallas."}[estado_final])
    return estado(carpeta_curso, sesion)


# ---------- Revisor independiente opcional (PLAN.md §0, decisión 22) ----------

async def revisar_con_revisor(carpeta_curso: Path, curso: str, sesion: int, consulta=agente.query) -> dict:
    """Una sesión nueva de Opus revisa las diapositivas ya generadas. No corrige: lo que encuentra queda como
    pendiente para que el profesor decida."""
    material = _estado(carpeta_curso, sesion)
    previo = material.get("estado")
    if previo not in ("verificada", "con pendientes", "aprobada"):
        raise NoSePuedeRevisar("El revisor independiente revisa unas diapositivas generadas y sin fallas.")
    rutas = archivos(carpeta_curso, sesion)
    contenido = Diapositivas.model_validate(comun.leer_json(rutas["contenido"]))
    oraciones = comun.leer_json(rutas["excel"].with_suffix(".json"))["oraciones"]
    inicio = tokens.lineas(curso)
    _actualizar(carpeta_curso, sesion, estado="trabajando", previo=previo)
    _avance(carpeta_curso, sesion, "Revisor independiente: una sesión nueva lee las diapositivas, las fuentes y las fichas.")
    try:
        resultado = await revisor.ejecutar(
            oraciones, ronda=1, carpeta=rutas["revision"] / "ronda_1", carpeta_curso=carpeta_curso, curso=curso,
            sesion=sesion, material=CLAVE, nombre_material=MATERIAL, bloques=bloques_de(contenido), consulta=consulta)
    except asyncio.CancelledError:
        marcar_detenida(carpeta_curso, sesion)
        raise
    except Exception as error:
        _avance(carpeta_curso, sesion, f"El revisor independiente se detuvo por un error: {error}")
        _actualizar(carpeta_curso, sesion, estado=previo, previo="")
        raise
    hallazgos = resultado.hallazgos
    excel.agregar_historial(rutas["excel"], [
        {"nivel": "REVISOR", "seccion": rutas["pptx"].name, "oracion": h.oracion, "regla": f"revisor independiente: {h.defecto}",
         "detalle": f"{h.explicacion} Prueba: «{h.prueba}» ({h.fuente}).", "resolucion": "Pendiente: decides tú."}
        for h in hallazgos] + [
        {"nivel": "REVISOR", "seccion": rutas["pptx"].name, "oracion": "", "regla": "revisor independiente: lista de verificación",
         "detalle": f"{p['pregunta']} {p['detalle']}", "resolucion": "Informativo."} for p in resultado.lista_no])
    material = _actualizar(
        carpeta_curso, sesion, estado="con pendientes" if hallazgos else previo, previo="",
        aprobada="" if hallazgos else material.get("aprobada", ""),
        problemas=material.get("problemas", []) + [h.describir() for h in hallazgos],
        revisor={"hallazgos": len(hallazgos), "descartados": len(resultado.descartados), "lista": len(resultado.lista_no),
                 "costo": tokens.total(curso, sesion=f"S{sesion}", material=CLAVE, desde_linea=inicio)})
    _escribir_entrega(carpeta_curso, sesion, material)
    _avance(carpeta_curso, sesion, f"Revisor independiente: {comun.cuantos(len(hallazgos), 'hallazgo')} con prueba"
            + (", pendientes para que decidas." if hallazgos else "."))
    return estado(carpeta_curso, sesion)


# ---------- Entrega (SPEC §8 y SKILL.md «Formato de cada entrega») ----------

def _escribir_entrega(carpeta_curso: Path, sesion: int, material: dict) -> dict:
    material = _actualizar(carpeta_curso, sesion, entrega=_entrega(material))
    archivos(carpeta_curso, sesion)["entrega"].write_text(
        entrega.a_markdown(material["entrega"], f"Entrega · {MATERIAL} · Sesión {sesion}"), encoding="utf-8")
    return material


def _entrega(material: dict) -> dict:
    archivos_ = material["archivos"]
    total = material.get("diapositivas") or 0
    lineas_archivos = [
        f"{archivos_['pptx']}: las diapositivas, 16:9" + (f", {total} diapositivas" if total else "")
        + ", con notas del profesor en cada una.",
        f"{archivos_['excel']}: el archivo de verificación, con la hoja Hallazgos.",
        f"{archivos_['entrega']}: esta entrega, en texto.",
    ]
    probe = []
    if material.get("medidas"):
        probe.append(f"Medí con PowerPoint cada texto de las {material['medidas']} diapositivas: "
                     + ("ninguno se sale de su recuadro." if not material.get("desbordes")
                        else f"{comun.cuantos(material['desbordes'], 'texto')} no caben. Están en la hoja Hallazgos."))
    if material.get("imagenes"):
        probe.append(f"Guardé una imagen de cada diapositiva en la carpeta {material['carpeta_imagenes']}.")
    probe.append("Las diapositivas no tienen ejercicios ni archivos de práctica que ejecutar.")
    c = material["correcciones"]
    r = material.get("revision") or {}
    valide = [f"Verificador: {material['resumen']}." if material["resumen"] else "El verificador no llegó a correr.",
              *([f"Avisos explicados en la hoja Hallazgos: {material['avisos_explicados']}."]
                if material.get("avisos_explicados") else []),
              *([f"Avisos informativos de relleno o palabras imprecisas: {material['avisos_informativos']}. "
                 "Están en la hoja Hallazgos; no obligan a corregir."] if material.get("avisos_informativos") else []),
              f"Fallas del verificador y de la medición corregidas: {c['verificador']}."]
    if r.get("bloques"):
        contra = "la lectura aprobada" if material.get("base", "lectura") == "lectura" else "las fuentes y las fichas"
        texto = (f"Revisión del contenido contra {contra}: {comun.cuantos(r['bloques'], 'bloque')}, "
                 f"{comun.cuantos(r['errores'], 'error')} con prueba")
        if r["errores"]:
            texto += f" ({comun.cuantos(r['corregidos'], 'corregido')} y {comun.cuantos(r['pendientes'], 'pendiente')})"
        valide.append(texto + ".")
        if r.get("descartados"):
            valide.append(f"El programa descartó {comun.cuantos(r['descartados'], 'error')} de la revisión porque su "
                          "prueba no existe.")
    rev = material.get("revisor") or {}
    if rev:
        valide.append(f"Revisor independiente (lo pediste tú): {comun.cuantos(rev['hallazgos'], 'hallazgo')} con prueba"
                      + (f", {rev['descartados']} descartados" if rev.get("descartados") else "")
                      + f". Costo: {rev['costo']['costo_usd']:.2f} USD estimados.")
    costo = material["costo"]
    valide.append(f"Costo de estas diapositivas: {costo['llamadas']} llamadas, {costo['costo_usd']:.2f} USD estimados.")

    no_pude = []
    if not r.get("bloques"):
        no_pude.append("La revisión del contenido no corrió porque quedaron fallas.")
    if not material.get("medidas"):
        no_pude.append("No pude medir las diapositivas con PowerPoint.")
    if not no_pude:
        no_pude.append("Nada: las diapositivas no tienen ejercicios que ejecutar.")

    decidi = []
    if material.get("base") == "fuentes":
        origen = "; ".join(material.get("referencia") or []) or "los temas de la ficha de la sesión"
        decidi.append(f"La sesión no tiene lectura: las diapositivas salen de {origen} y de las fichas "
                      "(PLAN.md §0, decisión 26).")
    decidi += [d["texto"] for d in material["decisiones"] if d["tipo"] == "decisión"]
    decidi += [f"Dato nuevo del caso, agregado a la ficha del curso: {d}" for d in material.get("datos_agregados", [])]
    if not decidi:
        decidi.append("Nada que revisar: todo salió de la lectura aprobada. Las notas del redactor están en "
                      "la hoja Hallazgos.")
    return entrega.componer(archivos=lineas_archivos, probe=probe, valide=valide,
                            pendientes=material["problemas"], no_pude=no_pude, decidi=decidi)


def aprobar(carpeta_curso: Path, sesion: int) -> dict:
    """El profesor aprueba las diapositivas desde la página. Con pendientes de la revisión también se pueden
    aprobar: el profesor ya los vio. Las fallas no."""
    material = estado(carpeta_curso, sesion)
    if material.get("estado") not in ("verificada", "con pendientes"):
        raise NoSePuedeAprobar("Solo se aprueban unas diapositivas generadas y sin fallas.")
    if material.get("desactualizado"):
        raise NoSePuedeAprobar("La lectura o las fichas cambiaron después de generar las diapositivas. Genéralas de nuevo.")
    return _actualizar(carpeta_curso, sesion, estado="aprobada", aprobada=datetime.now().isoformat(timespec="seconds"))
