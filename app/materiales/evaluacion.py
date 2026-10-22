"""Material 6 · Evaluación práctica (PBQ) y su clave (SKILL.md, «Material 6»; PLAN.md §0, decisión 64; etapa 9).

Fase 9a: el estado, los archivos y lo que hace falta para generarla. La redacción, la validación y la ejecución
llegan en las fases 9b y 9c; la página del material, en la 9d. Mientras tanto la evaluación no se registra en la
interfaz (decisión 46).

Flujo previsto, igual al del laboratorio:
1. Comprueba las dos fichas confirmadas, las preguntas de la ficha y la lectura y el laboratorio aprobados y al día
   (decisión 64 a): la evaluación no evalúa nada que no hayan enseñado.
2. El agente escribe las preguntas, sus archivos y la clave como datos (contenido.Evaluacion).
3. Un programa crea la hoja del alumno, la clave y el .zip de los archivos, y el verificador los revisa.
4. Revisión del contenido por pregunta, una sola corrección, y cada pregunta resuelta como un alumno.
"""

import json
import re
import shutil
import unicodedata
from pathlib import Path

from app.fichas import almacen, dependencias, plantillas
from app.materiales import actividad, comun, docx, estilo, laboratorio, lectura, practica
from app.materiales.contenido import ArchivoPractica, Evaluacion, Laboratorio
from app.validacion import verificador

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
