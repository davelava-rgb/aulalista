"""Material 6 · Evaluación práctica (PBQ) y su clave (SKILL.md, «Material 6»; PLAN.md §0, decisión 64; etapa 9).

La página del material llega en la fase 9d: mientras tanto la evaluación no se registra en la interfaz (decisión 46).

Flujo, igual al del laboratorio:
1. Comprueba las dos fichas confirmadas, las preguntas de la ficha y la lectura y el laboratorio aprobados y al día
   (decisión 64 a): la evaluación no evalúa nada que no hayan enseñado.
2. El agente escribe las preguntas, sus archivos y la clave como datos (contenido.Evaluacion).
3. Un programa crea la hoja del alumno, la clave y el .zip de los archivos, y el verificador los revisa con los
   controles propios de la evaluación (fase 9b). Hasta tres correcciones.
4. Revisión del contenido por pregunta, una sola corrección y la confirmación de lo que cambió (decisión 22).
5. Cada pregunta la resuelve Claude como un alumno, sin la clave, y lo que sale se compara con la clave y con la
   respuesta de la ficha (decisión 64 e). Una diferencia con prueba queda pendiente; una sin prueba se descarta.
"""

import asyncio
import json
import re
import shutil
import unicodedata
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from app import agente, entrega, skill, tokens
from app.fichas import almacen, dependencias, plantillas, referencia, verificacion
from app.materiales import actividad, comun, docx, ejecucion, estilo, laboratorio, lectura, practica
from app.materiales.contenido import ESQUEMA_EVALUACION, TAREAS_DE_EVALUACION, ArchivoPractica, Evaluacion, Laboratorio
from app.validacion import excel, pasada2, revision, revisor, verificador
from app.validacion.pasajes import Corpus

Hallazgo = verificador.verificar.Hallazgo
FALLA, AVISO = verificador.verificar.FALLA, verificador.verificar.AVISO

# Tamaño de la evaluación (SKILL.md, «Tamaño de la evaluación»; decisión 64 c).
PALABRAS_MAX = 250        # la situación y los archivos de texto de una pregunta
FILAS_MAX = 15            # cada tabla: la de respuesta, las de los Word y las hojas de los Excel
DECISIONES_MAX = 10       # las celdas que el alumno llena en su tabla de respuesta
PREGUNTAS_POR_OMISION = 3

MATERIAL = "Evaluacion"
CLAVE = "evaluacion"
CARPETA_ARCHIVOS = "materiales/_trabajo/evaluacion/archivos"   # relativa a la carpeta de la sesión, para el verificador
VUELTAS_DEL_VERIFICADOR = comun.VUELTAS_DEL_VERIFICADOR
SECCIONES_DE_LA_SKILL = ("Reglas comunes", "Paso 3 · Vocabulario de la sesión", "Material 6 · Evaluación práctica (PBQ)")
# Lo que se corrige por oraciones no toca nombres, números, la tabla de respuesta ni la clave: una celda cambiada
# descuadraría la pregunta. Esos problemas van a una corrección completa.
CAMPOS_QUE_NO_SE_CORRIGEN = comun.CAMPOS_QUE_NO_SE_CORRIGEN | {
    "nombre", "numero", "archivos", "archivo", "hoja", "hojas", "tarea", "encabezados", "filas", "respuesta",
    "aceptadas", "concepto"}
ESQUEMA_CORRECCION = comun.esquema_de_correccion(CLAVE, ESQUEMA_EVALUACION)
ESQUEMA_CORRECCIONES = comun.esquema_de_correcciones(completa=ESQUEMA_CORRECCION, oraciones=comun.ESQUEMA_CAMBIOS)


class NoSePuedeEmpezar(RuntimeError):
    """Faltan las fichas confirmadas, las preguntas de la ficha, o la lectura o el laboratorio aprobados."""


class NoSePuedeRevisar(RuntimeError):
    """El revisor independiente opcional necesita una evaluación generada sin fallas abiertas."""


class NoSePuedeAprobar(RuntimeError):
    """La evaluación tiene fallas abiertas, está desactualizada o no se generó."""


def archivos(carpeta_curso: Path, sesion: int) -> dict[str, Path]:
    """La hoja del alumno, la clave, el .zip de sus archivos (aparte del del laboratorio) y el Excel de verificación
    van a materiales/; lo que usa AulaLista, a su carpeta de trabajo (decisión 64 d)."""
    carpeta = lectura.carpeta_materiales(carpeta_curso, sesion)
    trabajo = carpeta / comun.TRABAJO / CLAVE
    return {
        "word": carpeta / f"S{sesion}_Evaluacion.docx",
        "clave": carpeta / f"S{sesion}_Evaluacion_Clave.docx",
        "zip": carpeta / f"S{sesion}_Evaluacion_Archivos.zip",
        "excel": carpeta / f"S{sesion}_Evaluacion_Verificacion.xlsx",
        "verificacion_json": trabajo / "verificacion.json",
        "archivos": trabajo / "archivos",
        "revision": trabajo / "revisor",
        "contenido": trabajo / "contenido.json",
        "ejecucion": trabajo / "ejecucion",
        "ejecucion_json": trabajo / "ejecucion.json",
        "registro": carpeta / f"S{sesion}_Evaluacion_Ejecucion.md",
        "explicaciones": trabajo / "explicaciones.json",
        "sistema": trabajo / "sistema_correccion.txt",
    }


# ---------- Estado ----------

def estado(carpeta_curso: Path, sesion: int) -> dict:
    """El estado guardado. Si la lectura o el laboratorio se generaron de nuevo después de esta evaluación, queda
    desactualizada: los dos son su fuente (decisión 64 g)."""
    material = comun.estado(carpeta_curso, sesion, CLAVE)
    if dependencias.lectura_nueva(carpeta_curso, sesion, material) or \
            dependencias.laboratorio_nuevo(carpeta_curso, sesion, material):
        return {**material, "desactualizado": True}
    return material


def gasto_de_la_corrida(carpeta_curso: Path, curso: str, sesion: int) -> dict | None:
    return comun.gasto_de_la_corrida(carpeta_curso, curso, sesion, CLAVE)


def marcar_detenida(carpeta_curso: Path, sesion: int) -> bool:
    return comun.marcar_detenida(carpeta_curso, sesion, CLAVE)


def _aprobado_y_al_dia(modulo, carpeta_curso: Path, sesion: int, el: str, verbo: str) -> list[str]:
    """Lo que falta de un material que la evaluación usa como fuente: aprobado y sin cambios después."""
    material = modulo.estado(carpeta_curso, sesion)
    if material.get("estado") != "aprobada":
        return [f"Aprueba primero {el}: la evaluación no evalúa nada que no se haya enseñado."]
    if material.get("desactualizado"):
        return [f"{el[:1].upper()}{el[1:]} está desactualizad{'o' if el.startswith('el ') else 'a'}: {verbo} y "
                f"apruéba{'lo' if el.startswith('el ') else 'la'} de nuevo."]
    return []


def faltan(carpeta_curso: Path, sesion: int) -> dict[str, list[str]]:
    """En «ficha», lo que se completa en la ficha de la sesión. En «otros», la lectura y el laboratorio aprobados y al
    día, si la sesión los produce (decisión 64 a). Lo de la ficha va primero: sin preguntas, lo demás no importa."""
    ficha = almacen.faltantes_para(carpeta_curso, sesion, CLAVE)
    if ficha:
        return {"ficha": ficha, "otros": []}
    incluidos = almacen.materiales_de_la_sesion(almacen.cargar(carpeta_curso, "sesion", sesion))
    otros = []
    if lectura.CLAVE in incluidos:
        otros += _aprobado_y_al_dia(lectura, carpeta_curso, sesion, "la lectura", "genérala")
    if laboratorio.CLAVE in incluidos:
        otros += _aprobado_y_al_dia(laboratorio, carpeta_curso, sesion, "el laboratorio", "genéralo")
    return {"ficha": [], "otros": otros}


