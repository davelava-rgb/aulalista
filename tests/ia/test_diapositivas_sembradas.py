"""La revisión de las diapositivas marca lo que la lectura no dice, aunque esté en una fuente del curso
(SKILL.md, Material 2: «No agregues contenido nuevo»). Gasta tokens. Se corre con:
    pytest -m ia tests/ia/test_diapositivas_sembradas.py -s
"""

import asyncio

import pytest

from app.materiales import diapositivas
from app.materiales.contenido import Lectura
from app.validacion import pasada2, revision
from app.validacion.pasajes import Corpus
from tests.ia.test_revision_sembrados import GUIA, curso  # noqa: F401

LECTURA = Lectura.model_validate({
    "idea_central": ["Scrum es un marco liviano que ayuda a generar valor."],
    "bloques": [
        {"subtitulo": "Qué es Scrum", "parrafos": [GUIA[0]], "ejemplo": {"titulo": "Ejemplo", "parrafos": [
            "Comercial Los Volcanes usa Scrum para su tienda en línea."]}, "tabla": None},
        {"subtitulo": "Pilares de Scrum", "parrafos": [GUIA[1]], "ejemplo": {"titulo": "Ejemplo", "parrafos": [
            "El equipo muestra su tablero a todos."]}, "tabla": None},
    ],
    "aplicalo": {"parrafos": ["Usa estas preguntas."], "plantilla": ["Qué observamos."]},
    "cuidado": ["Confundir pilares con valores."],
})
CORRECTAS = ["Scrum ayuda a generar valor.", "Tres pilares: transparencia, inspección y adaptación.",
             "Qué preguntar al grupo: ¿Qué pilar usan más en su área?"]
FUERA_DE_LA_LECTURA = "El Scrum Team es lo suficientemente pequeño como para seguir siendo ágil."   # está en la guía


@pytest.mark.ia
def test_marca_lo_que_no_esta_en_la_lectura(curso):  # noqa: F811
    bloques = [pasada2.Bloque("Diapositivas de «Qué es Scrum»", [CORRECTAS[0], FUERA_DE_LA_LECTURA]),
               pasada2.Bloque("Diapositivas de «Pilares de Scrum»", CORRECTAS[1:])]
    corpus = Corpus.del_curso(curso, 1, extras=[diapositivas.fuente_de_la_lectura(LECTURA)])
    resultado = asyncio.run(revision.ejecutar(
        bloques, corpus=corpus, curso="scrum", sesion=1, material="prueba sembrados", nombre_material="Diapositivas",
        etapa="prueba sembrados", indicaciones=diapositivas.INDICACIONES_DE_REVISION))
    marcadas = {e.oracion: e.tipo for e in resultado.errores}
    print(f"\nMarcadas: {marcadas}")
    assert FUERA_DE_LA_LECTURA in marcadas
    assert not any(o in marcadas for o in CORRECTAS)
