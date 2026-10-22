"""La interfaz muestra el estado de cada material, el siguiente paso y el costo antes de gastar."""

import json
import re

from fastapi.testclient import TestClient

from app import servidor, tokens
from app.fichas import almacen, flujo
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
    assert "Material 1 de 4 de la sesión 1" in pagina


def test_sin_la_ficha_de_la_sesion_confirmada_la_sesion_abre_su_material(sesion):  # noqa: F811
    # La ficha de la sesión se prepara y confirma al generar (decisión 55): no hace falta pasar por ella.
    almacen.guardar(sesion, "sesion", 1, {**almacen.cargar(sesion, "sesion", 1), "confirmada": False})
    r = cliente.get("/cursos/scrum/sesiones/1", follow_redirects=False)
    assert r.headers["location"] == "/cursos/scrum/sesiones/1/materiales/lectura"


def test_generar_prepara_y_confirma_la_ficha_de_la_sesion_antes(sesion, monkeypatch):  # noqa: F811
    almacen.guardar(sesion, "sesion", 1, {**almacen.cargar(sesion, "sesion", 1), "confirmada": False})
    preparadas, generadas = [], []

    async def con_problemas(carpeta, curso, numero, consulta=None):
        preparadas.append(numero)
        return {"mensajes": ["Corregí el ejercicio 2."], "errores": ["Ejercicio 2: hay que llenar algo a mano."]}

    monkeypatch.setattr(flujo, "preparar_y_confirmar", con_problemas)
    monkeypatch.setattr(servidor, "_trabajo_en_segundo_plano", lambda *a, **k: generadas.append(a))
    r = cliente.post("/cursos/scrum/sesiones/1/materiales/lectura", follow_redirects=False)
    assert r.headers["location"] == "/cursos/scrum/sesiones/1/ficha" and generadas == []
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert "Para generar, la ficha de la sesión tiene que quedar confirmada. Corregí el ejercicio 2." in pagina
    assert "Ejercicio 2: hay que llenar algo a mano." in pagina

    async def confirma(carpeta, curso, numero, consulta=None):
        ficha = almacen.cargar(carpeta, "sesion", numero)
        almacen.guardar(carpeta, "sesion", numero, {**ficha, "confirmada": True})
        return {"mensajes": [], "errores": []}

    monkeypatch.setattr(flujo, "preparar_y_confirmar", confirma)
    r = cliente.post("/cursos/scrum/sesiones/1/materiales/lectura", follow_redirects=False)
    assert r.headers["location"] == "/cursos/scrum/sesiones/1/materiales/lectura" and len(generadas) == 1


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
    assert pasos(estado="aprobada", aprobada="2026-10-15T10:00:00")[3] == ("hecho", "El 15 de octubre")
    # Desactualizado: el «!» va en Generar, que es lo que hay que rehacer; Aprobar recuerda la aprobación anterior.
    assert pasos(estado="aprobada", desactualizado=True, aprobada="2026-10-15T10:00:00") == [
        ("falla", "Después cambió la ficha"), ("pendiente", "Sin IA"), ("pendiente", "Con IA, por bloque"),
        ("pendiente", "Aprobado el 15 de octubre, antes del cambio")]
    diapositivas = [(r["clase"], r["nota"]) for r in servidor._recorrido(
        {**servidor.MATERIALES["diapositivas"], "clave": "diapositivas"}, {"estado": "aprobada", "desactualizado": True, "aprobada": "2026-10-15"})]
    assert diapositivas[0] == ("falla", "Después cambió la lectura o la ficha")
    assert diapositivas[3] == ("pendiente", "Aprobadas el 15 de octubre, antes del cambio")
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
    assert "Aprobado</span>" in pagina and "El 15 de octubre" in pagina
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
    # El costo se dice una sola vez: en «La última generación» y el botón remite a esa línea, sin decir dónde está.
    assert "La última generación: 1 llamada, 0.42 USD estimados." in pagina
    assert "Gasta tokens (la unidad con que se paga el uso de Claude), como la última generación." in pagina
    assert "(arriba)" not in pagina


def test_la_pagina_del_curso_es_un_tablero_con_lo_que_sigue_las_sesiones_y_la_preparacion(sesion):  # noqa: F811
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00")
    hoja = cliente.get("/cursos/scrum").text.split('<main class="hoja" id="principal" tabindex="-1">')[1]
    assert '<p class="sigue-etiqueta" id="t-sigue">Lo que sigue</p>' in hoja
    assert '<p class="sigue-paso">Sesión 1: completa lo que falta para generar las diapositivas.</p>' in hoja
    assert '<p class="sigue-motivo">Falta información para generarlas. La página del material dice qué.</p>' in hoja
    assert "Faltan las diapositivas, el laboratorio y la actividad web." in hoja
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
    hoja = cliente.get("/cursos/curso-vacio").text.split('<main class="hoja" id="principal" tabindex="-1">')[1]
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
    assert "Decisiones pendientes: al aprobar, las aceptas</h3>" in pagina and "<li>Una.</li>" in pagina
    assert '<details class="detalle">' in pagina and "Detalles de la entrega</summary>" in pagina
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert "Aprobaste con 2 decisiones pendientes</h3>" in pagina   # después de aprobar siguen a la vista


