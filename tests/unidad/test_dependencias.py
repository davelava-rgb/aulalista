"""Cada material se desactualiza solo por lo que usa (PLAN.md §0, decisión 62). Sin IA."""

import json
import time
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import servidor
from app.fichas import almacen, dependencias
from app.fuentes import convertir
from app.materiales import actividad, comun, diapositivas, evaluacion, laboratorio, lectura
from tests.unidad.test_lectura import sesion  # noqa: F401

cliente = TestClient(servidor.app)
# Con la evaluación (decisión 64), cinco; el nombre queda del tiempo de la decisión 62.
CUATRO = {"lectura", "diapositivas", "laboratorio", "actividad", "evaluacion"}
ESTADOS = {"lectura": lectura, "diapositivas": diapositivas, "laboratorio": laboratorio, "actividad": actividad,
           "evaluacion": evaluacion}


def _generar_todos(carpeta):
    """Los materiales generados y aprobados con las fichas de ahora: guardan lo que usan."""
    for clave in ("lectura", "diapositivas", "laboratorio", "actividad", "evaluacion"):
        comun.actualizar(carpeta, 1, clave, estado="trabajando", previo="")
        ahora = datetime.now().isoformat(timespec="seconds")
        comun.actualizar(carpeta, 1, clave, estado="aprobada", fecha=ahora, aprobada=ahora, desactualizado=False)


def _cambiar(carpeta, tipo, campo_id, valor):
    ficha = almacen.cargar(carpeta, tipo, None if tipo == "curso" else 1)
    ficha["campos"][campo_id] = {**(ficha["campos"].get(campo_id) or {}), "valor": valor}
    almacen.guardar(carpeta, tipo, None if tipo == "curso" else 1, ficha, "editada por el profesor")


def _desactualizados(carpeta):
    almacen.marcar_desactualizados(carpeta, 1)
    return {c for c, m in ESTADOS.items() if m.estado(carpeta, 1).get("desactualizado")}


@pytest.mark.parametrize("tipo, campo, quedan", [
    ("sesion", "sesion.alcance", CUATRO),
    ("sesion", "sesion.numero_titulo", CUATRO),
    ("sesion", "sesion.ya_vieron", CUATRO),
    ("sesion", "sesion.referencia", CUATRO),
    ("sesion", "vocabulario.conceptos", CUATRO),
    ("sesion", "lectura.ejemplo", {"lectura", "diapositivas"}),
    ("sesion", "lectura.bloque.2", {"lectura", "diapositivas"}),
    ("sesion", "ejercicio.1.respuesta", {"laboratorio"}),
    ("curso", "herramientas.ejercicios", {"laboratorio"}),
    ("curso", "herramientas.adjuntos", {"laboratorio"}),
    ("sesion", "evaluacion.entrega", {"evaluacion"}),        # decisión 64 g
    ("sesion", "pregunta.1.respuesta", {"evaluacion"}),
    ("curso", "publico.quienes", CUATRO),
    ("curso", "caso.empresa", CUATRO),
    ("curso", "curso.idioma", CUATRO),
    ("curso", "portada.docente", {"lectura", "diapositivas", "laboratorio"}),
    ("curso", "visual.principal", CUATRO),
    ("curso", "curso.horas", set()),
])
def test_cada_campo_desactualiza_solo_los_materiales_que_lo_usan(sesion, tipo, campo, quedan):  # noqa: F811
    _generar_todos(sesion)
    _cambiar(sesion, tipo, campo, "Un valor nuevo para esta prueba.")
    assert _desactualizados(sesion) == quedan


def test_quitar_la_marca_propuesto_no_desactualiza(sesion):  # noqa: F811
    _generar_todos(sesion)
    ficha = almacen.cargar(sesion, "sesion", 1)
    _cambiar(sesion, "sesion", "sesion.alcance", almacen.valor(ficha, "sesion.alcance") + " (propuesto)")
    assert _desactualizados(sesion) == set()


def test_agregar_un_dato_fijo_no_desactualiza_y_cambiarlo_si(sesion):  # noqa: F811
    _generar_todos(sesion)
    almacen.agregar_datos_fijos(sesion, ["Código de la tienda: T-900"], "prueba")
    assert _desactualizados(sesion) == set()
    curso = almacen.cargar(sesion, "curso")
    lineas = almacen.valor(curso, "datos.fijos").split("\n")
    _cambiar(sesion, "curso", "datos.fijos", "\n".join(lineas[1:]))   # se quita la primera línea
    assert _desactualizados(sesion) == CUATRO
    assert "Datos fijos del caso (se cambió o quitó una línea)" in " ".join(lectura.estado(sesion, 1)["razones"])


def test_el_renglon_de_la_sesion_en_sesiones_desactualiza_solo_si_es_el_suyo(sesion):  # noqa: F811
    _generar_todos(sesion)
    curso = almacen.cargar(sesion, "curso")
    lineas = almacen.valor(curso, "curso.sesiones").split("\n")
    otra = [l if not l.lstrip().startswith("2") else l + " Otro título." for l in lineas]
    _cambiar(sesion, "curso", "curso.sesiones", "\n".join(otra))
    assert _desactualizados(sesion) == set()
    suya = [l if not l.lstrip().startswith("1") else l + " Otro título." for l in lineas]
    _cambiar(sesion, "curso", "curso.sesiones", "\n".join(suya))
    assert _desactualizados(sesion) == CUATRO