# ---------- Archivos (fase 9b) ----------

def crear_archivos(contenido: Evaluacion, identidad: estilo.Identidad, portada: docx.Portada, rutas: dict[str, Path],
                   sesion: int) -> list[str]:
    """Los archivos de cada pregunta, la hoja del alumno, la clave y el .zip de los archivos. Devuelve los problemas
    que encuentra al empaquetar."""
    rutas_archivos = practica.crear(contenido, identidad, rutas["archivos"])
    docx.generar_evaluacion(contenido, identidad, docx.Portada(**{**portada.__dict__, "material": "Evaluación práctica"}),
                            rutas["word"], nombre_zip=rutas["zip"].name, sesion=sesion)
    docx.generar_clave(contenido, identidad, docx.Portada(**{**portada.__dict__, "material": "Clave de la evaluación"}),
                       rutas["clave"], sesion=sesion)
    practica.empaquetar(rutas_archivos, rutas["zip"])
    en_zip, nombres = practica.nombres_del_zip(rutas["zip"]), sorted(a.nombre for a in contenido.archivos)
    if en_zip != nombres:
        return [f"FALLA · nombre de archivo · el .zip trae {en_zip}; la hoja del alumno nombra {nombres}."]
    return []


# ---------- Controles propios (decisión 64 c y f) ----------

def _plano(texto: str) -> str:
    """Minúsculas, sin tildes y sin signos: para buscar una respuesta sin que la delate una coma."""
    descompuesto = unicodedata.normalize("NFD", (texto or "").lower())
    sin_tildes = "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9ñ]+", " ", sin_tildes).split())


def _palabras(texto: str) -> int:
    return len(re.findall(r"\w+", texto or ""))


def _texto_word(archivo: ArchivoPractica) -> str:
    partes = [p.texto for p in archivo.parrafos]
    if archivo.tabla:
        partes += [c for f in archivo.tabla.filas for c in f]
    return " ".join(partes)


def _lo_que_ve_el_alumno(contenido: Evaluacion) -> str:
    """La hoja del alumno y sus archivos, sin la clave ni el problema sembrado (que el alumno no lee)."""
    partes = [contenido.indicaciones.consulta, contenido.indicaciones.entrega]
    for p in contenido.preguntas:
        partes += [p.titulo, p.situacion, *p.pasos, p.tabla_de_respuesta.titulo,
                   *p.tabla_de_respuesta.encabezados, *[c for f in p.tabla_de_respuesta.filas for c in f]]
    for a in contenido.archivos:
        partes += [a.descripcion, practica._texto_de_archivo(a)]
    return _plano(" ".join(partes))


def respuestas(p) -> list[str]:
    """Lo que delata la respuesta de una pregunta: cada fila completa de la clave que el alumno tenía que llenar, y
    cada respuesta aceptada. Una fila de una sola celda corta (un número, una palabra) no sirve para buscar: es
    normal que aparezca en otros textos."""
    encontradas = []
    for dada, completa in zip(p.tabla_de_respuesta.filas, p.clave.respuesta):
        if all(c.strip() for c in dada):
            continue                                  # la fila ya venía llena: no es respuesta
        texto = _plano(" ".join(completa))
        if len(completa) > 1 or len(texto) >= 12:
            encontradas.append(texto)
    encontradas += [_plano(t) for t in p.clave.aceptadas if len(_plano(t)) >= 12]
    return [t for t in encontradas if t]


def _textos_de_strings(datos) -> list[str]:
    if isinstance(datos, str):
        return [datos]
    if isinstance(datos, dict):
        return [t for v in datos.values() for t in _textos_de_strings(v)]
    if isinstance(datos, list):
        return [t for v in datos for t in _textos_de_strings(v)]
    return []


def textos_de_otros(carpeta_curso: Path, sesion: int) -> dict[str, str]:
    """El texto de la guía del laboratorio y de la actividad web ya generados, para comprobar que ninguno da una
    respuesta de la evaluación (decisión 64 f)."""
    otros = {}
    for nombre, modulo in (("la guía del laboratorio", laboratorio), ("la actividad web", actividad)):
        ruta = modulo.archivos(carpeta_curso, sesion)["contenido"]
        if ruta.exists():
            otros[nombre] = _plano(" ".join(_textos_de_strings(json.loads(ruta.read_text(encoding="utf-8")))))
    return otros


def archivos_del_laboratorio(carpeta_curso: Path, sesion: int) -> list[ArchivoPractica]:
    ruta = laboratorio.archivos(carpeta_curso, sesion)["contenido"]
    if not ruta.exists():
        return []
    try:
        return Laboratorio.model_validate(json.loads(ruta.read_text(encoding="utf-8"))).archivos
    except ValueError:
        return []


def _datos(archivo: ArchivoPractica) -> list[str]:
    """Las filas de datos de un archivo (o sus párrafos), cada una en texto plano: para ver si se repiten."""
    filas = [_plano(" ".join(str(v) for v in f if v is not None)) for h in archivo.hojas for f in h.filas]
    filas += [_plano(p.texto) for p in archivo.parrafos]
    if archivo.tabla:
        filas += [_plano(" ".join(f)) for f in archivo.tabla.filas]
    return [f for f in filas if f]


def controles(contenido: Evaluacion, preguntas_esperadas: int, otros: dict[str, str] | None = None,
              del_laboratorio: list[ArchivoPractica] | None = None) -> list:
    """Lo que el verificador no sabe medir y AulaLista sí: el tamaño de cada pregunta (decisión 64 c), la cantidad
    de preguntas, que ninguna respuesta se vea fuera de la clave y que los archivos sean nuevos (decisión 64 f).
    Devuelve hallazgos del verificador, para que vayan al mismo Excel."""
    hallazgos = []

    def agregar(nivel, seccion, regla, detalle, oracion=""):
        hallazgos.append(Hallazgo(nivel, seccion, oracion, regla, detalle))

    if len(contenido.preguntas) != preguntas_esperadas:
        agregar(FALLA, "Evaluación", "cantidad de preguntas",
                f"la ficha pide {preguntas_esperadas} preguntas y la evaluación tiene {len(contenido.preguntas)}")
    por_nombre = {a.nombre: a for a in contenido.archivos}
    tamanos = []
    for p in contenido.preguntas:
        seccion = f"Pregunta {p.numero}"
        archivos_ = [por_nombre[n] for n in p.archivos if n in por_nombre]
        palabras = _palabras(p.situacion) + sum(_palabras(_texto_word(a)) for a in archivos_ if a.extension == "docx")
        if palabras > PALABRAS_MAX:
            agregar(FALLA, seccion, "tamaño de la pregunta",
                    f"la situación y los archivos de texto suman {palabras} palabras; el máximo es {PALABRAS_MAX}")
        tablas = [("la tabla de respuesta", len(p.tabla_de_respuesta.filas))]
        tablas += [(f"la hoja {h.nombre} de {a.nombre}", len(h.filas)) for a in archivos_ for h in a.hojas]
        tablas += [(f"la tabla de {a.nombre}", len(a.tabla.filas)) for a in archivos_ if a.tabla]
        for donde, filas in tablas:
            if filas > FILAS_MAX:
                agregar(FALLA, seccion, "tamaño de la pregunta", f"{donde} tiene {filas} filas; el máximo es {FILAS_MAX}")
        decisiones = p.tabla_de_respuesta.por_llenar
        tamanos.append(decisiones)
        if decisiones > DECISIONES_MAX:
            agregar(FALLA, seccion, "tamaño de la pregunta",
                    f"el alumno llena {decisiones} celdas, y cada una es una decisión; el máximo es {DECISIONES_MAX}")
    if len(tamanos) > 1 and min(tamanos) and max(tamanos) > 2 * min(tamanos):
        agregar(AVISO, "Evaluación", "tamaño parecido",
                f"una pregunta pide {max(tamanos)} decisiones y otra {min(tamanos)}: las preguntas deben tener un "
                "tamaño parecido")

    alumno = _lo_que_ve_el_alumno(contenido)
    for p in contenido.preguntas:
        for respuesta in respuestas(p):
            for donde, texto in [("la hoja del alumno o sus archivos", alumno), *(otros or {}).items()]:
                if respuesta in texto:
                    agregar(FALLA, f"Pregunta {p.numero}", "respuesta fuera de la clave",
                            f"la respuesta aparece en {donde}", oracion=respuesta)

    del_lab = {a.nombre: set(_datos(a)) for a in (del_laboratorio or [])}
    for archivo in contenido.archivos:
        datos = set(_datos(archivo))
        if not datos:
            continue
        for nombre, otros_datos in del_lab.items():
            repetidos = datos & otros_datos
            if repetidos == datos:
                agregar(FALLA, archivo.nombre, "archivo del laboratorio",
                        f"trae los mismos datos que {nombre}: la evaluación usa archivos y datos nuevos")
            elif len(repetidos) * 2 >= len(datos):
                agregar(AVISO, archivo.nombre, "datos del laboratorio",
                        f"repite {len(repetidos)} de sus {len(datos)} filas de {nombre}")
    return hallazgos


