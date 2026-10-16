"""Controles del formulario de las fichas (PLAN.md §0, decisión 27).

Cada control escribe en la ficha el mismo texto que antes se escribía a mano, así que la plantilla,
el verificador y los generadores leen la ficha igual. Tipos:
- "lista": una opción de una lista, con «Otro…» si se permite escribir otra.
- "opciones": botones de opción (sí, no, no sé).
- "casillas": varias opciones marcadas, más «Otros» si se permite.
- "color": un color en hexadecimal; el primero muestra también las paletas listas.
- "logo": un archivo PNG o JPG que se sube a la carpeta del curso, o «sin logo».
- "archivos": uno o varios PDF que se suben a cursos/[curso]/modelos/.
- "numero": un número entero positivo.
"""

import re
from pathlib import Path

from app.materiales.catalogo import ESTILOS, PALETAS

OTRO = "__otro"
SIN_LOGO = "sin logo"
SEPARADOR_ARCHIVOS = "; "
CARPETA_MODELOS = "modelos"
EXTENSIONES_LOGO = (".png", ".jpg", ".jpeg")

# Sin práctica interactiva ni guía del profesor (PLAN.md §0, decisiones 34 y 35).
MATERIALES = ("lectura", "diapositivas", "laboratorio", "evaluación")
TODOS_LOS_MATERIALES = "los cuatro"
NUNCA_POR_OMISION = ("tiempos", "puntajes", "objetivos de aprendizaje", "requisitos previos", "glosarios",
                     "relleno", "emojis", "lenguaje publicitario")

TIPOGRAFIAS = ("Calibri", "Aptos", "Segoe UI", "Arial", "Verdana", "Cambria", "Georgia", "Garamond")
IDIOMAS = ("Español", "Inglés", "Portugués", "Francés")

POR_OMISION_DEL_CURSO = {
    "portada.docente": "José Fernando Davelouis Mendía",
    "portada.contacto": "www.linkedin.com/in/jdavelouis; info@futurasoft.net",
}

_COLOR = {"tipo": "color"}

CONTROLES = {
    "curso.idioma": {"tipo": "lista", "opciones": IDIOMAS, "otro": True},
    "curso.horas": {"tipo": "numero", "titulo": "Horas del curso",
                    "ayuda": "Solo sirve para repartir el tema en sesiones. Ningún material muestra tiempos."},
    "curso.numero_sesiones": {"tipo": "numero", "titulo": "Número de sesiones"},
    "visual.logo": {"tipo": "logo", "titulo": "Logo",
                    "ayuda": "Sube un PNG o JPG. Queda guardado en la carpeta del curso."},
    "visual.principal": {"tipo": "color", "paletas": True,
                         "ayuda": "Elige una paleta lista o cambia cada color. Máximo tres colores, más el fondo de "
                                  "los recuadros y el texto. Vacío: se toman del modelo o se usa la paleta sobria."},
    "visual.acento": _COLOR,
    "visual.advertencia": _COLOR,
    "visual.fondos": _COLOR,
    "visual.texto": _COLOR,
    "visual.tipografia": {"tipo": "lista", "opciones": TIPOGRAFIAS, "otro": True, "por_omision": "Calibri",
                          "ayuda": "Fuentes que vienen con Office. Por defecto: la del modelo en PDF; sin modelo, Calibri."},
    "visual.estilo": {"tipo": "lista", "titulo": "Estilo", "opciones": tuple(ESTILOS), "otro": False,
                      "por_omision": "profesional",
                      "descripciones": {nombre: e.descripcion for nombre, e in ESTILOS.items()},
                      "ayuda": "Cambia la portada, los títulos, los recuadros y el tono."},
    "herramientas.ejercicios": {
        "tipo": "opciones", "titulo": "¿Con qué herramienta hace el alumno los ejercicios?",
        "opciones": (("ninguna", "Ninguna: el alumno hace la tarea a mano en el archivo de práctica (Excel o Word)"),
                     ("Excel", "Excel: los ejercicios usan fórmulas, porque el curso trata de Excel"),
                     ("IA", "IA: los ejercicios usan prompts, porque el curso trata de IA"),
                     ("Excel e IA", "Excel e IA: fórmulas y prompts, porque el curso trata de los dos")),
        "ayuda": "Sale del tema del curso, no de los modelos. Vacío: ninguna.",
    },
    "herramientas.neutral": {
        "tipo": "opciones", "titulo": "¿El material habla en general o nombra una herramienta?",
        "opciones": (("sí", "Hablar en general, sin nombrar productos («una IA generativa», «una hoja de cálculo»)"),
                     ("no", "Nombrar la herramienta exacta que usan los alumnos")),
        "ayuda": "Decide si el material nombra marcas. Si eliges nombrarla, escribe abajo cuál.",
    },
    "herramientas.cual": {"tipo": "texto", "titulo": "Herramienta y versión que usan los alumnos", "depende": ("herramientas.neutral", "no"),
                          "ayuda": "Por ejemplo: «Microsoft Copilot en Word 365». El laboratorio se escribe para ella."},
    "herramientas.adjuntos": {
        "tipo": "opciones", "titulo": "¿La herramienta de los alumnos acepta archivos adjuntos?",
        "opciones": (("sí", "Sí: el ejercicio dice «adjunta el archivo»"),
                     ("no", "No: el alumno copia el texto del archivo y lo pega en el mensaje"),
                     ("no sé", "No sé: se dan las dos formas")),
        "ayuda": "Decide cómo usan los ejercicios los archivos de práctica.",
    },
    "materiales.por_sesion": {"tipo": "casillas", "titulo": "Materiales por sesión", "opciones": MATERIALES, "todos": TODOS_LOS_MATERIALES,
                              "ayuda": "La evaluación no se genera (decisión 37)."},
    "materiales.nunca": {"tipo": "casillas", "titulo": "Lo que nunca se incluye", "opciones": NUNCA_POR_OMISION, "otros": True, "omision": True,
                         "ayuda": "Marcadas por defecto. Agrega otras en «Otros», separadas por comas."},
    "materiales.cuales": {"tipo": "casillas", "titulo": "Materiales que se producen en esta sesión", "opciones": MATERIALES, "todos": TODOS_LOS_MATERIALES,
                          "ayuda": "Sin ninguna marcada se producen todos los que AulaLista genera: lectura, "
                                   "diapositivas y laboratorio. La evaluación no se genera (decisión 37)."},
    "modelos.aprobados": {"tipo": "archivos", "titulo": "Modelos de diseño y tono (PDF)", "extension": ".pdf",
                          "ayuda": "Sube uno o varios PDF. Dan los colores y la tipografía que la ficha deja vacíos, "
                                   "y guían el tono. Las secciones de cada material siguen siendo las de la skill."},
}


