"""Segunda pasada: la revisión del contenido, por bloque (PLAN.md §0, decisión 22)."""

import copy

import openpyxl
import pytest

from app.materiales import lectura
from app.validacion import revision
from app.validacion.pasajes import Corpus
from tests.unidad.test_lectura import (  # noqa: F401  (sesion es la base de prueba)
    LIMPIA, SIN_ERRORES, cambios, error, generar, sesion)
from tests.unidad.test_lectura import revision as respuesta

PILARES = "Los pilares de Scrum son tres."
MANIFIESTO = "El Manifiesto Ágil tiene cuatro aspectos."


def hallazgos_excel(sesion) -> list[tuple]:
    hoja = openpyxl.load_workbook(lectura.archivos(sesion, 1)["excel"])["Hallazgos"]
    return list(hoja.iter_rows(min_row=2, values_only=True))


# ---------- El pedido ----------

def test_la_revision_lee_cada_bloque_con_sus_pasajes_y_acepta_otras_palabras(sesion):
    con_ancla = copy.deepcopy(LIMPIA)
    con_ancla["pasajes"][0]["oracion"] = PILARES     # el redactor dice qué pasaje usó para esta oración
    _, consulta = generar(sesion, con_ancla)
    pedido = consulta.llamadas[1]["prompt"]
    for nombre in ("Idea central", "El Manifiesto Ágil", "Pilares de Scrum", "Aplícalo así", "Cuidado con"):
        assert f"\n[{nombre}]\n" in pedido
    assert "Pasajes de las fuentes y de las fichas:" in pedido
    pilares = pedido.split("\n[Pilares de Scrum]\n")[1].split("\n[")[0]
    assert "- (silabo.pdf · página 1) Scrum Master con IA" in pilares     # el pasaje del redactor, en su bloque
    assert "Decir lo mismo que la fuente con otras palabras, con sinónimos, en otro orden o en un resumen." in pedido
    assert all(t in pedido for t in revision.TIPOS)
    assert "Usé una tienda como ejemplo." not in pedido                   # las decisiones del redactor no van
    opciones = consulta.llamadas[1]["options"]
    assert opciones.model == "claude-sonnet-5-5" and opciones.max_budget_usd == 0.80


def test_la_revision_recibe_las_posibles_inconsistencias(sesion):
    doble = copy.deepcopy(LIMPIA)
    doble["bloques"][0]["parrafos"].append("El Sprint dura dos semanas.")
    doble["bloques"][1]["parrafos"].append("El Sprint dura tres semanas.")
    _, consulta = generar(sesion, doble)
    pedido = consulta.llamadas[1]["prompt"]
    assert "- semanas: «dos semanas» en:" in pedido and "«tres semanas» en:" in pedido


# ---------- El programa comprueba cada error ----------

def test_un_error_sin_prueba_real_o_sin_oracion_se_descarta(sesion):
    inventada = error(PILARES, "contradice la fuente", prueba="Scrum tiene cinco pilares.", donde="silabo.pdf")
    sin_oracion = error("Esta oración no está en el material.")
    material, consulta = generar(sesion, LIMPIA, respuesta(inventada, sin_oracion), revisar=False)
    assert material["estado"] == "verificada"
    assert len(consulta.llamadas) == 2      # nada que corregir
    assert material["revision"]["descartados"] == 2 and material["revision"]["errores"] == 0
    motivos = [f[5] for f in hallazgos_excel(sesion) if f[3].startswith("revisión")]
    assert motivos == ["Descartado por el programa: La prueba no existe en las fuentes, las fichas ni el material.",
                       "Descartado por el programa: La oración no está en el material."]


def test_la_prueba_de_una_contradiccion_se_ubica_en_la_fuente_la_ficha_o_el_material(sesion):
    generar(sesion, LIMPIA)
    corpus = Corpus.del_curso(sesion, 1)
    bloques = lectura.bloques_de(lectura.Lectura.model_validate(LIMPIA))
    assert revision.ubicar_prueba("Scrum Master con IA", corpus, bloques) == "silabo.pdf, página 1"
    assert revision.ubicar_prueba("scrum master con ia", corpus, bloques) == "silabo.pdf, página 1"   # sin mayúsculas
    assert revision.ubicar_prueba("Duración de cada Sprint: dos semanas", corpus, bloques).startswith("ficha del curso, ")
    assert revision.ubicar_prueba(PILARES, corpus, bloques) == "el material"
    assert revision.ubicar_prueba("Sprint de tres semanas", corpus, bloques) is None


