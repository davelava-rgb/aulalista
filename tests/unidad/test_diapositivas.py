"""Las diapositivas: PowerPoint 16:9 desde la lectura aprobada, validado en dos pasadas (SKILL.md, Material 2)."""

import asyncio
import copy
import re
import zipfile
from urllib.parse import unquote

import openpyxl
import pytest
from fastapi.testclient import TestClient
from pptx import Presentation
from pptx.util import Pt

from app import office, servidor
from app.materiales import comun, diapositivas, estilo, lectura
from app.materiales import pptx as generador
from app.materiales.contenido import Diapositivas
from app.materiales.docx import Portada
from tests.conftest import consulta_en_secuencia
from tests.unidad.test_lectura import LIMPIA, SIN_ERRORES, error, revision, sesion, una_pagina  # noqa: F401

cliente = TestClient(servidor.app)

NOTAS = {"destacar": "Que el equipo ve el trabajo.", "preguntar": "¿Qué ven ustedes en su tablero?"}


def diapositiva(bloque, titulo, tipo="frases", frases=None, **otros):
    return {"bloque": bloque, "titulo": titulo, "tipo": tipo, "frases": frases or [], "columnas": [],
            "tabla": None, "notas": NOTAS, **otros}


MANIFIESTO, PILARES = "El Manifiesto Ágil", "Pilares de Scrum"
LIMPIAS = {
    "portada": {"notas": NOTAS},
    "idea_central": {"frases": ["Scrum ayuda a un equipo a trabajar con lo que observa."], "notas": NOTAS},
    "diapositivas": [
        diapositiva(MANIFIESTO, "El Manifiesto Ágil", frases=["El Manifiesto Ágil tiene cuatro aspectos."]),
        diapositiva(MANIFIESTO, "Qué valora más", "tabla", frases=["Cada aspecto valora más un elemento."],
                    tabla={"titulo": "", "encabezados": ["Aspecto", "Qué valora más"],
                           "filas": [["Primero", "Las personas"], ["Segundo", "El producto que funciona"]]}),
        diapositiva(MANIFIESTO, "Ejemplo: la tienda", "ejemplo", frases=["Una tienda conversa con sus clientes cada semana."]),
        diapositiva(MANIFIESTO, "Personas y producto", "columnas",
                    columnas=[{"titulo": "Primero", "frases": ["Las personas."]},
                              {"titulo": "Segundo", "frases": ["El producto que funciona."]}]),
        diapositiva(MANIFIESTO, "Para recordar", frases=["El Manifiesto Ágil tiene cuatro aspectos."]),
        diapositiva(PILARES, "Pilares de Scrum", frases=["Los pilares de Scrum son tres."]),
        diapositiva(PILARES, "Cómo se usan", "pasos", frases=["Observa el tablero.", "Decide qué cambiar."]),
        diapositiva(PILARES, "Ejemplo: el tablero", "ejemplo", frases=["El equipo muestra su tablero a todos."]),
        diapositiva(PILARES, "Todos ven el trabajo", frases=["El equipo muestra su tablero a todos."]),
        diapositiva(PILARES, "Para recordar", frases=["Los pilares de Scrum son tres."]),
    ],
    "aplicalo": {"frases": ["Usa estas dos preguntas al cerrar cada semana."],
                 "plantilla": ["Qué observamos esta semana.", "Qué cambiamos la próxima semana."], "notas": NOTAS},
    "cuidado": {"riesgos": ["Revisar el avance sin cambiar nada después."], "notas": NOTAS},
    "pasajes": [{"oracion": "Los pilares de Scrum son tres.", "fuente": diapositivas.FUENTE_LECTURA,
                 "ubicacion": PILARES, "texto": "Los pilares de Scrum son tres."}],
    "decisiones": [{"texto": "Repetí una frase de cierre en cada bloque.", "tipo": "nota"}],
}


def con(**cambios) -> dict:
    datos = copy.deepcopy(LIMPIAS)
    datos.update(cambios)
    return datos


def medir_sin_desbordes(ruta, _carpeta):
    return office.Medicion(diapositivas=len(Presentation(ruta).slides), desbordes=[], imagenes=[])


@pytest.fixture
def con_lectura(sesion):  # noqa: F811
    """Curso con las dos fichas confirmadas y la lectura generada y aprobada."""
    asyncio.run(lectura.generar(sesion, "scrum", 1, consulta=consulta_en_secuencia(LIMPIA, SIN_ERRORES),
                                contar_paginas=una_pagina))
    lectura.aprobar(sesion, 1)
    return sesion


def generar(carpeta, *salidas, medir=medir_sin_desbordes, revisar=True):
    consulta = consulta_en_secuencia(*salidas, *([SIN_ERRORES] if revisar else []))
    material = asyncio.run(diapositivas.generar(carpeta, "scrum", 1, consulta=consulta, medir=medir))
    return material, consulta


