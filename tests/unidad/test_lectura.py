"""Etapa 5a: la lectura en Word con la identidad visual, sin fallas del verificador."""

import asyncio
import copy
import re
import zipfile

import openpyxl
import pytest
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt
from fastapi.testclient import TestClient

from app import servidor, skill
from app.fichas import almacen, flujo
from app.materiales import docx as generador
from app.materiales import estilo, lectura
from app.materiales.contenido import Lectura
from tests.conftest import consulta_en_secuencia, consulta_simulada, pasada, segunda
from tests.fixtures import fichas as datos
from tests.unidad.test_fichas import con_fuente

LIMPIA = {
    "idea_central": ["Scrum ayuda a un equipo a trabajar con lo que observa.", "Tres pilares sostienen ese trabajo."],
    "bloques": [
        {"subtitulo": "El Manifiesto Ágil", "parrafos": ["El Manifiesto Ágil tiene cuatro aspectos."],
         "ejemplo": {"titulo": "Ejemplo", "parrafos": ["Una tienda conversa con sus clientes cada semana."]},
         "tabla": {"titulo": "Aspectos", "encabezados": ["Aspecto", "Qué valora más"],
                   "filas": [["Primero", "Las personas"], ["Segundo", "El producto que funciona"]]}},
        {"subtitulo": "Pilares de Scrum", "parrafos": ["Los pilares de Scrum son tres."],
         "ejemplo": {"titulo": "Ejemplo", "parrafos": ["El equipo muestra su tablero a todos."]}, "tabla": None},
    ],
    "aplicalo": {"parrafos": ["Usa estas dos preguntas al cerrar cada semana."],
                 "plantilla": ["Qué observamos esta semana.", "Qué cambiamos la próxima semana."]},
    "cuidado": ["Revisar el avance sin cambiar nada después."],
    "pasajes": [{"fuente": "silabo.pdf", "ubicacion": "página 1", "texto": "Scrum Master con IA"}],
    "decisiones": ["Usé una tienda como ejemplo."],
    "agrupacion": "",
}


def con_error(oracion: str) -> dict:
    contenido = copy.deepcopy(LIMPIA)
    contenido["bloques"][1]["parrafos"].append(oracion)
    return contenido


def cambios(*pares, explicaciones=None, datos_nuevos=None):
    """Respuesta simulada de una corrección por oraciones."""
    return {"cambios": [{"oracion": a, "nueva": b} for a, b in pares],
            "explicaciones": explicaciones or [], "datos_nuevos": datos_nuevos or []}


def una_pagina(_ruta):
    return 2


@pytest.fixture
def sesion(entorno):
    """Curso con una fuente y las dos fichas confirmadas."""
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    carpeta = entorno["cursos"] / "scrum"
    (carpeta / "fuentes").mkdir(parents=True)
    (carpeta / "curso.json").write_text('{"nombre": "Scrum"}', encoding="utf-8")
    con_fuente(carpeta)
    almacen.guardar(carpeta, "curso", None, datos.ficha("curso", datos.CURSO))
    flujo.confirmar_curso(carpeta)
    almacen.guardar(carpeta, "sesion", 1, datos.ficha("sesion", datos.SESION))
    revisor = consulta_simulada(structured_output={"ejercicios": [
        {"numero": n, "funciona_solo": True, "sin_llenar_a_mano": True, "motivo": "Cumple"} for n in (1, 2, 3)]})
    asyncio.run(flujo.confirmar_sesion(carpeta, "scrum", 1, consulta=revisor))
    return carpeta


def generar(sesion, *salidas, contar_paginas=una_pagina):
    consulta = consulta_en_secuencia(*salidas)
    material = asyncio.run(lectura.generar(sesion, "scrum", 1, consulta=consulta, contar_paginas=contar_paginas))
    return material, consulta


# ---------- Word con el diseño de la skill ----------

@pytest.fixture
def word(tmp_path):
    identidad = estilo.Identidad(**estilo.PALETA_SOBRIA, tipografia="Calibri", logo=None)
    ruta = generador.generar_lectura(Lectura.model_validate(LIMPIA), identidad,
                                     generador.Portada("Scrum Master con IA", "Sesión 1 · Fundamentos", "Lectura"),
                                     tmp_path / "S1_Lectura.docx")
    return ruta, identidad


