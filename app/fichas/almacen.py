"""Fichas del curso y de la sesión: guardar, editar, versiones, revisión y confirmación.

Cada ficha se guarda en dos archivos:
- [ficha].json: los valores con su origen y su estado. Es lo que lee AulaLista.
- [ficha].md: el texto de la plantilla de la skill con los valores. Es lo que leen el
  profesor y el agente.
Cada vez que se guarda, queda una copia en fichas/versiones/ con la fecha.
"""

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

from app.fichas import controles, plantillas

NOMBRES = {"curso": "ficha_del_curso", "sesion": "ficha_de_la_sesion"}
PROPUESTO = "propuesto"
FALTA_DEFINIR = "falta definir"
CONFLICTO = "conflicto"
PROFESOR = "profesor"
MAX_PREGUNTAS_POR_VEZ = 4  # SPEC §3: cuatro preguntas como máximo por vez

# Sin práctica interactiva ni guía del profesor (PLAN.md §0, decisiones 34 y 35).
MATERIALES = ("lectura", "diapositivas", "laboratorio", "evaluación")


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
    ficha = {"tipo": tipo, "confirmada": False, "fecha_confirmacion": "", "campos": {}}
    poner_por_omision(ficha)
    return ficha


def cargar(carpeta_curso: Path, tipo: str, sesion: int | None = None) -> dict:
    ruta = ruta_ficha(carpeta_curso, tipo, sesion)
    ficha = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else nueva(tipo)
    poner_nombre_del_curso(carpeta_curso, ficha)
    quitar_faltas_viejas(ficha)
    revision = ficha.get("revision_ejercicios") or {}
    vigente = ficha["tipo"] == "sesion" and revision.get("huella") == huella_de_ejercicios(ficha)
    quitar_marcas_del_valor(ficha)
    if vigente:
        # Quitar la marca no cambia los ejercicios: la revisión guardada sigue valiendo.
        revision["huella"] = huella_de_ejercicios(ficha)
    poner_por_omision(ficha)
    return ficha


def poner_nombre_del_curso(carpeta_curso: Path, ficha: dict) -> None:
    """El nombre que el profesor dio al crear el curso llena «Nombre del curso» si está vacío. Así la propuesta
    desde las fuentes no lo reemplaza por el título de un PDF."""
    ruta = carpeta_curso / "curso.json"
    if ficha["tipo"] != "curso" or valor(ficha, "curso.nombre").strip() or not ruta.exists():
        return
    nombre = json.loads(ruta.read_text(encoding="utf-8")).get("nombre", "").strip()
    if nombre:
        ficha["campos"]["curso.nombre"] = {"valor": nombre, "origen": PROFESOR, "estado": ""}


def texto_de_ejercicios(ficha: dict) -> tuple[str, list[int]]:
    """Los ejercicios llenos, con sus etiquetas: lo que revisa la IA antes de confirmar la ficha de la sesión."""
    ids = ("area", "accion", "entregable", "archivo", "problema", "respuesta", "pregunta_herramienta")
    numeros = bloques_llenos(ficha, "ejercicio", plantillas.MAX_EJERCICIOS, ids)
    etiquetas = {c.id: c.etiqueta for c in plantillas.FICHA_DE_LA_SESION[1][3].elementos[0].campos}
    bloques = []
    for n in numeros:
        bloques.append("\n".join(
            f"- {etiquetas[i].replace('[número]', str(n))}: {valor(ficha, f'ejercicio.{n}.{i}')}" for i in ids
        ))
    return "\n\n".join(bloques), numeros


def huella_de_ejercicios(ficha: dict) -> str:
    return hashlib.sha256(texto_de_ejercicios(ficha)[0].encode("utf-8")).hexdigest()


MARCA_PROPUESTO = re.compile(r"[ \t]*\(\s*propuest[oa]s?\s*\)", re.I)


def sin_marca(texto: str) -> str:
    """Quita «(propuesto)» de una línea. La marca vive en el estado del dato, nunca en su valor:
    si queda en el valor, llega a los materiales."""
    return MARCA_PROPUESTO.sub("", texto).rstrip()


def quitar_marcas_del_valor(ficha: dict) -> None:
    """Una ficha propuesta antes de esta corrección puede traer «(propuesto)» escrito dentro del valor."""
    for dato in ficha["campos"].values():
        if dato and dato.get("valor"):
            dato["valor"] = sin_marcas(dato["valor"])
        for version in (dato or {}).get("versiones", []):
            version["valor"] = sin_marcas(version["valor"])


def sin_marcas(texto: str) -> str:
    """sin_marca() en cada línea de un valor."""
    return "\n".join(sin_marca(l) for l in texto.split("\n")).strip()