# ---------- PowerPoint con el diseño de la skill ----------

@pytest.fixture
def presentacion(tmp_path):
    identidad = estilo.Identidad(**estilo.PALETA_SOBRIA, tipografia="Calibri", logo=None)
    ruta = generador.generar_diapositivas(Diapositivas.model_validate(LIMPIAS), identidad,
                                          Portada("Scrum Master con IA", "Sesión 1 · Fundamentos", "Diapositivas"),
                                          tmp_path / "S1_Diapositivas.pptx")
    return ruta, identidad


def test_16_9_con_portada_idea_central_conceptos_y_cierre(presentacion):
    p = Presentation(presentacion[0])
    assert round(p.slide_width / p.slide_height, 2) == round(16 / 9, 2)
    assert len(p.slides) == 14
    titulos = [s.shapes.title.text if s.shapes.title is not None else "" for s in p.slides]
    assert titulos[1] == "Idea central" and titulos[-2:] == ["Aplícalo así", "Cuidado con"]
    portada = " ".join(f.text_frame.text for f in p.slides[0].shapes if f.has_text_frame)
    assert "Scrum Master con IA" in portada and "Sesión 1 · Fundamentos" in portada
    assert not any(t in ("Preguntas", "Gracias") for t in titulos)


def test_notas_del_profesor_en_cada_diapositiva(presentacion):
    for s in Presentation(presentacion[0]).slides:
        notas = s.notes_slide.notes_text_frame.text
        assert "Qué destacar:" in notas and "Qué preguntar al grupo:" in notas


def test_letra_legible_a_distancia(presentacion):
    tamanos = [r.font.size for s in Presentation(presentacion[0]).slides for f in s.shapes if f.has_text_frame
               for par in f.text_frame.paragraphs for r in par.runs]
    assert tamanos and min(tamanos) >= Pt(generador.TAMANO_MINIMO)


def test_recuadros_con_borde_izquierdo_y_tabla_del_diseno_comun(presentacion):
    ruta, identidad = presentacion
    xml = zipfile.ZipFile(ruta).read("ppt/slides/slide5.xml").decode("utf-8")   # el ejemplo de la tienda
    assert f'<a:srgbClr val="{identidad.principal}"/>' in xml and f'<a:srgbClr val="{identidad.fondo}"/>' in xml
    tabla = zipfile.ZipFile(ruta).read("ppt/slides/slide4.xml").decode("utf-8")
    assert generador.SIN_ESTILO_NI_CUADRICULA in tabla          # sin bordes de la plantilla
    assert f'<a:srgbClr val="{estilo.GRIS_FILA_ALTERNA}"/>' in tabla
    cuidado = zipfile.ZipFile(ruta).read("ppt/slides/slide14.xml").decode("utf-8")
    assert f'<a:srgbClr val="{identidad.advertencia}"/>' in cuidado


def test_diseno_uniforme_solo_usa_los_colores_de_la_identidad(presentacion):
    ruta, identidad = presentacion
    archivo = zipfile.ZipFile(ruta)
    xml = "".join(archivo.read(n).decode("utf-8") for n in archivo.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n))
    usados = set(re.findall(r'<a:srgbClr val="([0-9A-Fa-f]{6})"', xml))
    assert usados and usados <= identidad.colores_permitidos()


def test_un_texto_largo_baja_de_tamano_sin_pasar_del_minimo():
    corto = generador.tamano_que_cabe(["Una frase corta."], generador.CUERPO_ANCHO, generador.CUERPO_ALTO)
    largo = generador.tamano_que_cabe(["Una frase larga que se repite. " * 12] * 6, generador.CUERPO_ANCHO,
                                      generador.CUERPO_ALTO)
    assert corto == generador.TAMANO_CUERPO and largo == generador.TAMANO_MINIMO


# ---------- Estructura: cantidad y orden de la lectura ----------

def lectura_limpia():
    from app.materiales.contenido import Lectura
    return Lectura.model_validate(LIMPIA)


def test_cuenta_las_cuatro_fijas_y_pide_de_14_a_18():
    _, problemas = diapositivas._validar(con(diapositivas=LIMPIAS["diapositivas"][:9]), lectura_limpia())
    assert any("hay 13 con las 4 fijas; deben ser de 14 a 18" in p for p in problemas)


def test_sigue_el_orden_de_la_lectura():
    desordenadas = LIMPIAS["diapositivas"][5:] + LIMPIAS["diapositivas"][:5]
    _, problemas = diapositivas._validar(con(diapositivas=desordenadas), lectura_limpia())
    assert any("no sigue el orden de la lectura" in p for p in problemas)