def test_pagina_a4_margenes_y_cuerpo_de_la_skill(word):
    documento = Document(word[0])
    seccion = documento.sections[0]
    assert (round(seccion.page_width.cm, 1), round(seccion.page_height.cm, 1)) == (21.0, 29.7)
    assert all(abs(getattr(seccion, m) - Cm(2.5)) < Cm(0.01) for m in ("left_margin", "right_margin", "top_margin", "bottom_margin"))
    normal = documento.styles["Normal"]
    assert normal.font.size == Pt(11)
    assert normal.paragraph_format.line_spacing == 1.15
    assert normal.paragraph_format.space_after == Pt(6)
    assert normal.font.name == "Calibri"


def test_portada_encabezado_pie_y_titulos_reales(word):
    documento = Document(word[0])
    textos = [p.text for p in documento.paragraphs]
    assert textos.index("Scrum Master con IA") < textos.index("Sesión 1 · Fundamentos") < textos.index("Lectura")
    seccion = documento.sections[0]
    assert seccion.different_first_page_header_footer is True
    assert seccion.header.paragraphs[0].text == "Scrum Master con IA"
    assert 'w:instr="PAGE"' in seccion.footer._element.xml
    titulos = [p.text for p in documento.paragraphs if p.style.name == "Heading 1"]
    assert titulos == ["Idea central", "El Manifiesto Ágil", "Pilares de Scrum"]


def test_sin_texto_justificado(word):
    documento = Document(word[0])
    assert all(p.alignment != WD_ALIGN_PARAGRAPH.JUSTIFY for p in documento.paragraphs)


def test_recuadros_con_borde_izquierdo_y_tablas_sin_bordes_verticales(word):
    xml = zipfile.ZipFile(word[0]).read("word/document.xml").decode("utf-8")
    tablas = re.findall(r"<w:tbl>.*?</w:tbl>", xml, re.S)
    recuadros = [t for t in tablas if re.search(r'<w:left w:val="single" w:sz="24"', t)]
    assert len(recuadros) == 4  # dos ejemplos, «Aplícalo así» y «Cuidado con»
    datos_tabla = [t for t in tablas if t not in recuadros]
    assert len(datos_tabla) == 1
    for lado in ("left", "right", "insideV"):
        assert f'<w:{lado} w:val="nil"/>' in datos_tabla[0]
    assert f'w:fill="{estilo.PALETA_SOBRIA["principal"]}"' in datos_tabla[0]
    assert f'w:fill="{estilo.GRIS_FILA_ALTERNA}"' in datos_tabla[0]
    cuidado = next(t for t in recuadros if "Cuidado con" in t)
    assert f'w:color="{estilo.PALETA_SOBRIA["advertencia"]}"' in cuidado


def test_diseno_uniforme_solo_usa_los_colores_de_la_identidad(word):
    """Colores del texto, los títulos, los recuadros y las tablas: solo los de la identidad."""
    ruta, identidad = word
    archivo = zipfile.ZipFile(ruta)
    partes = [n for n in archivo.namelist() if re.match(r"word/(document|header\d*|footer\d*)\.xml$", n)]
    xml = "".join(archivo.read(n).decode("utf-8") for n in partes)
    usados = set(re.findall(r'w:(?:fill|color|val)="([0-9A-Fa-f]{6})"', xml))
    documento = Document(ruta)
    for nombre in ("Normal", "Title", "Heading 1", "Heading 2", "Heading 3"):
        usados.add(str(documento.styles[nombre].font.color.rgb))
    assert usados and usados <= identidad.colores_permitidos()


def test_un_color_claro_se_oscurece_solo_como_texto():
    claro = "F6C343"
    assert estilo.contraste(claro) < 4.5
    oscuro = estilo.para_texto(claro)
    assert estilo.contraste(oscuro) >= 4.5 and oscuro != claro
    assert estilo.para_texto("0F4C5C") == "0F4C5C"


