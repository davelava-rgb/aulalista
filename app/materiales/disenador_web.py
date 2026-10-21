"""Agente diseñador de la página del alumno de la actividad web (PLAN.md §0, decisión 57; fase 8c del plan).

El redactor escribe el contenido y la validación lo aprueba. Después, el diseñador escribe la página completa, a
medida, en un solo archivo HTML con el CSS y el JavaScript dentro. AulaLista:
1. pone el contenido aprobado, tal cual, en el bloque <script type="application/json" id="contenido">: el
   diseñador deja ahí la marca MARCA y la página dibuja todo su texto desde ese bloque;
2. revisa la página antes de entregarla (controles de la decisión 57 f): el bloque de contenido es idéntico al
   aprobado; todo texto visible, en el HTML o en el JavaScript, sale del contenido salvo etiquetas cortas; sin
   scripts ni hojas externas, salvo las fuentes de Google; sin fetch, XMLHttpRequest, WebSocket, eval ni import;
   sin tiempos; solo los colores de la ficha y grises.
Las pruebas en el navegador (Playwright) llegan en la fase 8d y usan el contrato de atributos «data-» de la guía.
"""

import html.parser
import json
import re
from pathlib import Path

from app.materiales import estilo
from app.materiales.contenido import Actividad
from app.validacion import verificador

MARCA = "/*CONTENIDO*/"
PALABRAS_DE_UNA_ETIQUETA = 8
REGLA_DEL_PUNTAJE = "Cada pregunta suma sus puntos solo si se acierta en el primer intento."
HOSTS_DE_FUENTES = ("fonts.googleapis.com", "fonts.gstatic.com")   # también la conexión previa (preconnect)
GRIS_MAXIMO = 24   # diferencia entre el canal más alto y el más bajo: #AEB5BB, un gris azulado, sigue siendo gris

ESQUEMA_DISENO = {
    "type": "object",
    "properties": {"html": {"type": "string"}, "notas": {"type": "string"}},
    "required": ["html", "notas"],
    "additionalProperties": False,
}
# Un arreglo cambia trozos de la página: reescribirla entera en cada arreglo costaría casi lo mismo que el diseño.
ESQUEMA_ARREGLO = {
    "type": "object",
    "properties": {
        "cambios": {"type": "array", "items": {
            "type": "object",
            "properties": {"buscar": {"type": "string"}, "reemplazar": {"type": "string"}},
            "required": ["buscar", "reemplazar"], "additionalProperties": False}},
        "notas": {"type": "string"},
    },
    "required": ["cambios", "notas"],
    "additionalProperties": False,
}


# ---------- Los datos de la página ----------

def datos_de_la_pagina(actividad: Actividad, curso: str, sesion: int, nombre_curso: str, nota_del_puntaje: str) -> dict:
    """Lo que la página muestra: el contenido aprobado sin los pasajes ni las decisiones del redactor, más los textos
    fijos del programa y la clave con que la página guarda el avance del alumno."""
    contenido = actividad.model_dump(exclude={"pasajes", "decisiones"})
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


# ---------- Guía y pedidos ----------

