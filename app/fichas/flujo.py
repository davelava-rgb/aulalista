"""Pasos 1 y 2 del flujo (SPEC §5): proponer las fichas desde las fuentes y confirmarlas.

Reglas de la skill (Paso 1 y Paso 2):
- Cada dato lleva anotado el archivo del que salió.
- Un dato deducido se marca «(propuesto)». Un dato ausente se marca «Falta definir».
- Si dos archivos se contradicen, se muestran las dos versiones y se pregunta cuál vale.
- Cada ejercicio se revisa con tres preguntas antes de confirmar la ficha de la sesión.
"""

import hashlib
import json
import re
import unicodedata
from pathlib import Path

from app import agente
from app.fichas import almacen, controles, plantillas, verificacion
from app.fuentes import convertir

ESQUEMA_PROPUESTA = {
    "type": "object",
    "properties": {
        "campos": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"}, "valor": {"type": "string"},
                "origen": {"type": "string"}, "literal": {"type": "boolean"},
            },
            "required": ["id", "valor", "origen", "literal"], "additionalProperties": False,
        }},
        "conflictos": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "id": {"type": "string"},
                "versiones": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"valor": {"type": "string"}, "origen": {"type": "string"}},
                    "required": ["valor", "origen"], "additionalProperties": False,
                }},
            },
            "required": ["id", "versiones"], "additionalProperties": False,
        }},
    },
    "required": ["campos", "conflictos"],
    "additionalProperties": False,
}

_REVISION_DE_UNO = {
    "type": "object",
    "properties": {
        "numero": {"type": "integer"},
        "funciona_solo": {"type": "boolean"},
        "sin_llenar_a_mano": {"type": "boolean"},
        "motivo": {"type": "string"},
    },
    "required": ["numero", "funciona_solo", "sin_llenar_a_mano", "motivo"], "additionalProperties": False,
}
ESQUEMA_REVISION = {
    "type": "object",
    # «preguntas»: las de la evaluación, revisadas con los ejercicios (decisión 64 h). Vacía si no hay.
    "properties": {"ejercicios": {"type": "array", "items": _REVISION_DE_UNO},
                   "preguntas": {"type": "array", "items": _REVISION_DE_UNO}},
    "required": ["ejercicios", "preguntas"],
    "additionalProperties": False,
}


class FichaDelCursoSinConfirmar(ValueError):
    """La ficha de la sesión necesita la ficha del curso confirmada (SPEC §5, pasos 1 y 2)."""


# ---------- Propuesta desde las fuentes ----------