def test_identidad_desde_la_ficha(sesion):
    identidad = estilo.desde_ficha(sesion)
    assert identidad.principal == estilo.PALETA_SOBRIA["principal"]
    assert any("no trae paleta" in a for a in identidad.avisos)
    assert any("sin logo" in a for a in identidad.avisos)
    ficha = almacen.cargar(sesion, "curso")
    almacen.aplicar_formulario(ficha, {"visual.principal": "Azul #1A4D8F", "visual.logo": "logo.png"})
    almacen.guardar(sesion, "curso", None, ficha)
    (sesion / "fuentes" / "logo.png").write_bytes(b"\x89PNG")
    identidad = estilo.desde_ficha(sesion)
    assert identidad.principal == "1A4D8F"
    assert identidad.logo == sesion / "fuentes" / "logo.png"
    assert not any("paleta" in a for a in identidad.avisos)


def test_el_redactor_recibe_las_secciones_de_la_skill_sin_el_claude_md():
    texto = skill.secciones("Reglas comunes", "Material 1 · Lectura")
    assert texto.startswith("## Reglas comunes") and "## Material 1 · Lectura" in texto
    assert "## Material 2" not in texto
    with pytest.raises(KeyError):
        skill.secciones("No existe")


# ---------- Flujo: redactar, generar, verificar y corregir ----------

def test_sin_fichas_confirmadas_no_empieza(entorno):
    carpeta = entorno["cursos"] / "x"
    (carpeta / "fuentes").mkdir(parents=True)
    with pytest.raises(lectura.NoSePuedeEmpezar):
        asyncio.run(lectura.generar(carpeta, "x", 1, consulta=consulta_en_secuencia()))


def test_lectura_limpia_queda_verificada_en_una_vuelta(sesion):
    material, consulta = generar(sesion, LIMPIA, pasada(), segunda())
    rutas = lectura.archivos(sesion, 1)
    assert material["estado"] == "verificada"
    assert material["resumen"].endswith("Fallas: 0 · Avisos: 0")
    assert rutas["word"].exists() and rutas["excel"].exists()
    assert len(consulta.llamadas) == 3
    opciones = consulta.llamadas[0]["options"]
    assert opciones.model == "claude-opus-5-5" and opciones.tools == ["Read", "Grep", "Glob"]
    assert "## Material 1 · Lectura" in consulta.llamadas[0]["prompt"]
    assert "FICHA DE LA SESIÓN" in consulta.llamadas[0]["prompt"]
    assert material["decisiones"] == ["Usé una tienda como ejemplo."]


def test_una_falla_se_corrige_y_se_verifica_de_nuevo(sesion):
    material, consulta = generar(sesion, con_error("Lee este bloque en 10 minutos."),
                                 cambios(("Lee este bloque en 10 minutos.", "")), pasada(), segunda())
    assert material["estado"] == "verificada"
    assert len(consulta.llamadas) == 4
    assert material["correcciones"] == {"verificador": 1, "primera pasada": 0, "segunda pasada": 0}
    correccion = consulta.llamadas[1]["options"]
    assert (correccion.model, correccion.max_budget_usd, correccion.effort) == ("claude-sonnet-5-5", 0.60, "medium")
    contenido = lectura.archivos(sesion, 1)["contenido"].read_text(encoding="utf-8")
    assert "10 minutos" not in contenido
    pedido = consulta.llamadas[1]["prompt"]
    assert pedido.startswith("REGLAS DE LA SKILL")  # la parte fija va primero
    assert pedido.rstrip().endswith("FALLA · tiempo · «Lee este bloque en 10 minutos.»: dice «minutos»")


