"""Archivos de práctica del laboratorio: Excel para datos y Word para textos (SKILL.md, «Material 3»).

El redactor escribe el contenido de cada archivo como datos. Este programa crea el archivo real, con un diseño
sobrio y sin portada, y el .zip con todos. Las figuras de la guía se sacan después de estos archivos reales.
"""

import re
import zipfile
from pathlib import Path

import openpyxl
from docx import Document
from docx.shared import Pt, RGBColor
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.materiales import docx as generador_docx
from app.materiales.contenido import ArchivoPractica, Laboratorio
from app.materiales.estilo import Identidad

EXTENSIONES = ("xlsx", "docx")
ANCHO_MAXIMO_COLUMNA = 45
# Lo que el alumno copia funciona tal cual: sin espacios por llenar (SKILL.md, «Ejercicios que se ejecutan»).
POR_LLENAR = re.compile(r"\[[^\]\n]{0,40}\]|_{3,}|<[^<>\n]{1,40}>|\bX{3,}\b|\{\{?[^{}\n]{0,40}\}?\}")
# En una fórmula, «<» y «>» son operadores: solo se buscan corchetes vacíos, guiones bajos y «XXX».
POR_LLENAR_EN_FORMULA = re.compile(r"\[\s*\]|_{3,}|\bX{3,}\b")
FIGURAS_POR_EJERCICIO = 1     # PLAN.md §0, decisión 33: una como máximo, y solo si hace falta


def textos_del_ejercicio(e) -> list[str]:
    """Todo lo que el alumno lee en un ejercicio, también en «Mejora el resultado»."""
    recuadros = [*e.copiar, *e.mejora.copiar]
    return [e.situacion, *[p.texto for p in e.pasos], *[r.explicacion for r in recuadros],
            *[l for r in recuadros for l in r.lineas], e.mejora.texto, *e.mejora.pasos]


# Nombres de las funciones: la guía los escribe en español; dentro del archivo, Excel los guarda en inglés.
FUNCIONES = {
    "SI": "IF", "Y": "AND", "O": "OR", "NO": "NOT", "SUMA": "SUM", "PROMEDIO": "AVERAGE", "CONTAR": "COUNT",
    "CONTARA": "COUNTA", "CONTAR.SI": "COUNTIF", "CONTAR.SI.CONJUNTO": "COUNTIFS", "SUMAR.SI": "SUMIF",
    "SUMAR.SI.CONJUNTO": "SUMIFS", "PROMEDIO.SI": "AVERAGEIF", "BUSCARV": "VLOOKUP", "BUSCARH": "HLOOKUP",
    "BUSCARX": "XLOOKUP", "INDICE": "INDEX", "COINCIDIR": "MATCH", "SI.ERROR": "IFERROR", "REDONDEAR": "ROUND",
    "MAX": "MAX", "MIN": "MIN", "HOY": "TODAY", "FECHA": "DATE", "DIAS": "DAYS", "TEXTO": "TEXT",
    "CONCATENAR": "CONCATENATE", "IZQUIERDA": "LEFT", "DERECHA": "RIGHT", "EXTRAE": "MID", "LARGO": "LEN",
    "MAYUSC": "UPPER", "ESPACIOS": "TRIM", "SIFECHA": "DATEDIF", "ABS": "ABS", "ENTERO": "INT",
}
_FUNCION = re.compile(r"(?<![A-Za-z0-9_.])([A-ZÁÉÍÓÚ][A-ZÁÉÍÓÚ0-9]*(?:\.[A-ZÁÉÍÓÚ0-9]+)*)\s*\(")


def funciones_usadas(formulas: list[str]) -> list[tuple[str, str]]:
    """Las funciones de las fórmulas de la guía, en español y en inglés, en orden de aparición."""
    vistas = []
    for formula in formulas:
        for m in _FUNCION.finditer(formula.upper()):
            nombre = m.group(1).replace("Í", "I")
            if nombre in FUNCIONES and nombre not in vistas:
                vistas.append(nombre)
    return [(n, FUNCIONES[n]) for n in vistas]


def formula_para_excel(formula: str) -> str:
    """«=SUMA(B2:B9)» → «=SUM(B2:B9)»; los separadores «;» pasan a «,», como los guarda Excel."""
    def cambiar(m):
        nombre = m.group(1).upper().replace("Í", "I")
        return FUNCIONES.get(nombre, m.group(1)) + "("
    partes = re.split(r'("[^"]*")', formula)        # no se toca el texto entre comillas
    return "".join(p if p.startswith('"') else _FUNCION.sub(cambiar, p).replace(";", ",") for p in partes)


