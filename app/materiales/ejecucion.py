"""Ejecución de cada ejercicio del laboratorio como lo haría un alumno (SKILL.md, «Ejercicios que se ejecutan»;
PLAN.md §0, decisión 35, y «Lo que no se puede construir como está escrito», punto 3).

- Fórmulas: un programa sigue los pasos tal cual. Escribe los textos y copia cada fórmula en la celda que dice el
  paso, la copia hacia abajo si el paso lo pide, y Excel calcula el archivo. Un valor de error es una FALLA.
- Prompts: una conversación nueva con Claude, sin herramientas. El texto de cada archivo adjunto va dentro del
  mensaje. Después va la respuesta exacta del alumno, si la ficha la trae.
- Lo que salió se compara con la respuesta correcta de la ficha. Cada diferencia trae un trozo copiado de la ficha
  y otro de lo que salió; un programa los busca y descarta la diferencia sin prueba. Lo que queda es pendiente.
- A mano (PLAN.md §0, decisión 36): un ejercicio sin prompt ni fórmula lo hace Claude como alumno, en una
  conversación nueva y sin herramientas. Recibe el texto de sus archivos de práctica, la situación y los pasos de la
  guía, y entrega lo que escribiría en el archivo. Así también se completa una plantilla.
"""

import re
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path

import openpyxl
from docx import Document
from openpyxl.formula.translate import Translator

from app import agente
from app.materiales import practica
from app.materiales.contenido import Ejercicio, Laboratorio

ERRORES_DE_EXCEL = ("#NAME?", "#VALUE!", "#REF!", "#DIV/0!", "#N/A", "#NUM!", "#NULL!", "#SPILL!", "#CALC!")
ESCRIBE = re.compile(r"[Ee]scribe \*\*(.+?)\*\* en la celda ([A-Z]{1,3}\d+)")
LIMITE_DE_SALIDA = 12000      # letras de lo que salió que se envían a la comparación

ESQUEMA_COMPARACION = {
    "type": "object",
    "properties": {"diferencias": {"type": "array", "items": {
        "type": "object",
        "properties": {"esperado": {"type": "string"}, "salio": {"type": "string"}, "explicacion": {"type": "string"}},
        "required": ["esperado", "salio", "explicacion"], "additionalProperties": False,
    }}},
    "required": ["diferencias"],
    "additionalProperties": False,
}


@dataclass
class Turno:
    rol: str        # «alumno» o «herramienta»
    texto: str


@dataclass
class Diferencia:
    esperado: str   # trozo copiado de la respuesta de la ficha
    salio: str      # trozo copiado de lo que salió; vacío si falta
    explicacion: str


@dataclass
class Ejecucion:
    numero: int
    titulo: str
    respuesta_ficha: str = ""
    celdas: list[dict] = field(default_factory=list)          # archivo, hoja, celda, formula, valor
    conversacion: list[Turno] = field(default_factory=list)
    a_mano: bool = False                                      # la conversación es Claude haciendo el ejercicio a mano
    fallas: list[str] = field(default_factory=list)
    diferencias: list[Diferencia] = field(default_factory=list)
    descartadas: int = 0
    no_pude: list[str] = field(default_factory=list)

    @property
    def conversaciones(self) -> int:
        return 1 if self.conversacion else 0

    @property
    def coincide(self) -> bool:
        return (bool(self.respuesta_ficha) and bool(self.celdas or self.conversacion)
                and not (self.fallas or self.diferencias))

    def salida(self) -> str:
        """Lo que salió: los valores calculados y la última respuesta de la herramienta."""
        partes = [f"{c['archivo']} · hoja {c['hoja']} · celda {c['celda']}: {c['valor']}" for c in self.celdas]
        respuestas = [t.texto for t in self.conversacion if t.rol in ("herramienta", "resultado")]
        return "\n".join(partes + respuestas)

    def pendientes(self) -> list[str]:
        return [f"Ejecución · ejercicio {self.numero}: la ficha dice «{d.esperado}» y "
                + (f"salió «{d.salio}»." if d.salio else "eso no salió.") + f" {d.explicacion}".rstrip()
                for d in self.diferencias]

    def a_dict(self) -> dict:
        return asdict(self)


