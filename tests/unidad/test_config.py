import pytest

from app import config


def test_lee_la_clave_del_archivo_env(entorno):
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-de-prueba\n", encoding="utf-8")
    assert config.leer_clave() == "sk-ant-de-prueba"


def test_ignora_la_variable_de_windows(entorno, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-de-windows")
    entorno["env"].write_text("ANTHROPIC_API_KEY=sk-ant-del-env\n", encoding="utf-8")
    assert config.leer_clave() == "sk-ant-del-env"


def test_sin_archivo_env_se_detiene_aunque_windows_tenga_clave(entorno, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-de-windows")
    with pytest.raises(config.FaltaClave, match=r"\.env"):
        config.leer_clave()


@pytest.mark.parametrize("contenido", ["", "ANTHROPIC_API_KEY=\n", "ANTHROPIC_API_KEY=   \n", "OTRA=1\n"])
def test_clave_vacia_se_detiene_con_mensaje(entorno, contenido):
    entorno["env"].write_text(contenido, encoding="utf-8")
    with pytest.raises(config.FaltaClave, match="No hay clave de API"):
        config.leer_clave()


def test_cada_tarea_tiene_modelo_y_tope():
    tarea = config.leer_tarea("conexion")
    assert tarea["modelo"].startswith("claude-")
    assert 0 < tarea["tope_usd"] <= 1


def test_tarea_desconocida_avisa():
    with pytest.raises(KeyError, match="no está"):
        config.leer_tarea("no-existe")


def test_env_no_se_sube_al_repositorio():
    lineas = (config.RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in lineas
