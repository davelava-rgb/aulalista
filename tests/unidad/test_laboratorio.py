"""Etapa 7a: guía del laboratorio, archivos de práctica reales, figuras sacadas de ellos y el .zip."""

import asyncio
import zipfile
from urllib.parse import unquote

import openpyxl
import pytest
from docx import Document
from fastapi.testclient import TestClient
from PIL import Image

from app import servidor
from app.materiales import figuras, laboratorio, practica
from app.materiales.contenido import Laboratorio
from tests.conftest import consulta_en_secuencia
from tests.sembrados import laboratorio as sembrados
from tests.unidad.test_lectura import SIN_ERRORES, sesion, una_pagina  # noqa: F401

cliente = TestClient(servidor.app)
LLAMADAS_A_EXCEL = []


def recalcular_sin_excel(ruta):
    """En las pruebas no se abre Excel: se escribe el valor de la fórmula del laboratorio limpio."""
    LLAMADAS_A_EXCEL.append(ruta.name)
    libro = openpyxl.load_workbook(ruta)
    for hoja in libro.worksheets:
        for fila in hoja.iter_rows():
            for celda in fila:
                if isinstance(celda.value, str) and celda.value.startswith("=SUM"):
                    celda.value = 10
    libro.save(ruta)
    return ruta


def generar(carpeta, *salidas):
    consulta = consulta_en_secuencia(*salidas, SIN_ERRORES)
    material = asyncio.run(laboratorio.generar(carpeta, "scrum", 1, consulta=consulta, recalcular=recalcular_sin_excel,
                                               contar_paginas=una_pagina))
    return material, consulta


# ---------- Generación completa ----------

def test_genera_la_guia_los_archivos_las_figuras_y_el_zip(sesion):  # noqa: F811
    material, consulta = generar(sesion, sembrados.limpio())
    assert material["estado"] == "verificada", material.get("problemas")
    rutas = laboratorio.archivos(sesion, 1)
    nombres = ["S1_E1_pedidos-semana.xlsx", "S1_E2_aviso-almacen.docx", "S1_E3_capacitacion.xlsx"]
    assert sorted(p.name for p in rutas["practica"].iterdir()) == nombres
    assert sorted(zipfile.ZipFile(rutas["zip"]).namelist()) == nombres
    assert "S1_E3_capacitacion.xlsx" in LLAMADAS_A_EXCEL            # tiene una fórmula: Excel la calcula
    guia = Document(rutas["word"])
    textos = [p.text for p in guia.paragraphs]
    assert laboratorio.AVISO_ADJUNTOS in textos                       # la ficha no dice que acepta adjuntos
    tabla = guia.tables[0]
    assert [c.text for c in tabla.rows[0].cells] == ["Archivo", "Ejercicio", "Contenido"]
    assert [tabla.cell(i, 0).text for i in range(1, 4)] == nombres
    titulos = [p.text for p in guia.paragraphs if p.style.name.startswith("Heading")]
    assert titulos[:3] == ["Antes de empezar", "Archivos de práctica", "Ejercicio 1 · Clasifica los pedidos de la semana"]
    assert titulos.count("Mejora el resultado (opcional)") == 3
    assert "Cada ejercicio funciona solo. Puedes hacerlos en cualquier orden." in textos
    assert "Los 3 archivos están en el archivo comprimido S1_Laboratorio_Archivos.zip." in textos
    assert "Área: Ventas" in textos and "Situación" in textos
    assert "S1_E1_pedidos-semana.xlsx. Tiene una hoja: Pedidos." in textos
    assert "2.	Revisa la columna Entrega de la hoja Pedidos. Mira la figura 1." in textos
    assert "Figura 1. La columna Entrega de la hoja Pedidos." in textos
    assert "Figura 2. La oración del aviso que habla del Sprint." in textos
    # Ejercicio 3: fórmulas en español en la guía, recuadro «Antes de copiar una fórmula» con su tabla.
    tablas = [[c.text for c in fila.cells] for tabla in guia.tables for fila in tabla.rows]
    assert ["Función en español", "Función en inglés"] in tablas and ["SI", "IF"] in tablas and ["PROMEDIO", "AVERAGE"] in tablas
    celdas = " ".join(c.text for tabla in guia.tables for fila in tabla.rows for c in fila.cells)
    assert '=SI(B2<5,"REVISAR","OK")' in celdas and "Fórmula 2 · Promedio de horas" in celdas
    pie = guia.sections[0].footer.paragraphs[0].text
    assert pie.startswith("Sesión 1 · Laboratorio · Página")
    assert len(guia.inline_shapes) == 2
    redaccion = consulta.llamadas[0]["prompt"]
    assert "## Material 3 · Laboratorio y archivos de práctica" in redaccion
    assert "Mira la figura N" in redaccion and laboratorio.AVISO_ADJUNTOS in redaccion
    entrega = {s["clave"]: s["lineas"] for s in material["entrega"]["secciones"]}
    assert entrega["archivos"][1].startswith("S1_Laboratorio_Archivos.zip: los 3 archivos de práctica")
    assert any("etapa 7b" in l for l in entrega["no_pude"])
    assert any("Problema sembrado en S1_E1_pedidos-semana.xlsx" in l for l in entrega["decidi"])


