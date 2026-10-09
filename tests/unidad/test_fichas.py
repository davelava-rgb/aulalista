"""Etapa 4: fichas con los campos de la skill, edición con versiones, propuesta y confirmación."""

import asyncio
import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

from app.fichas import almacen, flujo, plantillas, verificacion
from app.fuentes import convertir
from tests.conftest import consulta_simulada
from tests.fixtures import fichas as datos
from tests.fixtures import fuentes as archivos

RAIZ = Path(__file__).resolve().parents[2]
SKILL = (RAIZ / ".claude" / "skills" / "material-de-clase" / "SKILL.md").read_text(encoding="utf-8")


def correr(coro):
    return asyncio.run(coro)


@pytest.fixture
def curso(tmp_path):
    carpeta = tmp_path / "curso"
    (carpeta / "fuentes").mkdir(parents=True)
    return carpeta


def con_fuente(curso, nombre="silabo.pdf"):
    """Sílabo convertido a texto, sin IA."""
    import pymupdf
    documento = pymupdf.open()
    pagina = documento.new_page()
    pagina.insert_text((72, 72), "Scrum Master con IA", fontsize=12)
    pagina.insert_text((72, 100), "Docente: jefe de capacitación", fontsize=12)
    documento.save(curso / "fuentes" / nombre)
    correr(convertir.convertir_curso(curso, None))


def ficha_curso_confirmada(curso):
    almacen.guardar(curso, "curso", None, datos.ficha("curso", datos.CURSO))
    flujo.confirmar_curso(curso)


def revisor_sin_problemas():
    return consulta_simulada(structured_output={"ejercicios": [
        {"numero": n, "funciona_solo": True, "sin_llenar_a_mano": True, "motivo": "Cumple"} for n in (1, 2, 3)]})


# ---------- Plantillas: los campos exactos de la skill ----------

@pytest.mark.parametrize("tipo, indice", [("curso", 0), ("sesion", 1)])
def test_la_ficha_vacia_es_igual_a_la_plantilla_de_la_skill(tipo, indice):
    plantilla = re.findall(r"```\n(FICHA DE.*?)```", SKILL, re.S)[indice]
    assert plantillas.renderizar(tipo, {}) == plantilla


@pytest.mark.parametrize("tipo", ["curso", "sesion"])
def test_el_formulario_tiene_todos_los_campos(tipo):
    en_formulario = set()
    for seccion in plantillas.vista(tipo, {}):
        for e in seccion["elementos"]:
            if e.get("repetible"):
                en_formulario |= {c["id"] for b in e["bloques"] for c in b["campos"]}
            elif e.get("grupo"):
                en_formulario |= {c["id"] for c in e["campos"]}
            else:
                en_formulario.add(e["id"])
    assert en_formulario == almacen.ids_validos(tipo)


def test_la_ficha_llena_conserva_las_etiquetas_y_anota_el_origen(curso):
    ficha = datos.ficha("sesion", datos.SESION)
    ficha["campos"]["sesion.alcance"] = {"valor": "Pilares", "origen": "silabo.pdf", "estado": "propuesto"}
    ficha["campos"]["sesion.ya_vieron"] = {"valor": "", "origen": "", "estado": "falta definir"}
    ficha["campos"]["sesion.no_adelantar"] = {"valor": "", "origen": "", "estado": "conflicto",
                                              "versiones": [{"valor": "Roles", "origen": "a.pdf"}, {"valor": "Eventos", "origen": "b.pdf"}]}
    almacen.guardar(curso, "sesion", 1, ficha)
    md = almacen.ruta_ficha(curso, "sesion", 1, ".md").read_text(encoding="utf-8")
    assert "- Alcance (obligatorio): Pilares (propuesto) (fuente: silabo.pdf)\n" in md
    assert "- Lo que los alumnos ya vieron en sesiones anteriores: Falta definir\n" in md
    assert "Conflicto: «Roles» (a.pdf) / «Eventos» (b.pdf)" in md
    assert "- Ejercicio 3 · Área: Recursos Humanos\n" in md
    assert "  Pregunta 2 · Concepto que evalúa: Pilares de Scrum\n" in md
    assert "- Ejercicio 4 · Área" not in md  # los bloques vacíos no se escriben