def test_un_aviso_explicado_queda_anotado_en_el_excel(sesion):
    oracion = "Algunas tiendas revisan su tablero cada día."
    material, consulta = generar(sesion, con_error(oracion), pasada(), segunda(), cambios(explicaciones=[
        {"regla": "palabra imprecisa", "oracion": oracion, "explicacion": "El caso no dice cuántas tiendas."}]))
    assert len(consulta.llamadas) == 4  # el aviso va en la corrección de la pasada: no gasta una vuelta propia
    assert material["estado"] == "verificada"
    hoja = openpyxl.load_workbook(lectura.archivos(sesion, 1)["excel"])["Hallazgos"]
    filas = [[c.value for c in f] for f in hoja.iter_rows(min_row=2)]
    assert filas[0] == ["AVISO", "S1_Lectura.docx · Pilares de Scrum", oracion, "palabra imprecisa", "algunas",
                        "El caso no dice cuántas tiendas."]
    assert filas[1][-1] == "Enviado a corrección en la vuelta 1. Resuelto."  # el historial de la vuelta 1


def test_mas_de_seis_paginas_es_falla_y_se_pide_acortar(sesion):
    paginas = iter([7, 5])
    material, consulta = generar(sesion, LIMPIA, {"lectura": LIMPIA, "explicaciones": [], "datos_nuevos": []},
                                 pasada(), segunda(), contar_paginas=lambda _: next(paginas))
    assert "FALLA · páginas · S1_Lectura.docx: tiene 7 páginas; el máximo es 6" in consulta.llamadas[1]["prompt"]
    assert material["estado"] == "verificada"


def test_una_estructura_invalida_se_pide_corregir(sesion):
    sin_bloques = copy.deepcopy(LIMPIA)
    sin_bloques["bloques"] = sin_bloques["bloques"][:1]
    material, consulta = generar(sesion, sin_bloques, {"lectura": LIMPIA, "explicaciones": [], "datos_nuevos": []}, pasada(), segunda())
    assert "FALLA · estructura · bloques" in consulta.llamadas[1]["prompt"]
    assert material["estado"] == "verificada"


def test_despues_del_tope_de_correcciones_queda_con_fallas(sesion):
    mala = con_error("Lee este bloque en 10 minutos.")
    respuesta = cambios()
    material, consulta = generar(sesion, mala, *[respuesta] * lectura.MAX_CORRECCIONES)
    assert material["estado"] == "con fallas"
    assert len(consulta.llamadas) == 1 + lectura.MAX_CORRECCIONES
    assert material["problemas"] == ["FALLA · tiempo · «Lee este bloque en 10 minutos.»: dice «minutos»"]


def test_cada_llamada_queda_en_el_registro_de_tokens(sesion):
    from app import tokens
    generar(sesion, con_error("Lee este bloque en 10 minutos."), cambios(("Lee este bloque en 10 minutos.", "")),
            pasada(), segunda())
    lineas = (sesion / "tokens.jsonl").read_text(encoding="utf-8").splitlines()
    etapas = [__import__("json").loads(l)["etapa"] for l in lineas]
    assert etapas[-4:] == ["redacción", "corrección 1", "primera pasada", "segunda pasada"]
    assert tokens.total("scrum")["llamadas"] >= 2


def test_el_word_real_cuenta_sus_paginas_con_word(sesion):
    material, _ = generar(sesion, LIMPIA, pasada(), segunda(), contar_paginas=None)
    assert material["estado"] == "verificada"


# ---------- Página de la sesión ----------

cliente = TestClient(servidor.app)


def test_la_pagina_de_la_sesion_genera_y_permite_descargar(sesion, monkeypatch):
    llamadas = []
    original = lectura.generar

    async def generar_simulado(carpeta, curso, numero):
        llamadas.append(numero)
        return await original(carpeta, curso, numero, consulta=consulta_en_secuencia(LIMPIA, pasada(), segunda()), contar_paginas=una_pagina)

    monkeypatch.setattr(lectura, "generar", generar_simulado)
    r = cliente.post("/cursos/scrum/sesiones/1/materiales/lectura", follow_redirects=False)
    assert r.status_code == 303
    servidor_hilos = [h for h in __import__("threading").enumerate() if h.daemon]
    for hilo in servidor_hilos:
        hilo.join(timeout=60)
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    assert "Verificada" in pagina and "S1_Lectura.docx" in pagina
    descarga = cliente.get("/cursos/scrum/sesiones/1/descargar/S1_Lectura.docx")
    assert descarga.status_code == 200 and descarga.content[:2] == b"PK"
    assert cliente.get("/cursos/scrum/sesiones/1/descargar/..%5C..%5Cficha_del_curso.json").status_code == 404
    assert llamadas == [1]


