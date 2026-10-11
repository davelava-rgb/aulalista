"""Revisor independiente opcional, entrega y aprobación (PLAN.md §0, decisión 22 y SPEC §8)."""

import asyncio

import openpyxl
import pytest
from fastapi.testclient import TestClient

from app import entrega, herramientas, servidor, tokens
from app.fichas import almacen
from app.materiales import lectura
from app.validacion import revisor
from tests.conftest import consulta_en_secuencia
from tests.unidad.test_lectura import (  # noqa: F401  (sesion es la base de prueba)
    LIMPIA, cambios, con_error, error, generar, sesion)
from tests.unidad.test_lectura import revision as respuesta

RELLENO = "Los pilares de Scrum son tres."
MANIFIESTO = "El Manifiesto Ágil tiene cuatro aspectos."
SIN_HALLAZGOS = {"hallazgos": [], "bloques": [], "lista": []}


def hallazgo(oracion: str, defecto: str = "relleno", prueba: str | None = None, donde: str = "material.txt") -> dict:
    """Un hallazgo del revisor. Por defecto, la prueba es la misma oración, copiada del material."""
    return {"n": 0, "oracion": oracion, "defecto": defecto, "prueba": prueba or oracion, "donde": donde,
            "explicacion": f"{defecto} en la oración."}


def revisar(sesion, *salidas):
    """Corre el revisor opcional sobre la lectura ya generada."""
    consulta = consulta_en_secuencia(*(salidas or [SIN_HALLAZGOS]))
    material = asyncio.run(lectura.revisar_con_revisor(sesion, "scrum", 1, consulta=consulta))
    return material, consulta


def hallazgos_excel(sesion) -> list[tuple]:
    hoja = openpyxl.load_workbook(lectura.archivos(sesion, 1)["excel"])["Hallazgos"]
    return list(hoja.iter_rows(min_row=2, values_only=True))


# ---------- El revisor no corre solo: lo pide el profesor ----------

def test_el_revisor_no_corre_al_generar(sesion):
    material, consulta = generar(sesion, LIMPIA)
    assert not any("Busca errores en este material." in l["prompt"] for l in consulta.llamadas)
    assert material["revisor"] == {}


def test_el_revisor_es_una_sesion_nueva_con_el_pedido_de_la_skill(sesion):
    generar(sesion, LIMPIA)
    _, consulta = revisar(sesion)
    llamada = consulta.llamadas[0]
    pedido, opciones = llamada["prompt"], llamada["options"]
    assert revisor.PEDIDO_DE_AULALISTA in pedido
    assert "- Imprecisión:" in pedido and "- Relleno:" in pedido
    # Sesión nueva: no continúa ni retoma la del redactor.
    assert opciones.resume is None and not opciones.continue_conversation and not opciones.fork_session
    assert opciones.model == "claude-opus-5-5"
    # Sin herramientas propias de Claude Code: solo leer y buscar en su carpeta. Nada de escribir.
    assert opciones.tools == [] and opciones.permission_mode == "dontAsk"
    assert opciones.allowed_tools == list(herramientas.HERRAMIENTAS_REVISOR)
    assert list(opciones.mcp_servers) == [herramientas.SERVIDOR_REVISOR]
    assert opciones.cwd == str(lectura.archivos(sesion, 1)["revision"] / "ronda_1")


def test_el_revisor_no_recibe_borradores(sesion):
    generar(sesion, LIMPIA)
    _, consulta = revisar(sesion)
    pedido = consulta.llamadas[0]["prompt"]
    assert "Usé una tienda como ejemplo." not in pedido      # «decisiones» del redactor
    assert "REGLAS DE LA SKILL" not in pedido          # las reglas y el contexto del redactor
    assert "\n1. " in pedido and RELLENO in pedido           # el material final, con oraciones numeradas
    carpeta = lectura.archivos(sesion, 1)["revision"] / "ronda_1"
    assert herramientas.listar(carpeta).splitlines() == [
        "ficha_de_la_sesion.md", "ficha_del_curso.md", "fuentes/silabo.pdf.txt", "material.txt"]
    assert "No existe" in herramientas.leer(carpeta, "../../lectura/contenido.json", 1, 50)
    assert "No existe" in herramientas.leer(carpeta, "../../S1_Lectura_Verificacion.json", 1, 50)
    assert "material.txt:" in herramientas.buscar_texto(carpeta, "pilares de scrum son")


