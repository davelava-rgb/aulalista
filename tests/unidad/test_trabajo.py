"""Decisión 42: en materiales/ quedan solo los archivos del profesor; lo que usa AulaLista va en _trabajo/."""

from pathlib import Path

from app.materiales import comun, diapositivas, laboratorio, lectura


def test_las_rutas_de_trabajo_de_los_tres_materiales_estan_en_trabajo(tmp_path):
    for modulo, del_profesor in ((lectura, {"word", "excel"}), (diapositivas, {"pptx", "excel"}),
                                 (laboratorio, {"word", "zip", "excel", "registro"})):
        rutas = modulo.archivos(tmp_path, 1)
        assert "entrega" not in rutas
        for clave, ruta in rutas.items():
            assert (comun.TRABAJO in ruta.parts) == (clave not in del_profesor), (modulo.__name__, clave)
    assert laboratorio.CARPETA_PRACTICA == "materiales/_trabajo/laboratorio/practica"


def test_una_carpeta_de_la_forma_anterior_se_ordena(tmp_path):
    carpeta = tmp_path / "scrum" / "sesiones" / "S1" / "materiales"
    (carpeta / "diapositivas" / "diseno").mkdir(parents=True)
    (carpeta / "diapositivas" / "contenido.json").write_text("{}", encoding="utf-8")
    (carpeta / "diapositivas" / "diseno" / "aprobado.js").write_text("x", encoding="utf-8")
    (carpeta / "practica").mkdir()
    (carpeta / "practica" / "S1_E1.xlsx").write_bytes(b"")
    for nombre in ("S1_Diapositivas.pptx", "S1_Diapositivas_Verificacion.xlsx", "S1_Diapositivas_Verificacion.json",
                   "S1_Diapositivas_Entrega.md", "S1_Lectura_Entrega.md"):
        (carpeta / nombre).write_text("x", encoding="utf-8")

    comun.ordenar_cursos(tmp_path)

    assert sorted(p.name for p in carpeta.iterdir()) == ["S1_Diapositivas.pptx", "S1_Diapositivas_Verificacion.xlsx",
                                                         comun.TRABAJO]
    rutas = diapositivas.archivos(tmp_path / "scrum", 1)
    assert rutas["contenido"].exists() and rutas["verificacion_json"].exists()
    assert (rutas["contenido"].parent / "diseno" / "aprobado.js").exists()
    assert (laboratorio.archivos(tmp_path / "scrum", 1)["practica"] / "S1_E1.xlsx").exists()
    comun.ordenar_cursos(tmp_path)                  # una segunda vez no cambia nada
    assert rutas["contenido"].exists()


def test_los_pedidos_de_correccion_no_repiten_lo_que_va_en_el_mensaje_de_sistema():
    """Decisión 43: contexto, formato y reglas van en el archivo de sistema, que el SDK guarda en caché."""
    datos, problemas = {"titulo": "x"}, ["FALLA · algo"]
    pedidos = [lectura.pedido_de_cambios(datos, problemas), lectura.pedido_de_correccion(datos, problemas),
               laboratorio.pedido_de_cambios(datos, problemas), laboratorio.pedido_de_correccion(datos, problemas),
               laboratorio.pedido_de_correccion_por_ejercicios(datos, problemas, {2}),
               diapositivas.pedido_de_cambios(datos, problemas), diapositivas.pedido_de_correccion(datos, problemas)]
    for pedido in pedidos:
        assert pedido.startswith("Corrige el material según el contexto, el formato y las reglas de tus instrucciones.")
        assert comun.REGLAS_DE_CORRECCION not in pedido and "- FALLA · algo" in pedido
    for modulo in (lectura, diapositivas, laboratorio):
        assert modulo.archivos(Path("c"), 1)["sistema"].name == "sistema_correccion.txt"
