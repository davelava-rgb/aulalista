"""Etapa 5d: revisor independiente, ciclo de corrección y entrega (PLAN.md §5.4, §5.5 y SPEC §8)."""

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app import entrega, herramientas, servidor, tokens
from app.fichas import almacen
from app.materiales import lectura
from app.validacion import revisor
from tests.conftest import pasada, segunda
from tests.unidad.test_lectura import LIMPIA, cambios, con_error, generar, sesion  # noqa: F401

RELLENO = "Los pilares de Scrum son tres."
MANIFIESTO = "El Manifiesto Ágil tiene cuatro aspectos."
CUIDADO = "Revisar el avance sin cambiar nada después."


def hallazgo(oracion: str, defecto: str = "relleno", prueba: str | None = None, donde: str = revisor.MATERIAL,
             n: int = 0) -> dict:
    """Un hallazgo del revisor. Por defecto, la prueba es la misma oración, copiada del material."""
    return {"n": n, "oracion": oracion, "defecto": defecto, "prueba": prueba or oracion, "donde": donde,
            "explicacion": f"{defecto} en la oración."}


def revision(*hallazgos) -> dict:
    return {"hallazgos": list(hallazgos)}


def correccion(*pares, rechazos=None) -> dict:
    """Respuesta simulada de una corrección con hallazgos del revisor."""
    return {**cambios(*pares), "rechazos": rechazos or []}


def columna_revisor(sesion) -> dict[str, str]:
    hoja = openpyxl.load_workbook(lectura.archivos(sesion, 1)["excel"])["Oraciones"]
    return {f[3]: f[8] for f in hoja.iter_rows(min_row=2, values_only=True)}


def hallazgos_excel(sesion) -> list[tuple]:
    hoja = openpyxl.load_workbook(lectura.archivos(sesion, 1)["excel"])["Hallazgos"]
    return list(hoja.iter_rows(min_row=2, values_only=True))


# ---------- Una sesión nueva, con solo tres cosas ----------

def test_el_revisor_es_una_sesion_nueva_con_el_pedido_de_la_skill(sesion):
    _, consulta = generar(sesion, LIMPIA, pasada(), segunda())
    llamada = consulta.llamadas[3]
    pedido, opciones = llamada["prompt"], llamada["options"]
    assert revisor.pedido_de_la_skill() in pedido
    assert pedido.count("Busca errores en este material. Compara cada oración con las fuentes.") == 1
    assert "- Imprecisión:" in pedido and "- Relleno:" in pedido
    # Sesión nueva: no continúa ni retoma la del redactor.
    assert opciones.resume is None and not opciones.continue_conversation and not opciones.fork_session
    assert opciones.model == "claude-opus-5-5"
    # Sin herramientas propias de Claude Code: solo leer y buscar en su carpeta. Nada de escribir.
    assert opciones.tools == [] and opciones.permission_mode == "dontAsk"
    assert opciones.allowed_tools == list(herramientas.HERRAMIENTAS_REVISOR)
    assert list(opciones.mcp_servers) == [herramientas.SERVIDOR_REVISOR]
    assert opciones.cwd == str(lectura.archivos(sesion, 1)["revision"] / "ronda_1")


def test_el_revisor_no_recibe_borradores_ni_la_tabla(sesion):
    _, consulta = generar(sesion, LIMPIA, pasada(), segunda())
    pedido = consulta.llamadas[3]["prompt"]
    assert "Usé una tienda como ejemplo." not in pedido      # «decisiones» del redactor
    assert "REGLAS DE LA SKILL" not in pedido and "Veredicto" not in pedido and "coincide" not in pedido
    assert f"\n1. " in pedido and RELLENO in pedido           # el material final, con oraciones numeradas
    carpeta = lectura.archivos(sesion, 1)["revision"] / "ronda_1"
    assert herramientas.listar(carpeta).splitlines() == [
        "ficha_de_la_sesion.md", "ficha_del_curso.md", "fuentes/silabo.pdf.txt", "material.txt"]
    assert "[página 1] Scrum Master con IA" in (carpeta / "fuentes" / "silabo.pdf.txt").read_text(encoding="utf-8")


