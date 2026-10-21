"""Actividad web, fase 8a: el contenido como datos, sus revisiones sin IA y su vista (PLAN.md §0, decisión 57)."""

import asyncio
import copy
import json

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app import servidor
from app.fichas import almacen, controles
from app.materiales import actividad, comun, estilo, lectura
from app.materiales.contenido import Actividad
from tests.conftest import consulta_en_secuencia
from app.materiales.contenido import repartir
from tests.sembrados.actividad import CASOS, LIMPIA, PESOS_LIMPIOS, PUNTAJE_LIMPIO, PUNTOS_LIMPIOS
from tests.unidad.test_lectura import LIMPIA as LECTURA_LIMPIA
from tests.unidad.test_lectura import SIN_ERRORES, cambios, error, revision, sesion  # noqa: F401

cliente = TestClient(servidor.app)


def lectura_aprobada(carpeta, numero=1):
    lectura.archivos(carpeta, numero)["contenido"].parent.mkdir(parents=True, exist_ok=True)
    comun.guardar_json(lectura.archivos(carpeta, numero)["contenido"], LECTURA_LIMPIA)
    comun.actualizar(carpeta, numero, lectura.CLAVE, estado="aprobada", aprobada="2026-10-21T10:00:00")


def generar(carpeta, *salidas, revisar=True, disenar=False):
    """revisar=True agrega al final la revisión del contenido sin errores (fase 8b). Si quedan fallas del
    verificador, la revisión no corre y esa respuesta queda sin usar."""
    consulta = consulta_en_secuencia(*salidas, *([SIN_ERRORES] if revisar else []))
    material = asyncio.run(actividad.generar(carpeta, "scrum", 1, consulta=consulta, disenar=disenar))
    return material, consulta


# ---------- Revisiones del programa, sin IA ----------

def test_el_contenido_limpio_pasa_la_revision_del_programa():
    contenido, fallas = actividad._validar(copy.deepcopy(LIMPIA), ",")
    assert fallas == []
    assert contenido.puntaje_total == PUNTAJE_LIMPIO == 100
    assert contenido.puntos_finales() == PUNTOS_LIMPIOS and sum(PUNTOS_LIMPIOS) == 100


# ---------- Puntaje sobre 100 (decisión 59) ----------

@pytest.mark.parametrize("pesos, puntos", [
    (PESOS_LIMPIOS, PUNTOS_LIMPIOS),
    ([1, 1, 1], [34, 33, 33]),            # a igual resto, el punto que falta va a la primera
    ([3] * 4, [25] * 4),
    ([1, 2, 3], [17, 33, 50]),
    ([1] * 7, [15, 15, 14, 14, 14, 14, 14]),
])
def test_los_pesos_se_reparten_en_puntos_que_suman_100(pesos, puntos):
    assert repartir(pesos) == puntos


@pytest.mark.parametrize("pesos", [[1] + [3] * 31, [3] * 31 + [1], [1, 2, 3] * 10 + [2, 2], [2] * 32, [1]])
def test_el_total_es_siempre_100_y_ninguna_pregunta_queda_en_cero(pesos):
    puntos = repartir(pesos)
    assert sum(puntos) == 100 and min(puntos) >= 1
    assert all(puntos[i] <= puntos[j] for i in range(len(pesos)) for j in range(len(pesos)) if pesos[i] < pesos[j])


@pytest.mark.parametrize("ident, datos, esperado", CASOS, ids=[c[0] for c in CASOS])
def test_cada_error_sembrado_de_la_actividad_queda_marcado(ident, datos, esperado):
    _, fallas = actividad._validar(datos, ",")
    assert any(esperado in f for f in fallas), fallas
    assert all(f.startswith("FALLA") for f in fallas)


def test_describe_o_explica_en_una_pregunta_cerrada_no_es_respuesta_abierta():
    datos = copy.deepcopy(LIMPIA)
    datos["pasos"][0]["preguntas"][0]["enunciado"] = "¿Qué opción describe mejor lo que explica la lectura?"
    assert actividad._validar(datos, ",")[1] == []


