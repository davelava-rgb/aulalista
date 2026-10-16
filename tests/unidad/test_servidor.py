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


def test_con_el_puerto_ocupado_avisa_en_vez_de_abrir_la_version_vieja():
    import socket
    from app import __main__ as inicio
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as ocupado:
        ocupado.bind((inicio.DIRECCION, 0))
        ocupado.listen()
        puerto = ocupado.getsockname()[1]
        assert inicio.puerto_libre(inicio.DIRECCION, puerto) is False
    assert inicio.puerto_libre(inicio.DIRECCION, puerto) is True


def test_reconoce_su_propia_linea_de_comando():
    from app import __main__ as inicio
    assert inicio.es_aulalista('"C:\aula\.venv\Scripts\python.exe"  -m app')
    assert inicio.es_aulalista(".venv/Scripts/python.exe -m uvicorn app.servidor:app --port 8766")
    assert not inicio.es_aulalista("C:\Program Files\otro\servidor.exe --port 8765")


def test_dice_que_se_esta_generando(tmp_path):
    from app import __main__ as inicio
    assert inicio.trabajos_en_curso(tmp_path) == []
    sesion = tmp_path / "scrum" / "sesiones" / "S2"
    sesion.mkdir(parents=True)
    (sesion / "estado.json").write_text(
        '{"materiales": {"lectura": {"estado": "aprobada"}, "diapositivas": {"estado": "trabajando"}}}', encoding="utf-8")
    (tmp_path / "scrum" / "propuesta_curso.json").write_text('{"estado": "trabajando"}', encoding="utf-8")
    assert inicio.trabajos_en_curso(tmp_path) == ["- scrum, sesión 2: diapositivas",
                                                  "- scrum: la ficha se está proponiendo desde las fuentes"]


def test_cierra_la_version_anterior_solo_si_no_trabaja(tmp_path, monkeypatch):
    from app import __main__ as inicio
    cerrados = []
    monkeypatch.setattr(inicio.subprocess, "run", lambda orden, **_: cerrados.append(orden))
    monkeypatch.setattr(inicio, "puerto_libre", lambda *_: True)
    monkeypatch.setattr(inicio, "proceso_en_puerto", lambda *_: (4321, "python.exe -m app"))
    assert inicio.cerrar_version_anterior(tmp_path) is None
    assert cerrados == [["taskkill", "/PID", "4321", "/F"]]

    sesion = tmp_path / "scrum" / "sesiones" / "S1"
    sesion.mkdir(parents=True)
    (sesion / "estado.json").write_text('{"materiales": {"lectura": {"estado": "trabajando"}}}', encoding="utf-8")
    cerrados.clear()
    aviso = inicio.cerrar_version_anterior(tmp_path)
    assert "está trabajando" in aviso and "scrum, sesión 1: lectura" in aviso and cerrados == []

    monkeypatch.setattr(inicio, "proceso_en_puerto", lambda *_: (99, "otro.exe"))
    assert "no es AulaLista" in inicio.cerrar_version_anterior(tmp_path) and cerrados == []


def test_un_trabajando_viejo_no_impide_cerrar_la_version_anterior(tmp_path):
    import time
    from app import __main__ as inicio
    sesion = tmp_path / "scrum" / "sesiones" / "S1"
    sesion.mkdir(parents=True)
    (sesion / "estado.json").write_text('{"materiales": {"lectura": {"estado": "trabajando"}}}', encoding="utf-8")
    assert inicio.trabajos_en_curso(tmp_path) == ["- scrum, sesión 1: lectura"]
    dentro_de_una_hora = time.time() + 3600   # quedó de una AulaLista que se cerró a mitad de camino
    assert inicio.trabajos_en_curso(tmp_path, ahora=dentro_de_una_hora) == []