def test_aprobar_dice_junto_al_boton_que_acepta_las_decisiones(sesion):  # noqa: F811
    entrega = {"pregunta": "¿Apruebas la lectura?", "secciones": [
        {"clave": "archivos", "titulo": "Archivos", "lineas": ["S1_Lectura.docx: la lectura.",
                                                              "S1_Lectura_Verificacion.xlsx: los hallazgos."]},
        {"clave": "pendientes", "titulo": "Decisiones pendientes", "lineas": ["Una.", "Otra."]}]}
    _poner(sesion, "lectura", estado="con pendientes", entrega=entrega)
    form = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text.split('class="aprobar">')[1].split("</form>")[0]
    assert "Al aprobar aceptas las 2 decisiones pendientes de arriba." in form
    assert 'href="/cursos/scrum/sesiones/1/descargar/S1_Lectura_Verificacion.xlsx"' in form


def test_un_material_aprobado_cierra_con_lo_que_sigue_y_pliega_lo_que_gasta(sesion):  # noqa: F811
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    bloque = pagina.split('<div class="bloque-accion" id="acciones">')[1].split("</section>")[0]
    assert "La lectura está aprobada.</strong>" in bloque and 'class="boton"' in bloque
    assert bloque.index('<details class="otras-acciones">') < bloque.index("Generar de nuevo")
    assert 'class="saltar" href="#principal"' in pagina and 'id="principal"' in pagina


def test_si_todo_esta_aprobado_pero_desactualizado_el_siguiente_paso_lo_dice(sesion):  # noqa: F811
    for clave in servidor.MATERIALES:
        _poner(sesion, clave, estado="aprobada", aprobada="2026-10-15T10:00:00")
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00", desactualizado=True)
    siguiente = servidor._vista_de_materiales(sesion, "scrum", 1)["siguiente"]
    # Una idea por oración: el paso en el texto, la causa en el motivo (crítica de la interfaz).
    assert siguiente["texto"] == "Decide si generas de nuevo la lectura."
    assert siguiente["motivo"] == "La ficha cambió después de aprobarla."
    assert siguiente["ancla"] == "lectura" and siguiente["boton"] == "Ir a la lectura"   # se nombra y se enlaza
    _poner(sesion, "diapositivas", estado="aprobada", aprobada="2026-10-15T10:00:00", desactualizado=True)
    siguiente = servidor._vista_de_materiales(sesion, "scrum", 1)["siguiente"]
    assert siguiente["texto"] == "Decide si generas de nuevo la lectura y las diapositivas."
    assert siguiente["motivo"] == "La ficha cambió después de aprobarlas."
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00", desactualizado=False)
    assert servidor._vista_de_materiales(sesion, "scrum", 1)["siguiente"]["motivo"] == (
        "La lectura o la ficha cambió después de aprobarlas.")


def test_un_material_desactualizado_avisa_una_vez_y_marca_sus_archivos(sesion):  # noqa: F811
    entrega = {"pregunta": "¿Apruebas la lectura?", "secciones": [
        {"clave": "archivos", "titulo": "Archivos", "lineas": ["S1_Lectura.docx: la lectura."]}]}
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00", desactualizado=True, entrega=entrega)
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert pagina.count('class="aviso-viejo"') == 1 and "No entregues sus archivos sin generarla de nuevo." in pagina
    assert '<strong class="version-anterior">Versión anterior.</strong> La lectura.' in pagina
    assert "Las dos fichas están confirmadas." not in pagina


def test_las_acciones_van_juntas_con_un_solo_boton_principal(sesion):  # noqa: F811
    _poner(sesion, "lectura", estado="con pendientes", entrega={"pregunta": "¿Apruebas la lectura?", "secciones": []})
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    bloque = pagina.split('<div class="bloque-accion" id="acciones">')[1].split("</section>")[0]
    assert "Aprobar la lectura</button>" in bloque and "Pedir revisor independiente</button>" in bloque
    assert bloque.count('<button type="submit">') == 1   # Aprobar es el único principal; Generar de nuevo es secundario