def test_un_total_con_separador_de_miles_suma_bien():
    datos = copy.deepcopy(LIMPIA)
    datos["caso"]["tablas"][0]["filas"] = [["Semana 1", "S/ 1.500"], ["Semana 2", "S/ 1.060"], ["Total", "S/ 2.560"]]
    assert actividad._validar(datos, ",")[1] == []
    datos["caso"]["tablas"][0]["filas"] = [["Semana 1", "1,500"], ["Semana 2", "1,060"], ["Total", "2,560"]]
    assert actividad._validar(datos, ".")[1] == []


# ---------- Vista del contenido ----------

def test_la_vista_muestra_el_contenido_con_sus_respuestas_y_el_puntaje():
    identidad = estilo.Identidad(**estilo.PALETA_SOBRIA, tipografia="Calibri", logo=None)
    pagina = actividad.vista_html(Actividad.model_validate(LIMPIA), identidad)
    assert "<h1>Scrum en la Sucursal Norte</h1>" in pagina
    assert "<h2>Paso 1. Reconozca los pilares</h2>" in pagina
    assert "Opción única · 22 puntos" in pagina and "Clasificar · 34 puntos" in pagina
    assert "Correcta. La lectura nombra tres pilares." in pagina
    assert "Incorrecta. Faltaría un pilar: la lectura nombra tres." in pagina
    assert f"Puntaje total: {PUNTAJE_LIMPIO} puntos." in pagina and actividad.NOTA_DEL_PUNTAJE in pagina
    assert "No es la página del alumno" in pagina
    assert "<script" not in pagina   # la vista no corrige nada: solo se lee


# ---------- Lo que falta para generar ----------

def test_sin_la_lectura_aprobada_no_se_genera(sesion):  # noqa: F811
    assert actividad.faltan(sesion, 1) == {"ficha": [], "otros": ["Aprueba primero la lectura: la actividad sale de ella."]}
    with pytest.raises(actividad.NoSePuedeEmpezar):
        asyncio.run(actividad.generar(sesion, "scrum", 1, consulta=consulta_en_secuencia()))


def test_la_ficha_ofrece_la_actividad_web_entre_los_materiales():
    assert "actividad web" in controles.MATERIALES and controles.TODOS_LOS_MATERIALES == "los cinco"
    assert "actividad" in almacen.MATERIALES
    ficha = {"tipo": "sesion", "campos": {"materiales.cuales": {"valor": "lectura y actividad web"}}}
    assert almacen.materiales_de_la_sesion(ficha) == {"lectura", "actividad"}
    sin = {"tipo": "sesion", "campos": {"materiales.cuales": {"valor": "lectura y diapositivas"}}}
    assert almacen.errores_del_material(sin, "actividad") == ["«Materiales de esta sesión» no incluye actividad."]
    todos = {"tipo": "sesion", "campos": {"materiales.cuales": {"valor": "los cuatro"}}}   # ficha anterior
    assert "actividad" in almacen.materiales_de_la_sesion(todos)


# ---------- Generación ----------

def test_un_contenido_limpio_queda_verificado_con_dos_llamadas(sesion):  # noqa: F811
    lectura_aprobada(sesion)
    material, consulta = generar(sesion, copy.deepcopy(LIMPIA))
    rutas = actividad.archivos(sesion, 1)
    assert material["estado"] == "verificada", material["problemas"]
    assert material["resumen"].endswith("Fallas: 0 · Avisos: 0")
    assert (material["pasos"], material["preguntas"], material["puntaje_total"]) == (4, 5, PUNTAJE_LIMPIO)
    assert rutas["vista"].exists() and rutas["excel"].exists()
    assert json.loads(rutas["contenido"].read_text(encoding="utf-8"))["titulo"] == LIMPIA["titulo"]
    assert len(consulta.llamadas) == 2   # redacción y revisión del contenido (decisión 22)
    assert consulta.llamadas[1]["options"].model == "claude-sonnet-5-5"
    assert material["revision"] == {"bloques": 5, "errores": 0, "corregidos": 0, "pendientes": 0, "descartados": 0}
    pedido, opciones = consulta.llamadas[0]["prompt"], consulta.llamadas[0]["options"]
    assert opciones.model == "claude-opus-5-5" and opciones.tools == ["Read", "Grep", "Glob"]
    assert "## Actividad web" in pedido and "Única excepción: la actividad web lleva puntos" in pedido
    assert "LECTURA APROBADA DE LA SESIÓN" in pedido and "Los pilares de Scrum son tres." in pedido
    assert opciones.output_format["schema"]["properties"]["pasos"]["items"]["properties"]["preguntas"]
    # Los puntos de esta actividad no son falla en el Excel (decisión 57 c).
    hoja = openpyxl.load_workbook(rutas["excel"])["Hallazgos"]
    assert not [f for f in hoja.iter_rows(min_row=2, values_only=True) if f[0] == "FALLA"]
    secciones = [s["clave"] for s in material["entrega"]["secciones"]]
    assert "archivos" in secciones