def _normal(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return " ".join("".join(c for c in descompuesto if unicodedata.category(c) != "Mn").split())


def _dice_literal(carpeta_curso: Path, archivo: str, texto: str) -> bool:
    """Comprueba con un programa que la fuente dice el dato tal cual."""
    fuente = _normal(" ".join(p["texto"] for p in convertir.leer_pasajes(carpeta_curso, archivo)))
    renglones = [_normal(r) for r in texto.splitlines() if r.strip()]
    return bool(renglones) and all(r in fuente for r in renglones)


# Campos que la propuesta no llena: la identidad visual, que AulaLista resuelve con su paleta, y los modelos de
# diseño, que elige el profesor. El docente y el contacto son datos de personas reales: solo se toman si la fuente
# los dice tal cual; nunca se proponen.
NO_SE_PROPONEN = ("visual.", "modelos.", "sesion.exclusiones")   # las exclusiones las decide el profesor (decisión 23)
SOLO_TAL_CUAL = ("portada.", "curso.horas", "curso.numero_sesiones")   # las horas y las sesiones las da el profesor


def campos_vacios(ficha: dict) -> list[tuple[str, str]]:
    vacios = []
    for campo, _ in plantillas.campos_de(ficha["tipo"]):
        if campo.id.startswith(NO_SE_PROPONEN):
            continue
        dato = ficha["campos"].get(campo.id) or {}
        if not dato.get("valor") and dato.get("estado") != almacen.CONFLICTO:
            vacios.append((campo.id, campo.etiqueta))
    return vacios


def _opciones_del_control(campo_id: str) -> str:
    """Las opciones del control de la página, para que el valor propuesto se pueda elegir (decisión 27)."""
    control = controles.CONTROLES.get(campo_id)
    if not control or control["tipo"] not in ("lista", "opciones", "casillas"):
        return ""
    opciones = [o[0] if isinstance(o, tuple) else o for o in control["opciones"]]
    forma = "una de estas, tal cual" if control["tipo"] != "casillas" else "las que correspondan, separadas por comas"
    otra = " (o escribe otra si ninguna sirve)" if control.get("otro") else ""
    return f" [usa {forma}: {', '.join(opciones)}{otra}]"


# Los ejercicios salen del tema de la sesión; la herramienta, del tema del curso (PLAN.md §0, decisión 36).
_SIN_PREGUNTA = "Deja vacío «Si la herramienta debe preguntar algo»: no hay una herramienta que pregunte."
DE_QUE_TRATAN_LOS_EJERCICIOS = {
    frozenset(): "Cada ejercicio practica el tema de la sesión: el alumno hace la acción a mano en su archivo de "
                 "práctica, en Excel o Word, sin fórmulas ni prompts. " + _SIN_PREGUNTA,
    frozenset({"excel"}): "Cada ejercicio practica el tema de la sesión en Excel: puede usar fórmulas, nunca prompts. "
                          + _SIN_PREGUNTA,
    frozenset({"ia"}): "Cada ejercicio practica el tema de la sesión con un asistente de IA: puede usar prompts, nunca "
                       "fórmulas.",
    frozenset({"excel", "ia"}): "Cada ejercicio practica el tema de la sesión con Excel o con un asistente de IA: "
                                "puede usar fórmulas y prompts.",
}


def pedido_de_propuesta(carpeta_curso: Path, tipo: str, sesion: int | None, ficha: dict) -> str:
    fuentes = verificacion.fuentes_utilizables(carpeta_curso)
    lineas = [
        f"Vas a llenar la {'ficha del curso' if tipo == 'curso' else f'ficha de la sesión {sesion}'}.",
        "Trabajas solo con los archivos .jsonl de esta carpeta. Cada uno es una fuente del curso convertida "
        "a texto: una línea por pasaje, con su texto y su ubicación.",
        "Fuentes que puedes usar (el nombre del .jsonl es el nombre de la fuente más «.jsonl»):",
        *[f"- {f}" for f in fuentes],
        "Busca con Grep y lee con Read. Lo que dice la fuente se toma de la fuente, no de tu memoria.",
        "",
        "Campos vacíos que debes intentar llenar (id: etiqueta):",
        *[f"- {campo_id}: {etiqueta}" + _opciones_del_control(campo_id) for campo_id, etiqueta in campos_vacios(ficha)],
        "",
        "Reglas:",
        "- Por cada dato devuelve id, valor, origen y literal. El origen es el nombre exacto de la fuente.",
        "- literal = true solo si la fuente dice el dato con esas mismas palabras. Si lo deduces, literal = false.",
        "- Si dos fuentes dicen cosas distintas sobre el mismo dato, no elijas: devuélvelo en «conflictos» con las dos versiones.",
        "- Propón todos los campos de la lista, aunque la fuente no los diga (PLAN.md §0, decisión 17). El profesor",
        "  solo revisa y confirma. Lo que deduces o propones va con literal = false. AulaLista lo marca como",
        "  propuesto: no escribas «(propuesto)» ni otra marca dentro del valor.",
        "- Deduce del contenido de la fuente lo que se pueda: las sesiones (una por capítulo o tema principal, en el",
        "  orden de la fuente), el público y lo que ya sabe, el idioma, los temas y el vocabulario.",
        "- Los datos del caso son ficticios: propón una empresa o institución ficticia que encaje con el tema, sus",
        "  áreas, la moneda y el país, la fecha de referencia y las cifras fijas, coherentes entre sí.",
        "- No inventes hechos del mundo real: ni cifras reales, ni estudios, ni personas reales. El docente y los",
        "  datos de contacto solo van si la fuente los dice tal cual; si no, no los devuelvas.",
        "- En los campos de varias líneas, escribe un elemento por línea.",
        "- Escribe en el idioma del curso, en oraciones cortas y claras.",
    ]
    if tipo == "curso":
        lineas += [
            "- En «Sesiones» escribe una línea por sesión que empiece con su número: «1. Título: alcance».",
            "- En «Herramienta de los ejercicios» decide por el tema del curso (PLAN.md §0, decisión 36): «Excel» solo si",
            "  el curso enseña Excel, «IA» solo si enseña a usar IA, «Excel e IA» si enseña los dos y «ninguna» en los",
            "  demás casos. Los modelos de diseño no cuentan: guían el formato, no la herramienta.",
        ]
    else:
        ficha_curso = almacen.ruta_ficha(carpeta_curso, "curso", extension=".md").read_text(encoding="utf-8")
        herramienta = almacen.herramienta_de_los_ejercicios(carpeta_curso)
        sesiones = {s["numero"]: s["texto"] for s in almacen.sesiones_del_curso(almacen.cargar(carpeta_curso, "curso"))}
        lineas += [
            "- Puedes proponer temas, bloques, ejercicios, problemas sembrados, estaciones y preguntas que "
            "encajen con el alcance de la sesión y con el caso del curso. Todo lo que propongas va con literal = false.",
            "- Cada ejercicio funciona solo, tiene su archivo de práctica y su problema sembrado, y trae todo lo que "
            "el alumno necesita. Usa de 3 a 5 ejercicios y de 5 a 7 estaciones, una por línea.",
            "- " + DE_QUE_TRATAN_LOS_EJERCICIOS[herramienta],
            "- Los archivos de práctica y de la evaluación son Excel para datos y Word para textos. "
            "PDF solo si el caso lo exige. Nunca .txt.",
            "- La evaluación tiene 3 preguntas, salvo que la ficha diga otra cantidad. Cada pregunta "
            "usa archivos y datos nuevos, y no repite un ejercicio del laboratorio.",
            "- En «Material de referencia» escribe, por cada fuente que cubre el alcance de la sesión, "
            "«archivo: páginas X a Y». Usa el campo «pagina» de cada pasaje (la página del PDF), no el número impreso. "
            "Las exclusiones las decide el profesor (PLAN.md §0, decisión 23).",
            "- En el vocabulario escribe un concepto por línea con su nombre único, en el orden en que la fuente los "
            "presenta. Si conviene, agrega «(no usar: variante 1, variante 2)». No pongas como variante un término "
            "que la fuente usa (PLAN.md §0, decisión 31).",
            "- Los temas, los bloques y los pasos van en el orden de la fuente.",
            "- En «Temas de sesiones posteriores que no se deben adelantar» escribe los temas que no se desarrollan. "
            "La lectura puede nombrarlos en pocas oraciones si hace falta para entender la sesión.",
            "- Los datos del caso son ficticios y cuadran con los datos fijos de la ficha del curso.",
            "",
            f"Sesión {sesion}: {sesiones.get(sesion, '')}",
            "Ficha del curso confirmada:",
            ficha_curso,
        ]
    return "\n".join(lineas)


def aplicar_propuesta(carpeta_curso: Path, ficha: dict, propuesta: dict) -> dict:
    """Llena solo los campos vacíos. Comprueba con un programa cada dato que la IA dice literal."""
    validos = almacen.ids_validos(ficha["tipo"])
    permitidas = set(verificacion.fuentes_utilizables(carpeta_curso))
    resumen = {"de_las_fuentes": 0, "propuestos": 0, "conflictos": 0, "descartados": 0}

    def vacio(campo_id):
        dato = ficha["campos"].get(campo_id) or {}
        return not dato.get("valor") and dato.get("estado") != almacen.CONFLICTO

    for dato in propuesta.get("campos", []):
        campo_id, texto = dato["id"], almacen.sin_marcas(dato["valor"])
        origen = dato["origen"].removesuffix(".jsonl").strip()
        if campo_id not in validos or campo_id.startswith(NO_SE_PROPONEN) or not texto or not vacio(campo_id):
            resumen["descartados"] += 1
            continue
        if origen in permitidas and dato["literal"] and _dice_literal(carpeta_curso, origen, texto):
            ficha["campos"][campo_id] = {"valor": texto, "origen": origen, "estado": ""}
            resumen["de_las_fuentes"] += 1
        elif campo_id.startswith(SOLO_TAL_CUAL):
            resumen["descartados"] += 1     # una persona real no se propone
        else:
            ficha["campos"][campo_id] = {
                "valor": texto, "origen": origen if origen in permitidas else "deducido", "estado": almacen.PROPUESTO,
            }
            resumen["propuestos"] += 1

    for conflicto in propuesta.get("conflictos", []):
        versiones = [
            {"valor": almacen.sin_marcas(v["valor"]), "origen": v["origen"].removesuffix(".jsonl").strip()}
            for v in conflicto["versiones"]
            if almacen.sin_marcas(v["valor"]) and v["origen"].removesuffix(".jsonl").strip() in permitidas
        ]
        distintas = {v["valor"] for v in versiones}
        if conflicto["id"] in validos and vacio(conflicto["id"]) and len(distintas) >= 2:
            ficha["campos"][conflicto["id"]] = {"valor": "", "origen": "", "estado": almacen.CONFLICTO, "versiones": versiones}
            resumen["conflictos"] += 1
        else:
            resumen["descartados"] += 1

    almacen.marcar_faltantes(ficha)
    ficha["confirmada"] = False
    return resumen


async def proponer(carpeta_curso: Path, curso: str, tipo: str, sesion: int | None = None, consulta=agente.query) -> dict:
    if tipo == "sesion" and not almacen.cargar(carpeta_curso, "curso")["confirmada"]:
        raise FichaDelCursoSinConfirmar("Guarda primero la ficha del curso completa: así queda confirmada.")
    ficha = almacen.cargar(carpeta_curso, tipo, sesion)
    if not verificacion.fuentes_utilizables(carpeta_curso) and tipo == "curso":
        almacen.marcar_faltantes(ficha)
        almacen.guardar(carpeta_curso, tipo, sesion, ficha, "sin fuentes")
        return {"de_las_fuentes": 0, "propuestos": 0, "conflictos": 0, "descartados": 0, "sin_fuentes": True}
    (carpeta_curso / "fuentes_texto").mkdir(parents=True, exist_ok=True)
    propuesta = await agente.consultar(
        pedido_de_propuesta(carpeta_curso, tipo, sesion, ficha),
        tarea="fichas", esquema=ESQUEMA_PROPUESTA, curso=curso, etapa=f"propuesta ficha {tipo}",
        sesion=f"S{sesion}" if sesion else "-", cwd=carpeta_curso / "fuentes_texto",
        herramientas=("Read", "Grep", "Glob"), consulta=consulta,
    )
    resumen = aplicar_propuesta(carpeta_curso, ficha, propuesta)
    almacen.guardar(carpeta_curso, tipo, sesion, ficha, "propuesta desde las fuentes")
    return resumen


# ---------- Completar secciones de la ficha del curso (PLAN.md §0, decisión 28) ----------

_CURSO = ("curso.nombre", "curso.idioma", "curso.horas", "curso.numero_sesiones")
_PUBLICO = ("publico.quienes", "publico.saben", "publico.valoran")
_CASO = ("caso.empresa", "caso.areas", "caso.moneda")

# Cada botón «Completar» llena los campos vacíos de su sección con lo que ya dicen las secciones anteriores.
# «Repartir las sesiones» reemplaza lo que haya y un programa calcula qué parte de las fuentes cubre (decisión 53).
COMPLETAR = {
    "sesiones": {
        "seccion": "1. Curso", "boton": "Repartir las sesiones", "destino": ("curso.sesiones",),
        "usa": _CURSO + _PUBLICO, "exige": ("curso.nombre", "curso.horas", "curso.numero_sesiones"),
        "ayuda": "Reparte el contenido de las fuentes en el número de sesiones, según las horas y el público "
                 "(sección 2). Reemplaza lo que haya en «Sesiones» y calcula qué parte de las páginas de las "
                 "fuentes cubre.",
    },
    "caso": {
        "seccion": "3. Caso del curso", "boton": "Completar el caso", "destino": _CASO,
        "usa": _CURSO + ("curso.sesiones",) + _PUBLICO, "exige": ("curso.nombre",),
        "ayuda": "Propone una empresa o institución ficticia que encaje con el curso y el público. Llena solo lo vacío.",
    },
    "datos": {
        "seccion": "4. Datos fijos del caso", "boton": "Completar los datos fijos", "destino": ("datos.fecha", "datos.fijos"),
        "usa": _CURSO + ("curso.sesiones",) + _PUBLICO + _CASO, "exige": ("curso.nombre", "caso.empresa"),
        "ayuda": "Propone la fecha de referencia y las cifras, reglas y nombres del caso. Llena solo lo vacío.",
    },
}

ESQUEMA_COMPLETAR = {
    "type": "object",
    "properties": {"campos": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"}, "valor": {"type": "string"}},
        "required": ["id", "valor"], "additionalProperties": False,
    }}},
    "required": ["campos"],
    "additionalProperties": False,
}

