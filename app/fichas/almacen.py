"""Fichas del curso y de la sesión: guardar, editar, versiones, revisión y confirmación.

Cada ficha se guarda en dos archivos:
- [ficha].json: los valores con su origen y su estado. Es lo que lee AulaLista.
- [ficha].md: el texto de la plantilla de la skill con los valores. Es lo que leen el
  profesor y el agente.
Cada vez que se guarda, queda una copia en fichas/versiones/ con la fecha.
"""

import json
import re
from datetime import datetime
from pathlib import Path

from app.fichas import plantillas

NOMBRES = {"curso": "ficha_del_curso", "sesion": "ficha_de_la_sesion"}
PROPUESTO = "propuesto"
FALTA_DEFINIR = "falta definir"
CONFLICTO = "conflicto"
PROFESOR = "profesor"
MAX_PREGUNTAS_POR_VEZ = 4  # SPEC §3: cuatro preguntas como máximo por vez

MATERIALES = ("lectura", "diapositivas", "laboratorio", "guía del profesor", "práctica interactiva", "evaluación")


class FichaIncompleta(ValueError):
    """La ficha no se puede confirmar todavía."""

    def __init__(self, errores: list[str]):
        super().__init__(" ".join(errores))
        self.errores = errores


# ---------- Rutas ----------

def carpeta_sesion(carpeta_curso: Path, sesion: int) -> Path:
    return carpeta_curso / "sesiones" / f"S{sesion}"


def _carpeta_de(carpeta_curso: Path, tipo: str, sesion: int | None) -> Path:
    return carpeta_curso if tipo == "curso" else carpeta_sesion(carpeta_curso, sesion)


def ruta_ficha(carpeta_curso: Path, tipo: str, sesion: int | None = None, extension: str = ".json") -> Path:
    return _carpeta_de(carpeta_curso, tipo, sesion) / f"{NOMBRES[tipo]}{extension}"


def _carpeta_versiones(carpeta_curso: Path, tipo: str, sesion: int | None) -> Path:
    return _carpeta_de(carpeta_curso, tipo, sesion) / "fichas" / "versiones"


# ---------- Leer y guardar ----------

def nueva(tipo: str) -> dict:
    return {"tipo": tipo, "confirmada": False, "fecha_confirmacion": "", "campos": {}}


def cargar(carpeta_curso: Path, tipo: str, sesion: int | None = None) -> dict:
    ruta = ruta_ficha(carpeta_curso, tipo, sesion)
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else nueva(tipo)


def valor(ficha: dict, campo_id: str) -> str:
    return (ficha["campos"].get(campo_id) or {}).get("valor", "")


def nota_de_origen(ficha: dict, campo_id: str) -> str:
    """Nota que acompaña a cada dato en el .md: de dónde salió y si es propuesto (SPEC §3)."""
    dato = ficha["campos"].get(campo_id) or {}
    estado, origen = dato.get("estado", ""), dato.get("origen", "")
    if estado == FALTA_DEFINIR:
        return "Falta definir"
    if estado == CONFLICTO:
        versiones = " / ".join(f"«{v['valor']}» ({v['origen']})" for v in dato.get("versiones", []))
        return f"Conflicto: {versiones}"
    if not dato.get("valor"):
        return ""
    partes = []
    if estado == PROPUESTO:
        partes.append("(propuesto)")
    if origen and origen != PROFESOR:
        partes.append(f"(fuente: {origen})")
    return " ".join(partes)


def guardar(carpeta_curso: Path, tipo: str, sesion: int | None, ficha: dict, motivo: str = "guardada") -> Path:
    ruta = ruta_ficha(carpeta_curso, tipo, sesion)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ficha["actualizada"] = datetime.now().isoformat(timespec="seconds")
    texto = json.dumps(ficha, ensure_ascii=False, indent=2)
    ruta.write_text(texto, encoding="utf-8")
    ruta_ficha(carpeta_curso, tipo, sesion, ".md").write_text(
        plantillas.renderizar(tipo, ficha["campos"], lambda campo_id: nota_de_origen(ficha, campo_id)),
        encoding="utf-8",
    )
    versiones = _carpeta_versiones(carpeta_curso, tipo, sesion)
    versiones.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    # Nombre corto: Windows no admite rutas de más de 260 caracteres.
    (versiones / f"{marca}_{_slug(motivo)[:24]}.json").write_text(texto, encoding="utf-8")
    return ruta