def test_los_archivos_de_practica_son_reales_y_sobrios(sesion):  # noqa: F811
    generar(sesion, sembrados.limpio())
    carpeta = laboratorio.archivos(sesion, 1)["practica"]
    libro = openpyxl.load_workbook(carpeta / "S1_E1_pedidos-semana.xlsx")
    hoja = libro["Pedidos"]
    assert [c.value for c in hoja[1]] == ["Pedido", "Cliente", "Entrega"] and hoja["C4"].value == "Envío"
    assert hoja["A1"].font.bold and hoja.freeze_panes == "A2"
    horas = openpyxl.load_workbook(carpeta / "S1_E3_capacitacion.xlsx")["Horas"]
    assert horas["B2"].value == 4                                     # un número queda como número
    aviso = Document(carpeta / "S1_E2_aviso-almacen.docx")
    assert [p.text for p in aviso.paragraphs][:2] == ["Aviso al equipo", "El Sprint dura dos semanas."]


def test_las_figuras_salen_del_archivo_real_con_marcas_ambar(sesion):  # noqa: F811
    generar(sesion, sembrados.limpio())
    rutas = laboratorio.archivos(sesion, 1)
    imagen = Image.open(rutas["figuras"] / "E1_paso2.png").convert("RGB")
    colores = {c for _, c in imagen.getcolors(maxcolors=1 << 20)}
    assert figuras.AMBAR in colores
    contenido = Laboratorio.model_validate(sembrados.limpio())
    figura = contenido.ejercicios[0].pasos[1].figura
    otra = figuras.hacer(rutas["practica"] / figura.archivo, figura, rutas["figuras"] / "prueba.png")
    assert otra.letra_pt >= figuras.LETRA_MINIMA_PT and otra.ancho_cm <= figuras.ANCHO_MAXIMO_CM
    word = Image.open(rutas["figuras"] / "E2_paso2.png").convert("RGB")
    assert figuras.AMBAR in {c for _, c in word.getcolors(maxcolors=1 << 20)}


def test_una_formula_en_espanol_se_guarda_en_ingles_dentro_del_archivo(tmp_path):
    from app.materiales import estilo
    from app.materiales.contenido import ArchivoPractica
    archivo = ArchivoPractica.model_validate({
        "nombre": "S1_E1_horas.xlsx", "descripcion": "Horas.", "parrafos": [], "tabla": None, "problema": "",
        "hojas": [{"nombre": "Horas", "encabezados": ["Persona", "Horas", "Revisión"],
                   "filas": [["Analista 1", 4, '=SI(Y(B2<5;B2>0);"REVISAR";"OK")'], ["Total", "=SUMA(B2:B2)", None]]}]})
    identidad = estilo.Identidad(**estilo.PALETA_SOBRIA, tipografia="Calibri", logo=None)
    hoja = openpyxl.load_workbook(practica.crear_excel(archivo, identidad, tmp_path / archivo.nombre))["Horas"]
    assert hoja["C2"].value == '=IF(AND(B2<5,B2>0),"REVISAR","OK")'
    assert hoja["B3"].value == "=SUM(B2:B2)"
    assert practica.funciones_usadas(['=SI(Y(A1>2,B1),1,0)', "=PROMEDIO(B2:B3)"]) == [
        ("SI", "IF"), ("Y", "AND"), ("PROMEDIO", "AVERAGE")]


# ---------- Errores sembrados: los detecta un programa antes de crear los archivos ----------

@pytest.mark.parametrize("nombre", list(sembrados.SEMBRADOS))
def test_cada_error_sembrado_se_detecta(sesion, nombre):  # noqa: F811
    cambio, esperado = sembrados.SEMBRADOS[nombre]
    contenido, problemas = laboratorio._validar(sembrados.con(cambio), sesion, 1)
    assert contenido is None
    assert any(esperado in p for p in problemas), problemas


def test_el_laboratorio_limpio_no_tiene_problemas(sesion):  # noqa: F811
    contenido, problemas = laboratorio._validar(sembrados.limpio(), sesion, 1)
    assert problemas == [] and contenido is not None


def test_la_respuesta_a_la_pregunta_de_la_herramienta_va_en_el_ejercicio():
    contenido = Laboratorio.model_validate(sembrados.limpio())
    problemas = practica.revisar(contenido, 1, 3, respuestas_a_la_herramienta={2: "Sí, usa el aviso de ayer"})
    assert any("ejercicio 2: la ficha dice que la herramienta pregunta algo" in p for p in problemas)


def test_un_error_de_estructura_se_corrige_con_el_laboratorio_completo(sesion):  # noqa: F811
    roto = sembrados.con(sembrados.SEMBRADOS["espacio por llenar"][0])
    corregido = {"laboratorio": sembrados.limpio(), "explicaciones": [], "datos_nuevos": []}
    material, consulta = generar(sesion, roto, corregido)
    assert material["estado"] == "verificada"
    assert "«[nombre del cliente]» en lo que el alumno copia" in consulta.llamadas[1]["prompt"]
    assert consulta.llamadas[1]["options"].output_format["schema"] == laboratorio.ESQUEMA_CORRECCION


# ---------- Página ----------

def test_la_pagina_de_la_sesion_genera_y_aprueba_el_laboratorio(sesion, monkeypatch):  # noqa: F811
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    assert "3. Laboratorio y archivos de práctica" in pagina and "Generar laboratorio" in pagina
    generar(sesion, sembrados.limpio())
    pagina = cliente.get("/cursos/scrum/sesiones/1").text
    assert "S1_Laboratorio.docx" in pagina and "S1_Laboratorio_Archivos.zip" in pagina
    r = cliente.get("/cursos/scrum/sesiones/1/descargar/S1_Laboratorio_Archivos.zip")
    assert r.status_code == 200 and r.content[:2] == b"PK"
    r = cliente.post("/cursos/scrum/sesiones/1/materiales/laboratorio/aprobar", follow_redirects=False)
    assert "Laboratorio aprobado." in unquote(r.headers["location"])
    assert laboratorio.estado(sesion, 1)["estado"] == "aprobada"