# ---------- Del valor guardado al control ----------

def _partes(texto: str) -> list[str]:
    return [p.strip(" .").lower() for p in re.split(r",|;|\by\b|\n", texto or "") if p.strip(" .")]


def marcadas(campo_id: str, valor: str) -> tuple[list[str], str]:
    """Casillas marcadas y el resto escrito a mano. Vacío marca todas (es el valor por defecto)."""
    control = CONTROLES[campo_id]
    opciones = list(control["opciones"])
    if not (valor or "").strip() or (control.get("todos") and (control["todos"] in valor.lower() or re.search(r"\blos (cinco|seis)\b", valor.lower()))):
        return opciones, ""
    partes = _partes(valor)
    elegidas = [o for o in opciones if any(_coincide(o, p) for p in partes)]
    otros = [p for p in partes if not any(_coincide(o, p) for o in opciones)]
    return elegidas, ", ".join(otros)


def _coincide(opcion: str, parte: str) -> bool:
    sin = str.maketrans("áéíóú", "aeiou")
    a, b = opcion.lower().translate(sin), parte.lower().translate(sin)
    return a == b or a.rstrip("s") == b.rstrip("s") or (a.split()[0] in b.split() and len(a.split()) > 1)


def archivos_de(valor: str) -> list[str]:
    return [p.strip() for p in re.split(r";|\n", valor or "") if p.strip()]


def _sin_tildes(texto: str) -> str:
    return (texto or "").strip().lower().translate(str.maketrans("áéíóú", "aeiou"))


def elegida(campo_id: str, valor: str) -> str | None:
    """La opción que corresponde al valor guardado, sin importar mayúsculas ni tildes.

    "" es la opción por defecto (valor vacío o igual al de por defecto). None: no es ninguna opción.
    En los botones de opción vale también un valor que empieza con la opción («Sí, es neutral»).
    """
    control = CONTROLES[campo_id]
    texto = _sin_tildes(valor)
    if not texto or texto == _sin_tildes(control.get("por_omision", "")):
        return ""
    if control["tipo"] == "lista":
        return next((o for o in control["opciones"] if _sin_tildes(o) == texto), None)
    if control["tipo"] == "opciones":
        for opcion, _ in sorted(control["opciones"], key=lambda o: -len(o[0])):
            clave = _sin_tildes(opcion)
            if texto == clave or re.match(rf"{re.escape(clave)}\b", texto):
                return opcion
    return None


def equivalente(campo_id: str, nuevo: str, anterior: str) -> bool:
    """El control muestra lo mismo para los dos valores: guardar sin tocarlo no cambia el dato ni su origen."""
    control = CONTROLES.get(campo_id)
    if control is None or not anterior:
        return False
    if control["tipo"] in ("lista", "opciones"):
        actual = elegida(campo_id, anterior)
        return actual is not None and actual == elegida(campo_id, nuevo)
    if control["tipo"] == "casillas":
        return marcadas(campo_id, nuevo) == marcadas(campo_id, anterior)
    return False