# ---------- Edición y versiones ----------

def test_lo_que_escribe_el_profesor_queda_con_su_origen():
    ficha = datos.ficha("curso", {})
    ficha["campos"]["curso.idioma"] = {"valor": "Español", "origen": "silabo.pdf", "estado": ""}
    ficha["confirmada"] = True
    cambio = almacen.aplicar_formulario(ficha, {"curso.nombre": "Scrum", "curso.idioma": "Español", "otro": "x"})
    assert cambio is True
    assert ficha["campos"]["curso.nombre"] == {"valor": "Scrum", "origen": "profesor", "estado": ""}
    assert ficha["campos"]["curso.idioma"]["origen"] == "silabo.pdf"  # sin cambios, conserva su fuente
    assert "otro" not in ficha["campos"]
    assert ficha["confirmada"] is False  # editar una ficha confirmada la deja sin confirmar


def test_sin_cambios_la_ficha_sigue_confirmada():
    ficha = datos.ficha("curso", {"curso.nombre": "Scrum"}, confirmada=True)
    assert almacen.aplicar_formulario(ficha, {"curso.nombre": "Scrum\r\n"}) is False
    assert ficha["confirmada"] is True


def test_el_profesor_elige_una_version_del_conflicto():
    ficha = datos.ficha("curso", {})
    ficha["campos"]["caso.moneda"] = {"valor": "", "origen": "", "estado": "conflicto",
                                      "versiones": [{"valor": "Soles", "origen": "a.pdf"}, {"valor": "Dólares", "origen": "b.pdf"}]}
    almacen.aplicar_formulario(ficha, {"caso.moneda": "", "elegir.caso.moneda": "1"})
    assert ficha["campos"]["caso.moneda"] == {"valor": "Dólares", "origen": "b.pdf", "estado": ""}


def test_cada_guardado_deja_una_version_que_se_puede_recuperar(curso):
    almacen.guardar(curso, "curso", None, datos.ficha("curso", {"curso.nombre": "Primera"}), "primera")
    almacen.guardar(curso, "curso", None, datos.ficha("curso", {"curso.nombre": "Segunda"}, confirmada=True), "segunda")
    versiones = almacen.listar_versiones(curso, "curso")
    assert [v["motivo"] for v in versiones] == ["segunda", "primera"]
    restaurada = almacen.restaurar(curso, "curso", None, versiones[1]["archivo"])
    assert almacen.valor(restaurada, "curso.nombre") == "Primera"
    assert almacen.cargar(curso, "curso")["confirmada"] is False
    assert len(almacen.listar_versiones(curso, "curso")) == 3


def test_no_se_puede_restaurar_fuera_de_la_carpeta_de_versiones(curso):
    with pytest.raises(FileNotFoundError):
        almacen.restaurar(curso, "curso", None, "../../ficha_del_curso.json")


# ---------- Revisión antes de confirmar ----------

def test_ficha_del_curso_sin_obligatorios_no_se_confirma(curso):
    almacen.guardar(curso, "curso", None, datos.ficha("curso", {"curso.nombre": "Scrum"}))
    with pytest.raises(almacen.FichaIncompleta) as error:
        flujo.confirmar_curso(curso)
    assert "Falta «Sesiones. Una línea por sesión: número, título y alcance.»." in error.value.errores
    assert "Falta «Quiénes son»." in error.value.errores  # la sección «Público» es obligatoria