GUIA = """ERES EL DISEÑADOR DE LA PÁGINA DE UNA ACTIVIDAD PARA ALUMNOS.
El contenido ya está escrito y aprobado. Tu trabajo es solo el diseño y la interacción: escribe una página web
completa, a medida, que el alumno recorre por pasos para reforzar lo que aprendió en clase. Diséñala como un
diseñador de producto con oficio: con carácter propio, que se sienta hecha para este tema y este caso, no como una
plantilla.

CÓMO ES LA PÁGINA
- Un solo archivo HTML, con el CSS y el JavaScript dentro. Sin librerías. Solo puedes cargar fuentes de Google
  Fonts (fonts.googleapis.com); la página debe verse bien sin conexión, con fuentes del sistema de respaldo.
- El contenido va en un bloque que AulaLista llena. Escríbelo exactamente así, una sola vez:
    <script type="application/json" id="contenido">{marca}</script>
  Tu JavaScript lo lee con JSON.parse(document.getElementById("contenido").textContent) y dibuja la página desde
  ahí. Los datos están abajo, en «DATOS DE LA PÁGINA»: tienen la misma forma que el bloque.
- No uses fetch, XMLHttpRequest, WebSocket, eval, new Function, import ni scripts u hojas de estilo externos.
- El avance del alumno se guarda en localStorage con la clave de «clave», siempre dentro de try/catch. Si el
  navegador no deja guardar, la página funciona igual. Guarda el paso actual, las respuestas, los intentos y la
  retroalimentación.

EL TEXTO
- Todo el texto del contenido sale del bloque, tal cual: no lo copies dentro del HTML ni del JavaScript, no lo
  cambies, no lo resumas y no agregues afirmaciones sobre el tema.
- Solo puedes escribir etiquetas cortas de {etiqueta} palabras como máximo: botones («Anterior», «Siguiente: Paso 2»,
  «Comprobar», «Intentar otra vez», «Copiar mi entrega»), títulos de interfaz («Su entrega», «Ver los datos del caso»),
  avisos breves («Respuesta correcta», «Revise su respuesta»). Una etiqueta nombra o guía; nunca enseña ni afirma
  algo del tema. Usa el trato del contenido (usted o tú).
- Sin tiempos ni duración: ni minutos, ni cronómetros, ni cuentas regresivas.

CÓMO FUNCIONA
- Un inicio con «titulo», «presentacion», el curso y la sesión. Después, un paso por elemento de «pasos», en orden,
  y al final la entrega.
- Una barra de pasos arriba: el paso actual marcado y los completos con otro aspecto (con ícono o texto, no solo
  color). No se avanza sin responder todas las preguntas del paso actual; los pasos no alcanzados quedan
  desactivados. Botones «Anterior» y «Siguiente».
- El caso («caso»: título, párrafos, tablas y gráficos) se puede ver desde cualquier paso, por ejemplo en una
  columna fija en escritorio y en un panel que se abre en celular. Dibuja los gráficos con SVG o CSS desde sus
  datos, con su título y sus ejes, y ofrece los mismos datos como tabla. Las tablas anchas se desplazan dentro de su
  recuadro, nunca la página.
- «recuerde», si no está vacío, va en un recuadro destacado del paso.
- Cada pregunta según su «tipo»:
  - opcion_unica: botones de opción. opcion_multiple: casillas.
  - ordenar: la lista mezclada siempre con el mismo orden (por ejemplo, invertida o rotada en uno; nunca en el orden
    correcto) y botones para subir y bajar cada elemento. No dependas solo de arrastrar.
  - relacionar: por cada «izquierda», una lista desplegable con todas las «derecha», en un orden mezclado fijo.
  - clasificar: por cada elemento, una lista desplegable con las «categorias».
- Botón «Comprobar» por pregunta. La respuesta es correcta solo si coincide entera. Al comprobar, muestra si es
  correcta, con ícono y texto, y la «explicacion» de cada opción o elemento que el alumno eligió; si es correcta,
  también la de la respuesta correcta. Botón «Intentar otra vez» si no acertó. Cuenta los intentos.
- Puntos: cada pregunta suma sus «puntos» solo si se acierta en el primer intento. Muestra «puntos» junto a cada
  pregunta, y en la entrega el puntaje obtenido de «puntaje_total», con «regla_del_puntaje» y «nota_del_puntaje».
- La entrega: un campo para el nombre del alumno, un resumen de todas sus respuestas con sus intentos y el puntaje,
  un botón «Copiar mi entrega» (portapapeles, y si falla, un cuadro de texto ya seleccionado para copiar a mano) y
  un botón «Borrar mis respuestas» que pide confirmación.

CONTRATO PARA LAS PRUEBAS (obligatorio: AulaLista recorre la página con un navegador usando estos atributos)
- Cada pantalla lleva data-paso: "0" el inicio, "1", "2"… cada paso y "entrega" la entrega. Solo la pantalla actual
  está visible.
- Botones con data-accion="siguiente" y data-accion="anterior".
- Cada pregunta, un contenedor con data-pregunta="i.j" (paso i y pregunta j, desde 1). Dentro:
  - opcion_unica y opcion_multiple: inputs con value igual a la posición de la opción en «opciones» (desde 0).
  - ordenar: cada elemento con data-elemento igual a su posición en «elementos» (desde 0), y botones
    data-accion="subir" y data-accion="bajar".
  - relacionar: un select por par con data-izquierda igual a su posición en «pares»; cada option con value igual a
    la posición del par al que pertenece esa derecha.
  - clasificar: un select por elemento con data-elemento igual a su posición; cada option con value igual al texto
    de la categoría.
  - Un botón data-accion="comprobar" y otro data-accion="reintentar". Después de comprobar, un elemento con
    data-resultado="correcta" o data-resultado="incorrecta".
- En la entrega: un input con data-campo="nombre", un elemento data-puntaje que muestra solo el número obtenido,
  un botón data-accion="copiar" y un botón data-accion="borrar".

EL DISEÑO
Reglas fijas:
- Solo los colores de la ficha (abajo, en «COLORES DE LA FICHA») y grises. Para tonos suaves usa color-mix() o
  transparencia sobre esos colores, no otros colores. Define los colores como variables en :root.
- Modo claro y modo oscuro con prefers-color-scheme, con contraste suficiente en los dos.
- La tipografía de la ficha para el texto; puedes elegir una fuente de Google para los títulos.
- Funciona en celular (375 px de ancho) sin desplazamiento horizontal de la página.
- Botones y controles de 44 px de alto como mínimo. Foco visible con el teclado. Todo se usa con el teclado.
  Etiquetas para los lectores de pantalla y aria-live en la retroalimentación. Correcto e incorrecto, con ícono y
  texto, no solo con color.
- Hover solo en pantallas con puntero (@media (hover:hover)). Animaciones breves, solo con transform y opacity, y
  ninguna con prefers-reduced-motion: reduce.
Lo demás lo decides tú: la composición, la jerarquía, el ritmo, los detalles que hacen que el caso se sienta real.
"""


