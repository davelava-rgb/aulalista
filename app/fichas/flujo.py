"""Pasos 1 y 2 del flujo (SPEC §5): proponer las fichas desde las fuentes y confirmarlas.

Reglas de la skill (Paso 1 y Paso 2):
- Cada dato lleva anotado el archivo del que salió.
- Un dato deducido se marca «(propuesto)». Un dato ausente se marca «Falta definir».
- Si dos archivos se contradicen, se muestran las dos versiones y se pregunta cuál vale.
- Cada ejercicio se revisa con tres preguntas antes de confirmar la ficha de la sesión.
"""

import hashlib
import unicodedata
from pathlib import Path

from app import agente
from app.fichas import almacen, plantillas, verificacion
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


def campos_vacios(ficha: dict) -> list[tuple[str, str]]:
    vacios = []
    for campo, _ in plantillas.campos_de(ficha["tipo"]):
        dato = ficha["campos"].get(campo.id) or {}
        if not dato.get("valor") and dato.get("estado") != almacen.CONFLICTO:
            vacios.append((campo.id, campo.etiqueta))
    return vacios


def pedido_de_propuesta(carpeta_curso: Path, tipo: str, sesion: int | None, ficha: dict) -> str:
    fuentes = verificacion.fuentes_utilizables(carpeta_curso)
    lineas = [
        f"Vas a llenar la {'ficha del curso' if tipo == 'curso' else f'ficha de la sesión {sesion}'}.",
        "Trabajas solo con los archivos .jsonl de esta carpeta. Cada uno es una fuente del curso convertida "
        "a texto: una línea por pasaje, con su texto y su ubicación.",
        "Fuentes que puedes usar (el nombre del .jsonl es el nombre de la fuente más «.jsonl»):",
        *[f"- {f}" for f in fuentes],
        "Busca con Grep y lee con Read. No uses tu memoria. No inventes datos para llenar un vacío.",
        "",
        "Campos vacíos que debes intentar llenar (id: etiqueta):",
        *[f"- {campo_id}: {etiqueta}" for campo_id, etiqueta in campos_vacios(ficha)],
        "",
        "Reglas:",
        "- Por cada dato devuelve id, valor, origen y literal. El origen es el nombre exacto de la fuente.",
        "- literal = true solo si la fuente dice el dato con esas mismas palabras. Si lo deduces, literal = false.",
        "- Si dos fuentes dicen cosas distintas sobre el mismo dato, no elijas: devuélvelo en «conflictos» con las dos versiones.",
        "- Si ninguna fuente dice un dato y no se puede deducir con seguridad, no lo devuelvas.",
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
            "- En el vocabulario escribe un concepto por línea con su nombre único. Si conviene, agrega "
            "«(no usar: variante 1, variante 2)».",
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
        if campo_id not in validos or not texto or not vacio(campo_id):
            resumen["descartados"] += 1
            continue
        if origen in permitidas and dato["literal"] and _dice_literal(carpeta_curso, origen, texto):
            ficha["campos"][campo_id] = {"valor": texto, "origen": origen, "estado": ""}
            resumen["de_las_fuentes"] += 1
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
        raise FichaDelCursoSinConfirmar("Confirma primero la ficha del curso.")
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


async def revisar_ejercicios(ficha: dict, curso: str, sesion: int, consulta=agente.query) -> list[str]:
    """Las tres preguntas de la skill (Paso 2.4). La segunda la revisa errores() sin IA."""
    texto, numeros = _texto_de_ejercicios(ficha)
    if not numeros:
        return []
    huella = hashlib.sha256(texto.encode("utf-8")).hexdigest()
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
        raise FichaDelCursoSinConfirmar("Confirma primero la ficha del curso.")
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

