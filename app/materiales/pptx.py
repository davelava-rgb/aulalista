"""Generador de las diapositivas de AulaLista, con el diseño común de la skill.

Diapositivas (SKILL.md, «Material 2»): PowerPoint 16:9, una idea por diapositiva, frases cortas,
ejemplos en recuadros legibles a distancia y notas del profesor en cada diapositiva.
Diseño común: la identidad visual de la ficha, tres colores como máximo más los fondos de recuadro,
recuadros sombreados con borde izquierdo de color y tablas con encabezado en el color principal,
filas alternas en gris muy claro y sin bordes verticales.

El generador elige el tamaño de letra que cabe según una estimación. Quien mide de verdad es
PowerPoint (app/office.py, medir_diapositivas): un texto que se sale de su recuadro es una falla.
"""

import math
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Cm, Emu, Pt

from app.materiales import estilo
from app.materiales.contenido import Diapositiva, Diapositivas, Notas, Tabla
from app.materiales.docx import Portada, lineas_de_contacto
from app.materiales.estilo import Identidad

ANCHO, ALTO = Cm(33.867), Cm(19.05)          # 16:9
MARGEN = Cm(1.6)
TITULO_ARRIBA, TITULO_ALTO = Cm(0.9), Cm(2.3)
CUERPO_ARRIBA = Cm(3.6)
CUERPO_ALTO = ALTO - CUERPO_ARRIBA - Cm(1.2)
CUERPO_ANCHO = ANCHO - 2 * MARGEN
SEPARACION = Cm(0.8)
BORDE = Cm(0.25)                              # borde izquierdo de color de los recuadros

TAMANO_TITULO = 32
TAMANO_CUERPO = 26
TAMANO_MINIMO = 18                            # menos que esto no se lee a distancia
TAMANO_TABLA = 20
ALTO_FILA = Cm(1.25)

DISENO_SOLO_TITULO = 5
DISENO_EN_BLANCO = 6
SIN_ESTILO_NI_CUADRICULA = "{2D5ABB26-0587-4C30-8999-92F81FD0307C}"


def _rgb(color: str) -> RGBColor:
    return RGBColor.from_string(color)


def alto_estimado(parrafos: list[str], ancho: Emu, tamano: int) -> Emu:
    """Estimación: letras por renglón según el ancho y renglones según el largo de cada párrafo."""
    letras_por_renglon = max(8, int(Emu(ancho).pt / (tamano * 0.5)))
    renglones = sum(max(1, math.ceil(len(p) / letras_por_renglon)) for p in parrafos)
    return Pt(renglones * tamano * 1.2 + len(parrafos) * tamano * 0.45)


def _cabe(parrafos: list[str], ancho: Emu, alto: Emu, tamano: int) -> bool:
    return alto_estimado(parrafos, ancho, tamano) <= alto


def tamano_que_cabe(parrafos: list[str], ancho: Emu, alto: Emu, base: int = TAMANO_CUERPO) -> int:
    for tamano in range(base, TAMANO_MINIMO - 1, -2):
        if _cabe(parrafos, ancho, alto, tamano):
            return tamano
    return TAMANO_MINIMO


def _vineta(parrafo, numerada: bool, tamano: int) -> None:
    """Viñeta o número real de PowerPoint, con sangría francesa."""
    ppr = parrafo._p.get_or_add_pPr()
    sangria = int(Pt(tamano) * 1.1)
    ppr.set("marL", str(sangria))
    ppr.set("indent", str(-sangria))
    for viejo in ppr.findall(qn("a:buNone")) + ppr.findall(qn("a:buChar")) + ppr.findall(qn("a:buAutoNum")):
        ppr.remove(viejo)
    if numerada:
        vineta = ppr.makeelement(qn("a:buAutoNum"), {"type": "arabicPeriod"})
    else:
        vineta = ppr.makeelement(qn("a:buChar"), {"char": "•"})
    ppr.append(vineta)