def test_lo_que_encuentra_el_revisor_queda_pendiente_y_no_se_corrige(sesion):
    generar(sesion, LIMPIA)
    lectura.aprobar(sesion, 1)
    falso = hallazgo(MANIFIESTO, "imprecisión", prueba="Scrum tiene cinco pilares.", donde="fuentes/silabo.pdf.txt")
    material, consulta = revisar(sesion, {"hallazgos": [hallazgo(RELLENO), falso], "bloques": [], "lista": []})
    assert len(consulta.llamadas) == 1          # no corrige
    assert material["estado"] == "con pendientes" and material["aprobada"] == ""
    assert material["problemas"] == [revisor.Hallazgo(1, 0, RELLENO, "relleno", RELLENO, "el material",
                                                      "relleno en la oración.").describir()]
    assert material["revisor"]["hallazgos"] == 1 and material["revisor"]["descartados"] == 1
    fila = next(f for f in hallazgos_excel(sesion) if f[3] == "revisor independiente: relleno")
    assert fila[0] == "REVISOR" and fila[5] == "Pendiente: decides tú."
    valide = next(s["lineas"] for s in material["entrega"]["secciones"] if s["clave"] == "valide")
    assert any(l.startswith("Revisor independiente (lo pediste tú): 1 hallazgo con prueba, 1 descartados.") for l in valide)
    assert lectura.aprobar(sesion, 1)["estado"] == "aprobada"   # el profesor decide


def test_sin_hallazgos_la_lectura_queda_como_estaba(sesion):
    generar(sesion, LIMPIA)
    material, _ = revisar(sesion)
    assert material["estado"] == "verificada" and material["revisor"]["hallazgos"] == 0


def test_sin_lectura_generada_o_con_fallas_no_se_lanza(sesion):
    with pytest.raises(lectura.NoSePuedeRevisar):
        revisar(sesion)
    generar(sesion, con_error("Lee este bloque en 10 minutos."), *[cambios()] * lectura.VUELTAS_DEL_VERIFICADOR,
            revisar=False)
    with pytest.raises(lectura.NoSePuedeRevisar):
        revisar(sesion)


def test_si_el_revisor_falla_la_lectura_vuelve_a_su_estado(sesion):
    generar(sesion, LIMPIA)
    with pytest.raises(Exception):
        revisar(sesion, {"no": "es lo que pide el esquema"})
    material = lectura.estado(sesion, 1)
    assert material["estado"] == "verificada"
    assert "El revisor independiente se detuvo por un error" in material["avance"][-1]


def test_la_prueba_de_una_ficha_o_de_una_fuente_se_ubica_con_su_lugar(sesion):
    generar(sesion, LIMPIA)
    from app.validacion.pasajes import Corpus
    corpus = Corpus.del_curso(sesion, 1)
    oraciones = [{"n": 1, "texto": RELLENO}]
    assert revisor.ubicar_prueba("Scrum Master con IA", "fuentes/silabo.pdf.txt", corpus, oraciones) == "silabo.pdf, página 1"
    assert revisor.ubicar_prueba(RELLENO, "material.txt", corpus, oraciones) == "el material"
    assert revisor.ubicar_prueba("Sprint de tres semanas", "ficha_del_curso.md", corpus, oraciones) is None


# ---------- Entrega ----------

TITULOS = ["Archivos", "Qué probé", "Qué validé", "Qué no pude probar", "Qué decidí por mi cuenta"]


def test_la_entrega_tiene_los_puntos_del_spec_en_orden(sesion):
    material, _ = generar(sesion, LIMPIA)
    datos = material["entrega"]
    assert [s["titulo"] for s in datos["secciones"]] == TITULOS      # sin decisiones pendientes: se omite
    assert datos["pregunta"] == "¿Apruebas este material para pasar a la siguiente etapa?"
    secciones = {s["clave"]: s["lineas"] for s in datos["secciones"]}
    assert secciones["archivos"][0] == "S1_Lectura.docx: la lectura, 2 páginas, con 2 bloques."
    assert secciones["archivos"][1] == "S1_Lectura_Verificacion.xlsx: el archivo de verificación, con la hoja Hallazgos."
    assert secciones["probe"][0] == "Conté las páginas con Word: 2. El máximo es 6."
    assert secciones["valide"][0].startswith("Verificador: Oraciones: ") and "Fallas: 0" in secciones["valide"][0]
    assert "Revisión del contenido: 5 bloques, 0 errores con prueba." in secciones["valide"]
    assert secciones["valide"][-1].startswith("Costo de esta lectura: 2 llamadas, ")
    assert secciones["no_pude"] == ["Nada: la lectura no tiene ejercicios que ejecutar."]
    assert secciones["decidi"] == ["Usé una tienda como ejemplo."]
    texto = lectura.archivos(sesion, 1)["entrega"].read_text(encoding="utf-8")
    posiciones = [texto.index(f"## {t}") for t in TITULOS]
    assert posiciones == sorted(posiciones)
    assert texto.rstrip().endswith(entrega.PREGUNTA)