def test_ficha_de_la_sesion_revisa_bloques_ejercicios_estaciones_y_preguntas():
    valores = dict(datos.SESION)
    valores.pop("lectura.bloque.2")
    valores.pop("ejercicio.3.area"); valores.pop("ejercicio.3.accion"); valores.pop("ejercicio.3.entregable")
    valores.pop("ejercicio.3.archivo"); valores.pop("ejercicio.3.problema"); valores.pop("ejercicio.3.respuesta")
    valores.pop("ejercicio.2.problema")
    valores["practica.estaciones"] = "Una\nDos"
    valores.pop("pregunta.1.respuesta")
    lista = almacen.errores(datos.ficha("sesion", valores))
    assert "La lectura necesita de 2 a 4 bloques." in lista
    assert "El laboratorio necesita de 3 a 5 ejercicios; tiene 2." in lista
    assert "Ejercicio 2: falta el problema que trae a propósito." in lista
    assert "La práctica necesita de 5 a 7 estaciones, una por línea; tiene 2." in lista
    assert "Pregunta 1: falta la respuesta correcta." in lista


def test_si_la_sesion_no_produce_un_material_no_se_exigen_sus_datos():
    valores = {k: v for k, v in datos.SESION.items() if not k.startswith(("ejercicio.", "pregunta.", "practica."))}
    valores["materiales.cuales"] = "Lectura y diapositivas"
    assert almacen.errores(datos.ficha("sesion", valores)) == []


def test_como_maximo_cuatro_preguntas_por_vez_y_primero_las_obligatorias():
    ficha = datos.ficha("curso", {})
    ficha["campos"]["caso.moneda"] = {"valor": "Soles", "origen": "deducido", "estado": "propuesto"}
    preguntas = almacen.preguntas_pendientes(ficha)
    assert len(preguntas) == 4
    assert all(p["motivo"].startswith("Es obligatorio") for p in preguntas)
    todas = almacen.preguntas_pendientes(ficha, maximo=100)
    assert todas[-1]["id"] == "caso.moneda"


# ---------- Propuesta desde las fuentes ----------

def test_la_propuesta_llena_solo_campos_vacios_y_comprueba_lo_literal(curso):
    con_fuente(curso)
    ficha = datos.ficha("curso", {"curso.idioma": "Español"})
    propuesta = {"campos": [
        {"id": "curso.nombre", "valor": "Scrum Master con IA", "origen": "silabo.pdf", "literal": True},
        {"id": "portada.docente", "valor": "Jefe de capacitación", "origen": "silabo.pdf.jsonl", "literal": True},
        {"id": "caso.empresa", "valor": "Comercial Los Volcanes", "origen": "silabo.pdf", "literal": True},
        {"id": "caso.moneda", "valor": "Soles", "origen": "otro.pdf", "literal": True},
        {"id": "curso.idioma", "valor": "Inglés", "origen": "silabo.pdf", "literal": True},
        {"id": "no.existe", "valor": "x", "origen": "silabo.pdf", "literal": True},
    ], "conflictos": []}
    resumen = flujo.aplicar_propuesta(curso, ficha, propuesta)
    campos = ficha["campos"]
    assert campos["curso.nombre"] == {"valor": "Scrum Master con IA", "origen": "silabo.pdf", "estado": ""}
    assert campos["portada.docente"]["estado"] == ""  # se encontró tal cual, sin importar mayúsculas
    assert campos["caso.empresa"] == {"valor": "Comercial Los Volcanes", "origen": "silabo.pdf", "estado": "propuesto"}
    assert campos["caso.moneda"] == {"valor": "Soles", "origen": "deducido", "estado": "propuesto"}
    assert campos["curso.idioma"]["valor"] == "Español"  # no pisa lo que ya estaba
    assert campos["publico.quienes"]["estado"] == "falta definir"
    assert resumen == {"de_las_fuentes": 2, "propuestos": 2, "conflictos": 0, "descartados": 2}


def test_dos_versiones_distintas_quedan_como_conflicto(curso):
    con_fuente(curso, "a.pdf")
    con_fuente(curso, "b.pdf")
    ficha = datos.ficha("curso", {})
    flujo.aplicar_propuesta(curso, ficha, {"campos": [], "conflictos": [
        {"id": "caso.moneda", "versiones": [{"valor": "Soles", "origen": "a.pdf"}, {"valor": "Dólares", "origen": "b.pdf"}]},
        {"id": "caso.areas", "versiones": [{"valor": "Ventas", "origen": "a.pdf"}, {"valor": "Ventas", "origen": "b.pdf"}]},
    ]})
    assert ficha["campos"]["caso.moneda"]["estado"] == "conflicto"
    assert "caso.areas" not in ficha["campos"]  # dos versiones iguales no son un conflicto
    assert almacen.preguntas_pendientes(ficha)[0]["motivo"].startswith("Es obligatorio")
    assert "Elige la versión que vale en «Moneda y país de los casos»." in almacen.errores(ficha)


