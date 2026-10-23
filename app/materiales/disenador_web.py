"""La página del alumno de la actividad web (PLAN.md §0, decisiones 57 y 70).

El redactor escribe el contenido y la validación lo aprueba. Después, AulaLista arma la página con su plantilla
fija (app/disenador/actividad.html): un solo archivo HTML con el CSS y el JavaScript dentro, con los colores y la
tipografía de la ficha. AulaLista:
1. pone el contenido aprobado, tal cual, en el bloque <script type="application/json" id="contenido">: la
   plantilla tiene ahí la marca MARCA y dibuja todo su texto desde ese bloque;
2. revisa la página antes de entregarla (controles de la decisión 57 f): el bloque de contenido es idéntico al
   aprobado; todo texto visible, en el HTML o en el JavaScript, sale del contenido salvo etiquetas cortas; sin
   scripts ni hojas externas, salvo las fuentes de Google; sin fetch, XMLHttpRequest, WebSocket, eval ni import;
   sin tiempos; solo los colores de la ficha y grises.
Playwright la recorre como un alumno (navegador.py) con el contrato de atributos «data-» de la plantilla. Desde la
decisión 70 no hay diseñador con IA: una falla de los controles o del navegador es un error de la plantilla.
"""

import html.parser
import json
import re
from pathlib import Path

from app.config import RAIZ
from app.materiales import estilo
from app.materiales.contenido import Actividad
from app.validacion import verificador

MARCA = "/*CONTENIDO*/"
PALABRAS_DE_UNA_ETIQUETA = 8
REGLA_DEL_PUNTAJE = "Cada pregunta suma sus puntos solo si se acierta en el primer intento."
HOSTS_DE_FUENTES = ("fonts.googleapis.com", "fonts.gstatic.com")   # también la conexión previa (preconnect)
GRIS_MAXIMO = 24   # diferencia entre el canal más alto y el más bajo: #AEB5BB, un gris azulado, sigue siendo gris

# ---------- Los datos de la página ----------

def datos_de_la_pagina(actividad: Actividad, curso: str, sesion: int, nombre_curso: str, nota_del_puntaje: str) -> dict:
    """Lo que la página muestra: el contenido aprobado sin los pasajes ni las decisiones del redactor, más los textos
    fijos del programa y la clave con que la página guarda el avance del alumno."""
    contenido = actividad.model_dump(exclude={"pasajes", "decisiones"})
    puntos = iter(actividad.puntos_finales())   # sobre 100 (decisión 59)
    for paso in contenido["pasos"]:
        for pregunta in paso["preguntas"]:
            pregunta["puntos"] = next(puntos)
    return {
        "curso": nombre_curso,
        "sesion": f"Sesión {sesion}",
        "clave": f"aulalista-{re.sub(r'[^a-z0-9]+', '-', curso.lower()).strip('-')}-s{sesion}-actividad-v1",
        "puntaje_total": actividad.puntaje_total,
        "nota_del_puntaje": nota_del_puntaje,
        "regla_del_puntaje": REGLA_DEL_PUNTAJE,
        **contenido,
    }


def bloque_de_contenido(datos_: dict) -> str:
    """El JSON del bloque de contenido, sin «</» para que no cierre la etiqueta script."""
    return json.dumps(datos_, ensure_ascii=False, indent=1).replace("</", "<\\/")


def armar(html_: str, datos_: dict) -> str:
    """Pone el contenido aprobado en la marca del diseñador."""
    return html_.replace(MARCA, bloque_de_contenido(datos_), 1)


# ---------- La página fija (decisión 70) ----------

PLANTILLA = RAIZ / "app" / "disenador" / "actividad.html"
MARCAS = {"{{PRINCIPAL}}": "principal", "{{ACENTO}}": "acento", "{{ADVERTENCIA}}": "advertencia", "{{FONDO}}": "fondo",
          "{{TEXTO}}": "texto"}


def plantilla_con_identidad(identidad: estilo.Identidad) -> str:
    """La plantilla con los colores y la tipografía de la ficha, con la marca del contenido todavía vacía."""
    pagina = PLANTILLA.read_text(encoding="utf-8")
    for marca, campo in MARCAS.items():
        pagina = pagina.replace(marca, "#" + getattr(identidad, campo).lstrip("#").upper())
    return pagina.replace("{{TIPOGRAFIA}}", identidad.tipografia)


def pagina_fija(datos_: dict, identidad: estilo.Identidad) -> str:
    """La página del alumno lista: la plantilla con la identidad de la ficha y el contenido aprobado en su bloque."""
    return armar(plantilla_con_identidad(identidad), datos_)


# ---------- Controles (decisión 57 f) ----------

