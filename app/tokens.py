"""Registro de los tokens que gasta cada llamada al SDK (SPEC §9).

Cada curso tiene su archivo cursos/[curso]/tokens.jsonl, con una línea por llamada.
El costo es la estimación que da el SDK, no la factura.

Desde la decisión 68 cada línea guarda también el costo por modelo y los tokens de razonamiento, y
`python -m app.tokens` imprime en qué se fue el gasto: por etapa, material, modelo y componente.
"""

import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import ResultMessage

from app import config

CURSO_SISTEMA = "_sistema"


def _tokens_de_entrada(uso: dict) -> int:
    return (
        uso.get("input_tokens", 0)
        + uso.get("cache_read_input_tokens", 0)
        + uso.get("cache_creation_input_tokens", 0)
    )


def _por_modelo(model_usage: dict | None) -> dict:
    """Lo que gastó cada modelo en la llamada. El SDK lo da con nombres en inglés; aquí van en español."""
    salida = {}
    for modelo, uso in (model_usage or {}).items():
        uso = uso or {}
        salida[modelo] = {
            "entrada": uso.get("inputTokens", 0),
            "cache_creada": uso.get("cacheCreationInputTokens", 0),
            "cache_leida": uso.get("cacheReadInputTokens", 0),
            "salida": uso.get("outputTokens", 0),
            "costo_usd": uso.get("costUSD", 0.0) or 0.0,
        }
    return salida


def registrar(
    resultado: ResultMessage,
    *,
    curso: str,
    sesion: str,
    material: str,
    etapa: str,
    carpeta_cursos: Path | None = None,
) -> dict:
    """Agrega una línea al registro del curso y la devuelve."""
    uso = resultado.usage or {}
    fila = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "curso": curso,
        "sesion": sesion,
        "material": material,
        "etapa": etapa,
        "modelos": sorted((resultado.model_usage or {}).keys()),
        "tokens_entrada": _tokens_de_entrada(uso),
        "tokens_salida": uso.get("output_tokens", 0),
        "razonamiento": (uso.get("output_tokens_details") or {}).get("thinking_tokens", 0),
        "costo_usd": resultado.total_cost_usd or 0.0,
        "por_modelo": _por_modelo(resultado.model_usage),
        "uso": uso,
        "duracion_ms": resultado.duration_ms,
        "turnos": resultado.num_turns,
        "error": resultado.is_error,
    }
    ruta = (carpeta_cursos or config.CARPETA_CURSOS) / curso / "tokens.jsonl"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a", encoding="utf-8") as archivo:
        archivo.write(json.dumps(fila, ensure_ascii=False) + "\n")
    return fila


def copiar_registro(origen: Path, destino: Path, *, curso: str, etapa_prefijo: str) -> int:
    """Copia las líneas de un registro a otro, con el curso cambiado y la etapa precedida de `etapa_prefijo`.
    Lo usan las pruebas con IA: escriben en una carpeta temporal que se borra, y así su gasto queda en
    cursos/_sistema/ (decisión 68 a). Devuelve cuántas líneas copió."""
    if not origen.exists():
        return 0
    filas = [json.loads(l) for l in origen.read_text(encoding="utf-8").splitlines() if l.strip()]
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "a", encoding="utf-8") as archivo:
        for fila in filas:
            fila["curso"] = curso
            fila["etapa"] = f"{etapa_prefijo}{fila.get('etapa', '')}"
            archivo.write(json.dumps(fila, ensure_ascii=False) + "\n")
    return len(filas)


def lineas(curso: str, carpeta_cursos: Path | None = None) -> int:
    """Cuántas llamadas tiene ya el registro. Marca el inicio de un trabajo para sumar solo lo que gastó."""
    ruta = (carpeta_cursos or config.CARPETA_CURSOS) / curso / "tokens.jsonl"
    if not ruta.exists():
        return 0
    return sum(1 for linea in ruta.read_text(encoding="utf-8").splitlines() if linea.strip())


