"""Material 3 · Laboratorio y archivos de práctica (SKILL.md, «Material 3»; PLAN.md §4, etapa 7a).

Flujo, igual al de la lectura:
1. Comprueba que las dos fichas estén confirmadas y que la ficha de la sesión traiga de 3 a 5 ejercicios.
2. El agente escribe los ejercicios y el contenido de cada archivo de práctica como datos.
3. Un programa comprueba la estructura: nombres, un archivo por ejercicio, nada por llenar en lo que se copia,
   figuras que salen de un archivo de ese ejercicio, fecha de referencia dentro del archivo.
4. Un programa crea los archivos de práctica reales (Excel y Word), las figuras a partir de esos archivos, la guía
   en Word y el .zip.
5. Primera pasada: el verificador, sobre la guía y los archivos de práctica. Segunda pasada: la revisión del
   contenido, un bloque por ejercicio. Una sola corrección; lo que quede va a la entrega como pendiente.
6. Ejecución de cada ejercicio como un alumno: las fórmulas con Excel y los prompts con Claude, y la comparación con
   la respuesta correcta de la ficha (PLAN.md §0, decisión 35). Una fórmula que da error se corrige una vez; una
   diferencia con la ficha va a la entrega como pendiente. No hay guía del profesor.
"""

import asyncio
import json
import re
import shutil
from datetime import datetime
from pathlib import Path

import openpyxl
from pydantic import ValidationError

from app import agente, entrega, office, skill, tokens
from app.fichas import almacen, plantillas, referencia, verificacion
from app.materiales import comun, docx, ejecucion, estilo, figuras, lectura, practica
from app.materiales.contenido import ESQUEMA_LABORATORIO, Laboratorio
from app.validacion import excel, pasada2, revision, revisor, verificador
from app.validacion.pasajes import Corpus

MATERIAL = "Laboratorio"
CLAVE = "laboratorio"
VUELTAS_DEL_VERIFICADOR = comun.VUELTAS_DEL_VERIFICADOR
SECCIONES_DE_LA_SKILL = ("Reglas comunes", "Paso 3 · Vocabulario de la sesión", "Material 3 · Laboratorio y archivos de práctica")
CARPETA_PRACTICA = "materiales/practica"            # relativa a la carpeta de la sesión, para el verificador
# Lo que se corrige por oraciones no toca nombres, números, lugares de las marcas ni los datos de los Excel:
# una celda borrada descuadraría la hoja. Esos problemas van a una corrección completa.
CAMPOS_QUE_NO_SE_CORRIGEN = comun.CAMPOS_QUE_NO_SE_CORRIGEN | {
    "nombre", "numero", "archivos", "archivo", "hoja", "rango", "lugar", "estilo", "hojas", "area"}
ESQUEMA_CORRECCION = comun.esquema_de_correccion(CLAVE, ESQUEMA_LABORATORIO)
AVISO_ADJUNTOS = "Si tu herramienta no acepta archivos, copia el texto del archivo y pégalo en el mensaje."


class NoSePuedeEmpezar(RuntimeError):
    """Faltan las fichas confirmadas o los ejercicios de la ficha de la sesión."""


class NoSePuedeRevisar(RuntimeError):
    """El revisor independiente opcional necesita un laboratorio generado sin fallas abiertas."""


class NoSePuedeAprobar(RuntimeError):
    """El laboratorio tiene fallas abiertas, está desactualizado o no se generó."""


def archivos(carpeta_curso: Path, sesion: int) -> dict[str, Path]:
    carpeta = lectura.carpeta_materiales(carpeta_curso, sesion)
    return {
        "word": carpeta / f"S{sesion}_Laboratorio.docx",
        "zip": carpeta / f"S{sesion}_Laboratorio_Archivos.zip",
        "excel": carpeta / f"S{sesion}_Laboratorio_Verificacion.xlsx",
        "entrega": carpeta / f"S{sesion}_Laboratorio_Entrega.md",
        "practica": carpeta / "practica",
        "figuras": carpeta / CLAVE / "figuras",
        "revision": carpeta / CLAVE / "revisor",
        "contenido": carpeta / CLAVE / "contenido.json",
        "ejecucion": carpeta / CLAVE / "ejecucion",
        "ejecucion_json": carpeta / CLAVE / "ejecucion.json",
        "registro": carpeta / f"S{sesion}_Laboratorio_Ejecucion.md",
        "explicaciones": carpeta / CLAVE / "explicaciones.json",
    }


# ---------- Estado ----------

def _estado(carpeta_curso: Path, sesion: int) -> dict:
    return comun.estado(carpeta_curso, sesion, CLAVE)


def _actualizar(carpeta_curso: Path, sesion: int, **cambios) -> dict:
    return comun.actualizar(carpeta_curso, sesion, CLAVE, **cambios)


def _avance(carpeta_curso: Path, sesion: int, texto: str) -> None:
    comun.avance(carpeta_curso, sesion, CLAVE, texto)


def estado(carpeta_curso: Path, sesion: int) -> dict:
    return _estado(carpeta_curso, sesion)


def gasto_de_la_corrida(carpeta_curso: Path, curso: str, sesion: int) -> dict | None:
    return comun.gasto_de_la_corrida(carpeta_curso, curso, sesion, CLAVE)


def marcar_detenida(carpeta_curso: Path, sesion: int) -> bool:
    return comun.marcar_detenida(carpeta_curso, sesion, CLAVE)


def faltan(carpeta_curso: Path, sesion: int) -> dict[str, list[str]]:
    return {"ficha": almacen.faltantes_para(carpeta_curso, sesion, CLAVE), "otros": []}


# ---------- Datos de las fichas que usa el programa ----------

def _ficha_sesion(carpeta_curso: Path, sesion: int) -> dict:
    return almacen.cargar(carpeta_curso, "sesion", sesion)


def ejercicios_de_la_ficha(carpeta_curso: Path, sesion: int) -> list[int]:
    ids = ("area", "accion", "entregable", "archivo", "problema", "respuesta")
    return almacen.bloques_llenos(_ficha_sesion(carpeta_curso, sesion), "ejercicio", plantillas.MAX_EJERCICIOS, ids)