def sistema(datos_: dict, identidad: estilo.Identidad) -> str:
    """La guía y los datos: lo que no cambia entre el diseño y sus arreglos. Va en el mensaje de sistema, en caché."""
    colores = {"principal": identidad.principal, "acento": identidad.acento, "advertencia": identidad.advertencia,
               "fondo": identidad.fondo, "texto": identidad.texto}
    return "\n".join([
        GUIA.replace("{etiqueta}", str(PALABRAS_DE_UNA_ETIQUETA)).replace("{marca}", MARCA),
        "COLORES DE LA FICHA (hexadecimal): " + json.dumps({k: f"#{v}" for k, v in colores.items()}),
        f"TIPOGRAFÍA DE LA FICHA: {identidad.tipografia}",
        "DATOS DE LA PÁGINA (la forma del bloque de contenido):",
        json.dumps(datos_, ensure_ascii=False),
    ])


def escribir_sistema(datos_: dict, identidad: estilo.Identidad, carpeta: Path) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    ruta = carpeta / "diseno_sistema.txt"
    ruta.write_text(sistema(datos_, identidad), encoding="utf-8")
    return ruta


def pedido_de_diseno() -> str:
    return "\n".join([
        "Diseña la página según la guía y los datos de tus instrucciones.",
        f"Devuelve en «html» el archivo completo, con el bloque de contenido y la marca {MARCA} donde dice la guía.",
        "En «notas», resume en una o dos frases las decisiones de diseño.",
    ])


def pedido_de_arreglo(html_: str, problemas: list[str], con_imagenes: bool = False) -> str:
    return "\n".join([
        "Corrige la página según la guía y los datos de tus instrucciones.",
        *(["Arriba van capturas de la página donde falló el recorrido en el navegador. Míralas para encontrar la "
           "causa de cada problema antes de cambiar el código."] if con_imagenes else []),
        "",
        "PÁGINA ACTUAL (con la marca del contenido; AulaLista la llena):",
        html_,
        "",
        "PROBLEMAS QUE ENCONTRÓ AULALISTA (controles del programa o recorrido en un navegador con el contrato de la",
        "guía). Corrígelos todos.",
        *[f"- {p}" for p in problemas],
        "",
        "CÓMO DEVOLVER EL ARREGLO",
        "- En «cambios», una entrada por trozo: «buscar» copiado tal cual de la página actual (debe aparecer una sola",
        "  vez; toma unas líneas de contexto) y «reemplazar» con el texto nuevo. No reescribas lo que no cambia.",
        "- En «notas», di en una frase qué cambiaste.",
    ])


def aplicar_cambios(html_: str, cambios: list[dict]) -> tuple[str, list[str]]:
    """Aplica los cambios de un arreglo. Un trozo que no está una sola vez no se aplica y vuelve como problema."""
    problemas = []
    for c in cambios:
        veces = html_.count(c["buscar"]) if c["buscar"] else 0
        if veces != 1:
            problemas.append(f"Un cambio no se aplicó: su «buscar» aparece {veces} veces en la página "
                             f"(empieza con «{c['buscar'][:60]}»). Cópialo tal cual y con contexto para que sea único.")
            continue
        html_ = html_.replace(c["buscar"], c["reemplazar"], 1)
    return html_, problemas


# ---------- Controles de la página (decisión 57 f) ----------

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