def test_un_vacio_o_una_ambiguedad_no_necesitan_prueba(sesion):
    resultado = revision.comprobar(respuesta(error(PILARES, "vacío"), error(MANIFIESTO, "ambigüedad", "El Manifiesto Ágil")),
                                   lectura.bloques_de(lectura.Lectura.model_validate(LIMPIA)), Corpus([]))
    assert [(e.tipo, e.oracion) for e in resultado.errores] == [("vacío", PILARES), ("ambigüedad", MANIFIESTO)]
    assert resultado.descartados == []


# ---------- Una corrección y la confirmación de lo corregido ----------

def test_un_error_se_corrige_una_vez_y_se_confirma_solo_su_bloque(sesion):
    nueva = PILARES + " Son transparencia, inspección y adaptación."
    material, consulta = generar(sesion, LIMPIA, respuesta(error(PILARES, "vacío")), cambios((PILARES, nueva)),
                                 SIN_ERRORES, revisar=False)
    assert material["estado"] == "verificada"
    assert len(consulta.llamadas) == 4   # redacción, revisión, corrección y confirmación
    assert "REVISIÓN · vacío · «Los pilares de Scrum son tres.»" in consulta.llamadas[2]["prompt"]
    confirmacion = consulta.llamadas[3]["prompt"]
    assert "\n[Pilares de Scrum]\n" in confirmacion and "[Idea central]" not in confirmacion
    assert material["revision"] == {"bloques": 5, "errores": 1, "corregidos": 1, "pendientes": 0, "descartados": 0}
    assert material["correcciones"] == {"verificador": 0, "revisión": 1}
    fila = next(f for f in hallazgos_excel(sesion) if f[3] == "revisión: vacío")
    assert fila[0] == "REVISIÓN" and fila[2] == PILARES and fila[5] == "Corregido y confirmado por la revisión."
    valide = next(s["lineas"] for s in material["entrega"]["secciones"] if s["clave"] == "valide")
    assert "Revisión del contenido: 5 bloques, 1 error con prueba (1 corregido y 0 pendientes)." in valide


def test_lo_que_la_correccion_no_arregla_queda_pendiente_y_se_puede_aprobar(sesion):
    material, consulta = generar(sesion, LIMPIA, respuesta(error(PILARES, "vacío")), cambios(), revisar=False)
    assert len(consulta.llamadas) == 3   # el bloque no cambió: no hay confirmación
    assert material["estado"] == "con pendientes"
    assert material["problemas"] == ["REVISIÓN · vacío · «Los pilares de Scrum son tres.»: vacío en la oración."]
    pendientes = next(s["lineas"] for s in material["entrega"]["secciones"] if s["clave"] == "pendientes")
    assert pendientes == material["problemas"]
    fila = next(f for f in hallazgos_excel(sesion) if f[3] == "revisión: vacío")
    assert fila[5] == "La corrección no cambió su bloque. Pendiente: decides tú."
    assert lectura.aprobar(sesion, 1)["estado"] == "aprobada"      # el profesor decide


def test_un_error_que_sigue_o_uno_nuevo_en_la_confirmacion_quedan_pendientes(sesion):
    nueva = "Los pilares de Scrum son tres: transparencia, inspección y adaptación."
    otro = "El equipo muestra su tablero a todos."
    material, _ = generar(sesion, LIMPIA, respuesta(error(PILARES, "vacío")), cambios((PILARES, nueva)),
                          respuesta(error(nueva, "vacío"), error(otro, "ambigüedad")), revisar=False)
    assert material["estado"] == "con pendientes"
    assert material["revision"]["pendientes"] == 2 and material["revision"]["corregidos"] == 0
    resoluciones = {f[2]: f[5] for f in hallazgos_excel(sesion) if f[3].startswith("revisión")}
    assert resoluciones == {nueva: "Sigue después de la corrección. Pendiente: decides tú.",
                            otro: "Apareció en la confirmación. Pendiente: decides tú."}


def test_una_correccion_que_rompe_el_verificador_deja_la_lectura_con_fallas(sesion):
    rota = "Los pilares se revisan en 10 minutos."
    material, consulta = generar(sesion, LIMPIA, respuesta(error(PILARES, "ambigüedad")), cambios((PILARES, rota)),
                                 *[cambios()] * lectura.VUELTAS_DEL_VERIFICADOR, revisar=False)
    assert material["estado"] == "con fallas"
    assert material["problemas"][0].startswith("FALLA · tiempo")
    fila = next(f for f in hallazgos_excel(sesion) if f[3] == "revisión: ambigüedad")
    assert fila[5] == "No se confirmó: quedaron fallas del verificador."
    with pytest.raises(lectura.NoSePuedeAprobar):
        lectura.aprobar(sesion, 1)
