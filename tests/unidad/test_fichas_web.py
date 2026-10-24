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
    assert "¿El material habla en general o nombra una herramienta?" in r.text
    assert "Responde primero esta" in r.text   # las sesiones: el nombre ya es el que se dio al crear el curso


def test_guardar_con_datos_faltantes_guarda_sin_confirmar(curso):
    r = cliente.post("/cursos/scrum/ficha", data={"accion": "guardar", "curso.nombre": "Scrum Master con IA"})
    assert "Ficha guardada. Todavía no está confirmada." in r.text
    assert "Para confirmarla falta" in r.text
    assert "Falta «Sesiones. Una línea por sesión: número, título y alcance.»." in r.text
    assert almacen.valor(almacen.cargar(curso, "curso"), "curso.nombre") == "Scrum Master con IA"


def test_el_nombre_del_curso_es_el_que_dio_el_profesor_y_la_propuesta_no_lo_cambia(curso):
    ficha = almacen.cargar(curso, "curso")
    assert ficha["campos"]["curso.nombre"] == {"valor": "Scrum", "origen": "profesor", "estado": ""}
    resumen = flujo.aplicar_propuesta(curso, ficha, {"campos": [
        {"id": "curso.nombre", "valor": "Título del PDF", "origen": "deducido", "literal": False}], "conflictos": []})
    assert resumen["descartados"] == 1 and almacen.valor(ficha, "curso.nombre") == "Scrum"
    assert "curso.nombre" not in flujo.pedido_de_propuesta(curso, "curso", None, ficha)   # no se pide lo que está lleno


def test_guardar_una_pagina_abierta_antes_de_la_propuesta_no_borra_lo_propuesto(curso):
    # La página se abrió con la ficha vacía; mientras, la propuesta llenó campos que la página no muestra.
    base = cliente.get("/cursos/scrum/ficha").text.split('name="base" value="', 1)[1].split('"', 1)[0]
    ficha = almacen.cargar(curso, "curso")
    ficha["campos"]["curso.nombre"] = {"valor": "Nombre propuesto", "origen": "deducido", "estado": almacen.PROPUESTO}
    ficha["campos"]["publico.quienes"] = {"valor": "Jefes de proyecto", "origen": "deducido", "estado": almacen.PROPUESTO}
    almacen.guardar(curso, "curso", None, ficha, "propuesta desde las fuentes")
    cliente.post("/cursos/scrum/ficha", data={
        "accion": "guardar", "base": base.replace("&#34;", '"'),
        "curso.nombre": "Agilidad de Negocios", "curso.sesiones": "1. Dominios", "publico.quienes": ""})
    guardada = almacen.cargar(curso, "curso")
    assert almacen.valor(guardada, "curso.nombre") == "Agilidad de Negocios"      # lo que escribió el profesor
    assert almacen.valor(guardada, "curso.sesiones") == "1. Dominios"
    assert almacen.valor(guardada, "publico.quienes") == "Jefes de proyecto"      # lo propuesto que no tocó


def test_guardar_la_ficha_del_curso_completa_la_confirma_y_abre_las_sesiones(curso):
    r = cliente.post("/cursos/scrum/ficha", data={"accion": "guardar", **datos.CURSO})
    assert "Ficha del curso guardada y confirmada." in r.text
    assert almacen.cargar(curso, "curso")["confirmada"] is True
    pagina = cliente.get("/cursos/scrum").text
    assert "Agilidad y fundamentos de Scrum" in pagina
    assert "/cursos/scrum/sesiones/2/ficha" in pagina