_TIEMPOS = re.compile(r"\b(horas?|minutos?|segundos?|hrs?)\b", re.I)


def _etiquetas() -> dict[str, str]:
    return {c.id: c.nombre for c, _ in plantillas.campos_de("curso")}


def pedido_de_completar(ficha: dict, clave: str) -> str:
    datos = COMPLETAR[clave]
    etiquetas = _etiquetas()
    vacios = [c for c in datos["destino"] if not almacen.valor(ficha, c).strip()]
    lineas = [
        "Vas a completar una parte de la ficha de un curso. Lo que ya está escrito lo decidió el profesor.",
        "",
        "Lo que ya dice la ficha:",
        *[f"- {etiquetas[c]}: {almacen.valor(ficha, c).strip()}" for c in datos["usa"] if almacen.valor(ficha, c).strip()],
        "",
        "Campos que debes llenar (id: etiqueta):",
        *[f"- {c}: {etiquetas[c]}" for c in vacios],
        "",
        "Reglas:",
        "- Devuelve un dato por campo, con su id y su valor. No devuelvas otros campos.",
        "- Lo que propones encaja con todo lo que ya dice la ficha y no lo contradice.",
        "- No inventes hechos del mundo real: ni cifras reales, ni estudios, ni personas reales, ni funciones de herramientas.",
        "- No escribas horas, minutos ni ningún otro tiempo: ningún material muestra tiempos.",
        "- Escribe en el idioma del curso, en oraciones cortas y claras, sin jerga ni lenguaje publicitario.",
        "- En los campos de varias líneas, escribe un elemento por línea.",
    ]
    if clave == "caso":
        lineas += [
            "- El caso es ficticio: una empresa o institución que no existe, con su rubro, que encaja con el tema y el público.",
            "- Las áreas son de 3 a 5, en una sola línea, separadas por comas. Entre ellas rotan los ejemplos.",
            "- La moneda y el país van juntos, por ejemplo «Dólares estadounidenses (USD), El Salvador».",
        ]
    else:
        lineas += [
            "- La fecha de referencia es una fecha ficticia, con día, mes y año.",
            "- En las cifras, reglas y nombres escribe de 5 a 8 líneas con la forma «Etiqueta: valor».",
            "- Cada dato es ficticio y coherente con la empresa, sus áreas, su moneda y su país.",
            "- Los nombres de personas son ficticios y no se parecen a los de personas reales conocidas.",
        ]
    return "\n".join(lineas)


