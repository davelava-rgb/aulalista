"""Modelos aprobados en PDF: apariencia y tono (PLAN.md §0, decisión 27).

Un programa, sin IA, saca de cada PDF los colores, la tipografía y un pasaje corto de prosa.
- Los colores y la tipografía solo llenan lo que la ficha del curso deja vacío: la ficha manda.
- El pasaje va al redactor solo como guía de tono. Las secciones siguen las de la skill.
Cada modelo se analiza una sola vez: el resultado queda en modelos/analisis.json con su huella.
"""

import json
import re
from collections import Counter
from pathlib import Path

import pymupdf

from app.fichas import almacen
from app.fuentes import convertir

CARPETA = "modelos"
ANALISIS = "analisis.json"
PALABRAS_DE_MUESTRA = 180
MINIMO_DE_PALABRAS_POR_PARRAFO = 25
MAXIMO_DE_PAGINAS = 20


def carpeta(carpeta_curso: Path) -> Path:
    return carpeta_curso / CARPETA


def archivos(carpeta_curso: Path) -> list[Path]:
    """Los PDF que la ficha del curso nombra en «Modelos» y que existen en la carpeta de modelos."""
    texto = almacen.valor(almacen.cargar(carpeta_curso, "curso"), "modelos.aprobados")
    nombres = [p.strip() for p in re.split(r";|\n", texto) if p.strip()]
    return [carpeta(carpeta_curso) / Path(n).name for n in nombres
            if (carpeta(carpeta_curso) / Path(n).name).is_file() and n.lower().endswith(".pdf")]


# ---------- Análisis de un PDF ----------

def _hex(entero: int) -> str:
    return f"{entero:06X}"


def _hex_de_relleno(color) -> str | None:
    if not color or len(color) != 3:
        return None
    return "".join(f"{round(c * 255):02X}" for c in color)


def _luminancia(color: str) -> float:
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _saturacion(color: str) -> float:
    r, g, b = (int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return max(r, g, b) - min(r, g, b)


def _nombre_de_fuente(nombre: str) -> str:
    """«ABCDEF+Calibri-Bold» → «Calibri»; «ArialMT» → «Arial». Se compara después sin espacios."""
    nombre = nombre.split("+", 1)[-1]
    nombre = re.split(r"[-,]", nombre)[0]
    return re.sub(r"(PSMT|MT|PS)$", "", nombre).strip()


def analizar(ruta: Path) -> dict:
    """Colores del texto, rellenos, fuentes y un pasaje de prosa, contados por cantidad de letras."""
    texto_por_color, relleno_por_color, letras_por_fuente = Counter(), Counter(), Counter()
    parrafos = []
    with pymupdf.open(ruta) as documento:
        for numero, pagina in enumerate(documento):
            if numero >= MAXIMO_DE_PAGINAS:
                break
            for bloque in pagina.get_text("dict")["blocks"]:
                for linea in bloque.get("lines", []):
                    for tramo in linea["spans"]:
                        letras = len(tramo["text"].strip())
                        if letras:
                            texto_por_color[_hex(tramo["color"])] += letras
                            letras_por_fuente[_nombre_de_fuente(tramo["font"])] += letras
            for dibujo in pagina.get_drawings():
                color = _hex_de_relleno(dibujo.get("fill"))
                if color:
                    rect = dibujo.get("rect")
                    relleno_por_color[color] += int(rect.width * rect.height) if rect else 1
            if numero > 0:  # la primera página suele ser la portada
                for bloque in pagina.get_text("blocks"):
                    texto = " ".join(bloque[4].split())
                    if bloque[6] == 0 and len(texto.split()) >= MINIMO_DE_PALABRAS_POR_PARRAFO:
                        parrafos.append(texto)
    return {
        "texto": texto_por_color.most_common(12),
        "rellenos": relleno_por_color.most_common(12),
        "fuentes": letras_por_fuente.most_common(6),
        "muestra": _muestra(parrafos),
    }


def _muestra(parrafos: list[str]) -> str:
    palabras = []
    for parrafo in parrafos:
        palabras += parrafo.split()
        if len(palabras) >= PALABRAS_DE_MUESTRA:
            break
    return " ".join(palabras[:PALABRAS_DE_MUESTRA])


def _analisis(carpeta_curso: Path) -> list[tuple[str, dict]]:
    """Analiza cada modelo una sola vez; si su huella no cambia, usa lo guardado."""
    rutas = archivos(carpeta_curso)
    if not rutas:
        return []
    guardado_en = carpeta(carpeta_curso) / ANALISIS
    guardado = json.loads(guardado_en.read_text(encoding="utf-8")) if guardado_en.exists() else {}
    resultado, cambio = [], False
    for ruta in rutas:
        huella = convertir.huella(ruta)
        entrada = guardado.get(ruta.name)
        if not entrada or entrada.get("huella") != huella:
            entrada = {"huella": huella, **analizar(ruta)}
            guardado[ruta.name] = entrada
            cambio = True
        resultado.append((ruta.name, entrada))
    if cambio:
        guardado_en.write_text(json.dumps(guardado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


# ---------- Lo que usan los materiales ----------

def apariencia(carpeta_curso: Path, tipografias_conocidas: tuple[str, ...]) -> dict:
    """Colores y tipografía sacados de los modelos. Devuelve solo lo que encontró, con el archivo de origen."""
    analisis = _analisis(carpeta_curso)
    if not analisis:
        return {}
    texto, rellenos, fuentes = Counter(), Counter(), Counter()
    for _, entrada in analisis:
        texto.update(dict(entrada["texto"]))
        rellenos.update(dict(entrada["rellenos"]))
        fuentes.update(dict(entrada["fuentes"]))
    resultado = {"origen": ", ".join(nombre for nombre, _ in analisis)}
    # Colores con tono propio, del texto y de los rellenos: el más usado es el principal y el siguiente, el acento.
    vivos = Counter()
    for color, peso in list(texto.items()) + [(c, p // 50) for c, p in rellenos.items()]:
        if _saturacion(color) >= 0.18 and 0.04 <= _luminancia(color) <= 0.8:
            vivos[color] += peso
    elegidos = [c for c, _ in vivos.most_common()]
    if elegidos:
        resultado["principal"] = elegidos[0]
        distintos = [c for c in elegidos[1:] if _distancia(c, elegidos[0]) > 90]
        if distintos:
            resultado["acento"] = distintos[0]
    claros = [c for c, _ in rellenos.most_common() if 0.85 <= _luminancia(c) < 0.99]
    if claros:
        resultado["fondo"] = claros[0]
    oscuros = [c for c, _ in texto.most_common() if _luminancia(c) < 0.25 and _saturacion(c) < 0.18]
    if oscuros:
        resultado["texto"] = oscuros[0]
    conocidas = {t.lower().replace(" ", ""): t for t in tipografias_conocidas}
    for fuente, _ in fuentes.most_common():
        clave = fuente.lower().replace(" ", "")
        if clave in conocidas:
            resultado["tipografia"] = conocidas[clave]
            break
    return resultado


def _distancia(a: str, b: str) -> float:
    return sum(abs(int(a[i:i + 2], 16) - int(b[i:i + 2], 16)) for i in (0, 2, 4))


def muestra_de_tono(carpeta_curso: Path) -> tuple[str, str]:
    """Un pasaje corto de prosa del primer modelo que la tenga, con su archivo. Vacío si no hay."""
    for nombre, entrada in _analisis(carpeta_curso):
        if entrada.get("muestra"):
            return nombre, entrada["muestra"]
    return "", ""