def patron_de_nombre(sesion: int, ejercicio: int | None = None) -> re.Pattern:
    numero = str(ejercicio) if ejercicio is not None else r"\d+"
    return re.compile(rf"^S{sesion}_E{numero}_[a-z0-9]+(?:-[a-z0-9]+)*\.(?:{'|'.join(EXTENSIONES)})$")


def numero_de_ejercicio(nombre: str) -> int | None:
    m = re.match(r"^S\d+_E(\d+)_", nombre)
    return int(m.group(1)) if m else None


# ---------- Crear los archivos ----------

def _valor(texto):
    """Un número escrito como texto se guarda como número; un código con ceros a la izquierda queda como texto."""
    if not isinstance(texto, str):
        return texto
    limpio = texto.strip()
    if limpio.startswith("="):
        return formula_para_excel(limpio)
    if re.fullmatch(r"-?\d+", limpio) and not (len(limpio) > 1 and limpio.lstrip("-").startswith("0")):
        return int(limpio)
    if re.fullmatch(r"-?\d+\.\d+", limpio):
        return float(limpio)
    return texto


def crear_excel(archivo: ArchivoPractica, identidad: Identidad, destino: Path) -> Path:
    libro = openpyxl.Workbook()
    libro.remove(libro.active)
    fuente = identidad.tipografia
    borde = Side(style="thin", color=identidad.principal)
    for hoja_ in archivo.hojas:
        hoja = libro.create_sheet(hoja_.nombre)
        hoja.append(hoja_.encabezados)
        for fila in hoja_.filas:
            hoja.append([_valor(v) for v in fila])
        for celda in hoja[1]:
            celda.font = Font(name=fuente, bold=True, color=identidad.texto)
            celda.fill = PatternFill("solid", fgColor=identidad.fondo)
            celda.border = Border(bottom=borde)
            celda.alignment = Alignment(vertical="center", wrap_text=True)
        for fila in hoja.iter_rows(min_row=2):
            for celda in fila:
                celda.font = Font(name=fuente, color=identidad.texto)
                celda.alignment = Alignment(vertical="top", wrap_text=isinstance(celda.value, str) and len(celda.value) > 30)
        for i, encabezado in enumerate(hoja_.encabezados, start=1):
            largo = max([len(str(encabezado))] + [len(str(f[i - 1])) for f in hoja_.filas if f[i - 1] is not None])
            hoja.column_dimensions[get_column_letter(i)].width = min(ANCHO_MAXIMO_COLUMNA, max(10, largo + 2))
        hoja.freeze_panes = "A2"
    libro.save(destino)
    return destino


def crear_word(archivo: ArchivoPractica, identidad: Identidad, destino: Path) -> Path:
    documento = Document()
    normal = documento.styles["Normal"]
    normal.font.name = identidad.tipografia
    normal.font.size = Pt(11)
    normal.font.color.rgb = RGBColor.from_string(identidad.texto)
    for parrafo in archivo.parrafos:
        if parrafo.estilo == "titulo":
            p = documento.add_paragraph(style="Heading 1")
            corrida = p.add_run(parrafo.texto)
            corrida.font.color.rgb = RGBColor.from_string(identidad.principal)
            corrida.font.name = identidad.tipografia
        elif parrafo.estilo == "lista":
            documento.add_paragraph(parrafo.texto, style="List Bullet")
        else:
            documento.add_paragraph(parrafo.texto)
    if archivo.tabla is not None:
        generador_docx.tabla_de_datos(documento, identidad, archivo.tabla)
    documento.save(destino)
    return destino


def crear(contenido: Laboratorio, identidad: Identidad, carpeta: Path) -> list[Path]:
    """Crea todos los archivos de práctica en una carpeta limpia."""
    carpeta.mkdir(parents=True, exist_ok=True)
    for vieja in carpeta.iterdir():
        if vieja.is_file():
            vieja.unlink(missing_ok=True)
    rutas = []
    for archivo in contenido.archivos:
        destino = carpeta / archivo.nombre
        rutas.append(crear_excel(archivo, identidad, destino) if archivo.extension == "xlsx"
                     else crear_word(archivo, identidad, destino))
    return rutas


def empaquetar(rutas: list[Path], destino: Path) -> Path:
    destino.unlink(missing_ok=True)
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zip_:
        for ruta in sorted(rutas):
            zip_.write(ruta, ruta.name)
    return destino


def nombres_del_zip(ruta: Path) -> list[str]:
    with zipfile.ZipFile(ruta) as zip_:
        return sorted(zip_.namelist())


# ---------- Controles antes de crear los archivos ----------

