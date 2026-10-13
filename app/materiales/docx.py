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


# ---------- Laboratorio (SKILL.md, «Material 3») ----------

MEJORA = "Mejora el resultado (opcional)"
_MENCION_DE_FIGURA = re.compile(r"\s*\(?\s*mira la figura\s*\d*\s*\.?\)?\s*", re.I)


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


def generar_laboratorio(contenido, identidad: Identidad, portada: Portada, destino: Path, imagenes: dict,
                        aviso_adjuntos: str = "") -> Path:
    """Guía del alumno: portada «Laboratorio», tabla de archivos de práctica y cada ejercicio con su situación,
    sus archivos, sus pasos (con sus figuras), lo que copia y «Mejora el resultado (opcional)».
    `imagenes`: {(ejercicio, paso): Imagen} de app/materiales/figuras.py."""
    documento = documento_base(identidad, portada)
    documento.add_heading("Archivos de práctica", level=1)
    if aviso_adjuntos:
        documento.add_paragraph(aviso_adjuntos)
    ejercicio_de = {n: e.numero for e in contenido.ejercicios for n in e.archivos}
    tabla_de_datos(documento, identidad, Tabla(
        titulo="", encabezados=["Archivo", "Ejercicio", "Contenido"],
        filas=[[a.nombre, f"Ejercicio {ejercicio_de.get(a.nombre, '')}", a.descripcion] for a in contenido.archivos]))
    numero_figura = 0
    for e in contenido.ejercicios:
        documento.add_heading(f"Ejercicio {e.numero} · {e.titulo}", level=1)
        documento.add_paragraph(e.situacion)
        if e.archivos:
            archivos_ = documento.add_paragraph()
            archivos_.add_run("Archivos de práctica: ").bold = True
            archivos_.add_run(", ".join(e.archivos) + ".")
        documento.add_heading("Pasos", level=2)
        for i, paso in enumerate(e.pasos, start=1):
            texto = _MENCION_DE_FIGURA.sub(" ", paso.texto).strip()
            imagen = imagenes.get((e.numero, i))
            if imagen is not None:
                numero_figura += 1
                texto = f"{texto} Mira la figura {numero_figura}."
            parrafo = documento.add_paragraph(f"{i}. {texto}")
            parrafo.paragraph_format.left_indent = Cm(0.6)
            parrafo.paragraph_format.first_line_indent = Cm(-0.6)
            if imagen is not None:
                parrafo.paragraph_format.keep_with_next = True
                _figura(documento, imagen, numero_figura, paso.figura.descripcion)
        for recuadro_ in e.copiar:
            recuadro(documento, identidad, recuadro_.titulo, [], lineas_para_copiar=recuadro_.lineas)
        documento.add_heading(MEJORA, level=2)
        recuadro(documento, identidad, "Pedido de seguimiento", [], lineas_para_copiar=[e.mejora])
    destino.parent.mkdir(parents=True, exist_ok=True)
    documento.save(destino)
    return destino
