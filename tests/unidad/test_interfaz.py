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
    assert 'Siguiente paso:</strong>' in otra and 'materiales/lectura" data-atajo="s" aria-keyshortcuts="S">Genera la lectura.</a>' in otra
    assert "Material 1 de 3 de la sesión 1" in pagina


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
    assert pasos(estado="aprobada", desactualizado=True, aprobada="2026-10-15T10:00:00") == [
        ("hecho", "Listo"), ("hecho", "Sin fallas"), ("hecho", "Hecho"), ("hecho", "El 2026-10-15; después cambió la ficha")]
    assert pasos(estado="verificada", desactualizado=True)[0] == ("ahora", "Las fichas cambiaron")


def test_el_recorrido_se_ve_en_la_pagina_con_su_estado_en_palabras(sesion):  # noqa: F811
    _poner(sesion, "lectura", estado="con fallas")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert 'aria-label="Recorrido del material"' in pagina
    assert '<li class="falla"><strong>Verificar</strong> <span class="paso-nota">Con fallas</span>' in pagina
    assert "(con problema)" in pagina


def test_el_laboratorio_concuerda_en_masculino(sesion):  # noqa: F811
    _poner(sesion, "laboratorio", estado="aprobada", aprobada="2026-10-15T10:00:00")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/laboratorio").text
    assert "Aprobado</span>" in pagina and "El 2026-10-15" in pagina
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
    assert "Es la primera vez: todavía no hay con qué estimar el costo." in pagina
    _poner(sesion, "lectura", estado="verificada", corrida_desde=tokens.lineas("scrum"))
    with open(sesion / "tokens.jsonl", "a", encoding="utf-8") as archivo:
        archivo.write(json.dumps({"fecha": "x", "curso": "scrum", "sesion": "S1", "material": "lectura",
                                  "etapa": "redacción", "tokens_entrada": 1, "tokens_salida": 1, "costo_usd": 0.42}) + "\n")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    # El costo se dice una sola vez: en «Desde que pulsaste Generar» y el botón remite a esa línea.
    assert "Desde que pulsaste Generar: 1 llamada, 0.42 USD estimados." in pagina
    assert "Gasta tokens (la unidad con que se paga el uso de Claude), como la vez anterior (arriba)." in pagina


def test_la_pagina_del_curso_es_un_tablero_con_lo_que_sigue_las_sesiones_y_la_preparacion(sesion):  # noqa: F811
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00")
    hoja = cliente.get("/cursos/scrum").text.split('<main class="hoja">')[1]
    assert '<p class="sigue-etiqueta" id="t-sigue">Lo que sigue</p>' in hoja
    assert '<p class="sigue-paso">Sesión 1: completa lo que falta para generar las diapositivas.</p>' in hoja
    assert '<p class="sigue-motivo">Falta información para generarlas. La página del material dice qué.</p>' in hoja
    assert "Faltan las diapositivas y el laboratorio." in hoja
    assert '<a class="boton" href="/cursos/scrum/sesiones/1/materiales/diapositivas" data-atajo="s" aria-keyshortcuts="S">Ir a las diapositivas</a>' in hoja
    assert '<a class="ficha-material bien" href="/cursos/scrum/sesiones/1/materiales/lectura">' in hoja
    assert "Aprobada el 15 de octubre" in hoja
    assert '<a class="ficha-material vacia" href="/cursos/scrum/sesiones/1/materiales/laboratorio">' in hoja
    # Preparación lista: va plegada, al final, y sin el botón de convertir porque no hay nada sin convertir.
    assert '<details class="prep" id="fuentes" >' in hoja and "<b>Preparación lista.</b>" in hoja
    assert hoja.index("sesiones-tablero") < hoja.index('class="prep"')
    assert "Convertir fuentes a texto" not in hoja
    assert '<span class="indicador bien"><svg' in hoja and "Confirmada</span>" in hoja   # estado de la ficha del curso


def test_sin_preparacion_lista_la_preparacion_va_abierta_y_arriba(entorno):
    cliente.post("/cursos", data={"nombre": "Curso vacío"})
    hoja = cliente.get("/cursos/curso-vacio").text.split('<main class="hoja">')[1]
    assert '<p class="sigue-paso">Sube las fuentes del curso.</p>' in hoja
    assert '<details class="prep" id="fuentes" open>' in hoja and "sesiones-tablero" not in hoja


