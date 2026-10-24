"""Etapa 2 desde la página: crear curso, subir fuentes, convertirlas y ver sus pasajes."""

import pytest
from fastapi.testclient import TestClient

from app import cursos, servidor
from tests.fixtures import fuentes
from tests.unidad.test_fuentes import LectorSimulado

cliente = TestClient(servidor.app)


@pytest.fixture
def lector(monkeypatch):
    simulado = LectorSimulado(["Texto de la imagen"])
    monkeypatch.setattr(servidor, "lector_de_imagenes", lambda curso: simulado)
    return simulado


def test_nombre_del_curso_se_vuelve_carpeta_sin_tildes():
    assert cursos.identificador("Scrum Master con IA · Edición 2026") == "scrum-master-con-ia-edicion-2026"


def test_crear_curso_crea_su_carpeta(entorno):
    r = cliente.post("/cursos", data={"nombre": "Scrum Máster"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/cursos/scrum-master"
    assert (entorno["cursos"] / "scrum-master" / "fuentes").is_dir()
    assert "Scrum Máster" in cliente.get("/").text


def test_curso_repetido_avisa(entorno):
    cliente.post("/cursos", data={"nombre": "Scrum"})
    r = cliente.post("/cursos", data={"nombre": "scrum"})
    assert "Ya existe" in r.text


def test_curso_inexistente_o_reservado_da_404(entorno):
    assert cliente.get("/cursos/no-existe").status_code == 404
    assert cliente.get("/cursos/_sistema").status_code == 404


def test_subir_convertir_y_ver_pasajes(entorno, tmp_path, lector):
    cliente.post("/cursos", data={"nombre": "Scrum"})
    pdf = fuentes.pdf_con_texto(tmp_path / "norma.pdf").read_bytes()
    png = fuentes.imagen(tmp_path / "foto.png").read_bytes()

    r = cliente.post(
        "/cursos/scrum/fuentes",
        files=[("archivos", ("norma.pdf", pdf)), ("archivos", ("foto.png", png))],
    )
    # Subir convierte enseguida lo que no necesita IA. La imagen espera a que el profesor pida la lectura con IA.
    assert "Archivos guardados: 2. Fuentes convertidas: 1." in r.text
    assert "Una imagen o página escaneada se lee con IA cuando pulses «Leer con IA lo que falta»." in r.text
    assert "Espera la lectura con IA" in r.text and "sin convertir" not in r.text
    assert "Leer con IA lo que falta" in r.text and lector.llamadas == []

    r = cliente.get("/cursos/scrum/fuentes/norma.pdf")
    assert "página 2 · número impreso 43" in r.text
    assert "Scrum es gratuito." in r.text

    r = cliente.post("/cursos/scrum/convertir")
    assert "Fuentes leídas con IA: 1." in r.text
    assert "Revisa el texto leído por IA" in r.text and "Leer con IA lo que falta" not in r.text
    assert len(lector.llamadas) == 1

    r = cliente.post("/cursos/scrum/convertir")
    assert "No había nada nuevo que convertir." in r.text
    assert len(lector.llamadas) == 1


def test_formato_no_admitido_se_rechaza(entorno, lector):
    cliente.post("/cursos", data={"nombre": "Scrum"})
    r = cliente.post("/cursos/scrum/fuentes", files=[("archivos", ("virus.exe", b"x"))])
    assert "no se admite" in r.text
    assert not (entorno["cursos"] / "scrum" / "fuentes" / "virus.exe").exists()


def test_nombre_de_archivo_no_sale_de_la_carpeta(entorno, tmp_path, lector):
    cliente.post("/cursos", data={"nombre": "Scrum"})
    pdf = fuentes.pdf_con_texto(tmp_path / "n.pdf").read_bytes()
    cliente.post("/cursos/scrum/fuentes", files=[("archivos", ("..\\..\\fuera.pdf", pdf))])
    assert (entorno["cursos"] / "scrum" / "fuentes" / "fuera.pdf").exists()
    assert not (entorno["cursos"] / "fuera.pdf").exists()


def test_marcar_fuente_revisada_desde_la_pagina(entorno, tmp_path, lector):
    cliente.post("/cursos", data={"nombre": "Scrum"})
    png = fuentes.imagen(tmp_path / "foto.png").read_bytes()
    cliente.post("/cursos/scrum/fuentes", files=[("archivos", ("foto.png", png))])
    cliente.post("/cursos/scrum/convertir")

    assert "Marcar como revisada" in cliente.get("/cursos/scrum/fuentes/foto.png").text
    r = cliente.post("/cursos/scrum/fuentes/foto.png/revisada")
    assert "Revisaste el texto que leyó la IA." in r.text


def test_convertir_word_desde_la_pagina_usa_office_en_otro_hilo(entorno, tmp_path, lector):
    cliente.post("/cursos", data={"nombre": "Scrum"})
    docx = fuentes.word_dos_paginas(tmp_path / "silabo.docx").read_bytes()
    r = cliente.post("/cursos/scrum/fuentes", files=[("archivos", ("silabo.docx", docx))])
    assert "Fuentes convertidas: 1." in r.text
    assert "Segunda página del sílabo." in cliente.get("/cursos/scrum/fuentes/silabo.docx").text


def test_nombre_de_curso_largo_se_acorta_para_windows():
    assert len(cursos.identificador("Curso de " + "gestión " * 20)) <= 40


def test_un_pdf_con_paginas_escaneadas_se_usa_enseguida_y_avisa_lo_que_falta_leer(entorno, tmp_path, lector):
    cliente.post("/cursos", data={"nombre": "Scrum"})
    pdf = fuentes.pdf_escaneado(tmp_path / "e.pdf").read_bytes()
    r = cliente.post("/cursos/scrum/fuentes", files=[("archivos", ("e.pdf", pdf))])
    assert "Fuentes convertidas: 1." in r.text and "Convertida: 1 pasajes." in r.text
    assert "Una página o imagen por leer con IA." in r.text
    assert servidor._estado_de_fuentes(entorno["cursos"] / "scrum")["clase"] == "bien"   # con texto, ya sirve
    r = cliente.post("/cursos/scrum/convertir")
    assert "Fuentes leídas con IA: 1." in r.text and "por leer con IA" not in r.text
    assert len(lector.llamadas) == 1