def test_una_fuente_leida_por_ia_sin_revisar_no_se_usa(curso):
    archivos.imagen(curso / "fuentes" / "foto.png", "Scrum Master con IA")

    async def lector(*_):
        return ["Scrum Master con IA"]

    correr(convertir.convertir_curso(curso, lector))
    assert verificacion.fuentes_utilizables(curso) == []
    convertir.marcar_revisada(curso, "foto.png")
    assert verificacion.fuentes_utilizables(curso) == ["foto.png"]


def test_proponer_usa_solo_lectura_y_busqueda_en_las_fuentes(entorno, curso):
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    con_fuente(curso)
    consulta = consulta_simulada(structured_output={"campos": [
        {"id": "curso.nombre", "valor": "Scrum Master con IA", "origen": "silabo.pdf", "literal": True}], "conflictos": []})
    resumen = correr(flujo.proponer(curso, "curso-x", "curso", consulta=consulta))
    opciones = consulta.llamadas[0]["options"]
    assert opciones.tools == ["Read", "Grep", "Glob"] == opciones.allowed_tools
    assert opciones.permission_mode == "dontAsk"
    assert Path(opciones.cwd) == curso / "fuentes_texto"
    assert "- curso.nombre: Nombre del curso (obligatorio)" in consulta.llamadas[0]["prompt"]
    assert resumen["de_las_fuentes"] == 1
    assert almacen.cargar(curso, "curso")["campos"]["curso.nombre"]["origen"] == "silabo.pdf"


def test_proponer_sin_fuentes_no_gasta_tokens_y_marca_lo_que_falta(curso):
    consulta = consulta_simulada()
    resumen = correr(flujo.proponer(curso, "c", "curso", consulta=consulta))
    assert resumen["sin_fuentes"] is True and consulta.llamadas == []
    assert almacen.cargar(curso, "curso")["campos"]["curso.nombre"]["estado"] == "falta definir"


def test_la_ficha_de_la_sesion_no_se_propone_sin_la_del_curso(curso):
    with pytest.raises(flujo.FichaDelCursoSinConfirmar):
        correr(flujo.proponer(curso, "c", "sesion", 1, consulta=consulta_simulada()))


# ---------- Confirmación, verificacion.json y materiales desactualizados ----------