def herramienta_de_los_ejercicios(carpeta_curso: Path) -> frozenset[str]:
    """«excel», «ia», los dos o ninguno, según la ficha del curso (PLAN.md §0, decisión 36). Vacío vale «ninguna»:
    los ejercicios salen del tema de la sesión y el alumno trabaja a mano en el archivo de práctica."""
    texto = valor(cargar(carpeta_curso, "curso"), "herramientas.ejercicios").strip().lower()
    return frozenset(nombre for nombre, patron in (("excel", r"\bexcel\b"), ("ia", r"\bia\b")) if re.search(patron, texto))


def poner_por_omision(ficha: dict) -> None:
    """El docente y el contacto vacíos de la ficha del curso toman su valor por defecto. Se pueden cambiar,
    pero no quedar vacíos (decisión 27)."""
    if ficha["tipo"] != "curso":
        return
    for campo_id, texto in controles.POR_OMISION_DEL_CURSO.items():
        if not valor(ficha, campo_id):
            ficha["campos"][campo_id] = {"valor": texto, "origen": PROFESOR, "estado": ""}


def quitar_faltas_viejas(ficha: dict) -> None:
    """Quita «Falta definir» de los campos vacíos que ya no son obligatorios. Una ficha guardada antes de la
    decisión 16 puede traer esa marca en «Público» o en «Empresa»."""
    obligatorios = {c.id for c, s in plantillas.campos_de(ficha["tipo"]) if plantillas.es_obligatorio(c, s)}
    for campo_id, dato in ficha["campos"].items():
        if dato and dato.get("estado") == FALTA_DEFINIR and campo_id not in obligatorios and not dato.get("valor"):
            dato["estado"] = ""


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


# Las horas solo sirven para repartir el tema en sesiones. Ningún material muestra tiempos (SPEC §6).
SOLO_PARA_LA_FICHA = ("- Horas del curso:",)


def texto_para_materiales(carpeta_curso: Path, tipo: str, sesion: int | None = None) -> str:
    """El .md de la ficha que recibe el redactor, sin los datos que no van a ningún material."""
    texto = ruta_ficha(carpeta_curso, tipo, sesion, ".md").read_text(encoding="utf-8")
    # La marca «(propuesto)» del .md es para el profesor: el redactor no la recibe.
    return "".join(MARCA_PROPUESTO.sub("", l) for l in texto.splitlines(keepends=True)
                   if not l.startswith(SOLO_PARA_LA_FICHA))


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
        if nuevo == anterior.get("valor", "") or controles.equivalente(campo_id, nuevo, anterior.get("valor", "")):
            continue
        if nuevo:
            ficha["campos"][campo_id] = {"valor": nuevo, "origen": PROFESOR, "estado": ""}
        else:
            ficha["campos"].pop(campo_id, None)
        cambio = True
    if cambio:
        ficha["confirmada"] = False
    return cambio


def valores_de(ficha: dict) -> dict[str, str]:
    """Lo que muestra la página al abrirse: el valor de cada campo con dato."""
    return {campo_id: dato["valor"] for campo_id, dato in ficha["campos"].items() if dato and dato.get("valor")}


def solo_lo_cambiado(formulario: dict, base: dict[str, str]) -> dict:
    """Quita del formulario los campos que el profesor no tocó: los que siguen como estaban al abrir la página.
    Así, si la ficha cambió mientras la página estaba abierta (una propuesta que terminó), guardar no la borra."""
    return {
        clave: texto for clave, texto in formulario.items()
        if not (_limpiar(texto) == _limpiar(base.get(clave, ""))
                or controles.equivalente(clave, _limpiar(texto), base.get(clave, "")))
    }


def _limpiar(texto: str) -> str:
    return "\n".join(sin_marca(linea) for linea in str(texto).replace("\r\n", "\n").strip().split("\n"))


def marcar_faltantes(ficha: dict) -> None:
    """Un obligatorio vacío queda marcado «Falta definir» (SPEC §3)."""
    for campo, seccion in plantillas.campos_de(ficha["tipo"]):
        if plantillas.es_obligatorio(campo, seccion) and not valor(ficha, campo.id):
            if (ficha["campos"].get(campo.id) or {}).get("estado") != CONFLICTO:
                ficha["campos"][campo.id] = {"valor": "", "origen": "", "estado": FALTA_DEFINIR}


# ---------- Revisión ----------

