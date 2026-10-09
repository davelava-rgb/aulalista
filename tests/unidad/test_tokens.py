import json

from app import tokens
from tests.conftest import resultado_simulado


def test_registra_una_linea_por_llamada(entorno):
    tokens.registrar(resultado_simulado(), curso="curso-a", sesion="S1", material="lectura", etapa="redaccion")
    tokens.registrar(resultado_simulado(), curso="curso-a", sesion="S1", material="lectura", etapa="pasada1")

    lineas = (entorno["cursos"] / "curso-a" / "tokens.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lineas) == 2
    fila = json.loads(lineas[0])
    assert fila["curso"] == "curso-a"
    assert fila["sesion"] == "S1"
    assert fila["material"] == "lectura"
    assert fila["etapa"] == "redaccion"
    assert fila["modelos"] == ["claude-haiku-4-5-20251001"]
    assert fila["tokens_entrada"] == 115  # entrada + caché leída + caché creada
    assert fila["tokens_salida"] == 7
    assert fila["costo_usd"] == 0.0012
    assert fila["error"] is False


def test_suma_el_gasto_del_curso(entorno):
    for _ in range(3):
        tokens.registrar(resultado_simulado(), curso="curso-b", sesion="S1", material="-", etapa="x")
    suma = tokens.total("curso-b")
    assert suma == {"llamadas": 3, "tokens_entrada": 345, "tokens_salida": 21, "costo_usd": 0.0036}


def test_curso_sin_registro_suma_cero(entorno):
    assert tokens.total("sin-registro")["llamadas"] == 0


def test_resultado_sin_uso_no_rompe_el_registro(entorno):
    fila = tokens.registrar(
        resultado_simulado(usage=None, total_cost_usd=None, model_usage=None),
        curso="c", sesion="-", material="-", etapa="x",
    )
    assert fila["tokens_entrada"] == 0
    assert fila["costo_usd"] == 0.0