def vista(campo_id: str, valor: str) -> dict | None:
    """Datos que necesita la página para dibujar el control, o None si el campo sigue siendo texto."""
    control = CONTROLES.get(campo_id)
    if control is None:
        return None
    datos = dict(control)
    if control["tipo"] in ("lista", "opciones"):
        datos["elegida"] = elegida(campo_id, valor)
        datos["es_otro"] = datos["elegida"] is None
        por_omision = _sin_tildes(control.get("por_omision", ""))
        datos["opciones"] = [o for o in control["opciones"]
                             if control["tipo"] == "opciones" or _sin_tildes(o) != por_omision]
    elif control["tipo"] == "casillas":
        datos["marcadas"], datos["texto_otros"] = marcadas(campo_id, valor)
    elif control["tipo"] == "archivos":
        datos["archivos"] = archivos_de(valor)
    elif control["tipo"] == "color":
        color = re.search(r"#?\b([0-9A-Fa-f]{6})\b", valor or "")
        datos["hex"] = f"#{color.group(1).upper()}" if color else ""
        if control.get("paletas"):
            datos["paletas"] = PALETAS
    return datos


# ---------- Del formulario al valor guardado ----------

def _nombre_seguro(nombre: str) -> str:
    nombre = Path(nombre or "").name
    return re.sub(r"[^\w.\- ]", "_", nombre).strip() or "archivo"


async def leer(formulario, carpeta_curso: Path) -> dict:
    """Convierte el formulario (con varios valores por nombre y archivos) en {campo: texto}.

    Los campos sin control pasan tal cual. Los archivos se guardan en la carpeta del curso.
    """
    resultado = {}
    for clave in formulario.keys():
        # Las partes de un control («visual.logo.archivo») no son campos. «ejercicio.1.archivo» sí es un campo.
        base, _, parte = clave.rpartition(".")
        if base in CONTROLES and parte in ("otro", "otros", "casillas", "archivo", "archivos", "quitar"):
            continue
        valores = formulario.getlist(clave)
        if len(valores) == 1 and isinstance(valores[0], str):
            resultado[clave] = valores[0]
    for campo_id, control in CONTROLES.items():
        tipo = control["tipo"]
        if tipo == "lista" and resultado.get(campo_id) == OTRO:
            resultado[campo_id] = str(formulario.get(f"{campo_id}.otro", "")).strip()
        elif tipo == "casillas" and f"{campo_id}.casillas" in formulario:
            resultado[campo_id] = _texto_de_casillas(control, formulario.getlist(campo_id),
                                                     str(formulario.get(f"{campo_id}.otros", "")))
        elif tipo == "logo" and campo_id in formulario:
            subido = await _guardar(formulario.get(f"{campo_id}.archivo"), carpeta_curso, EXTENSIONES_LOGO)
            if subido:
                resultado[campo_id] = subido
        elif tipo == "archivos" and f"{campo_id}.casillas" in formulario:
            quedan = [a for a in archivos_de(str(formulario.get(campo_id, ""))) if a not in formulario.getlist(f"{campo_id}.quitar")]
            for archivo in formulario.getlist(f"{campo_id}.archivos"):
                subido = await _guardar(archivo, carpeta_curso / CARPETA_MODELOS, (control["extension"],))
                if subido and subido not in quedan:
                    quedan.append(subido)
            resultado[campo_id] = SEPARADOR_ARCHIVOS.join(quedan)
    return resultado


def _texto_de_casillas(control: dict, elegidas: list, otros: str) -> str:
    opciones = list(control["opciones"])
    elegidas = [o for o in opciones if o in elegidas]
    extra = [p.strip() for p in re.split(r",|;", otros or "") if p.strip()]
    if control.get("todos") and (elegidas == opciones or not elegidas) and not extra:
        return ""  # vacío vale «los cuatro» (SKILL.md, plantilla de la ficha; PLAN.md §0, decisiones 34 y 35)
    if control.get("omision") and elegidas == opciones and not extra:
        return ""  # vacío vale la lista por defecto de la plantilla
    partes = elegidas + extra
    return ", ".join(partes[:-1]) + (" y " if len(partes) > 1 else "") + partes[-1] if partes else ""


async def _guardar(archivo, carpeta: Path, extensiones: tuple[str, ...]) -> str:
    """Guarda un archivo subido. Devuelve su nombre, o "" si no hay archivo o la extensión no sirve."""
    if archivo is None or isinstance(archivo, str) or not getattr(archivo, "filename", ""):
        return ""
    nombre = _nombre_seguro(archivo.filename)
    if Path(nombre).suffix.lower() not in extensiones:
        return ""
    contenido = await archivo.read()
    if not contenido:
        return ""
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / nombre).write_bytes(contenido)
    return nombre