def test_sin_fichas_el_boton_esta_desactivado(entorno):
    cliente.post("/cursos", data={"nombre": "Otro"})
    carpeta = entorno["cursos"] / "otro"
    almacen.guardar(carpeta, "curso", None, datos.ficha("curso", datos.CURSO))
    flujo.confirmar_curso(carpeta)
    pagina = cliente.get("/cursos/otro/sesiones/1").text
    assert "falta confirmar las fichas" in pagina
    assert re.search(r"<button type=\"submit\"\s+disabled>", pagina)


def test_una_configuracion_rota_se_detecta_antes_de_gastar_tokens(sesion):
    (sesion / "fuentes_texto" / "silabo.pdf.jsonl").unlink()
    consulta = consulta_en_secuencia(LIMPIA)
    with pytest.raises(Exception, match="No existe el texto"):
        asyncio.run(lectura.generar(sesion, "scrum", 1, consulta=consulta, contar_paginas=una_pagina))
    assert consulta.llamadas == []
    assert lectura.estado(sesion, 1)["estado"] == "error"


def test_un_aviso_explicado_con_la_oracion_copiada_con_diferencias_no_vuelve(sesion):
    oracion = "Algunas tiendas revisan su tablero cada día."
    material, consulta = generar(sesion, con_error(oracion), pasada(), segunda(), cambios(explicaciones=[
        {"regla": "Palabra imprecisa", "oracion": "«algunas tiendas revisan su tablero cada dia»",
         "explicacion": "El caso no dice cuántas tiendas."}]))
    assert material["estado"] == "verificada"
    assert len(consulta.llamadas) == 4  # redacción, las dos pasadas juntas y una corrección
    hoja = openpyxl.load_workbook(lectura.archivos(sesion, 1)["excel"])["Hallazgos"]
    assert hoja["F2"].value == "El caso no dice cuántas tiendas."


# ---------- Corrección por oraciones ----------

def test_aplicar_cambios_reemplaza_y_elimina_dentro_de_los_parrafos():
    datos = copy.deepcopy(LIMPIA)
    datos["bloques"][0]["parrafos"] = ["Primera oración. Segunda oración.", "Sola."]
    nuevo, no_encontradas = lectura.aplicar_cambios(datos, [
        {"oracion": "Segunda oración.", "nueva": "Segunda corregida."},
        {"oracion": "Sola.", "nueva": ""},
        {"oracion": "Primero", "nueva": "Encabezado"},
        {"oracion": "No existe.", "nueva": "x"},
    ])
    assert nuevo["bloques"][0]["parrafos"] == ["Primera oración. Segunda corregida."]
    assert nuevo["bloques"][0]["tabla"]["filas"][0][0] == "Encabezado"
    assert no_encontradas == ["No existe."]
    assert datos["bloques"][0]["parrafos"] == ["Primera oración. Segunda oración.", "Sola."]  # no cambia el original


def test_borrar_una_celda_no_descuadra_la_tabla_ni_toca_los_pasajes():
    datos = copy.deepcopy(LIMPIA)
    datos["pasajes"][0]["texto"] = "Las personas"
    nuevo, _ = lectura.aplicar_cambios(datos, [{"oracion": "Las personas", "nueva": ""}])
    assert nuevo["bloques"][0]["tabla"]["filas"][0] == ["Primero", ""]
    assert nuevo["pasajes"][0]["texto"] == "Las personas"


def test_un_problema_del_documento_entero_pide_la_correccion_completa(sesion):
    paginas = iter([7, 5])
    material, consulta = generar(sesion, LIMPIA, {"lectura": LIMPIA, "explicaciones": [], "datos_nuevos": []},
                                 pasada(), segunda(), contar_paginas=lambda _: next(paginas))
    assert consulta.llamadas[1]["options"].model == "claude-opus-5-5"
    assert material["estado"] == "verificada"



