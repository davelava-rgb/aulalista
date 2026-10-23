"""Fase 8c: el diseñador de la página del alumno y los controles de la decisión 57 f."""

import asyncio
import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import servidor
from app.materiales import actividad, disenador_web, estilo
from app.materiales.contenido import Actividad
from tests.conftest import consulta_en_secuencia
from tests.sembrados.actividad import LIMPIA, PUNTOS_LIMPIOS
from tests.unidad.test_actividad import SIN_ERRORES, lectura_aprobada
from tests.unidad.test_lectura import sesion  # noqa: F401

PAGINA = (Path(__file__).resolve().parents[1] / "fixtures" / "actividad_pagina.html").read_text(encoding="utf-8")
IDENTIDAD = estilo.Identidad(**estilo.PALETA_SOBRIA, tipografia="Calibri", logo=None)
DATOS = disenador_web.datos_de_la_pagina(Actividad.model_validate(LIMPIA), "Scrum IA", 1, "Scrum Master con IA",
                                         actividad.NOTA_DEL_PUNTAJE)
cliente = TestClient(servidor.app)


def revisar(html_: str, datos=DATOS) -> list[str]:
    return disenador_web.revisar(disenador_web.armar(html_, datos), datos, IDENTIDAD)


# ---------- Los datos y el bloque de contenido ----------

def test_los_datos_de_la_pagina_son_el_contenido_sin_borradores():
    assert DATOS["titulo"] == LIMPIA["titulo"] and DATOS["pasos"][0]["titulo"] == "Reconozca los pilares"
    assert "pasajes" not in DATOS and "decisiones" not in DATOS
    assert DATOS["clave"] == "aulalista-scrum-ia-s1-actividad-v1"
    assert DATOS["puntaje_total"] == 100 and DATOS["regla_del_puntaje"] == disenador_web.REGLA_DEL_PUNTAJE


def test_la_pagina_muestra_los_puntos_sobre_100():
    """Decisión 59: cada pregunta lleva sus puntos ya repartidos y la suma de la página da 100."""
    puntos = [q["puntos"] for paso in DATOS["pasos"] for q in paso["preguntas"]]
    assert puntos == PUNTOS_LIMPIOS and sum(puntos) == DATOS["puntaje_total"] == 100
    assert [q["puntos"] for paso in LIMPIA["pasos"] for q in paso["preguntas"]] == [2, 1, 2, 1, 3]   # el contenido no cambia


def test_el_bloque_no_puede_cerrar_su_etiqueta():
    datos = {**DATOS, "titulo": "Un </script> en el texto"}
    pagina = disenador_web.armar(PAGINA, datos)
    assert "<\\/script>" in pagina and revisar(PAGINA, datos) == []


# ---------- Controles: una página bien hecha pasa ----------

def test_una_pagina_que_cumple_pasa_los_controles():
    assert revisar(PAGINA) == []


# ---------- Controles: errores sembrados, uno por control ----------

SEMBRADOS = [
    ("fetch", lambda h: h.replace('"use strict";', '"use strict"; fetch("https://otro.sitio/datos");'),
     "El JavaScript usa «fetch"),
    ("XMLHttpRequest", lambda h: h.replace('"use strict";', '"use strict"; new XMLHttpRequest();'), "XMLHttpRequest"),
    ("eval", lambda h: h.replace('"use strict";', '"use strict"; eval("1");'), "«eval"),
    ("script externo", lambda h: h.replace("</head>", '<script src="https://cdn.otro.com/libreria.js"></script></head>'),
     "Carga algo de afuera: <script src=\"https://cdn.otro.com/libreria.js\">"),
    ("hoja externa", lambda h: h.replace("</head>", '<link rel="stylesheet" href="https://cdn.otro.com/estilo.css"></head>'),
     "Carga algo de afuera: <link href=\"https://cdn.otro.com/estilo.css\">"),
    ("texto inventado en el HTML", lambda h: h.replace(
        '<main id="app"', '<p>Scrum fue creado por un comité de expertos para todas las empresas del mundo.</p><main id="app"'),
     "Texto que no sale del contenido: «Scrum fue creado por un comité"),
    ("texto inventado en el JavaScript", lambda h: h.replace(
        '"Su entrega"', '"Recuerde que el equipo siempre debe trabajar los fines de semana sin descanso"'),
     "Texto que no sale del contenido: «Recuerde que el equipo siempre debe trabajar"),
    ("bloque cambiado", lambda h: h.replace(disenador_web.MARCA, json.dumps({**DATOS, "titulo": "Otro título"})),
     "El bloque de contenido no es el aprobado"),
    ("sin bloque", lambda h: h.replace('<script type="application/json" id="contenido">/*CONTENIDO*/</script>', ""),
     "tiene 0"),
    ("tiempo", lambda h: h.replace('"Copiar mi entrega"', '"Tiene 20 minutos para terminar"'), "Muestra un tiempo: «minutos»"),
    ("color ajeno", lambda h: h.replace("--acento: #B7791F", "--acento: #FF00AA"), "colores que no son de la ficha: #FF00AA"),
    ("sin contrato", lambda h: h.replace('"data-puntaje"', '"data-total"'), "Falta el atributo data-puntaje"),
]