def preguntas_de_la_ficha(carpeta_curso: Path, sesion: int) -> int:
    """La cantidad de preguntas: las que trae la ficha de la sesión o, si no trae ninguna, 3 (SKILL.md)."""
    ficha = almacen.cargar(carpeta_curso, "sesion", sesion)
    ids = ("concepto", "tarea", "archivo", "problema", "respuesta")
    return len(almacen.bloques_llenos(ficha, "pregunta", plantillas.MAX_PREGUNTAS, ids)) or PREGUNTAS_POR_OMISION


def armar_y_verificar(carpeta_curso: Path, sesion: int, contenido: Evaluacion,
                      explicaciones: dict | None = None) -> tuple[list[str], object]:
    """Fase 9b, sin IA: crea los archivos desde un contenido ya escrito y corre el verificador con los controles
    propios. Devuelve los problemas de empaquetar y el resultado del verificador. La fase 9c le pone delante la
    redacción y detrás la revisión del contenido y la ejecución."""
    rutas = archivos(carpeta_curso, sesion)
    shutil.rmtree(rutas["archivos"], ignore_errors=True)
    portada = lectura._portada(carpeta_curso, sesion)
    problemas = crear_archivos(contenido, estilo.desde_ficha(carpeta_curso), portada, rutas, sesion)
    configuracion = verificador.configuracion_del_material(
        almacen.carpeta_sesion(carpeta_curso, sesion), MATERIAL, carpeta_practica=CARPETA_ARCHIVOS)
    extra = controles(contenido, preguntas_de_la_ficha(carpeta_curso, sesion), textos_de_otros(carpeta_curso, sesion),
                      archivos_del_laboratorio(carpeta_curso, sesion))
    resultado = verificador.ejecutar(
        configuracion, [rutas["word"], rutas["clave"], *sorted(rutas["archivos"].iterdir()), rutas["zip"]],
        rutas["excel"], explicaciones, hallazgos_extra=extra, salida_json=rutas["verificacion_json"])
    return problemas, resultado


# ---------- Pedidos al agente (fase 9c) ----------

def _aprobado(modulo, carpeta_curso: Path, sesion: int) -> dict | None:
    rutas = modulo.archivos(carpeta_curso, sesion)
    if modulo.estado(carpeta_curso, sesion).get("estado") != "aprobada" or not rutas["contenido"].exists():
        return None
    return comun.leer_json(rutas["contenido"])


def _contexto(carpeta_curso: Path, sesion: int, pasajes: list[str] | None = None) -> str:
    """Las reglas, las fichas, las fuentes y lo ya aprobado de la sesión: la evaluación solo evalúa lo que enseñaron
    la lectura y el laboratorio, y no repite sus ejercicios ni las preguntas de la actividad web."""
    ficha_curso = almacen.texto_para_materiales(carpeta_curso, "curso")
    ficha_sesion = almacen.texto_para_materiales(carpeta_curso, "sesion", sesion)
    fuentes = verificacion.fuentes_utilizables(carpeta_curso)
    partes = [
        "REGLAS DE LA SKILL (son obligatorias):",
        skill.secciones(*SECCIONES_DE_LA_SKILL),
        "",
        "FICHA DEL CURSO (confirmada):", ficha_curso,
        "FICHA DE LA SESIÓN (confirmada):", ficha_sesion,
        estilo.guia_de_tono(carpeta_curso),
        "FUENTES DEL CURSO que puedes citar (archivos .jsonl de esta carpeta, un pasaje por línea con su ubicación):",
        *([f"- {f}" for f in fuentes] or ["- (ninguna: no cites fuentes)"]),
    ]
    leida = _aprobado(lectura, carpeta_curso, sesion)
    if leida:
        partes += ["", "LECTURA APROBADA DE LA SESIÓN. La evaluación no evalúa nada que no esté aquí o en el laboratorio:",
                   json.dumps(leida.get("bloques", []), ensure_ascii=False)]
    lab = _aprobado(laboratorio, carpeta_curso, sesion)
    if lab:
        resumen = [{"numero": e.get("numero"), "titulo": e.get("titulo"), "situacion": e.get("situacion"),
                    "archivos": e.get("archivos")} for e in lab.get("ejercicios", [])]
        partes += ["", "LABORATORIO APROBADO. Ninguna pregunta repite un ejercicio, sus archivos ni sus datos:",
                   json.dumps(resumen, ensure_ascii=False)]
    act = _aprobado(actividad, carpeta_curso, sesion)
    if act:
        enunciados = [p.get("enunciado") for paso in act.get("pasos", []) for p in paso.get("preguntas", [])]
        partes += ["", "ACTIVIDAD WEB APROBADA. Ninguna pregunta repite estas preguntas:",
                   json.dumps(enunciados, ensure_ascii=False)]
    return "\n".join(partes)