def test_con_pendientes_la_entrega_los_lista(sesion):
    material, _ = generar(sesion, LIMPIA, respuesta(error(RELLENO, "vacío")), cambios(), revisar=False)
    titulos = [s["titulo"] for s in material["entrega"]["secciones"]]
    assert titulos == TITULOS[:3] + ["Decisiones pendientes"] + TITULOS[3:]
    assert material["entrega"]["secciones"][3]["lineas"] == material["problemas"]


def test_el_costo_de_la_entrega_es_solo_el_de_esta_generacion(sesion):
    generar(sesion, LIMPIA)
    material, _ = generar(sesion, LIMPIA)
    assert material["costo"]["llamadas"] == 2
    assert tokens.total("scrum")["llamadas"] >= 4
    assert tokens.total("scrum", sesion="S1", material="otro")["llamadas"] == 0


# ---------- Aprobación y botones de la página ----------

cliente = TestClient(servidor.app)


def test_el_profesor_aprueba_la_lectura_desde_la_pagina(sesion):
    generar(sesion, LIMPIA)
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    for titulo in TITULOS:
        assert titulo in pagina
    assert entrega.PREGUNTA in pagina and "Aprobar la lectura" in pagina and "Pedir revisor independiente" in pagina
    assert cliente.get("/cursos/scrum/sesiones/1/descargar/S1_Lectura_Entrega.md").status_code == 200
    r = cliente.post("/cursos/scrum/sesiones/1/materiales/lectura/aprobar", follow_redirects=False)
    assert r.status_code == 303
    assert lectura.estado(sesion, 1)["estado"] == "aprobada"
    assert "Aprobada" in cliente.get("/cursos/scrum/sesiones/1").text


def test_con_pendientes_la_pagina_deja_aprobar(sesion):
    generar(sesion, LIMPIA, respuesta(error(RELLENO, "vacío")), cambios(), revisar=False)
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    assert "Lista, con pendientes de la revisión" in pagina and "Aprobar la lectura" in pagina
    cliente.post("/cursos/scrum/sesiones/1/materiales/lectura/aprobar")
    assert lectura.estado(sesion, 1)["estado"] == "aprobada"


def test_no_se_aprueba_una_lectura_desactualizada_ni_con_fallas(sesion):
    generar(sesion, LIMPIA)
    almacen.marcar_desactualizados(sesion, 1)
    r = cliente.post("/cursos/scrum/sesiones/1/materiales/lectura/aprobar", follow_redirects=True)
    assert lectura.estado(sesion, 1)["estado"] == "verificada"
    assert "Las fichas cambiaron" in r.text
    generar(sesion, con_error("Lee este bloque en 10 minutos."), *[cambios()] * lectura.VUELTAS_DEL_VERIFICADOR,
            revisar=False)
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    assert "Aprobar la lectura" not in pagina and "Decisiones pendientes" in pagina
    assert "Pedir revisor independiente" not in pagina
    cliente.post("/cursos/scrum/sesiones/1/materiales/lectura/aprobar")
    assert lectura.estado(sesion, 1)["estado"] == "con fallas"


def test_el_boton_del_revisor_lo_lanza_en_segundo_plano(sesion, monkeypatch):
    import threading
    generar(sesion, LIMPIA)
    llamadas = []
    original = lectura.revisar_con_revisor

    async def simulado(carpeta, curso, numero):
        llamadas.append(numero)
        return await original(carpeta, curso, numero, consulta=consulta_en_secuencia(SIN_HALLAZGOS))

    monkeypatch.setattr(lectura, "revisar_con_revisor", simulado)
    r = cliente.post("/cursos/scrum/sesiones/1/materiales/lectura/revisor", follow_redirects=False)
    assert r.status_code == 303
    for hilo in [h for h in threading.enumerate() if h.daemon]:
        hilo.join(timeout=30)
    assert llamadas == [1]
    assert lectura.estado(sesion, 1)["revisor"]["hallazgos"] == 0


def test_la_entrega_se_arma_en_el_orden_fijo():
    datos = entrega.componer(archivos=["a"], probe=["b"], valide=["c"], pendientes=[], no_pude=["d"], decidi=["e"])
    assert [s["clave"] for s in datos["secciones"]] == ["archivos", "probe", "valide", "no_pude", "decidi"]
    con = entrega.componer(archivos=["a"], probe=["b"], valide=["c"], pendientes=["p"], no_pude=["d"], decidi=["e"])
    assert [s["clave"] for s in con["secciones"]][3] == "pendientes"


