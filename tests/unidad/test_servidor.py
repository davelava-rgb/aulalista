from fastapi.testclient import TestClient

from app import agente, servidor
from tests.conftest import consulta_simulada

cliente = TestClient(servidor.app)


def test_la_pagina_de_inicio_no_muestra_la_conexion_con_claude(entorno):
    r = cliente.get("/")
    assert r.status_code == 200
    assert "Crear curso" in r.text
    assert "Conexión con Claude" not in r.text and "Probar conexión" not in r.text


def test_probar_conexion_sin_clave_responde_el_mensaje(entorno):
    r = cliente.post("/api/probar-conexion")
    assert r.status_code == 400
    assert "No hay clave de API" in r.json()["error"]


def test_probar_conexion_devuelve_respuesta_y_gasto(entorno, monkeypatch):
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    original = agente.probar_conexion
    monkeypatch.setattr(agente, "probar_conexion", lambda: original(consulta_simulada()))

    r = cliente.post("/api/probar-conexion")

    assert r.status_code == 200
    datos = r.json()
    assert datos["texto"] == "Conexión correcta."
    assert datos["gasto"]["llamadas"] == 1


def test_el_servidor_solo_escucha_en_esta_computadora():
    from app import __main__ as inicio
    assert inicio.DIRECCION == "127.0.0.1"