def instrucciones_de_formato(sesion: int, preguntas: int) -> str:
    tareas = "; ".join(f"«{clave}» ({texto})" for clave, texto in TAREAS_DE_EVALUACION.items())
    return f"""
CÓMO ENTREGAR LA EVALUACIÓN (PLAN.md §0, decisión 64)
- Devuelve solo los datos del esquema. Un programa crea la hoja del alumno en Word (portada «Evaluación práctica»,
  indicaciones, tabla de archivos y cada pregunta con «Situación», «Archivos», «Tarea» y «Tu respuesta»), la clave
  en otro Word («Clave de la evaluación»), los archivos reales y su .zip.
- indicaciones: «consulta», el material que el alumno puede consultar, y «entrega», la forma de entrega de las
  respuestas. Salen de la ficha de la sesión; si la ficha no las trae, escribe una oración sencilla para cada una.
- preguntas: {preguntas}, las de la ficha de la sesión, en su orden, numeradas desde 1. Cada una funciona sola.
  - concepto: el concepto del vocabulario que evalúa, con su nombre único.
  - tarea: una de estas: {tareas}.
  - titulo: una acción concreta («Clasifica los hechos del Sprint según su pilar»). Sin «Pregunta N».
  - situacion: de 2 a 3 oraciones con el caso del curso, con datos nuevos: quién pide qué y para qué.
  - archivos: los nombres exactos de los archivos de esa pregunta.
  - pasos: la tarea en pasos numerados, en el orden real. Cada paso es una sola acción. El último dice dónde
    escribe el alumno su respuesta: en la tabla de «Tu respuesta».
  - tabla_de_respuesta: la tabla que el alumno llena, con «titulo», «encabezados» y «filas». Las celdas que el
    alumno llena van vacías (""); las que ya trae (un número de fila, el nombre de un elemento) van escritas. Cada
    celda vacía es una decisión del alumno: 10 como máximo por pregunta y un número parecido en todas las preguntas.
    15 filas como máximo. La tabla no da pistas de la respuesta.
  - clave: «respuesta», la misma tabla completa, con las mismas filas y columnas, sin cambiar las celdas que ya
    trae; «aceptadas», otras respuestas aceptadas, solo si la pregunta admite más de una; «partes», la respuesta
    en partes, una por línea; «problemas», lo que cada archivo trae a propósito; «errores_comunes», los errores que
    más cometen los alumnos y por qué son errores.
- archivos: los de cada pregunta, con nombre S{sesion}_P[pregunta]_[descripcion-corta] en minúsculas y con guiones
  («S{sesion}_P1_hechos-ventas.xlsx»). Excel (.xlsx) para datos y Word (.docx) para textos. Datos nuevos: no copies
  los archivos ni los datos del laboratorio. Datos ficticios y coherentes con los datos fijos de la ficha.
  - Excel: «hojas», con «nombre», «encabezados» y «filas»; 15 filas como máximo. Sin «listas».
  - Word: «parrafos» (estilo «titulo», «texto» o «lista») y, si hace falta, «tabla».
  - problema: lo que el archivo trae a propósito, según la ficha. No va en la hoja del alumno.
- La situación de una pregunta y sus archivos de texto suman 250 palabras como máximo.
- Ninguna parte de la hoja del alumno ni de sus archivos da la respuesta. La respuesta solo va en la clave.
- Sin minutos, puntos, notas ni porcentajes en ninguna parte. El profesor decide el tiempo y la calificación.
- Un programa resuelve cada pregunta como un alumno, sin la clave, y compara lo que sale con la clave.
- pasajes: los pasajes de las fuentes que usaste: «oracion» que sostiene, la fuente, la ubicación y en «texto» solo
  el comienzo del pasaje: sus primeras 6 a 10 palabras, copiadas tal cual. AulaLista busca ese comienzo en la fuente
  y copia el pasaje completo.
- decisiones: una entrada por punto, con «texto» y «tipo» («sin fuente» o «decisión»). Lo que solo describe tu
  trabajo no se anota.
"""


def pedido_de_redaccion(carpeta_curso: Path, sesion: int, pasajes: list[str] | None = None) -> str:
    return "\n".join([
        _contexto(carpeta_curso, sesion, pasajes),
        instrucciones_de_formato(sesion, preguntas_de_la_ficha(carpeta_curso, sesion)),
        "TAREA: prepara la evaluación práctica de la sesión, con su clave. Toma las preguntas de la ficha de la sesión:",
        "su concepto, la tarea, el archivo con su problema y la respuesta correcta. Si citas una fuente, toma el pasaje",
        "de la lista de pasajes de arriba. Antes de entregar, resuelve tú cada pregunta como un alumno, con",
        "sus archivos: cada paso se puede hacer y la respuesta es una sola, la de la clave.",
    ])


def sistema_de_correccion(carpeta_curso: Path, sesion: int) -> str:
    """El mensaje de sistema de todas las correcciones: igual en cada una, se lee de caché (decisión 43)."""
    return "\n".join([_contexto(carpeta_curso, sesion),
                      instrucciones_de_formato(sesion, preguntas_de_la_ficha(carpeta_curso, sesion)),
                      comun.REGLAS_DE_CORRECCION])


def _pedido_con_problemas(datos: dict, problemas: list[str], como_entregar: list[str]) -> str:
    return "\n".join(["Corrige el material según el contexto, el formato y las reglas de tus instrucciones.",
                      *como_entregar, "", "EVALUACIÓN ACTUAL:", json.dumps(datos, ensure_ascii=False), "",
                      "PROBLEMAS QUE ENCONTRÓ LA VALIDACIÓN:", *[f"- {p}" for p in problemas]])


def pedido_de_cambios(datos, problemas) -> str:
    return _pedido_con_problemas(datos, problemas, [
        "CÓMO ENTREGAR LA CORRECCIÓN",
        "- En «cambios», una entrada por oración que cambias: «oracion» copiada tal cual y «nueva» con el texto nuevo.",
        "  Para eliminar una oración, deja «nueva» vacío. No devuelvas las oraciones que no cambian.",
    ])


def pedido_de_correccion(datos, problemas) -> str:
    return _pedido_con_problemas(datos, problemas, ["Devuelve la evaluación completa con el mismo esquema."])


# ---------- Estructura y bloques de la revisión ----------

REGLAS_PROPIAS = ("cantidad de preguntas", "tamaño de la pregunta", "tamaño parecido", "respuesta fuera de la clave",
                  "archivo del laboratorio", "datos del laboratorio")