def _escribir(marco, parrafos: list[str], identidad: Identidad, tamano: int, *, titulo: str = "",
              color_titulo: str | None = None, vinetas: bool = False, numerada: bool = False) -> None:
    marco.word_wrap = True
    marco.auto_size = MSO_AUTO_SIZE.NONE
    marco.vertical_anchor = MSO_ANCHOR.TOP
    primero = True
    if titulo:
        p = marco.paragraphs[0]
        corrida = p.add_run()
        corrida.text = titulo
        _letra(corrida, identidad, tamano, color_titulo or identidad.texto, negrita=True)
        p.space_after = Pt(tamano * 0.4)
        p.alignment = PP_ALIGN.LEFT
        primero = False
    for texto in parrafos:
        p = marco.paragraphs[0] if primero else marco.add_paragraph()
        primero = False
        corrida = p.add_run()
        corrida.text = texto
        _letra(corrida, identidad, tamano, identidad.texto)
        p.space_after = Pt(tamano * 0.45)
        p.alignment = PP_ALIGN.LEFT
        if vinetas or numerada:
            _vineta(p, numerada, tamano)


def _letra(corrida, identidad: Identidad, tamano: float, color: str, negrita: bool = False) -> None:
    corrida.font.name = identidad.tipografia
    corrida.font.size = Pt(tamano)
    corrida.font.bold = negrita
    corrida.font.color.rgb = _rgb(color)


def _caja(diapositiva, izquierda, arriba, ancho, alto):
    caja = diapositiva.shapes.add_textbox(izquierda, arriba, ancho, alto)
    return caja.text_frame


def _titulo(diapositiva, texto: str, identidad: Identidad) -> None:
    titulo = diapositiva.shapes.title
    titulo.left, titulo.top, titulo.width, titulo.height = MARGEN, TITULO_ARRIBA, CUERPO_ANCHO, TITULO_ALTO
    marco = titulo.text_frame
    marco.clear()
    marco.word_wrap = True
    marco.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = marco.paragraphs[0]
    corrida = p.add_run()
    corrida.text = texto
    tamano = TAMANO_TITULO if _cabe([texto], CUERPO_ANCHO, TITULO_ALTO, TAMANO_TITULO) else 26
    _letra(corrida, identidad, tamano, estilo.para_texto(identidad.principal), negrita=True)
    p.alignment = PP_ALIGN.LEFT


def _notas(diapositiva, notas: Notas) -> None:
    diapositiva.notes_slide.notes_text_frame.text = notas.texto()


MARGEN_RECUADRO_LADO, MARGEN_RECUADRO_ALTO = Cm(0.6), Cm(0.4)


def medida_de_recuadro(parrafos: list[str], ancho, alto_maximo, titulo: str = "",
                       base: int = TAMANO_CUERPO) -> tuple[int, Emu]:
    """Tamaño de letra y alto del recuadro: el alto justo para su texto, sin pasar del espacio disponible."""
    textos = ([titulo] if titulo else []) + parrafos
    interior_ancho = ancho - BORDE - 2 * MARGEN_RECUADRO_LADO - Cm(0.8)   # la sangría de las viñetas
    interior_alto = alto_maximo - 2 * MARGEN_RECUADRO_ALTO
    tamano = tamano_que_cabe(textos, interior_ancho, interior_alto, base)
    alto = alto_estimado(textos, interior_ancho, tamano) + 2 * MARGEN_RECUADRO_ALTO + Cm(0.6)
    return tamano, min(alto_maximo, max(Cm(3), alto))


def _sin_sombra_ni_linea(figura) -> None:
    figura.line.fill.background()
    figura.shadow.inherit = False


def recuadro(diapositiva, identidad: Identidad, izquierda, arriba, ancho, alto_maximo, parrafos: list[str], *,
             titulo: str = "", color_borde: str | None = None, vinetas: bool = False,
             base: int = TAMANO_CUERPO, medida: tuple[int, Emu] | None = None) -> None:
    """Recuadro sombreado con borde izquierdo de color. Mismo estilo que en los Word."""
    color = color_borde or identidad.principal
    tamano, alto = medida or medida_de_recuadro(parrafos, ancho, alto_maximo, titulo, base)
    borde = diapositiva.shapes.add_shape(MSO_SHAPE.RECTANGLE, izquierda, arriba, BORDE, alto)
    borde.fill.solid()
    borde.fill.fore_color.rgb = _rgb(color)
    _sin_sombra_ni_linea(borde)
    caja = diapositiva.shapes.add_shape(MSO_SHAPE.RECTANGLE, izquierda + BORDE, arriba, ancho - BORDE, alto)
    caja.fill.solid()
    caja.fill.fore_color.rgb = _rgb(identidad.fondo)
    _sin_sombra_ni_linea(caja)
    marco = caja.text_frame
    marco.margin_left = marco.margin_right = MARGEN_RECUADRO_LADO
    marco.margin_top = marco.margin_bottom = MARGEN_RECUADRO_ALTO
    _escribir(marco, parrafos, identidad, tamano, titulo=titulo,
              color_titulo=estilo.para_texto(color, identidad.fondo), vinetas=vinetas)