def test_la_explicacion_vale_aunque_la_regla_venga_con_su_nivel():
    from app.validacion import verificador
    oracion = 'Si se aplican solo algunas partes, "el resultado final no es Scrum".'
    explicaciones = {verificador.clave_de_hallazgo("AVISO · palabra imprecisa", oracion): "Viene de la fuente."}
    assert verificador.buscar_explicacion("palabra imprecisa", oracion, explicaciones) == "Viene de la fuente."
    assert verificador.buscar_explicacion("oración larga", oracion, explicaciones) is None



# ---------- Segunda pasada dentro de la lectura ----------

def test_un_defecto_de_la_segunda_pasada_se_corrige_y_llena_su_hoja(sesion):
    relleno = "Los pilares de Scrum son tres."
    defecto = {"tipo": "relleno", "bloque": "Pilares de Scrum", "oracion": relleno,
               "detalle": "Repite lo que dice el título."}
    material, consulta = generar(sesion, LIMPIA, pasada(), segunda(defectos=[defecto]),
                                 cambios((relleno, "Los pilares sostienen el trabajo del equipo.")), pasada(), segunda())
    assert material["estado"] == "verificada"
    assert material["correcciones"]["segunda pasada"] == 1
    assert "SEGUNDA PASADA · relleno · «Los pilares de Scrum son tres.»" in consulta.llamadas[3]["prompt"]
    assert consulta.llamadas[5]["prompt"].rstrip().endswith("BLOQUES A REVISAR: [Pilares de Scrum]")  # solo el bloque que cambió
    assert consulta.llamadas[2]["options"].effort == "high"     # primera revisión de la lectura completa
    assert consulta.llamadas[5]["options"].effort == "medium"   # revisión de un bloque cambiado
    libro = openpyxl.load_workbook(lectura.archivos(sesion, 1)["excel"])
    filas = list(libro["Segunda pasada"].iter_rows(min_row=2, values_only=True))
    assert [f[0] for f in filas] == ["Idea central", "El Manifiesto Ágil", "Pilares de Scrum", "Aplícalo así", "Cuidado con"]
    assert all(f[1] and f[2] and f[3] and f[4] for f in filas)
    historial = [f for f in libro["Hallazgos"].iter_rows(min_row=2, values_only=True)]
    assert historial[0][3] == "segunda pasada: relleno"


def test_un_defecto_que_cita_una_oracion_inexistente_se_descarta(sesion):
    inventado = {"tipo": "vacío", "bloque": "Pilares de Scrum", "oracion": "Esta oración no está.", "detalle": "x"}
    material, consulta = generar(sesion, LIMPIA, pasada(), segunda(defectos=[inventado]))
    assert material["estado"] == "verificada"
    assert len(consulta.llamadas) == 3


def test_un_punto_de_la_lista_de_verificacion_sin_cumplir_se_corrige(sesion):
    punto = {"pregunta": "¿Hay contenido de sesiones posteriores?", "respuesta": "no", "detalle": "Menciona los roles."}
    material, consulta = generar(sesion, LIMPIA, pasada(), segunda(lista_no=[punto]), cambios(), segunda())
    assert "LISTA DE VERIFICACIÓN · ¿Hay contenido de sesiones posteriores?: Menciona los roles." in consulta.llamadas[3]["prompt"]
    assert material["estado"] == "verificada"


def test_la_segunda_pasada_recibe_las_posibles_inconsistencias(sesion):
    doble = copy.deepcopy(LIMPIA)
    doble["bloques"][0]["parrafos"].append("El Sprint dura dos semanas.")
    doble["bloques"][1]["parrafos"].append("El Sprint dura tres semanas.")
    _, consulta = generar(sesion, doble, pasada(), segunda())
    pedido = consulta.llamadas[2]["prompt"]
    assert "- semanas: «dos semanas» en:" in pedido and "«tres semanas» en:" in pedido



def test_desde_la_tercera_vuelta_la_veracidad_pide_copiar_o_eliminar(sesion):
    mala = "El Manifiesto Ágil tiene cinco aspectos."
    datos = con_error(mala)
    falla = pasada({mala: {"tipo": "norma", "veredicto": "sin fuente", "pasaje": ""}})
    material, consulta = generar(sesion, datos, falla, segunda(), cambios(), falla, cambios(), falla,
                                 cambios((mala, "")), segunda())
    assert lectura.ULTIMO_INTENTO not in consulta.llamadas[3]["prompt"]
    assert lectura.ULTIMO_INTENTO in consulta.llamadas[7]["prompt"]
    assert material["estado"] == "verificada"


