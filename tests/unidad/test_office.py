"""Word, PowerPoint y Excel se abren y se cierran sin quedar abiertos (PLAN.md §6, etapa 2)."""

import pytest

from app import office


procesos = office.procesos


@pytest.mark.parametrize(
    "abrir, ejecutable",
    [(office.abrir_word, "WINWORD.EXE"), (office.abrir_excel, "EXCEL.EXE")],
)
def test_abre_y_cierra_sin_dejar_procesos(abrir, ejecutable):
    antes = procesos(ejecutable)
    with abrir() as app:
        assert app.Visible is False or app.Visible == 0
    assert procesos(ejecutable) <= antes


def test_powerpoint_abre_y_cierra_sin_dejar_procesos():
    if office.proceso_activo("POWERPNT.EXE"):
        pytest.skip("PowerPoint ya está abierto: no se cierra el trabajo del profesor.")
    with office.abrir_powerpoint():
        pass
    assert not office.proceso_activo("POWERPNT.EXE")


def test_si_powerpoint_ya_estaba_abierto_no_se_cierra(monkeypatch):
    cerrado = []

    class AppFalsa:
        Visible = True
        def Quit(self):
            cerrado.append(True)

    monkeypatch.setattr(office, "proceso_activo", lambda _: True)
    monkeypatch.setattr(office.win32com.client, "DispatchEx", lambda _: AppFalsa())
    with office.abrir_powerpoint():
        pass
    assert cerrado == []


def test_word_a_pdf_cierra_word_aunque_falle(tmp_path):
    antes = procesos("WINWORD.EXE")
    roto = tmp_path / "roto.docx"
    roto.write_bytes(b"no es un Word")
    with pytest.raises(Exception):
        office.word_a_pdf(roto, tmp_path / "roto.pdf")
    assert procesos("WINWORD.EXE") <= antes


def test_powerpoint_mide_el_texto_que_no_cabe_y_guarda_una_imagen_por_diapositiva(tmp_path):
    """Material sembrado: la segunda diapositiva tiene un texto que se sale de su recuadro."""
    from tests.sembrados.diapositivas import TEXTO_QUE_NO_CABE, con_desborde
    abierto_antes = office.proceso_activo("POWERPNT.EXE")
    medicion = office.medir_diapositivas(con_desborde(tmp_path / "sembrado.pptx"), tmp_path / "imagenes")
    assert medicion.diapositivas == 2
    assert [d.diapositiva for d in medicion.desbordes] == [2]
    assert medicion.desbordes[0].texto.startswith(TEXTO_QUE_NO_CABE.strip()[:40]) and medicion.desbordes[0].sobra_cm > 1
    assert [i.name for i in medicion.imagenes] == ["diapositiva_01.png", "diapositiva_02.png"]
    assert all(i.stat().st_size > 0 for i in medicion.imagenes)
    if not abierto_antes:
        assert not office.proceso_activo("POWERPNT.EXE")


def test_excel_lee_la_lista_de_opciones_y_se_cierra(tmp_path):
    """PLAN.md §0, decisión 60: el Excel instalado ofrece en la celda las opciones que escribió AulaLista."""
    from app.materiales import estilo, practica
    from app.materiales.contenido import Laboratorio
    from tests.sembrados import laboratorio as sembrados
    archivo = Laboratorio.model_validate(sembrados.con_listas()).archivos[0]
    identidad = estilo.Identidad(**estilo.PALETA_SOBRIA, tipografia="Calibri", logo=None)
    ruta = practica.crear_excel(archivo, identidad, tmp_path / archivo.nombre)
    antes = procesos("EXCEL.EXE")
    assert office.lista_de_la_celda(ruta, "Pedidos", "D3") == ["Sí", "No"]
    assert office.lista_de_la_celda(ruta, "Pedidos", "E2") == sembrados.CONCEPTOS
    assert office.lista_de_la_celda(ruta, "Pedidos", "A2") is None
    assert procesos("EXCEL.EXE") <= antes