def tabla(diapositiva, identidad: Identidad, datos: Tabla, arriba, alto_disponible) -> None:
    """Encabezado en el color principal, filas alternas en gris muy claro y sin bordes verticales."""
    filas, columnas = 1 + len(datos.filas), len(datos.encabezados)
    alto = min(alto_disponible, ALTO_FILA * filas)
    marco = diapositiva.shapes.add_table(filas, columnas, MARGEN, arriba, CUERPO_ANCHO, alto)
    estilo_tabla = marco._element.graphic.graphicData.tbl.tblPr.find(qn("a:tableStyleId"))
    if estilo_tabla is not None:
        estilo_tabla.text = SIN_ESTILO_NI_CUADRICULA
    t = marco.table
    t.first_row, t.horz_banding = True, False
    for fila_numero in range(filas):
        valores = datos.encabezados if fila_numero == 0 else datos.filas[fila_numero - 1]
        for columna, texto in enumerate(valores):
            celda = t.cell(fila_numero, columna)
            celda.fill.solid()
            if fila_numero == 0:
                celda.fill.fore_color.rgb = _rgb(identidad.principal)
            else:
                celda.fill.fore_color.rgb = _rgb(estilo.GRIS_FILA_ALTERNA if fila_numero % 2 == 0 else estilo.BLANCO)
            marco_celda = celda.text_frame
            marco_celda.word_wrap = True
            corrida = marco_celda.paragraphs[0].add_run()
            corrida.text = texto
            _letra(corrida, identidad, TAMANO_TABLA, estilo.BLANCO if fila_numero == 0 else identidad.texto,
                   negrita=fila_numero == 0)


# ---------- Cada tipo de diapositiva ----------

def _nueva(presentacion, diseno: int = DISENO_SOLO_TITULO):
    return presentacion.slides.add_slide(presentacion.slide_layouts[diseno])


def _portada(presentacion, identidad: Identidad, portada: Portada, notas: Notas) -> None:
    diapositiva = _nueva(presentacion, DISENO_EN_BLANCO)
    arriba = Cm(4.2)
    if identidad.estilo.franja:  # estilos moderno y corporativo (decisión 27)
        franja = diapositiva.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, presentacion.slide_width, Cm(0.9))
        franja.fill.solid()
        franja.fill.fore_color.rgb = _rgb(identidad.principal)
        _sin_sombra_ni_linea(franja)
    if identidad.logo is not None:
        diapositiva.shapes.add_picture(str(identidad.logo), MARGEN, Cm(1.4), height=Cm(2.4))
    for texto, tamano, color, negrita, alto in (
            (portada.curso, 40, estilo.para_texto(identidad.principal), True, Cm(4.6)),
            (portada.sesion, 26, identidad.texto, False, Cm(3.2)),
            (f"Docente: {portada.docente}" if portada.docente else "", 20, identidad.texto, False, Cm(1.6)),
            *((dato, 16, identidad.texto, False, Cm(1.0)) for dato in lineas_de_contacto(portada.contacto))):
        if not texto:
            continue
        marco = _caja(diapositiva, MARGEN, arriba, CUERPO_ANCHO, alto)
        marco.word_wrap = True
        marco.auto_size = MSO_AUTO_SIZE.NONE
        corrida = marco.paragraphs[0].add_run()
        corrida.text = texto
        _letra(corrida, identidad, tamano, color, negrita)
        arriba += alto
    _notas(diapositiva, notas)