def test_antes_de_generar_dice_lo_que_ya_se_cumple_y_lo_que_falta(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert "Todo está listo para generar la lectura." in pagina
    assert '<li class="si">Las dos fichas están confirmadas.</li>' in pagina
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/diapositivas").text
    assert "Antes de generar las diapositivas:" in pagina
    assert ('<li class="no">Aprueba primero la lectura: las diapositivas salen de ella. '
            '<a href="/cursos/scrum/sesiones/1/materiales/lectura">Ir a la lectura</a></li>') in pagina


def test_ninguna_pagina_usa_puntos_medios_como_separador(sesion):  # noqa: F811
    for url in ("/", "/cursos/scrum", "/cursos/scrum/ficha", "/cursos/scrum/sesiones/1/materiales/lectura"):
        pagina = cliente.get(url).text
        assert " · " not in pagina.split("<body>")[1], url


def test_la_ficha_tiene_indice_y_aviso_de_cambios_y_no_se_recarga_sola(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert 'aria-label="Secciones de la ficha"' in pagina and 'href="#seccion-1"' in pagina
    assert 'id="sin-guardar"' in pagina and "location.reload(), 5000" not in pagina
    assert 'id="propuesta-en-curso"' not in pagina   # la ficha ya no se propone sola en segundo plano (decisión 17)


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


def _contraste(a: str, b: str) -> float:
    def luz(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    claro, oscuro = sorted((luz(a), luz(b)), reverse=True)
    return (claro + 0.05) / (oscuro + 0.05)


def test_el_texto_magenta_sobre_niebla_usa_el_magenta_para_texto_en_los_dos_modos():
    # Crítica de la interfaz: «Nuevo» del panel daba 4.3:1 de día y 4.0:1 de noche (el mínimo es 4.5:1).
    css = (servidor.RAIZ / "web" / "estaticos" / "estilo.css").read_text(encoding="utf-8")
    dia = dict(re.findall(r"--([a-z-]+): (#[0-9a-f]{6});", css.split("}")[0]))
    noche = dict(re.findall(r"--([a-z-]+): (#[0-9a-f]{6});", css.split(':root[data-tema="oscuro"]')[1].split("}")[0]))
    for modo in (dia, noche):
        assert _contraste(modo["principal-texto"], modo["suave"]) >= 4.5
        assert _contraste(modo["principal"], modo["fondo"]) >= 4.5
        assert _contraste(modo["principal"], modo["suave"]) < 4.5      # por eso el panel no usa el magenta normal
    regla = re.search(r"\.panel-nuevo \{[^}]*\}", css).group(0)
    assert "color: var(--principal-texto)" in regla


# ---------- Panel del curso (PLAN.md §0, decisión 38) ----------

def test_el_panel_aparece_en_todas_las_paginas_del_curso_y_no_en_el_inicio(sesion):  # noqa: F811
    fuente = next(iter(servidor.convertir.leer_indice(sesion)))
    for url in ("/cursos/scrum", "/cursos/scrum/ficha", "/cursos/scrum/sesiones/1/ficha", "/cursos/scrum/sesiones/1",
                f"/cursos/scrum/fuentes/{fuente}"):
        pagina = cliente.get(url).text
        assert '<nav class="panel" id="panel" aria-label="Cursos">' in pagina, url
        assert '<main class="hoja" id="principal" tabindex="-1">' in pagina, url
    (sesion.parent / "_sistema" / "ultimo_curso.txt").unlink()           # sin último curso, el inicio es la lista
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
    assert "Decisiones pendientes: al aprobar, la aceptas</h3>" in pagina
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
    assert "0 de 8 materiales aprobados en 2 sesiones." in pagina
    assert '<strong>Sigue:</strong> <a href="/cursos/scrum/sesiones/1/materiales/lectura" data-atajo="s" aria-keyshortcuts="S">Sesión 1: genera la lectura.</a>' in pagina
    _poner(sesion, "lectura", estado="con fallas")
    pagina = cliente.get("/").text
    assert '<p class="curso-problema">Sesión 1: lectura con fallas.</p>' in pagina
    assert pagina.count('<span class="tramo error">') == 1
    for clave in ("lectura", "diapositivas", "laboratorio", "actividad"):
        _poner(sesion, clave, estado="aprobada", aprobada="2026-10-15T10:00:00")
    pagina = cliente.get("/").text
    # La 1 ya está. La 2 no necesita su ficha confirmada: se confirma al generar (decisión 55).
    assert '<a href="/cursos/scrum/sesiones/2/materiales/lectura" data-atajo="s" aria-keyshortcuts="S">Sesión 2: genera la lectura.</a>' in pagina
    listo = {"fuentes": {"texto": "1 lista"}, "ficha_curso": {"clase": "bien"},
             "sesiones": [{"numero": 1, "puede_empezar": True, "siguiente": {"ancla": "", "texto": "Listo"}}]}
    assert servidor._que_sigue("scrum", listo) is None      # todo aprobado: la página dice que no queda nada


def test_el_inicio_de_un_curso_nuevo_enlaza_las_fuentes(entorno):
    cliente.post("/cursos", data={"nombre": "Curso vacío"}, follow_redirects=False)   # sin abrirlo: no es el último
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


def test_si_una_lectura_desactualizada_bloquea_las_diapositivas_lo_que_sigue_es_la_lectura(sesion):  # noqa: F811
    # Las diapositivas salen de la lectura aprobada: con la lectura desactualizada, su botón Generar está bloqueado.
    # Lo que sigue no puede llevar a ese botón: lleva a la lectura y dice por qué (crítica de la interfaz, P1).
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00", desactualizado=True)
    assert servidor.diapositivas.faltan(sesion, 1)["otros"]          # de verdad bloqueadas
    siguiente = servidor._vista_de_materiales(sesion, "scrum", 1)["siguiente"]
    assert siguiente["ancla"] == "lectura" and siguiente["texto"] == "Genera de nuevo la lectura y apruébala."
    sigue = servidor._tablero(sesion, "scrum", servidor._panel(sesion, "scrum", "curso"))["sigue"]
    assert sigue["texto"] == "Sesión 1: genera de nuevo la lectura y apruébala."
    assert sigue["url"] == "/cursos/scrum/sesiones/1/materiales/lectura" and sigue["boton"] == "Ir a la lectura"
    assert sigue["motivo"] == "Las diapositivas salen de la lectura. La ficha cambió después de aprobarla."
    # La página de las diapositivas enlaza a la lectura en vez de dejar solo el botón bloqueado.
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/diapositivas").text
    assert ('<a href="/cursos/scrum/sesiones/1/materiales/lectura" data-atajo="s" aria-keyshortcuts="S">'
            "Genera de nuevo la lectura y apruébala.</a>") in pagina
    # El motivo del bloqueo enlaza a la lectura.
    assert ('<li class="no">La lectura está desactualizada: genérala y apruébala de nuevo. '
            '<a href="/cursos/scrum/sesiones/1/materiales/lectura">Ir a la lectura</a></li>') in pagina
    # En el tablero, la ficha de las diapositivas no ofrece «Generar»: dice qué espera.
    tablero = cliente.get("/cursos/scrum").text
    assert 'class="ficha-material vacia bloqueada" href="/cursos/scrum/sesiones/1/materiales/diapositivas"' in tablero
    assert '<span class="ficha-estado">Espera la lectura</span>' in tablero
    # El laboratorio no sale de la lectura: sigue ofreciendo «Generar».
    assert 'class="ficha-material vacia" href="/cursos/scrum/sesiones/1/materiales/laboratorio"' in tablero


def test_lo_que_sigue_no_repite_de_nuevo_y_contrae_al_y_del(sesion):  # noqa: F811
    assert servidor._a("el laboratorio") == "al laboratorio" and servidor._a("la lectura") == "a la lectura"
    assert servidor._de("el laboratorio") == "del laboratorio" and servidor._de("las diapositivas") == "de las diapositivas"
    for clave in ("lectura", "diapositivas", "actividad"):
        _poner(sesion, clave, estado="aprobada", aprobada="2026-10-15T10:00:00")
    _poner(sesion, "laboratorio", estado="aprobada", aprobada="2026-10-15T10:00:00", desactualizado=True)
    sigue = servidor._tablero(sesion, "scrum", servidor._panel(sesion, "scrum", "curso"))["sigue"]
    assert sigue["texto"] == "Sesión 1: decide si generas de nuevo el laboratorio."
    assert sigue["motivo"] == "La ficha cambió después de aprobarlo."
    assert sigue["boton"] == "Ir al laboratorio"
    pagina = cliente.get("/cursos/scrum").text
    assert "de nuevo de nuevo" not in pagina and "Ir a el " not in pagina
    _poner(sesion, "laboratorio", estado="con fallas", aprobada="", desactualizado=False)
    texto = servidor._vista_de_materiales(sesion, "scrum", 1)["siguiente"]["texto"]
    assert texto == "Resuelve las fallas del laboratorio en las fichas y genéralo de nuevo."


def test_con_la_sesion_aprobada_el_siguiente_paso_es_lo_pendiente_del_curso(sesion):  # noqa: F811
    # Crítica de la interfaz: decía «Siguiente paso: Los materiales de esta sesión están aprobados.» sin ningún paso.
    for clave in ("lectura", "diapositivas", "laboratorio", "actividad"):
        _poner(sesion, clave, estado="aprobada", aprobada="2026-10-15T10:00:00")
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    # El paso solo, sin anidar frases; el botón dice que es de otra sesión.
    assert ('<strong>Siguiente paso:</strong> <a href="/cursos/scrum/sesiones/2/materiales/lectura"'
            ' data-atajo="s" aria-keyshortcuts="S">Sesión 2: genera la lectura.</a> </p>') in " ".join(pagina.split())
    assert '<a class="boton" href="/cursos/scrum/sesiones/2/materiales/lectura">Ir a la lectura de la sesión 2</a>' in pagina


def test_las_fichas_sin_generar_dicen_su_estado_y_solo_la_que_sigue_se_destaca(sesion):  # noqa: F811
    # Crítica de la interfaz: cada ficha decía «Generar», como si gastara; eran siete puertas con el mismo peso.
    hoja = cliente.get("/cursos/scrum").text
    assert 'class="ficha-material vacia sigue" href="/cursos/scrum/sesiones/1/materiales/lectura"' in hoja
    assert '<span class="ficha-estado">Lo que sigue</span>' in hoja
    assert 'class="ficha-material vacia" href="/cursos/scrum/sesiones/1/materiales/laboratorio"' in hoja
    assert '<span class="ficha-estado">Sin generar</span>' in hoja and ">Generar</span>" not in hoja
    assert len(re.findall(r'class="ficha-material [^"]*\bsigue"', hoja)) == 1


def test_guardar_la_ficha_de_la_sesion_dice_que_usa_ia_y_lleva_su_costo_al_lado(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert re.search(r'id="guardar-ficha"[^>]*>Guardar y (preparar el plan|revisar) con IA</button>', pagina)
    assert 'data-texto-seccion="Guardar esta sección y revisar con IA"' in pagina
    assert '<p class="nota costo-guardar">Gasta tokens' in pagina
    assert "guardar.textContent = guardar.dataset.texto;" in pagina          # al cerrar una sección no vuelve a «Guardar»
    curso = cliente.get("/cursos/scrum/ficha").text                         # en el curso, Guardar no llama a la IA
    assert re.search(r'id="guardar-ficha"[^>]*>Guardar</button>', curso)
    # En el curso gasta «Proponer desde las fuentes»: su costo va en la barra, junto al botón (crítica de la interfaz).
    acciones = curso.split('<div class="acciones">')[1].split("</div>")[0]
    assert "Proponer desde las fuentes</button>" in acciones
    assert '<p class="nota costo-guardar">«Proponer desde las fuentes» gasta tokens' in acciones


def test_el_aviso_de_la_ficha_del_curso_no_nombra_una_seccion_de_la_sesion(sesion):  # noqa: F811
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00")
    curso = cliente.get("/cursos/scrum/ficha").text
    assert "Materiales de esta sesión» no lo desactualiza" not in curso
    assert "Ficha confirmada: guardar un cambio puede desactualizar" in curso
    assert "Cada material se desactualiza solo por lo que usa." in curso
    assert "Cambiar solo «Materiales de esta sesión» no lo desactualiza." in cliente.get("/cursos/scrum/sesiones/1/ficha").text


def test_los_titulos_sobre_niebla_usan_el_magenta_para_texto():
    css = (servidor.RAIZ / "web" / "estaticos" / "estilo.css").read_text(encoding="utf-8")
    assert ".seccion.tarjeta.apagada h2, .mensaje h2 { color: var(--principal-texto); }" in css


def test_lo_aceptado_al_aprobar_se_ve_en_el_tablero_y_en_el_recorrido(sesion):  # noqa: F811
    # Crítica de la interfaz: «Lista» y todo en verde escondían 6 decisiones pendientes aceptadas al aprobar.
    entrega = {"secciones": [{"clave": "pendientes", "titulo": "Decisiones pendientes",
                              "lineas": ["Afirmación sin fuente: uno.", "REVISIÓN · ambigüedad · dos."]}]}
    for clave in ("lectura", "diapositivas", "laboratorio", "actividad"):
        _poner(sesion, clave, estado="aprobada", aprobada="2026-10-15T10:00:00")
    _poner(sesion, "laboratorio", estado="aprobada", aprobada="2026-10-15T10:00:00", entrega=entrega)
    hoja = cliente.get("/cursos/scrum").text
    assert "Lista: todos sus materiales están aprobados. El laboratorio se aprobó con 2 decisiones pendientes." in hoja
    assert "<span>Con 2 decisiones pendientes</span>" in hoja
    datos = {**servidor.MATERIALES["laboratorio"], "clave": "laboratorio"}
    recorrido = servidor._recorrido(datos, {"estado": "aprobada", "aprobada": "2026-10-15", "entrega": entrega})
    assert recorrido[2]["nota"] == "Con 2 decisiones pendientes"
    # Una FALLA no es una decisión aceptada: no se cuenta.
    con_falla = {"secciones": [{"clave": "pendientes", "titulo": "", "lineas": ["FALLA: algo.", "Una duda."]}]}
    assert servidor._aceptadas({"estado": "aprobada", "entrega": con_falla}) == 1
    assert servidor._aceptadas({"estado": "verificada", "entrega": con_falla}) == 0


def test_la_ficha_aprobada_y_desactualizada_dice_que_la_fecha_es_de_antes_del_cambio(sesion):  # noqa: F811
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00", desactualizado=True)
    hoja = cliente.get("/cursos/scrum").text
    assert "<span>Aprobada el 15 de octubre, antes del cambio</span>" in hoja
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00", desactualizado=False)
    assert "<span>Aprobada el 15 de octubre</span>" in cliente.get("/cursos/scrum").text


def test_la_busqueda_en_una_fuente_no_distingue_tildes_y_resalta_lo_que_coincide():
    assert servidor._plano("Gestión DE Datos") == "gestion de datos"
    partes = servidor._partes("La Gestión y la gestion.", "gestion")
    assert [p["texto"] for p in partes if p["marca"]] == ["Gestión", "gestion"]
    assert "".join(p["texto"] for p in partes) == "La Gestión y la gestion."     # el texto no cambia


def test_la_pagina_de_una_fuente_se_busca_por_texto_y_pagina_y_va_por_tramos(sesion, monkeypatch):  # noqa: F811
    # Crítica de la interfaz: 8089 pasajes en una sola página, sin buscador y con desplazamiento lateral.
    fuente = next(iter(servidor.convertir.leer_indice(sesion)))
    pasajes = servidor.convertir.leer_pasajes(sesion, fuente)
    url = f"/cursos/scrum/fuentes/{fuente}"
    palabra = max(pasajes[0]["texto"].split(), key=len).strip(".,;:")
    pagina = cliente.get(url, params={"q": palabra.upper()}).text
    esperados = sum(1 for p in pasajes if servidor._plano(palabra) in servidor._plano(p["texto"]))
    assert f"{esperados} {'pasaje coincide' if esperados == 1 else 'pasajes coinciden'} con «{palabra.upper()}»" in pagina
    assert "<mark>" in pagina and '<a href="?">Quitar la búsqueda</a>' in pagina
    numero = pasajes[0]["pagina"]
    pagina = cliente.get(url, params={"pagina": str(numero)}).text
    assert f"en la página {numero}." in pagina
    assert "Ningún pasaje coincide con la búsqueda." in cliente.get(url, params={"q": "zzzqqqxx"}).text
    # Por tramos: con un pasaje por tramo, el primero enlaza al siguiente y el último al anterior.
    monkeypatch.setattr(servidor, "PASAJES_POR_TRAMO", 1)
    pagina = cliente.get(url).text
    assert pagina.count("<tr>") + pagina.count('<tr class="ia">') == 2           # el encabezado y un pasaje
    assert '<a class="boton secundario" href="?tramo=2">Siguientes</a>' in pagina and "Anteriores" not in pagina
    pagina = cliente.get(url, params={"tramo": "9999"}).text                       # fuera de rango: el último
    assert f"Tramo {len(pasajes)} de {len(pasajes)}" in pagina and "Siguientes</a>" not in pagina
    css = (servidor.RAIZ / "web" / "estaticos" / "estilo.css").read_text(encoding="utf-8")
    assert "table.datos.pasajes { table-layout: fixed; }" in css and "table.datos.pasajes td { overflow-wrap: anywhere; }" in css


def test_la_ficha_confirmada_dice_aparte_y_en_rojo_lo_que_hay_que_generar_de_nuevo(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert "Hay que generar de nuevo" not in pagina
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00", desactualizado=True)
    _poner(sesion, "laboratorio", estado="aprobada", aprobada="2026-10-15T10:00:00", desactualizado=True)
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    confirmada = pagina.split('<p class="estado-ficha confirmada">')[1].split("</p>")[0]
    assert "Confirmada." in confirmada and "generar" not in confirmada      # el verde solo dice «Confirmada»
    pendiente = pagina.split('<p class="estado-ficha pendiente">')[1].split("</p>")[0]
    assert ('Hay que generar de nuevo <a href="/cursos/scrum/sesiones/1/materiales/lectura">la lectura</a> y '
            '<a href="/cursos/scrum/sesiones/1/materiales/laboratorio">el laboratorio</a>, porque las fichas cambiaron.') in pendiente


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
    # En un campo de varias líneas, cada línea es un elemento: no se leen pegados.
    lista = {**_campo("s", "Sesiones", "Sesión 1 · Datos" + chr(10) + "Sesión 2 · Calidad"), "multilinea": True}
    sesiones = servidor._indice_de_secciones([_seccion("1. Curso", lista)])
    assert sesiones[0]["resumen"][0]["valor"] == "Sesión 1 · Datos; Sesión 2 · Calidad"
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


def test_la_ficha_confirmada_se_abre_desplegada_y_editar_solo_en_lo_desplegado(sesion):  # noqa: F811
    """Decisión 63: confirmada, se abre desplegada salvo lo que no se usa; «Editar» solo en una sección desplegada."""
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert 'plegar(seccion, seccion.classList.contains(confirmada ? "estado-no_se_usa" : "estado-completa"));' in pagina
    assert '<span class="sr">Plegar o desplegar 1. Sesión</span>' in pagina      # la flecha dice su sección
    assert 'setProperty("--alto-indice", indice.offsetHeight + "px")' in pagina   # el índice mide su alto real
    css = (servidor.RAIZ / "web" / "estaticos" / "estilo.css").read_text(encoding="utf-8")
    assert ".plegable-js .seccion.plegada .sec-editar { display: none; }" in css
    assert "scroll-margin-top: calc(var(--alto-indice, 7rem) + 0.5rem)" in css


# ---------- Diseño integrado: datos del panel de cursos (PLAN.md §0, decisión 50, fase 1) ----------

def test_el_resumen_de_un_curso_dice_su_avance_en_una_linea(sesion):  # noqa: F811
    r = servidor._resumen_de_curso("scrum")
    assert (r["avance"], r["alerta"]) == ("0 de 8", False)
    _poner(sesion, "lectura", estado="aprobada", aprobada="2026-10-15T10:00:00")
    assert servidor._resumen_de_curso("scrum")["avance"] == "1 de 8"
    _poner(sesion, "diapositivas", estado="con fallas")
    assert servidor._resumen_de_curso("scrum")["alerta"] is True         # el punto rojo del panel
    for n in (1, 2):
        for clave in ("lectura", "diapositivas", "laboratorio", "actividad"):
            comun.actualizar(sesion, n, clave, estado="aprobada", aprobada="2026-10-15T10:00:00")
    r = servidor._resumen_de_curso("scrum")
    assert (r["avance"], r["alerta"]) == ("Completo", False)


def test_el_resumen_de_un_curso_sin_ficha_confirmada_lo_dice(entorno):
    cliente.post("/cursos", data={"nombre": "Curso vacío"})
    r = servidor._resumen_de_curso("curso-vacio")
    assert (r["nombre"], r["avance"], r["alerta"]) == ("Curso vacío", "Sin ficha", False)


def test_el_panel_trae_todos_los_cursos_en_orden(entorno):
    for nombre in ("Excel", "Ciberseguridad", "Power BI"):
        cliente.post("/cursos", data={"nombre": nombre})
    assert [c["curso"] for c in servidor._cursos_del_panel()] == ["ciberseguridad", "excel", "power-bi"]


def test_abrir_un_curso_lo_anota_como_el_ultimo(sesion, entorno):  # noqa: F811
    from app import cursos
    ruta = entorno["cursos"] / "_sistema" / "ultimo_curso.txt"
    assert cursos.ultimo() is None
    cliente.post("/cursos", data={"nombre": "Excel"})
    cliente.get("/cursos/excel")
    assert cursos.ultimo() == "excel"
    cliente.get("/cursos/scrum/sesiones/1/materiales/lectura")
    assert ruta.read_text(encoding="utf-8") == "scrum"
    cliente.get("/cursos/excel")
    cliente.get("/cursos/scrum/sesiones/1", follow_redirects=False)
    assert cursos.ultimo() == "scrum"
    cliente.get("/")                                                     # el inicio no cambia el último
    assert cursos.ultimo() == "scrum"


def test_el_ultimo_curso_se_ignora_si_ya_no_existe(entorno):
    from app import cursos
    cliente.post("/cursos", data={"nombre": "Excel"})
    cliente.get("/cursos/excel")
    (entorno["cursos"] / "excel" / "curso.json").unlink()
    assert cursos.ultimo() is None
    (entorno["cursos"] / "_sistema" / "ultimo_curso.txt").write_text("../fuera", encoding="utf-8")
    assert cursos.ultimo() is None


# ---------- Diseño integrado: el panel con todos los cursos (decisión 50, fase 2) ----------

def _panel_de(pagina):
    return pagina[pagina.index('<nav class="panel"'):pagina.index("</nav>")]


def test_el_panel_muestra_todos_los_cursos_y_solo_el_abierto_con_sesiones(sesion):  # noqa: F811
    for nombre in ("Excel", "Ciberseguridad"):
        cliente.post("/cursos", data={"nombre": nombre})
    panel = _panel_de(cliente.get("/cursos/scrum").text)
    nombres = [panel.index(f'<span class="panel-curso-nombre">{n}</span>') for n in ("Ciberseguridad", "Excel", "Scrum Master con IA")]
    assert nombres == sorted(nombres)                                        # en el orden de sus carpetas
    for n in ("Ciberseguridad", "Excel", "Scrum Master con IA"):
        assert panel.count(f'<span class="panel-curso-nombre">{n}</span>') == 1
    assert '<li class="panel-linea abierto">' in panel and panel.count('<li class="panel-linea">') == 2
    assert panel.count('<div class="panel-sesiones">') == 1                  # solo el abierto
    assert '<a href="/cursos/scrum" class="panel-titulo" aria-current="page">' in panel
    assert '<a href="/cursos/excel" class="panel-otro">' in panel
    assert '<span class="panel-avance">Sin ficha</span>' in panel
    assert '<span class="panel-avance">0 de 8</span>' in panel
    panel = _panel_de(cliente.get("/cursos/excel").text)                     # otro curso abierto
    assert '<a href="/cursos/scrum" class="panel-otro">' in panel and '<div class="panel-sesiones">' not in panel
    assert "Las sesiones aparecen al confirmar la ficha del curso." in panel


def test_la_linea_de_cada_curso_lleva_a_su_tablero_y_nunca_a_una_ficha(sesion):  # noqa: F811
    import re
    cliente.post("/cursos", data={"nombre": "Excel"})
    panel = _panel_de(cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text)
    lineas = re.findall(r'<a href="([^"]+)" class="panel-(?:titulo|otro)"', panel)
    assert lineas == ["/cursos/excel", "/cursos/scrum"]
    assert '<a href="/cursos/excel/ficha"' not in panel
    assert 'class="panel-mat panel-ficha bien" href="/cursos/scrum/sesiones/1/ficha"' in panel   # el abierto la conserva


def test_el_punto_rojo_del_panel_sale_solo_con_problemas(sesion):  # noqa: F811
    assert "panel-alerta" not in _panel_de(cliente.get("/cursos/scrum").text)
    _poner(sesion, "lectura", estado="con fallas")
    panel = _panel_de(cliente.get("/cursos/scrum").text)
    assert panel.count('<i class="panel-alerta" aria-hidden="true"></i>') == 1
    assert "Tiene un material con problemas." in panel


def test_el_panel_muestra_el_gasto_del_curso_y_el_total(sesion):  # noqa: F811
    _registro(sesion, ("redacción", "S1", 1.5))
    panel = _panel_de(cliente.get("/cursos/scrum").text)
    assert "Gasto del curso <b>" in panel
    assert "Gasto total de AulaLista:" in panel and "Es una estimación, no la factura." in panel


def test_sin_javascript_el_panel_se_ve_entero(sesion):  # noqa: F811
    panel = _panel_de(cliente.get("/cursos/scrum").text)
    assert "<script" not in panel
    # Solo lo que pone JavaScript: el botón «Cursos», el de replegar y el buscador (decisiones 50 f y 52).
    assert panel.count(" hidden") == 3 and '<div class="panel-barra" hidden>' in panel
    assert 'class="panel-replegar" aria-expanded="true" aria-controls="panel-contenido" hidden>' in panel
    assert '<div class="panel-buscar" hidden>' in panel
    css = (servidor.RAIZ / "web" / "estaticos" / "estilo.css").read_text(encoding="utf-8")
    for regla in ("panel-cabeza", "panel-linea:not(.abierto)", "panel-gasto", "panel-sesion:not(.abierta)"):
        assert f".panel.plegado .{regla}" in css                              # se pliega solo con la clase de JavaScript
        assert f"  .{regla}" not in css.split("@media (max-width: 52rem)")[1].split("}")[0]


# ---------- Panel replegable y buscador de cursos (decisión 52) ----------

def test_el_panel_tiene_buscador_de_cursos_con_etiqueta(sesion):  # noqa: F811
    panel = _panel_de(cliente.get("/cursos/scrum").text)
    assert '<label for="panel-buscador" class="sr">Buscar un curso</label>' in panel
    assert '<input type="search" id="panel-buscador"' in panel
    assert '<p class="panel-sin-resultados" role="status"></p>' in panel   # avisa cuando ningún curso coincide
    pagina = cliente.get("/cursos/scrum").text
    assert 'normalize("NFD")' in pagina and "Ningún curso coincide con la búsqueda." in pagina   # sin tildes ni mayúsculas


def test_el_panel_se_repliega_en_pantallas_anchas_y_lo_recuerda(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum").text
    assert '<span class="sr">Replegar el panel de cursos</span>' in pagina
    cabeza = pagina.split("</head>")[0]
    assert 'localStorage.getItem("panel") === "replegado"' in cabeza   # antes de pintar: sin parpadeo
    css = (servidor.RAIZ / "web" / "estaticos" / "estilo.css").read_text(encoding="utf-8")
    anchas = css.split("@media (min-width: 52.0625rem)")[1].split("\n}")[0]
    assert ".panel-replegado .entorno { grid-template-columns: 3.25rem minmax(0, 1fr); }" in anchas
    assert ".panel-replegado #panel-contenido" in anchas
    angostas = css.split("@media (max-width: 52rem)")[1].split("\n}")[0]
    assert ".panel-replegar { display: none !important; }" in angostas   # en el teléfono manda el botón «Cursos»
    assert ".panel.plegado .panel-buscar" in angostas


# ---------- Diseño integrado: inicio y curso nuevo (decisión 50, fase 3) ----------

def test_el_inicio_abre_el_ultimo_curso_usado(sesion):  # noqa: F811
    cliente.post("/cursos", data={"nombre": "Excel"})                    # crear un curso lo abre: queda como último
    r = cliente.get("/", follow_redirects=False)
    assert (r.status_code, r.headers["location"]) == (303, "/cursos/excel")
    cliente.get("/cursos/scrum/sesiones/1/materiales/lectura")
    assert cliente.get("/", follow_redirects=False).headers["location"] == "/cursos/scrum"


def test_sin_cursos_el_inicio_muestra_el_formulario(entorno):
    pagina = cliente.get("/").text
    assert "Todavía no hay cursos." in pagina and '<form method="post" action="/cursos"' in pagina


def test_si_el_ultimo_curso_ya_no_existe_el_inicio_muestra_la_lista(entorno):
    import shutil
    cliente.post("/cursos", data={"nombre": "Excel"})
    cliente.post("/cursos", data={"nombre": "Power BI"})
    shutil.rmtree(entorno["cursos"] / "power-bi")
    r = cliente.get("/", follow_redirects=False)
    assert r.status_code == 200 and '<a href="/cursos/excel">Excel</a>' in r.text


def test_nuevo_abre_la_pagina_corta_y_crear_lleva_al_tablero(sesion):  # noqa: F811
    panel = cliente.get("/cursos/scrum").text
    assert '<a href="/curso-nuevo" class="panel-nuevo">Nuevo</a>' in panel and "Todos los cursos" not in panel
    pagina = cliente.get("/curso-nuevo").text
    assert "<h1>Curso nuevo</h1>" in pagina and '<a href="/cursos/scrum">Volver al curso</a>' in pagina
    r = cliente.post("/cursos", data={"nombre": "Excel"}, follow_redirects=False)
    assert r.headers["location"] == "/cursos/excel"
    cliente.get(r.headers["location"])
    assert cliente.get("/", follow_redirects=False).headers["location"] == "/cursos/excel"


def test_un_error_al_crear_vuelve_a_la_pagina_corta_con_el_aviso(sesion):  # noqa: F811
    r = cliente.post("/cursos", data={"nombre": "Scrum"})
    assert r.url.path == "/curso-nuevo" and "Ya existe un curso" in r.text


# ---------- Diseño integrado: el panel en pantallas angostas (decisión 50, fase 4) ----------

def test_el_boton_cursos_abre_y_cierra_el_panel(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert ('<button type="button" class="panel-boton secundario" aria-expanded="false" '
            'aria-controls="panel-cursos-lista">Cursos</button>') in pagina
    assert '<ul class="panel-cursos" id="panel-cursos-lista"' in pagina
    script = pagina[pagina.index("Panel plegable en pantallas angostas"):]
    assert 'panel.classList.toggle("plegado", !abierto);' in script
    assert 'boton.setAttribute("aria-expanded", String(abierto));' in script
    assert 'boton.textContent = abierto ? "Cerrar" : "Cursos";' in script
    assert 'barra.hidden = false;' in script and "poner(false);" in script     # empieza plegado
    assert 'if (evento.target.closest("a")) poner(false);' in script           # elegir un enlace lo cierra


def test_el_tablero_muestra_la_actividad_web_con_su_estado(sesion):  # noqa: F811
    """Fase 8e (decisión 57): la actividad web es un material más del tablero, con su ícono y su estado."""
    for clave in ("lectura", "diapositivas", "laboratorio"):
        _poner(sesion, clave, estado="aprobada", aprobada="2026-10-15T10:00:00")
    hoja = cliente.get("/cursos/scrum").text.split('<main class="hoja" id="principal" tabindex="-1">')[1]
    # La espera la lectura, que figura aprobada sin su contenido: la ficha no ofrece «Generar».
    assert '<a class="ficha-material vacia bloqueada sigue" href="/cursos/scrum/sesiones/1/materiales/actividad">' in hoja
    assert '<use href="#i-actividad"/>' in hoja
    # La lectura figura aprobada sin su contenido: el tablero pide completar lo que falta, en la actividad.
    assert "Sesión 1: completa lo que falta para generar la actividad web." in hoja
    _poner(sesion, "actividad", estado="con fallas")
    hoja = cliente.get("/cursos/scrum").text.split('<main class="hoja" id="principal" tabindex="-1">')[1]
    assert '<a class="ficha-material error" href="/cursos/scrum/sesiones/1/materiales/actividad">' in hoja
    _poner(sesion, "actividad", estado="aprobada", aprobada="2026-10-21T10:00:00")
    hoja = cliente.get("/cursos/scrum").text.split('<main class="hoja" id="principal" tabindex="-1">')[1]
    assert '<a class="ficha-material bien" href="/cursos/scrum/sesiones/1/materiales/actividad">' in hoja


def test_los_avisos_de_diseno_no_se_cuentan_en_el_resumen_de_la_entrega(sesion):  # noqa: F811
    entrega = {"pregunta": "¿Apruebas la lectura?", "secciones": [
        {"clave": "archivos", "titulo": "Archivos", "lineas": ["S1_Lectura.docx: la lectura."]}]}
    _poner(sesion, "lectura", estado="verificada", entrega=entrega, avisos_de_diseno=["La ficha no trae logo."])
    pagina = cliente.get("/cursos/scrum/sesiones/1/materiales/lectura").text
    assert "1 archivo y 0 decisiones pendientes.</p>" in pagina and "aviso de diseño" not in pagina
    assert "<summary>Detalles de la entrega</summary>" in pagina and "<li>La ficha no trae logo.</li>" in pagina
