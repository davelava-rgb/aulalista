"""La interfaz muestra el estado de cada material, el siguiente paso y el costo antes de gastar."""

import json

from fastapi.testclient import TestClient

from app import servidor, tokens
from app.fichas import almacen
from app.materiales import comun
from tests.unidad.test_lectura import sesion  # noqa: F401

cliente = TestClient(servidor.app)


def _poner(carpeta, material, **datos):
    comun.actualizar(carpeta, 1, material, **datos)


def _registro(carpeta, *filas):
    with open(carpeta / "tokens.jsonl", "a", encoding="utf-8") as archivo:
        for etapa, sesion, costo in filas:
            archivo.write(json.dumps({"fecha": "2026-10-15T10:00:00", "curso": "scrum", "sesion": sesion,
                                      "material": "-", "etapa": etapa, "tokens_entrada": 1, "tokens_salida": 1,
                                      "costo_usd": costo}) + "\n")


def test_la_ultima_corrida_suma_solo_las_llamadas_seguidas_del_final(entorno):
    carpeta = entorno["cursos"] / "scrum"
    carpeta.mkdir(parents=True)
    _registro(carpeta, ("propuesta ficha curso", "-", 1.0), ("redacción", "S1", 5.0),
              ("propuesta ficha curso", "-", 0.25), ("propuesta ficha curso", "-", 0.5))
    assert tokens.ultima_corrida("scrum", "propuesta ficha curso") == {
        "llamadas": 2, "costo_usd": 0.75, "fecha": "2026-10-15T10:00:00"}
    assert tokens.ultima_corrida("scrum", "completar ficha") is None


def test_la_franja_muestra_los_materiales_el_siguiente_paso_y_la_evaluacion_como_etapa_posterior(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    assert 'aria-label="Materiales de la sesión"' in pagina
    for nombre in ("1. Lectura", "2. Diapositivas", "3. Laboratorio", "4. Evaluación y clave"):
        assert nombre in pagina
    assert "Etapa posterior" in pagina
    assert "Siguiente paso:" in pagina and "Genera la lectura." in pagina


def test_el_laboratorio_concuerda_en_masculino(sesion):  # noqa: F811
    _poner(sesion, "laboratorio", estado="aprobada", aprobada="2026-10-15T10:00:00")
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    assert "Aprobado por ti el 2026-10-15" in pagina and "Aprobada por ti" not in pagina
    assert "AulaLista lo reemplaza" in pagina


def test_el_estado_lleva_icono_color_y_palabra(sesion):  # noqa: F811
    _poner(sesion, "lectura", estado="con fallas")
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    assert '<span class="indicador error"><svg' in pagina and "Con fallas</span>" in pagina


def test_un_material_aprobado_desactualizado_no_se_ve_aprobado(sesion):  # noqa: F811
    datos = {"aprobada": "2026-10-15T10:00:00"}
    vista = servidor._situacion(servidor.MATERIALES["lectura"], {"estado": "aprobada", "desactualizado": True, **datos}, True)
    assert vista == {"clase": "error", "texto": "Desactualizada"}


def test_generar_de_nuevo_un_material_aprobado_pide_confirmacion(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    assert "data-confirmar=" not in pagina
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00")
    assert "data-confirmar=\"La lectura ya está aprobada." in cliente.get("/cursos/scrum/sesiones/1").text


def test_el_boton_generar_dice_lo_que_gasto_la_ultima_corrida(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    assert "Todavía no hay una corrida anterior para estimar el costo." in pagina
    _poner(sesion, "lectura", estado="verificada", corrida_desde=tokens.lineas("scrum"))
    with open(sesion / "tokens.jsonl", "a", encoding="utf-8") as archivo:
        archivo.write(json.dumps({"fecha": "x", "curso": "scrum", "sesion": "S1", "material": "lectura",
                                  "etapa": "redacción", "tokens_entrada": 1, "tokens_salida": 1, "costo_usd": 0.42}) + "\n")
    assert "La última corrida gastó 0.42 USD estimados (1 llamada)." in cliente.get("/cursos/scrum/sesiones/1").text


def test_la_tabla_del_curso_muestra_el_avance_de_cada_sesion(sesion):  # noqa: F811
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00")
    pagina = cliente.get("/cursos/scrum").text
    assert "1 de 3 aprobados" in pagina and "las diapositivas.</p>" in pagina


def test_la_entrega_resume_en_una_linea_y_pliega_los_detalles(sesion):  # noqa: F811
    entrega = {"pregunta": "¿Apruebas la lectura?", "secciones": [
        {"clave": "archivos", "titulo": "Archivos", "lineas": ["S1_Lectura.docx: la lectura."]},
        {"clave": "probe", "titulo": "Qué probé", "lineas": ["Algo."]},
        {"clave": "pendientes", "titulo": "Decisiones pendientes", "lineas": ["Una.", "Otra."]}]}
    _poner(sesion, "lectura", estado="con pendientes", entrega=entrega)
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    assert "1 archivo · 2 decisiones pendientes" in pagina
    assert '<details class="detalle">' in pagina and "Detalles de la entrega: qué probé</summary>" in pagina


def test_la_ficha_tiene_indice_aviso_de_cambios_y_consulta_la_propuesta_sin_recargar(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert 'aria-label="Secciones de la ficha"' in pagina and 'href="#seccion-1"' in pagina
    assert 'id="sin-guardar"' in pagina and "location.reload(), 5000" not in pagina
    assert cliente.get("/cursos/scrum/sesiones/1/ficha/propuesta").json() == {}


def test_guardar_una_ficha_confirmada_avisa_que_desactualiza_lo_generado(sesion):  # noqa: F811
    assert "lo ya generado queda desactualizado" not in cliente.get("/cursos/scrum/sesiones/1/ficha").text
    _poner(sesion, "lectura", estado="verificada")
    assert almacen.cargar(sesion, "sesion", 1)["confirmada"]
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert "lo ya generado queda desactualizado y hay que generarlo de nuevo: la lectura." in pagina


def test_los_bloques_llenos_se_pliegan_y_los_con_alertas_quedan_abiertos():
    campos = lambda valor, estado="": [{"valor": valor, "estado": estado}]  # noqa: E731
    secciones = [{"elementos": [{"repetible": True, "bloques": [
        {"numero": 1, "campos": campos("x")}, {"numero": 2, "campos": campos("", "falta definir")},
        {"numero": 3, "campos": campos("")}]}]}]
    vista = servidor._indice_de_secciones(secciones)
    assert [b["situacion"] for b in vista[0]["elementos"][0]["bloques"]] == ["lleno", "alerta", "vacio"]
    assert vista[0]["alertas"] == 1 and vista[0]["ancla"] == "seccion-1"


def test_el_inicio_muestra_el_gasto(entorno):
    pagina = cliente.get("/").text
    assert "Gasto total: 0 llamadas a Claude" in pagina


def test_todas_las_paginas_tienen_el_alternador_de_modo_claro_u_oscuro(entorno):
    pagina = cliente.get("/").text
    assert 'id="alternar-tema"' in pagina and '>Cambiar a modo oscuro</button>' in pagina
    css = (servidor.RAIZ / "web" / "estaticos" / "estilo.css").read_text(encoding="utf-8")
    assert ':root[data-tema="oscuro"]' in css and ':root:not([data-tema="claro"])' in css
