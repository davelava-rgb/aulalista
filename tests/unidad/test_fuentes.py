"""Etapa 2: cada formato da sus pasajes con la ubicación correcta (PLAN.md §6)."""

import asyncio
import json

import pytest

from app.fuentes import convertir
from tests.fixtures import fuentes


class LectorSimulado:
    """Reemplaza a Claude: devuelve una línea fija y cuenta las llamadas."""

    def __init__(self, lineas=("Texto leído por IA",)):
        self.lineas = list(lineas)
        self.llamadas = []

    async def __call__(self, imagen, tipo, etiqueta):
        self.llamadas.append({"tipo": tipo, "etiqueta": etiqueta, "bytes": len(imagen)})
        return self.lineas


def correr(coro):
    return asyncio.run(coro)


def textos_y_ubicaciones(conversion):
    return [(p["texto"], p["ubicacion"]) for p in conversion.pasajes]


def test_pdf_da_cada_pasaje_con_su_pagina_y_numero_impreso(tmp_path):
    conversion = correr(convertir.extraer_pdf(fuentes.pdf_con_texto(tmp_path / "a.pdf"), None))
    assert textos_y_ubicaciones(conversion) == [
        ("Scrum tiene tres pilares.", "página 1"),
        ("Scrum es gratuito.", "página 2 · número impreso 43"),
    ]
    assert conversion.revisar is False


def test_pagina_escaneada_la_lee_la_ia_y_queda_para_revisar(tmp_path):
    lector = LectorSimulado(["Texto escaneado"])
    conversion = correr(convertir.extraer_pdf(fuentes.pdf_escaneado(tmp_path / "e.pdf"), lector))
    assert textos_y_ubicaciones(conversion) == [
        ("Página con texto.", "página 1"),
        ("Texto escaneado", "página 2 · leída por IA"),
    ]
    assert conversion.pasajes[1]["origen"] == "ia"
    assert conversion.revisar is True
    assert len(lector.llamadas) == 1 and lector.llamadas[0]["tipo"] == "image/png"


def test_pagina_escaneada_sin_lector_queda_como_aviso(tmp_path):
    conversion = correr(convertir.extraer_pdf(fuentes.pdf_escaneado(tmp_path / "e.pdf"), None))
    assert conversion.avisos == ["Página 2: es una imagen y no se leyó."]


def test_word_conserva_las_paginas_reales_de_word(tmp_path):
    ruta = fuentes.word_dos_paginas(tmp_path / "silabo.docx")
    conversion = correr(convertir.extraer_word(ruta, None, tmp_path / "_pdf"))
    assert conversion.metodo == "Word convertido a PDF"
    pasajes = textos_y_ubicaciones(conversion)
    assert ("Primera página del sílabo.", "página 1") in pasajes
    assert ("Segunda página del sílabo.", "página 2") in pasajes
    assert any("Sesión 1" in t and u == "página 2" for t, u in pasajes)


def test_word_sin_office_usa_parrafos_y_avisa(tmp_path, monkeypatch):
    def falla(*_):
        raise convertir.office.ErrorDeOffice("Word no instalado")
    monkeypatch.setattr(convertir.office, "word_a_pdf", falla)
    ruta = fuentes.word_dos_paginas(tmp_path / "silabo.docx")
    conversion = correr(convertir.extraer_word(ruta, None, tmp_path / "_pdf"))
    assert ("Primera página del sílabo.", "párrafo 1") in textos_y_ubicaciones(conversion)
    assert ("Sesión 1 | Fundamentos", "tabla 1, fila 1") in textos_y_ubicaciones(conversion)
    assert "no páginas" in conversion.avisos[0]


def test_powerpoint_da_lamina_notas_tabla_e_imagen(tmp_path):
    lector = LectorSimulado(["Diagrama del Sprint"])
    conversion = correr(convertir.extraer_pptx(fuentes.powerpoint(tmp_path / "s.pptx"), lector))
    assert textos_y_ubicaciones(conversion) == [
        ("Valores de Scrum", "lámina 1"),
        ("Compromiso", "lámina 1"),
        ("Pregunta al grupo por un ejemplo.", "lámina 1 · notas"),
        ("Pilar | Definición", "lámina 2"),
        ("Inspección | Revisar el avance.", "lámina 2"),
        ("Diagrama del Sprint", "lámina 3 · leída por IA"),
    ]
    assert conversion.revisar is True


def test_excel_da_hoja_y_celda(tmp_path):
    conversion = correr(convertir.extraer_xlsx(fuentes.excel(tmp_path / "r.xlsx"), None))
    assert textos_y_ubicaciones(conversion) == [
        ("Fecha de referencia", "hoja Registro, celda A1"),
        ("05/10/2026", "hoja Registro, celda B1"),
        ("Pedidos listos", "hoja Registro, celda A2"),
        ("12", "hoja Registro, celda B2"),
        ("Almacén central", "hoja Datos, celda C3"),
    ]