async def completar(carpeta_curso: Path, curso: str, clave: str, consulta=agente.query) -> str:
    """Llena los campos vacíos de una sección de la ficha del curso. Devuelve el mensaje para la página."""
    datos = COMPLETAR[clave]
    ficha = almacen.cargar(carpeta_curso, "curso")
    etiquetas = _etiquetas()
    faltan = [etiquetas[c] for c in datos["exige"] if not almacen.valor(ficha, c).strip()]
    if faltan:
        return f"Para {datos['boton'][:1].lower()}{datos['boton'][1:]}, llena primero " + \
            " y ".join(f"«{f}»" for f in faltan) + "."
    if clave == "sesiones":
        return await repartir(carpeta_curso, curso, ficha, consulta)
    vacios = [c for c in datos["destino"] if not almacen.valor(ficha, c).strip()]
    if not vacios:
        return "Esa parte ya está llena. Borra lo que quieras cambiar y pulsa otra vez «Completar»."
    respuesta = await agente.consultar(
        pedido_de_completar(ficha, clave), tarea="completar_ficha", esquema=ESQUEMA_COMPLETAR,
        curso=curso, etapa=f"completar ficha: {clave}", consulta=consulta,
    )
    llenados = []
    for dato in respuesta.get("campos", []):
        texto = almacen.sin_marcas(dato["valor"])
        if dato["id"] in vacios and texto and dato["id"] not in llenados:
            ficha["campos"][dato["id"]] = {"valor": texto, "origen": "deducido", "estado": almacen.PROPUESTO}
            llenados.append(dato["id"])
    if not llenados:
        return "La propuesta llegó vacía. No cambié nada."
    ficha["confirmada"] = False
    almacen.guardar(carpeta_curso, "curso", None, ficha, f"completada {clave}")
    nombres = ", ".join(f"«{etiquetas[c]}»" for c in llenados)
    return " ".join([f"Propuse {nombres}. Revisa lo marcado «Propuesto» y guarda.", *_avisos_de_completar(ficha, clave)])


# ---------- Repartir las sesiones y su cobertura (PLAN.md §0, decisión 53) ----------

ESQUEMA_REPARTIR = {
    "type": "object",
    "properties": {"sesiones": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "numero": {"type": "integer"}, "titulo": {"type": "string"}, "alcance": {"type": "string"},
            "paginas": {"type": "array", "items": {
                "type": "object",
                "properties": {"fuente": {"type": "string"}, "desde": {"type": "integer"}, "hasta": {"type": "integer"}},
                "required": ["fuente", "desde", "hasta"], "additionalProperties": False,
            }},
        },
        "required": ["numero", "titulo", "alcance", "paginas"], "additionalProperties": False,
    }}},
    "required": ["sesiones"],
    "additionalProperties": False,
}


def paginas_de_las_fuentes(carpeta_curso: Path, fuentes: list[str]) -> dict[str, list[int]]:
    """Las páginas del PDF que tienen texto, por fuente. Una fuente sin páginas (Word, PowerPoint) no se cuenta."""
    return {f: sorted({p["pagina"] for p in convertir.leer_pasajes(carpeta_curso, f) if p.get("pagina")})
            for f in fuentes}


def _horas_por_sesion(ficha: dict) -> str:
    horas, numero = almacen.valor(ficha, "curso.horas").strip(), almacen.valor(ficha, "curso.numero_sesiones").strip()
    try:
        cada = float(horas.replace(",", ".")) / int(numero)
    except (ValueError, ZeroDivisionError):
        return ""
    return f"{cada:g}".replace(".", ",")


def pedido_de_repartir(ficha: dict, paginas: dict[str, list[int]]) -> str:
    etiquetas = _etiquetas()
    numero = almacen.valor(ficha, "curso.numero_sesiones").strip()
    cada = _horas_por_sesion(ficha)
    lineas = [
        "Vas a repartir el tema de un curso en sesiones. Lo que ya está escrito lo decidió el profesor.",
        "",
        "Lo que ya dice la ficha:",
        *[f"- {etiquetas[c]}: {almacen.valor(ficha, c).strip()}" for c in COMPLETAR["sesiones"]["usa"]
          if almacen.valor(ficha, c).strip()],
        *([f"- Horas de cada sesión: {cada}"] if cada else []),
        "",
        "Reglas:",
        f"- Devuelve exactamente {numero} sesiones, numeradas de 1 a {numero}.",
        "- Cada sesión tiene un título corto y un alcance: qué temas cubre, en una o dos oraciones.",
        "- Usa las horas solo para medir cuánto cabe en cada sesión. No escribas horas, minutos ni ningún otro "
        "tiempo: ningún material muestra tiempos.",
        "- Ajusta el nivel a lo que el público ya sabe y a lo que valora.",
        "- No inventes hechos del mundo real: ni cifras reales, ni estudios, ni personas reales, ni funciones de herramientas.",
        "- Escribe en el idioma del curso, en oraciones cortas y claras, sin jerga ni lenguaje publicitario.",
        "- No escribas el número de la sesión dentro del título.",
    ]
    con_paginas = {f: p for f, p in paginas.items() if p}
    if paginas:
        lineas += [
            "- Las fuentes del curso son los archivos .jsonl de esta carpeta: una línea por pasaje, con su texto y su "
            "campo «pagina» (la página del PDF). Busca con Grep y lee con Read. Fuentes:",
            *[f"  - {f}" + (f" (páginas {p[0]} a {p[-1]})" if p else "") for f, p in paginas.items()],
            "- Cubre todo el contenido de las fuentes si cabe en las horas de cada sesión. Si no cabe, elige los temas "
            "más importantes y deja fuera lo secundario: anexos, ejemplos que se repiten, bibliografía, créditos.",
            "- Sigue los capítulos y el orden de las fuentes.",
        ]
    if con_paginas:
        lineas += [
            "- En «paginas» escribe los tramos de cada fuente que cubre la sesión: el nombre de la fuente copiado tal "
            "cual de la lista de arriba, la primera y la última página. Usa el campo «pagina» de los pasajes, no el "
            "número impreso. Para saber en qué página está un tema, búscalo con Grep y mira su campo «pagina».",
            "- Cada sesión trae al menos un tramo. Un mismo tramo no va en dos sesiones. Lo que dejas fuera no va en "
            "ningún tramo.",
        ]
    else:
        lineas.append("- Deja «paginas» vacío.")
    return "\n".join(lineas)