def test_la_ficha_corta_de_la_sesion_se_llena_desde_la_del_curso_y_el_plan_va_plegado(curso):
    cliente.post("/cursos/scrum/ficha", data={"accion": "guardar", **datos.CURSO})
    ficha_curso = almacen.cargar(curso, "curso")
    texto = almacen.valor(ficha_curso, "curso.sesiones")
    ficha_curso["cobertura_sesiones"] = flujo.cobertura(
        [{"numero": 2, "paginas": [{"fuente": "guia.pdf", "desde": 4, "hasta": 9}]}], {"guia.pdf": list(range(1, 20))}, texto)
    almacen.guardar(curso, "curso", None, ficha_curso)
    pagina = cliente.get("/cursos/scrum/sesiones/2/ficha").text
    ficha = almacen.cargar(curso, "sesion", 2)
    assert almacen.valor(ficha, "sesion.numero_titulo") == "2. Roles de Scrum"
    assert almacen.valor(ficha, "sesion.alcance") == "responsabilidades"
    assert almacen.valor(ficha, "sesion.ya_vieron") == "Agilidad y fundamentos de Scrum"
    assert almacen.valor(ficha, "sesion.no_adelantar") == ""
    assert almacen.valor(ficha, "sesion.referencia") == "guia.pdf: páginas 4 a 9"
    assert ficha["campos"]["sesion.alcance"]["origen"] == flujo.DESDE_EL_CURSO
    # Lo que prepara AulaLista va plegado, después de la ficha corta, y no se pregunta.
    plan = pagina.index('<details class="plan-sesion"')
    assert pagina.index('id="t-seccion-1"') < pagina.index('id="t-seccion-6"') < plan < pagina.index('id="t-seccion-2"')
    preguntas = pagina.split('<section class="preguntas">', 1)[-1].split("</section>", 1)[0]
    assert "lectura." not in preguntas and "ejercicio." not in preguntas
    # Lo que el profesor cambió no se pisa al volver a abrir la ficha.
    ficha["campos"]["sesion.alcance"] = {"valor": "Solo el Scrum Master", "origen": "profesor", "estado": ""}
    almacen.guardar(curso, "sesion", 2, ficha)
    cliente.get("/cursos/scrum/sesiones/2/ficha")
    assert almacen.valor(almacen.cargar(curso, "sesion", 2), "sesion.alcance") == "Solo el Scrum Master"


def test_guardar_prepara_el_plan_vacio_con_ia_y_abrir_la_ficha_no_gasta(curso, entorno, monkeypatch):
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    cliente.post("/cursos/scrum/ficha", data={"accion": "guardar", **datos.CURSO})
    monkeypatch.setattr(flujo, "proponer", lambda *a, **k: pytest.fail("abrir la ficha no debe gastar"))
    cliente.get("/cursos/scrum/sesiones/1/ficha")

    llamadas = []
    plan ={c: v for c, v in datos.SESION.items() if c in flujo.plantillas.ids_del_plan()}

    async def proponer(carpeta, nombre, tipo, sesion, consulta=None):
        llamadas.append("propuesta")
        ficha = almacen.cargar(carpeta, "sesion", sesion)
        for campo, texto in plan.items():
            ficha["campos"][campo] = {"valor": texto, "origen": "deducido", "estado": almacen.PROPUESTO}
        almacen.guardar(carpeta, "sesion", sesion, ficha, "propuesta")
        return {"de_las_fuentes": 0, "propuestos": len(plan), "conflictos": 0, "descartados": 0}

    monkeypatch.setattr(flujo, "proponer", proponer)
    revisor = consulta_simulada(structured_output={"ejercicios": [
        {"numero": n, "funciona_solo": True, "sin_llenar_a_mano": True, "motivo": "Cumple"} for n in (1, 2, 3)]})
    original = flujo.confirmar_sesion
    monkeypatch.setattr(flujo, "confirmar_sesion", lambda c, cu, s, consulta=None: original(c, cu, s, consulta=revisor))
    corta = {c: v for c, v in datos.SESION.items() if c not in plan}
    r = cliente.post("/cursos/scrum/sesiones/1/ficha", data={"accion": "guardar", **corta})
    assert llamadas == ["propuesta"]
    assert f"Preparé el plan de la sesión: {len(plan)} datos." in r.text and "Ficha de la sesión guardada y confirmada." in r.text
    ficha = almacen.cargar(curso, "sesion", 1)
    assert ficha["confirmada"] is True
    assert not any((d or {}).get("estado") == almacen.PROPUESTO for d in ficha["campos"].values())
    # En la sesión no hay botones aparte para aceptar ni para proponer.
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert 'value="aceptar"' not in pagina and 'value="proponer"' not in pagina