def respuestas_a_la_herramienta(carpeta_curso: Path, sesion: int) -> dict[int, str]:
    ficha = _ficha_sesion(carpeta_curso, sesion)
    respuestas = {}
    for n in ejercicios_de_la_ficha(carpeta_curso, sesion):
        texto = almacen.valor(ficha, f"ejercicio.{n}.pregunta_herramienta").strip()
        # «No aplica», «ninguna» o «no» dicen que la herramienta no pregunta nada: no hay respuesta que exigir.
        if texto and not re.match(r"^(no aplica|no|ninguna|n/?a|-)", texto, re.I):
            respuestas[n] = texto
    return respuestas


def respuestas_para_ejecutar(carpeta_curso: Path, sesion: int) -> tuple[dict[int, str], dict[int, str]]:
    """La respuesta correcta y la respuesta exacta del alumno de cada ejercicio de la ficha, por el número que tiene
    en el laboratorio: el laboratorio sigue el orden de la ficha."""
    ficha = _ficha_sesion(carpeta_curso, sesion)
    del_alumno = respuestas_a_la_herramienta(carpeta_curso, sesion)
    correctas, alumno = {}, {}
    for numero, n in enumerate(ejercicios_de_la_ficha(carpeta_curso, sesion), start=1):
        correctas[numero] = almacen.valor(ficha, f"ejercicio.{n}.respuesta").strip()
        if n in del_alumno:
            alumno[numero] = del_alumno[n]
    return correctas, alumno


def fecha_de_referencia(carpeta_curso: Path) -> str:
    return almacen.valor(almacen.cargar(carpeta_curso, "curso"), "datos.fecha").strip()


def aviso_de_adjuntos(carpeta_curso: Path) -> str:
    """SKILL.md, «Neutralidad»: la alternativa va una sola vez, al inicio, si la herramienta puede no aceptar archivos."""
    ficha = almacen.cargar(carpeta_curso, "curso")
    adjuntos = almacen.valor(ficha, "herramientas.adjuntos").strip().lower()
    return "" if adjuntos.startswith("sí") or adjuntos.startswith("si") else AVISO_ADJUNTOS


# ---------- Pedidos al agente ----------

def _contexto(carpeta_curso: Path, sesion: int, paginas: list[str] | None = None) -> str:
    ficha_curso = almacen.ruta_ficha(carpeta_curso, "curso", extension=".md").read_text(encoding="utf-8")
    ficha_sesion = almacen.ruta_ficha(carpeta_curso, "sesion", sesion, ".md").read_text(encoding="utf-8")
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
    rutas_lectura = lectura.archivos(carpeta_curso, sesion)
    if lectura.estado(carpeta_curso, sesion).get("estado") == "aprobada" and rutas_lectura["contenido"].exists():
        partes += ["", "LECTURA APROBADA DE LA SESIÓN. Usa su vocabulario y no repitas sus ejemplos en los ejercicios:",
                   json.dumps(comun.leer_json(rutas_lectura["contenido"]).get("bloques", []), ensure_ascii=False)]
    if paginas:
        partes += referencia.texto_de_paginas(paginas)
    return "\n".join(partes)


def instrucciones_de_formato(sesion: int, aviso: str) -> str:
    return f"""
CÓMO ENTREGAR EL LABORATORIO (PLAN.md §0, decisión 33)
- Devuelve solo los datos del esquema. Un programa crea la guía en Word con esta estructura: portada, «Antes de
  empezar», la tabla de archivos, el recuadro «Antes de copiar una fórmula» si hay fórmulas, y cada ejercicio con
  «Área:», «Situación», «Archivos de práctica», «Pasos», sus recuadros y «{docx.MEJORA}». También crea los archivos
  de práctica reales, la figura de cada ejercicio que la necesite y el .zip.
- antes_de_empezar:
  - contexto: de 2 a 4 oraciones con la empresa o institución del caso, qué hace y qué debe hacer ahora, y la fecha
    de referencia de la ficha. El programa agrega «{docx.CADA_UNO_SOLO}».
  - tablas: las tablas que usan varios ejercicios (por ejemplo, unos criterios), o ninguna. Sin la tabla de archivos:
    la pone el programa.
  - reglas: las reglas del caso que valen en todos los ejercicios, una por elemento. Una regla propia del curso
    dice «en este curso».
- ejercicios: los de la ficha de la sesión, en su orden, numerados desde 1. De menor a mayor dificultad. Las áreas
  rotan: dos ejercicios seguidos no son de la misma área.
  - titulo: una acción concreta («Revisa la opción de tratamiento de cada riesgo»). Sin «Ejercicio N».
  - area: el área del caso.
  - situacion: de 2 a 3 oraciones: quién pide qué y para qué sirve el entregable.
  - archivos: los nombres exactos de los archivos de práctica de ese ejercicio.
  - pasos: en el orden real. Cada paso es una sola acción y nombra la hoja y la celda o la columna exactas. Puedes
    poner en negrita el nombre de una hoja o de un apartado con **dos asteriscos**. Si un archivo hace falta, el paso
    dice «adjunta el archivo». Si la herramienta debe detenerse a preguntar, ordénalo y escribe la respuesta exacta.
  - figura: una por ejercicio como máximo. Ponla en el paso que pide ubicar algo en el archivo: una columna, una
    celda, un rango o un párrafo. Si un paso pide ubicar algo, la figura es obligatoria: un programa lo revisa.
    Si ningún paso pide ubicar algo, deja todas en null. No menciones la figura en el
    texto: el programa agrega «Mira la figura N». La figura no muestra la respuesta.
    - Excel: «hoja», «rango» (hasta 8 columnas y 16 filas, por ejemplo «A1:E9») y «marcas» con la celda o el rango
      que señala («C5», «B2:B9»). La fila 1 es la de los encabezados.
    - Word: «marcas» con un trozo del texto del archivo, copiado tal cual. «hoja» y «rango» vacíos.
    - descripcion: una línea que dice qué muestra.
  - copiar: de uno a cuatro recuadros, con su «tipo»:
    - «prompt»: una línea por parte: rol, contexto, tarea, formato de salida y restricciones.
    - «formula»: «titulo» como «Fórmula 1 · Revisa si el riesgo se puede aceptar», «explicacion» con una línea que
      dice qué avisa o calcula, y en «lineas» la fórmula con los nombres de las funciones en español y los datos
      separados por comas («=SI(Y(H2="Aceptar",E2>4),"NO SE PUEDE ACEPTAR","OK")»). Un programa ejecuta los pasos
      tal cual y Excel calcula el archivo (decisión 35), así que se escriben con estas formas exactas:
      «Copia la fórmula 1 en la celda L2», «Copia la celda L2 hacia abajo, hasta la fila 9» y
      «Escribe **Total** en la celda A10». Un paso que cambia de hoja la nombra: «Entra a la hoja **Riesgos**».
    - «plantilla»: un texto que el alumno completa; solo si completarlo es el tema del ejercicio.
    Lo que se copia funciona tal cual: sin corchetes, guiones bajos ni espacios por llenar, salvo en una plantilla.
  - Comillas («» o “”) solo para copiar texto tal cual de una fuente: el verificador las busca en las fuentes. El
    texto que el alumno escribe o que la herramienta debe usar va en **negrita**, sin comillas.
  - mejora: «texto» con lo que se agrega y para qué; «pasos» y «copiar» si hacen falta, con las mismas reglas.
  - No escribas «Cómo se ve un buen resultado» ni «Criterio de calidad»: la skill no los permite.
- archivos: cada archivo de práctica, con nombre S{sesion}_E[ejercicio]_[descripcion-corta] en minúsculas y con
  guiones («S{sesion}_E1_riesgos-rrhh.xlsx»). Excel (.xlsx) para datos y Word (.docx) para textos. Cada ejercicio
  usa solo sus archivos: ninguno necesita el resultado de otro.
  - descripcion: lo que dirá la tabla de archivos («Ocho riesgos de Recursos Humanos con su opción de tratamiento»).
  - Excel: «hojas», cada una con un nombre corto, «encabezados» y «filas». Datos ficticios y coherentes con los datos
    fijos del caso. Los números van como números. Deja vacías las columnas donde el alumno copiará las fórmulas.
  - Word: «parrafos» (estilo «titulo», «texto» o «lista») y, si hace falta, «tabla».
  - Si el ejercicio depende de fechas o plazos, escribe la fecha de referencia de la ficha dentro del archivo.
  - problema: el problema que el archivo trae a propósito, según la ficha. No va en la guía del alumno.
- Un programa ejecuta cada ejercicio como un alumno: cada prompt en una conversación nueva con Claude, con el
  texto de los archivos adjuntos, y cada fórmula con Excel. Lo que sale se compara con la respuesta correcta de la
  ficha.
- pasajes: los pasajes de las fuentes que usaste: «oracion» del laboratorio que sostiene, la fuente, la ubicación y
  en «texto» el pasaje copiado, de 40 palabras como máximo.
- decisiones: una entrada por punto, con «texto» y «tipo» («sin fuente», «decisión» o «nota»).
""" + (f"- El programa agrega al inicio de la guía: «{aviso}». No lo repitas.\n" if aviso else "")


