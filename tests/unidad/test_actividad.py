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
from tests.sembrados.actividad import CASOS, LIMPIA, PUNTAJE_LIMPIO
from tests.unidad.test_lectura import LIMPIA as LECTURA_LIMPIA
from tests.unidad.test_lectura import cambios, sesion  # noqa: F401

cliente = TestClient(servidor.app)


def lectura_aprobada(carpeta, numero=1):
    lectura.archivos(carpeta, numero)["contenido"].parent.mkdir(parents=True, exist_ok=True)
    comun.guardar_json(lectura.archivos(carpeta, numero)["contenido"], LECTURA_LIMPIA)
    comun.actualizar(carpeta, numero, lectura.CLAVE, estado="aprobada", aprobada="2026-10-21T10:00:00")


def generar(carpeta, *salidas):
    consulta = consulta_en_secuencia(*salidas)
    material = asyncio.run(actividad.generar(carpeta, "scrum", 1, consulta=consulta))
    return material, consulta


# ---------- Revisiones del programa, sin IA ----------

def test_el_contenido_limpio_pasa_la_revision_del_programa():
    contenido, fallas = actividad._validar(copy.deepcopy(LIMPIA), ",")
    assert fallas == []
    assert contenido.puntaje_total == PUNTAJE_LIMPIO


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
    assert "Opción única · 2 puntos" in pagina and "Clasificar · 3 puntos" in pagina
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

def test_un_contenido_limpio_queda_verificado_con_una_llamada(sesion):  # noqa: F811
    lectura_aprobada(sesion)
    material, consulta = generar(sesion, copy.deepcopy(LIMPIA))
    rutas = actividad.archivos(sesion, 1)
    assert material["estado"] == "verificada", material["problemas"]
    assert material["resumen"].endswith("Fallas: 0 · Avisos: 0")
    assert (material["pasos"], material["preguntas"], material["puntaje_total"]) == (4, 5, PUNTAJE_LIMPIO)
    assert rutas["vista"].exists() and rutas["excel"].exists()
    assert json.loads(rutas["contenido"].read_text(encoding="utf-8"))["titulo"] == LIMPIA["titulo"]
    assert len(consulta.llamadas) == 1   # sin revisión con IA hasta la fase 8b
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
    assert len(consulta.llamadas) == 2 and material["correcciones"] == {"verificador": 1}
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
    material, _ = generar(sesion, roto, *[copy.deepcopy(sigue) for _ in range(actividad.VUELTAS_DEL_VERIFICADOR)])
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
    assert "Pedir revisor independiente" not in pagina   # llega en la fase 8b
    respuesta = cliente.get("/cursos/scrum/sesiones/1/descargar/S1_Actividad_Contenido.html")
    assert respuesta.status_code == 200 and respuesta.headers["content-disposition"].startswith("inline")
    excel = cliente.get("/cursos/scrum/sesiones/1/descargar/S1_Actividad_Verificacion.xlsx")
    assert excel.headers["content-disposition"].startswith("attachment")
    r = cliente.post("/cursos/scrum/sesiones/1/materiales/actividad/revisor", follow_redirects=False)
    assert "revisor" in r.headers["location"] and actividad.estado(sesion, 1)["estado"] == "verificada"