def _huella_sesiones(texto: str) -> str:
    return hashlib.sha256(" ".join(texto.split()).encode("utf-8")).hexdigest()


def _tramos(paginas: list[int]) -> str:
    """[1, 2, 3, 7, 9, 10] → «1 a 3, 7, 9 y 10»."""
    tramos = []
    for p in paginas:
        if tramos and p == tramos[-1][1] + 1:
            tramos[-1][1] = p
        else:
            tramos.append([p, p])
    partes = []
    for a, b in tramos:
        partes += [str(a)] if a == b else [str(a), str(b)] if b == a + 1 else [f"{a} a {b}"]
    return " y ".join([", ".join(partes[:-1]), partes[-1]]) if len(partes) > 1 else "".join(partes)


def _comparable(nombre: str) -> str:
    return " ".join(nombre.lower().removesuffix(".jsonl").split())


def _fuente_de(nombre: str, fuentes) -> str | None:
    """La fuente del curso que nombra la IA, sin importar mayúsculas, espacios, «.jsonl» ni la extensión."""
    buscado = _comparable(nombre)
    for fuente in fuentes:
        if buscado in (_comparable(fuente), _comparable(Path(fuente).stem)):
            return fuente
    return None


def cobertura(sesiones: list[dict], paginas: dict[str, list[int]], texto: str,
              sin_revisar: dict[str, list[int]] | None = None) -> dict:
    """Qué parte de las páginas de las fuentes cubren las sesiones. Lo calcula un programa, no la IA: solo cuentan
    los tramos de fuentes del curso y las páginas que existen en ellas. Una fuente que el profesor todavía no
    revisó cuenta en el total, pero ninguna sesión puede usarla: su texto lo leyó la IA y nadie lo confirmó."""
    cubiertas = {f: set() for f in paginas}
    por_sesion, descartados = {}, []
    for s in sesiones:
        tramos = []
        for tramo in s["paginas"]:
            fuente = _fuente_de(tramo["fuente"], paginas)
            desde, hasta = sorted((tramo["desde"], tramo["hasta"]))
            dentro = {p for p in paginas.get(fuente, []) if desde <= p <= hasta}
            if dentro:
                cubiertas[fuente] |= dentro
                tramos.append(f"{fuente}: páginas {_tramos(sorted(dentro))}")
            elif fuente is None:
                descartados.append(f"Sesión {s['numero']}: «{tramo['fuente']}» no es una fuente del curso.")
            else:
                descartados.append(f"Sesión {s['numero']}: {fuente} no tiene las páginas {desde} a {hasta}.")
        por_sesion[str(s["numero"])] = tramos
    fuentes = [{"fuente": f, "cubiertas": len(cubiertas[f]), "total": len(p), "sin_revisar": False,
                "fuera": _tramos(sorted(set(p) - cubiertas[f]))} for f, p in paginas.items() if p]
    fuentes += [{"fuente": f, "cubiertas": 0, "total": len(p), "sin_revisar": True, "fuera": _tramos(p)}
                for f, p in (sin_revisar or {}).items() if p]
    total = sum(f["total"] for f in fuentes)
    cubiertas_total = sum(f["cubiertas"] for f in fuentes)
    return {"huella": _huella_sesiones(texto), "porcentaje": round(100 * cubiertas_total / total) if total else 0,
            "cubiertas": cubiertas_total, "total": total, "fuentes": fuentes, "sesiones": por_sesion,
            "descartados": descartados}


def fuentes_sin_revisar(carpeta_curso: Path) -> list[str]:
    """Fuentes convertidas que no se pueden usar: la IA leyó parte de su texto y el profesor no lo revisó."""
    usables = set(verificacion.fuentes_utilizables(carpeta_curso))
    return [f for f, e in convertir.leer_indice(carpeta_curso).items()
            if e["estado"] == convertir.CONVERTIDA and f not in usables]


def cobertura_vigente(ficha: dict) -> dict | None:
    """La cobertura guardada y si todavía vale: deja de valer si el profesor cambió las sesiones después."""
    guardada = ficha.get("cobertura_sesiones")
    if not guardada:
        return None
    return {**guardada, "vigente": guardada["huella"] == _huella_sesiones(almacen.valor(ficha, "curso.sesiones"))}


async def repartir(carpeta_curso: Path, curso: str, ficha: dict, consulta=agente.query) -> str:
    """Reparte el contenido de las fuentes en las sesiones. Reemplaza lo que haya en «Sesiones»."""
    fuentes = verificacion.fuentes_utilizables(carpeta_curso)
    paginas = paginas_de_las_fuentes(carpeta_curso, fuentes)
    sin_revisar = paginas_de_las_fuentes(carpeta_curso, fuentes_sin_revisar(carpeta_curso))
    opciones = {}
    if fuentes:
        (carpeta_curso / "fuentes_texto").mkdir(parents=True, exist_ok=True)
        opciones = {"cwd": carpeta_curso / "fuentes_texto", "herramientas": ("Read", "Grep", "Glob")}
    respuesta = await agente.consultar(
        pedido_de_repartir(ficha, paginas), tarea="completar_ficha", esquema=ESQUEMA_REPARTIR,
        curso=curso, etapa="completar ficha: sesiones", consulta=consulta, **opciones,
    )
    sesiones = sorted(respuesta.get("sesiones", []), key=lambda s: s["numero"])
    lineas = []
    for s in sesiones:
        titulo, alcance = almacen.sin_marcas(s["titulo"]).strip(" .:"), almacen.sin_marcas(s["alcance"]).strip()
        if titulo:
            lineas.append(f"{s['numero']}. {titulo}: {alcance}" if alcance else f"{s['numero']}. {titulo}")
    if not lineas:
        return "La propuesta llegó vacía. No cambié nada."
    texto = "\n".join(lineas)
    ficha["campos"]["curso.sesiones"] = {"valor": texto, "origen": "deducido", "estado": almacen.PROPUESTO}
    if any(paginas.values()) or any(sin_revisar.values()):
        ficha["cobertura_sesiones"] = cobertura(sesiones, paginas, texto, sin_revisar)
    else:
        ficha.pop("cobertura_sesiones", None)
    ficha["confirmada"] = False
    almacen.guardar(carpeta_curso, "curso", None, ficha, "sesiones repartidas")
    resumen = [f"Repartí el contenido en {len(lineas)} sesiones."]
    if "cobertura_sesiones" in ficha:
        c = ficha["cobertura_sesiones"]
        resumen.append(f"Cubren el {c['porcentaje']} % de las páginas de las fuentes ({c['cubiertas']} de {c['total']}).")
        resumen += [f"Ojo: la sesión {n} no trae páginas de las fuentes." for n, t in c["sesiones"].items()
                    if not t and any(paginas.values())]
        if any(sin_revisar.values()):
            resumen.append("Ojo: " + _y([f"«{f}»" for f, p in sin_revisar.items() if p]) +
                           " no se usó porque falta revisar el texto que leyó la IA.")
    elif fuentes:
        resumen.append("Las fuentes no tienen páginas: no se calculó la cobertura.")
    else:
        resumen.append("Sin fuentes convertidas no se calcula la cobertura.")
    return " ".join([*resumen, "Revisa lo marcado «Propuesto» y guarda.", *_avisos_de_completar(ficha, "sesiones")])


