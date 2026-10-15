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
import time
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

ESQUEMA_REVISION = {
    "type": "object",
    "properties": {"ejercicios": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "numero": {"type": "integer"},
            "funciona_solo": {"type": "boolean"},
            "sin_llenar_a_mano": {"type": "boolean"},
            "motivo": {"type": "string"},
        },
        "required": ["numero", "funciona_solo", "sin_llenar_a_mano", "motivo"], "additionalProperties": False,
    }}},
    "required": ["ejercicios"],
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
_INTENTOS_DE_REEMPLAZO = 40   # 40 × 0,05 s: unos dos segundos


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
        "  solo revisa y confirma. Lo que deduces o propones va con literal = false y queda marcado «(propuesto)».",
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
        lineas.append("- En «Sesiones» escribe una línea por sesión que empiece con su número: «1. Título: alcance».")
    else:
        ficha_curso = almacen.ruta_ficha(carpeta_curso, "curso", extension=".md").read_text(encoding="utf-8")
        sesiones = {s["numero"]: s["texto"] for s in almacen.sesiones_del_curso(almacen.cargar(carpeta_curso, "curso"))}
        lineas += [
            "- Puedes proponer temas, bloques, ejercicios, problemas sembrados, estaciones y preguntas que "
            "encajen con el alcance de la sesión y con el caso del curso. Todo lo que propongas va con literal = false.",
            "- Cada ejercicio funciona solo, tiene su archivo de práctica y su problema sembrado, y se ejecuta "
            "sin llenar nada a mano. Usa de 3 a 5 ejercicios y de 5 a 7 estaciones, una por línea.",
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
        campo_id, texto = dato["id"], dato["valor"].strip()
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
            {"valor": v["valor"].strip(), "origen": v["origen"].removesuffix(".jsonl").strip()}
            for v in conflicto["versiones"]
            if v["valor"].strip() and v["origen"].removesuffix(".jsonl").strip() in permitidas
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
COMPLETAR = {
    "sesiones": {
        "seccion": "1. Curso", "boton": "Completar las sesiones", "destino": ("curso.sesiones",),
        "usa": _CURSO + _PUBLICO, "exige": ("curso.nombre", "curso.numero_sesiones"),
        "ayuda": "Reparte el tema en el número de sesiones, según las horas y el público (sección 2). "
                 "Llena «Sesiones» si está vacío.",
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


def pedido_de_completar(ficha: dict, clave: str, fuentes: list[str]) -> str:
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
    if clave == "sesiones":
        numero = almacen.valor(ficha, "curso.numero_sesiones").strip()
        lineas += [
            f"- Escribe exactamente {numero} líneas, una por sesión, que empiecen con su número: «1. Título: alcance».",
            "- Reparte el tema de forma pareja entre las sesiones. Usa las horas solo para medir cuánto cabe en cada una.",
            "- El alcance dice qué temas cubre la sesión, en una o dos oraciones. Sigue el orden lógico del tema.",
            "- Ajusta el nivel a lo que el público ya sabe y a lo que valora.",
        ]
        if fuentes:
            lineas += [
                "- Si las fuentes del curso cubren el tema, sigue sus capítulos y su orden. Son los archivos .jsonl de "
                "esta carpeta: una línea por pasaje. Busca con Grep y lee con Read. Fuentes:",
                *[f"  - {f}" for f in fuentes],
            ]
    elif clave == "caso":
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
        return "Para completar, llena primero " + " y ".join(f"«{f}»" for f in faltan) + "."
    vacios = [c for c in datos["destino"] if not almacen.valor(ficha, c).strip()]
    if not vacios:
        return "Esa parte ya está llena. Borra lo que quieras cambiar y pulsa otra vez «Completar»."
    fuentes = verificacion.fuentes_utilizables(carpeta_curso) if clave == "sesiones" else []
    opciones = {}
    if fuentes:
        (carpeta_curso / "fuentes_texto").mkdir(parents=True, exist_ok=True)
        opciones = {"cwd": carpeta_curso / "fuentes_texto", "herramientas": ("Read", "Grep", "Glob")}
    respuesta = await agente.consultar(
        pedido_de_completar(ficha, clave, fuentes), tarea="completar_ficha", esquema=ESQUEMA_COMPLETAR,
        curso=curso, etapa=f"completar ficha: {clave}", consulta=consulta, **opciones,
    )
    llenados = []
    for dato in respuesta.get("campos", []):
        texto = dato["valor"].strip()
        if dato["id"] in vacios and texto and dato["id"] not in llenados:
            ficha["campos"][dato["id"]] = {"valor": texto, "origen": "deducido", "estado": almacen.PROPUESTO}
            llenados.append(dato["id"])
    if not llenados:
        return "La propuesta llegó vacía. No cambié nada."
    ficha["confirmada"] = False
    almacen.guardar(carpeta_curso, "curso", None, ficha, f"completada {clave}")
    nombres = ", ".join(f"«{etiquetas[c]}»" for c in llenados)
    return " ".join([f"Propuse {nombres}. Revisa lo marcado «Propuesto» y guarda.", *_avisos_de_completar(ficha, clave)])


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


# ---------- Propuesta automática al abrir la ficha (PLAN.md §0, decisión 17) ----------

def _ruta_propuesta(carpeta_curso: Path, tipo: str, sesion: int | None) -> Path:
    return almacen.ruta_ficha(carpeta_curso, tipo, sesion).with_name(f"propuesta_{tipo}.json")


def estado_propuesta(carpeta_curso: Path, tipo: str, sesion: int | None = None) -> dict:
    """{estado: trabajando, lista o error; mensaje}. Vacío si nunca se propuso sola."""
    ruta = _ruta_propuesta(carpeta_curso, tipo, sesion)
    if not ruta.exists():
        return {}
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"estado": "trabajando", "mensaje": ""}   # se está escribiendo justo ahora


def _guardar_estado_propuesta(carpeta_curso: Path, tipo: str, sesion: int | None, **estado) -> None:
    ruta = _ruta_propuesta(carpeta_curso, tipo, sesion)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    # Se escribe aparte y se reemplaza de una vez: la página nunca lee el archivo a medio escribir.
    temporal = ruta.with_suffix(".tmp")
    temporal.write_text(json.dumps(estado, ensure_ascii=False), encoding="utf-8")
    # En Windows el reemplazo falla mientras la página lee el archivo. Se reintenta unos instantes.
    for intento in range(_INTENTOS_DE_REEMPLAZO):
        try:
            temporal.replace(ruta)
            return
        except PermissionError:
            if intento == _INTENTOS_DE_REEMPLAZO - 1:
                raise
            time.sleep(0.05)


def debe_proponer_sola(carpeta_curso: Path, tipo: str, sesion: int | None = None) -> bool:
    """Una ficha sin confirmar, con campos vacíos y con fuentes convertidas se propone sola, una sola vez.
    Sin fuentes, el profesor la llena a mano."""
    if estado_propuesta(carpeta_curso, tipo, sesion):
        return False
    if not verificacion.fuentes_utilizables(carpeta_curso):
        return False
    if tipo == "sesion" and not almacen.cargar(carpeta_curso, "curso")["confirmada"]:
        return False
    ficha = almacen.cargar(carpeta_curso, tipo, sesion)
    return not ficha["confirmada"] and bool(campos_vacios(ficha))


def marcar_propuesta_en_curso(carpeta_curso: Path, tipo: str, sesion: int | None = None) -> None:
    """Se marca antes de empezar, para que recargar la página no lance otra propuesta."""
    _guardar_estado_propuesta(carpeta_curso, tipo, sesion, estado="trabajando", mensaje="")


async def proponer_sola(carpeta_curso: Path, curso: str, tipo: str, sesion: int | None = None,
                        consulta=agente.query) -> dict:
    try:
        resumen = await proponer(carpeta_curso, curso, tipo, sesion, consulta=consulta)
    except Exception as error:   # la página muestra el motivo; el botón «Proponer» sigue disponible
        _guardar_estado_propuesta(carpeta_curso, tipo, sesion, estado="error",
                                  mensaje=f"No se pudo proponer la ficha desde las fuentes: {error}")
        raise
    _guardar_estado_propuesta(
        carpeta_curso, tipo, sesion, estado="lista",
        mensaje=(f"AulaLista llenó la ficha desde las fuentes. Datos tomados tal cual: {resumen['de_las_fuentes']}. "
                 f"Propuestos: {resumen['propuestos']}. Con dos versiones: {resumen['conflictos']}. "
                 "Revisa lo marcado «Propuesto» y guarda."))
    return resumen


def aceptar_propuestos(ficha: dict) -> int:
    """«Aceptar lo propuesto»: los datos propuestos quedan como datos del profesor. Devuelve cuántos."""
    aceptados = 0
    for dato in ficha["campos"].values():
        if dato and dato.get("estado") == almacen.PROPUESTO and dato.get("valor"):
            dato["estado"] = ""
            aceptados += 1
    return aceptados


# ---------- Revisión de los ejercicios ----------

def _texto_de_ejercicios(ficha: dict) -> tuple[str, list[int]]:
    ids = ("area", "accion", "entregable", "archivo", "problema", "respuesta", "pregunta_herramienta")
    numeros = almacen.bloques_llenos(ficha, "ejercicio", plantillas.MAX_EJERCICIOS, ids)
    etiquetas = {c.id: c.etiqueta for c in plantillas.FICHA_DE_LA_SESION[1][3].elementos[0].campos}
    bloques = []
    for n in numeros:
        bloques.append("\n".join(
            f"- {etiquetas[i].replace('[número]', str(n))}: {almacen.valor(ficha, f'ejercicio.{n}.{i}')}" for i in ids
        ))
    return "\n\n".join(bloques), numeros


def _huella_de_ejercicios(ficha: dict) -> str:
    return hashlib.sha256(_texto_de_ejercicios(ficha)[0].encode("utf-8")).hexdigest()


def problemas_de_ejercicios_guardados(ficha: dict) -> list[str]:
    """Los problemas de la última revisión, si los ejercicios no cambiaron desde entonces. Sin IA:
    la página los muestra al abrirse, para que el profesor sepa por qué la ficha sigue sin confirmar."""
    guardada = ficha.get("revision_ejercicios") or {}
    if ficha.get("confirmada") or guardada.get("huella") != _huella_de_ejercicios(ficha):
        return []
    return guardada.get("problemas", [])


async def revisar_ejercicios(ficha: dict, curso: str, sesion: int, consulta=agente.query) -> list[str]:
    """Las tres preguntas de la skill (Paso 2.4). La segunda la revisa errores() sin IA."""
    texto, numeros = _texto_de_ejercicios(ficha)
    if not numeros:
        return []
    huella = _huella_de_ejercicios(ficha)
    guardada = ficha.get("revision_ejercicios") or {}
    if guardada.get("huella") == huella:
        return guardada["problemas"]
    pedido = (
        "Revisa cada ejercicio de esta ficha de laboratorio con dos preguntas.\n"
        "1. ¿Funciona solo, sin el resultado de otro ejercicio?\n"
        "2. ¿Se puede ejecutar de principio a fin sin llenar nada a mano? Llenar algo a mano solo vale "
        "si llenarlo es el tema del ejercicio.\n"
        "Responde por cada ejercicio con su número, las dos respuestas y un motivo de una oración. "
        "Si las dos respuestas son sí, el motivo puede ser «Cumple».\n\n" + texto
    )
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
    ficha["revision_ejercicios"] = {"huella": huella, "problemas": problemas}
    return problemas


# ---------- Confirmación ----------

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
    ficha["confirmada"] = True
    almacen.guardar(carpeta_curso, "sesion", sesion, ficha, "confirmada")
    ruta = verificacion.escribir(carpeta_curso, sesion)
    return {"verificacion": ruta, "desactualizados": almacen.marcar_desactualizados(carpeta_curso, sesion)}