def test_la_entrega_resume_en_una_linea_muestra_las_decisiones_y_pliega_los_detalles(sesion):  # noqa: F811
    entrega = {"pregunta": "¿Apruebas la lectura?", "secciones": [
        {"clave": "archivos", "titulo": "Archivos", "lineas": ["S1_Lectura.docx: la lectura."]},
        {"clave": "probe", "titulo": "Qué probé", "lineas": ["Algo."]},
        {"clave": "pendientes", "titulo": "Decisiones pendientes", "lineas": ["Una.", "Otra."]}]}
    _poner(sesion, "lectura", estado="con pendientes", entrega=entrega)
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert "1 archivo y 2 decisiones pendientes." in pagina
    assert '<ul class="entrega-archivos" aria-label="Archivos">' in pagina and "<span>La lectura.</span>" in pagina
    assert "Decisiones pendientes: decide si las aceptas</h3>" in pagina and "<li>Una.</li>" in pagina
    assert '<details class="detalle">' in pagina and "Detalles de la entrega: qué probé</summary>" in pagina
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert "Aprobaste con 2 decisiones pendientes</h3>" in pagina   # después de aprobar siguen a la vista


def test_las_acciones_van_juntas_con_un_solo_boton_principal(sesion):  # noqa: F811
    _poner(sesion, "lectura", estado="con pendientes", entrega={"pregunta": "¿Apruebas la lectura?", "secciones": []})
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    bloque = pagina.split('<div class="bloque-accion">')[1].split("</section>")[0]
    assert "Aprobar la lectura</button>" in bloque and "Pedir revisor independiente</button>" in bloque
    assert bloque.count('<button type="submit">') == 1   # Aprobar es el único principal; Generar de nuevo es secundario


