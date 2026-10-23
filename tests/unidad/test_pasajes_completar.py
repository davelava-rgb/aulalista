"""Decisión 67: el redactor da el comienzo de un pasaje y el programa lo completa desde la fuente."""

from app.materiales import comun
from app.validacion.pasajes import Corpus, Fuente

MANUAL = Fuente("manual.pdf", [
    {"texto": "Gobierno de Datos es el ejercicio de la autoridad y el control (planificación, seguimiento y "
              "aplicación) sobre la gestión de los activos de datos. Guía a las demás funciones.", "ubicacion": "página 63"},
    {"texto": "Los data stewards tienen tres niveles: ejecutivo, de coordinación y de negocio. Cada nivel decide "
              "sobre una parte del modelo.", "ubicacion": "página 64"},
    {"texto": "Esta oración es larga de verdad y sigue y sigue con muchas palabras para pasar del tope " + "palabra " * 50
              + "y termina aquí.", "ubicacion": "página 65"},
])


def test_completa_desde_el_comienzo_hasta_el_fin_de_la_oracion():
    texto, ubicacion = MANUAL.completar("Gobierno de Datos es el ejercicio de la autoridad")
    assert texto == ("Gobierno de Datos es el ejercicio de la autoridad y el control (planificación, seguimiento y "
                     "aplicación) sobre la gestión de los activos de datos.")
    assert ubicacion == "página 63"


def test_el_comienzo_se_busca_sin_tildes_ni_mayusculas_ni_signos():
    texto, ubicacion = MANUAL.completar("los data stewards tienen tres niveles ejecutivo de coordinacion")
    assert texto == "Los data stewards tienen tres niveles: ejecutivo, de coordinación y de negocio."
    assert ubicacion == "página 64"


def test_un_comienzo_que_empieza_a_mitad_de_pasaje_vale():
    texto, _ = MANUAL.completar("Guía a las demás funciones")
    assert texto == "Guía a las demás funciones."


def test_el_pasaje_se_corta_en_el_tope_de_palabras():
    texto, ubicacion = MANUAL.completar("Esta oración es larga de verdad y sigue")
    assert len(texto.split()) == 40 and texto.startswith("Esta oración es larga de verdad")
    assert ubicacion == "página 65"


def test_un_comienzo_con_el_final_mal_copiado_se_ubica_por_sus_primeras_cinco_palabras():
    texto, _ = MANUAL.completar("Los data stewards tienen tres niveles muy distintos entre ellos")
    assert texto == "Los data stewards tienen tres niveles: ejecutivo, de coordinación y de negocio."


def test_un_comienzo_que_no_esta_o_muy_corto_no_se_completa():
    assert MANUAL.completar("Scrum nació en Japón en 1986") is None
    assert MANUAL.completar("Gobierno") is None
    assert Corpus([MANUAL]).completar("otro.pdf", "Gobierno de Datos es el ejercicio") is None


def test_completar_pasajes_marca_los_que_no_se_ubican_y_cuenta():
    datos = {"pasajes": [
        {"oracion": "El gobierno decide.", "fuente": "manual.pdf", "ubicacion": "p. 1", "texto": "Gobierno de Datos es el ejercicio"},
        {"oracion": "Inventada.", "fuente": "manual.pdf", "ubicacion": "p. 9", "texto": "Scrum nació en Japón"},
        {"oracion": "De otra parte.", "fuente": "deducido", "ubicacion": "", "texto": "Los data stewards tienen"},
    ]}
    datos, no_ubicados = comun.completar_pasajes(datos, Corpus([MANUAL]))
    assert no_ubicados == 2
    primero, segundo, tercero = datos["pasajes"]
    assert primero["ubicado"] is True and primero["ubicacion"] == "página 63"
    assert primero["texto"].endswith("sobre la gestión de los activos de datos.")
    assert segundo == {"oracion": "Inventada.", "fuente": "manual.pdf", "ubicacion": "p. 9", "texto": "Scrum nació en Japón",
                       "ubicado": False}
    assert tercero["ubicado"] is False
    # Completar otra vez no cambia nada: un pasaje completo empieza igual.
    otra_vez, _ = comun.completar_pasajes(datos, Corpus([MANUAL]))
    assert otra_vez["pasajes"][0] == primero


def test_la_entrega_dice_cuantos_pasajes_no_se_ubicaron():
    assert comun.nota_de_pasajes({"pasajes_no_ubicados": 0}) == []
    assert comun.nota_de_pasajes({}) == []
    (linea,) = comun.nota_de_pasajes({"pasajes_no_ubicados": 2})
    assert linea.startswith("2 pasajes del redactor no se encontraron en su fuente")