def total(curso: str, carpeta_cursos: Path | None = None, *, sesion: str | None = None,
          material: str | None = None, desde_linea: int = 0) -> dict:
    """Suma los tokens y el costo estimado de un curso. Con los filtros, solo de una sesión,
    de un material o de las llamadas que siguen a `desde_linea` (por ejemplo, las de una generación)."""
    suma = {"llamadas": 0, "tokens_entrada": 0, "tokens_salida": 0, "costo_usd": 0.0}
    ruta = (carpeta_cursos or config.CARPETA_CURSOS) / curso / "tokens.jsonl"
    if not ruta.exists():
        return suma
    filas = [linea for linea in ruta.read_text(encoding="utf-8").splitlines() if linea.strip()]
    for linea in filas[desde_linea:]:
        fila = json.loads(linea)
        if (sesion is not None and fila["sesion"] != sesion) or (material is not None and fila["material"] != material):
            continue
        suma["llamadas"] += 1
        suma["tokens_entrada"] += fila["tokens_entrada"]
        suma["tokens_salida"] += fila["tokens_salida"]
        suma["costo_usd"] += fila["costo_usd"]
    suma["costo_usd"] = round(suma["costo_usd"], 6)
    return suma


def ultima_corrida(curso: str, etapa: str, carpeta_cursos: Path | None = None, *, sesion: str | None = None) -> dict | None:
    """Lo que gastó la última vez una acción: las llamadas seguidas, al final del registro, cuya etapa empieza
    con `etapa`. Sirve para decir el costo junto al botón antes de pulsarlo. None si nunca se hizo."""
    ruta = (carpeta_cursos or config.CARPETA_CURSOS) / curso / "tokens.jsonl"
    if not ruta.exists():
        return None
    filas = [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]
    coincide = [str(f.get("etapa", "")).startswith(etapa) and (sesion is None or f.get("sesion") == sesion)
                for f in filas]
    if True not in coincide:
        return None
    fin = len(coincide) - 1 - coincide[::-1].index(True)
    inicio = fin
    while inicio > 0 and coincide[inicio - 1]:
        inicio -= 1
    grupo = filas[inicio:fin + 1]
    return {"llamadas": len(grupo), "costo_usd": round(sum(f["costo_usd"] for f in grupo), 6),
            "fecha": grupo[-1]["fecha"]}


# ---------- Resumen del gasto (decisión 68 a) ----------

# Precios por millón de tokens, solo para repartir el costo de una llamada entre sus componentes. El costo total
# de cada llamada es el que dio el SDK; estos precios solo deciden qué parte va a cada componente.
PESO_RELATIVO = {"entrada": 1.0, "cache_creada": 1.25, "cache_leida": 0.1, "salida": 5.0}
COMPONENTES = ("entrada nueva", "caché creada", "caché leída", "salida (texto)", "salida (razonamiento)")


def _etapa_general(etapa: str) -> str:
    """«corrección completa 2» → «corrección completa»; «ejecución ejercicio 4» → «ejecución ejercicio»."""
    etapa = re.sub(r"\s+\d+$", "", etapa.strip())
    return re.sub(r"\s+\d+\s+·", " ·", etapa)


def _componentes(fila: dict) -> dict[str, float]:
    """Reparte el costo de una llamada entre sus componentes, en proporción a los tokens y a su peso relativo."""
    uso = fila.get("uso") or {}
    razonamiento = fila.get("razonamiento") or (uso.get("output_tokens_details") or {}).get("thinking_tokens", 0)
    salida = fila.get("tokens_salida", 0)
    partes = {
        "entrada nueva": uso.get("input_tokens", 0) * PESO_RELATIVO["entrada"],
        "caché creada": uso.get("cache_creation_input_tokens", 0) * PESO_RELATIVO["cache_creada"],
        "caché leída": uso.get("cache_read_input_tokens", 0) * PESO_RELATIVO["cache_leida"],
        "salida (texto)": max(salida - razonamiento, 0) * PESO_RELATIVO["salida"],
        "salida (razonamiento)": razonamiento * PESO_RELATIVO["salida"],
    }
    peso_total = sum(partes.values())
    costo = fila.get("costo_usd", 0.0)
    if peso_total <= 0:
        return {c: 0.0 for c in COMPONENTES}
    return {c: costo * p / peso_total for c, p in partes.items()}