def _y(partes: list[str]) -> str:
    return " y ".join([", ".join(partes[:-1]), partes[-1]]) if len(partes) > 1 else "".join(partes)


# ---------- La ficha corta de la sesión (PLAN.md §0, decisión 54) ----------

DESDE_EL_CURSO = "ficha del curso"


def datos_desde_el_curso(ficha_curso: dict, sesion: int) -> dict[str, str]:
    """Lo que la ficha de la sesión toma de la del curso, sin IA: número y título, alcance, lo ya visto, lo que no se
    adelanta y, si la cobertura de «Repartir las sesiones» sigue valiendo, las páginas de referencia."""
    sesiones = almacen.sesiones_del_curso(ficha_curso)
    titulos = {s["numero"]: s["texto"].partition(":")[0].strip(" .") for s in sesiones}
    actual = next((s for s in sesiones if s["numero"] == sesion), None)
    if actual is None:
        return {}
    titulo, separador, alcance = actual["texto"].partition(":")
    datos = {
        "sesion.numero_titulo": f"{sesion}. {titulo.strip(' .')}",
        "sesion.alcance": (alcance if separador else actual["texto"]).strip(),
        "sesion.ya_vieron": "; ".join(t for n, t in sorted(titulos.items()) if n < sesion),
        "sesion.no_adelantar": "; ".join(t for n, t in sorted(titulos.items()) if n > sesion),
    }
    cobertura_curso = cobertura_vigente(ficha_curso)
    if cobertura_curso and cobertura_curso["vigente"]:
        datos["sesion.referencia"] = "\n".join(cobertura_curso["sesiones"].get(str(sesion), []))
    return {campo: texto for campo, texto in datos.items() if texto}


def llenar_desde_el_curso(carpeta_curso: Path, sesion: int) -> list[str]:
    """Llena los campos vacíos de la ficha corta con la ficha del curso y la guarda. Una ficha confirmada no cambia.
    Devuelve los campos que llenó."""
    ficha = almacen.cargar(carpeta_curso, "sesion", sesion)
    if ficha["confirmada"]:
        return []
    llenados = []
    for campo, texto in datos_desde_el_curso(almacen.cargar(carpeta_curso, "curso"), sesion).items():
        dato = ficha["campos"].get(campo) or {}
        if not dato.get("valor") and dato.get("estado") != almacen.CONFLICTO:
            ficha["campos"][campo] = {"valor": texto, "origen": DESDE_EL_CURSO, "estado": ""}
            llenados.append(campo)
    if llenados:
        almacen.guardar(carpeta_curso, "sesion", sesion, ficha, "datos desde la ficha del curso")
    return llenados


def _avisos_de_completar(ficha: dict, clave: str) -> list[str]:
    """Lo que un programa comprueba en la propuesta. No la descarta: el profesor decide."""
    avisos = []
    if clave == "sesiones":
        numero = almacen.valor(ficha, "curso.numero_sesiones").strip()
        cuantas = len(almacen.sesiones_del_curso(ficha))
        if numero.isdigit() and cuantas != int(numero):
            avisos.append(f"Ojo: pediste {numero} sesiones y la propuesta trae {cuantas}.")
    if clave == "datos":
        _, sin_formato = almacen.datos_fijos(ficha)
        if sin_formato:
            avisos.append(f"Ojo: {len(sin_formato)} líneas de los datos fijos no tienen la forma «Etiqueta: valor».")
    if any(_TIEMPOS.search(almacen.valor(ficha, c)) for c in COMPLETAR[clave]["destino"]):
        avisos.append("Ojo: la propuesta menciona un tiempo. Bórralo: ningún material muestra tiempos.")
    return avisos


def aceptar_propuestos(ficha: dict) -> int:
    """«Aceptar lo propuesto»: los datos propuestos quedan como datos del profesor. Devuelve cuántos."""
    aceptados = 0
    for dato in ficha["campos"].values():
        if dato and dato.get("estado") == almacen.PROPUESTO and dato.get("valor"):
            dato["estado"] = ""
            aceptados += 1
    return aceptados


# ---------- Revisión de los ejercicios ----------



def problemas_de_ejercicios_guardados(ficha: dict) -> list[str]:
    """Los problemas de la última revisión, si los ejercicios no cambiaron desde entonces. Sin IA:
    la página los muestra al abrirse, para que el profesor sepa por qué la ficha sigue sin confirmar."""
    guardada = ficha.get("revision_ejercicios") or {}
    if ficha.get("confirmada") or guardada.get("huella") != almacen.huella_de_ejercicios(ficha):
        return []
    return guardada.get("problemas", [])


