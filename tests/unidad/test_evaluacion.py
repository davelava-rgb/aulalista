"""Evaluación práctica (PBQ) y su clave, fase 9a (PLAN.md §0, decisión 64): el modelo de datos, lo que hace falta
para generarla, la revisión de sus preguntas en la ficha y el plan de la sesión. Sin IA."""

import asyncio
import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import servidor
from app.fichas import almacen, flujo
from app.materiales import comun, evaluacion
from app.materiales.contenido import ESQUEMA_EVALUACION, Evaluacion
from tests.conftest import consulta_en_secuencia
from tests.sembrados import evaluacion as sembrados
from tests.unidad.test_lectura import sesion  # noqa: F401

cliente = TestClient(servidor.app)


# ---------- Modelo de datos ----------

def test_la_evaluacion_limpia_cumple_el_modelo():
    contenido = Evaluacion.model_validate(sembrados.limpio())
    assert len(contenido.preguntas) == 2
    assert contenido.preguntas[0].tabla_de_respuesta.por_llenar == 3   # cada celda vacía es una decisión (64 c)
    assert set(ESQUEMA_EVALUACION["properties"]) == {"indicaciones", "preguntas", "archivos", "pasajes", "decisiones"}


@pytest.mark.parametrize("campo", ["puntos", "puntaje", "minutos", "tiempo", "nota"])
def test_el_modelo_no_acepta_puntos_ni_tiempos(campo):
    """SKILL.md, «Sin tiempos ni puntajes»: la evaluación no tiene dónde ponerlos."""
    datos = sembrados.limpio()
    datos["preguntas"][0][campo] = 5
    with pytest.raises(ValidationError):
        Evaluacion.model_validate(datos)
    datos = sembrados.limpio()
    datos[campo] = "30 minutos"
    with pytest.raises(ValidationError):
        Evaluacion.model_validate(datos)


@pytest.mark.parametrize("cambio, mensaje", [
    (lambda d: d["preguntas"][0]["clave"]["respuesta"][0].__setitem__(1, ""), "sin llenar"),
    (lambda d: d["preguntas"][0]["clave"]["respuesta"].pop(), "forma de la tabla"),
    (lambda d: d["preguntas"][0]["clave"]["respuesta"][0].__setitem__(0, "Hecho 9"), "cambia una celda"),
    (lambda d: d["preguntas"][0]["tabla_de_respuesta"].__setitem__("filas", [["Hecho 1", "Transparencia"]]),
     "forma de la tabla"),
    (lambda d: d["preguntas"][0]["clave"].__setitem__("partes", []), "partes"),
    (lambda d: d["preguntas"][0].__setitem__("tarea", "redactar"), "tarea"),
    (lambda d: d["preguntas"][1].__setitem__("numero", 3), "numeradas"),
    (lambda d: d["archivos"][0].__setitem__("nombre", "S1_E1_hechos.xlsx"), "no sigue la forma"),
    (lambda d: d["archivos"][0].__setitem__("nombre", "S1_P2_hechos-ventas.xlsx"), "es de la pregunta 2"),
    (lambda d: d["preguntas"][0]["archivos"].append("S1_P1_otro.xlsx"), "no está en los archivos"),
])
def test_el_modelo_rechaza_una_pregunta_sin_respuesta_clara(cambio, mensaje):
    datos = sembrados.limpio()
    cambio(datos)
    with pytest.raises(ValidationError, match=mensaje):
        Evaluacion.model_validate(datos)


def test_una_tabla_sin_celdas_para_el_alumno_no_es_una_pregunta():
    datos = sembrados.limpio()
    completa = datos["preguntas"][0]["clave"]["respuesta"]
    datos["preguntas"][0]["tabla_de_respuesta"]["filas"] = [list(f) for f in completa]
    with pytest.raises(ValidationError, match="ninguna celda para el alumno"):
        Evaluacion.model_validate(datos)


# ---------- Lo que hace falta para generarla (decisión 64 a) ----------

def _aprobar(carpeta, clave):
    ahora = datetime.now().isoformat(timespec="seconds")
    comun.actualizar(carpeta, 1, clave, estado="aprobada", fecha=ahora, aprobada=ahora, desactualizado=False)


def test_la_evaluacion_espera_la_lectura_y_el_laboratorio_aprobados_y_al_dia(sesion):  # noqa: F811
    assert evaluacion.faltan(sesion, 1) == {"ficha": [], "otros": [
        "Aprueba primero la lectura: la evaluación no evalúa nada que no se haya enseñado.",
        "Aprueba primero el laboratorio: la evaluación no evalúa nada que no se haya enseñado."]}
    _aprobar(sesion, "lectura")
    _aprobar(sesion, "laboratorio")
    assert evaluacion.faltan(sesion, 1) == {"ficha": [], "otros": []}
    comun.actualizar(sesion, 1, "laboratorio", desactualizado=True)
    assert evaluacion.faltan(sesion, 1)["otros"] == [
        "El laboratorio está desactualizado: genéralo y apruébalo de nuevo."]


