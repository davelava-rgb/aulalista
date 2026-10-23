"""Las pruebas con IA escriben su registro de tokens en una carpeta temporal que pytest borra. Este arreglo copia
ese gasto a cursos/_sistema/tokens.jsonl, con la etapa precedida de «prueba ia · nombre de la prueba», para que
el gasto de las pruebas también se vea (PLAN.md §0, decisión 68 a)."""

import pytest

from app import config, tokens

CARPETA_REAL = config.CARPETA_CURSOS   # se toma antes de que una prueba la reemplace por una temporal


@pytest.fixture(autouse=True)
def registrar_gasto_de_la_prueba(request, tmp_path):
    yield
    destino = CARPETA_REAL / tokens.CURSO_SISTEMA / "tokens.jsonl"
    for origen in sorted(tmp_path.rglob("tokens.jsonl")):
        if origen.resolve() == destino.resolve():
            continue
        tokens.copiar_registro(origen, destino, curso=tokens.CURSO_SISTEMA,
                               etapa_prefijo=f"prueba ia · {request.node.name} · ")