async def revisar_ejercicios(ficha: dict, curso: str, sesion: int, consulta=agente.query) -> list[str]:
    """Las tres preguntas de la skill (Paso 2.4). La segunda la revisa errores() sin IA. Si la sesión produce la
    evaluación, sus preguntas se revisan en la misma llamada (decisión 64 h)."""
    texto, numeros = almacen.texto_de_ejercicios(ficha)
    texto_preguntas, preguntas = almacen.texto_de_preguntas(ficha)
    if not numeros and not preguntas:
        return []
    huella = almacen.huella_de_ejercicios(ficha)
    guardada = ficha.get("revision_ejercicios") or {}
    if guardada.get("huella") == huella:
        return guardada["problemas"]
    pedido = (
        "Revisa cada ejercicio de esta ficha de laboratorio con dos preguntas.\n"
        "1. ¿Funciona solo, sin el resultado de otro ejercicio?\n"
        "2. ¿Se puede hacer de principio a fin con lo que trae, sin inventar datos que faltan? Escribir el "
        "resultado del ejercicio (una clasificación, una marca, un texto) es el ejercicio, no un dato que falta. "
        "Llenar espacios en blanco de un texto para copiar solo vale si llenarlos es el tema del ejercicio.\n"
        "Responde por cada ejercicio con su número, las dos respuestas y un motivo de una oración. "
        "Si las dos respuestas son sí, el motivo puede ser «Cumple».\n\n" + texto
    )
    if preguntas:
        pedido += (
            "\n\nRevisa también cada pregunta de la evaluación práctica con las mismas dos preguntas: ¿funciona "
            "sola, sin el resultado de otra pregunta ni de un ejercicio? ¿Se puede resolver con lo que trae, sin "
            "inventar datos que faltan? Escribir la respuesta en la tabla de la hoja es la tarea, no un dato que "
            "falta. Responde en «preguntas», con el número de cada pregunta.\n\n" + texto_preguntas
        )
    else:
        pedido += "\n\nNo hay preguntas de evaluación: deja «preguntas» vacía."
    respuesta = await agente.consultar(
        pedido, tarea="revision_ejercicios", esquema=ESQUEMA_REVISION, curso=curso,
        etapa="revisión de ejercicios", sesion=f"S{sesion}", consulta=consulta,
    )
    problemas = []
    for e in respuesta["ejercicios"]:
        if not e["funciona_solo"]:
            problemas.append(f"Ejercicio {e['numero']}: no funciona solo. {e['motivo']}")
        if not e["sin_llenar_a_mano"]:
            problemas.append(f"Ejercicio {e['numero']}: hay que llenar algo a mano. {e['motivo']}")
    for p in respuesta.get("preguntas", []) if preguntas else []:
        if not p["funciona_solo"]:
            problemas.append(f"Pregunta {p['numero']} de la evaluación: no funciona sola. {p['motivo']}")
        if not p["sin_llenar_a_mano"]:
            problemas.append(f"Pregunta {p['numero']} de la evaluación: le faltan datos para resolverla. {p['motivo']}")
    ficha["revision_ejercicios"] = {"huella": huella, "problemas": problemas}
    return problemas


CAMPOS_DEL_EJERCICIO = ("area", "accion", "entregable", "archivo", "problema", "respuesta", "pregunta_herramienta")


def ejercicios_con_problemas(problemas: list[str]) -> list[int]:
    return sorted({int(m.group(1)) for p in problemas if (m := re.match(r"Ejercicio (\d+):", p))})


def pedido_de_correccion(ficha: dict, ficha_curso: str, problemas: list[str]) -> str:
    numeros = ejercicios_con_problemas(problemas)
    etiquetas = {c.id: c.etiqueta for c in plantillas.FICHA_DE_LA_SESION[1][3].elementos[0].campos}
    bloques = []
    for n in numeros:
        bloques.append(f"Ejercicio {n}:\n" + "\n".join(
            f"- ejercicio.{n}.{i} ({etiquetas[i].replace('[número]', str(n))}): {almacen.valor(ficha, f'ejercicio.{n}.{i}')}"
            for i in CAMPOS_DEL_EJERCICIO))
    return "\n".join([
        "Vas a corregir ejercicios de la ficha de laboratorio de una sesión. Una revisión encontró estos problemas:",
        *[f"- {p}" for p in problemas],
        "",
        f"Alcance de la sesión: {almacen.valor(ficha, 'sesion.alcance')}",
        "",
        "Ejercicios que debes corregir (id del campo, etiqueta y valor actual):",
        "\n\n".join(bloques),
        "",
        "Reglas:",
        "- Corrige solo lo necesario para resolver cada problema. Conserva el área, el tema y la intención del ejercicio.",
        "- Cada ejercicio funciona solo, sin el resultado de otro ejercicio.",
        "- Cada ejercicio se ejecuta de principio a fin sin llenar nada a mano: el archivo de práctica trae todos los "
        "datos que el alumno necesita.",
        "- Los campos del ejercicio quedan coherentes entre sí: acción, archivo, problema, respuesta y entregable.",
        "- Los archivos de práctica son Excel para datos y Word para textos. PDF solo si el caso lo exige. Nunca .txt.",
        "- Los datos del caso son ficticios y cuadran con los datos fijos de la ficha del curso.",
        "- No inventes hechos del mundo real: ni cifras reales, ni estudios, ni personas reales, ni funciones de herramientas.",
        "- No escribas tiempos ni puntajes.",
        "- Devuelve solo los campos que cambias, con su id y su valor completo. No escribas marcas como «(propuesto)».",
        "- Escribe en el idioma del curso, en oraciones cortas y claras.",
        "",
        "Ficha del curso confirmada:",
        ficha_curso,
    ])