# ---------- Fórmulas, con Excel ----------

def _ultima_mencion(texto: str, nombres: list[str]) -> str | None:
    """El nombre que el paso menciona por último: el paso «Abre el archivo X y entra a la hoja Y» deja Y."""
    vistos = [(m.start(), n) for n in nombres for m in re.finditer(rf"(?<![\w-]){re.escape(n)}(?![\w-])", texto)]
    return max(vistos)[1] if vistos else None


def _formulas(e: Ejercicio, carpeta_practica: Path, carpeta: Path, recalcular) -> tuple[list[dict], list[str]]:
    recuadros = practica.formulas_por_numero(e)
    libros_ = [n for n in e.archivos if n.endswith(".xlsx") and (carpeta_practica / n).exists()]
    if not recuadros:
        return [], []
    if not libros_:
        return [], [f"FALLA · ejecución · ejercicio {e.numero}: trae fórmulas y ningún Excel donde copiarlas."]
    shutil.rmtree(carpeta, ignore_errors=True)
    carpeta.mkdir(parents=True, exist_ok=True)
    libros = {}
    for nombre in libros_:
        shutil.copy2(carpeta_practica / nombre, carpeta / nombre)
        libros[nombre] = openpyxl.load_workbook(carpeta / nombre)
    archivo = libros_[0]
    hoja = libros[archivo].worksheets[0].title
    escritas, fallas = [], []
    for texto in [p.texto for p in e.pasos]:
        limpio = texto.replace("**", "")
        mencionado = _ultima_mencion(limpio, libros_)
        if mencionado and mencionado != archivo:
            archivo, hoja = mencionado, libros[mencionado].worksheets[0].title
        if re.search(r"\bhoja\b", limpio, re.I):
            hoja = _ultima_mencion(limpio, libros[archivo].sheetnames) or hoja
        ws = libros[archivo][hoja]
        for m in ESCRIBE.finditer(texto):
            ws[m.group(2)] = practica.valor_de_celda(m.group(1))
        for m in practica.COPIA_FORMULA.finditer(limpio):
            numero, celda = int(m.group(1)), m.group(2)
            recuadro = recuadros.get(numero)
            if recuadro is None:
                continue                  # lo informa practica.revisar antes de crear los archivos
            formula = practica.formula_para_excel(" ".join(l.strip() for l in recuadro.lineas))
            ws[celda] = formula
            escritas.append({"archivo": archivo, "hoja": hoja, "celda": celda, "formula": formula})
        for m in practica.HACIA_ABAJO.finditer(limpio):
            columna, fila, hasta = m.group(1), int(m.group(2)), int(m.group(3))
            origen = ws[f"{columna}{fila}"].value
            if not (isinstance(origen, str) and origen.startswith("=")):
                fallas.append(f"FALLA · ejecución · ejercicio {e.numero}: el paso «{texto[:80]}» copia hacia abajo la "
                              f"celda {columna}{fila}, que no tiene una fórmula en ese momento.")
                continue
            for f in range(fila + 1, hasta + 1):
                destino = f"{columna}{f}"
                ws[destino] = Translator(origen, origin=f"{columna}{fila}").translate_formula(destino)
                escritas.append({"archivo": archivo, "hoja": hoja, "celda": destino, "formula": ws[destino].value})
    for nombre, libro in libros.items():
        libro.save(carpeta / nombre)
        if any(c["archivo"] == nombre for c in escritas):
            recalcular(carpeta / nombre)
    calculados = {n: openpyxl.load_workbook(carpeta / n, data_only=True) for n in libros}
    for c in escritas:
        valor = calculados[c["archivo"]][c["hoja"]][c["celda"]].value
        c["valor"] = "" if valor is None else valor
        if isinstance(valor, str) and valor.strip().upper() in ERRORES_DE_EXCEL:
            fallas.append(f"FALLA · ejecución · ejercicio {e.numero}: la fórmula de la celda {c['celda']} (hoja "
                          f"{c['hoja']}) da {valor} al calcularla con Excel. Revisa la fórmula y los datos del archivo.")
    return escritas, fallas