def test_las_herramientas_del_revisor_no_salen_de_su_carpeta(sesion):
    generar(sesion, LIMPIA, pasada(), segunda())
    carpeta = lectura.archivos(sesion, 1)["revision"] / "ronda_1"
    assert "No existe" in herramientas.leer(carpeta, "../../lectura/contenido.json", 1, 50)
    assert "No existe" in herramientas.leer(carpeta, str(lectura.archivos(sesion, 1)["contenido"]), 1, 50)
    assert "No existe" in herramientas.leer(carpeta, "../../S1_Lectura_Verificacion.json", 1, 50)
    assert herramientas.leer(carpeta, "material.txt", 1, 1).startswith("1: 1. ")
    assert "material.txt:" in herramientas.buscar_texto(carpeta, "pilares de scrum son")
    assert "fuentes/silabo.pdf.txt:1:" in herramientas.buscar_texto(carpeta, "SCRUM MASTER")
    assert herramientas.buscar_texto(carpeta, "Usé una tienda") == "Sin coincidencias."


# ---------- La prueba de cada hallazgo se comprueba ----------

def test_un_hallazgo_sin_prueba_real_se_descarta(sesion):
    inventado = hallazgo(RELLENO, "imprecisión", prueba="Scrum tiene cinco pilares.", donde="fuentes/silabo.pdf.txt")
    sin_oracion = hallazgo("Esta oración no está en el material.")
    material, consulta = generar(sesion, LIMPIA, pasada(), segunda(), revision(inventado, sin_oracion), revisor=False)
    assert material["estado"] == "verificada"
    assert len(consulta.llamadas) == 4      # nada que corregir
    assert material["revisor"] == [{"ronda": 1, "hallazgos": 0, "descartados": 2, "resuelto": 0, "rechazado": 0, "abierto": 0}]
    descartados = [f for f in hallazgos_excel(sesion) if f[3].startswith("revisor independiente")]
    assert [f[5] for f in descartados] == ["Descartado por el programa: La prueba no aparece tal cual.",
                                           "Descartado por el programa: La oración no está en el material."]


def test_la_prueba_de_una_ficha_o_de_una_fuente_se_ubica_con_su_lugar(sesion):
    generar(sesion, LIMPIA, pasada(), segunda())
    from app.validacion.pasajes import Corpus
    corpus = Corpus.del_curso(sesion, 1)
    oraciones = [{"n": 1, "texto": RELLENO}]
    assert revisor.ubicar_prueba("Scrum Master con IA", "fuentes/silabo.pdf.txt", corpus, oraciones) == "silabo.pdf, página 1"
    assert revisor.ubicar_prueba("Duración de cada Sprint: dos semanas", "ficha_del_curso.md", corpus, oraciones) \
        .startswith("ficha del curso, ")
    assert revisor.ubicar_prueba(RELLENO, "material.txt", corpus, oraciones) == "el material"
    assert revisor.ubicar_prueba("Sprint de tres semanas", "ficha_del_curso.md", corpus, oraciones) is None


# ---------- Corrección y nuevas rondas ----------

