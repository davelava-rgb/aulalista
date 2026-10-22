"""Generador de los Word de AulaLista, con el diseño común de la skill.

Lectura (SKILL.md, «Material 1»): A4, márgenes de 2,5 cm, cuerpo en 11 pt, interlineado 1,15,
6 pt después de cada párrafo, portada limpia, encabezado con el nombre del curso, pie con
número de página y estilos reales de Título 1, 2 y 3. El laboratorio, la guía del profesor y
la evaluación usan este mismo diseño.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ROW_HEIGHT_RULE, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

from app.materiales import estilo
from app.materiales.contenido import Lectura, Tabla
from app.materiales.estilo import Identidad


@dataclass
class Portada:
    curso: str
    sesion: str        # «Sesión 1 · Agilidad y fundamentos de Scrum»
    material: str      # «Lectura», «Laboratorio», «Guía del profesor»…
    docente: str = ""
    contacto: str = ""   # «enlace; correo»: una línea por dato en la portada


def _rgb(color: str) -> RGBColor:
    return RGBColor.from_string(color)


def _fuente(estilo_word, identidad: Identidad, tamano: float, color: str, negrita: bool = False) -> None:
    fuente = estilo_word.font
    fuente.name = identidad.tipografia
    fuente.size = Pt(tamano)
    fuente.bold = negrita
    fuente.color.rgb = _rgb(color)
    rpr = estilo_word.element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    for atributo in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"):
        rfonts.set(qn(atributo), identidad.tipografia)


def documento_base(identidad: Identidad, portada: Portada) -> Document:
    documento = Document()
    seccion = documento.sections[0]
    seccion.page_width, seccion.page_height = Cm(21), Cm(29.7)
    for margen in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(seccion, margen, Cm(2.5))

    estilos = documento.styles
    _fuente(estilos["Normal"], identidad, 11, identidad.texto)
    formato = estilos["Normal"].paragraph_format
    formato.line_spacing = 1.15
    formato.space_after = Pt(6)
    formato.space_before = Pt(0)
    formato.alignment = WD_ALIGN_PARAGRAPH.LEFT
    titular = estilo.para_texto(identidad.principal)
    diseno = identidad.estilo
    for (nombre, antes), tamano in zip((("Heading 1", 18), ("Heading 2", 12), ("Heading 3", 10)), diseno.titulos_pt):
        color = estilo.para_texto(identidad.acento) if nombre == "Heading 2" and diseno.acento_en_titulo2 else titular
        _fuente(estilos[nombre], identidad, tamano, color, negrita=True)
        estilos[nombre].paragraph_format.space_before = Pt(antes)
        estilos[nombre].paragraph_format.space_after = Pt(6)
        estilos[nombre].paragraph_format.keep_with_next = True
    if diseno.linea_titulo1:
        _linea_inferior(estilos["Heading 1"], identidad.principal)
    _fuente(estilos["Title"], identidad, diseno.titulo_pt, titular, negrita=True)
    estilos["Title"].paragraph_format.space_after = Pt(12)
    _quitar_borde_del_titulo(estilos["Title"])

    seccion.different_first_page_header_footer = True
    encabezado = seccion.header.paragraphs[0]
    encabezado.text = portada.curso
    encabezado.runs[0].font.size = Pt(9)
    encabezado.runs[0].font.color.rgb = _rgb(identidad.texto)
    _numero_de_pagina(seccion.footer.paragraphs[0], identidad)

    _portada(documento, identidad, portada)
    return documento


def _quitar_borde_del_titulo(estilo_word) -> None:
    ppr = estilo_word.element.get_or_add_pPr()
    for borde in ppr.findall(qn("w:pBdr")):
        ppr.remove(borde)


def _linea_inferior(estilo_word, color: str) -> None:
    """Línea fina del color principal bajo el párrafo (estilos académico y corporativo)."""
    ppr = estilo_word.element.get_or_add_pPr()
    bordes = OxmlElement("w:pBdr")
    abajo = OxmlElement("w:bottom")
    for atributo, valor in (("w:val", "single"), ("w:sz", "6"), ("w:space", "2"), ("w:color", color)):
        abajo.set(qn(atributo), valor)
    bordes.append(abajo)
    ppr.append(bordes)


def _franja(documento: Document, identidad: Identidad) -> None:
    """Franja del color principal arriba de la portada (estilos moderno y corporativo)."""
    tabla = documento.add_table(rows=1, cols=1)
    _bordes(tabla)
    fila = tabla.rows[0]
    fila.height = Cm(1.2)
    fila.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    _sombrear(fila.cells[0], identidad.principal)


def _numero_de_pagina(parrafo, identidad: Identidad) -> None:
    parrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    campo = OxmlElement("w:fldSimple")
    campo.set(qn("w:instr"), "PAGE")
    corrida = OxmlElement("w:r")
    texto = OxmlElement("w:t")
    texto.text = "1"
    corrida.append(texto)
    campo.append(corrida)
    parrafo._p.append(campo)


def _portada(documento: Document, identidad: Identidad, portada: Portada) -> None:
    """Portada limpia: logo si existe, curso, sesión, material, docente y contacto. Sin imágenes decorativas.

    El estilo decide si va centrada y si lleva una franja de color arriba (decisión 27). Con un modelo, lo decide
    su carátula, que también da el lugar del logo (decisión 28).
    """
    diseno = identidad.estilo
    inicio = len(documento.paragraphs)
    if diseno.franja:
        _franja(documento, identidad)
    for _ in range(3 if diseno.franja else 4):
        documento.add_paragraph()
    parrafo_logo = None
    if identidad.logo is not None:
        documento.add_picture(str(identidad.logo), width=Cm(4))
        parrafo_logo = documento.paragraphs[-1]
    documento.add_paragraph(portada.curso, style="Title")
    sesion = documento.add_paragraph(portada.sesion)
    sesion.runs[0].font.size = Pt(16)
    material = documento.add_paragraph(portada.material)
    material.runs[0].font.size = Pt(20)
    material.runs[0].font.bold = True
    material.runs[0].font.color.rgb = _rgb(estilo.para_texto(identidad.acento))
    if portada.docente or portada.contacto:
        documento.add_paragraph()
    if portada.docente:
        documento.add_paragraph(f"Docente: {portada.docente}")
    for dato in lineas_de_contacto(portada.contacto):
        documento.add_paragraph(dato).paragraph_format.space_after = Pt(0)
    if diseno.portada_centrada:
        for parrafo in documento.paragraphs[inicio:]:
            parrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if parrafo_logo is not None and diseno.logo in LUGAR_DEL_LOGO:
        parrafo_logo.alignment = LUGAR_DEL_LOGO[diseno.logo]
    documento.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


LUGAR_DEL_LOGO = {"izquierda": WD_ALIGN_PARAGRAPH.LEFT, "centro": WD_ALIGN_PARAGRAPH.CENTER,
                  "derecha": WD_ALIGN_PARAGRAPH.RIGHT}


def lineas_de_contacto(contacto: str) -> list[str]:
    return [p.strip() for p in re.split(r";|\n", contacto or "") if p.strip()]


# ---------- Bloques comunes ----------

def _sombrear(celda, color: str) -> None:
    propiedades = celda._tc.get_or_add_tcPr()
    sombra = OxmlElement("w:shd")
    sombra.set(qn("w:val"), "clear")
    sombra.set(qn("w:color"), "auto")
    sombra.set(qn("w:fill"), color)
    propiedades.append(sombra)


def _bordes(tabla, **lados) -> None:
    """lados: nombre → (color, grosor en octavos de punto) o None para quitar el borde."""
    propiedades = tabla._tbl.tblPr
    bordes = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        elemento = OxmlElement(f"w:{lado}")
        valor = lados.get(lado)
        if valor is None:
            elemento.set(qn("w:val"), "nil")
        else:
            color, grosor = valor
            elemento.set(qn("w:val"), "single")
            elemento.set(qn("w:sz"), str(grosor))
            elemento.set(qn("w:color"), color)
        bordes.append(elemento)
    propiedades.append(bordes)


def _margen_interior(tabla, izquierda: int = 200, derecha: int = 160) -> None:
    """Espacio entre el borde del recuadro y el texto, en vigésimos de punto."""
    margenes = OxmlElement("w:tblCellMar")
    for lado, valor in (("top", 60), ("left", izquierda), ("bottom", 60), ("right", derecha)):
        elemento = OxmlElement(f"w:{lado}")
        elemento.set(qn("w:w"), str(valor))
        elemento.set(qn("w:type"), "dxa")
        margenes.append(elemento)
    tabla._tbl.tblPr.append(margenes)


def _no_partir_fila(fila) -> None:
    propiedades = fila._tr.get_or_add_trPr()
    elemento = OxmlElement("w:cantSplit")
    propiedades.append(elemento)


def recuadro(documento: Document, identidad: Identidad, titulo: str, parrafos: list[str],
             color_borde: str | None = None, lineas_para_copiar: list[str] | None = None) -> None:
    """Recuadro sombreado con borde izquierdo de color. Mismo estilo en todos los materiales."""
    tabla = documento.add_table(rows=1, cols=1)
    tabla.alignment = WD_TABLE_ALIGNMENT.LEFT
    _bordes(tabla, left=(color_borde or identidad.principal, identidad.estilo.borde_recuadro))
    _margen_interior(tabla)
    celda = tabla.cell(0, 0)
    _sombrear(celda, identidad.fondo)
    _no_partir_fila(tabla.rows[0])
    primero = celda.paragraphs[0]
    primero.add_run(titulo).bold = True
    primero.runs[0].font.color.rgb = _rgb(estilo.para_texto(color_borde or identidad.principal, identidad.fondo))
    for texto in parrafos:
        celda.add_paragraph(texto)
    for linea in lineas_para_copiar or []:
        celda.add_paragraph(linea)
    documento.add_paragraph()


def tabla_de_datos(documento: Document, identidad: Identidad, datos: Tabla) -> None:
    """Encabezado en el color principal, filas alternas en gris muy claro y sin bordes verticales."""
    if datos.titulo:
        documento.add_paragraph(datos.titulo).runs[0].bold = True
    tabla = documento.add_table(rows=1 + len(datos.filas), cols=len(datos.encabezados))
    _bordes(tabla)
    for i, texto in enumerate(datos.encabezados):
        celda = tabla.cell(0, i)
        _sombrear(celda, identidad.principal)
        corrida = celda.paragraphs[0].add_run(texto)
        corrida.bold = True
        corrida.font.color.rgb = _rgb(estilo.BLANCO)
    for numero, fila in enumerate(datos.filas, start=1):
        _no_partir_fila(tabla.rows[numero])
        for i, texto in enumerate(fila):
            celda = tabla.cell(numero, i)
            if numero % 2 == 0:
                _sombrear(celda, estilo.GRIS_FILA_ALTERNA)
            celda.paragraphs[0].add_run(texto)
    documento.add_paragraph()


# ---------- Lectura ----------

def generar_lectura(contenido: Lectura, identidad: Identidad, portada: Portada, destino: Path) -> Path:
    documento = documento_base(identidad, portada)
    documento.add_heading("Idea central", level=1)
    for texto in contenido.idea_central:
        documento.add_paragraph(texto)
    for bloque in contenido.bloques:
        documento.add_heading(bloque.subtitulo, level=1)
        for texto in bloque.parrafos:
            documento.add_paragraph(texto)
        if bloque.tabla is not None:
            tabla_de_datos(documento, identidad, bloque.tabla)
        recuadro(documento, identidad, bloque.ejemplo.titulo, bloque.ejemplo.parrafos)
    recuadro(documento, identidad, "Aplícalo así", contenido.aplicalo.parrafos,
             lineas_para_copiar=contenido.aplicalo.plantilla)
    recuadro(documento, identidad, "Cuidado con", contenido.cuidado, color_borde=identidad.advertencia)
    destino.parent.mkdir(parents=True, exist_ok=True)
    documento.save(destino)
    return destino


# ---------- Laboratorio (SKILL.md, «Material 3»; PLAN.md §0, decisión 33) ----------

MEJORA = "Mejora el resultado (opcional)"
CADA_UNO_SOLO = "Cada ejercicio funciona solo. Puedes hacerlos en cualquier orden."
ANTES_DE_COPIAR = [
    "Las fórmulas de esta guía usan los nombres de las funciones en español y separan los datos con comas.",
    "Si tu hoja de cálculo muestra un error al pegar una fórmula, cambia cada coma por un punto y coma.",
    "Si tu hoja de cálculo está en inglés, cambia los nombres de las funciones con esta tabla.",
    "Copiar una celda hacia abajo significa copiar la celda, seleccionar las celdas de abajo y pegar.",
]
_MENCION_DE_FIGURA = re.compile(r"\s*\(?\s*mira la figura\s*\d*\s*\.?\)?\s*", re.I)
_NEGRITA = re.compile(r"\*\*(.+?)\*\*")
MONOESPACIADA = "Consolas"


def _con_negritas(parrafo, texto: str) -> None:
    """«**Riesgos**» va en negrita: así los pasos destacan el nombre de una hoja o de una celda."""
    posicion = 0
    for m in _NEGRITA.finditer(texto):
        if m.start() > posicion:
            parrafo.add_run(texto[posicion:m.start()])
        parrafo.add_run(m.group(1)).bold = True
        posicion = m.end()
    if posicion < len(texto):
        parrafo.add_run(texto[posicion:])


def sin_marcas(texto: str) -> str:
    return _NEGRITA.sub(r"\1", texto)


def _pie(documento: Document, texto: str, identidad: Identidad) -> None:
    """Pie de página «Sesión N · Laboratorio · Página N», a la derecha (decisión 33)."""
    parrafo = documento.sections[0].footer.paragraphs[0]
    for hijo in list(parrafo._p):
        if hijo.tag != qn("w:pPr"):
            parrafo._p.remove(hijo)
    parrafo.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    corrida = parrafo.add_run(f"{texto} · Página ")
    campo = OxmlElement("w:fldSimple")
    campo.set(qn("w:instr"), "PAGE")
    numero = OxmlElement("w:r")
    texto_ = OxmlElement("w:t")
    texto_.text = "1"
    numero.append(texto_)
    campo.append(numero)
    parrafo._p.append(campo)
    corrida.font.size = Pt(9)
    corrida.font.color.rgb = _rgb(identidad.texto)


def _subtitulo(documento: Document, texto: str, identidad: Identidad) -> None:
    """Subtítulo pequeño dentro de un ejercicio: «Situación», «Archivos de práctica», «Pasos»."""
    parrafo = documento.add_paragraph()
    parrafo.paragraph_format.space_before = Pt(8)
    parrafo.paragraph_format.space_after = Pt(3)
    parrafo.paragraph_format.keep_with_next = True
    corrida = parrafo.add_run(texto)
    corrida.bold = True
    corrida.font.color.rgb = _rgb(estilo.para_texto(identidad.principal))


def _lista_numerada(documento: Document, pasos: list[str], identidad: Identidad, imagenes: dict | None = None,
                    figuras_: list | None = None, contador: list | None = None) -> None:
    """Pasos numerados: el número en negrita y la figura justo después de su paso."""
    for i, paso in enumerate(pasos, start=1):
        texto = _MENCION_DE_FIGURA.sub(" ", paso).strip()
        imagen = (imagenes or {}).get(i)
        if imagen is not None:
            contador[0] += 1
            texto = f"{texto} Mira la figura {contador[0]}."
        parrafo = documento.add_paragraph()
        parrafo.paragraph_format.left_indent = Cm(0.7)
        parrafo.paragraph_format.first_line_indent = Cm(-0.7)
        parrafo.paragraph_format.space_after = Pt(3)
        numero = parrafo.add_run(f"{i}.\t")
        numero.bold = True
        numero.font.color.rgb = _rgb(estilo.para_texto(identidad.principal))
        parrafo.paragraph_format.tab_stops.add_tab_stop(Cm(0.7))
        _con_negritas(parrafo, texto)
        if imagen is not None:
            parrafo.paragraph_format.keep_with_next = True
            _figura(documento, imagen, contador[0], figuras_[i - 1].descripcion)


def _figura(documento: Document, imagen, numero: int, descripcion: str) -> None:
    """La imagen justo después de su paso, con «Figura N» y una línea debajo. Imagen y pie no se separan."""
    parrafo = documento.add_paragraph()
    parrafo.alignment = WD_ALIGN_PARAGRAPH.CENTER
    parrafo.paragraph_format.keep_with_next = True
    parrafo.add_run().add_picture(str(imagen.ruta), width=Cm(imagen.ancho_cm))
    pie = documento.add_paragraph()
    pie.alignment = WD_ALIGN_PARAGRAPH.CENTER
    etiqueta = pie.add_run(f"Figura {numero}. ")
    etiqueta.bold = True
    pie.add_run(descripcion)
    for corrida in pie.runs:
        corrida.font.size = Pt(10)


def recuadro_para_copiar(documento: Document, identidad: Identidad, recuadro_) -> None:
    """Prompt, fórmula o plantilla: el título, una línea de explicación y lo que se copia en letra monoespaciada,
    sobre fondo blanco dentro del recuadro (decisión 33)."""
    tabla = documento.add_table(rows=1, cols=1)
    tabla.alignment = WD_TABLE_ALIGNMENT.LEFT
    _bordes(tabla, left=(identidad.principal, identidad.estilo.borde_recuadro))
    _margen_interior(tabla)
    celda = tabla.cell(0, 0)
    _sombrear(celda, identidad.fondo)
    _no_partir_fila(tabla.rows[0])
    titulo = celda.paragraphs[0]
    corrida = titulo.add_run(recuadro_.titulo)
    corrida.bold = True
    corrida.font.color.rgb = _rgb(estilo.para_texto(identidad.principal, identidad.fondo))
    if recuadro_.explicacion:
        celda.add_paragraph(recuadro_.explicacion)
    monoespaciada = recuadro_.tipo in ("formula", "plantilla")
    for linea in recuadro_.lineas:
        parrafo = celda.add_paragraph()
        parrafo.paragraph_format.space_after = Pt(0 if monoespaciada else 4)
        corrida = parrafo.add_run(linea)
        if monoespaciada:
            corrida.font.name = MONOESPACIADA
            corrida.font.size = Pt(9.5)
            propiedades = parrafo._p.get_or_add_pPr()
            sombra = OxmlElement("w:shd")
            sombra.set(qn("w:val"), "clear")
            sombra.set(qn("w:color"), "auto")
            sombra.set(qn("w:fill"), estilo.BLANCO)
            propiedades.append(sombra)
    documento.add_paragraph()


def generar_laboratorio(contenido, identidad: Identidad, portada: Portada, destino: Path, imagenes: dict,
                        aviso_adjuntos: str = "", nombre_zip: str = "", hojas: dict | None = None,
                        funciones: list[tuple[str, str]] | None = None, sesion: int | None = None) -> Path:
    """Guía del alumno con la estructura de la referencia (decisión 33).
    `imagenes`: {(ejercicio, paso): Imagen}; `hojas`: {archivo: [hojas]}; `funciones`: [(español, inglés)]."""
    documento = documento_base(identidad, portada)
    if sesion is not None:
        _pie(documento, f"Sesión {sesion} · Laboratorio", identidad)
    antes = contenido.antes_de_empezar
    documento.add_heading("Antes de empezar", level=1)
    for texto in antes.contexto:
        documento.add_paragraph(texto)
    documento.add_paragraph(CADA_UNO_SOLO)
    if aviso_adjuntos:
        documento.add_paragraph(aviso_adjuntos)
    documento.add_heading("Archivos de práctica", level=2)
    if nombre_zip:
        cuantos = len(contenido.archivos)
        documento.add_paragraph(f"Los {cuantos} archivos están en el archivo comprimido {nombre_zip}."
                                if cuantos > 1 else f"El archivo está en el archivo comprimido {nombre_zip}.")
    ejercicio_de = {n: e.numero for e in contenido.ejercicios for n in e.archivos}
    tabla_de_datos(documento, identidad, Tabla(
        titulo="", encabezados=["Archivo", "Ejercicio", "Contenido"],
        filas=[[a.nombre, str(ejercicio_de.get(a.nombre, "")), a.descripcion] for a in contenido.archivos]))
    for tabla_ in antes.tablas:
        if tabla_.titulo:
            documento.add_heading(tabla_.titulo, level=2)
        tabla_de_datos(documento, identidad, Tabla(titulo="", encabezados=tabla_.encabezados, filas=tabla_.filas))
    for regla in antes.reglas:
        documento.add_paragraph(regla, style="List Bullet")
    if funciones:
        recuadro(documento, identidad, "Antes de copiar una fórmula", ANTES_DE_COPIAR)
        tabla_de_datos(documento, identidad, Tabla(titulo="", encabezados=["Función en español", "Función en inglés"],
                                                   filas=[list(f) for f in funciones]))

    contador = [0]
    for e in contenido.ejercicios:
        titulo = documento.add_heading(f"Ejercicio {e.numero} · {e.titulo}", level=1)
        titulo.paragraph_format.page_break_before = True       # cada ejercicio empieza en una página nueva
        area = documento.add_paragraph()
        area.add_run("Área: ").bold = True
        area.add_run(e.area)
        _subtitulo(documento, "Situación", identidad)
        documento.add_paragraph(e.situacion)
        if e.archivos:
            _subtitulo(documento, "Archivos de práctica", identidad)
            for nombre in e.archivos:
                parrafo = documento.add_paragraph(style="List Bullet")
                parrafo.add_run(nombre).bold = True
                nombres_de_hojas = (hojas or {}).get(nombre) or []
                if len(nombres_de_hojas) > 1:
                    parrafo.add_run(f". Tiene {len(nombres_de_hojas)} hojas: "
                                    + ", ".join(nombres_de_hojas[:-1]) + f" y {nombres_de_hojas[-1]}.")
                elif nombres_de_hojas:
                    parrafo.add_run(f". Tiene una hoja: {nombres_de_hojas[0]}.")
                else:
                    parrafo.add_run(".")
        _subtitulo(documento, "Pasos", identidad)
        con_figura = {i: imagenes[(e.numero, i)] for i in range(1, len(e.pasos) + 1) if (e.numero, i) in imagenes}
        _lista_numerada(documento, [p.texto for p in e.pasos], identidad, con_figura,
                        [p.figura for p in e.pasos], contador)
        documento.add_paragraph()
        for recuadro_ in e.copiar:
            recuadro_para_copiar(documento, identidad, recuadro_)
        documento.add_heading(MEJORA, level=2)
        documento.add_paragraph(e.mejora.texto)
        if e.mejora.pasos:
            _lista_numerada(documento, e.mejora.pasos, identidad)
            documento.add_paragraph()
        for recuadro_ in e.mejora.copiar:
            recuadro_para_copiar(documento, identidad, recuadro_)
    destino.parent.mkdir(parents=True, exist_ok=True)
    documento.save(destino)
    return destino


# ---------- Evaluación práctica (SKILL.md, «Material 6»; PLAN.md §0, decisión 64) ----------

CADA_PREGUNTA_SOLA = "Cada pregunta funciona sola. Puedes resolverlas en cualquier orden."
ALTO_DE_FILA_DE_RESPUESTA = Cm(1)


def _tabla_sin_minimo(encabezados: list[str], filas: list[list[str]]) -> Tabla:
    """La tabla de respuesta puede tener una sola columna; Tabla pide dos, así que se arma sin validar."""
    return Tabla.model_construct(titulo="", encabezados=encabezados, filas=filas)


def _encabezado_de_pregunta(documento: Document, p) -> None:
    titulo = documento.add_heading(f"Pregunta {p.numero} · {p.titulo}", level=1)
    titulo.paragraph_format.page_break_before = True          # cada pregunta empieza en una página nueva


def generar_evaluacion(contenido, identidad: Identidad, portada: Portada, destino: Path, nombre_zip: str = "",
                       sesion: int | None = None) -> Path:
    """Hoja del alumno (SKILL.md, «Material 6»): después de la portada, las dos líneas de indicaciones; por pregunta,
    título, situación, archivos, tarea en pasos y la tabla donde escribe la respuesta. Sin respuestas, sin el
    concepto que evalúa, sin puntos ni tiempos."""
    documento = documento_base(identidad, portada)
    if sesion is not None:
        _pie(documento, f"Sesión {sesion} · Evaluación práctica", identidad)
    documento.add_heading("Indicaciones", level=1)
    documento.add_paragraph(contenido.indicaciones.consulta)
    documento.add_paragraph(contenido.indicaciones.entrega)
    documento.add_paragraph(CADA_PREGUNTA_SOLA)
    if contenido.archivos:
        documento.add_heading("Archivos de la evaluación", level=2)
        if nombre_zip:
            cuantos = len(contenido.archivos)
            documento.add_paragraph(f"Los {cuantos} archivos están en el archivo comprimido {nombre_zip}."
                                    if cuantos > 1 else f"El archivo está en el archivo comprimido {nombre_zip}.")
        pregunta_de = {n: p.numero for p in contenido.preguntas for n in p.archivos}
        tabla_de_datos(documento, identidad, Tabla(
            titulo="", encabezados=["Archivo", "Pregunta", "Contenido"],
            filas=[[a.nombre, str(pregunta_de.get(a.nombre, "")), a.descripcion] for a in contenido.archivos]))
    for p in contenido.preguntas:
        _encabezado_de_pregunta(documento, p)
        _subtitulo(documento, "Situación", identidad)
        documento.add_paragraph(p.situacion)
        if p.archivos:
            _subtitulo(documento, "Archivos", identidad)
            for nombre in p.archivos:
                documento.add_paragraph(style="List Bullet").add_run(nombre).bold = True
        _subtitulo(documento, "Tarea", identidad)
        _lista_numerada(documento, p.pasos, identidad)
        _subtitulo(documento, "Tu respuesta", identidad)
        tabla = p.tabla_de_respuesta
        if tabla.titulo:
            documento.add_paragraph(tabla.titulo)
        tabla_de_datos(documento, identidad, _tabla_sin_minimo(tabla.encabezados, tabla.filas))
        for fila in documento.tables[-1].rows[1:]:          # espacio para escribir a mano en cada fila
            fila.height, fila.height_rule = ALTO_DE_FILA_DE_RESPUESTA, WD_ROW_HEIGHT_RULE.AT_LEAST
    destino.parent.mkdir(parents=True, exist_ok=True)
    documento.save(destino)
    return destino


def generar_clave(contenido, identidad: Identidad, portada: Portada, destino: Path, sesion: int | None = None) -> Path:
    """Clave de corrección, en un Word aparte con el título «Clave de la evaluación» (SKILL.md, «Material 6»): por
    pregunta, la respuesta completa como se vería en la tabla, las partes una por línea, las otras respuestas
    aceptadas, los problemas sembrados y los errores más comunes."""
    documento = documento_base(identidad, portada)
    if sesion is not None:
        _pie(documento, f"Sesión {sesion} · Clave de la evaluación", identidad)
    problemas_de = {}
    for archivo in contenido.archivos:
        if archivo.problema:
            problemas_de.setdefault(archivo.nombre, []).append(archivo.problema)
    for p in contenido.preguntas:
        _encabezado_de_pregunta(documento, p)
        concepto = documento.add_paragraph()
        concepto.add_run("Concepto que evalúa: ").bold = True
        concepto.add_run(p.concepto)
        _subtitulo(documento, "Respuesta correcta", identidad)
        tabla_de_datos(documento, identidad, _tabla_sin_minimo(p.tabla_de_respuesta.encabezados, p.clave.respuesta))
        if p.clave.aceptadas:
            _subtitulo(documento, "Otras respuestas aceptadas", identidad)
            for texto in p.clave.aceptadas:
                documento.add_paragraph(texto, style="List Bullet")
        _subtitulo(documento, "Partes de la respuesta", identidad)
        for texto in p.clave.partes:
            documento.add_paragraph(texto, style="List Bullet")
        sembrados = [*p.clave.problemas,
                     *[f"{nombre}: {t}" for nombre in p.archivos for t in problemas_de.get(nombre, [])]]
        if sembrados:
            _subtitulo(documento, "Problemas sembrados en los archivos", identidad)
            for texto in sembrados:
                documento.add_paragraph(texto, style="List Bullet")
        _subtitulo(documento, "Errores comunes", identidad)
        for texto in p.clave.errores_comunes:
            documento.add_paragraph(texto, style="List Bullet")
    destino.parent.mkdir(parents=True, exist_ok=True)
    documento.save(destino)
    return destino