def test_una_fuente_con_otro_contenido_desactualiza_los_cuatro(sesion):  # noqa: F811
    _generar_todos(sesion)
    indice = convertir.leer_indice(sesion)
    nombre = next(iter(indice))
    indice[nombre]["huella"] = "otra-huella"
    convertir._guardar_indice(sesion, indice)
    assert _desactualizados(sesion) == CUATRO
    assert f"Cambió el contenido de la fuente {nombre}." in lectura.estado(sesion, 1)["razones"]


def test_una_lectura_nueva_desactualiza_lo_que_sale_de_ella(sesion):  # noqa: F811
    _generar_todos(sesion)
    time.sleep(1.1)
    comun.actualizar(sesion, 1, "lectura", fecha=datetime.now().isoformat(timespec="seconds"))
    for clave in ("laboratorio", "actividad"):
        assert ESTADOS[clave].estado(sesion, 1)["desactualizado"] is True
    assert not lectura.estado(sesion, 1).get("desactualizado")


def test_si_lo_usado_vuelve_a_coincidir_deja_de_estar_desactualizado(sesion):  # noqa: F811
    _generar_todos(sesion)
    antes = almacen.valor(almacen.cargar(sesion, "sesion", 1), "sesion.alcance")
    _cambiar(sesion, "sesion", "sesion.alcance", "Otro alcance.")
    assert _desactualizados(sesion) == CUATRO
    _cambiar(sesion, "sesion", "sesion.alcance", antes)
    assert _desactualizados(sesion) == set()


def test_el_aviso_dice_solo_lo_que_desactualizo_ese_material(sesion):  # noqa: F811
    _generar_todos(sesion)
    _cambiar(sesion, "sesion", "sesion.alcance", "Otro alcance.")
    _cambiar(sesion, "sesion", "ejercicio.1.respuesta", "Otra respuesta.")
    almacen.marcar_desactualizados(sesion, 1)
    comun.actualizar(sesion, 1, "lectura", entrega={"pregunta": "¿Apruebas la lectura?", "secciones": []})
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert "<li>En la ficha de la sesión: Alcance.</li>" in pagina and "Ejercicio 1" not in pagina


def test_un_material_de_antes_toma_lo_que_uso_de_las_versiones_de_su_fecha(sesion):  # noqa: F811
    time.sleep(1.1)
    generada = datetime.now().isoformat(timespec="seconds")
    time.sleep(1.1)
    estado = almacen.cargar_estado(sesion, 1)
    estado["materiales"]["lectura"] = {"estado": "aprobada", "fecha": generada, "desactualizado": True}
    almacen.guardar_estado(sesion, 1, estado)
    _cambiar(sesion, "curso", "herramientas.ejercicios", "Excel")   # no la usa la lectura
    assert dependencias.por_migrar(almacen.cargar_estado(sesion, 1))
    assert _desactualizados(sesion) == set()
    assert "usado" in almacen.cargar_estado(sesion, 1)["materiales"]["lectura"]
    assert dependencias.usado_en(sesion, 1, "2000-01-01T00:00:00") is None   # sin versión de entonces: no se sabe


def test_los_campos_se_nombran_corto():
    from app.fichas import plantillas
    assert plantillas.etiqueta_corta("sesion", "sesion.referencia") == "Material de referencia"
    assert plantillas.etiqueta_corta("sesion", "ejercicio.3.respuesta") == "Ejercicio 3 · respuesta correcta"
    assert plantillas.etiqueta_corta("curso", "datos.fijos") == "Datos fijos del caso"


def test_lo_usado_queda_guardado_al_generar(sesion):  # noqa: F811
    comun.actualizar(sesion, 1, "laboratorio", estado="trabajando", previo="")
    material = almacen.cargar_estado(sesion, 1)["materiales"]["laboratorio"]
    assert set(material["usado"]) == {"curso", "sesion", "linea_de_la_sesion", "datos_fijos", "fuentes"}
    assert json.dumps(material["usado"])   # se guarda como datos simples


def test_una_lectura_o_un_laboratorio_nuevos_desactualizan_la_evaluacion(sesion):  # noqa: F811
    """Decisión 64 g: la evaluación sale de la lectura y del laboratorio aprobados."""
    _generar_todos(sesion)
    assert not evaluacion.estado(sesion, 1).get("desactualizado")
    time.sleep(1.1)   # la fecha va en segundos: la nueva tiene que ser distinta
    ahora = datetime.now().isoformat(timespec="seconds")
    comun.actualizar(sesion, 1, "laboratorio", estado="aprobada", fecha=ahora, aprobada=ahora)
    assert evaluacion.estado(sesion, 1)["desactualizado"] is True
    assert not lectura.estado(sesion, 1).get("desactualizado")
    _generar_todos(sesion)
    time.sleep(1.1)
    ahora = datetime.now().isoformat(timespec="seconds")
    comun.actualizar(sesion, 1, "lectura", estado="aprobada", fecha=ahora, aprobada=ahora)
    assert evaluacion.estado(sesion, 1)["desactualizado"] is True