def pedido_de_redaccion(carpeta_curso: Path, sesion: int, paginas: list[str] | None = None) -> str:
    citar = ("Si citas una fuente, toma el pasaje de las páginas del material de referencia, que están arriba." if paginas
             else "Si citas una fuente, busca con Grep y lee con Read los pasajes antes de escribir.")
    return "\n".join([
        _contexto(carpeta_curso, sesion, paginas),
        instrucciones_de_formato(sesion, aviso_de_adjuntos(carpeta_curso)),
        "TAREA: prepara el laboratorio de la sesión. Actúa como diseñador instruccional. Toma los ejercicios de la ficha",
        "de la sesión: su área, la acción, el entregable, el archivo de práctica con su problema y la respuesta correcta.",
        citar,
        "Antes de entregar, ejecuta mentalmente cada ejercicio como un alumno, con sus archivos: cada paso se puede hacer,",
        "lo que se copia funciona tal cual y el resultado es el entregable de la ficha.",
    ])


def _pedido_con_problemas(carpeta_curso, sesion, datos: dict, problemas: list[str], como_entregar: list[str]) -> str:
    return "\n".join([
        _contexto(carpeta_curso, sesion),
        instrucciones_de_formato(sesion, aviso_de_adjuntos(carpeta_curso)),
        comun.REGLAS_DE_CORRECCION,
        *como_entregar,
        "",
        "LABORATORIO ACTUAL:",
        json.dumps(datos, ensure_ascii=False),
        "",
        "PROBLEMAS QUE ENCONTRÓ LA VALIDACIÓN:",
        *[f"- {p}" for p in problemas],
    ])


def pedido_de_cambios(carpeta_curso, sesion, datos, problemas) -> str:
    return _pedido_con_problemas(carpeta_curso, sesion, datos, problemas, [
        "CÓMO ENTREGAR LA CORRECCIÓN",
        "- En «cambios», una entrada por oración que cambias: «oracion» copiada tal cual y «nueva» con el texto nuevo.",
        "  Para eliminar una oración, deja «nueva» vacío. No devuelvas las oraciones que no cambian.",
    ])


def pedido_de_correccion(carpeta_curso, sesion, datos, problemas) -> str:
    return _pedido_con_problemas(carpeta_curso, sesion, datos, problemas,
                                 ["Devuelve el laboratorio completo con el mismo esquema."])


# ---------- Corrección por ejercicio ----------
# Cuando todos los problemas son de unos ejercicios, se reescriben solo esos ejercicios y sus archivos. Reescribir el
# laboratorio entero costaba unos 0,58 USD por corrección.

_PROPIEDADES = ESQUEMA_LABORATORIO["properties"]
ESQUEMA_CORRECCION_POR_EJERCICIO = {
    "type": "object",
    "properties": {"ejercicios": _PROPIEDADES["ejercicios"], "archivos": _PROPIEDADES["archivos"],
                   "pasajes": _PROPIEDADES["pasajes"], "explicaciones": comun.ESQUEMA_EXPLICACIONES,
                   "datos_nuevos": {"type": "array", "items": {"type": "string"}}},
    "required": ["ejercicios", "archivos", "pasajes", "explicaciones", "datos_nuevos"],
    "additionalProperties": False,
}
_EJERCICIO = re.compile(r"\bejercicio (\d+)\b|\bS\d+_E(\d+)_", re.I)


def ejercicios_nombrados(textos: list[str]) -> set[int] | None:
    """Los ejercicios a los que pertenecen los problemas. None si alguno no es de un ejercicio (por ejemplo, de
    «Antes de empezar» o del .zip): entonces se corrige el laboratorio completo."""
    numeros = set()
    for texto in textos:
        encontrados = {int(a or b) for a, b in _EJERCICIO.findall(texto)}
        if not encontrados:
            return None
        numeros |= encontrados
    return numeros or None