@pytest.mark.parametrize("ident, cambio, esperado", SEMBRADOS, ids=[s[0] for s in SEMBRADOS])
def test_cada_error_sembrado_de_la_pagina_queda_marcado(ident, cambio, esperado):
    html_ = cambio(PAGINA)
    assert html_ != PAGINA
    fallas = revisar(html_)
    assert any(esperado in f for f in fallas), fallas


def test_las_fuentes_de_google_y_los_grises_se_permiten():
    html_ = PAGINA.replace("--linea: #DDDDDD;", "--linea: #DDDDDD; --sombra: rgba(0, 0, 0, .3); --c: #ccc;")
    assert revisar(html_) == []


def test_una_etiqueta_corta_no_es_texto_ajeno():
    assert revisar(PAGINA.replace('"Comprobar"', '"Comprobar mi respuesta ahora"')) == []


# ---------- La página fija (decisión 70) ----------

def test_la_plantilla_toma_los_colores_y_la_tipografia_de_la_ficha():
    otra = estilo.Identidad(principal="1F4E79", acento="2E86AB", advertencia="B03A2E", fondo="EEF4FA", texto="2B2B2B",
                            tipografia="Georgia", logo=None)
    pagina = disenador_web.plantilla_con_identidad(otra)
    assert "{{" not in pagina and disenador_web.MARCA in pagina
    assert "--principal:#1F4E79" in pagina and "--acento:#2E86AB" in pagina and "--advertencia:#B03A2E" in pagina
    assert "--fondo:#EEF4FA" in pagina and "--texto:#2B2B2B" in pagina and "#0F4C5C" not in pagina
    assert "--cuerpo:Georgia," in pagina


def test_la_pagina_fija_pasa_los_controles_con_cualquier_paleta():
    datos = disenador_web.datos_de_la_pagina(Actividad.model_validate(LIMPIA), "scrum", 1, "Scrum", actividad.NOTA_DEL_PUNTAJE)
    for nombre, paleta in (("Sobria", estilo.PALETA_SOBRIA),
                           ("Vino", {"principal": "6D1A36", "acento": "9C7A1E", "advertencia": "B03A2E", "fondo": "F7F1F3",
                                     "texto": "2B2B2B"})):
        identidad = estilo.Identidad(**paleta, tipografia="Calibri", logo=None)
        pagina = disenador_web.pagina_fija(datos, identidad)
        assert disenador_web.revisar(pagina, datos, identidad) == [], nombre
        assert disenador_web.MARCA not in pagina and '"titulo": "Scrum en la Sucursal Norte"' in pagina


# ---------- La página dentro de la generación ----------

def disenar(sesion, probar_en_navegador=False):  # noqa: F811
    lectura_aprobada(sesion)
    consulta = consulta_en_secuencia(copy.deepcopy(LIMPIA), SIN_ERRORES)
    material = asyncio.run(actividad.generar(sesion, "scrum", 1, consulta=consulta, probar_en_navegador=probar_en_navegador))
    return material, consulta