def _con_frases(presentacion, identidad: Identidad, titulo: str, frases: list[str], notas: Notas, *,
                vinetas: bool = True, numerada: bool = False, base: int = TAMANO_CUERPO) -> None:
    diapositiva = _nueva(presentacion)
    _titulo(diapositiva, titulo, identidad)
    marco = _caja(diapositiva, MARGEN, CUERPO_ARRIBA, CUERPO_ANCHO, CUERPO_ALTO)
    tamano = tamano_que_cabe(frases, CUERPO_ANCHO - Cm(0.5), CUERPO_ALTO - Cm(0.3), base)
    _escribir(marco, frases, identidad, tamano, vinetas=vinetas and not numerada, numerada=numerada)
    _notas(diapositiva, notas)


def _de_concepto(presentacion, identidad: Identidad, d: Diapositiva) -> None:
    if d.tipo == "frases":
        _con_frases(presentacion, identidad, d.titulo, d.frases, d.notas)
        return
    if d.tipo == "pasos":
        _con_frases(presentacion, identidad, d.titulo, d.frases, d.notas, numerada=True)
        return
    diapositiva = _nueva(presentacion)
    _titulo(diapositiva, d.titulo, identidad)
    arriba, alto = CUERPO_ARRIBA, CUERPO_ALTO
    if d.tipo == "ejemplo":
        recuadro(diapositiva, identidad, MARGEN, arriba, CUERPO_ANCHO, alto, d.frases)
    elif d.tipo == "columnas":
        ancho = (CUERPO_ANCHO - SEPARACION) // 2
        # Las dos columnas con la misma letra y el mismo alto, para que se comparen a la vista.
        medidas = [medida_de_recuadro(c.frases, ancho, alto, c.titulo, base=24) for c in d.columnas]
        medida = (min(m[0] for m in medidas), max(m[1] for m in medidas))
        for i, columna in enumerate(d.columnas):
            recuadro(diapositiva, identidad, MARGEN + i * (ancho + SEPARACION), arriba, ancho, alto, columna.frases,
                     titulo=columna.titulo, vinetas=True, medida=medida)
    elif d.tipo == "tabla":
        if d.frases:
            alto_frases = Cm(1.6) * len(d.frases)
            marco = _caja(diapositiva, MARGEN, arriba, CUERPO_ANCHO, alto_frases)
            _escribir(marco, d.frases, identidad, tamano_que_cabe(d.frases, CUERPO_ANCHO, alto_frases, 24))
            arriba, alto = arriba + alto_frases, alto - alto_frases
        tabla(diapositiva, identidad, d.tabla, arriba, alto)
    _notas(diapositiva, d.notas)


def generar_diapositivas(contenido: Diapositivas, identidad: Identidad, portada: Portada, destino: Path) -> Path:
    presentacion = Presentation()
    presentacion.slide_width, presentacion.slide_height = ANCHO, ALTO
    _portada(presentacion, identidad, portada, contenido.portada.notas)
    _con_frases(presentacion, identidad, "Idea central", contenido.idea_central.frases, contenido.idea_central.notas,
                vinetas=False, base=30)
    for d in contenido.diapositivas:
        _de_concepto(presentacion, identidad, d)

    aplicalo = contenido.aplicalo
    diapositiva = _nueva(presentacion)
    _titulo(diapositiva, "Aplícalo así", identidad)
    arriba, alto = CUERPO_ARRIBA, CUERPO_ALTO
    if aplicalo.frases:
        alto_frases = Cm(1.7) * len(aplicalo.frases)
        marco = _caja(diapositiva, MARGEN, arriba, CUERPO_ANCHO, alto_frases)
        _escribir(marco, aplicalo.frases, identidad, tamano_que_cabe(aplicalo.frases, CUERPO_ANCHO, alto_frases, 24))
        arriba, alto = arriba + alto_frases + Cm(0.3), alto - alto_frases - Cm(0.3)
    recuadro(diapositiva, identidad, MARGEN, arriba, CUERPO_ANCHO, alto, aplicalo.plantilla, base=24)
    _notas(diapositiva, aplicalo.notas)

    diapositiva = _nueva(presentacion)
    _titulo(diapositiva, "Cuidado con", identidad)
    recuadro(diapositiva, identidad, MARGEN, CUERPO_ARRIBA, CUERPO_ANCHO, CUERPO_ALTO, contenido.cuidado.riesgos,
             color_borde=identidad.advertencia, vinetas=True)
    _notas(diapositiva, contenido.cuidado.notas)

    destino.parent.mkdir(parents=True, exist_ok=True)
    presentacion.save(destino)
    return destino