def test_generar_de_nuevo_borra_la_entrega_y_la_aprobacion_anteriores(sesion):
    generar(sesion, LIMPIA)
    lectura.aprobar(sesion, 1)
    with pytest.raises(Exception):
        generar(sesion, revisar=False)      # la redacción falla: no hay respuesta
    material = lectura.estado(sesion, 1)
    assert material["estado"] == "error" and material["entrega"] == {} and material["aprobada"] == ""
    assert "Aprobar la lectura" not in cliente.get("/cursos/scrum/sesiones/1").text

# ---------- Lista de verificación por material (PLAN.md §0, decisión 11) ----------

def test_cada_material_recibe_solo_sus_preguntas_de_la_lista():
    from app.validacion import pasada2
    completa = pasada2.lista_completa()
    assert len(completa) == 14
    lectura_ = pasada2.lista_de_verificacion("Lectura")
    laboratorio = pasada2.lista_de_verificacion("Laboratorio")
    guia = pasada2.lista_de_verificacion("Guía del profesor")
    evaluacion = pasada2.lista_de_verificacion("Evaluación")
    assert lectura_ == [p for p in completa if p.startswith((
        "¿Cada sección aporta", "¿Hay alguna frase con dos ideas", "¿Hay contenido de sesiones posteriores"))]
    assert pasada2.lista_de_verificacion("Diapositivas") == lectura_     # PLAN.md §0, decisión 20
    assert pasada2.campos_de("Lectura") == pasada2.campos_de("Diapositivas") == ["que_puede_hacer", "dos_lecturas"]
    assert pasada2.campos_de("Laboratorio") == pasada2.CAMPOS
    assert any(p.startswith("En el laboratorio:") for p in laboratorio)
    assert not any(p.startswith("En el laboratorio:") for p in lectura_ + evaluacion)
    assert any(p.startswith("En la evaluación:") for p in evaluacion)
    assert not any(p.startswith("¿Algún material da la respuesta") for p in guia)   # la guía trae las respuestas
    assert any(p.startswith("¿Ejecutaste cada ejercicio") for p in guia + laboratorio)
    # Lo que revisa el programa no va a la IA en ningún material.
    for material in pasada2.TODOS:
        preguntas = pasada2.lista_de_verificacion(material)
        assert "¿El diseño es uniforme?" not in preguntas
        assert not any("minutos, puntos, notas" in p for p in preguntas)


def test_una_pregunta_nueva_en_la_skill_detiene_el_programa(monkeypatch):
    from app.validacion import pasada2
    monkeypatch.setattr(pasada2, "lista_completa", lambda: ["¿Una pregunta que nadie repartió?"])
    with pytest.raises(KeyError, match="pregunta nueva"):
        pasada2.lista_de_verificacion("Lectura")


def test_si_la_skill_cambia_el_pedido_del_revisor_el_programa_se_detiene(sesion, monkeypatch):
    generar(sesion, LIMPIA)
    monkeypatch.setattr(revisor, "pedido_de_la_skill", lambda: "Otro pedido.")
    with pytest.raises(KeyError, match="decisión 12"):
        revisar(sesion)


def test_la_carpeta_del_revisor_se_libera_aunque_windows_no_deje_borrarla(sesion, tmp_path, monkeypatch):
    from app.validacion import revisor as modulo
    carpeta = tmp_path / "revisor" / "ronda_1"
    (carpeta / "fuentes").mkdir(parents=True)
    (carpeta / "fuentes" / "viejo.txt").write_text("de la generación anterior", encoding="utf-8")
    oraciones = [{"n": 1, "huella": "h1", "texto": "Scrum tiene tres pilares."}]
    # Caso normal: la carpeta vieja se mueve, se borra y la nueva queda con el mismo nombre.
    usada = modulo.preparar_carpeta(carpeta, sesion, 1, oraciones)
    assert usada == carpeta and not (carpeta / "fuentes" / "viejo.txt").exists()
    assert list(carpeta.parent.glob("ronda_1.borrar-*")) == []
    # Windows no deja mover la carpeta (la tiene abierta otro programa): se usa una carpeta nueva.
    def sin_permiso(self, destino):
        raise PermissionError(5, "Acceso denegado")
    monkeypatch.setattr(type(carpeta), "rename", sin_permiso)
    usada = modulo.preparar_carpeta(carpeta, sesion, 1, oraciones)
    assert usada != carpeta and usada.name.startswith("ronda_1-")
    assert (usada / "material.txt").read_text(encoding="utf-8").startswith("1. Scrum tiene tres pilares.")