def pedido_de_correccion_por_ejercicios(carpeta_curso, sesion, datos, problemas, numeros: set[int]) -> str:
    cuales = ", ".join(map(str, sorted(numeros)))
    return _pedido_con_problemas(carpeta_curso, sesion, datos, problemas, [
        "CÓMO ENTREGAR LA CORRECCIÓN",
        f"- Los problemas son solo de los ejercicios {cuales}. Corrige solo esos ejercicios.",
        f"- En «ejercicios», devuelve completos los ejercicios {cuales}, con su mismo número. No devuelvas los demás.",
        "- En «archivos», devuelve completos los archivos de práctica de esos ejercicios que cambias. Los que no",
        "  devuelves quedan como están. Un archivo que el ejercicio ya no nombra se quita.",
        "- En «pasajes», solo los pasajes nuevos que necesitan las oraciones que cambias.",
    ])


def aplicar_por_ejercicios(datos: dict, respuesta: dict, numeros: set[int]) -> tuple[dict, list[int]]:
    """Reemplaza los ejercicios corregidos y sus archivos. Los demás no se tocan. Devuelve también los ejercicios
    pedidos que no volvieron."""
    nuevo = json.loads(json.dumps(datos))
    devueltos = {e["numero"]: e for e in respuesta.get("ejercicios", []) if e["numero"] in numeros}
    nuevo["ejercicios"] = [devueltos.get(e["numero"], e) for e in nuevo.get("ejercicios", [])]
    nombrados = {n for e in devueltos.values() for n in e.get("archivos", [])}
    archivos = {a["nombre"]: a for a in nuevo.get("archivos", [])
                if practica.numero_de_ejercicio(a["nombre"]) not in devueltos or a["nombre"] in nombrados}
    for a in respuesta.get("archivos", []):
        if practica.numero_de_ejercicio(a["nombre"]) in numeros:
            archivos[a["nombre"]] = a
    nuevo["archivos"] = list(archivos.values())
    vistos = {(p.get("oracion", ""), p["texto"]) for p in nuevo.get("pasajes", [])}
    nuevo["pasajes"] = nuevo.get("pasajes", []) + [p for p in respuesta.get("pasajes", [])
                                                     if (p.get("oracion", ""), p["texto"]) not in vistos]
    return nuevo, sorted(numeros - set(devueltos))


# ---------- Estructura ----------