def test_sin_laboratorio_en_la_sesion_la_evaluacion_no_lo_espera(sesion):  # noqa: F811
    ficha = almacen.cargar(sesion, "sesion", 1)
    ficha["campos"]["materiales.cuales"] = {"valor": "lectura, evaluación", "origen": "profesor", "estado": ""}
    almacen.guardar(sesion, "sesion", 1, ficha, "editada por el profesor")
    _aprobar(sesion, "lectura")
    assert evaluacion.faltan(sesion, 1) == {"ficha": [], "otros": []}


def test_sin_preguntas_en_la_ficha_lo_que_falta_es_la_ficha(sesion):  # noqa: F811
    ficha = almacen.cargar(sesion, "sesion", 1)
    for campo in [c for c in ficha["campos"] if c.startswith("pregunta.")]:
        ficha["campos"][campo] = {"valor": "", "origen": "", "estado": ""}
    almacen.guardar(sesion, "sesion", 1, ficha, "editada por el profesor")
    faltan = evaluacion.faltan(sesion, 1)
    assert faltan["otros"] == [] and any("al menos una pregunta" in f for f in faltan["ficha"])


def test_la_evaluacion_tiene_sus_propios_archivos(sesion):  # noqa: F811
    rutas = evaluacion.archivos(sesion, 1)
    nombres = {k: r.name for k, r in rutas.items() if k in ("word", "clave", "zip", "excel")}
    assert nombres == {"word": "S1_Evaluacion.docx", "clave": "S1_Evaluacion_Clave.docx",
                       "zip": "S1_Evaluacion_Archivos.zip", "excel": "S1_Evaluacion_Verificacion.xlsx"}
    assert rutas["zip"] != servidor.laboratorio.archivos(sesion, 1)["zip"]     # aparte del .zip del laboratorio


# ---------- La ficha y el plan de la sesión (decisión 64 h e i) ----------

def _revision(ejercicios, preguntas):
    def fila(n, solo=True, datos=True):
        return {"numero": n, "funciona_solo": solo, "sin_llenar_a_mano": datos, "motivo": "Cumple"}
    return {"ejercicios": [fila(n) for n in ejercicios], "preguntas": [fila(n, *p) for n, p in preguntas]}


def test_la_revision_de_la_ficha_revisa_tambien_las_preguntas(sesion):  # noqa: F811
    ficha = almacen.cargar(sesion, "sesion", 1)
    ficha.pop("revision_ejercicios", None)          # sin una revisión guardada de antes
    texto, preguntas = almacen.texto_de_preguntas(ficha)
    assert preguntas and "Pregunta 1 · Concepto que evalúa: Pilares de Scrum" in texto
    _, ejercicios = almacen.texto_de_ejercicios(ficha)
    consulta = consulta_en_secuencia(_revision(ejercicios, [(1, (True, True)), (2, (False, True))]))
    problemas = asyncio.run(flujo.revisar_ejercicios(ficha, "scrum", 1, consulta=consulta))
    assert problemas == ["Pregunta 2 de la evaluación: no funciona sola. Cumple"]
    assert "Revisa también cada pregunta de la evaluación práctica" in consulta.llamadas[0]["prompt"]


def test_sin_evaluacion_en_la_sesion_sus_preguntas_no_se_revisan(sesion):  # noqa: F811
    ficha = almacen.cargar(sesion, "sesion", 1)
    huella_con = almacen.huella_de_ejercicios(ficha)
    ficha["campos"]["materiales.cuales"] = {"valor": "lectura, laboratorio", "origen": "profesor", "estado": ""}
    assert almacen.texto_de_preguntas(ficha) == ("", [])
    assert almacen.huella_de_ejercicios(ficha) != huella_con   # cambia lo que se revisa: se revisa de nuevo
    _, ejercicios = almacen.texto_de_ejercicios(ficha)
    consulta = consulta_en_secuencia(_revision(ejercicios, []))
    asyncio.run(flujo.revisar_ejercicios(ficha, "scrum", 1, consulta=consulta))
    assert "No hay preguntas de evaluación" in consulta.llamadas[0]["prompt"]


def test_el_plan_de_la_sesion_cuenta_la_evaluacion_solo_si_la_produce(sesion):  # noqa: F811
    ficha = almacen.cargar(sesion, "sesion", 1)
    assert not flujo.plan_por_preparar(ficha)
    ficha["campos"]["pregunta.1.respuesta"] = {"valor": "", "origen": "", "estado": ""}
    assert flujo.plan_por_preparar(ficha)                         # falta algo que la evaluación pide
    ficha["campos"]["materiales.cuales"] = {"valor": "lectura, laboratorio", "origen": "profesor", "estado": ""}
    assert not flujo.plan_por_preparar(ficha)                     # la sesión no la produce: no cuenta


def test_la_ficha_ya_no_dice_que_la_evaluacion_no_se_usa(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert "estado-no_se_usa" not in pagina and "AulaLista no genera la evaluación" not in pagina
    assert "decisión 37" not in pagina and "apagada" not in pagina
    assert "Las preguntas se revisan al guardar, junto con los ejercicios." in pagina
    # El material todavía no se genera desde la interfaz (decisión 46): llega en la fase 9d.
    assert "/materiales/evaluacion" not in cliente.get("/cursos/scrum").text