# ---------- Prompts, con Claude ----------

def texto_del_archivo(ruta: Path) -> str:
    """Lo que vería la herramienta del alumno al recibir el archivo adjunto."""
    if ruta.suffix == ".xlsx":
        libro = openpyxl.load_workbook(ruta, data_only=True)
        partes = []
        for hoja in libro.worksheets:
            partes.append(f"Hoja {hoja.title}:")
            partes += [" | ".join("" if v is None else str(v) for v in fila)
                       for fila in hoja.iter_rows(values_only=True) if any(v is not None for v in fila)]
        return "\n".join(partes)
    documento = Document(ruta)
    partes = [p.text for p in documento.paragraphs if p.text.strip()]
    partes += [" | ".join(c.text for c in fila.cells) for tabla in documento.tables for fila in tabla.rows]
    return "\n".join(partes)


def primer_mensaje(prompt: str, adjuntos: dict[str, str]) -> str:
    partes = [f"[Archivo adjunto: {nombre}]\n{texto}\n[Fin de {nombre}]" for nombre, texto in adjuntos.items()]
    return "\n\n".join(partes + [prompt])


def con_historial(turnos: list[Turno], nuevo: str) -> str:
    """El SDK recibe un solo mensaje: la conversación anterior va escrita antes del mensaje nuevo."""
    if not turnos:
        return nuevo
    previo = "\n\n".join(f"[{'Usuario' if t.rol == 'alumno' else 'Tú'}]\n{t.texto}" for t in turnos)
    return f"Esta es la conversación hasta ahora:\n\n{previo}\n\nNuevo mensaje del usuario:\n{nuevo}"


def _adjunta(e: Ejercicio) -> bool:
    return any(re.search(r"\badjunta", p.texto, re.I) for p in e.pasos)


async def _conversar(e: Ejercicio, carpeta_practica: Path, respuesta_alumno: str, llamada: dict) -> list[Turno]:
    prompts = ["\n".join(r.lineas) for r in e.copiar if r.tipo == "prompt"]
    if not prompts:
        return []
    adjuntos = {n: texto_del_archivo(carpeta_practica / n) for n in e.archivos
                if _adjunta(e) and (carpeta_practica / n).exists()}
    mensajes = [primer_mensaje(prompts[0], adjuntos), *prompts[1:]]
    if respuesta_alumno:
        mensajes.insert(1, respuesta_alumno)
    turnos: list[Turno] = []
    for mensaje in mensajes:
        respuesta = await agente.conversar(con_historial(turnos, mensaje), tarea="ejecucion",
                                           etapa=f"ejecución ejercicio {e.numero}", **llamada)
        turnos += [Turno("alumno", mensaje), Turno("herramienta", respuesta)]
    return turnos


# ---------- A mano, con Claude como alumno ----------