def test_un_tiempo_es_falla_y_se_corrige_por_oraciones(sesion):  # noqa: F811
    lectura_aprobada(sesion)
    datos = copy.deepcopy(LIMPIA)
    datos["presentacion"].append("La actividad dura 20 minutos.")
    material, consulta = generar(sesion, datos, cambios(("La actividad dura 20 minutos.", "")))
    assert material["estado"] == "verificada"
    assert len(consulta.llamadas) == 3 and material["correcciones"] == {"verificador": 1, "revisión": 0}
    assert "«oraciones»" in consulta.llamadas[1]["prompt"]
    assert "20 minutos" not in actividad.archivos(sesion, 1)["contenido"].read_text(encoding="utf-8")


def test_una_pregunta_con_dos_correctas_se_corrige_completa(sesion):  # noqa: F811
    lectura_aprobada(sesion)
    roto = copy.deepcopy(LIMPIA)
    roto["pasos"][0]["preguntas"][0]["opciones"][1]["correcta"] = True
    corregida = {"actividad": copy.deepcopy(LIMPIA), "explicaciones": [], "datos_nuevos": []}
    material, consulta = generar(sesion, roto, corregida)
    assert material["estado"] == "verificada"
    pedido = consulta.llamadas[1]["prompt"]
    assert "Llena solo «completa»" in pedido and "tiene 2 opciones correctas" in pedido


def test_si_las_fallas_siguen_no_se_puede_aprobar(sesion):  # noqa: F811
    lectura_aprobada(sesion)
    roto = copy.deepcopy(LIMPIA)
    roto["pasos"][0]["preguntas"][0]["opciones"][1]["correcta"] = True
    sigue = {"actividad": roto, "explicaciones": [], "datos_nuevos": []}
    material, consulta = generar(sesion, roto, *[copy.deepcopy(sigue) for _ in range(actividad.VUELTAS_DEL_VERIFICADOR)],
                                 revisar=False)
    assert len(consulta.llamadas) == 1 + actividad.VUELTAS_DEL_VERIFICADOR   # con fallas, la revisión no corre
    assert material["estado"] == "con fallas"
    with pytest.raises(actividad.NoSePuedeAprobar):
        actividad.aprobar(sesion, 1)


def test_una_afirmacion_sin_fuente_queda_pendiente_y_se_puede_aprobar(sesion):  # noqa: F811
    lectura_aprobada(sesion)
    datos = copy.deepcopy(LIMPIA)
    datos["decisiones"].append({"texto": "El foco evita dispersarse.", "tipo": "sin fuente"})
    material, _ = generar(sesion, datos)
    assert material["estado"] == "con pendientes"
    assert "Afirmación sin fuente: El foco evita dispersarse." in material["problemas"]
    assert actividad.aprobar(sesion, 1)["estado"] == "aprobada"


# ---------- Página ----------

def test_la_pagina_de_la_actividad_genera_y_abre_la_vista_en_el_navegador(sesion):  # noqa: F811
    lectura_aprobada(sesion)
    generar(sesion, copy.deepcopy(LIMPIA))
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/actividad").text
    assert "<h1 id=\"t-actividad\">Actividad web</h1>" in pagina
    assert "S1_Actividad_Contenido.html" in pagina and "Aprobar la actividad web" in pagina
    assert "Pedir revisor independiente" in pagina
    respuesta = cliente.get("/cursos/scrum/sesiones/1/descargar/S1_Actividad_Contenido.html")
    assert respuesta.status_code == 200 and respuesta.headers["content-disposition"].startswith("inline")
    excel = cliente.get("/cursos/scrum/sesiones/1/descargar/S1_Actividad_Verificacion.xlsx")
    assert excel.headers["content-disposition"].startswith("attachment")