def test_guardar_sin_lo_obligatorio_de_la_ficha_corta_no_gasta(curso, monkeypatch):
    cliente.post("/cursos/scrum/ficha", data={"accion": "guardar", **datos.CURSO})
    monkeypatch.setattr(flujo, "proponer", lambda *a, **k: pytest.fail("no debe gastar"))
    r = cliente.post("/cursos/scrum/sesiones/5/ficha", data={"accion": "guardar"})
    assert "Todavía no está confirmada." in r.text and "Falta «Alcance»." in r.text


def test_la_ficha_de_la_sesion_espera_a_la_del_curso(curso):
    assert cliente.get("/cursos/scrum/sesiones/1/ficha").status_code == 409


def test_guardar_la_ficha_de_la_sesion_completa_la_confirma(curso, entorno, monkeypatch):
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    cliente.post("/cursos/scrum/ficha", data={"accion": "guardar", **datos.CURSO})
    revisor = consulta_simulada(structured_output={"ejercicios": [
        {"numero": n, "funciona_solo": True, "sin_llenar_a_mano": True, "motivo": "Cumple"} for n in (1, 2, 3)]})
    original = flujo.confirmar_sesion
    monkeypatch.setattr(flujo, "confirmar_sesion", lambda c, cu, s, consulta=None: original(c, cu, s, consulta=revisor))
    r = cliente.post("/cursos/scrum/sesiones/1/ficha", data={"accion": "guardar", **datos.SESION})
    assert "Ficha de la sesión guardada y confirmada. Se escribió verificacion.json." in r.text
    assert (curso / "sesiones" / "S1" / "verificacion.json").exists()
    assert "Confirmada" in cliente.get("/cursos/scrum").text


def test_al_abrir_de_nuevo_la_ficha_muestra_por_que_sigue_sin_confirmar(curso, entorno, monkeypatch):
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    cliente.post("/cursos/scrum/ficha", data={"accion": "guardar", **datos.CURSO})
    revisor = consulta_simulada(structured_output={"ejercicios": [
        {"numero": 1, "funciona_solo": True, "sin_llenar_a_mano": False, "motivo": "Falta el cargo."}]})
    original = flujo.confirmar_sesion
    monkeypatch.setattr(flujo, "confirmar_sesion", lambda c, cu, s, consulta=None: original(c, cu, s, consulta=revisor))
    corrector = consulta_simulada(structured_output={"campos": [{"id": "ejercicio.1.archivo", "valor": "Otro Word"}]})
    corregir = flujo.corregir_ejercicios
    monkeypatch.setattr(flujo, "corregir_ejercicios",
                        lambda c, cu, s, consulta=None: corregir(c, cu, s, consulta=corrector))
    r = cliente.post("/cursos/scrum/sesiones/1/ficha", data={"accion": "guardar", **datos.SESION})
    # Guardar corrige una sola vez; lo que la revisión siga encontrando queda para el profesor (decisión 22).
    assert "Corregí el ejercicio 1." in r.text and "Todavía no está confirmada." in r.text
    assert len(corrector.llamadas) == 1
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert "Para confirmarla falta" in pagina
    assert "Ejercicio 1: hay que llenar algo a mano. Falta el cargo." in pagina
    # Si el profesor cambia los ejercicios, el aviso viejo ya no se muestra.
    ficha = almacen.cargar(curso, "sesion", 1)
    almacen.aplicar_formulario(ficha, {"ejercicio.1.archivo": "Word con seis situaciones y el cargo de cada persona"})
    almacen.guardar(curso, "sesion", 1, ficha, "editada por el profesor")
    assert "Para confirmarla falta" not in cliente.get("/cursos/scrum/sesiones/1/ficha").text


def test_el_formulario_guarda_el_archivo_de_practica_de_cada_ejercicio(curso):
    cliente.post("/cursos/scrum/ficha", data={"accion": "guardar", **datos.CURSO})
    cliente.post("/cursos/scrum/sesiones/1/ficha", data={"accion": "guardar", "ejercicio.1.archivo": "Excel con usuarios",
                                                          "pregunta.1.archivo": "Word con un memorando"})
    ficha = almacen.cargar(curso, "sesion", 1)
    assert almacen.valor(ficha, "ejercicio.1.archivo") == "Excel con usuarios"
    assert almacen.valor(ficha, "pregunta.1.archivo") == "Word con un memorando"