def pedido_a_mano(e: Ejercicio, adjuntos: dict[str, str]) -> str:
    """Lo que tiene el alumno: sus archivos, la situación y los pasos de la guía. Nada de la ficha ni de la respuesta."""
    pasos = [f"{i}. {p.texto.replace('**', '')}" for i, p in enumerate(e.pasos, start=1)]
    plantillas = [f"{r.titulo}:\n" + "\n".join(r.lineas) for r in e.copiar if r.tipo == "plantilla"]
    archivos = [f"[Archivo de práctica: {nombre}]\n{texto}\n[Fin de {nombre}]" for nombre, texto in adjuntos.items()]
    return "\n".join([
        "Eres un alumno de un curso. Haz este ejercicio de laboratorio a mano, tal como dice la guía. No tienes",
        "otra ayuda: solo los archivos de práctica, la situación y los pasos. Sigue cada paso en su orden.",
        "Al terminar, entrega lo que escribiste en el archivo: en un Excel, una tabla con la fila y las columnas que",
        "llenaste; en un Word, el texto que agregaste o cambiaste. No expliques cómo lo hiciste.",
        "",
        *archivos,
        "",
        f"EJERCICIO {e.numero} · {e.titulo}",
        e.situacion,
        "",
        "PASOS:",
        *pasos,
        *(["", "PLANTILLA QUE COMPLETAS:", *plantillas] if plantillas else []),
    ])


async def _a_mano(e: Ejercicio, carpeta_practica: Path, llamada: dict) -> list[Turno]:
    adjuntos = {n: texto_del_archivo(carpeta_practica / n) for n in e.archivos if (carpeta_practica / n).exists()}
    pedido = pedido_a_mano(e, adjuntos)
    respuesta = await agente.conversar(pedido, tarea="ejecucion", etapa=f"ejecución a mano ejercicio {e.numero}",
                                       **llamada)
    return [Turno("guía", pedido), Turno("resultado", respuesta)]


# ---------- Comparación con la respuesta de la ficha ----------

def _normal(texto: str) -> str:
    return " ".join(re.sub(r"[*«»“”\"`]", "", str(texto)).lower().split())


def pedido_de_comparacion(ejecucion: Ejecucion, situacion: str) -> str:
    salida = ejecucion.salida()
    if len(salida) > LIMITE_DE_SALIDA:
        salida = salida[:LIMITE_DE_SALIDA] + "\n[…recortado]"
    return "\n".join([
        "Revisas un ejercicio de laboratorio que ya se ejecutó. Compara lo que salió con la respuesta correcta que",
        "escribió el profesor en la ficha.",
        "- Solo es una diferencia: un dato distinto (una clasificación, un número, un nombre, una decisión), algo de",
        "  la respuesta que no salió, o algo que salió y la contradice.",
        "- Decir lo mismo con otras palabras, en otro orden o en otro formato no es una diferencia. Tampoco lo es que",
        "  salgan explicaciones o datos de más que no contradicen la respuesta.",
        "- Si la respuesta de la ficha describe el resultado en general, compara solo lo que dice.",
        "- En «esperado» copia tal cual un trozo corto de la respuesta de la ficha. En «salio» copia tal cual un trozo",
        "  corto de lo que salió, o déjalo vacío si eso no salió. Un programa busca los dos trozos.",
        "- Sin diferencias, devuelve la lista vacía.",
        "",
        f"EJERCICIO {ejecucion.numero} · {ejecucion.titulo}",
        situacion,
        "",
        "RESPUESTA CORRECTA DE LA FICHA:",
        ejecucion.respuesta_ficha,
        "",
        "LO QUE SALIÓ AL EJECUTARLO:",
        salida,
    ])


def con_prueba(diferencias: list[dict], respuesta_ficha: str, salida: str) -> tuple[list[Diferencia], int]:
    """Solo queda una diferencia cuyo trozo «esperado» está en la ficha y cuyo trozo «salio» está en lo que salió."""
    ficha, salio = _normal(respuesta_ficha), _normal(salida)
    buenas = [Diferencia(d["esperado"].strip(), d["salio"].strip(), d["explicacion"].strip()) for d in diferencias
              if _normal(d["esperado"]) and _normal(d["esperado"]) in ficha
              and (not _normal(d["salio"]) or _normal(d["salio"]) in salio)]
    return buenas, len(diferencias) - len(buenas)


# ---------- Todo el laboratorio ----------