def test_menos_de_tres_hallazgos_se_corrigen_y_no_hay_otra_ronda(sesion):
    nueva = "Los pilares sostienen el trabajo del equipo."
    material, consulta = generar(sesion, LIMPIA, pasada(), segunda(), revision(hallazgo(RELLENO)),
                                 correccion((RELLENO, nueva)), pasada(), segunda(), revisor=False)
    assert material["estado"] == "verificada"
    assert len(consulta.llamadas) == 7          # sin un segundo revisor
    pedido = consulta.llamadas[4]["prompt"]
    assert "REVISOR INDEPENDIENTE · relleno · «Los pilares de Scrum son tres.»" in pedido
    assert "«rechazos»" in pedido
    assert "rechazos" in consulta.llamadas[4]["options"].output_format["schema"]["properties"]
    assert material["revisor"] == [{"ronda": 1, "hallazgos": 1, "descartados": 0, "resuelto": 1, "rechazado": 0, "abierto": 0}]
    valide = next(s["lineas"] for s in material["entrega"]["secciones"] if s["clave"] == "valide")
    assert "Revisor independiente, ronda 1: 1 hallazgo (1 corregido, 0 rechazados con su pasaje, 0 abiertos)." in valide
    columna = columna_revisor(sesion)
    assert columna[nueva] == "Ronda 1: relleno. Resuelto."
    assert columna[MANIFIESTO] == "Ronda 1: sin hallazgos."
    assert all(columna.values())                # ninguna fila queda sin nota del revisor
    fila = next(f for f in hallazgos_excel(sesion) if f[3] == "revisor independiente: relleno")
    assert fila[2] == RELLENO and fila[5] == "Ronda 1: relleno. Resuelto en la vuelta 1."


def test_tres_hallazgos_lanzan_un_revisor_nuevo(sesion):
    tres = revision(hallazgo(RELLENO), hallazgo(MANIFIESTO, "imprecisión"), hallazgo(CUIDADO, "ambigüedad"))
    arreglo = correccion((RELLENO, "Los pilares sostienen el trabajo."),
                         (MANIFIESTO, "El Manifiesto Ágil tiene cuatro valores."),
                         (CUIDADO, "Revisar el avance y no cambiar nada."))
    material, consulta = generar(sesion, LIMPIA, pasada(), segunda(), tres, arreglo, pasada(), segunda())
    assert material["estado"] == "verificada"
    assert [r["ronda"] for r in material["revisor"]] == [1, 2]
    segundo = consulta.llamadas[-1]
    assert "Busca errores en este material." in segundo["prompt"]
    assert RELLENO not in segundo["prompt"] and "Los pilares sostienen el trabajo." in segundo["prompt"]
    assert segundo["options"].cwd.endswith("ronda_2")
    assert columna_revisor(sesion)["Los pilares sostienen el trabajo."] == "Ronda 1: relleno. Resuelto. Ronda 2: sin hallazgos."


def test_despues_de_la_tercera_ronda_se_detiene_y_avisa(sesion):
    secuencia = [LIMPIA, pasada(), segunda()]
    oraciones = [RELLENO, MANIFIESTO, CUIDADO]
    for ronda in range(1, lectura.MAX_RONDAS + 1):
        nuevas = [o.rstrip(".") + f" en la ronda {ronda}." for o in oraciones]
        secuencia += [revision(*[hallazgo(o) for o in oraciones]), correccion(*zip(oraciones, nuevas)), pasada(), segunda()]
        oraciones = nuevas
    material, consulta = generar(sesion, *secuencia)
    assert len(consulta.llamadas) == len(secuencia)      # no se lanza un cuarto revisor
    assert [r["ronda"] for r in material["revisor"]] == [1, 2, 3]
    assert material["estado"] == "verificada"
    assert "ronda 3 encontró 3 errores" in material["aviso_del_revisor"]
    no_pude = next(s for s in material["entrega"]["secciones"] if s["clave"] == "no_pude")
    assert no_pude["lineas"] == [material["aviso_del_revisor"]]


def test_un_rechazo_con_un_pasaje_real_queda_anotado(sesion):
    rechazo = {"oracion": RELLENO, "pasaje": "Scrum Master con IA", "fuente": "silabo.pdf"}
    material, consulta = generar(sesion, LIMPIA, pasada(), segunda(), revision(hallazgo(RELLENO, "imprecisión")),
                                 correccion(rechazos=[rechazo]), revisor=False)
    assert material["estado"] == "verificada"
    assert len(consulta.llamadas) == 5          # la lectura no cambió: nada nuevo que validar con IA
    esperado = "Ronda 1: imprecisión. Rechazado: «Scrum Master con IA» (silabo.pdf, página 1)."
    assert columna_revisor(sesion)[RELLENO] == esperado
    assert material["revisor"][0]["rechazado"] == 1


