"""Decisión 68 c: las páginas de referencia se recortan por vocabulario y el programa elige pasajes."""

from app.fichas import referencia


LINEAS = [("[m.pdf · página 1] El gobierno de datos decide quién aprueba cada dato.", "El gobierno de datos decide quién aprueba cada dato."),
          ("[m.pdf · página 1] Esta página habla del clima de la ciudad.", "Esta página habla del clima de la ciudad."),
          ("[m.pdf · página 2] Un data steward cuida la calidad de los datos.", "Un data steward cuida la calidad de los datos."),
          ("[m.pdf · página 2] Otro párrafo sin relación con nada.", "Otro párrafo sin relación con nada.")]
CLAVES = referencia.raices("gobierno de datos") | referencia.raices("data steward")


def test_si_caben_van_todas_las_lineas():
    assert referencia.recortar(LINEAS, CLAVES, tope=10_000) == [l for l, _ in LINEAS]


def test_si_no_caben_quedan_las_que_nombran_el_vocabulario_en_su_orden():
    assert referencia.recortar(LINEAS, CLAVES, tope=200) == [LINEAS[0][0], LINEAS[2][0]]


def test_si_tampoco_caben_quedan_las_que_mas_palabras_clave_nombran():
    assert referencia.recortar(LINEAS, CLAVES, tope=80) == [LINEAS[2][0]]   # «data», «steward», «datos»: tres claves


def test_los_textos_de_la_sesion_salen_de_la_ficha():
    ficha = {"campos": {"sesion.numero_titulo": {"valor": "Sesión 1 · Gobierno"},
                        "lectura.bloque.1": {"valor": "Qué es el gobierno de datos"},
                        "vocabulario.conceptos": {"valor": "gobierno de datos\ndata steward (no usar: custodio)"},
                        "ejercicio.1.accion": {"valor": "Clasifica los datos"},
                        "sesion.exclusiones": {"valor": "nada de esto"}}}
    assert referencia.textos_de_la_sesion(ficha) == ["Sesión 1 · Gobierno", "Qué es el gobierno de datos",
                                                     "gobierno de datos", "data steward (no usar: custodio)",
                                                     "Clasifica los datos"]
    assert "gobie" in referencia.palabras_clave(ficha) and "nada" not in referencia.palabras_clave(ficha)