def _validar(datos: dict) -> tuple[Evaluacion | None, list[str]]:
    try:
        return Evaluacion.model_validate(datos), []
    except ValidationError as error:
        return None, [f"FALLA · estructura · {'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()]


def bloques_de(contenido: Evaluacion) -> list[pasada2.Bloque]:
    """Un bloque para las indicaciones y uno por pregunta, con sus archivos y su clave: la revisión del contenido
    trabaja pregunta por pregunta."""
    separar = verificador.verificar.separar_oraciones
    por_nombre = {a.nombre: a for a in contenido.archivos}

    def oraciones(*textos):
        return [o for t in textos if t for o in separar(t)]

    bloques = [pasada2.Bloque("Indicaciones", oraciones(contenido.indicaciones.consulta, contenido.indicaciones.entrega))]
    for p in contenido.preguntas:
        tabla = p.tabla_de_respuesta
        textos = [p.titulo, p.situacion, *p.pasos,
                  f"Tabla de respuesta «{tabla.titulo}»: " + " | ".join(tabla.encabezados),
                  *[f"Clave, fila {i}: " + " | ".join(f) for i, f in enumerate(p.clave.respuesta, start=1)],
                  *[f"Clave, respuesta aceptada: {t}" for t in p.clave.aceptadas],
                  *[f"Clave, parte: {t}" for t in p.clave.partes],
                  *[f"Clave, problema sembrado: {t}" for t in p.clave.problemas],
                  *[f"Clave, error común: {t}" for t in p.clave.errores_comunes]]
        for nombre in p.archivos:
            archivo = por_nombre.get(nombre)
            if archivo is None:
                continue
            textos.append(f"Archivo {nombre}: {archivo.descripcion}")
            textos += [x.texto for x in archivo.parrafos]
            if archivo.tabla:
                textos += [f"{nombre} · " + " | ".join(f) for f in [archivo.tabla.encabezados, *archivo.tabla.filas]]
            for hoja in archivo.hojas:
                textos += [f"{nombre} · {hoja.nombre} · " + " | ".join(str(v) for v in fila if v is not None)
                           for fila in [hoja.encabezados, *hoja.filas]]
        bloques.append(pasada2.Bloque(f"Pregunta {p.numero} · {p.titulo}", oraciones(*textos)))
    return bloques


INDICACIONES_DE_REVISION = (
    "Es una evaluación práctica: la hoja del alumno, sus archivos y la clave de corrección del profesor. Revisa que "
    "cada pregunta funcione sola, con sus archivos; que tenga una sola respuesta correcta y que esa respuesta sea la "
    "de la clave; que los datos cuadren entre la situación, los archivos, la clave y los datos fijos de la ficha; que "
    "evalúe solo lo que la lectura y el laboratorio enseñaron; y que la hoja del alumno no dé la respuesta. Las líneas "
    "que empiezan con «Clave» son de la clave: ahí la respuesta debe estar. El problema que un archivo trae a "
    "propósito no es un error: es parte de la pregunta.")


# ---------- Ejecución como un alumno (decisión 64 e) ----------

def pedido_como_alumno(p, adjuntos: dict[str, str]) -> str:
    """Lo que tiene el alumno: sus archivos, la situación, la tarea y la tabla vacía. Nada de la clave ni de la ficha."""
    tabla = p.tabla_de_respuesta
    filas = [" | ".join(c if c.strip() else "____" for c in fila) for fila in tabla.filas]
    archivos_ = [f"[Archivo: {nombre}]\n{texto}\n[Fin de {nombre}]" for nombre, texto in adjuntos.items()]
    return "\n".join([
        "Eres un alumno de un curso y estás resolviendo una evaluación práctica. Solo tienes los archivos, la situación",
        "y la tarea. Sigue cada paso en su orden. Al terminar, entrega la tabla de tu respuesta completa, con las mismas",
        "filas y columnas: llena cada celda marcada con ____ y deja igual las demás. No expliques cómo lo hiciste.",
        "",
        *archivos_,
        "",
        f"PREGUNTA {p.numero} · {p.titulo}",
        p.situacion,
        "",
        "TAREA:",
        *[f"{i}. {paso}" for i, paso in enumerate(p.pasos, start=1)],
        "",
        f"TU RESPUESTA · {tabla.titulo}",
        " | ".join(tabla.encabezados),
        *filas,
    ])


def texto_de_la_clave(p, respuesta_ficha: str = "") -> str:
    """Contra qué se compara lo que salió: la clave y, si la ficha la trae, su respuesta correcta."""
    lineas = [" | ".join(p.tabla_de_respuesta.encabezados), *[" | ".join(f) for f in p.clave.respuesta]]
    lineas += [f"También se acepta: {t}" for t in p.clave.aceptadas]
    if respuesta_ficha:
        lineas += ["", f"Respuesta correcta de la ficha: {respuesta_ficha}"]
    return "\n".join(lineas)


def pedido_de_comparacion(x: ejecucion.Ejecucion, situacion: str) -> str:
    return "\n".join([
        "Revisas una pregunta de una evaluación práctica que un alumno ya resolvió. Compara su respuesta con la clave",
        "del profesor y con la respuesta correcta de la ficha.",
        "- Solo es una diferencia: una celda con otro dato (una clasificación, un orden, un número, un nombre), una",
        "  celda que el alumno no llenó, o algo de la clave que contradice la respuesta de la ficha.",
        "- Escribir lo mismo con otras palabras, mayúsculas o signos no es una diferencia. Tampoco lo es una respuesta",
        "  que la clave acepta.",
        "- En «esperado» copia tal cual un trozo corto de la clave o de la ficha. En «salio» copia tal cual un trozo",
        "  corto de la respuesta del alumno, o déjalo vacío si eso no salió. Un programa busca los dos trozos.",
        "- Sin diferencias, devuelve la lista vacía.",
        "",
        f"PREGUNTA {x.numero} · {x.titulo}",
        situacion,
        "",
        "CLAVE Y RESPUESTA DE LA FICHA:",
        x.respuesta_ficha,
        "",
        "RESPUESTA DEL ALUMNO:",
        x.salida(),
    ])


def respuestas_de_la_ficha(carpeta_curso: Path, sesion: int) -> dict[int, str]:
    """La respuesta correcta de cada pregunta de la ficha, por el número que tiene en la evaluación (mismo orden)."""
    ficha = almacen.cargar(carpeta_curso, "sesion", sesion)
    ids = ("concepto", "tarea", "archivo", "problema", "respuesta")
    numeros = almacen.bloques_llenos(ficha, "pregunta", plantillas.MAX_PREGUNTAS, ids)
    return {i: almacen.valor(ficha, f"pregunta.{n}.respuesta").strip() for i, n in enumerate(numeros, start=1)}


async def ejecutar(contenido: Evaluacion, *, carpeta_archivos: Path, respuestas_ficha: dict[int, str], llamada: dict,
                   avance=lambda texto: None) -> list[ejecucion.Ejecucion]:
    """Cada pregunta, resuelta por Claude como un alumno en una conversación nueva y sin herramientas, y comparada
    con la clave y con la ficha. Cada diferencia trae su prueba; la que no la tiene se descarta (decisión 35 d)."""
    resultados = []
    for p in contenido.preguntas:
        avance(f"Resolviendo la pregunta {p.numero} como un alumno.")
        adjuntos = {n: ejecucion.texto_del_archivo(carpeta_archivos / n) for n in p.archivos
                    if (carpeta_archivos / n).exists()}
        pedido = pedido_como_alumno(p, adjuntos)
        respuesta = await agente.conversar(pedido, tarea="ejecucion", etapa=f"ejecución pregunta {p.numero}", **llamada)
        x = ejecucion.Ejecucion(p.numero, p.titulo, respuesta_ficha=texto_de_la_clave(p, respuestas_ficha.get(p.numero, "")),
                                conversacion=[ejecucion.Turno("guía", pedido), ejecucion.Turno("resultado", respuesta)],
                                a_mano=True)
        comparacion = await agente.consultar(pedido_de_comparacion(x, p.situacion), tarea="comparacion_ejecucion",
                                             esquema=ejecucion.ESQUEMA_COMPARACION,
                                             etapa=f"comparación pregunta {p.numero}", **llamada)
        x.diferencias, x.descartadas = ejecucion.con_prueba(comparacion["diferencias"], x.respuesta_ficha, x.salida())
        resultados.append(x)
    return resultados


def pendientes_de(x: ejecucion.Ejecucion) -> list[str]:
    return [f"Ejecución · pregunta {x.numero}: la clave dice «{d.esperado}» y "
            + (f"el alumno respondió «{d.salio}»." if d.salio else "eso no salió.") + f" {d.explicacion}".rstrip()
            for d in x.diferencias]


# ---------- Generación ----------

class _Trabajo:
    def __init__(self, carpeta_curso, curso, sesion, rutas, consulta, ejecutar_=None):
        self.carpeta_curso, self.curso, self.sesion, self.rutas = carpeta_curso, curso, sesion, rutas
        self.consulta = consulta
        self._ejecutar = ejecutar_ or ejecutar
        self.carpeta_sesion = almacen.carpeta_sesion(carpeta_curso, sesion)
        self.identidad = estilo.desde_ficha(carpeta_curso)
        self.portada = lectura._portada(carpeta_curso, sesion)
        self.comun = {"curso": curso, "sesion": f"S{sesion}", "material": CLAVE, "cwd": carpeta_curso / "fuentes_texto",
                      "herramientas": ("Read", "Grep", "Glob"), "consulta": consulta}
        self.esperadas = preguntas_de_la_ficha(carpeta_curso, sesion)
        self.otros = textos_de_otros(carpeta_curso, sesion)
        self.del_laboratorio = archivos_del_laboratorio(carpeta_curso, sesion)
        self.datos: dict = {}
        self.contenido: Evaluacion | None = None
        self.explicaciones: dict[str, str] = {}
        self.historial: list[dict] = []
        self.correcciones = {"verificador": 0, "revisión": 0}
        self.datos_agregados: list[str] = []
        self.resultado = None
        self.fallas: list[str] = []
        self.descartados: list[dict] = []
        self.vuelta = 0

    def avance(self, texto: str) -> None:
        comun.avance(self.carpeta_curso, self.sesion, CLAVE, texto)

    def corpus(self) -> Corpus:
        return Corpus.del_curso(self.carpeta_curso, self.sesion)

    async def verificar(self) -> bool:
        for intento in range(VUELTAS_DEL_VERIFICADOR + 1):
            self.vuelta += 1
            self.datos, self.pasajes_no_ubicados = comun.completar_pasajes(self.datos, self.corpus())
            contenido, problemas = _validar(self.datos)
            completa = bool(problemas)
            comun.guardar_json(self.rutas["contenido"], self.datos)
            if contenido is not None:
                self.contenido = contenido
                problemas = crear_archivos(contenido, self.identidad, self.portada, self.rutas, self.sesion)
                completa = bool(problemas)
                if not problemas:
                    configuracion = verificador.configuracion_del_material(
                        self.carpeta_sesion, MATERIAL, carpeta_practica=CARPETA_ARCHIVOS)
                    extra = controles(contenido, self.esperadas, self.otros, self.del_laboratorio)
                    self.resultado = verificador.ejecutar(
                        configuracion, [self.rutas["word"], self.rutas["clave"],
                                        *sorted(self.rutas["archivos"].iterdir()), self.rutas["zip"]],
                        self.rutas["excel"], self.explicaciones, hallazgos_extra=extra,
                        salida_json=self.rutas["verificacion_json"])
                    if comun.explicar_literales(self.resultado, self.explicaciones, self.corpus()):
                        comun.guardar_json(self.rutas["explicaciones"], self.explicaciones)
                        verificador.anotar_explicaciones(self.rutas["excel"], self.explicaciones)
                    excel.anotar_reglas(self.rutas["excel"], comun.AVISOS_INFORMATIVOS, comun.NOTA_INFORMATIVA)
                    fallas, avisos = comun.hallazgos_abiertos(self.resultado, self.explicaciones)
                    self.avance(f"Verificador, vuelta {self.vuelta}: {self.resultado.resumen()}.")
                    problemas = [comun.texto_de(h) for h in fallas + avisos]
                    nombres = {a.nombre for a in contenido.archivos}
                    # Los controles propios, lo que no tiene oración y lo de un archivo se arreglan con la evaluación
                    # completa: cambian el tamaño de una pregunta, su tabla o sus archivos.
                    completa = any(h.regla in REGLAS_PROPIAS or not h.oracion or h.seccion.split(" · ")[0] in nombres
                                   for h in fallas + avisos)
                    self.historial += comun.historial(fallas + avisos, self.vuelta)
            self.fallas = problemas
            if not problemas:
                return True
            if intento == VUELTAS_DEL_VERIFICADOR:
                self.avance(f"Quedan {len(problemas)} fallas después de {VUELTAS_DEL_VERIFICADOR} correcciones. "
                            "No se puede aprobar la evaluación con fallas.")
                return False
            self.correcciones["verificador"] += len(problemas)
            await self.corregir(problemas, completa)
        return False

    async def revisar(self, bloques: list[pasada2.Bloque], etapa: str) -> revision.Resultado:
        resultado = await revision.ejecutar(
            bloques, corpus=self.corpus(), anclas=[p.model_dump() for p in self.contenido.pasajes],
            curso=self.curso, sesion=self.sesion, material=CLAVE, nombre_material=MATERIAL, etapa=etapa,
            indicaciones=INDICACIONES_DE_REVISION, consulta=self.consulta)
        self.descartados += resultado.descartados
        return resultado

    async def corregir(self, problemas: list[str], completa: bool) -> None:
        vuelta = self.vuelta
        sistema = comun.escribir_sistema(self.rutas["sistema"], sistema_de_correccion(self.carpeta_curso, self.sesion))
        if completa:
            self.avance(f"Corrigiendo la evaluación completa: {comun.cuantos(len(problemas), 'problema')}.")
            respuesta = await comun.consultar_correccion(pedido_de_correccion(self.datos, problemas), "completa",
                                                         ESQUEMA_CORRECCIONES, tarea="correccion",
                                                         etapa=f"corrección completa {vuelta}", sistema=sistema,
                                                         **self.comun)
            self.datos = respuesta[CLAVE]
        else:
            self.avance(f"Corrigiendo {comun.cuantos(len(problemas), 'problema')}.")
            respuesta = await comun.consultar_correccion(pedido_de_cambios(self.datos, problemas), "oraciones",
                                                         ESQUEMA_CORRECCIONES, tarea="correccion_oraciones",
                                                         etapa=f"corrección {vuelta}", sistema=sistema, **self.comun)
            self.datos, no_encontradas = comun.aplicar_cambios(self.datos, respuesta["cambios"], CAMPOS_QUE_NO_SE_CORRIGEN)
            if no_encontradas:
                self.avance(f"{comun.cuantos(len(no_encontradas), 'oración')} a cambiar no se encontraron.")
        for e in respuesta["explicaciones"]:
            self.explicaciones[verificador.clave_de_hallazgo(e["regla"], e["oracion"])] = e["explicacion"]
        comun.guardar_json(self.rutas["explicaciones"], self.explicaciones)
        nuevos = almacen.agregar_datos_fijos(self.carpeta_curso, respuesta.get("datos_nuevos", []),
                                             f"Evaluación S{self.sesion}")
        if nuevos:
            self.datos_agregados += nuevos
            for numero in almacen.sesiones_confirmadas(self.carpeta_curso):
                verificacion.escribir(self.carpeta_curso, numero)
            self.avance(f"Datos nuevos del caso agregados a la ficha del curso: {len(nuevos)}.")

    async def ejecutar(self) -> list[ejecucion.Ejecucion]:
        self.avance("Resolviendo cada pregunta como un alumno, sin la clave, y comparando con la clave.")
        return await self._ejecutar(
            self.contenido, carpeta_archivos=self.rutas["archivos"],
            respuestas_ficha=respuestas_de_la_ficha(self.carpeta_curso, self.sesion),
            llamada={"curso": self.curso, "sesion": f"S{self.sesion}", "material": CLAVE, "consulta": self.consulta},
            avance=self.avance)


def _limpiar(rutas: dict[str, Path]) -> None:
    for clave in ("word", "clave", "zip", "excel", "verificacion_json", "contenido", "explicaciones", "registro",
                  "ejecucion_json"):
        try:
            rutas[clave].unlink(missing_ok=True)
        except OSError:
            pass
    for clave in ("archivos", "revision", "ejecucion"):
        shutil.rmtree(rutas[clave], ignore_errors=True)


def _sin_empezar(carpeta_curso: Path, sesion: int) -> str:
    """Por qué la evaluación no puede empezar, o "" si puede."""
    if not almacen.puede_empezar_material(carpeta_curso, sesion):
        return "Guarda completas la ficha del curso y la ficha de la sesión antes de generar la evaluación."
    falta = faltan(carpeta_curso, sesion)
    if falta["ficha"]:
        return "Completa la ficha de la sesión antes de generar la evaluación: " + " ".join(falta["ficha"])
    return " ".join(falta["otros"])


def se_puede_reanudar(carpeta_curso: Path, sesion: int) -> bool:
    """Decisión 40: hay contenido guardado de una generación que no terminó bien, y nada cambió desde entonces."""
    material = estado(carpeta_curso, sesion)
    return (material.get("estado") in ("con fallas", "detenida", "error") and not material.get("desactualizado")
            and archivos(carpeta_curso, sesion)["contenido"].exists() and not _sin_empezar(carpeta_curso, sesion))


async def reanudar(carpeta_curso: Path, curso: str, sesion: int, consulta=agente.query, **opciones) -> dict:
    """Sigue desde el contenido guardado, sin repetir la redacción ni sus correcciones (PLAN.md §0, decisión 40)."""
    if not se_puede_reanudar(carpeta_curso, sesion):
        raise NoSePuedeEmpezar("No se puede reanudar la evaluación: no hay un trabajo guardado que siga a las fichas y "
                               "a los materiales de ahora. Genérala de nuevo.")
    return await generar(carpeta_curso, curso, sesion, consulta, desde_guardado=True, **opciones)


async def generar(carpeta_curso: Path, curso: str, sesion: int, consulta=agente.query, ejecutar_=None,
                  desde_guardado: bool = False) -> dict:
    """`ejecutar_` reemplaza la resolución de las preguntas como alumno en las pruebas."""
    motivo = _sin_empezar(carpeta_curso, sesion)
    if motivo:
        raise NoSePuedeEmpezar(motivo)
    rutas = archivos(carpeta_curso, sesion)
    guardado = None
    if desde_guardado:
        guardado = {"datos": comun.leer_json(rutas["contenido"]),
                    "explicaciones": comun.leer_json(rutas["explicaciones"]) if rutas["explicaciones"].exists() else {},
                    "fecha": comun.estado(carpeta_curso, sesion, CLAVE).get("fecha", "")}
    rutas["contenido"].parent.mkdir(parents=True, exist_ok=True)
    comun.actualizar(carpeta_curso, sesion, CLAVE, estado="trabajando", previo="", avance=[], error="",
                     desactualizado=False, entrega={}, aprobada="", revisor={}, corrida_desde=tokens.lineas(curso))
    try:
        return await _generar(carpeta_curso, curso, sesion, rutas, consulta, ejecutar_, guardado)
    except asyncio.CancelledError:
        marcar_detenida(carpeta_curso, sesion)
        raise
    except Exception as error:
        comun.actualizar(carpeta_curso, sesion, CLAVE, estado="error", error=str(error))
        raise


async def _generar(carpeta_curso, curso, sesion, rutas, consulta, ejecutar_, guardado=None) -> dict:
    inicio = tokens.lineas(curso)
    skill.comprobar(secciones=SECCIONES_DE_LA_SKILL + pasada2.SECCIONES_DE_LA_SKILL + revisor.SECCIONES_DE_LA_SKILL,
                    subsecciones=revisor.SUBSECCIONES_DE_LA_SKILL)
    trabajo = _Trabajo(carpeta_curso, curso, sesion, rutas, consulta, ejecutar_)
    verificador.verificar.leer_configuracion(
        verificador.configuracion_del_material(trabajo.carpeta_sesion, MATERIAL, carpeta_practica=CARPETA_ARCHIVOS))
    _limpiar(rutas)
    if guardado is not None:
        trabajo.datos, trabajo.explicaciones = guardado["datos"], guardado["explicaciones"]
        trabajo.avance(f"Reanudo desde lo generado el {guardado['fecha'][:16].replace('T', ' ')}: "
                       "no repito la redacción ni sus correcciones.")
    else:
        trabajo.avance("Leyendo las fichas, la lectura, el laboratorio y las fuentes, y escribiendo la evaluación.")
        pasajes = referencia.pasajes_elegidos(
            carpeta_curso, sesion, referencia.textos_de_la_sesion(almacen.cargar(carpeta_curso, "sesion", sesion)))
        trabajo.datos = await agente.consultar(pedido_de_redaccion(carpeta_curso, sesion, pasajes), tarea="redaccion",
                                               esquema=ESQUEMA_EVALUACION, etapa="redacción",
                                               **{**trabajo.comun, "cwd": None, "herramientas": ()})
    errores: list[revision.Error] = []
    revisados = 0
    ejecuciones: list[ejecucion.Ejecucion] = []
    if await trabajo.verificar():
        errores, revisados = await comun.revisar_y_corregir(trabajo, bloques_de)
        if not trabajo.fallas:
            ejecuciones = await trabajo.ejecutar()
    if ejecuciones:
        comun.guardar_json(rutas["ejecucion_json"], [x.a_dict() for x in ejecuciones])
        rutas["registro"].write_text(_registro(ejecuciones, sesion), encoding="utf-8")
    diferencias = [p for x in ejecuciones for p in pendientes_de(x)]
    pendientes = [e for e in errores if e.estado == "pendiente"]
    final = trabajo.contenido
    decisiones = final.decisiones if final else []
    sin_fuente = [f"Afirmación sin fuente: {d.texto}" for d in decisiones if d.tipo == "sin fuente"]
    estado_final = "con fallas" if trabajo.fallas else (
        "con pendientes" if pendientes or sin_fuente or diferencias else "verificada")
    if trabajo.resultado is not None:
        excel.solo_hallazgos(rutas["excel"], "Sección")
        excel.agregar_historial(rutas["excel"], [
            {**h, "resolucion": f"Enviado a corrección en la vuelta {h['vuelta']}." + ("" if trabajo.fallas else " Resuelto.")}
            for h in trabajo.historial] + comun.filas_de_revision(errores, trabajo.descartados, rutas["word"].name)
            + comun.filas_de_decisiones(decisiones, rutas["word"].name))
    hallazgos = trabajo.resultado.hallazgos if trabajo.resultado else []
    material = comun.actualizar(
        carpeta_curso, sesion, CLAVE,
        estado=estado_final,
        resumen=trabajo.resultado.resumen() if trabajo.resultado else "",
        problemas=trabajo.fallas + [e.describir() for e in pendientes] + sin_fuente + diferencias,
        correcciones=trabajo.correcciones,
        revision={"bloques": revisados, "errores": len(errores), "corregidos": sum(e.estado == "corregido" for e in errores),
                  "pendientes": len(pendientes), "descartados": len(trabajo.descartados)},
        datos_agregados=trabajo.datos_agregados,
        pasajes_no_ubicados=getattr(trabajo, "pasajes_no_ubicados", 0),
        reanudada=guardado["fecha"] if guardado is not None else "",
        avisos_de_diseno=trabajo.identidad.avisos,
        avisos_explicados=sum(1 for h in hallazgos if h.nivel == "AVISO" and h.regla not in comun.AVISOS_INFORMATIVOS),
        avisos_informativos=sum(1 for h in hallazgos if h.nivel == "AVISO" and h.regla in comun.AVISOS_INFORMATIVOS),
        preguntas=len(final.preguntas) if final else 0,
        archivos_evaluacion=[{"nombre": a.nombre, "problema": a.problema} for a in (final.archivos if final else [])],
        ejecucion={"preguntas": len(ejecuciones), "coinciden": [x.numero for x in ejecuciones if not x.diferencias],
                   "diferencias": sum(len(x.diferencias) for x in ejecuciones),
                   "descartadas": sum(x.descartadas for x in ejecuciones),
                   "modelo": agente.leer_tarea("ejecucion")["modelo"] if ejecuciones else ""},
        decisiones=[d.model_dump() for d in decisiones],
        archivos={"word": rutas["word"].name, "clave": rutas["clave"].name, "zip": rutas["zip"].name,
                  "excel": rutas["excel"].name, **({"registro": rutas["registro"].name} if ejecuciones else {})},
        costo=tokens.total(curso, sesion=f"S{sesion}", material=CLAVE, desde_linea=inicio),
        fecha=datetime.now().isoformat(timespec="seconds"),
    )
    comun.actualizar(carpeta_curso, sesion, CLAVE, entrega=_entrega(material))
    trabajo.avance({"verificada": "Evaluación lista para tu aprobación.",
                    "con pendientes": f"Evaluación lista, con "
                                      f"{comun.cuantos(len(pendientes) + len(sin_fuente) + len(diferencias), 'pendiente')} "
                                      "para que decidas.",
                    "con fallas": "La evaluación quedó con fallas del verificador."}[estado_final])
    return comun.estado(carpeta_curso, sesion, CLAVE)


def _registro(ejecuciones: list[ejecucion.Ejecucion], sesion: int) -> str:
    """Lo que respondió el alumno simulado en cada pregunta y lo que no coincidió con la clave."""
    lineas = [f"# Ejecución · Evaluación · Sesión {sesion}", "",
              f"Cada pregunta la resolvió Claude ({agente.leer_tarea('ejecucion')['modelo']}) como un alumno, en una "
              "conversación nueva y sin herramientas, con el texto de sus archivos, la situación, la tarea y la tabla "
              "vacía. No vio la clave.", ""]
    for x in ejecuciones:
        lineas += [f"## Pregunta {x.numero} · {x.titulo}", "", "Respuesta del alumno:", "", x.salida(), ""]
        lineas += (["Diferencias con la clave:", "", *[f"- {p}" for p in pendientes_de(x)], ""] if x.diferencias
                   else ["Coincide con la clave.", ""])
    return "\n".join(lineas)


def _entrega(material: dict) -> dict:
    archivos_ = material["archivos"]
    propios = material.get("archivos_evaluacion") or []
    lineas_archivos = [
        f"{archivos_['word']}: la hoja del alumno, con {comun.cuantos(material['preguntas'], 'pregunta')}.",
        f"{archivos_['clave']}: la clave de corrección, con la respuesta completa de cada pregunta.",
        f"{archivos_['zip']}: los {comun.cuantos(len(propios), 'archivo')} de la evaluación: "
        + ", ".join(a["nombre"] for a in propios) + ".",
        f"{archivos_['excel']}: el archivo de verificación, con la hoja Hallazgos.",
        *([f"{archivos_['registro']}: lo que respondió el alumno simulado en cada pregunta."] if archivos_.get("registro")
          else []),
    ]
    probe = ["Creé cada archivo de la evaluación con un programa, en un .zip aparte del .zip del laboratorio.",
             "Comprobé el tamaño de cada pregunta: palabras, filas y celdas que llena el alumno.",
             "Comprobé que ninguna respuesta de la clave aparece en la hoja del alumno, en sus archivos, en la guía del "
             "laboratorio ni en la actividad web, y que los archivos no son los del laboratorio."]
    ej = material.get("ejecucion") or {}
    if ej.get("preguntas"):
        probe.append(f"Resolví {comun.cuantos(ej['preguntas'], 'pregunta')} con Claude como un alumno, sin la clave.")
        if ej["coinciden"]:
            probe.append("Coinciden con la clave: " + ", ".join(f"pregunta {n}" for n in ej["coinciden"]) + ".")
        if ej.get("descartadas"):
            probe.append(f"Diferencias descartadas porque su prueba no está en la clave ni en la respuesta: "
                         f"{ej['descartadas']}.")
    c, r = material["correcciones"], material.get("revision") or {}
    valide = [f"Verificador, sobre la hoja del alumno, la clave y los archivos: {material['resumen']}."
              if material["resumen"] else "El verificador no llegó a correr.",
              *([f"Avisos explicados en la hoja Hallazgos: {material['avisos_explicados']}."]
                if material.get("avisos_explicados") else []),
              *([f"Avisos informativos: {material['avisos_informativos']}. Están en la hoja Hallazgos; no obligan a "
                 "corregir."] if material.get("avisos_informativos") else []),
              f"Fallas del verificador corregidas: {c['verificador']}."]
    if r.get("bloques"):
        texto = f"Revisión del contenido: {comun.cuantos(r['bloques'], 'bloque')}, {comun.cuantos(r['errores'], 'error')} con prueba"
        if r["errores"]:
            texto += f" ({comun.cuantos(r['corregidos'], 'corregido')} y {comun.cuantos(r['pendientes'], 'pendiente')})"
        valide.append(texto + ".")
    rev = material.get("revisor") or {}
    if rev:
        valide.append(f"Revisor independiente (lo pediste tú): {comun.cuantos(rev['hallazgos'], 'hallazgo')} con prueba. "
                      f"Costo: {rev['costo']['costo_usd']:.2f} USD estimados.")
    costo = material["costo"]
    valide.append(f"Costo de esta evaluación: {costo['llamadas']} llamadas, {costo['costo_usd']:.2f} USD estimados.")
    no_pude = ([f"Las preguntas las resolvió Claude ({ej['modelo']}) con el texto de sus archivos. No abrió Excel ni "
                "Word: un alumno puede equivocarse en otros lugares."] if ej.get("preguntas")
               else ["No resolví las preguntas porque quedaron fallas antes de llegar a la ejecución."])
    if material.get("reanudada"):
        no_pude.append(f"Reanudé desde lo generado el {material['reanudada'][:16].replace('T', ' ')} "
                       "(PLAN.md §0, decisión 40). El historial de las vueltas de esa vez no está en el Excel.")
    if not r.get("bloques"):
        no_pude.append("La revisión del contenido no corrió porque quedaron fallas del verificador.")
    decidi = [d["texto"] for d in material["decisiones"] if d["tipo"] == "decisión"]
    decidi += [f"Problema sembrado en {a['nombre']}: {a['problema']}" for a in propios if a.get("problema")]
    decidi += [f"Dato nuevo del caso, agregado a la ficha del curso: {d}" for d in material["datos_agregados"]]
    if not decidi:
        decidi.append("Nada que revisar: todo salió de las fichas, de las fuentes y de lo ya aprobado.")
    no_pude += comun.nota_de_pasajes(material)
    return entrega.componer(archivos=lineas_archivos, probe=probe, valide=valide,
                            pendientes=material["problemas"], no_pude=no_pude, decidi=decidi)


# ---------- Revisor independiente y aprobación ----------

async def revisar_con_revisor(carpeta_curso: Path, curso: str, sesion: int, consulta=agente.query) -> dict:
    material = comun.estado(carpeta_curso, sesion, CLAVE)
    previo = material.get("estado")
    if previo not in ("verificada", "con pendientes", "aprobada"):
        raise NoSePuedeRevisar("El revisor independiente revisa una evaluación generada y sin fallas del verificador.")
    rutas = archivos(carpeta_curso, sesion)
    contenido = Evaluacion.model_validate(comun.leer_json(rutas["contenido"]))
    oraciones = comun.leer_json(rutas["verificacion_json"])["oraciones"]
    inicio = tokens.lineas(curso)
    comun.actualizar(carpeta_curso, sesion, CLAVE, estado="trabajando", previo=previo)
    comun.avance(carpeta_curso, sesion, CLAVE,
                 "Revisor independiente: una sesión nueva lee la hoja del alumno, la clave, los archivos, las fuentes y "
                 "las fichas.")
    try:
        resultado = await revisor.ejecutar(
            oraciones, ronda=1, carpeta=rutas["revision"] / "ronda_1", carpeta_curso=carpeta_curso, curso=curso,
            sesion=sesion, material=CLAVE, nombre_material=MATERIAL, bloques=bloques_de(contenido), consulta=consulta)
    except asyncio.CancelledError:
        marcar_detenida(carpeta_curso, sesion)
        raise
    except Exception as error:
        comun.avance(carpeta_curso, sesion, CLAVE, f"El revisor independiente se detuvo por un error: {error}")
        comun.actualizar(carpeta_curso, sesion, CLAVE, estado=previo, previo="")
        raise
    hallazgos = resultado.hallazgos
    excel.agregar_historial(rutas["excel"], [
        {"nivel": "REVISOR", "seccion": rutas["word"].name, "oracion": h.oracion, "regla": f"revisor independiente: {h.defecto}",
         "detalle": f"{h.explicacion} Prueba: «{h.prueba}» ({h.fuente}).", "resolucion": "Pendiente: decides tú."}
        for h in hallazgos])
    material = comun.actualizar(
        carpeta_curso, sesion, CLAVE, estado="con pendientes" if hallazgos else previo, previo="",
        aprobada="" if hallazgos else material.get("aprobada", ""),
        problemas=material.get("problemas", []) + [h.describir() for h in hallazgos],
        revisor={"hallazgos": len(hallazgos), "descartados": len(resultado.descartados), "lista": len(resultado.lista_no),
                 "costo": tokens.total(curso, sesion=f"S{sesion}", material=CLAVE, desde_linea=inicio)})
    comun.actualizar(carpeta_curso, sesion, CLAVE, entrega=_entrega(material))
    return comun.estado(carpeta_curso, sesion, CLAVE)


def aprobar(carpeta_curso: Path, sesion: int) -> dict:
    material = estado(carpeta_curso, sesion)
    if material.get("estado") not in ("verificada", "con pendientes"):
        raise NoSePuedeAprobar("Solo se aprueba una evaluación generada y sin fallas del verificador.")
    if material.get("desactualizado"):
        raise NoSePuedeAprobar("Algo que la evaluación usa cambió después de generarla. Genérala de nuevo.")
    return comun.actualizar(carpeta_curso, sesion, CLAVE, estado="aprobada",
                            aprobada=datetime.now().isoformat(timespec="seconds"))
