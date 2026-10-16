"""La interfaz muestra el estado de cada material, el siguiente paso y el costo antes de gastar."""

import json

from fastapi.testclient import TestClient

from app import servidor, tokens
from app.fichas import almacen
from app.materiales import comun
from tests.unidad.test_lectura import sesion  # noqa: F401

cliente = TestClient(servidor.app)


def _poner(carpeta, material, **datos):
    comun.actualizar(carpeta, 1, material, **datos)


def _registro(carpeta, *filas):
    with open(carpeta / "tokens.jsonl", "a", encoding="utf-8") as archivo:
        for etapa, sesion, costo in filas:
            archivo.write(json.dumps({"fecha": "2026-10-15T10:00:00", "curso": "scrum", "sesion": sesion,
                                      "material": "-", "etapa": etapa, "tokens_entrada": 1, "tokens_salida": 1,
                                      "costo_usd": costo}) + "\n")


def test_la_ultima_corrida_suma_solo_las_llamadas_seguidas_del_final(entorno):
    carpeta = entorno["cursos"] / "scrum"
    carpeta.mkdir(parents=True)
    _registro(carpeta, ("propuesta ficha curso", "-", 1.0), ("redacción", "S1", 5.0),
              ("propuesta ficha curso", "-", 0.25), ("propuesta ficha curso", "-", 0.5))
    assert tokens.ultima_corrida("scrum", "propuesta ficha curso") == {
        "llamadas": 2, "costo_usd": 0.75, "fecha": "2026-10-15T10:00:00"}
    assert tokens.ultima_corrida("scrum", "completar ficha") is None


