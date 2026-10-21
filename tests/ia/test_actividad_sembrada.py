"""La revisión del contenido de la actividad web encuentra errores puestos a propósito (PLAN.md §4, fase 8b).

Una pregunta con dos respuestas defendibles y una explicación que contradice la lectura deben salir. Una paráfrasis
de la lectura y las opciones incorrectas a propósito no son errores. Gasta tokens. Se corre con:
    pytest -m ia tests/ia/test_actividad_sembrada.py -s
"""

import asyncio
import copy

import pytest

from app.materiales import actividad, diapositivas
from app.materiales.contenido import Actividad, Lectura
from app.validacion import revision
from app.validacion.pasajes import Corpus
from tests.ia.test_revision_sembrados import curso  # noqa: F401  (curso con una guía y las dos fichas)
from tests.sembrados.actividad import LIMPIA
from tests.unidad.test_lectura import LIMPIA as LECTURA

PARAFRASIS = "Scrum se apoya en tres pilares."              # dice lo mismo que la lectura: no es error
CONTRADICE = "La lectura dice que Scrum tiene cinco pilares."   # explicación de la opción correcta: contradice
AMBIGUA = "Lo lee con el equipo."                           # opción «incorrecta» que también es defendible
INCORRECTAS = ["Dos", "Faltaría un pilar: la lectura nombra tres.", "Cierra la sucursal.", "Borra el registro."]


def sembrada() -> Actividad:
    datos = copy.deepcopy(LIMPIA)
    paso1 = datos["pasos"][0]
    paso1["recuerde"] = PARAFRASIS
    paso1["preguntas"][0]["opciones"][2]["explicacion"] = CONTRADICE   # «Cinco», incorrecta: su explicación miente
    datos["pasos"][1]["preguntas"].append({
        "tipo": "opcion_unica", "enunciado": "¿Qué hace el equipo con el registro de pedidos el viernes?", "puntos": 1,
        "opciones": [{"texto": "Lo revisa.", "correcta": True, "explicacion": "El caso dice que lo revisa cada viernes."},
                     {"texto": AMBIGUA, "correcta": False, "explicacion": "El caso no dice que lo lea."},
                     {"texto": "Lo borra.", "correcta": False, "explicacion": "El registro no se borra."}],
        "elementos": [], "pares": [], "categorias": []})
    return Actividad.model_validate(datos)


@pytest.mark.ia
def test_la_revision_de_la_actividad_encuentra_lo_sembrado_y_respeta_lo_correcto(curso):  # noqa: F811
    corpus = Corpus.del_curso(curso, 1, extras=[diapositivas.fuente_de_la_lectura(Lectura.model_validate(LECTURA))])
    resultado = asyncio.run(revision.ejecutar(
        actividad.bloques_de(sembrada()), corpus=corpus, curso="scrum", sesion=1, material="prueba actividad",
        nombre_material=actividad.MATERIAL, etapa="prueba sembrados", indicaciones=actividad.INDICACIONES_DE_REVISION))

    marcadas = {e.oracion: e.tipo for e in resultado.errores}
    print(f"\nErrores con prueba: {len(resultado.errores)}. Descartados: {len(resultado.descartados)}.")
    for e in resultado.errores:
        print(f"  {e.tipo}: {e.oracion} · {e.explicacion}")
    falsas = [o for o in [PARAFRASIS, *INCORRECTAS] if o in marcadas]
    assert falsas == [], f"Marcó como error lo que está bien: {falsas}"
    assert CONTRADICE in marcadas, "No encontró la explicación que contradice la lectura."
    ambigua = [e for e in resultado.errores if e.bloque.startswith("Paso 2") and e.tipo == "ambigüedad"]
    assert ambigua, "No encontró la pregunta con dos respuestas defendibles."