# ---------- Fase 8b: sumas y porcentajes del caso ----------

def test_los_porcentajes_redondeados_no_son_falla():
    from tests.sembrados.actividad import CON_PORCENTAJES_LIMPIA
    assert actividad._validar(copy.deepcopy(CON_PORCENTAJES_LIMPIA), ",")[1] == []


# ---------- Fase 8b: la revisión del contenido ----------

def test_los_bloques_marcan_la_opcion_correcta_y_las_incorrectas():
    bloques = actividad.bloques_de(Actividad.model_validate(LIMPIA))
    assert [b.nombre for b in bloques] == ["Presentación y caso", "Paso 1. Reconozca los pilares",
                                           "Paso 2. Revise el cierre de la semana", "Paso 3. Ordene la revisión",
                                           "Paso 4. Relacione y clasifique"]
    assert "Semana | Pedidos" in bloques[0].oraciones and "Total | 95" in bloques[0].oraciones
    paso1 = bloques[1].oraciones
    assert paso1[paso1.index("Tres") - 1] == actividad.CORRECTA
    assert paso1[paso1.index("Dos") - 1] == actividad.INCORRECTA
    assert paso1[paso1.index("Dos") + 1] == actividad.EXPLICACION   # la explicación se revisa aparte del texto
    assert "[orden correcto]" in bloques[3].oraciones
    assert "[categoría: Apertura]" in bloques[4].oraciones and "[par] Foco → Trabaja en un pedido a la vez." in bloques[4].oraciones


def test_la_revision_compara_con_la_lectura_y_sabe_que_una_opcion_incorrecta_no_es_error(sesion):  # noqa: F811
    lectura_aprobada(sesion)
    _, consulta = generar(sesion, copy.deepcopy(LIMPIA))
    pedido = consulta.llamadas[1]["prompt"]
    assert "El texto de una opción incorrecta afirma algo falso a propósito: no es error." in pedido
    assert "compara cada explicación con la lectura, también la de una opción incorrecta" in pedido
    assert "[Paso 1. Reconozca los pilares]" in pedido and actividad.INCORRECTA in pedido
    assert "(lectura aprobada ·" in pedido   # la lectura es una fuente más de la revisión


def test_un_error_de_la_revision_se_corrige_y_se_confirma(sesion):  # noqa: F811
    lectura_aprobada(sesion)
    datos = copy.deepcopy(LIMPIA)
    datos["pasos"][0]["preguntas"][0]["opciones"][0]["explicacion"] = "La lectura nombra cuatro pilares."
    falla = error("La lectura nombra cuatro pilares.", "contradice la fuente", bloque="Paso 1. Reconozca los pilares",
                  prueba="Los pilares de Scrum son tres.")
    material, consulta = generar(sesion, datos, revision(falla),
                                 cambios(("La lectura nombra cuatro pilares.", "La lectura nombra tres pilares.")))
    assert material["estado"] == "verificada"
    assert material["revision"]["errores"] == 1 and material["revision"]["corregidos"] == 1
    assert material["correcciones"]["revisión"] == 1
    assert len(consulta.llamadas) == 4   # redacción, revisión, corrección y confirmación del bloque que cambió
    assert "[Paso 1. Reconozca los pilares]" in consulta.llamadas[3]["prompt"]
    assert "[Presentación y caso]" not in consulta.llamadas[3]["prompt"]
    filas = list(openpyxl.load_workbook(actividad.archivos(sesion, 1)["excel"])["Hallazgos"].iter_rows(values_only=True))
    assert any(f[3] == "revisión: contradice la fuente" and f[5] == "Corregido y confirmado por la revisión." for f in filas)


def test_lo_que_sigue_despues_de_la_correccion_queda_pendiente(sesion):  # noqa: F811
    lectura_aprobada(sesion)
    ambigua = error("Decide qué cambia la próxima semana.", "ambigüedad", bloque="Paso 2. Revise el cierre de la semana")
    material, _ = generar(sesion, copy.deepcopy(LIMPIA), revision(ambigua),
                          cambios(("Decide qué cambia la próxima semana.", "Decide un cambio para la próxima semana.")),
                          revision({**ambigua, "oracion": "Decide un cambio para la próxima semana."}), revisar=False)
    assert material["estado"] == "con pendientes"
    assert material["revision"]["pendientes"] == 1
    assert any("ambigüedad" in p for p in material["problemas"])
    assert actividad.aprobar(sesion, 1)["estado"] == "aprobada"   # el profesor ya vio el pendiente