def cargar_verificador():
    ruta = RAIZ / ".claude" / "skills" / "material-de-clase" / "scripts" / "verificar.py"
    especificacion = importlib.util.spec_from_file_location("verificar", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    sys.modules["verificar"] = modulo
    especificacion.loader.exec_module(modulo)
    return modulo


def test_confirmar_la_sesion_escribe_un_verificacion_json_valido(entorno, curso):
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    con_fuente(curso)
    ficha_curso_confirmada(curso)
    almacen.guardar(curso, "sesion", 1, datos.ficha("sesion", datos.SESION))
    correr(flujo.confirmar_sesion(curso, "c", 1, consulta=revisor_sin_problemas()))

    ruta = almacen.carpeta_sesion(curso, 1) / "verificacion.json"
    contenido = json.loads(ruta.read_text(encoding="utf-8"))
    assert contenido["datos_fijos"][:2] == [
        {"etiqueta": "Fecha de referencia", "valor": "lunes 5 de octubre de 2026"},
        {"etiqueta": "Duración de cada Sprint", "valor": "dos semanas"},
    ]
    assert contenido["vocabulario"][0] == {"concepto": "Manifiesto Ágil", "orden": 1, "variantes": ["Agile", "manifiesto agile"]}
    assert contenido["nunca_se_incluye"] == ["objetivos de aprendizaje", "requisitos previos", "glosario", "glosarios"]
    assert contenido["fuentes"][0]["texto"] == "../../fuentes_texto/silabo.pdf.jsonl"
    configuracion = cargar_verificador().leer_configuracion(ruta)  # el verificador lo acepta tal cual
    assert configuracion.fuentes[0].nombre == "silabo.pdf"
    assert almacen.puede_empezar_material(curso, 1) is True


def test_sin_ficha_confirmada_no_empieza_ningun_material(curso):
    assert almacen.puede_empezar_material(curso, 1) is False
    ficha_curso_confirmada(curso)
    almacen.guardar(curso, "sesion", 1, datos.ficha("sesion", datos.SESION))
    assert almacen.puede_empezar_material(curso, 1) is False


def test_la_revision_de_ejercicios_bloquea_y_no_se_repite_si_nada_cambia(entorno, curso):
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    ficha_curso_confirmada(curso)
    almacen.guardar(curso, "sesion", 1, datos.ficha("sesion", datos.SESION))
    revisor = consulta_simulada(structured_output={"ejercicios": [
        {"numero": 2, "funciona_solo": False, "sin_llenar_a_mano": True, "motivo": "Usa la tabla del ejercicio 1."}]})
    for _ in range(2):
        with pytest.raises(almacen.FichaIncompleta) as error:
            correr(flujo.confirmar_sesion(curso, "c", 1, consulta=revisor))
        assert error.value.errores == ["Ejercicio 2: no funciona solo. Usa la tabla del ejercicio 1."]
    assert len(revisor.llamadas) == 1
    assert almacen.cargar(curso, "sesion", 1)["confirmada"] is False


def test_cambiar_la_ficha_del_curso_actualiza_las_sesiones_y_desactualiza_materiales(entorno, curso):
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    ficha_curso_confirmada(curso)
    almacen.guardar(curso, "sesion", 1, datos.ficha("sesion", datos.SESION))
    correr(flujo.confirmar_sesion(curso, "c", 1, consulta=revisor_sin_problemas()))
    almacen.guardar_estado(curso, 1, {"materiales": {"lectura": {"estado": "aprobado", "desactualizado": False}}})

    ficha = almacen.cargar(curso, "curso")
    almacen.aplicar_formulario(ficha, {"datos.fecha": "lunes 12 de octubre de 2026"})
    almacen.guardar(curso, "curso", None, ficha)
    resultado = flujo.confirmar_curso(curso)

    assert resultado["desactualizados"] == {1: ["lectura"]}
    assert almacen.cargar_estado(curso, 1)["materiales"]["lectura"]["desactualizado"] is True
    contenido = json.loads((almacen.carpeta_sesion(curso, 1) / "verificacion.json").read_text(encoding="utf-8"))
    assert contenido["datos_fijos"][0]["valor"] == "lunes 12 de octubre de 2026"


def test_lineas_de_datos_fijos_sin_formato_se_informan():
    ficha = datos.ficha("curso", {"datos.fijos": "Moneda: soles\nLos pedidos se recogen en tienda"})
    fijos, sin_formato = almacen.datos_fijos(ficha)
    assert fijos == [{"etiqueta": "Moneda", "valor": "soles"}]
    assert sin_formato == ["Los pedidos se recogen en tienda"]


def test_sesiones_del_curso_se_leen_de_la_ficha():
    ficha = datos.ficha("curso", {"curso.sesiones": "1. Fundamentos\nSesión 2: Roles\n3) Eventos\nsin número"})
    assert [s["numero"] for s in almacen.sesiones_del_curso(ficha)] == [1, 2, 3]


def test_el_pedido_de_la_sesion_recuerda_formatos_y_tres_preguntas(curso):
    ficha_curso_confirmada(curso)
    pedido = flujo.pedido_de_propuesta(curso, "sesion", 1, almacen.cargar(curso, "sesion", 1))
    assert "Excel para datos y Word para textos" in pedido
    assert "La evaluación tiene 3 preguntas" in pedido
    assert "Sesión 1: Agilidad y fundamentos de Scrum: manifiesto, pilares y valores" in pedido
