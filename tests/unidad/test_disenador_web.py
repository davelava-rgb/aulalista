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
from tests.sembrados.actividad import LIMPIA
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
    assert DATOS["puntaje_total"] == 9 and DATOS["regla_del_puntaje"] == disenador_web.REGLA_DEL_PUNTAJE


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


# ---------- Arreglos por trozos ----------

def test_un_arreglo_cambia_solo_los_trozos_unicos():
    html_, problemas = disenador_web.aplicar_cambios("a b c b", [{"buscar": "a", "reemplazar": "x"},
                                                                 {"buscar": "b", "reemplazar": "y"},
                                                                 {"buscar": "z", "reemplazar": "w"}])
    assert html_ == "x b c b"
    assert "aparece 2 veces" in problemas[0] and "aparece 0 veces" in problemas[1]


# ---------- El diseño dentro de la generación ----------

def disenar(sesion, *disenos):  # noqa: F811
    lectura_aprobada(sesion)
    consulta = consulta_en_secuencia(copy.deepcopy(LIMPIA), SIN_ERRORES, *disenos)
    material = asyncio.run(actividad.generar(sesion, "scrum", 1, consulta=consulta, probar_en_navegador=False))
    return material, consulta


def test_con_el_contenido_aprobado_el_disenador_entrega_la_pagina(sesion):  # noqa: F811
    material, consulta = disenar(sesion, {"html": PAGINA, "notas": "Una columna con el caso."})
    rutas = actividad.archivos(sesion, 1)
    assert material["estado"] == "verificada", material["problemas"]
    assert material["diseno"] == {"arreglos": 0, "notas": "Una columna con el caso.", "problemas": [], "estado": "diseñada",
                                  "navegador": []}
    assert material["archivos"]["pagina"] == "S1_Actividad.html" and rutas["pagina"].exists()
    pagina = rutas["pagina"].read_text(encoding="utf-8")
    assert disenador_web.MARCA not in pagina and '"titulo": "Scrum en la Sucursal Norte"' in pagina
    assert len(consulta.llamadas) == 3   # redacción, revisión y diseño
    opciones = consulta.llamadas[2]["options"]
    assert opciones.model == "claude-opus-5-5" and opciones.max_budget_usd == 4.00
    sistema = Path(opciones.system_prompt["path"]).read_text(encoding="utf-8")
    assert sistema.startswith("ERES EL DISEÑADOR DE LA PÁGINA") and "CONTRATO PARA LAS PRUEBAS" in sistema
    assert '"principal": "#0F4C5C"' in sistema
    lineas = json.dumps(material["entrega"], ensure_ascii=False)
    assert "S1_Actividad.html: la página del alumno" in lineas and "No recorrí la página en un navegador" in lineas


def test_una_falla_de_la_pagina_se_arregla_por_trozos(sesion):  # noqa: F811
    con_fetch = PAGINA.replace('"use strict";', '"use strict"; fetch("x");')
    arreglo = {"cambios": [{"buscar": '"use strict"; fetch("x");', "reemplazar": '"use strict";'}], "notas": "Quité fetch."}
    material, consulta = disenar(sesion, {"html": con_fetch, "notas": ""}, arreglo)
    assert material["estado"] == "verificada" and material["diseno"]["arreglos"] == 1
    pedido = consulta.llamadas[3]["prompt"]
    assert "El JavaScript usa «fetch(»" in pedido and consulta.llamadas[3]["options"].max_budget_usd == 2.00


def test_si_la_pagina_sigue_con_fallas_no_se_entrega_ni_se_aprueba(sesion):  # noqa: F811
    con_fetch = PAGINA.replace('"use strict";', '"use strict"; fetch("x");')
    sin_cambio = {"cambios": [], "notas": ""}
    material, consulta = disenar(sesion, {"html": con_fetch, "notas": ""},
                                 *[copy.deepcopy(sin_cambio) for _ in range(actividad.ARREGLOS_DE_DISENO)])
    assert len(consulta.llamadas) == 3 + actividad.ARREGLOS_DE_DISENO
    assert material["estado"] == "con fallas" and "pagina" not in material["archivos"]
    assert not actividad.archivos(sesion, 1)["pagina"].exists()
    assert any(p.startswith("FALLA · diseño de la página · El JavaScript usa «fetch(»") for p in material["problemas"])
    with pytest.raises(actividad.NoSePuedeAprobar):
        actividad.aprobar(sesion, 1)


def test_con_el_contenido_con_fallas_no_se_disena(sesion):  # noqa: F811
    lectura_aprobada(sesion)
    roto = copy.deepcopy(LIMPIA)
    roto["pasos"][0]["preguntas"][0]["opciones"][1]["correcta"] = True
    sigue = {"actividad": roto, "explicaciones": [], "datos_nuevos": []}
    consulta = consulta_en_secuencia(roto, *[copy.deepcopy(sigue) for _ in range(actividad.VUELTAS_DEL_VERIFICADOR)])
    material = asyncio.run(actividad.generar(sesion, "scrum", 1, consulta=consulta, probar_en_navegador=False))
    assert material["estado"] == "con fallas" and material["diseno"] == {}
    assert not any("Diseña la página" in l["prompt"] for l in consulta.llamadas)
    assert "no se diseñó porque el contenido quedó con fallas" in json.dumps(material["entrega"], ensure_ascii=False)


def test_la_pagina_del_alumno_se_abre_en_el_navegador(sesion):  # noqa: F811
    disenar(sesion, {"html": PAGINA, "notas": ""})
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