def test_cada_bloque_de_la_lectura_tiene_diapositivas_y_ninguna_inventa_un_bloque():
    sin_pilares = [d for d in LIMPIAS["diapositivas"] if d["bloque"] == MANIFIESTO] * 2
    _, problemas = diapositivas._validar(con(diapositivas=sin_pilares), lectura_limpia())
    assert any("«Pilares de Scrum» de la lectura no tiene diapositivas" in p for p in problemas)
    otra = copy.deepcopy(LIMPIAS["diapositivas"])
    otra[0]["bloque"] = "Historia de Scrum"
    _, problemas = diapositivas._validar(con(diapositivas=otra), lectura_limpia())
    assert any("«Historia de Scrum» no es un bloque de la lectura" in p for p in problemas)


def test_cada_tipo_trae_lo_que_necesita():
    rota = copy.deepcopy(LIMPIAS["diapositivas"])
    rota[3]["columnas"] = rota[3]["columnas"][:1]
    contenido, problemas = diapositivas._validar(con(diapositivas=rota), lectura_limpia())
    assert contenido is None and any("dos columnas" in p for p in problemas)


# ---------- Flujo: la lectura aprobada primero ----------

def test_sin_la_lectura_aprobada_no_empieza(sesion):  # noqa: F811
    assert diapositivas.faltan(sesion, 1)["otros"] == ["Aprueba primero la lectura: las diapositivas salen de ella."]
    with pytest.raises(diapositivas.NoSePuedeEmpezar):
        asyncio.run(diapositivas.generar(sesion, "scrum", 1, consulta=consulta_en_secuencia(), medir=medir_sin_desbordes))
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    assert "2. Diapositivas" in pagina and "Aprueba primero la lectura" in pagina
    boton = pagina.split("Generar diapositivas")[0].rsplit("<button", 1)[1]
    assert "disabled" in boton
    r = cliente.post("/cursos/scrum/sesiones/1/materiales/diapositivas", follow_redirects=False)
    assert "Aprueba primero la lectura" in unquote(r.headers["location"])


def test_genera_verifica_y_entrega(con_lectura):
    material, consulta = generar(con_lectura, LIMPIAS)
    assert material["estado"] == "verificada", material.get("problemas")
    rutas = diapositivas.archivos(con_lectura, 1)
    assert len(Presentation(rutas["pptx"]).slides) == 14
    redaccion = consulta.llamadas[0]["prompt"]
    assert "## Material 2 · Diapositivas" in redaccion and "LECTURA APROBADA" in redaccion
    assert "Los pilares de Scrum son tres." in redaccion         # la lectura va en el pedido
    revision_ = consulta.llamadas[1]["prompt"]
    assert diapositivas.FUENTE_LECTURA in revision_ and "no agregan contenido" in revision_
    assert "[Diapositivas de «Pilares de Scrum»]" in revision_
    entrega = {s["clave"]: s["lineas"] for s in material["entrega"]["secciones"]}
    assert entrega["archivos"][0].startswith("S1_Diapositivas.pptx: las diapositivas, 16:9, 14 diapositivas")
    assert any("Medí con PowerPoint cada texto de las 14 diapositivas: ninguno se sale" in l for l in entrega["probe"])
    assert any("contra la lectura aprobada" in l for l in entrega["valide"])
    assert rutas["entrega"].read_text(encoding="utf-8").endswith("¿Apruebas este material para pasar a la siguiente etapa?\n")
    assert material["lectura_fecha"] == lectura.estado(con_lectura, 1)["fecha"]


def test_un_desborde_se_corrige_con_las_diapositivas_completas(con_lectura):
    medidas = []

    def medir(ruta, carpeta):
        medidas.append(ruta)
        if len(medidas) == 1:
            return office.Medicion(14, [office.Desborde(8, "Los pilares de Scrum son tres.", 1.4)], [])
        return medir_sin_desbordes(ruta, carpeta)

    corregidas = {"diapositivas": LIMPIAS, "explicaciones": [], "datos_nuevos": []}
    material, consulta = generar(con_lectura, LIMPIAS, corregidas, medir=medir)
    assert material["estado"] == "verificada"
    correccion = consulta.llamadas[1]["prompt"]
    assert "FALLA · desborde" in correccion and "Diapositiva 8 («Pilares de Scrum»)" in correccion
    assert "sobran 1.4 cm" in correccion
    assert consulta.llamadas[1]["options"].output_format["schema"] == diapositivas.ESQUEMA_CORRECCION
    hoja = openpyxl.load_workbook(diapositivas.archivos(con_lectura, 1)["excel"])["Hallazgos"]
    reglas = [(f[3].value, f[5].value) for f in hoja.iter_rows(min_row=2)]
    assert any(r == "desborde" and "Resuelto" in (c or "") for r, c in reglas)