def test_con_el_contenido_aprobado_aulalista_arma_la_pagina_sin_ia(sesion):  # noqa: F811
    material, consulta = disenar(sesion)
    rutas = actividad.archivos(sesion, 1)
    assert material["estado"] == "verificada", material["problemas"]
    assert material["diseno"] == {"arreglos": 0, "notas": "Plantilla fija de AulaLista (decisión 70).", "problemas": [],
                                  "estado": "diseñada", "navegador": []}
    assert material["archivos"]["pagina"] == "S1_Actividad.html" and rutas["pagina"].exists()
    pagina = rutas["pagina"].read_text(encoding="utf-8")
    assert disenador_web.MARCA not in pagina and '"titulo": "Scrum en la Sucursal Norte"' in pagina
    assert "--principal:#0F4C5C" in pagina
    assert len(consulta.llamadas) == 2   # redacción y revisión: ninguna llamada para el diseño
    lineas = json.dumps(material["entrega"], ensure_ascii=False)
    assert "S1_Actividad.html: la página del alumno, con la plantilla de AulaLista" in lineas
    assert "No recorrí la página en un navegador" in lineas and "Arreglos del diseñador" not in lineas


def test_una_falla_de_la_plantilla_deja_la_actividad_con_fallas_sin_llamar_a_nadie(sesion, monkeypatch):  # noqa: F811
    rota = disenador_web.plantilla_con_identidad(IDENTIDAD).replace(
        "</head>", '<script src="https://cdn.otro.com/libreria.js"></script></head>')
    assert rota != disenador_web.plantilla_con_identidad(IDENTIDAD)
    monkeypatch.setattr(disenador_web, "plantilla_con_identidad", lambda identidad: rota)
    material, consulta = disenar(sesion)
    assert len(consulta.llamadas) == 2
    assert material["estado"] == "con fallas" and "pagina" not in material["archivos"]
    assert not actividad.archivos(sesion, 1)["pagina"].exists()
    assert any(p.startswith("FALLA · diseño de la página · Carga algo de afuera") for p in material["problemas"])
    assert "hay que corregir la plantilla" in json.dumps(material["avance"], ensure_ascii=False)
    with pytest.raises(actividad.NoSePuedeAprobar):
        actividad.aprobar(sesion, 1)


def test_con_el_contenido_con_fallas_no_se_arma_la_pagina(sesion):  # noqa: F811
    lectura_aprobada(sesion)
    roto = copy.deepcopy(LIMPIA)
    roto["pasos"][0]["preguntas"][0]["opciones"][1]["correcta"] = True
    sigue = {"actividad": roto, "explicaciones": [], "datos_nuevos": []}
    consulta = consulta_en_secuencia(roto, *[copy.deepcopy(sigue) for _ in range(actividad.VUELTAS_DEL_VERIFICADOR)])
    material = asyncio.run(actividad.generar(sesion, "scrum", 1, consulta=consulta, probar_en_navegador=False))
    assert material["estado"] == "con fallas" and material["diseno"] == {}
    assert "no se diseñó porque el contenido quedó con fallas" in json.dumps(material["entrega"], ensure_ascii=False)


def test_la_pagina_del_alumno_se_abre_en_el_navegador(sesion):  # noqa: F811
    disenar(sesion)
    respuesta = cliente.get("/cursos/scrum/sesiones/1/descargar/S1_Actividad.html")
    assert respuesta.status_code == 200 and respuesta.headers["content-disposition"].startswith("inline")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/actividad").text
    assert "S1_Actividad.html" in pagina


# ---------- Falsos positivos de la primera actividad real (Agilidad de negocios S1) ----------

def test_la_conexion_previa_a_las_fuentes_de_google_se_permite():
    html_ = PAGINA.replace("</head>", '<link rel="preconnect" href="https://fonts.googleapis.com"></head>')
    assert revisar(html_) == []
    otra = PAGINA.replace("</head>", '<link rel="stylesheet" href="https://cdn.otro.com/fonts.googleapis.com/x.css"></head>')
    assert any("Carga algo de afuera" in f for f in revisar(otra))


def test_un_selector_de_css_en_el_javascript_no_es_texto():
    html_ = PAGINA.replace('"use strict";', '"use strict"; var sel = ".q-cuerpo input, .q-cuerpo select, '
                                             '.q-cuerpo button:not([aria-disabled])";')
    assert revisar(html_) == []


def test_un_gris_azulado_es_gris():
    assert revisar(PAGINA.replace("--linea: #DDDDDD;", "--linea: #AEB5BB;")) == []
    assert any("colores que no son de la ficha" in f for f in revisar(PAGINA.replace("--linea: #DDDDDD;", "--linea: #3366CC;")))