def _texto_de_archivo(archivo: ArchivoPractica) -> str:
    partes = [p.texto for p in archivo.parrafos]
    for hoja in archivo.hojas:
        partes += hoja.encabezados + [str(v) for fila in hoja.filas for v in fila if v is not None]
    if archivo.tabla:
        partes += archivo.tabla.encabezados + [c for f in archivo.tabla.filas for c in f]
    return "\n".join(partes)


def revisar(contenido: Laboratorio, sesion: int, ejercicios_de_la_ficha: int, fecha_de_referencia: str = "",
            respuestas_a_la_herramienta: dict[int, str] | None = None) -> list[str]:
    """Lo que un programa comprueba antes de crear los archivos (SKILL.md, «Material 3» y «Ejercicios que se
    ejecutan»). Cada problema es una FALLA de estructura: se arregla con una corrección completa."""
    problemas = []
    numeros = [e.numero for e in contenido.ejercicios]
    if numeros != list(range(1, len(numeros) + 1)):
        problemas.append(f"FALLA · estructura · ejercicios: van numerados 1, 2, 3…; vienen {numeros}.")
    if len(numeros) != ejercicios_de_la_ficha:
        problemas.append(f"FALLA · estructura · ejercicios: la ficha de la sesión trae {ejercicios_de_la_ficha}; "
                         f"hay {len(numeros)}.")
    for a, b in zip(contenido.ejercicios, contenido.ejercicios[1:]):
        if a.area.strip().lower() == b.area.strip().lower():
            problemas.append(f"FALLA · estructura · ejercicios {a.numero} y {b.numero}: los dos son del área «{a.area}»; "
                             "las áreas rotan.")
    por_nombre = {a.nombre: a for a in contenido.archivos}
    if len(por_nombre) != len(contenido.archivos):
        problemas.append("FALLA · estructura · archivos: hay dos archivos de práctica con el mismo nombre.")
    for archivo in contenido.archivos:
        if not patron_de_nombre(sesion).match(archivo.nombre):
            problemas.append(f"FALLA · nombre de archivo · «{archivo.nombre}»: el formato es "
                             f"S{sesion}_E[ejercicio]_[descripcion-corta].xlsx o .docx, en minúsculas y con guiones.")
        if archivo.extension == "xlsx" and not archivo.hojas:
            problemas.append(f"FALLA · estructura · «{archivo.nombre}»: un Excel necesita al menos una hoja con datos.")
        if archivo.extension == "docx" and not (archivo.parrafos or archivo.tabla):
            problemas.append(f"FALLA · estructura · «{archivo.nombre}»: un Word necesita párrafos o una tabla.")
        if not any(archivo.nombre in e.archivos for e in contenido.ejercicios):
            problemas.append(f"FALLA · estructura · «{archivo.nombre}»: ningún ejercicio lo usa.")
    respuestas = respuestas_a_la_herramienta or {}
    for e in contenido.ejercicios:
        for nombre in e.archivos:
            if nombre not in por_nombre:
                problemas.append(f"FALLA · archivo inexistente · ejercicio {e.numero}: «{nombre}» no está en «archivos».")
            elif numero_de_ejercicio(nombre) != e.numero:
                problemas.append(f"FALLA · estructura · ejercicio {e.numero}: usa «{nombre}», que es de otro ejercicio. "
                                 "Cada ejercicio funciona solo, con sus archivos.")
        texto = " ".join(textos_del_ejercicio(e))
        otro = re.search(r"\b(?:resultado|respuesta|salida|archivo)\s+del\s+ejercicio\s+(\d+)", texto, re.I)
        if otro and int(otro.group(1)) != e.numero:
            problemas.append(f"FALLA · estructura · ejercicio {e.numero}: usa el resultado del ejercicio {otro.group(1)}. "
                             "Cada ejercicio funciona solo.")
        for recuadro in [*e.copiar, *e.mejora.copiar]:
            if recuadro.tipo == "plantilla":
                continue                      # completar la plantilla es el tema del ejercicio
            patron = POR_LLENAR_EN_FORMULA if recuadro.tipo == "formula" else POR_LLENAR
            for linea in recuadro.lineas:
                m = patron.search(linea)
                if m:
                    problemas.append(f"FALLA · por llenar · ejercicio {e.numero}: «{m.group(0)}» en lo que el alumno "
                                     f"copia («{linea[:80]}»). Lo que copia funciona tal cual.")
        con_figura = [paso for paso in e.pasos if paso.figura is not None]
        if len(con_figura) > FIGURAS_POR_EJERCICIO:
            problemas.append(f"FALLA · figura · ejercicio {e.numero}: tiene {len(con_figura)} figuras; va una como "
                             "máximo, y solo si aclara dónde está algo en el archivo. Deja la más necesaria.")
        for paso in con_figura:
            problemas += _revisar_figura(e.numero, paso.figura, por_nombre, e.archivos)
        if fecha_de_referencia and re.search(r"\bplazos?\b|\bvenc\w*|\bfechas?\b", texto, re.I):
            de_sus_archivos = " ".join(_texto_de_archivo(por_nombre[n]) for n in e.archivos if n in por_nombre)
            if e.archivos and fecha_de_referencia.lower() not in de_sus_archivos.lower():
                problemas.append(f"FALLA · fecha de referencia · ejercicio {e.numero}: depende de fechas o plazos y su "
                                 f"archivo no trae la fecha de referencia «{fecha_de_referencia}». Escríbela en el archivo.")
        respuesta = (respuestas.get(e.numero) or "").strip()
        if respuesta and respuesta.lower() not in texto.lower():
            problemas.append(f"FALLA · estructura · ejercicio {e.numero}: la ficha dice que la herramienta pregunta algo "
                             f"y que el alumno responde «{respuesta}». Ordena que se detenga a preguntar y escribe esa "
                             "respuesta exacta.")
    return problemas