def test_un_rechazo_con_un_pasaje_inventado_sigue_abierto(sesion):
    falso = {"oracion": RELLENO, "pasaje": "Scrum tiene tres pilares según la guía.", "fuente": "silabo.pdf"}
    material, consulta = generar(sesion, LIMPIA, pasada(), segunda(), revision(hallazgo(RELLENO, "imprecisión")),
                                 correccion(rechazos=[falso]), correccion(rechazos=[falso]), revisor=False)
    assert "Sigue abierto" in consulta.llamadas[5]["prompt"]
    assert len(consulta.llamadas) == 2 + 2 + lectura.VUELTAS_POR_RONDA   # tope de vueltas de la ronda
    assert material["estado"] == "con fallas"
    assert material["problemas"][0].startswith("REVISOR INDEPENDIENTE · imprecisión · «Los pilares de Scrum son tres.»")
    assert columna_revisor(sesion)[RELLENO] == "Ronda 1: imprecisión. Abierto: queda en decisiones pendientes."
    with pytest.raises(lectura.NoSePuedeAprobar):
        lectura.aprobar(sesion, 1)


def test_sin_lectura_limpia_no_se_lanza_el_revisor(sesion):
    mala = con_error("Lee este bloque en 10 minutos.")
    material, consulta = generar(sesion, mala, *[cambios()] * lectura.MAX_CORRECCIONES)
    assert material["estado"] == "con fallas" and material["revisor"] == []
    assert not any("Busca errores" in l["prompt"] for l in consulta.llamadas)
    assert set(columna_revisor(sesion).values()) == {"No pasó por el revisor: la lectura quedó con problemas abiertos."}


# ---------- Entrega ----------

TITULOS = ["Archivos", "Qué probé", "Qué validé", "Qué no pude probar", "Qué decidí por mi cuenta"]


def test_la_entrega_tiene_los_puntos_del_spec_en_orden(sesion):
    material, _ = generar(sesion, LIMPIA, pasada(), segunda())
    datos = material["entrega"]
    assert [s["titulo"] for s in datos["secciones"]] == TITULOS      # sin decisiones pendientes: se omite
    assert datos["pregunta"] == "¿Apruebas este material para pasar a la siguiente etapa?"
    secciones = {s["clave"]: s["lineas"] for s in datos["secciones"]}
    assert secciones["archivos"][0] == "S1_Lectura.docx: la lectura, 2 páginas, con 2 bloques."
    assert secciones["archivos"][1].startswith("S1_Lectura_Verificacion.xlsx: el archivo de verificación")
    assert secciones["probe"][0] == "Conté las páginas con Word: 2. El máximo es 6."
    assert secciones["valide"][0].startswith("Verificador: Oraciones: ") and "Fallas: 0" in secciones["valide"][0]
    assert "Revisor independiente, ronda 1: 0 hallazgos." in secciones["valide"]
    assert secciones["valide"][-1].startswith("Costo de esta lectura: 4 llamadas, ")
    assert secciones["decidi"] == ["Usé una tienda como ejemplo."]
    texto = lectura.archivos(sesion, 1)["entrega"].read_text(encoding="utf-8")
    posiciones = [texto.index(f"## {t}") for t in TITULOS]
    assert posiciones == sorted(posiciones)
    assert texto.rstrip().endswith(entrega.PREGUNTA)