def test_antes_de_generar_dice_lo_que_ya_se_cumple_y_lo_que_falta(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert "Todo está listo para generar la lectura." in pagina
    assert '<li class="si">Las dos fichas están confirmadas.</li>' in pagina
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/diapositivas").text
    assert "Antes de generar las diapositivas:" in pagina
    assert '<li class="no">Aprueba primero la lectura: las diapositivas salen de ella.</li>' in pagina


def test_ninguna_pagina_usa_puntos_medios_como_separador(sesion):  # noqa: F811
    for url in ("/", "/cursos/scrum", "/cursos/scrum/ficha", "/cursos/scrum/sesiones/1/materiales/lectura"):
        pagina = cliente.get(url).text
        assert " · " not in pagina.split("<body>")[1], url


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
    panel = pagina.split('id="panel"')[1].split("</nav>")[0]
    assert 'href="/cursos/scrum/sesiones/1/ficha" aria-current="page"' in panel
    assert '<div class="panel-sesion abierta">' in panel and '<div class="panel-sesion">' in panel   # la 2 no se ve
    pagina = cliente.get("/cursos/scrum").text
    assert 'class="panel-titulo" aria-current="page"' in pagina
    assert '<div class="panel-sesion abierta">' not in pagina


def test_el_panel_solo_tiene_sesiones_con_sus_materiales_en_puntos_y_el_gasto(sesion):  # noqa: F811
    _poner(sesion, "lectura", estado="con fallas")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    panel = pagina.split('id="panel"')[1].split("</nav>")[0]
    assert "Preparación del curso" not in panel and "Fuentes" not in panel
    assert ('<a class="panel-mat error sigue" href="/cursos/scrum/sesiones/1/materiales/lectura" aria-current="page">'
            in panel)
    assert '<span class="sr">: Con fallas. Es lo que sigue</span>' in panel   # el estado también en palabras
    assert '<a class="panel-mat neutro" href="/cursos/scrum/sesiones/1/materiales/diapositivas">' in panel
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


def test_una_falla_no_se_presenta_como_decision_ni_con_la_lista_de_generar(sesion):  # noqa: F811
    entrega = {"pregunta": "", "secciones": [{"clave": "pendientes", "titulo": "Decisiones pendientes", "lineas": [
        "FALLA · desborde · S1_Diapositivas.pptx · diapositiva 4: no cabe.", "Afirmación sin fuente: algo."]}]}
    _poner(sesion, "lectura", estado="con fallas", entrega=entrega)
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert '<h3 class="alerta">Lo que impide aprobar</h3>' in pagina
    impide = pagina.split("Lo que impide aprobar</h3>")[1].split("</ol>")[0]
    assert "FALLA" in impide and "Afirmación sin fuente" not in impide
    assert "Decisiones pendientes: decide si la aceptas</h3>" in pagina
    assert "Todo está listo para generar" not in pagina and "resolverlas en las fichas" not in pagina


def test_el_curso_se_llama_igual_en_todas_partes_y_los_terminos_se_definen(sesion):  # noqa: F811
    nombre = servidor._nombre("scrum")
    assert nombre != "Scrum"                                    # el de la ficha, no el que se escribió al crearlo
    for url in ("/", "/cursos/scrum", "/cursos/scrum/sesiones/1/materiales/lectura"):
        assert nombre in cliente.get(url).text, url
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert pagina.count("(la unidad con que se paga el uso de Claude)") == 1   # se define una sola vez por página
    _poner(sesion, "lectura", estado="error", error="Traceback: algo falló")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert "Se detuvo por un error antes de terminar." in pagina
    assert "<summary>Detalle del error</summary><p><code>Traceback: algo falló</code>" in pagina


def test_el_inicio_muestra_el_avance_de_cada_curso_y_enlaza_lo_que_sigue(sesion):  # noqa: F811
    pagina = cliente.get("/").text
    assert "0 de 6 materiales aprobados en 2 sesiones." in pagina
    assert '<strong>Sigue:</strong> <a href="/cursos/scrum/sesiones/1/materiales/lectura" data-atajo="s" aria-keyshortcuts="S">Sesión 1: genera la lectura.</a>' in pagina
    _poner(sesion, "lectura", estado="con fallas")
    pagina = cliente.get("/").text
    assert '<p class="curso-problema">Sesión 1: lectura con fallas.</p>' in pagina
    assert pagina.count('<span class="tramo error">') == 1
    for clave in ("lectura", "diapositivas", "laboratorio"):
        _poner(sesion, clave, estado="aprobada", aprobada="2026-10-15T10:00:00")
    pagina = cliente.get("/").text
    assert '<a href="/cursos/scrum/sesiones/2/ficha" data-atajo="s" aria-keyshortcuts="S">Sesión 2: confirma su ficha.</a>' in pagina   # la 1 ya está
    listo = {"fuentes": {"texto": "1 lista"}, "ficha_curso": {"clase": "bien"},
             "sesiones": [{"numero": 1, "puede_empezar": True, "siguiente": {"ancla": "", "texto": "Listo"}}]}
    assert servidor._que_sigue("scrum", listo) is None      # todo aprobado: la página dice que no queda nada


def test_el_inicio_de_un_curso_nuevo_enlaza_las_fuentes(entorno):
    cliente.post("/cursos", data={"nombre": "Curso vacío"})
    pagina = cliente.get("/").text
    assert '<a href="/cursos/curso-vacio#fuentes" data-atajo="s" aria-keyshortcuts="S">Sube las fuentes del curso.</a>' in pagina
    assert "Las sesiones aparecen al confirmar la ficha del curso." in pagina



# ---------- Tablero del curso (PLAN.md §0, decisión 44) ----------

def _m(clave="laboratorio", estado="", desactualizado=False, aprobada=""):
    datos = servidor.MATERIALES[clave]
    return {"clave": clave, "corto": datos["corto"], "el": datos["el"], "plural": datos["plural"], "estado": estado,
            "desactualizado": desactualizado, "aprobada": aprobada,
            "situacion": {"clase": "bien" if estado == "aprobada" and not desactualizado else
                          "error" if desactualizado or estado in ("con fallas", "error") else "neutro", "texto": ""}}


def test_el_motivo_de_lo_que_sigue_concuerda_y_dice_por_que():
    assert servidor._motivo(_m("laboratorio", "aprobada", True)) == "La ficha cambió después de generarlo: ya no la sigue."
    assert servidor._motivo(_m("diapositivas", "aprobada", True)) == "La lectura o la ficha cambió después de generarlas: ya no siguen a lo de ahora."
    assert servidor._motivo(_m("lectura", "con fallas")) == "Tiene fallas del verificador y no se puede aprobar así."
    assert servidor._motivo(_m("lectura")) == "Todavía no se generó."
    assert servidor._fecha("2026-10-12T09:00:00") == "12 de octubre" and servidor._fecha("") == ""


def test_la_frase_de_cada_sesion_resume_su_avance():
    sesion = {"puede_empezar": True, "hechos": 1, "van": 3,
              "materiales": [_m("lectura", "aprobada", True), _m("diapositivas", "aprobada", True), _m("laboratorio", "aprobada")]}
    assert servidor._frase_de_sesion(sesion) == "1 de 3 aprobados. La ficha cambió: 2 materiales quedaron desactualizados."
    sesion = {"puede_empezar": True, "hechos": 1, "van": 2, "materiales": [_m("diapositivas", "aprobada"), _m("laboratorio")]}
    assert servidor._frase_de_sesion(sesion) == "1 de 2 aprobados. Falta el laboratorio."
    assert servidor._frase_de_sesion({**sesion, "hechos": 2}) == "Lista: todos sus materiales están aprobados."
    assert servidor._frase_de_sesion({**sesion, "puede_empezar": False}) == "Falta confirmar su ficha."


def test_el_tablero_trae_lo_que_sigue_con_motivo_boton_y_costo(sesion):  # noqa: F811
    # Un material aprobado no es lo que sigue aunque la ficha haya cambiado: queda marcado como desactualizado.
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00", desactualizado=True)
    tablero = servidor._tablero(sesion, "scrum", servidor._panel(sesion, "scrum", "curso"))
    assert not tablero["sigue"]["texto"].startswith("Sesión 1: genera la lectura")
    assert tablero["sesiones"][0]["materiales"][0]["situacion"]["texto"] == "Desactualizada"
    assert tablero["sesiones"][0]["materiales"][0]["fecha"] == "15 de octubre"
    # Uno que aún no se aprobó sí lo es: se genera de nuevo para que siga a la ficha.
    _poner(sesion, "lectura", estado="verificada", aprobada="", desactualizado=True)
    _registro(sesion, ("redacción", "S1", 0.5))
    sigue = servidor._tablero(sesion, "scrum", servidor._panel(sesion, "scrum", "curso"))["sigue"]
    assert sigue["texto"] == "Sesión 1: genera la lectura de nuevo."
    assert sigue["boton"] == "Ir a la lectura" and sigue["url"] == "/cursos/scrum/sesiones/1/materiales/lectura"
    assert sigue["motivo"] == "La ficha cambió después de generarla: ya no la sigue."


def test_material_ficha_y_fuente_tienen_un_enlace_para_volver_al_curso(sesion):  # noqa: F811
    for url in ("/cursos/scrum/sesiones/1/materiales/lectura", "/cursos/scrum/sesiones/1/ficha"):
        assert '<p class="volver"><a href="/cursos/scrum">Volver a las sesiones del curso</a></p>' in cliente.get(url).text


def test_la_ayuda_explica_el_flujo_y_se_enlaza_desde_todas_las_paginas(sesion):  # noqa: F811
    for url in ("/", "/cursos/scrum", "/cursos/scrum/sesiones/1/materiales/lectura"):
        assert '<a class="ayuda-enlace" href="/ayuda">Cómo funciona</a>' in cliente.get(url).text, url
    pagina = cliente.get("/ayuda").text
    pasos = pagina.split('<ol class="flujo">')[1].split("</ol>")[0]
    assert pasos.count("<h2>") == 5 and "Convierte las fuentes a texto" in pasos
    assert "<strong>pasajes</strong>: trozos cortos de texto" in pagina and "<strong>tokens</strong>" in pagina
    for situacion in ("Desactualizado", "Con fallas", "revisor independiente", "iniciar.cmd"):
        assert situacion in pagina


def test_corrida_no_aparece_en_la_interfaz(sesion):  # noqa: F811
    _registro(sesion, ("redacción", "S1", 0.4))
    for url in ("/", "/cursos/scrum", "/cursos/scrum/sesiones/1/materiales/lectura", "/ayuda"):
        cuerpo = cliente.get(url).text.split("<body>")[1]
        assert "corrida" not in cuerpo.lower(), url



# ---------- Ficha en modo de lectura (PLAN.md §0, decisión 45) ----------

def _seccion(titulo, *elementos):
    return {"titulo": titulo, "elementos": list(elementos)}


def _campo(id_, etiqueta, valor="", estado=""):
    return {"id": id_, "etiqueta": etiqueta, "valor": valor, "estado": estado, "origen": "", "versiones": []}


def test_cada_seccion_trae_su_estado_y_su_resumen():
    secciones = servidor._indice_de_secciones([
        _seccion("1. Sesión", _campo("a", "Alcance (obligatorio)", "Calidad de datos" + chr(10) + "y su ciclo.")),
        _seccion("2. Lectura", _campo("b", "Bloque 1")),
        _seccion("3. Vocabulario", _campo("c", "Conceptos", "", "falta definir")),
        _seccion("5. Evaluación práctica (PBQ)", _campo("d", "Material", "La lectura.")),
    ])
    assert [s["estado"] for s in secciones] == ["completa", "vacia", "alerta", "no_se_usa"]
    assert secciones[0]["resumen"] == [{"etiqueta": "Alcance", "completa": "Alcance (obligatorio)",
                                        "valor": "Calidad de datos y su ciclo."}]
    assert servidor._etiqueta_corta("Material de referencia: una línea por archivo") == "Material de referencia"
    assert servidor._etiqueta_corta('Riesgos de "Cuidado con" (de 1 a 3)') == 'Riesgos de "Cuidado con"'


def test_los_ejercicios_se_resumen_en_una_fila_cada_uno():
    bloques = [{"numero": 1, "campos": [_campo("e1", "Ejercicio 1 · Área", "Registro de actas"),
                                        _campo("e2", "Acción", "Revisa cada fila.")]},
               {"numero": 2, "campos": [_campo("f1", "Ejercicio 2 · Área"), _campo("f2", "Acción")]}]
    seccion = servidor._indice_de_secciones([_seccion("4. Laboratorio", {"repetible": True, "nombre": "ejercicio",
                                                                          "bloques": bloques})])[0]
    assert seccion["filas"] == [{"nombre": "Ejercicio", "numero": 1, "situacion": "lleno",
                                 "titulo": "Registro de actas", "detalle": "Revisa cada fila."}]
    assert seccion["vacios"] == 1 and seccion["resumen"] == []


def test_la_ficha_confirmada_trae_resumen_y_campos_en_cada_seccion(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert '<section class="seccion tarjeta estado-completa leer" id="seccion-1"' in pagina
    assert '<dl class="resumen-ficha">' in pagina and '<div class="sec-campos">' in pagina
    assert '<button type="button" class="secundario sec-editar" data-editar="seccion-1">Editar<span class="sr"> 1. Sesión</span></button>' in pagina
    assert 'class="pildora estado-completa" href="#seccion-1"' in pagina
    assert '<table class="filas-ficha">' in pagina and 'data-bloque="bloque-seccion-4-1"' in pagina   # ejercicios
    assert 'id="bloque-seccion-4-1"' in pagina


def test_una_ficha_sin_confirmar_se_abre_en_edicion(sesion):  # noqa: F811
    ficha = almacen.cargar(sesion, "sesion", 1)
    almacen.guardar(sesion, "sesion", 1, {**ficha, "confirmada": False})
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert 'class="seccion tarjeta' in pagina and " leer\"" not in pagina


def test_la_ficha_confirmada_trae_cancelar_y_activa_el_modo_de_lectura(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert '<form method="post" id="form-ficha" enctype="multipart/form-data" class="ficha-lectura">' in pagina
    assert '<button type="button" class="secundario" id="cancelar-seccion">Cancelar</button>' in pagina
    assert 'id="guardar-ficha"' in pagina and 'document.documentElement.classList.add("ficha-js")' in pagina
    ficha = almacen.cargar(sesion, "sesion", 1)
    almacen.guardar(sesion, "sesion", 1, {**ficha, "confirmada": False})
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert 'class="ficha-lectura"' not in pagina and 'id="cancelar-seccion"' not in pagina


def test_el_texto_oculto_de_las_pildoras_no_ensancha_la_pagina_en_el_celular(entorno):
    # Un .sr (posición absoluta) sin un padre posicionado se sale de la fila de píldoras y ensancha la página.
    css = (servidor.RAIZ / "web" / "estaticos" / "estilo.css").read_text(encoding="utf-8")
    assert ".indice a.pildora { position: relative;" in css and ".panel-mat { position: relative;" in css


def test_la_tecla_s_lleva_a_lo_que_sigue_y_la_ayuda_lo_explica(sesion):  # noqa: F811
    for url in ("/", "/cursos/scrum", "/cursos/scrum/sesiones/1/materiales/diapositivas"):
        pagina = cliente.get(url).text
        assert pagina.count('data-atajo="s"') == 1, url        # un solo destino por página
        assert 'evento.key === "s"' in pagina and 'closest("input, textarea, select, [contenteditable]")' in pagina
    assert "<kbd>S</kbd> abre lo que sigue" in cliente.get("/ayuda").text



def test_las_secciones_de_la_ficha_se_pliegan_y_editar_alterna_con_cancelar(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert '<button type="button" class="sec-plegar" aria-expanded="true" aria-controls="cuerpo-seccion-1">' in pagina
    assert '<div class="sec-cuerpo" id="cuerpo-seccion-1">' in pagina
    assert '<span class="sec-estado estado-completa">Completa</span>' in pagina
    assert 'data-plegar-todas="1">Plegar todas</button>' in pagina
    assert 'editar.firstChild.textContent = "Cancelar"' in pagina                 # Editar se vuelve Cancelar
    assert "seccion === abierta) cancelar();" in pagina