def leer(carpeta_cursos: Path | None = None, curso: str | None = None) -> list[dict]:
    """Todas las filas de los registros, de un curso o de todos."""
    carpeta = carpeta_cursos or config.CARPETA_CURSOS
    rutas = [carpeta / curso / "tokens.jsonl"] if curso else sorted(carpeta.glob("*/tokens.jsonl"))
    filas = []
    for ruta in rutas:
        if ruta.exists():
            filas += [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]
    return filas


def resumen(filas: list[dict]) -> dict:
    """El gasto repartido por etapa, material, modelo y componente. Cada apartado es un diccionario
    nombre → {llamadas, costo_usd}, ordenado de mayor a menor costo."""
    def agrupar(clave):
        grupos = defaultdict(lambda: {"llamadas": 0, "costo_usd": 0.0})
        for fila in filas:
            for nombre, costo in clave(fila):
                grupos[nombre]["llamadas"] += 1
                grupos[nombre]["costo_usd"] += fila["costo_usd"] if costo is None else costo
        return {n: {"llamadas": g["llamadas"], "costo_usd": round(g["costo_usd"], 4)}
                for n, g in sorted(grupos.items(), key=lambda kv: -kv[1]["costo_usd"])}

    def por_modelo(fila):
        detalle = fila.get("por_modelo") or {}
        if detalle:
            return [(m, d.get("costo_usd", 0.0)) for m, d in detalle.items()]
        return [(", ".join(fila.get("modelos") or ["?"]), None)]

    return {
        "llamadas": len(filas),
        "costo_usd": round(sum(f["costo_usd"] for f in filas), 4),
        "razonamiento": sum(f.get("razonamiento") or (f.get("uso") or {}).get("output_tokens_details", {}).get("thinking_tokens", 0)
                            for f in filas),
        "tokens_salida": sum(f.get("tokens_salida", 0) for f in filas),
        "por_etapa": agrupar(lambda f: [(_etapa_general(f["etapa"]), None)]),
        "por_material": agrupar(lambda f: [(f["material"], None)]),
        "por_curso": agrupar(lambda f: [(f["curso"], None)]),
        "por_modelo": agrupar(por_modelo),
        "por_componente": agrupar(lambda f: list(_componentes(f).items())),
    }


def texto_del_resumen(datos: dict, titulo: str = "todos los cursos") -> str:
    lineas_ = [f"Gasto registrado ({titulo}): {datos['costo_usd']:.2f} USD en {datos['llamadas']} llamadas.",
               f"Tokens de salida: {datos['tokens_salida']}, de los cuales {datos['razonamiento']} de razonamiento."]
    for apartado, nombre in (("por_componente", "Por componente"), ("por_etapa", "Por etapa"),
                             ("por_material", "Por material"), ("por_modelo", "Por modelo"), ("por_curso", "Por curso")):
        lineas_.append("")
        lineas_.append(f"{nombre}:")
        total_ = datos["costo_usd"] or 1
        for clave, g in datos[apartado].items():
            llamadas_ = f" · {g['llamadas']} llamadas" if g["llamadas"] and apartado != "por_componente" else ""
            lineas_.append(f"  {clave[:40]:40} {g['costo_usd']:8.2f} USD  {100 * g['costo_usd'] / total_:4.0f} %{llamadas_}")
    return "\n".join(lineas_)


def main(argumentos: list[str] | None = None) -> None:
    """python -m app.tokens [curso]: imprime el resumen del gasto de un curso o de todos."""
    argumentos = sys.argv[1:] if argumentos is None else argumentos
    curso = argumentos[0] if argumentos else None
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")   # la consola de Windows no siempre muestra las tildes
    print(texto_del_resumen(resumen(leer(curso=curso)), curso or "todos los cursos"))


if __name__ == "__main__":
    main()