def _slug(texto: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", texto.lower()).strip("-") or "guardada"


def listar_versiones(carpeta_curso: Path, tipo: str, sesion: int | None = None) -> list[dict]:
    carpeta = _carpeta_versiones(carpeta_curso, tipo, sesion)
    if not carpeta.exists():
        return []
    resultado = []
    for ruta in sorted(carpeta.glob("*.json"), reverse=True):
        coincidencia = re.match(r"(\d{8})-(\d{6})-\d+_(.+)\.json$", ruta.name)
        if coincidencia:
            dia, hora, motivo = coincidencia.groups()
            fecha = f"{dia[6:8]}/{dia[4:6]}/{dia[:4]} {hora[:2]}:{hora[2:4]}:{hora[4:6]}"
            resultado.append({"archivo": ruta.name, "fecha": fecha, "motivo": motivo.replace("-", " ")})
    return resultado


def restaurar(carpeta_curso: Path, tipo: str, sesion: int | None, archivo_version: str) -> dict:
    """Vuelve a una versión anterior. La ficha queda sin confirmar hasta revisarla de nuevo."""
    ruta = _carpeta_versiones(carpeta_curso, tipo, sesion) / Path(archivo_version).name
    if not ruta.exists():
        raise FileNotFoundError(archivo_version)
    ficha = json.loads(ruta.read_text(encoding="utf-8"))
    ficha["confirmada"] = False
    guardar(carpeta_curso, tipo, sesion, ficha, "restaurada")
    return ficha


# ---------- Edición desde el formulario ----------

def ids_validos(tipo: str) -> set[str]:
    return {campo.id for campo, _ in plantillas.campos_de(tipo)}


def aplicar_formulario(ficha: dict, formulario: dict) -> bool:
    """Aplica lo que el profesor escribió. Devuelve True si algo cambió.

    - Un valor nuevo o editado queda con origen «profesor» y sin marcas.
    - Un valor igual al anterior conserva su origen y su estado.
    - «elegir.[campo]» resuelve un conflicto con la versión elegida.
    """
    validos = ids_validos(ficha["tipo"])
    cambio = False
    resueltos = set()
    for clave, texto in formulario.items():
        if clave.startswith("elegir.") and texto != "":
            campo_id = clave.removeprefix("elegir.")
            dato = ficha["campos"].get(campo_id) or {}
            versiones = dato.get("versiones", [])
            if campo_id in validos and dato.get("estado") == CONFLICTO and texto.isdigit() and int(texto) < len(versiones):
                elegida = versiones[int(texto)]
                ficha["campos"][campo_id] = {"valor": elegida["valor"], "origen": elegida["origen"], "estado": ""}
                resueltos.add(campo_id)
                cambio = True
    for campo_id in validos:
        if campo_id not in formulario or campo_id in resueltos:
            continue
        nuevo = _limpiar(formulario[campo_id])
        anterior = ficha["campos"].get(campo_id) or {}
        if anterior.get("estado") == CONFLICTO and not nuevo:
            continue
        if nuevo == anterior.get("valor", ""):
            continue
        if nuevo:
            ficha["campos"][campo_id] = {"valor": nuevo, "origen": PROFESOR, "estado": ""}
        else:
            ficha["campos"].pop(campo_id, None)
        cambio = True
    if cambio:
        ficha["confirmada"] = False
    return cambio


def _limpiar(texto: str) -> str:
    return "\n".join(linea.rstrip() for linea in str(texto).replace("\r\n", "\n").strip().split("\n"))


def marcar_faltantes(ficha: dict) -> None:
    """Un obligatorio vacío queda marcado «Falta definir» (SPEC §3)."""
    for campo, seccion in plantillas.campos_de(ficha["tipo"]):
        if plantillas.es_obligatorio(campo, seccion) and not valor(ficha, campo.id):
            if (ficha["campos"].get(campo.id) or {}).get("estado") != CONFLICTO:
                ficha["campos"][campo.id] = {"valor": "", "origen": "", "estado": FALTA_DEFINIR}


# ---------- Revisión ----------

def materiales_de_la_sesion(ficha_sesion: dict) -> set[str]:
    """Materiales que se producen. Vacío o «los seis» significa todos."""
    texto = valor(ficha_sesion, "materiales.cuales").lower()
    if not texto.strip() or "seis" in texto or "todos" in texto:
        return set(MATERIALES)
    sin_tildes = texto.replace("í", "i").replace("á", "a").replace("ó", "o")
    claves = {"lectura": "lectura", "diapositiva": "diapositivas", "laboratorio": "laboratorio",
              "guia": "guía del profesor", "practica": "práctica interactiva", "evaluacion": "evaluación"}
    return {material for clave, material in claves.items() if clave in sin_tildes}


def _renglones(texto: str) -> list[str]:
    return [l.strip() for l in texto.splitlines() if l.strip()]


def bloques_llenos(ficha: dict, prefijo: str, maximo: int, ids: tuple[str, ...]) -> list[int]:
    return [n for n in range(1, maximo + 1) if any(valor(ficha, f"{prefijo}.{n}.{i}") for i in ids)]


def errores(ficha: dict) -> list[str]:
    """Lo que impide confirmar la ficha."""
    lista = []
    for campo, seccion in plantillas.campos_de(ficha["tipo"]):
        dato = ficha["campos"].get(campo.id) or {}
        if dato.get("estado") == CONFLICTO:
            lista.append(f"Elige la versión que vale en «{campo.nombre}».")
        elif plantillas.es_obligatorio(campo, seccion) and not dato.get("valor"):
            lista.append(f"Falta «{campo.nombre}».")
    if ficha["tipo"] == "sesion":
        lista += _errores_de_la_sesion(ficha)
    return lista


def _errores_de_la_sesion(ficha: dict) -> list[str]:
    lista = []
    materiales = materiales_de_la_sesion(ficha)
    bloques = [n for n in range(1, 5) if valor(ficha, f"lectura.bloque.{n}")]
    if "lectura" in materiales and len(bloques) < 2:
        lista.append("La lectura necesita de 2 a 4 bloques.")
    riesgos = _renglones(valor(ficha, "lectura.cuidado"))
    if "lectura" in materiales and not 1 <= len(riesgos) <= 3:
        lista.append("«Cuidado con» necesita de 1 a 3 riesgos, uno por línea.")
    if not vocabulario(ficha):
        lista.append("Escribe al menos un concepto clave del vocabulario.")
    if "laboratorio" in materiales:
        ids = ("area", "accion", "entregable", "archivo", "problema", "respuesta")
        ejercicios = bloques_llenos(ficha, "ejercicio", plantillas.MAX_EJERCICIOS, ids)
        if not 3 <= len(ejercicios) <= 5:
            lista.append(f"El laboratorio necesita de 3 a 5 ejercicios; tiene {len(ejercicios)}.")
        for n in ejercicios:
            for campo_id, nombre in (("archivo", "el archivo de práctica"), ("problema", "el problema que trae a propósito"),
                                     ("respuesta", "la respuesta correcta"), ("accion", "la acción del alumno")):
                if not valor(ficha, f"ejercicio.{n}.{campo_id}"):
                    lista.append(f"Ejercicio {n}: falta {nombre}.")
    if "práctica interactiva" in materiales:
        estaciones = _renglones(valor(ficha, "practica.estaciones"))
        if not 5 <= len(estaciones) <= 7:
            lista.append(f"La práctica necesita de 5 a 7 estaciones, una por línea; tiene {len(estaciones)}.")
    if "evaluación" in materiales:
        ids = ("concepto", "tarea", "archivo", "problema", "respuesta")
        preguntas = bloques_llenos(ficha, "pregunta", plantillas.MAX_PREGUNTAS, ids)
        if not preguntas:
            lista.append("La evaluación necesita al menos una pregunta (por defecto, 3).")
        for n in preguntas:
            for campo_id, nombre in (("concepto", "el concepto que evalúa"), ("tarea", "la tarea"),
                                     ("archivo", "el archivo de la evaluación"), ("respuesta", "la respuesta correcta")):
                if not valor(ficha, f"pregunta.{n}.{campo_id}"):
                    lista.append(f"Pregunta {n}: falta {nombre}.")
    return lista


def preguntas_pendientes(ficha: dict, maximo: int = MAX_PREGUNTAS_POR_VEZ) -> list[dict]:
    """Datos que el profesor debe responder, primero los obligatorios. Como máximo cuatro por vez."""
    pendientes = []
    for orden, (campo, seccion) in enumerate(plantillas.campos_de(ficha["tipo"])):
        dato = ficha["campos"].get(campo.id) or {}
        estado = dato.get("estado", "")
        obligatorio = plantillas.es_obligatorio(campo, seccion)
        if estado == CONFLICTO:
            motivo = "Dos archivos dicen cosas distintas. Elige cuál vale."
        elif obligatorio and not dato.get("valor"):
            motivo = "Es obligatorio y ningún archivo lo dice."
        elif estado == PROPUESTO:
            motivo = "Lo propuso AulaLista: ningún archivo lo dice tal cual."
        else:
            continue
        prioridad = 0 if obligatorio else 1
        pendientes.append({"id": campo.id, "nombre": campo.nombre, "motivo": motivo, "orden": (prioridad, orden)})
    pendientes.sort(key=lambda p: p["orden"])
    return pendientes[:maximo]


# ---------- Datos que usan otros componentes ----------

def sesiones_del_curso(ficha_curso: dict) -> list[dict]:
    """Lee el campo «Sesiones»: una línea por sesión, que empieza con su número."""
    resultado = []
    for linea in _renglones(valor(ficha_curso, "curso.sesiones")):
        coincidencia = re.match(r"^(?:sesi[oó]n\s*)?(\d+)\s*[.:·)\-–]?\s*(.*)$", linea, re.I)
        if coincidencia:
            resultado.append({"numero": int(coincidencia.group(1)), "texto": coincidencia.group(2).strip()})
    return resultado


def vocabulario(ficha_sesion: dict) -> list[dict]:
    """Conceptos clave en su orden. Las variantes prohibidas se escriben así:
    «Manifiesto Ágil (no usar: Agile, manifiesto agile)»."""
    conceptos = []
    for orden, linea in enumerate(_renglones(valor(ficha_sesion, "vocabulario.conceptos")), start=1):
        linea = re.sub(r"^\d+\s*[.)\-–]\s*", "", linea)
        variantes = []
        coincidencia = re.search(r"\(\s*no usar\s*:\s*([^)]*)\)", linea, re.I)
        if coincidencia:
            variantes = [v.strip() for v in coincidencia.group(1).split(",") if v.strip()]
            linea = (linea[:coincidencia.start()] + linea[coincidencia.end():]).strip()
        if linea:
            conceptos.append({"concepto": linea, "orden": orden, "variantes": variantes})
    return conceptos


def datos_fijos(ficha_curso: dict) -> tuple[list[dict], list[str]]:
    """Fecha de referencia y cada línea «Etiqueta: valor» de los datos fijos.
    Devuelve también las líneas que no tienen ese formato."""
    datos, sin_formato = [], []
    fecha = valor(ficha_curso, "datos.fecha").strip()
    if fecha:
        datos.append({"etiqueta": "Fecha de referencia", "valor": fecha})
    for linea in _renglones(valor(ficha_curso, "datos.fijos")):
        etiqueta, separador, dato = linea.lstrip("-• ").partition(":")
        if separador and etiqueta.strip() and dato.strip():
            datos.append({"etiqueta": etiqueta.strip(), "valor": dato.strip()})
        else:
            sin_formato.append(linea)
    return datos, sin_formato


# ---------- Estado de la sesión y confirmación ----------

def ruta_estado(carpeta_curso: Path, sesion: int) -> Path:
    return carpeta_sesion(carpeta_curso, sesion) / "estado.json"


def cargar_estado(carpeta_curso: Path, sesion: int) -> dict:
    ruta = ruta_estado(carpeta_curso, sesion)
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {"materiales": {}}


def guardar_estado(carpeta_curso: Path, sesion: int, estado: dict) -> None:
    ruta = ruta_estado(carpeta_curso, sesion)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(estado, ensure_ascii=False, indent=2), encoding="utf-8")


def marcar_desactualizados(carpeta_curso: Path, sesion: int) -> list[str]:
    """Los materiales ya generados no se entregan hasta validarlos con las fichas nuevas."""
    estado = cargar_estado(carpeta_curso, sesion)
    marcados = []
    for nombre, material in estado["materiales"].items():
        material["desactualizado"] = True
        marcados.append(nombre)
    guardar_estado(carpeta_curso, sesion, estado)
    return marcados


def sesiones_confirmadas(carpeta_curso: Path) -> list[int]:
    base = carpeta_curso / "sesiones"
    if not base.exists():
        return []
    numeros = []
    for carpeta in base.iterdir():
        if re.fullmatch(r"S\d+", carpeta.name) and cargar(carpeta_curso, "sesion", int(carpeta.name[1:]))["confirmada"]:
            numeros.append(int(carpeta.name[1:]))
    return sorted(numeros)


def puede_empezar_material(carpeta_curso: Path, sesion: int) -> bool:
    """Ningún material empieza sin las dos fichas confirmadas (SPEC §3)."""
    return cargar(carpeta_curso, "curso")["confirmada"] and cargar(carpeta_curso, "sesion", sesion)["confirmada"]