async def ejecutar(contenido: Laboratorio, *, carpeta_practica: Path, carpeta: Path, respuestas_ficha: dict[int, str],
                   respuestas_alumno: dict[int, str], recalcular, llamada: dict, solo: set[int] | None = None,
                   avance=lambda texto: None) -> list[Ejecucion]:
    """`respuestas_ficha` y `respuestas_alumno` van por número de ejercicio del laboratorio. `llamada` lleva curso,
    sesion, material y consulta para el SDK. `solo` ejecuta de nuevo algunos ejercicios."""
    resultados = []
    for e in contenido.ejercicios:
        if solo is not None and e.numero not in solo:
            continue
        avance(f"Ejecutando el ejercicio {e.numero} como un alumno.")
        ejecucion = Ejecucion(e.numero, e.titulo, respuesta_ficha=respuestas_ficha.get(e.numero, "").strip())
        ejecucion.celdas, ejecucion.fallas = _formulas(e, carpeta_practica, carpeta / f"E{e.numero}", recalcular)
        ejecucion.conversacion = await _conversar(e, carpeta_practica, respuestas_alumno.get(e.numero, ""), llamada)
        if not (ejecucion.celdas or ejecucion.conversacion or ejecucion.fallas):
            ejecucion.conversacion, ejecucion.a_mano = await _a_mano(e, carpeta_practica, llamada), True
        if not ejecucion.respuesta_ficha:
            ejecucion.no_pude.append(f"Ejercicio {e.numero}: la ficha no trae la respuesta correcta para compararla.")
        elif not ejecucion.fallas:
            respuesta = await agente.consultar(pedido_de_comparacion(ejecucion, e.situacion),
                                               tarea="comparacion_ejecucion", esquema=ESQUEMA_COMPARACION,
                                               etapa=f"comparación ejercicio {e.numero}", **llamada)
            ejecucion.diferencias, ejecucion.descartadas = con_prueba(
                respuesta["diferencias"], ejecucion.respuesta_ficha, ejecucion.salida())
        resultados.append(ejecucion)
    return resultados


def a_markdown(ejecuciones: list[Ejecucion], titulo: str, modelo: str) -> str:
    """El registro de la ejecución para el profesor: qué se copió, qué respondió la herramienta y qué se calculó."""
    lineas = [f"# {titulo}", "",
              f"Cada prompt se ejecutó en una conversación nueva con Claude ({modelo}), sin herramientas, con el texto "
              "de cada archivo adjunto dentro del mensaje. Cada fórmula se copió donde dice el paso y la calculó Excel. "
              "Cada ejercicio sin prompt ni fórmula lo hizo Claude a mano, como un alumno, con el texto de sus "
              "archivos, la situación y los pasos de la guía.",
              ""]
    for x in ejecuciones:
        lineas += [f"## Ejercicio {x.numero} · {x.titulo}", ""]
        if x.celdas:
            lineas += ["Fórmulas calculadas con Excel:", ""]
            lineas += [f"- {c['archivo']}, hoja {c['hoja']}, celda {c['celda']}: `{c['formula']}` → {c['valor']}"
                       for c in x.celdas]
            lineas.append("")
        for t in x.conversacion:
            quien = {"alumno": "Alumno", "herramienta": "Herramienta", "guía": "Lo que recibió Claude como alumno",
                     "resultado": "Lo que hizo Claude a mano"}[t.rol]
            lineas += [f"**{quien}:**", "", *[f"> {l}" if l else ">" for l in t.texto.splitlines()], ""]
        if x.fallas or x.diferencias:
            lineas += ["Resultado: no coincide.", "", *[f"- {f}" for f in x.fallas], *[f"- {p}" for p in x.pendientes()], ""]
        elif x.coincide:
            lineas += ["Resultado: coincide con la respuesta correcta de la ficha.", ""]
        lineas += [f"- {n}" for n in x.no_pude]
        if x.no_pude:
            lineas.append("")
    return "\n".join(lineas)