def test_al_llegar_al_tope_el_programa_elimina_lo_que_sigue_sin_coincidir(sesion):
    mala = "El Manifiesto Ágil tiene cinco aspectos."
    falla = pasada({mala: {"tipo": "norma", "veredicto": "sin fuente", "pasaje": ""}})
    secuencia = [con_error(mala), falla, segunda()]
    for _ in range(lectura.MAX_CORRECCIONES):
        secuencia += [cambios(), falla]
    material, consulta = generar(sesion, *secuencia)
    assert len(consulta.llamadas) == len(secuencia)   # después del cierre no hay otra segunda pasada
    assert material["estado"] == "verificada"
    assert material["eliminadas_por_el_programa"] == [mala]
    assert mala not in lectura.archivos(sesion, 1)["contenido"].read_text(encoding="utf-8")
    hoja = openpyxl.load_workbook(lectura.archivos(sesion, 1)["excel"])["Hallazgos"]
    assert "cierre por programa" in [f[3] for f in hoja.iter_rows(min_row=2, values_only=True)]


def test_un_vacio_al_llegar_al_tope_queda_como_decision_pendiente(sesion):
    vacio = {"tipo": "vacío", "bloque": "Pilares de Scrum", "oracion": "Los pilares de Scrum son tres.",
             "detalle": "No dice cuáles son."}
    secuencia = [LIMPIA, pasada(), segunda(defectos=[vacio])]
    for _ in range(lectura.MAX_CORRECCIONES):
        secuencia += [cambios(), segunda(defectos=[vacio])]
    material, _ = generar(sesion, *secuencia)
    assert material["estado"] == "con fallas"
    assert material["problemas"] == ["SEGUNDA PASADA · vacío · «Los pilares de Scrum son tres.»: No dice cuáles son."]
    assert material["eliminadas_por_el_programa"] == []


def test_un_aviso_en_una_oracion_literal_de_la_fuente_lo_explica_el_programa(sesion):
    # «Scrum Master con IA» está tal cual en el sílabo de prueba; con «algunas» antes, sería un aviso.
    from app.validacion.pasajes import Corpus, Fuente
    from app.validacion import verificador
    literal = "Algunas veces se usa el nombre completo del curso en la portada de cada material."
    corpus = Corpus([Fuente("norma.pdf", [{"texto": literal, "ubicacion": "página 3"}])])
    hallazgo = verificador.verificar.Hallazgo("AVISO", "S1_Lectura.docx · x", literal, "palabra imprecisa", "algunas")
    resultado = verificador.verificar.Resultado(hallazgos=[hallazgo])
    explicaciones = {}
    assert lectura._explicar_literales(resultado, explicaciones, corpus) is True
    assert "pasaje literal de la fuente (norma.pdf, página 3)" in verificador.buscar_explicacion(
        "palabra imprecisa", literal, explicaciones)


def test_un_vacio_que_el_cierre_no_puede_borrar_sigue_pendiente(sesion):
    mala = "El Manifiesto Ágil tiene cinco aspectos."
    vacio = {"tipo": "vacío", "bloque": "Pilares de Scrum", "oracion": "Los pilares de Scrum son tres.", "detalle": "No dice cuáles."}
    falla = pasada({mala: {"tipo": "norma", "veredicto": "sin fuente", "pasaje": ""}})
    secuencia = [con_error(mala), falla, segunda(defectos=[vacio])]
    for _ in range(lectura.MAX_CORRECCIONES):
        secuencia += [cambios(), falla, segunda(defectos=[vacio])]
    material, _ = generar(sesion, *secuencia)
    assert material["eliminadas_por_el_programa"] == [mala]
    assert material["estado"] == "con fallas"
    assert material["problemas"] == ["SEGUNDA PASADA · vacío · «Los pilares de Scrum son tres.»: No dice cuáles."]