class _Lector(html.parser.HTMLParser):
    """Separa el texto visible del HTML, los scripts, los estilos y las etiquetas que cargan algo de afuera."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.textos, self.scripts, self.estilos, self.externos, self.contenidos = [], [], [], [], []
        self._en = None
        self._actual: list[str] = []

    def handle_starttag(self, etiqueta, atributos):
        a = dict(atributos)
        if etiqueta == "script":
            if a.get("src"):
                self.externos.append(f"<script src=\"{a['src']}\">")
            self._en = "contenido" if a.get("type") == "application/json" and a.get("id") == "contenido" else (
                "datos" if a.get("type") == "application/json" else "script")
            self._actual = []
        elif etiqueta == "style":
            self._en, self._actual = "style", []
        elif etiqueta == "link":
            href = a.get("href") or ""
            if href.startswith(("http:", "https:", "//")) and not es_de_fuentes(href):
                self.externos.append(f"<link href=\"{href}\">")
        elif etiqueta in ("iframe", "object", "embed", "img", "audio", "video", "source"):
            src = a.get("src") or a.get("data") or ""
            if src.startswith(("http:", "https:", "//")) or etiqueta in ("iframe", "object", "embed"):
                self.externos.append(f"<{etiqueta}>")
        for nombre, valor in a.items():
            if nombre in ("title", "aria-label", "placeholder", "alt") and valor:
                self.textos.append(valor)

    def handle_endtag(self, etiqueta):
        if etiqueta in ("script", "style") and self._en:
            texto = "".join(self._actual)
            {"contenido": self.contenidos, "script": self.scripts, "style": self.estilos,
             "datos": self.scripts}[self._en].append(texto)
            self._en = None

    def handle_data(self, datos):
        if self._en:
            self._actual.append(datos)
        elif datos.strip():
            self.textos.append(datos)


PROHIBIDO = re.compile(r"\bfetch\s*\(|XMLHttpRequest|WebSocket|EventSource|sendBeacon|\beval\s*\(|new\s+Function\b|"
                       r"\bFunction\s*\(|\bimport\s*\(|^\s*import\b|\bimportScripts\b|\bWorker\s*\(", re.M)
IMPORTACION_CSS = re.compile(r"@import\s+(?:url\()?\s*['\"]?([^'\")\s;]+)")
URL_CSS = re.compile(r"url\(\s*['\"]?(https?:|//)([^'\")]+)")
LITERAL = re.compile(r"'((?:[^'\\\n]|\\.)*)'|\"((?:[^\"\\\n]|\\.)*)\"|`((?:[^`\\]|\\.)*)`", re.S)
COLOR_HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
COLOR_RGB = re.compile(r"rgba?\(\s*(\d+)[\s,]+(\d+)[\s,]+(\d+)")
SINTAXIS = re.compile(r"[{};=]|=>|\$\(")
# Un selector de CSS («.q-cuerpo input, button:not([aria-disabled])») no es texto que vea el alumno.
SELECTOR = re.compile(r"(?:^|[\s,(>+~])[.#][A-Za-z_-]|\[[\w-]+(?:[~|^$*]?=[^\]]*)?\]|:(?:not|is|where|has|nth-[a-z-]+)\(|"
                      r"::?(?:hover|focus|focus-visible|checked|disabled|before|after|first-child|last-child)\b")


def _normal(texto: str) -> str:
    texto = texto.lower().replace(" ", " ")
    texto = re.sub(r"[«»\"“”'‘’]", "", texto)
    return re.sub(r"\s+", " ", texto).strip(" .,:;·-–—•¿?¡!()")


def _palabras(texto: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", texto)


def _textos_de(valor) -> list[str]:
    if isinstance(valor, str):
        return [valor]
    if isinstance(valor, list):
        return [t for v in valor for t in _textos_de(v)]
    if isinstance(valor, dict):
        return [t for v in valor.values() for t in _textos_de(v)]
    return []


def _literales(codigo: str) -> list[str]:
    """Los textos entre comillas del JavaScript que parecen prosa: sin etiquetas HTML, con letras y espacios, y sin
    la sintaxis de CSS o de código. En una plantilla `…${x}…` cuenta cada tramo fijo."""
    textos = []
    for m in LITERAL.finditer(codigo):
        literal = next(g for g in m.groups() if g is not None)
        for tramo in re.split(r"\$\{[^}]*\}", literal):
            tramo = re.sub(r"<[^>]*>", " ", tramo).replace("\\n", " ")
            if (" " in tramo.strip() and not SINTAXIS.search(tramo) and not SELECTOR.search(tramo)
                    and re.search(r"[^\W\d_]{2}", tramo)):
                textos.append(tramo)
    return textos


def _ajeno(texto: str, corpus: str) -> bool:
    """Un texto es ajeno si suma más de PALABRAS_DE_UNA_ETIQUETA palabras que no salen del contenido."""
    normal = _normal(texto)
    if not normal or normal in corpus:
        return False
    tramos = [t.strip(" .,:;") for t in re.split(r"\s+[·|•–—:]\s+|[.!?]\s+", normal)]
    return sum(len(_palabras(t)) for t in tramos if t and t not in corpus) > PALABRAS_DE_UNA_ETIQUETA


def es_de_fuentes(url: str) -> bool:
    """Una dirección de las fuentes de Google, con ruta o sin ella."""
    host = re.sub(r"^(?:https?:)?//", "", url).split("/")[0].split("?")[0].lower()
    return url.startswith(("https://", "//")) and host in HOSTS_DE_FUENTES


def _gris(r: int, g: int, b: int) -> bool:
    return max(r, g, b) - min(r, g, b) <= GRIS_MAXIMO


def _hex6(valor: str) -> str:
    valor = valor.upper()
    return "".join(c * 2 for c in valor) if len(valor) == 3 else valor


def revisar(pagina: str, datos_: dict, identidad: estilo.Identidad) -> list[str]:
    """Los controles de la decisión 57 f sobre la página armada. Devuelve las fallas, cada una con su causa."""
    lector = _Lector()
    lector.feed(pagina)
    lector.close()
    fallas = []
    if len(lector.contenidos) != 1:
        fallas.append(f"La página debe tener un solo bloque <script type=\"application/json\" id=\"contenido\">; "
                      f"tiene {len(lector.contenidos)}.")
    else:
        try:
            igual = json.loads(lector.contenidos[0]) == datos_
        except json.JSONDecodeError:
            igual = False
        if not igual:
            fallas.append(f"El bloque de contenido no es el aprobado. Deja dentro solo la marca {MARCA}: AulaLista lo llena.")
    fallas += [f"Carga algo de afuera: {e}. Solo se permiten las fuentes de Google." for e in lector.externos]
    codigo = "\n".join(lector.scripts)
    for m in PROHIBIDO.finditer(codigo):
        fallas.append(f"El JavaScript usa «{m.group(0).strip()}», que no se permite.")
    estilos = "\n".join(lector.estilos)
    for m in IMPORTACION_CSS.finditer(estilos):
        if not es_de_fuentes(m.group(1)):
            fallas.append(f"El CSS importa «{m.group(1)}». Solo se permiten las fuentes de Google.")
    for m in URL_CSS.finditer(estilos + codigo):
        if not es_de_fuentes(m.group(1) + m.group(2)):
            fallas.append(f"Carga «{m.group(1)}{m.group(2)[:60]}» desde afuera. Solo se permiten las fuentes de Google.")

    corpus = _normal(" \n ".join(_textos_de(datos_)))
    visibles = lector.textos + _literales(codigo)
    for texto in visibles:
        if _ajeno(texto, corpus):
            fallas.append(f"Texto que no sale del contenido: «{' '.join(texto.split())[:120]}». Dibuja el texto desde el "
                          f"bloque de contenido; solo las etiquetas de {PALABRAS_DE_UNA_ETIQUETA} palabras o menos "
                          "pueden ir escritas en la página.")
    tiempos = [(r, p) for n, r, p in verificador.verificar.TIEMPOS_Y_PUNTAJES if r == "tiempo"]
    for texto in visibles:
        normal = verificador.verificar.normalizar(texto)
        for _, patron in tiempos:
            m = patron.search(normal)
            if m:
                fallas.append(f"Muestra un tiempo: «{m.group(0).strip()}». La actividad no muestra tiempos.")

    permitidos = {c.upper() for c in identidad.colores_permitidos()}
    ajenos = set()
    for m in COLOR_HEX.finditer(estilos + codigo):
        color = _hex6(m.group(1))
        r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
        if color not in permitidos and not _gris(r, g, b):
            ajenos.add(f"#{color}")
    for m in COLOR_RGB.finditer(estilos + codigo):
        r, g, b = (int(x) for x in m.groups())
        color = f"{r:02X}{g:02X}{b:02X}"
        if color not in permitidos and not _gris(r, g, b):
            ajenos.add(f"rgb({r}, {g}, {b})")
    if ajenos:
        fallas.append(f"Usa colores que no son de la ficha: {', '.join(sorted(ajenos))}. Usa solo los colores de la "
                      "ficha y grises; para tonos suaves, color-mix() o transparencia.")
    for atributo in ("data-paso", "data-pregunta", "data-accion", "data-resultado", "data-puntaje", "data-campo"):
        if atributo not in pagina:
            fallas.append(f"Falta el atributo {atributo} del contrato para las pruebas.")
    return fallas
