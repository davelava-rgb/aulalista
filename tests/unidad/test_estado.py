"""El estado de la sesión: escrituras que se cruzan, qué cambios desactualizan y la numeración de la ficha."""

import threading

from fastapi.testclient import TestClient

from app import servidor
from app.fichas import almacen
from app.materiales import comun
from tests.unidad.test_lectura import sesion  # noqa: F401

cliente = TestClient(servidor.app)


def test_leer_mientras_se_escribe_no_falla(sesion):  # noqa: F811
    """Antes, una página que leía el estado mientras el trabajo en segundo plano lo escribía lo encontraba vacío
    y respondía «Internal Server Error»."""
    errores = []

    def escribir():
        for n in range(150):
            comun.avance(sesion, 1, "actividad", f"Vuelta {n}.")

    def leer():
        for _ in range(300):
            try:
                almacen.cargar_estado(sesion, 1)
            except Exception as error:   # noqa: BLE001
                errores.append(repr(error))

    hilos = [threading.Thread(target=escribir), threading.Thread(target=leer), threading.Thread(target=leer)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    assert errores == []
    assert len(almacen.cargar_estado(sesion, 1)["materiales"]["actividad"]["avance"]) == 150


def _cambiar(carpeta, campo: str, valor: str) -> None:
    ficha = almacen.cargar(carpeta, "sesion", 1)
    ficha["campos"][campo] = {"valor": valor, "origen": "profesor", "estado": ""}
    almacen.guardar(carpeta, "sesion", 1, ficha)


def test_cambiar_solo_los_materiales_de_la_sesion_no_desactualiza_lo_generado(sesion):  # noqa: F811
    comun.actualizar(sesion, 1, "diapositivas", estado="trabajando")   # así empieza cada generación
    comun.actualizar(sesion, 1, "diapositivas", estado="aprobada")
    _cambiar(sesion, "materiales.cuales", "diapositivas, laboratorio y actividad web")
    assert almacen.marcar_desactualizados(sesion, 1) == []
    assert not comun.estado(sesion, 1, "diapositivas").get("desactualizado")
    _cambiar(sesion, "lectura.cuidado", "Otro riesgo")
    assert almacen.marcar_desactualizados(sesion, 1) == ["diapositivas"]
    assert comun.estado(sesion, 1, "diapositivas")["desactualizado"] is True


def test_una_sesion_sin_huella_tampoco_se_desactualiza_por_cambiar_solo_los_materiales(sesion):  # noqa: F811
    # Sin «trabajando» no se guarda la huella: así quedaron las sesiones generadas antes de que existiera.
    comun.actualizar(sesion, 1, "laboratorio", estado="aprobada")
    assert "huella_fichas" not in almacen.cargar_estado(sesion, 1)
    anterior = almacen.ultima_confirmada(sesion, 1)
    assert anterior is not None
    _cambiar(sesion, "materiales.cuales", "diapositivas y laboratorio")
    assert almacen.marcar_desactualizados(sesion, 1, anterior) == []
    assert almacen.cargar_estado(sesion, 1)["huella_fichas"] == almacen.huella_de_fichas(sesion, 1)
    _cambiar(sesion, "lectura.cuidado", "Otro riesgo")
    assert almacen.marcar_desactualizados(sesion, 1, anterior) == ["laboratorio"]


def test_una_sesion_sin_huella_ni_confirmacion_anterior_se_desactualiza_entera(sesion):  # noqa: F811
    # Así llega un cambio de la ficha del curso: no hay con qué comparar y se marca todo, como antes.
    comun.actualizar(sesion, 1, "laboratorio", estado="aprobada")
    _cambiar(sesion, "materiales.cuales", "diapositivas y laboratorio")
    assert almacen.marcar_desactualizados(sesion, 1) == ["laboratorio"]


def test_la_ficha_no_pide_confirmar_un_cambio_solo_de_materiales(sesion):  # noqa: F811
    comun.actualizar(sesion, 1, "lectura", estado="aprobada")
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    assert 'const SIN_EFECTO = ["materiales.cuales"];' in pagina
    assert "sinGuardar && conEfecto && !window.confirm" in pagina
    assert "Cambiar solo «Materiales de esta sesión» no lo desactualiza." in pagina


def test_las_secciones_de_la_ficha_se_numeran_en_el_orden_en_que_se_ven(sesion):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1/ficha").text
    titulos = [t.split("</h2>")[0].split(">")[-1] for t in pagina.split('<h2 id="t-seccion-')[1:]]
    assert titulos[:2] == ["1. Sesión", "2. Materiales de esta sesión"]
    assert [t.split(".")[0] for t in titulos] == [str(n) for n in range(1, len(titulos) + 1)]
    assert "6. Materiales de esta sesión" not in pagina