def test_excel_avisa_formulas_sin_valor_guardado(tmp_path):
    conversion = correr(convertir.extraer_xlsx(fuentes.excel_con_formula_sin_valor(tmp_path / "f.xlsx"), None))
    assert "Sheet!A2" in conversion.avisos[0]


def test_imagen_la_lee_la_ia_y_queda_para_revisar(tmp_path):
    lector = LectorSimulado(["Línea uno", "Línea dos"])
    conversion = correr(convertir.extraer_imagen(fuentes.imagen(tmp_path / "foto.png"), lector))
    assert textos_y_ubicaciones(conversion) == [
        ("Línea uno", "línea 1 · leída por IA"),
        ("Línea dos", "línea 2 · leída por IA"),
    ]
    assert conversion.revisar is True


# ---------- Curso completo ----------

@pytest.fixture
def curso(tmp_path):
    carpeta = tmp_path / "curso"
    (carpeta / "fuentes").mkdir(parents=True)
    return carpeta


def test_convierte_cada_fuente_y_guarda_pasajes_e_indice(curso):
    fuentes.pdf_con_texto(curso / "fuentes" / "norma.pdf")
    fuentes.excel(curso / "fuentes" / "registro.xlsx")
    indice = correr(convertir.convertir_curso(curso, None))
    assert indice["norma.pdf"]["estado"] == convertir.CONVERTIDA
    assert indice["norma.pdf"]["pasajes"] == 2
    lineas = (curso / "fuentes_texto" / "norma.pdf.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lineas[1]) == {
        "n": 2, "texto": "Scrum es gratuito.", "ubicacion": "página 2 · número impreso 43",
        "origen": "texto", "pagina": 2, "numero_impreso": 43,
    }
    assert convertir.leer_pasajes(curso, "registro.xlsx")[0]["ubicacion"] == "hoja Registro, celda A1"


def test_segunda_conversion_no_repite_el_trabajo(curso):
    fuentes.imagen(curso / "fuentes" / "foto.png")
    lector = LectorSimulado()
    primera = correr(convertir.convertir_curso(curso, lector))
    segunda = correr(convertir.convertir_curso(curso, lector))
    assert len(lector.llamadas) == 1
    assert segunda == primera


def test_fuente_cambiada_se_convierte_de_nuevo(curso):
    ruta = fuentes.imagen(curso / "fuentes" / "foto.png", "Primera versión")
    lector = LectorSimulado()
    correr(convertir.convertir_curso(curso, lector))
    fuentes.imagen(ruta, "Segunda versión")
    correr(convertir.convertir_curso(curso, lector))
    assert len(lector.llamadas) == 2


def test_fuente_borrada_sale_del_indice(curso):
    ruta = fuentes.pdf_con_texto(curso / "fuentes" / "norma.pdf")
    correr(convertir.convertir_curso(curso, None))
    ruta.unlink()
    indice = correr(convertir.convertir_curso(curso, None))
    assert indice == {}
    assert not (curso / "fuentes_texto" / "norma.pdf.jsonl").exists()


def test_fuente_ilegible_queda_marcada_y_sin_pasajes(curso):
    (curso / "fuentes" / "roto.pdf").write_bytes(b"esto no es un PDF")
    indice = correr(convertir.convertir_curso(curso, None))
    assert indice["roto.pdf"]["estado"] == convertir.NO_SE_PUEDE_LEER
    assert indice["roto.pdf"]["motivo"]
    assert convertir.leer_pasajes(curso, "roto.pdf") == []


def test_fuente_ilegible_se_reintenta_en_la_siguiente_conversion(curso):
    ruta = curso / "fuentes" / "roto.pdf"
    ruta.write_bytes(b"esto no es un PDF")
    correr(convertir.convertir_curso(curso, None))
    fuentes.pdf_con_texto(ruta)
    indice = correr(convertir.convertir_curso(curso, None))
    assert indice["roto.pdf"]["estado"] == convertir.CONVERTIDA


def test_error_de_la_ia_en_una_imagen_marca_la_fuente_ilegible(curso):
    fuentes.imagen(curso / "fuentes" / "foto.png")

    async def lector_que_falla(*_):
        raise RuntimeError("sin conexión")

    indice = correr(convertir.convertir_curso(curso, lector_que_falla))
    assert indice["foto.png"]["estado"] == convertir.NO_SE_PUEDE_LEER
    assert "sin conexión" in indice["foto.png"]["motivo"]


def test_el_profesor_marca_la_fuente_como_revisada(curso):
    fuentes.imagen(curso / "fuentes" / "foto.png")
    correr(convertir.convertir_curso(curso, LectorSimulado()))
    assert convertir.leer_indice(curso)["foto.png"]["revisada"] is False
    convertir.marcar_revisada(curso, "foto.png")
    assert convertir.leer_indice(curso)["foto.png"]["revisada"] is True


def test_temporales_de_office_se_ignoran(curso):
    (curso / "fuentes" / "~$silabo.docx").write_bytes(b"temporal")
    assert correr(convertir.convertir_curso(curso, None)) == {}