def test_guardar_corrige_los_ejercicios_marcados_y_confirma(curso, entorno, monkeypatch):
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    cliente.post("/cursos/scrum/ficha", data={"accion": "guardar", **datos.CURSO})
    con_problema = consulta_simulada(structured_output={"ejercicios": [
        {"numero": 2, "funciona_solo": True, "sin_llenar_a_mano": False, "motivo": "Falta el cargo."}]})
    sin_problemas = consulta_simulada(structured_output={"ejercicios": [
        {"numero": n, "funciona_solo": True, "sin_llenar_a_mano": True, "motivo": "Cumple"} for n in (1, 2, 3)]})
    revisores = [con_problema, sin_problemas]
    original = flujo.confirmar_sesion
    monkeypatch.setattr(flujo, "confirmar_sesion",
                        lambda c, cu, s, consulta=None: original(c, cu, s, consulta=revisores.pop(0)))
    corrector = consulta_simulada(structured_output={"campos": [
        {"id": "ejercicio.2.archivo", "valor": "Word con seis situaciones y el cargo de cada persona (propuesto)"},
        {"id": "ejercicio.1.archivo", "valor": "No se toca: el ejercicio 1 no tiene problemas"},
        {"id": "sesion.alcance", "valor": "Tampoco se toca"}]})
    corregir = flujo.corregir_ejercicios
    monkeypatch.setattr(flujo, "corregir_ejercicios",
                        lambda c, cu, s, consulta=None: corregir(c, cu, s, consulta=corrector))
    r = cliente.post("/cursos/scrum/sesiones/1/ficha", data={"accion": "guardar", **datos.SESION})
    assert "Corregí el ejercicio 2." in r.text
    assert "Ficha de la sesión guardada y confirmada." in r.text
    ficha = almacen.cargar(curso, "sesion", 1)
    assert ficha["confirmada"] is True
    # Lo corregido queda aceptado: el profesor no revisa el plan antes de redactar (decisión 54).
    assert ficha["campos"]["ejercicio.2.archivo"] == {
        "valor": "Word con seis situaciones y el cargo de cada persona", "origen": "deducido", "estado": ""}
    assert almacen.valor(ficha, "ejercicio.1.archivo") == datos.SESION["ejercicio.1.archivo"]
    assert almacen.valor(ficha, "sesion.alcance") == datos.SESION["sesion.alcance"]
    assert 'value="corregir_ejercicios"' not in r.text


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
    assert "Temas que debe cubrir (obligatorio para generar la lectura si no hay material de referencia)" in pagina


# ---------- La propuesta desde las fuentes, solo con su botón (PLAN.md §0, decisión 17) ----------

def _propuesta_simulada(llamadas):
    async def proponer(carpeta, curso, tipo, sesion=None, consulta=None):
        llamadas.append(tipo)
        ficha = almacen.cargar(carpeta, tipo, sesion)
        ficha["campos"]["publico.quienes"] = {"valor": "Jefes de proyecto", "origen": "silabo.pdf", "estado": "propuesto"}
        almacen.guardar(carpeta, tipo, sesion, ficha, "propuesta desde las fuentes")
        return {"de_las_fuentes": 1, "propuestos": 1, "conflictos": 0, "descartados": 0}
    return proponer


def test_abrir_la_ficha_del_curso_con_fuentes_no_gasta(curso, monkeypatch):
    from tests.unidad.test_fichas import con_fuente
    con_fuente(curso)
    monkeypatch.setattr(flujo, "proponer", lambda *a, **k: pytest.fail("abrir la ficha no debe gastar"))
    pagina = cliente.get("/cursos/scrum/ficha").text
    assert 'value="proponer"' in pagina and "Proponer desde las fuentes" in pagina
    assert almacen.valor(almacen.cargar(curso, "curso"), "publico.quienes") == ""


def test_el_boton_proponer_llena_la_ficha_desde_las_fuentes(curso, monkeypatch):
    from tests.unidad.test_fichas import con_fuente
    con_fuente(curso)
    llamadas = []
    monkeypatch.setattr(flujo, "proponer", _propuesta_simulada(llamadas))
    pagina = cliente.post("/cursos/scrum/ficha", data={"accion": "proponer"}).text
    assert llamadas == ["curso"]
    assert "Datos tomados de las fuentes: 1." in pagina
    assert "Jefes de proyecto" in pagina and "Aceptar lo propuesto y guardar" in pagina


