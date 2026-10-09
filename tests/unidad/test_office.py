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
