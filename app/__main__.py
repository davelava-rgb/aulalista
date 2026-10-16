"""Inicia AulaLista y abre la página en el navegador: python -m app"""

import json
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

DIRECCION = "127.0.0.1"
PUERTO = 8765

AVISO_PUERTO_OCUPADO = (
    "Otro programa usa el puerto {puerto} y no es AulaLista.\n"
    "Ciérralo y vuelve a iniciar."
)
AVISO_TRABAJANDO = (
    "Hay una AulaLista anterior abierta y está trabajando:\n{trabajos}\n"
    "No la cierro para no cortar ese trabajo ni perder lo gastado.\n"
    "Espera a que termine (la página lo dice) y vuelve a iniciar."
)


def puerto_libre(direccion: str = DIRECCION, puerto: int = PUERTO) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as prueba:
        try:
            prueba.bind((direccion, puerto))
        except OSError:
            return False
    return True


def proceso_en_puerto(puerto: int = PUERTO) -> tuple[int, str] | None:
    """El programa que escucha en el puerto: su número de proceso y su línea de comando. Lo pregunta a Windows."""
    orden = (f"$c = Get-NetTCPConnection -LocalPort {puerto} -State Listen -ErrorAction SilentlyContinue | "
             "Select-Object -First 1; if ($c) { $p = Get-CimInstance Win32_Process -Filter \"ProcessId=$($c.OwningProcess)\"; "
             "@{pid = $p.ProcessId; comando = $p.CommandLine} | ConvertTo-Json -Compress }")
    try:
        salida = subprocess.run(["powershell", "-NoProfile", "-Command", orden], capture_output=True, text=True,
                                timeout=30).stdout.strip()
        datos = json.loads(salida) if salida else None
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None
    return (int(datos["pid"]), datos.get("comando") or "") if datos else None


def es_aulalista(comando: str) -> bool:
    """La línea de comando es la de esta AulaLista: «python -m app» o el servidor uvicorn de app.servidor."""
    partes = comando.replace('"', " ").split()
    return ("-m" in partes and "app" in partes) or "app.servidor:app" in comando


VIGENCIA_MIN = 20


def _reciente(ruta: Path, ahora: float | None = None) -> bool:
    """Un trabajo escribe su estado al menos cada pocos minutos. Un «trabajando» sin cambios en VIGENCIA_MIN minutos
    quedó de una AulaLista que se cerró a mitad de camino: no impide cerrar la anterior."""
    return (ahora or time.time()) - ruta.stat().st_mtime < VIGENCIA_MIN * 60



def trabajos_en_curso(carpeta_cursos: Path, ahora: float | None = None) -> list[str]:
    """Lo que se está generando ahora: materiales en «trabajando» y fichas que se proponen solas."""
    trabajos = []
    for ruta in sorted(carpeta_cursos.glob("*/sesiones/*/estado.json")):
        if not _reciente(ruta, ahora):
            continue
        try:
            materiales = json.loads(ruta.read_text(encoding="utf-8")).get("materiales", {})
        except (OSError, json.JSONDecodeError):
            continue
        curso, sesion = ruta.parents[2].name, ruta.parent.name
        trabajos += [f"- {curso}, sesión {sesion.lstrip('S')}: {clave}" for clave, m in materiales.items()
                     if m.get("estado") == "trabajando"]
    for ruta in sorted(carpeta_cursos.glob("**/propuesta_*.json")):
        if not _reciente(ruta, ahora):
            continue
        try:
            trabajando = json.loads(ruta.read_text(encoding="utf-8")).get("estado") == "trabajando"
        except (OSError, json.JSONDecodeError):
            continue
        if trabajando:
            curso = ruta.relative_to(carpeta_cursos).parts[0]
            trabajos.append(f"- {curso}: la ficha se está proponiendo desde las fuentes")
    return trabajos


def cerrar_version_anterior(carpeta_cursos: Path, puerto: int = PUERTO) -> str | None:
    """Si la que ocupa el puerto es una AulaLista anterior y no está trabajando, la cierra. Devuelve el aviso que
    impide seguir, o None si el puerto quedó libre."""
    proceso = proceso_en_puerto(puerto)
    if proceso is None or not es_aulalista(proceso[1]):
        return AVISO_PUERTO_OCUPADO.format(puerto=puerto)
    trabajos = trabajos_en_curso(carpeta_cursos)
    if trabajos:
        return AVISO_TRABAJANDO.format(trabajos="\n".join(trabajos))
    print("Hay una AulaLista anterior abierta y no está trabajando. La cierro para abrir la versión de ahora.")
    subprocess.run(["taskkill", "/PID", str(proceso[0]), "/F"], capture_output=True)
    for _ in range(20):                                  # Windows tarda un poco en soltar el puerto
        if puerto_libre(DIRECCION, puerto):
            return None
        time.sleep(0.25)
    return AVISO_PUERTO_OCUPADO.format(puerto=puerto)


def main() -> None:
    url = f"http://{DIRECCION}:{PUERTO}/"
    from app import config
    # Sin esta prueba, el navegador abría la versión vieja que seguía corriendo.
    if not puerto_libre():
        aviso = cerrar_version_anterior(config.CARPETA_CURSOS)
        if aviso:
            print(aviso)
            sys.exit(1)
    from app.materiales import comun
    comun.ordenar_cursos(config.CARPETA_CURSOS)     # cursos generados antes de la decisión 42
    threading.Timer(1.5, webbrowser.open, args=[url]).start()
    print(f"AulaLista está en {url}. Para cerrarla, pulsa Ctrl+C.")
    uvicorn.run("app.servidor:app", host=DIRECCION, port=PUERTO)


if __name__ == "__main__":
    main()
