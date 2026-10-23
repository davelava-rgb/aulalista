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


# ---------- Decisión 68 a: costo por modelo, razonamiento, copia del registro y resumen ----------

def _resultado_con_dos_modelos():
    return resultado_simulado(
        total_cost_usd=1.0,
        usage={"input_tokens": 10, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 2000,
               "output_tokens": 500, "output_tokens_details": {"thinking_tokens": 200}},
        model_usage={
            "claude-opus-5-5": {"inputTokens": 5, "outputTokens": 480, "cacheReadInputTokens": 1000,
                                "cacheCreationInputTokens": 2000, "costUSD": 0.95},
            "claude-haiku-5-5": {"inputTokens": 5, "outputTokens": 20, "cacheReadInputTokens": 0,
                                 "cacheCreationInputTokens": 0, "costUSD": 0.05},
        },
    )


def test_guarda_el_costo_de_cada_modelo_y_el_razonamiento(entorno):
    fila = tokens.registrar(_resultado_con_dos_modelos(), curso="c", sesion="S1", material="lectura", etapa="redacción")
    assert fila["razonamiento"] == 200
    assert fila["por_modelo"]["claude-opus-5-5"] == {"entrada": 5, "cache_creada": 2000, "cache_leida": 1000,
                                                     "salida": 480, "costo_usd": 0.95}
    assert fila["por_modelo"]["claude-haiku-5-5"]["costo_usd"] == 0.05
    guardada = json.loads((entorno["cursos"] / "c" / "tokens.jsonl").read_text(encoding="utf-8"))
    assert guardada["por_modelo"]["claude-opus-5-5"]["salida"] == 480


def test_copia_el_registro_de_una_prueba_al_sistema(entorno, tmp_path):
    tokens.registrar(resultado_simulado(), curso="scrum", sesion="S1", material="prueba", etapa="revisión",
                     carpeta_cursos=tmp_path / "temporal")
    destino = entorno["cursos"] / "_sistema" / "tokens.jsonl"
    copiadas = tokens.copiar_registro(tmp_path / "temporal" / "scrum" / "tokens.jsonl", destino,
                                      curso="_sistema", etapa_prefijo="prueba ia · test_x · ")
    assert copiadas == 1
    fila = json.loads(destino.read_text(encoding="utf-8"))
    assert fila["curso"] == "_sistema"
    assert fila["etapa"] == "prueba ia · test_x · revisión"
    assert tokens.copiar_registro(tmp_path / "no-existe.jsonl", destino, curso="_sistema", etapa_prefijo="") == 0


def test_resumen_reparte_el_gasto(entorno):
    tokens.registrar(_resultado_con_dos_modelos(), curso="c", sesion="S1", material="lectura", etapa="redacción")
    tokens.registrar(_resultado_con_dos_modelos(), curso="c", sesion="S1", material="lectura", etapa="corrección completa 1")
    tokens.registrar(_resultado_con_dos_modelos(), curso="c", sesion="S1", material="diapositivas", etapa="corrección completa 2")
    datos = tokens.resumen(tokens.leer(entorno["cursos"]))
    assert datos["llamadas"] == 3
    assert datos["costo_usd"] == 3.0
    assert datos["razonamiento"] == 600
    # Las vueltas numeradas se juntan en una sola etapa.
    assert datos["por_etapa"]["corrección completa"] == {"llamadas": 2, "costo_usd": 2.0}
    assert datos["por_material"]["lectura"]["costo_usd"] == 2.0
    assert datos["por_modelo"]["claude-opus-5-5"] == {"llamadas": 3, "costo_usd": 2.85}
    assert datos["por_modelo"]["claude-haiku-5-5"]["costo_usd"] == 0.15
    # Los componentes suman el costo total y el razonamiento pesa lo suyo.
    componentes = datos["por_componente"]
    assert round(sum(g["costo_usd"] for g in componentes.values()), 2) == 3.0
    assert componentes["salida (razonamiento)"]["costo_usd"] > 0
    assert list(componentes) == sorted(componentes, key=lambda c: -componentes[c]["costo_usd"])
    texto = tokens.texto_del_resumen(datos, "c")
    assert "3.00 USD en 3 llamadas" in texto and "corrección completa" in texto


def test_resumen_sin_registros(entorno):
    datos = tokens.resumen(tokens.leer(entorno["cursos"]))
    assert datos == {"llamadas": 0, "costo_usd": 0.0, "razonamiento": 0, "tokens_salida": 0, "por_etapa": {},
                     "por_material": {}, "por_curso": {}, "por_modelo": {}, "por_componente": {}}


def test_filas_viejas_sin_por_modelo_ni_razonamiento(entorno):
    """Los registros anteriores a la decisión 68 no tienen esos campos: el resumen los lee igual."""
    ruta = entorno["cursos"] / "viejo" / "tokens.jsonl"
    ruta.parent.mkdir(parents=True)
    ruta.write_text(json.dumps({"fecha": "2026-10-10T00:00:00", "curso": "viejo", "sesion": "S1", "material": "lectura",
                                "etapa": "redacción", "modelos": ["claude-opus-5-5"], "tokens_entrada": 100,
                                "tokens_salida": 50, "costo_usd": 0.5,
                                "uso": {"input_tokens": 100, "output_tokens": 50,
                                        "output_tokens_details": {"thinking_tokens": 10}}}) + "\n", encoding="utf-8")
    datos = tokens.resumen(tokens.leer(entorno["cursos"]))
    assert datos["razonamiento"] == 10
    assert datos["por_modelo"] == {"claude-opus-5-5": {"llamadas": 1, "costo_usd": 0.5}}