async def corregir_ejercicios(carpeta_curso: Path, curso: str, sesion: int, consulta=agente.query) -> str:
    """Botón «Corregir los ejercicios»: la IA corrige los ejercicios que marcó la revisión. Una sola corrección;
    después, guardar vuelve a revisarlos. Lo corregido queda marcado «Propuesto» para que el profesor lo vea."""
    ficha = almacen.cargar(carpeta_curso, "sesion", sesion)
    problemas = problemas_de_ejercicios_guardados(ficha)
    numeros = ejercicios_con_problemas(problemas)
    if not numeros:
        return "No hay ejercicios que corregir."
    ficha_curso = almacen.texto_para_materiales(carpeta_curso, "curso")
    respuesta = await agente.consultar(
        pedido_de_correccion(ficha, ficha_curso, problemas), tarea="correccion_ejercicios", esquema=ESQUEMA_COMPLETAR,
        curso=curso, etapa="corrección de ejercicios", sesion=f"S{sesion}", consulta=consulta,
    )
    permitidos = {f"ejercicio.{n}.{i}" for n in numeros for i in CAMPOS_DEL_EJERCICIO}
    cambiados = []
    for dato in respuesta.get("campos", []):
        texto = almacen.sin_marcas(dato["valor"])
        if dato["id"] in permitidos and texto and texto != almacen.valor(ficha, dato["id"]) and dato["id"] not in cambiados:
            ficha["campos"][dato["id"]] = {"valor": texto, "origen": "deducido", "estado": almacen.PROPUESTO}
            cambiados.append(dato["id"])
    if not cambiados:
        return "La corrección llegó vacía. No cambié nada."
    ficha["confirmada"] = False
    almacen.guardar(carpeta_curso, "sesion", sesion, ficha, "ejercicios corregidos")
    numeros = sorted({int(c.split(".")[1]) for c in cambiados})
    cuales = f"el ejercicio {numeros[0]}" if len(numeros) == 1 else \
        "los ejercicios " + ", ".join(map(str, numeros[:-1])) + f" y {numeros[-1]}"
    return f"Corregí {cuales}. Lo cambiado quedó marcado «Propuesto»."


# ---------- Confirmación ----------

# ---------- «Guardar» en la ficha de la sesión (PLAN.md §0, decisión 54, fase 2) ----------

# La evaluación cuenta solo si la sesión la produce (decisión 64 h); la actividad web no pide nada de la ficha.
_MATERIALES_DEL_PLAN = ("lectura", "diapositivas", "laboratorio", "evaluacion")


def plan_por_preparar(ficha: dict) -> bool:
    """El plan de la sesión no alcanza para producir sus materiales: falta el vocabulario o algo que un material pide."""
    if not almacen.vocabulario(ficha):
        return True
    materiales = almacen.materiales_de_la_sesion(ficha)
    return any(almacen.errores_del_material(ficha, m) for m in _MATERIALES_DEL_PLAN if m in materiales)


async def preparar_y_confirmar(carpeta_curso: Path, curso: str, sesion: int, consulta=agente.query) -> dict:
    """Lo que hace «Guardar»: la IA llena lo que falte del plan, lo propuesto se acepta, los ejercicios se revisan y,
    si la revisión encuentra problemas, se corrigen una vez y se revisan de nuevo. Si todo cumple, la ficha queda
    confirmada. El profesor no revisa el plan antes; queda en la ficha para revisarlo cuando quiera.
    Devuelve {mensajes, errores}: lo que se hizo y lo que impide confirmar."""
    mensajes = []
    ficha = almacen.cargar(carpeta_curso, "sesion", sesion)
    if not almacen.cargar(carpeta_curso, "curso")["confirmada"]:
        raise FichaDelCursoSinConfirmar("Guarda primero la ficha del curso completa: así queda confirmada.")
    antes = [e for e in almacen.errores(ficha) if e != almacen.SIN_VOCABULARIO]   # el vocabulario lo prepara la IA
    if antes:
        return {"mensajes": mensajes, "errores": antes}     # lo que falta en la ficha corta va primero, sin gastar
    if plan_por_preparar(ficha):
        resumen = await proponer(carpeta_curso, curso, "sesion", sesion, consulta=consulta)
        mensajes.append(f"Preparé el plan de la sesión: {resumen['de_las_fuentes'] + resumen['propuestos']} datos.")
        ficha = almacen.cargar(carpeta_curso, "sesion", sesion)
    if aceptar_propuestos(ficha):
        almacen.guardar(carpeta_curso, "sesion", sesion, ficha, "plan aceptado")
    for intento in (1, 2):
        try:
            await confirmar_sesion(carpeta_curso, curso, sesion, consulta=consulta)
            mensajes.append("Ficha de la sesión guardada y confirmada. Se escribió verificacion.json.")
            return {"mensajes": mensajes, "errores": []}
        except almacen.FichaIncompleta as error:
            ficha = almacen.cargar(carpeta_curso, "sesion", sesion)
            if intento == 2 or not ejercicios_con_problemas(problemas_de_ejercicios_guardados(ficha)):
                return {"mensajes": mensajes, "errores": error.errores}
        # Una sola corrección de lo que encontró la revisión (decisión 22); lo corregido también se acepta.
        mensajes.append(await corregir_ejercicios(carpeta_curso, curso, sesion, consulta=consulta))
        ficha = almacen.cargar(carpeta_curso, "sesion", sesion)
        if aceptar_propuestos(ficha):
            almacen.guardar(carpeta_curso, "sesion", sesion, ficha, "corrección aceptada")
    return {"mensajes": mensajes, "errores": []}


def confirmar_curso(carpeta_curso: Path) -> dict:
    ficha = almacen.cargar(carpeta_curso, "curso")
    lista = almacen.errores(ficha)
    if lista:
        raise almacen.FichaIncompleta(lista)
    ficha["confirmada"] = True
    almacen.guardar(carpeta_curso, "curso", None, ficha, "confirmada")
    # Las sesiones ya confirmadas usan la ficha nueva: su verificacion.json se escribe de nuevo.
    desactualizados = {}
    for numero in almacen.sesiones_confirmadas(carpeta_curso):
        verificacion.escribir(carpeta_curso, numero)
        desactualizados[numero] = almacen.marcar_desactualizados(carpeta_curso, numero)
    return {"desactualizados": desactualizados}


async def confirmar_sesion(carpeta_curso: Path, curso: str, sesion: int, consulta=agente.query) -> dict:
    if not almacen.cargar(carpeta_curso, "curso")["confirmada"]:
        raise FichaDelCursoSinConfirmar("Guarda primero la ficha del curso completa: así queda confirmada.")
    ficha = almacen.cargar(carpeta_curso, "sesion", sesion)
    lista = almacen.errores(ficha)
    if lista:
        raise almacen.FichaIncompleta(lista)
    problemas = await revisar_ejercicios(ficha, curso, sesion, consulta)
    if problemas:
        almacen.guardar(carpeta_curso, "sesion", sesion, ficha, "revision de ejercicios")
        raise almacen.FichaIncompleta(problemas)
    anterior = almacen.ultima_confirmada(carpeta_curso, sesion)
    ficha["confirmada"] = True
    almacen.guardar(carpeta_curso, "sesion", sesion, ficha, "confirmada")
    ruta = verificacion.escribir(carpeta_curso, sesion)
    return {"verificacion": ruta, "desactualizados": almacen.marcar_desactualizados(carpeta_curso, sesion, anterior)}

