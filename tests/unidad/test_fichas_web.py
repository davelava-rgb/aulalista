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



def test_una_ficha_guardada_antes_no_muestra_falta_definir_en_campos_opcionales(curso):
    # Antes de la decisión 16, «Público» y «Empresa» eran obligatorios y quedaban marcados «Falta definir».
    ficha = datos.ficha("curso", {"curso.nombre": "Scrum Master con IA"})
    for campo_id in ("publico.quienes", "caso.empresa"):
        ficha["campos"][campo_id] = {"valor": "", "origen": "", "estado": "falta definir"}
    ficha["campos"]["curso.sesiones"] = {"valor": "", "origen": "", "estado": "falta definir"}
    almacen.guardar(curso, "curso", None, ficha)
    cargada = almacen.cargar(curso, "curso")
    assert cargada["campos"]["publico.quienes"]["estado"] == ""
    assert cargada["campos"]["caso.empresa"]["estado"] == ""
    assert cargada["campos"]["curso.sesiones"]["estado"] == "falta definir"   # este sigue obligatorio
    pagina = cliente.get("/cursos/scrum/ficha").text
    assert pagina.count('class="marca alerta">Falta definir') == 1
    assert "2. Público (obligatorio)" not in pagina and "Empresa o institución ficticia y rubro (obligatorio)" not in pagina


def test_los_temas_de_la_lectura_dicen_que_se_exigen_al_generarla(curso):
    almacen.guardar(curso, "curso", None, datos.ficha("curso", datos.CURSO))
    flujo.confirmar_curso(curso)
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert "Temas que debe cubrir (obligatorio para generar la lectura)" in pagina


# ---------- Propuesta automática al abrir la ficha (PLAN.md §0, decisión 17) ----------

def _esperar_hilos():
    import threading
    for hilo in [h for h in threading.enumerate() if h.daemon]:
        hilo.join(timeout=30)


def _propuesta_simulada(llamadas, falla=False):
    async def proponer(carpeta, curso, tipo, sesion=None, consulta=None):
        llamadas.append(tipo)
        if falla:
            raise RuntimeError("sin conexión")
        ficha = almacen.cargar(carpeta, tipo, sesion)
        ficha["campos"]["publico.quienes"] = {"valor": "Jefes de proyecto", "origen": "silabo.pdf", "estado": "propuesto"}
        almacen.guardar(carpeta, tipo, sesion, ficha, "propuesta desde las fuentes")
        return {"de_las_fuentes": 1, "propuestos": 1, "conflictos": 0, "descartados": 0}
    return proponer


def test_con_fuentes_la_ficha_se_propone_sola_una_vez(curso, monkeypatch):
    from tests.unidad.test_fichas import con_fuente
    con_fuente(curso)
    llamadas = []
    monkeypatch.setattr(flujo, "proponer", _propuesta_simulada(llamadas))
    primera = cliente.get("/cursos/scrum/ficha").text
    assert "Leyendo las fuentes y proponiendo la ficha" in primera
    _esperar_hilos()
    pagina = cliente.get("/cursos/scrum/ficha").text
    assert "AulaLista llenó la ficha desde las fuentes." in pagina
    assert "Jefes de proyecto" in pagina and "Aceptar lo propuesto y confirmar" in pagina
    cliente.get("/cursos/scrum/ficha")
    _esperar_hilos()
    assert llamadas == ["curso"]          # una sola vez: recargar no vuelve a gastar tokens


def test_sin_fuentes_la_ficha_no_se_propone_sola(curso, monkeypatch):
    llamadas = []
    monkeypatch.setattr(flujo, "proponer", _propuesta_simulada(llamadas))
    pagina = cliente.get("/cursos/scrum/ficha").text
    _esperar_hilos()
    assert llamadas == [] and 'id="propuesta-en-curso"' not in pagina
    assert flujo.estado_propuesta(curso, "curso") == {}


def test_mientras_se_propone_los_botones_esperan(curso):
    flujo.marcar_propuesta_en_curso(curso, "curso")
    pagina = cliente.get("/cursos/scrum/ficha").text
    assert 'id="propuesta-en-curso"' in pagina
    assert 'value="confirmar" class="secundario" disabled' in pagina


def test_si_la_propuesta_falla_la_pagina_lo_dice(curso, monkeypatch):
    from tests.unidad.test_fichas import con_fuente
    con_fuente(curso)
    monkeypatch.setattr(flujo, "proponer", _propuesta_simulada([], falla=True))
    cliente.get("/cursos/scrum/ficha")
    _esperar_hilos()
    pagina = cliente.get("/cursos/scrum/ficha").text
    assert "No se pudo proponer la ficha desde las fuentes: sin conexión" in pagina
    assert "Proponer desde las fuentes" in pagina          # el botón manual sigue disponible


def test_aceptar_lo_propuesto_confirma_la_ficha(curso):
    ficha = datos.ficha("curso", datos.CURSO)
    ficha["campos"]["caso.empresa"] = {"valor": "Comercial Los Volcanes", "origen": "deducido", "estado": "propuesto"}
    almacen.guardar(curso, "curso", None, ficha)
    formulario = {k: v for k, v in datos.CURSO.items()}
    r = cliente.post("/cursos/scrum/ficha", data={"accion": "aceptar", **formulario})
    assert "Ficha del curso confirmada." in r.text
    guardada = almacen.cargar(curso, "curso")
    assert guardada["confirmada"] is True
    assert guardada["campos"]["caso.empresa"]["estado"] == ""


def test_la_propuesta_llena_todo_salvo_identidad_visual_y_no_inventa_personas(curso):
    pedido = flujo.pedido_de_propuesta(curso, "curso", None, almacen.cargar(curso, "curso"))
    assert "Propón todos los campos de la lista" in pedido
    assert "una por capítulo o tema principal" in pedido
    assert "visual.principal" not in pedido and "modelos.aprobados" not in pedido
    assert "El docente y los\n  datos de contacto solo van si la fuente los dice tal cual" in pedido
    ficha = datos.ficha("curso", {})
    resumen = flujo.aplicar_propuesta(curso, ficha, {"campos": [
        {"id": "portada.docente", "valor": "Juan Pérez", "origen": "deducido", "literal": False},
        {"id": "visual.principal", "valor": "#123456", "origen": "deducido", "literal": False},
        {"id": "caso.empresa", "valor": "Comercial Los Volcanes", "origen": "deducido", "literal": False},
    ], "conflictos": []})
    assert resumen["propuestos"] == 1 and resumen["descartados"] == 2
    assert almacen.valor(ficha, "portada.docente") == "" and almacen.valor(ficha, "visual.principal") == ""


def test_un_estado_a_medio_escribir_no_rompe_la_pagina(curso):
    flujo.marcar_propuesta_en_curso(curso, "curso")
    ruta = almacen.ruta_ficha(curso, "curso").with_name("propuesta_curso.json")
    ruta.write_text("", encoding="utf-8")          # el instante en que el archivo se está escribiendo
    assert flujo.estado_propuesta(curso, "curso")["estado"] == "trabajando"
    assert cliente.get("/cursos/scrum/ficha").status_code == 200