# ---------- Guardar confirma y botones «Completar» (PLAN.md §0, decisión 28) ----------

def test_la_ficha_no_tiene_boton_confirmar(curso):
    pagina = cliente.get("/cursos/scrum/ficha").text
    assert 'value="confirmar"' not in pagina and "Confirmar ficha" not in pagina
    assert 'value="guardar"' in pagina


def test_guardar_una_ficha_confirmada_sin_cambios_no_desactualiza_materiales(curso, monkeypatch):
    cliente.post("/cursos/scrum/ficha", data={"accion": "guardar", **datos.CURSO})
    llamadas = []
    monkeypatch.setattr(flujo, "confirmar_curso", lambda c: llamadas.append(c))
    r = cliente.post("/cursos/scrum/ficha", data={"accion": "guardar", **datos.CURSO})
    assert "Ficha guardada. Sigue confirmada." in r.text and llamadas == []


def test_la_ficha_del_curso_tiene_horas_numero_de_sesiones_y_tres_botones_completar(curso):
    pagina = cliente.get("/cursos/scrum/ficha").text
    assert 'id="curso.horas"' in pagina and 'type="number"' in pagina
    assert 'id="curso.numero_sesiones"' in pagina
    for clave in ("sesiones", "caso", "datos"):
        assert f'value="completar.{clave}"' in pagina
    almacen.guardar(curso, "curso", None, datos.ficha("curso", datos.CURSO))
    flujo.confirmar_curso(curso)
    assert 'value="completar.' not in cliente.get("/cursos/scrum/sesiones/1/ficha").text


def test_completar_desde_la_pagina_llena_lo_vacio_con_lo_que_se_escribio(curso, monkeypatch):
    vistos = []

    async def completar(carpeta, nombre, clave, consulta=None):
        vistos.append((clave, almacen.valor(almacen.cargar(carpeta, "curso"), "curso.numero_sesiones")))
        return "Propuse «Sesiones». Revisa lo marcado «Propuesto» y guarda."
    monkeypatch.setattr(flujo, "completar", completar)
    r = cliente.post("/cursos/scrum/ficha", data={"accion": "completar.sesiones", "curso.nombre": "Excel",
                                                  "curso.numero_sesiones": "4"})
    assert "Propuse «Sesiones»." in r.text
    assert vistos == [("sesiones", "4")]   # lo escrito se guarda antes de completar


def test_al_abrir_la_ficha_de_la_sesion_se_dice_que_se_llena_sola(curso):
    cliente.post("/cursos/scrum/ficha", data={"accion": "guardar", **datos.CURSO})
    pagina = cliente.get("/cursos/scrum/sesiones/2/ficha").text
    assert ("AulaLista llenó «Número y título», «Alcance» y «Lo que los alumnos ya vieron en sesiones anteriores» "
            "con la ficha del curso. Revisa esos campos antes de guardar: cámbialos si hace falta.") in pagina
    assert pagina.count('<span class="marca">Tomado de la ficha del curso</span>') == 3
    # La segunda vez no hay nada nuevo que llenar: no se repite el aviso.
    assert "AulaLista llenó" not in cliente.get("/cursos/scrum/sesiones/2/ficha").text


def test_las_paginas_escritas_en_la_linea_de_la_sesion_pasan_a_su_ficha(curso):
    sesiones = datos.CURSO["curso.sesiones"].replace(
        "2. Roles de Scrum: responsabilidades", "2. Roles de Scrum: responsabilidades (guia.pdf: páginas 4 a 9, 12 y 15)")
    cliente.post("/cursos/scrum/ficha", data={"accion": "guardar", **datos.CURSO, "curso.sesiones": sesiones})
    cliente.get("/cursos/scrum/sesiones/2/ficha")
    ficha = almacen.cargar(curso, "sesion", 2)
    assert almacen.valor(ficha, "sesion.numero_titulo") == "2. Roles de Scrum"
    assert almacen.valor(ficha, "sesion.alcance") == "responsabilidades"
    assert almacen.valor(ficha, "sesion.referencia") == "guia.pdf: páginas 4 a 9, 12 y 15"