def _validar(datos: dict, carpeta_curso: Path, sesion: int) -> tuple[Laboratorio | None, list[str]]:
    try:
        contenido = Laboratorio.model_validate(datos)
    except ValidationError as error:
        return None, [f"FALLA · estructura · {'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()]
    problemas = practica.revisar(contenido, sesion, len(ejercicios_de_la_ficha(carpeta_curso, sesion)),
                                 fecha_de_referencia(carpeta_curso), respuestas_a_la_herramienta(carpeta_curso, sesion))
    return (None if problemas else contenido), problemas


def _tiene_formulas(ruta: Path) -> bool:
    libro = openpyxl.load_workbook(ruta)
    return any(isinstance(c.value, str) and c.value.startswith("=") for h in libro.worksheets for f in h.iter_rows()
               for c in f)


def bloques_de(contenido: Laboratorio) -> list[pasada2.Bloque]:
    """Un bloque por ejercicio, con sus archivos: la revisión del contenido trabaja ejercicio por ejercicio."""
    separar = verificador.verificar.separar_oraciones
    por_nombre = {a.nombre: a for a in contenido.archivos}

    def oraciones(*textos):
        return [o for t in textos if t for o in separar(t)]

    antes = contenido.antes_de_empezar
    bloques = [pasada2.Bloque("Antes de empezar", oraciones(
        *antes.contexto, *antes.reglas,
        *[" | ".join(fila) for tabla in antes.tablas for fila in [tabla.encabezados, *tabla.filas]]))]
    for e in contenido.ejercicios:
        recuadros = [*e.copiar, *e.mejora.copiar]
        textos = [e.titulo, e.situacion, *[docx.sin_marcas(p.texto) for p in e.pasos],
                  *[p.figura.descripcion for p in e.pasos if p.figura],
                  *[f"{r.titulo}: {r.explicacion}" for r in recuadros if r.explicacion],
                  *[f"{r.titulo}: {linea}" for r in recuadros for linea in r.lineas],
                  e.mejora.texto, *[docx.sin_marcas(p) for p in e.mejora.pasos]]
        for nombre in e.archivos:
            archivo = por_nombre.get(nombre)
            if archivo is None:
                continue
            textos.append(f"Archivo {nombre}: {archivo.descripcion}")
            textos += [p.texto for p in archivo.parrafos]
            for hoja in archivo.hojas:
                textos += [f"{nombre} · {hoja.nombre} · " + " | ".join(str(v) for v in fila if v is not None)
                           for fila in [hoja.encabezados, *hoja.filas]]
        bloques.append(pasada2.Bloque(f"Ejercicio {e.numero} · {e.titulo}", oraciones(*textos)))
    return bloques


INDICACIONES_DE_REVISION = (
    "Es la guía de laboratorio del alumno y sus archivos de práctica. Revisa que cada ejercicio funcione solo, con sus "
    "archivos; que lo que el alumno copia funcione tal cual; que los datos del caso cuadren entre la guía, los archivos y "
    "los datos fijos de la ficha; y que ninguna parte de la guía dé la respuesta del ejercicio. El problema que un "
    "archivo trae a propósito no es un error: es parte del ejercicio.")


# ---------- Generación ----------

class _Trabajo:
    def __init__(self, carpeta_curso, curso, sesion, rutas, consulta, recalcular, contar_paginas, ejecutar=None):
        self.carpeta_curso, self.curso, self.sesion, self.rutas = carpeta_curso, curso, sesion, rutas
        self.consulta = consulta
        self._recalcular = recalcular or office.recalcular_excel
        self._contar_paginas = contar_paginas or verificador.verificar._contar_paginas_con_word
        self._ejecutar = ejecutar or ejecucion.ejecutar
        self.carpeta_sesion = almacen.carpeta_sesion(carpeta_curso, sesion)
        self.identidad = estilo.desde_ficha(carpeta_curso)
        self.portada = lectura._portada(carpeta_curso, sesion)
        self.portada.material = MATERIAL
        self.aviso = aviso_de_adjuntos(carpeta_curso)
        self.comun = {"curso": curso, "sesion": f"S{sesion}", "material": CLAVE, "cwd": carpeta_curso / "fuentes_texto",
                      "herramientas": ("Read", "Grep", "Glob"), "consulta": consulta}
        self.datos: dict = {}
        self.contenido: Laboratorio | None = None
        self.explicaciones: dict[str, str] = {}
        self.historial: list[dict] = []
        self.correcciones = {"verificador": 0, "revisión": 0}
        self.datos_agregados: list[str] = []
        self.resultado = None
        self.fallas: list[str] = []
        self.descartados: list[dict] = []
        self.imagenes: dict = {}
        self.paginas: int | None = None
        self.vuelta = 0

    def avance(self, texto: str) -> None:
        _avance(self.carpeta_curso, self.sesion, texto)

    async def ejecutar(self, solo: set[int] | None = None) -> list[ejecucion.Ejecucion]:
        correctas, del_alumno = respuestas_para_ejecutar(self.carpeta_curso, self.sesion)
        return await self._ejecutar(
            self.contenido, carpeta_practica=self.rutas["practica"], carpeta=self.rutas["ejecucion"],
            respuestas_ficha=correctas, respuestas_alumno=del_alumno, recalcular=self._recalcular,
            llamada={"curso": self.curso, "sesion": f"S{self.sesion}", "material": CLAVE, "consulta": self.consulta},
            solo=solo, avance=self.avance)

    async def ejecutar_y_corregir(self) -> list[ejecucion.Ejecucion]:
        """Ejecuta cada ejercicio. Una fórmula que da error lleva a una corrección completa y a una nueva ejecución de
        esos ejercicios; si sigue, queda como falla. Las diferencias con la ficha quedan como pendientes."""
        self.avance("Ejecutando cada ejercicio como un alumno: las fórmulas con Excel y los prompts con Claude.")
        ejecuciones = await self.ejecutar()
        fallas = [f for x in ejecuciones for f in x.fallas]
        if fallas:
            self.correcciones["ejecución"] = len(fallas)
            await self.corregir(fallas, completa=True, ejercicios={x.numero for x in ejecuciones if x.fallas})
            if not await self.verificar():
                return ejecuciones
            con_fallas = {x.numero for x in ejecuciones if x.fallas}
            nuevas = {x.numero: x for x in await self.ejecutar(solo=con_fallas)}
            ejecuciones = [nuevas.get(x.numero, x) for x in ejecuciones]
            self.fallas = [f for x in ejecuciones for f in x.fallas]
        return ejecuciones

    def contar_paginas(self, ruta: Path) -> int:
        self.paginas = self._contar_paginas(ruta)
        return self.paginas

    def corpus(self) -> Corpus:
        return Corpus.del_curso(self.carpeta_curso, self.sesion)

    def crear_archivos(self, contenido: Laboratorio) -> list[str]:
        """Archivos de práctica reales, figuras sacadas de ellos, guía en Word y .zip. Devuelve los problemas de
        las figuras que no se leen sin ampliar."""
        rutas_practica = practica.crear(contenido, self.identidad, self.rutas["practica"])
        for ruta in rutas_practica:
            if ruta.suffix == ".xlsx" and _tiene_formulas(ruta):
                self._recalcular(ruta)
        shutil.rmtree(self.rutas["figuras"], ignore_errors=True)
        self.imagenes, problemas = {}, []
        for e in contenido.ejercicios:
            for i, paso in enumerate(e.pasos, start=1):
                if paso.figura is None:
                    continue
                imagen = figuras.hacer(self.rutas["practica"] / paso.figura.archivo, paso.figura,
                                       self.rutas["figuras"] / f"E{e.numero}_paso{i}.png")
                if imagen.letra_pt < figuras.LETRA_MINIMA_PT:
                    problemas.append(f"FALLA · figura · ejercicio {e.numero}, paso {i}: en la página, su letra queda de "
                                     f"{imagen.letra_pt} puntos y no se lee sin ampliar. Muestra menos columnas o filas.")
                self.imagenes[(e.numero, i)] = imagen
        hojas = {a.nombre: [h.nombre for h in a.hojas] for a in contenido.archivos}
        formulas = [l for e in contenido.ejercicios for r in [*e.copiar, *e.mejora.copiar] if r.tipo == "formula"
                    for l in r.lineas]
        docx.generar_laboratorio(contenido, self.identidad, self.portada, self.rutas["word"], self.imagenes, self.aviso,
                                 nombre_zip=self.rutas["zip"].name, hojas=hojas,
                                 funciones=practica.funciones_usadas(formulas), sesion=self.sesion)
        practica.empaquetar(rutas_practica, self.rutas["zip"])
        en_zip, en_carpeta = practica.nombres_del_zip(self.rutas["zip"]), sorted(a.nombre for a in contenido.archivos)
        if en_zip != en_carpeta:
            problemas.append(f"FALLA · nombre de archivo · el .zip trae {en_zip}; la guía nombra {en_carpeta}.")
        return problemas

    async def verificar(self) -> bool:
        for intento in range(VUELTAS_DEL_VERIFICADOR + 1):
            self.vuelta += 1
            contenido, problemas = _validar(self.datos, self.carpeta_curso, self.sesion)
            completa, ejercicios = bool(problemas), None
            comun.guardar_json(self.rutas["contenido"], self.datos)
            if contenido is not None:
                self.contenido = contenido
                problemas = self.crear_archivos(contenido)
                completa, ejercicios = bool(problemas), ejercicios_nombrados(problemas)
                if not problemas:
                    configuracion = verificador.configuracion_del_material(
                        self.carpeta_sesion, MATERIAL, carpeta_practica=CARPETA_PRACTICA)
                    practica_ = sorted(self.rutas["practica"].iterdir())
                    self.resultado = verificador.ejecutar(configuracion, [self.rutas["word"], *practica_, self.rutas["zip"]],
                                                          self.rutas["excel"], self.explicaciones, self.contar_paginas)
                    if comun.explicar_literales(self.resultado, self.explicaciones, self.corpus()):
                        comun.guardar_json(self.rutas["explicaciones"], self.explicaciones)
                        verificador.anotar_explicaciones(self.rutas["excel"], self.explicaciones)
                    excel.anotar_reglas(self.rutas["excel"], comun.AVISOS_INFORMATIVOS, comun.NOTA_INFORMATIVA)
                    fallas, avisos = comun.hallazgos_abiertos(self.resultado, self.explicaciones)
                    self.avance(f"Verificador, vuelta {self.vuelta}: {self.resultado.resumen()}.")
                    problemas = [comun.texto_de(h) for h in fallas + avisos]
                    nombres = {a.nombre for a in contenido.archivos}
                    # Sin oración, o en un archivo de práctica: se arregla con el laboratorio completo.
                    completa = any(not h.oracion or h.seccion.split(" · ")[0] in nombres for h in fallas + avisos)
                    ejercicios = ejercicios_nombrados([f"{h.seccion} {comun.texto_de(h)}" for h in fallas + avisos])
                    self.historial += comun.historial(fallas + avisos, self.vuelta)
            self.fallas = problemas
            if not problemas:
                return True
            if intento == VUELTAS_DEL_VERIFICADOR:
                self.avance(f"Quedan {len(problemas)} fallas después de {VUELTAS_DEL_VERIFICADOR} correcciones. "
                            "No se puede aprobar el laboratorio con fallas.")
                return False
            self.correcciones["verificador"] += len(problemas)
            await self.corregir(problemas, completa, ejercicios)
        return False

    async def revisar(self, bloques: list[pasada2.Bloque], etapa: str) -> revision.Resultado:
        resultado = await revision.ejecutar(
            bloques, corpus=self.corpus(), anclas=[p.model_dump() for p in self.contenido.pasajes],
            curso=self.curso, sesion=self.sesion, material=CLAVE, nombre_material=MATERIAL, etapa=etapa,
            indicaciones=INDICACIONES_DE_REVISION, consulta=self.consulta)
        self.descartados += resultado.descartados
        return resultado

    async def corregir(self, problemas: list[str], completa: bool, ejercicios: set[int] | None = None) -> None:
        vuelta = self.vuelta
        if completa and ejercicios:
            cuales = ", ".join(map(str, sorted(ejercicios)))
            self.avance(f"Corrigiendo solo los ejercicios {cuales}: {comun.cuantos(len(problemas), 'problema')}.")
            respuesta = await agente.consultar(
                pedido_de_correccion_por_ejercicios(self.carpeta_curso, self.sesion, self.datos, problemas, ejercicios),
                tarea="correccion", esquema=ESQUEMA_CORRECCION_POR_EJERCICIO,
                etapa=f"corrección de ejercicios {vuelta}", **self.comun)
            self.datos, no_volvieron = aplicar_por_ejercicios(self.datos, respuesta, ejercicios)
            if no_volvieron:
                self.avance(f"La corrección no devolvió los ejercicios {', '.join(map(str, no_volvieron))}.")
        elif completa:
            self.avance(f"Corrigiendo el laboratorio completo: {comun.cuantos(len(problemas), 'problema')}.")
            respuesta = await agente.consultar(pedido_de_correccion(self.carpeta_curso, self.sesion, self.datos, problemas),
                                               tarea="correccion", esquema=ESQUEMA_CORRECCION,
                                               etapa=f"corrección completa {vuelta}", **self.comun)
            self.datos = respuesta[CLAVE]
        else:
            self.avance(f"Corrigiendo {comun.cuantos(len(problemas), 'problema')}.")
            respuesta = await agente.consultar(pedido_de_cambios(self.carpeta_curso, self.sesion, self.datos, problemas),
                                               tarea="correccion_oraciones", esquema=comun.ESQUEMA_CAMBIOS,
                                               etapa=f"corrección {vuelta}", **self.comun)
            self.datos, no_encontradas = comun.aplicar_cambios(self.datos, respuesta["cambios"], CAMPOS_QUE_NO_SE_CORRIGEN)
            if no_encontradas:
                self.avance(f"{comun.cuantos(len(no_encontradas), 'oración')} a cambiar no se encontraron.")
        for e in respuesta["explicaciones"]:
            self.explicaciones[verificador.clave_de_hallazgo(e["regla"], e["oracion"])] = e["explicacion"]
        comun.guardar_json(self.rutas["explicaciones"], self.explicaciones)
        nuevos = almacen.agregar_datos_fijos(self.carpeta_curso, respuesta.get("datos_nuevos", []), f"Laboratorio S{self.sesion}")
        if nuevos:
            self.datos_agregados += nuevos
            for numero in almacen.sesiones_confirmadas(self.carpeta_curso):
                verificacion.escribir(self.carpeta_curso, numero)
            self.avance(f"Datos nuevos del caso agregados a la ficha del curso: {len(nuevos)}.")


def _limpiar(rutas: dict[str, Path]) -> None:
    for clave in ("word", "zip", "excel", "entrega", "contenido", "explicaciones", "registro", "ejecucion_json"):
        try:
            rutas[clave].unlink(missing_ok=True)
        except OSError:
            pass
    try:
        rutas["excel"].with_suffix(".json").unlink(missing_ok=True)
    except OSError:
        pass
    for clave in ("practica", "figuras", "revision", "ejecucion"):
        shutil.rmtree(rutas[clave], ignore_errors=True)


async def generar(carpeta_curso: Path, curso: str, sesion: int, consulta=agente.query, recalcular=None,
                  contar_paginas=None, ejecutar=None) -> dict:
    """`recalcular` reemplaza a Excel en las pruebas (calcula las fórmulas antes de sacar las figuras); `ejecutar`
    reemplaza la ejecución de los ejercicios."""
    if not almacen.puede_empezar_material(carpeta_curso, sesion):
        raise NoSePuedeEmpezar("Guarda completas la ficha del curso y la ficha de la sesión antes de generar el laboratorio.")
    faltan_ = almacen.faltantes_para(carpeta_curso, sesion, CLAVE)
    if faltan_:
        raise NoSePuedeEmpezar("Completa la ficha de la sesión antes de generar el laboratorio: " + " ".join(faltan_))
    rutas = archivos(carpeta_curso, sesion)
    rutas["contenido"].parent.mkdir(parents=True, exist_ok=True)
    _actualizar(carpeta_curso, sesion, estado="trabajando", previo="", avance=[], error="", desactualizado=False,
                entrega={}, aprobada="", revisor={}, corrida_desde=tokens.lineas(curso))
    try:
        return await _generar(carpeta_curso, curso, sesion, rutas, consulta, recalcular, contar_paginas, ejecutar)
    except asyncio.CancelledError:
        marcar_detenida(carpeta_curso, sesion)
        raise
    except Exception as error:
        _actualizar(carpeta_curso, sesion, estado="error", error=str(error))
        raise


async def _generar(carpeta_curso, curso, sesion, rutas, consulta, recalcular, contar_paginas, ejecutar) -> dict:
    inicio = tokens.lineas(curso)
    skill.comprobar(secciones=SECCIONES_DE_LA_SKILL + pasada2.SECCIONES_DE_LA_SKILL + revisor.SECCIONES_DE_LA_SKILL,
                    subsecciones=revisor.SUBSECCIONES_DE_LA_SKILL)
    trabajo = _Trabajo(carpeta_curso, curso, sesion, rutas, consulta, recalcular, contar_paginas, ejecutar)
    verificador.verificar.leer_configuracion(
        verificador.configuracion_del_material(trabajo.carpeta_sesion, MATERIAL, carpeta_practica=CARPETA_PRACTICA))
    _limpiar(rutas)

    trabajo.avance("Leyendo las fichas y las fuentes y escribiendo el laboratorio y sus archivos de práctica.")
    # Con material de referencia, sus páginas van en el pedido y la redacción no necesita herramientas.
    paginas = referencia.paginas(carpeta_curso, _ficha_sesion(carpeta_curso, sesion))
    opciones = trabajo.comun if paginas is None else {**trabajo.comun, "cwd": None, "herramientas": ()}
    trabajo.datos = await agente.consultar(pedido_de_redaccion(carpeta_curso, sesion, paginas), tarea="redaccion",
                                           esquema=ESQUEMA_LABORATORIO, etapa="redacción", **opciones)
    errores: list[revision.Error] = []
    revisados = 0
    ejecuciones: list[ejecucion.Ejecucion] = []
    if await trabajo.verificar():
        errores, revisados = await comun.revisar_y_corregir(trabajo, bloques_de)
        if not trabajo.fallas:
            ejecuciones = await trabajo.ejecutar_y_corregir()
    if ejecuciones:
        comun.guardar_json(rutas["ejecucion_json"], [x.a_dict() for x in ejecuciones])
        rutas["registro"].write_text(ejecucion.a_markdown(ejecuciones, f"Ejecución · {MATERIAL} · Sesión {sesion}",
                                                          agente.leer_tarea("ejecucion")["modelo"]), encoding="utf-8")
    diferencias = [p for x in ejecuciones for p in x.pendientes()]

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
    material = _actualizar(
        carpeta_curso, sesion,
        estado=estado_final,
        resumen=trabajo.resultado.resumen() if trabajo.resultado else "",
        problemas=trabajo.fallas + [e.describir() for e in pendientes] + sin_fuente + diferencias,
        correcciones=trabajo.correcciones,
        revision={"bloques": revisados, "errores": len(errores), "corregidos": sum(e.estado == "corregido" for e in errores),
                  "pendientes": len(pendientes), "descartados": len(trabajo.descartados)},
        datos_agregados=trabajo.datos_agregados,
        avisos_de_diseno=trabajo.identidad.avisos,
        avisos_explicados=sum(1 for h in hallazgos if h.nivel == "AVISO" and h.regla not in comun.AVISOS_INFORMATIVOS),
        avisos_informativos=sum(1 for h in hallazgos if h.nivel == "AVISO" and h.regla in comun.AVISOS_INFORMATIVOS),
        paginas=trabajo.paginas,
        ejercicios=len(final.ejercicios) if final else 0,
        archivos_practica=[{"nombre": a.nombre, "ejercicio": practica.numero_de_ejercicio(a.nombre),
                            "problema": a.problema} for a in (final.archivos if final else [])],
        figuras=len(trabajo.imagenes),
        ejecucion=_resumen_de_ejecucion(ejecuciones),
        decisiones=[d.model_dump() for d in decisiones],
        archivos={"word": rutas["word"].name, "zip": rutas["zip"].name, "excel": rutas["excel"].name,
                  "entrega": rutas["entrega"].name, **({"registro": rutas["registro"].name} if ejecuciones else {})},
        costo=tokens.total(curso, sesion=f"S{sesion}", material=CLAVE, desde_linea=inicio),
        fecha=datetime.now().isoformat(timespec="seconds"),
    )
    _escribir_entrega(carpeta_curso, sesion, material)
    trabajo.avance({"verificada": "Laboratorio listo para tu aprobación.",
                    "con pendientes": f"Laboratorio listo, con "
                                      f"{comun.cuantos(len(pendientes) + len(sin_fuente) + len(diferencias), 'pendiente')} "
                                      "para que decidas.",
                    "con fallas": "El laboratorio quedó con fallas del verificador."}[estado_final])
    return _estado(carpeta_curso, sesion)


def _resumen_de_ejecucion(ejecuciones: list[ejecucion.Ejecucion]) -> dict:
    return {"ejercicios": len(ejecuciones), "formulas": sum(len(x.celdas) for x in ejecuciones),
            "conversaciones": sum(x.conversaciones for x in ejecuciones),
            "coinciden": [x.numero for x in ejecuciones if x.coincide],
            "diferencias": sum(len(x.diferencias) for x in ejecuciones),
            "descartadas": sum(x.descartadas for x in ejecuciones),
            "no_pude": [n for x in ejecuciones for n in x.no_pude],
            "modelo": agente.leer_tarea("ejecucion")["modelo"] if ejecuciones else ""}


def _escribir_entrega(carpeta_curso: Path, sesion: int, material: dict) -> dict:
    material = _actualizar(carpeta_curso, sesion, entrega=_entrega(material))
    archivos(carpeta_curso, sesion)["entrega"].write_text(
        entrega.a_markdown(material["entrega"], f"Entrega · {MATERIAL} · Sesión {sesion}"), encoding="utf-8")
    return material


def _entrega(material: dict) -> dict:
    archivos_ = material["archivos"]
    practica_ = material.get("archivos_practica") or []
    lineas_archivos = [
        f"{archivos_['word']}: la guía del alumno, con {comun.cuantos(material['ejercicios'], 'ejercicio')}"
        + (f" y {comun.cuantos(material['figuras'], 'figura')}" if material.get("figuras") else "")
        + (f", {material['paginas']} páginas." if material.get("paginas") else "."),
        f"{archivos_['zip']}: los {comun.cuantos(len(practica_), 'archivo')} de práctica: "
        + ", ".join(a["nombre"] for a in practica_) + ".",
        f"{archivos_['excel']}: el archivo de verificación, con la hoja Hallazgos.",
        f"{archivos_['entrega']}: esta entrega, en texto.",
        *([f"{archivos_['registro']}: el registro de la ejecución de cada ejercicio: lo que se copió, lo que respondió "
           "la herramienta y lo que calculó Excel."] if archivos_.get("registro") else []),
    ]
    probe = [
        "Creé cada archivo de práctica con un programa y saqué cada figura del archivo real, con las marcas en ámbar.",
        "Comprobé que los nombres de archivo coinciden en la guía, en la tabla de archivos y en el .zip.",
        "Comprobé que cada ejercicio usa solo sus archivos y que lo que el alumno copia no tiene espacios por llenar.",
    ]
    ej = material.get("ejecucion") or {}
    if ej.get("ejercicios"):
        probe.append(f"Ejecuté {comun.cuantos(ej['ejercicios'], 'ejercicio')} como un alumno: "
                     f"{comun.cuantos(ej['formulas'], 'celda')} con fórmula calculadas con Excel y "
                     f"{comun.cuantos(ej['conversaciones'], 'conversación')} nuevas con Claude.")
        if ej["coinciden"]:
            probe.append("Coinciden con la respuesta correcta de la ficha: "
                         + ", ".join(f"ejercicio {n}" for n in ej["coinciden"]) + ".")
        if ej.get("descartadas"):
            probe.append(f"Diferencias descartadas porque su prueba no está en la ficha ni en lo que salió: "
                         f"{ej['descartadas']}.")
    c = material["correcciones"]
    r = material.get("revision") or {}
    valide = [f"Verificador, sobre la guía y los archivos de práctica: {material['resumen']}." if material["resumen"]
              else "El verificador no llegó a correr.",
              *([f"Avisos explicados en la hoja Hallazgos: {material['avisos_explicados']}."]
                if material.get("avisos_explicados") else []),
              *([f"Avisos informativos: {material['avisos_informativos']}. Están en la hoja Hallazgos; no obligan a "
                 "corregir."] if material.get("avisos_informativos") else []),
              f"Fallas del verificador corregidas: {c['verificador']}.",
              *([f"Fórmulas con error al ejecutarlas, enviadas a corrección: {c['ejecución']}."]
                if c.get("ejecución") else [])]
    if r.get("bloques"):
        texto = f"Revisión del contenido: {comun.cuantos(r['bloques'], 'ejercicio')}, {comun.cuantos(r['errores'], 'error')} con prueba"
        if r["errores"]:
            texto += f" ({comun.cuantos(r['corregidos'], 'corregido')} y {comun.cuantos(r['pendientes'], 'pendiente')})"
        valide.append(texto + ".")
    rev = material.get("revisor") or {}
    if rev:
        valide.append(f"Revisor independiente (lo pediste tú): {comun.cuantos(rev['hallazgos'], 'hallazgo')} con prueba. "
                      f"Costo: {rev['costo']['costo_usd']:.2f} USD estimados.")
    costo = material["costo"]
    valide.append(f"Costo de este laboratorio: {costo['llamadas']} llamadas, {costo['costo_usd']:.2f} USD estimados.")
    if ej.get("ejercicios"):
        no_pude = [f"Ejecuté los prompts con Claude ({ej['modelo']}), con el texto de cada archivo dentro del mensaje. "
                   "La herramienta de los alumnos puede responder distinto.",
                   "Las indicaciones que dependen de lo que responda la herramienta («Si falta…») no se ejecutaron.",
                   *ej["no_pude"]]
    else:
        no_pude = ["No ejecuté los ejercicios porque quedaron fallas antes de llegar a la ejecución."]
    if not r.get("bloques"):
        no_pude.append("La revisión del contenido no corrió porque quedaron fallas del verificador.")
    decidi = [d["texto"] for d in material["decisiones"] if d["tipo"] == "decisión"]
    decidi += [f"Problema sembrado en {a['nombre']}: {a['problema']}" for a in practica_ if a.get("problema")]
    decidi += [f"Dato nuevo del caso, agregado a la ficha del curso: {d}" for d in material["datos_agregados"]]
    if not decidi:
        decidi.append("Nada que revisar: todo salió de las fichas y de las fuentes.")
    return entrega.componer(archivos=lineas_archivos, probe=probe, valide=valide,
                            pendientes=material["problemas"], no_pude=no_pude, decidi=decidi)


# ---------- Revisor independiente y aprobación ----------

async def revisar_con_revisor(carpeta_curso: Path, curso: str, sesion: int, consulta=agente.query) -> dict:
    material = _estado(carpeta_curso, sesion)
    previo = material.get("estado")
    if previo not in ("verificada", "con pendientes", "aprobada"):
        raise NoSePuedeRevisar("El revisor independiente revisa un laboratorio generado y sin fallas del verificador.")
    rutas = archivos(carpeta_curso, sesion)
    contenido = Laboratorio.model_validate(comun.leer_json(rutas["contenido"]))
    oraciones = comun.leer_json(rutas["excel"].with_suffix(".json"))["oraciones"]
    inicio = tokens.lineas(curso)
    _actualizar(carpeta_curso, sesion, estado="trabajando", previo=previo)
    _avance(carpeta_curso, sesion, "Revisor independiente: una sesión nueva lee la guía, los archivos, las fuentes y las fichas.")
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
        {"nivel": "REVISOR", "seccion": rutas["word"].name, "oracion": h.oracion, "regla": f"revisor independiente: {h.defecto}",
         "detalle": f"{h.explicacion} Prueba: «{h.prueba}» ({h.fuente}).", "resolucion": "Pendiente: decides tú."}
        for h in hallazgos])
    material = _actualizar(
        carpeta_curso, sesion, estado="con pendientes" if hallazgos else previo, previo="",
        aprobada="" if hallazgos else material.get("aprobada", ""),
        problemas=material.get("problemas", []) + [h.describir() for h in hallazgos],
        revisor={"hallazgos": len(hallazgos), "descartados": len(resultado.descartados), "lista": len(resultado.lista_no),
                 "costo": tokens.total(curso, sesion=f"S{sesion}", material=CLAVE, desde_linea=inicio)})
    _escribir_entrega(carpeta_curso, sesion, material)
    return _estado(carpeta_curso, sesion)


def aprobar(carpeta_curso: Path, sesion: int) -> dict:
    material = _estado(carpeta_curso, sesion)
    if material.get("estado") not in ("verificada", "con pendientes"):
        raise NoSePuedeAprobar("Solo se aprueba un laboratorio generado y sin fallas del verificador.")
    if material.get("desactualizado"):
        raise NoSePuedeAprobar("Las fichas cambiaron después de generar el laboratorio. Genéralo de nuevo.")
    return _actualizar(carpeta_curso, sesion, estado="aprobada", aprobada=datetime.now().isoformat(timespec="seconds"))