def test_con_problemas_la_entrega_lista_las_decisiones_pendientes(sesion):
    material, _ = generar(sesion, con_error("Lee este bloque en 10 minutos."), *[cambios()] * lectura.MAX_CORRECCIONES)
    titulos = [s["titulo"] for s in material["entrega"]["secciones"]]
    assert titulos == TITULOS[:3] + ["Decisiones pendientes"] + TITULOS[3:]
    pendientes = material["entrega"]["secciones"][3]["lineas"]
    assert pendientes == ["FALLA · tiempo · «Lee este bloque en 10 minutos.»: dice «minutos»"]
    assert "La lectura no pasó por el revisor independiente porque quedó con problemas abiertos." in \
        material["entrega"]["secciones"][4]["lineas"]


def test_el_costo_de_la_entrega_es_solo_el_de_esta_generacion(sesion):
    generar(sesion, LIMPIA, pasada(), segunda())
    # La segunda vez, las pasadas reusan los resultados guardados: solo la redacción y el revisor llaman a Claude.
    material, _ = generar(sesion, LIMPIA)
    assert material["costo"]["llamadas"] == 2
    assert tokens.total("scrum")["llamadas"] >= 6
    assert tokens.total("scrum", sesion="S1", material="otro")["llamadas"] == 0


# ---------- Aprobación desde la página ----------

cliente = TestClient(servidor.app)


def test_el_profesor_aprueba_la_lectura_desde_la_pagina(sesion):
    generar(sesion, LIMPIA, pasada(), segunda())
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    for titulo in TITULOS:
        assert titulo in pagina
    assert entrega.PREGUNTA in pagina and "Aprobar la lectura" in pagina
    assert cliente.get("/cursos/scrum/sesiones/1/descargar/S1_Lectura_Entrega.md").status_code == 200
    r = cliente.post("/cursos/scrum/sesiones/1/materiales/lectura/aprobar", follow_redirects=False)
    assert r.status_code == 303
    assert lectura.estado(sesion, 1)["estado"] == "aprobada"
    assert "Aprobada" in cliente.get("/cursos/scrum/sesiones/1").text


def test_no_se_aprueba_una_lectura_desactualizada_ni_con_problemas(sesion):
    generar(sesion, LIMPIA, pasada(), segunda())
    almacen.marcar_desactualizados(sesion, 1)
    r = cliente.post("/cursos/scrum/sesiones/1/materiales/lectura/aprobar", follow_redirects=True)
    assert lectura.estado(sesion, 1)["estado"] == "verificada"
    assert "Las fichas cambiaron" in r.text
    generar(sesion, con_error("Lee este bloque en 10 minutos."), *[cambios()] * lectura.MAX_CORRECCIONES)
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    assert "Aprobar la lectura" not in pagina and "Decisiones pendientes" in pagina
    cliente.post("/cursos/scrum/sesiones/1/materiales/lectura/aprobar")
    assert lectura.estado(sesion, 1)["estado"] == "con fallas"


def test_la_entrega_se_arma_en_el_orden_fijo():
    datos = entrega.componer(archivos=["a"], probe=["b"], valide=["c"], pendientes=[], no_pude=["d"], decidi=["e"])
    assert [s["clave"] for s in datos["secciones"]] == ["archivos", "probe", "valide", "no_pude", "decidi"]
    con = entrega.componer(archivos=["a"], probe=["b"], valide=["c"], pendientes=["p"], no_pude=["d"], decidi=["e"])
    assert [s["clave"] for s in con["secciones"]][3] == "pendientes"


def test_generar_de_nuevo_borra_la_entrega_y_la_aprobacion_anteriores(sesion):
    generar(sesion, LIMPIA, pasada(), segunda())
    lectura.aprobar(sesion, 1)
    with pytest.raises(Exception):
        generar(sesion, revisor=False)      # la redacción falla: no hay respuesta
    material = lectura.estado(sesion, 1)
    assert material["estado"] == "error" and material["entrega"] == {} and material["aprobada"] == ""
    assert "Aprobar la lectura" not in cliente.get("/cursos/scrum/sesiones/1").text
