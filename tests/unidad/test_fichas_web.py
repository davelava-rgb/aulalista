"""Etapa 4 desde la página: llenar, guardar, confirmar, recuperar versiones y abrir la sesión."""

import pytest
from fastapi.testclient import TestClient

from app import servidor
from app.fichas import almacen, flujo
from tests.conftest import consulta_simulada
from tests.fixtures import fichas as datos

cliente = TestClient(servidor.app)


@pytest.fixture
def curso(entorno):
    cliente.post("/cursos", data={"nombre": "Scrum"})
    return entorno["cursos"] / "scrum"


def test_la_pagina_muestra_la_plantilla_y_las_preguntas_pendientes(curso):
    r = cliente.get("/cursos/scrum/ficha")
    assert r.status_code == 200
    assert "Nombre del curso (obligatorio)" in r.text
    assert "¿Material neutral respecto a marcas? (sí o no)" in r.text
    assert "Responde primero estas 2" in r.text   # nombre y sesiones: los dos obligatorios del curso


def test_guardar_y_confirmar_con_datos_faltantes(curso):
    r = cliente.post("/cursos/scrum/ficha", data={"accion": "confirmar", "curso.nombre": "Scrum Master con IA"})
    assert "La ficha no se confirmó." in r.text
    assert "Falta «Sesiones. Una línea por sesión: número, título y alcance.»." in r.text
    assert almacen.valor(almacen.cargar(curso, "curso"), "curso.nombre") == "Scrum Master con IA"


def test_confirmar_la_ficha_del_curso_abre_las_sesiones(curso):
    r = cliente.post("/cursos/scrum/ficha", data={"accion": "confirmar", **datos.CURSO})
    assert "Ficha del curso confirmada." in r.text
    pagina = cliente.get("/cursos/scrum").text
    assert "1. Agilidad y fundamentos de Scrum" in pagina
    assert "/cursos/scrum/sesiones/2/ficha" in pagina


def test_la_ficha_de_la_sesion_espera_a_la_del_curso(curso):
    assert cliente.get("/cursos/scrum/sesiones/1/ficha").status_code == 409


def test_confirmar_la_ficha_de_la_sesion_desde_la_pagina(curso, entorno, monkeypatch):
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    cliente.post("/cursos/scrum/ficha", data={"accion": "confirmar", **datos.CURSO})
    revisor = consulta_simulada(structured_output={"ejercicios": [
        {"numero": n, "funciona_solo": True, "sin_llenar_a_mano": True, "motivo": "Cumple"} for n in (1, 2, 3)]})
    original = flujo.confirmar_sesion
    monkeypatch.setattr(flujo, "confirmar_sesion", lambda c, cu, s: original(c, cu, s, consulta=revisor))
    r = cliente.post("/cursos/scrum/sesiones/1/ficha", data={"accion": "confirmar", **datos.SESION})
    assert "Ficha de la sesión confirmada. Se escribió verificacion.json." in r.text
    assert (curso / "sesiones" / "S1" / "verificacion.json").exists()
    assert "Confirmada" in cliente.get("/cursos/scrum").text


def test_recuperar_una_version_desde_la_pagina(curso):
    cliente.post("/cursos/scrum/ficha", data={"accion": "guardar", "curso.nombre": "Primero"})
    cliente.post("/cursos/scrum/ficha", data={"accion": "guardar", "curso.nombre": "Segundo"})
    version = almacen.listar_versiones(curso, "curso")[-1]["archivo"]
    r = cliente.post("/cursos/scrum/ficha/restaurar", data={"version": version})
    assert "Primero" in r.text


def test_proponer_sin_clave_avisa_sin_romper_la_pagina(curso, tmp_path):
    from tests.unidad.test_fichas import con_fuente
    con_fuente(curso)
    r = cliente.post("/cursos/scrum/ficha", data={"accion": "proponer"})
    assert r.status_code == 200
    assert "No hay clave de API" in r.text