def materiales_de_la_sesion(ficha_sesion: dict) -> set[str]:
    """Materiales que se producen. Vacío, «los cuatro», o «los cinco» y «los seis» de fichas anteriores, significa todos."""
    texto = valor(ficha_sesion, "materiales.cuales").lower()
    if not texto.strip() or re.search(r"\b(cuatro|cinco|seis|todos)\b", texto):
        return set(MATERIALES)
    sin_tildes = texto.replace("í", "i").replace("á", "a").replace("ó", "o")
    claves = {"lectura": "lectura", "diapositiva": "diapositivas", "laboratorio": "laboratorio",
              "evaluacion": "evaluación"}
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
    """Lo que se exige para confirmar la ficha de la sesión. Los datos de cada material se exigen al
    producir ese material (PLAN.md §0, decisión 16): ver errores_del_material()."""
    if not vocabulario(ficha):
        return [SIN_VOCABULARIO]
    return []


SIN_VOCABULARIO = "Escribe al menos un concepto clave del vocabulario."


def errores_del_material(ficha: dict, material: str) -> list[str]:
    """Lo que le falta a la ficha de la sesión para producir un material."""
    if material not in materiales_de_la_sesion(ficha):
        return [f"«Materiales de esta sesión» no incluye {material}."]
    lista = []
    # Sin lectura en la sesión, las diapositivas salen de las fichas y de la referencia: piden lo mismo que
    # pediría la lectura (PLAN.md §0, decisión 26).
    sin_lectura = material == "diapositivas" and "lectura" not in materiales_de_la_sesion(ficha)
    if material == "lectura" or sin_lectura:
        # Con material de referencia, los bloques salen de sus temas (PLAN.md §0, decisión 23).
        bloques = [n for n in range(1, 5) if valor(ficha, f"lectura.bloque.{n}")]
        if len(bloques) < 2 and not valor(ficha, "sesion.referencia").strip():
            quien = "La lectura necesita" if material == "lectura" else "Sin lectura, las diapositivas necesitan"
            lista.append(f"{quien} de 2 a 4 bloques, o un material de referencia.")
        riesgos = _renglones(valor(ficha, "lectura.cuidado"))
        if not 1 <= len(riesgos) <= 3:
            lista.append("«Cuidado con» necesita de 1 a 3 riesgos, uno por línea.")
    if material == "laboratorio":
        ids = ("area", "accion", "entregable", "archivo", "problema", "respuesta")
        ejercicios = bloques_llenos(ficha, "ejercicio", plantillas.MAX_EJERCICIOS, ids)
        if not 3 <= len(ejercicios) <= 5:
            lista.append(f"El laboratorio necesita de 3 a 5 ejercicios; tiene {len(ejercicios)}.")
        for n in ejercicios:
            for campo_id, nombre in (("archivo", "el archivo de práctica"), ("problema", "el problema que trae a propósito"),
                                     ("respuesta", "la respuesta correcta"), ("accion", "la acción del alumno")):
                if not valor(ficha, f"ejercicio.{n}.{campo_id}"):
                    lista.append(f"Ejercicio {n}: falta {nombre}.")
    if material == "evaluación":
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


def faltantes_para(carpeta_curso: Path, sesion: int, material: str) -> list[str]:
    """Lo que falta para producir un material: las dos fichas confirmadas y los datos de ese material."""
    if not puede_empezar_material(carpeta_curso, sesion):
        return ["Guarda completas la ficha del curso y la ficha de la sesión: al guardarlas completas quedan confirmadas."]
    from app.fichas import referencia   # importa este módulo: se carga aquí para no formar un círculo
    ficha = cargar(carpeta_curso, "sesion", sesion)
    return errores_del_material(ficha, material) + referencia.interpretar(carpeta_curso, ficha)[1]


def agregar_datos_fijos(carpeta_curso: Path, lineas: list[str], origen: str) -> list[str]:
    """Agrega datos nuevos del caso a la ficha del curso (SKILL.md, Paso 1.9).

    Solo agrega: la ficha sigue confirmada y los materiales no quedan desactualizados.
    Cada dato agregado queda registrado con su origen.
    """
    ficha = cargar(carpeta_curso, "curso")
    actuales = _renglones(valor(ficha, "datos.fijos"))
    vistos = {" ".join(l.lower().split()) for l in actuales}
    nuevos = []
    for linea in lineas:
        limpia = " ".join(linea.strip().lstrip("-• ").split())
        etiqueta, separador, dato = limpia.partition(":")
        if separador and etiqueta.strip() and dato.strip() and limpia.lower() not in vistos:
            nuevos.append(limpia)
            vistos.add(limpia.lower())
    if not nuevos:
        return []
    anterior = ficha["campos"].get("datos.fijos") or {"origen": PROFESOR, "estado": ""}
    ficha["campos"]["datos.fijos"] = {**anterior, "valor": "\n".join(actuales + nuevos)}
    ficha.setdefault("datos_agregados", []).extend(
        {"linea": l, "origen": origen, "fecha": datetime.now().isoformat(timespec="seconds")} for l in nuevos)
    guardar(carpeta_curso, "curso", None, ficha, "datos nuevos del caso")
    return nuevos