def test_menos_de_14_diapositivas_se_corrige(con_lectura):
    cortas = con(diapositivas=LIMPIAS["diapositivas"][:9])
    material, consulta = generar(con_lectura, cortas, {"diapositivas": LIMPIAS, "explicaciones": [], "datos_nuevos": []})
    assert material["estado"] == "verificada"
    assert "deben ser de 14 a 18" in consulta.llamadas[1]["prompt"]


def test_lo_que_no_esta_en_la_lectura_se_corrige_sin_tocar_el_orden(con_lectura):
    inventada = "Scrum nació en Japón en 1986."
    datos = copy.deepcopy(LIMPIAS)
    datos["diapositivas"][5]["frases"].append(inventada)
    revision_con_error = revision(error(inventada, "dato inventado", bloque=f"Diapositivas de «{PILARES}»"))
    cambios = {"cambios": [{"oracion": inventada, "nueva": ""}], "explicaciones": [], "datos_nuevos": []}
    material, consulta = generar(con_lectura, datos, revision_con_error, cambios)
    assert material["estado"] == "verificada" and material["revision"]["corregidos"] == 1
    final = comun.leer_json(diapositivas.archivos(con_lectura, 1)["contenido"])
    assert inventada not in str(final)
    assert [d["bloque"] for d in final["diapositivas"]] == [d["bloque"] for d in LIMPIAS["diapositivas"]]


def test_una_correccion_por_frases_no_cambia_el_bloque_ni_el_tipo():
    datos, no_encontradas = comun.aplicar_cambios(
        LIMPIAS, [{"oracion": "Pilares de Scrum", "nueva": "Otra cosa"}], diapositivas.CAMPOS_QUE_NO_SE_CORRIGEN)
    assert not no_encontradas
    assert [d["bloque"] for d in datos["diapositivas"]] == [d["bloque"] for d in LIMPIAS["diapositivas"]]
    assert datos["diapositivas"][5]["titulo"] == "Otra cosa"


def test_si_la_lectura_se_genera_de_nuevo_quedan_desactualizadas(con_lectura):
    generar(con_lectura, LIMPIAS)
    assert not diapositivas.estado(con_lectura, 1).get("desactualizado")
    lectura._actualizar(con_lectura, 1, fecha="2099-01-01T00:00:00")
    assert diapositivas.estado(con_lectura, 1)["desactualizado"] is True
    with pytest.raises(diapositivas.NoSePuedeAprobar):
        diapositivas.aprobar(con_lectura, 1)
    assert "Desactualizadas: la lectura o las fichas cambiaron." in cliente.get("/cursos/scrum/sesiones/1").text


def test_se_aprueban_desde_la_pagina(con_lectura):
    generar(con_lectura, LIMPIAS)
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    assert "Aprobar las diapositivas" in pagina and "S1_Diapositivas.pptx" in pagina
    r = cliente.post("/cursos/scrum/sesiones/1/materiales/diapositivas/aprobar", follow_redirects=False)
    assert "Diapositivas aprobadas." in unquote(r.headers["location"])
    assert diapositivas.estado(con_lectura, 1)["estado"] == "aprobada"
    assert "Aprobadas por ti el" in cliente.get("/cursos/scrum/sesiones/1").text


def test_detener_y_material_desconocido(con_lectura):
    r = cliente.post("/cursos/scrum/sesiones/1/materiales/diapositivas/detener", follow_redirects=False)
    assert "Las diapositivas no estaban trabajando." in unquote(r.headers["location"])
    assert cliente.post("/cursos/scrum/sesiones/1/materiales/otro").status_code == 404


def test_revisor_independiente_deja_pendientes_y_se_pueden_aprobar(con_lectura):
    from tests.unidad.test_revisor import hallazgo
    generar(con_lectura, LIMPIAS)
    frase = "El equipo muestra su tablero a todos."
    consulta = consulta_en_secuencia({"hallazgos": [hallazgo(frase)], "bloques": [], "lista": []})
    material = asyncio.run(diapositivas.revisar_con_revisor(con_lectura, "scrum", 1, consulta=consulta))
    assert material["estado"] == "con pendientes" and material["revisor"]["hallazgos"] == 1
    assert "nombre_material" not in consulta.llamadas[0]["prompt"] and "Diapositivas" in consulta.llamadas[0]["prompt"]
    pendientes = next(s["lineas"] for s in material["entrega"]["secciones"] if s["clave"] == "pendientes")
    assert any(frase in l for l in pendientes)
    diapositivas.aprobar(con_lectura, 1)
    assert diapositivas.estado(con_lectura, 1)["estado"] == "aprobada"