def test_la_sesion_abre_el_material_del_siguiente_paso_sin_la_evaluacion(sesion):  # noqa: F811
    r = cliente.get("/cursos/scrum/sesiones/1", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/cursos/scrum/sesiones/1/materiales/lectura"
    pagina = cliente.get(r.headers["location"]).text
    for clave in ("lectura", "diapositivas", "laboratorio"):
        assert f'href="/cursos/scrum/sesiones/1/materiales/{clave}"' in pagina
    assert "Evaluación y clave" not in pagina and "Etapa posterior" not in pagina  # sin etapa 9 (decisión 37)
    assert "Siguiente paso:" not in pagina   # el siguiente paso es este material: lo dicen el recorrido y el botón
    otra = cliente.get("/cursos/scrum/sesiones/1/materiales/diapositivas").text
    assert 'Siguiente paso:</strong>' in otra and 'materiales/lectura">Genera la lectura.</a>' in otra
    assert "Sesión 1 · Material 1 de 3" in pagina


def test_sin_fichas_la_sesion_abre_la_ficha(sesion):  # noqa: F811
    almacen.guardar(sesion, "sesion", 1, {**almacen.cargar(sesion, "sesion", 1), "confirmada": False})
    r = cliente.get("/cursos/scrum/sesiones/1", follow_redirects=False)
    assert r.headers["location"] == "/cursos/scrum/sesiones/1/ficha"


def test_un_material_que_no_existe_da_404(sesion):  # noqa: F811
    assert cliente.get("/cursos/scrum/sesiones/1/materiales/evaluacion").status_code == 404


def test_las_acciones_vuelven_a_la_pagina_del_material(sesion):  # noqa: F811
    r = cliente.post("/cursos/scrum/sesiones/1/materiales/diapositivas", follow_redirects=False)
    assert r.headers["location"].startswith("/cursos/scrum/sesiones/1/materiales/diapositivas?mensaje=")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/diapositivas").text
    assert 'href="/cursos/scrum/sesiones/1/materiales/diapositivas" aria-current="page"' in pagina


def test_el_recorrido_dice_en_que_paso_va_el_material(sesion):  # noqa: F811
    datos = servidor.MATERIALES["laboratorio"]
    def pasos(**estado):
        return [(r["clase"], r["nota"]) for r in servidor._recorrido(datos, estado)]
    assert pasos() == [("ahora", "Pendiente"), ("pendiente", "Sin IA"), ("pendiente", "Con IA, por bloque"),
                       ("pendiente", "Lo decides tú")]
    assert pasos(estado="trabajando")[0] == ("ahora", "En curso")
    assert pasos(estado="detenida")[0] == ("ahora", "Detenido por ti")
    assert pasos(estado="error")[0] == ("falla", "Se detuvo por un error")
    assert pasos(estado="con fallas")[:2] == [("hecho", "Listo"), ("falla", "Con fallas")]
    pendientes = {"secciones": [{"clave": "pendientes", "titulo": "Decisiones pendientes", "lineas": ["Una duda"]}]}
    assert pasos(estado="con pendientes", entrega=pendientes)[2:] == [("hecho", "Con pendientes"), ("ahora", "Lo decides tú")]
    assert pasos(estado="verificada")[2] == ("hecho", "Sin errores abiertos")
    assert pasos(estado="aprobada", aprobada="2026-10-15T10:00:00")[3] == ("hecho", "El 2026-10-15")
    assert pasos(estado="aprobada", desactualizado=True)[0] == ("ahora", "Las fichas cambiaron")


def test_el_recorrido_se_ve_en_la_pagina_con_su_estado_en_palabras(sesion):  # noqa: F811
    _poner(sesion, "lectura", estado="con fallas")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert 'aria-label="Recorrido del material"' in pagina
    assert '<li class="falla"><strong>Verificar</strong> <span class="paso-nota">Con fallas</span>' in pagina
    assert "(con problema)" in pagina


def test_el_laboratorio_concuerda_en_masculino(sesion):  # noqa: F811
    _poner(sesion, "laboratorio", estado="aprobada", aprobada="2026-10-15T10:00:00")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/laboratorio").text
    assert "Aprobado por ti el 2026-10-15" in pagina and "Aprobada por ti" not in pagina
    assert "AulaLista lo reemplaza" in pagina


def test_el_estado_lleva_icono_color_y_palabra(sesion):  # noqa: F811
    _poner(sesion, "lectura", estado="con fallas")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert '<span class="indicador error"><svg' in pagina and "Con fallas</span>" in pagina


def test_un_material_aprobado_desactualizado_no_se_ve_aprobado(sesion):  # noqa: F811
    datos = {"aprobada": "2026-10-15T10:00:00"}
    vista = servidor._situacion(servidor.MATERIALES["lectura"], {"estado": "aprobada", "desactualizado": True, **datos}, True)
    assert vista == {"clase": "error", "texto": "Desactualizada"}


def test_generar_de_nuevo_un_material_aprobado_pide_confirmacion(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert "data-confirmar=" not in pagina
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00")
    assert "data-confirmar=\"La lectura ya está aprobada." in cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text


def test_el_boton_generar_dice_lo_que_gasto_la_ultima_corrida(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert "Todavía no hay una corrida anterior para estimar el costo." in pagina
    _poner(sesion, "lectura", estado="verificada", corrida_desde=tokens.lineas("scrum"))
    with open(sesion / "tokens.jsonl", "a", encoding="utf-8") as archivo:
        archivo.write(json.dumps({"fecha": "x", "curso": "scrum", "sesion": "S1", "material": "lectura",
                                  "etapa": "redacción", "tokens_entrada": 1, "tokens_salida": 1, "costo_usd": 0.42}) + "\n")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    # El costo se dice una sola vez: en «Desde que pulsaste Generar» y el botón remite a esa línea.
    assert "Desde que pulsaste Generar: 1 llamada, 0.42 USD estimados." in pagina
    assert "Gasta tokens, como la corrida de arriba." in pagina


def test_la_pagina_del_curso_es_la_preparacion_y_el_avance_va_en_el_panel(sesion):  # noqa: F811
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00")
    pagina = cliente.get("/cursos/scrum").text
    hoja = pagina.split('<main class="hoja">')[1]
    assert "Preparación del curso" in hoja and 'id="fuentes"' in hoja
    assert '<span class="indicador bien"><svg' in hoja and "Confirmada</span>" in hoja   # estado de la ficha del curso
    assert "table class=\"datos sesiones\"" not in pagina and "Abrir sesión" not in pagina
    assert "1 de 3 aprobados" in pagina.split('id="panel"')[1].split("</nav>")[0]


def test_la_entrega_resume_en_una_linea_y_pliega_los_detalles(sesion):  # noqa: F811
    entrega = {"pregunta": "¿Apruebas la lectura?", "secciones": [
        {"clave": "archivos", "titulo": "Archivos", "lineas": ["S1_Lectura.docx: la lectura."]},
        {"clave": "probe", "titulo": "Qué probé", "lineas": ["Algo."]},
        {"clave": "pendientes", "titulo": "Decisiones pendientes", "lineas": ["Una.", "Otra."]}]}
    _poner(sesion, "lectura", estado="con pendientes", entrega=entrega)
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert "1 archivo · 2 decisiones pendientes" in pagina
    assert '<details class="detalle">' in pagina and "Detalles de la entrega: qué probé</summary>" in pagina


def test_la_ficha_tiene_indice_aviso_de_cambios_y_consulta_la_propuesta_sin_recargar(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert 'aria-label="Secciones de la ficha"' in pagina and 'href="#seccion-1"' in pagina
    assert 'id="sin-guardar"' in pagina and "location.reload(), 5000" not in pagina
    assert cliente.get("/cursos/scrum/sesiones/1/ficha/propuesta").json() == {}


def test_guardar_una_ficha_confirmada_avisa_que_desactualiza_lo_generado(sesion):  # noqa: F811
    assert "guardar un cambio desactualiza" not in cliente.get("/cursos/scrum/sesiones/1/ficha").text
    _poner(sesion, "lectura", estado="verificada")
    assert almacen.cargar(sesion, "sesion", 1)["confirmada"]
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert "Ficha confirmada: guardar un cambio desactualiza la lectura." in pagina
    # Y Guardar lo pregunta antes de enviar.
    assert 'data-confirmar="Esta ficha está confirmada. Si guardas el cambio, hay que generar de nuevo la lectura' in pagina


def test_la_ficha_redirige_despues_de_guardar_y_recargar_no_reenvia(sesion):  # noqa: F811
    r = cliente.post("/cursos/scrum/sesiones/1/ficha", data={"accion": "guardar"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/cursos/scrum/sesiones/1/ficha"
    assert "Ficha guardada." in cliente.get(r.headers["location"]).text
    assert "Ficha guardada." not in cliente.get(r.headers["location"]).text   # el aviso se muestra una sola vez


def test_los_bloques_llenos_se_pliegan_y_los_con_alertas_quedan_abiertos():
    campos = lambda valor, estado="": [{"valor": valor, "estado": estado}]  # noqa: E731
    secciones = [{"elementos": [{"repetible": True, "bloques": [
        {"numero": 1, "campos": campos("x")}, {"numero": 2, "campos": campos("", "falta definir")},
        {"numero": 3, "campos": campos("")}]}]}]
    vista = servidor._indice_de_secciones(secciones)
    assert [b["situacion"] for b in vista[0]["elementos"][0]["bloques"]] == ["lleno", "alerta", "vacio"]
    assert vista[0]["alertas"] == 1 and vista[0]["ancla"] == "seccion-1"


def test_el_inicio_muestra_el_gasto(entorno):
    pagina = cliente.get("/").text
    assert "Gasto total: 0 llamadas a Claude" in pagina


def test_todas_las_paginas_tienen_el_alternador_de_modo_claro_u_oscuro(entorno):
    pagina = cliente.get("/").text
    assert 'id="alternar-tema"' in pagina and '>Cambiar a modo oscuro</button>' in pagina
    css = (servidor.RAIZ / "web" / "estaticos" / "estilo.css").read_text(encoding="utf-8")
    assert ':root[data-tema="oscuro"]' in css and ':root:not([data-tema="claro"])' in css


def test_la_cabecera_lleva_el_logo_de_futurasoft(entorno):
    pagina = cliente.get("/").text
    assert 'src="/estaticos/marca/futurasoft-logo.png"' in pagina and 'alt="FuturaSoft' in pagina
    assert cliente.get("/estaticos/marca/futurasoft-logo.png").status_code == 200
    css = (servidor.RAIZ / "web" / "estaticos" / "estilo.css").read_text(encoding="utf-8")
    assert "--principal: #c537a0;" in css and "--marca: #1e0253;" in css


# ---------- Panel del curso (PLAN.md §0, decisión 38) ----------

def test_el_panel_aparece_en_todas_las_paginas_del_curso_y_no_en_el_inicio(sesion):  # noqa: F811
    fuente = next(iter(servidor.convertir.leer_indice(sesion)))
    for url in ("/cursos/scrum", "/cursos/scrum/ficha", "/cursos/scrum/sesiones/1/ficha", "/cursos/scrum/sesiones/1",
                f"/cursos/scrum/fuentes/{fuente}"):
        pagina = cliente.get(url).text
        assert '<nav class="panel" id="panel" aria-label="Curso">' in pagina, url
        assert '<main class="hoja">' in pagina, url
    assert 'id="panel"' not in cliente.get("/").text


def test_el_panel_marca_la_pagina_actual_y_abre_su_sesion(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert 'href="/cursos/scrum/sesiones/1/ficha" aria-current="page"' in pagina
    assert '<details class="panel-sesion abierta" open>' in pagina
    pagina = cliente.get("/cursos/scrum/ficha").text
    assert 'href="/cursos/scrum/ficha" aria-current="page"' in pagina
    assert '<details class="panel-sesion" >' in pagina   # la sesión que no se ve queda plegada


def test_el_panel_muestra_el_estado_con_palabra_el_siguiente_paso_y_el_gasto(sesion):  # noqa: F811
    _poner(sesion, "lectura", estado="con fallas")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    panel = pagina.split('id="panel"')[1].split("</nav>")[0]
    assert 'Lectura <span class="panel-sigue">Sigue</span>' in panel
    assert '<span class="indicador error"><svg' in panel and "Con fallas</span>" in panel
    assert "0 de 3 aprobados" in panel
    assert "Gasto del curso <b>" in panel and "Es una estimación, no la factura." in panel


def test_el_estado_de_las_fuentes_dice_lo_que_falta(sesion, tmp_path):  # noqa: F811
    assert servidor._estado_de_fuentes(sesion)["clase"] == "bien"
    vacia = tmp_path / "vacio"
    (vacia / "fuentes").mkdir(parents=True)
    assert servidor._estado_de_fuentes(vacia) == {"clase": "neutro", "texto": "Sin subir"}
    (vacia / "fuentes" / "guia.pdf").write_bytes(b"%PDF")
    assert servidor._estado_de_fuentes(vacia) == {"clase": "espera", "texto": "1 sin convertir"}


def test_el_borde_del_panel_tiene_version_de_noche(entorno):
    css = (servidor.RAIZ / "web" / "estaticos" / "estilo.css").read_text(encoding="utf-8")
    assert css.count("--borde: #") == 3   # claro, oscuro según Windows y oscuro elegido