_CELDA = re.compile(r"^\$?([A-Z]{1,3})\$?(\d+)$")


def celda(texto: str) -> tuple[int, int] | None:
    """«C5» → (fila 5, columna 3)."""
    m = _CELDA.match(texto.strip().upper())
    if not m:
        return None
    columna = 0
    for letra in m.group(1):
        columna = columna * 26 + ord(letra) - 64
    return int(m.group(2)), columna


def rango(texto: str) -> tuple[int, int, int, int] | None:
    """«A1:E8» → (fila 1, columna 1, fila 8, columna 5). Una celda sola es un rango de una celda."""
    partes = texto.strip().upper().split(":")
    if len(partes) not in (1, 2):
        return None
    inicio, fin = celda(partes[0]), celda(partes[-1])
    if inicio is None or fin is None:
        return None
    return min(inicio[0], fin[0]), min(inicio[1], fin[1]), max(inicio[0], fin[0]), max(inicio[1], fin[1])


def _revisar_figura(numero: int, figura, por_nombre: dict, archivos_del_ejercicio: list[str]) -> list[str]:
    donde = f"ejercicio {numero}, figura de «{figura.archivo}»"
    if figura.archivo not in archivos_del_ejercicio or figura.archivo not in por_nombre:
        return [f"FALLA · figura · {donde}: la figura sale de un archivo de práctica de ese mismo ejercicio."]
    archivo = por_nombre[figura.archivo]
    problemas = []
    if archivo.extension == "xlsx":
        hojas = {h.nombre: h for h in archivo.hojas}
        hoja = hojas.get(figura.hoja) if figura.hoja else archivo.hojas[0] if archivo.hojas else None
        if hoja is None:
            return [f"FALLA · figura · {donde}: la hoja «{figura.hoja}» no existe en el archivo."]
        caja = rango(figura.rango) if figura.rango else (1, 1, len(hoja.filas) + 1, len(hoja.encabezados))
        if caja is None:
            return [f"FALLA · figura · {donde}: el rango «{figura.rango}» no es válido. Usa la forma «A1:E8»."]
        if caja[2] > len(hoja.filas) + 1 or caja[3] > len(hoja.encabezados):
            problemas.append(f"FALLA · figura · {donde}: el rango «{figura.rango}» se sale de los datos de la hoja.")
        if caja[3] - caja[1] + 1 > 8 or caja[2] - caja[0] + 1 > 16:
            problemas.append(f"FALLA · figura · {donde}: el rango «{figura.rango}» es muy grande para leerse en la "
                             "página: hasta 8 columnas y 16 filas.")
        for marca in figura.marcas:
            lugar = rango(marca.lugar)
            if lugar is None or not (caja[0] <= lugar[0] and lugar[2] <= caja[2] and caja[1] <= lugar[1] and lugar[3] <= caja[3]):
                problemas.append(f"FALLA · figura · {donde}: la marca «{marca.lugar}» no es una celda o un rango dentro "
                                 f"de «{figura.rango or 'la hoja'}».")
    else:
        texto = _texto_de_archivo(archivo).lower()
        for marca in figura.marcas:
            if marca.lugar.strip().lower() not in texto:
                problemas.append(f"FALLA · figura · {donde}: el texto marcado «{marca.lugar[:60]}» no está tal cual en "
                                 "el archivo.")
    return problemas