def test_el_revisor_independiente_revisa_la_actividad_sin_corregir(sesion):  # noqa: F811
    from app.validacion import pasada2
    lectura_aprobada(sesion)
    generar(sesion, copy.deepcopy(LIMPIA))
    consulta = consulta_en_secuencia({"hallazgos": [], "bloques": [], "lista": []})
    material = asyncio.run(actividad.revisar_con_revisor(sesion, "scrum", 1, consulta=consulta))
    assert material["estado"] == "verificada" and material["revisor"]["hallazgos"] == 0
    assert len(consulta.llamadas) == 1 and consulta.llamadas[0]["options"].model == "claude-opus-5-5"
    assert "Revisor independiente (lo pediste tú): 0 hallazgos con prueba" in json.dumps(material["entrega"], ensure_ascii=False)
    preguntas = pasada2.lista_de_verificacion("Actividad web")
    assert preguntas and not any(p.startswith("¿Ejecutaste cada ejercicio") for p in preguntas)


def test_el_revisor_no_revisa_una_actividad_con_fallas(sesion):  # noqa: F811
    with pytest.raises(actividad.NoSePuedeRevisar):
        asyncio.run(actividad.revisar_con_revisor(sesion, "scrum", 1, consulta=consulta_en_secuencia()))


# ---------- Sin lectura en la sesión ----------

@pytest.fixture
def sin_lectura(entorno):
    """Curso con una fuente y una sesión que produce la actividad web, pero no la lectura."""
    from app.fichas import flujo
    from tests.fixtures import fichas as datos
    from tests.unidad.test_fichas import con_fuente
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    carpeta = entorno["cursos"] / "scrum"
    (carpeta / "fuentes").mkdir(parents=True)
    (carpeta / "curso.json").write_text('{"nombre": "Scrum"}', encoding="utf-8")
    con_fuente(carpeta)
    almacen.guardar(carpeta, "curso", None, datos.ficha("curso", datos.CURSO))
    flujo.confirmar_curso(carpeta)
    almacen.guardar(carpeta, "sesion", 1, datos.ficha("sesion", {**datos.SESION, "materiales.cuales": "actividad web"}))
    revisor_de_ejercicios = consulta_en_secuencia({"ejercicios": [
        {"numero": n, "funciona_solo": True, "sin_llenar_a_mano": True, "motivo": "Cumple"} for n in (1, 2, 3)]})
    asyncio.run(flujo.confirmar_sesion(carpeta, "scrum", 1, consulta=revisor_de_ejercicios))
    return carpeta


def test_sin_lectura_la_actividad_sale_de_las_fuentes_y_las_fichas(sin_lectura):
    assert actividad.usa_lectura(sin_lectura, 1) is False
    assert actividad.faltan(sin_lectura, 1) == {"ficha": [], "otros": []}
    material, consulta = generar(sin_lectura, copy.deepcopy(LIMPIA))
    assert material["estado"] == "verificada", material["problemas"]
    redaccion, revision_ = consulta.llamadas[0]["prompt"], consulta.llamadas[1]["prompt"]
    assert "ESTA SESIÓN NO TIENE LECTURA" in redaccion and "LECTURA APROBADA" not in redaccion
    assert "La actividad refuerza lo que enseñó la lectura." not in redaccion
    assert actividad.FUENTE_SIN_LECTURA in revision_ and actividad.FUENTE_CON_LECTURA not in revision_
    assert "(lectura aprobada ·" not in revision_
    entrega_ = json.dumps(material["entrega"], ensure_ascii=False)
    assert "Revisión del contenido contra las fuentes y las fichas" in entrega_


def test_con_lectura_la_revision_la_nombra_como_fuente(sesion):  # noqa: F811
    lectura_aprobada(sesion)
    _, consulta = generar(sesion, copy.deepcopy(LIMPIA))
    assert actividad.FUENTE_CON_LECTURA in consulta.llamadas[1]["prompt"]
    assert actividad.FUENTE_SIN_LECTURA not in consulta.llamadas[1]["prompt"]
