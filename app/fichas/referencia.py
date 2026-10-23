"""Material de referencia de una sesión y sus exclusiones (PLAN.md §0, decisión 23).

La ficha de la sesión puede nombrar archivos de las fuentes del curso, con sus páginas:
    manual.pdf: páginas 5 a 20
    guia.pdf: páginas 3 a 4, 9 a 12
    anexo.pdf                        (sin páginas: el archivo completo)
Las páginas son las del archivo (las del PDF), no el número impreso.

Con material de referencia, la lectura cubre todos sus temas menos las exclusiones, y su extensión
sale de esos temas. Sin material de referencia, mandan los temas de la ficha y el máximo de seis páginas.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from app.fichas import almacen, verificacion
from app.fuentes import convertir
from app.validacion.pasajes import FICHA_DE_LA_SESION, FICHA_DEL_CURSO, Corpus, raices

RANGO = re.compile(r"(\d+)\s*(?:a|al|hasta|-|–)\s*(\d+)|(\d+)")


@dataclass
class Tramo:
    archivo: str
    rangos: list[tuple[int, int]] = field(default_factory=list)   # vacío: el archivo completo
    paginas_del_archivo: int = 0

    @property
    def paginas(self) -> int:
        if not self.rangos:
            return self.paginas_del_archivo
        return len({p for desde, hasta in self.rangos for p in range(desde, hasta + 1)})

    def describir(self) -> str:
        cuantas = f"{self.paginas} página" + ("" if self.paginas == 1 else "s")
        if not self.rangos:
            return f"{self.archivo}: el archivo completo ({cuantas})"
        tramos = ", ".join(f"{a} a {b}" if a != b else str(a) for a, b in self.rangos)
        palabra = "página" if len(self.rangos) == 1 and self.rangos[0][0] == self.rangos[0][1] else "páginas"
        return f"{self.archivo}: {palabra} {tramos} ({cuantas})"


def _plano(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return " ".join(sin_tildes.lower().split())


def _renglones(texto: str) -> list[str]:
    return [l.strip().lstrip("-• ").strip() for l in (texto or "").splitlines() if l.strip().lstrip("-• ").strip()]


def tiene_referencia(ficha_sesion: dict) -> bool:
    return bool(_renglones(almacen.valor(ficha_sesion, "sesion.referencia")))


def exclusiones(ficha_sesion: dict) -> list[str]:
    return _renglones(almacen.valor(ficha_sesion, "sesion.exclusiones"))


def _buscar_archivo(nombre: str, fuentes: list[str]) -> str | None:
    buscado = _plano(nombre)
    exactos = [f for f in fuentes if _plano(f) == buscado]
    if exactos:
        return exactos[0]
    parecidos = [f for f in fuentes if buscado and buscado in _plano(f)]
    return parecidos[0] if len(parecidos) == 1 else None


def _rangos(texto: str) -> list[tuple[int, int]]:
    rangos = []
    for m in RANGO.finditer(texto):
        desde, hasta = (int(m.group(1)), int(m.group(2))) if m.group(1) else (int(m.group(3)),) * 2
        rangos.append((min(desde, hasta), max(desde, hasta)))
    return rangos


def interpretar(carpeta_curso: Path, ficha_sesion: dict) -> tuple[list[Tramo], list[str]]:
    """Los tramos del material de referencia y los problemas que impiden usarlo."""
    fuentes = verificacion.fuentes_utilizables(carpeta_curso)
    tramos, problemas = [], []
    for linea in _renglones(almacen.valor(ficha_sesion, "sesion.referencia")):
        # El nombre del archivo va antes de «:». Si no hay «:», la línea entera es el nombre.
        nombre, _, paginas = linea.partition(":") if ":" in linea else (linea, "", "")
        archivo = _buscar_archivo(nombre.strip(), fuentes)
        if archivo is None:
            problemas.append(f"Material de referencia: «{nombre.strip()}» no es una fuente convertida del curso.")
            continue
        total = max((p.get("pagina") or 0 for p in convertir.leer_pasajes(carpeta_curso, archivo)), default=0)
        rangos = _rangos(paginas)
        fuera = [r for r in rangos if r[0] < 1 or (total and r[1] > total)]
        if fuera:
            problemas.append(f"Material de referencia: {archivo} tiene {total} páginas; revisa las páginas «{paginas.strip()}».")
            continue
        tramos.append(Tramo(archivo, rangos, total))
    return tramos, problemas


# Tope de lo que va dentro del pedido de redacción (PLAN.md §0, decisión 68 c). Las páginas del material de
# referencia van en el pedido; si pasan del tope, un programa las recorta a los pasajes que nombran los temas y el
# vocabulario de la sesión. El redactor ya no busca con herramientas: buscar costaba de seis a trece vueltas, y en
# cada vuelta se paga de nuevo todo lo anterior.
CARACTERES_EN_EL_PEDIDO = 60_000
PASAJES_POR_TEXTO = 4            # cuántos pasajes elige el programa por cada tema o concepto, sin referencia
FICHAS = (FICHA_DEL_CURSO, FICHA_DE_LA_SESION)


def _linea(fuente: str, pasaje: dict) -> str:
    return f"[{fuente} · {pasaje['ubicacion']}] {pasaje['texto']}"


def textos_de_la_sesion(ficha_sesion: dict) -> list[str]:
    """Lo que dice la ficha sobre el tema: título, alcance, temas, bloques, vocabulario, ejercicios y preguntas.
    Sirve para elegir pasajes de las fuentes y para recortar las páginas de referencia."""
    textos = []
    for campo_id, dato in ficha_sesion.get("campos", {}).items():
        if campo_id.startswith(("sesion.numero_titulo", "sesion.alcance", "lectura.temas", "lectura.bloque",
                                "vocabulario.", "ejercicio.", "pregunta.")):
            textos += _renglones((dato or {}).get("valor", ""))
    return [t for t in textos if t]


def palabras_clave(ficha_sesion: dict) -> set[str]:
    return set().union(*(raices(t) for t in textos_de_la_sesion(ficha_sesion))) if ficha_sesion else set()


def recortar(lineas: list[tuple[str, str]], claves: set[str], tope: int) -> list[str]:
    """`lineas` son pares (línea del pedido, texto del pasaje). Si caben en el tope, van todas. Si no, quedan las
    que nombran alguna palabra clave, en su orden; si todavía no caben, las que más palabras clave nombran."""
    if sum(len(l) for l, _ in lineas) <= tope:
        return [l for l, _ in lineas]
    puntuadas = [(len(claves & raices(texto)), i, l) for i, (l, texto) in enumerate(lineas)]
    con_clave = [(p, i, l) for p, i, l in puntuadas if p > 0]
    if sum(len(l) for _, _, l in con_clave) > tope:
        elegidas, largo = [], 0
        for p, i, l in sorted(con_clave, key=lambda x: (-x[0], x[1])):
            if largo + len(l) > tope:
                continue
            elegidas.append((p, i, l))
            largo += len(l)
        con_clave = elegidas
    return [l for _, _, l in sorted(con_clave, key=lambda x: x[1])]


def paginas(carpeta_curso: Path, ficha_sesion: dict, tope: int | None = None) -> list[str] | None:
    """Los pasajes de las páginas del material de referencia, copiados por un programa, sin IA, con la forma
    «[fuente · ubicación] texto». Si pasan del tope, se recortan a los que nombran los temas y el vocabulario de
    la sesión (decisión 68 c). None si la sesión no tiene material de referencia."""
    lineas = []
    for tramo in interpretar(carpeta_curso, ficha_sesion)[0]:
        for pasaje in convertir.leer_pasajes(carpeta_curso, tramo.archivo):
            pagina = pasaje.get("pagina") or 0
            if not tramo.rangos or any(desde <= pagina <= hasta for desde, hasta in tramo.rangos):
                lineas.append((_linea(tramo.archivo, pasaje), pasaje["texto"]))
    if not lineas:
        return None
    return recortar(lineas, palabras_clave(ficha_sesion), tope or CARACTERES_EN_EL_PEDIDO)


def pasajes_elegidos(carpeta_curso: Path, sesion: int, textos: list[str], cantidad: int = PASAJES_POR_TEXTO,
                     tope: int | None = None) -> list[str]:
    """Sin material de referencia: los pasajes de las fuentes del curso que más se parecen a cada texto (un tema,
    un concepto, un ejercicio), elegidos por el programa con la misma búsqueda de la revisión. Con la forma
    «[fuente · ubicación] texto», sin repetir y hasta el tope. Así el redactor no busca con Grep ni Read."""
    corpus = Corpus.del_curso(carpeta_curso, sesion)
    lineas, vistos, largo = [], set(), 0
    tope = tope or CARACTERES_EN_EL_PEDIDO
    for texto in textos:
        for p in corpus.buscar(texto, cantidad + len(FICHAS)):
            if p["fuente"] in FICHAS:
                continue
            clave = (p["fuente"], p["ubicacion"], p["texto"][:60])
            linea = _linea(p["fuente"], p)
            if clave in vistos or largo + len(linea) > tope:
                continue
            vistos.add(clave)
            lineas.append(linea)
            largo += len(linea)
    return lineas


def texto_de_paginas(lineas: list[str]) -> list[str]:
    """El apartado del pedido con las páginas ya copiadas."""
    return ["", "PÁGINAS DEL MATERIAL DE REFERENCIA, copiadas de la fuente por AulaLista. Una línea por pasaje, con la "
            "forma «[fuente · ubicación] texto». No tienes herramientas: todo lo que cites sale de aquí.", *lineas]


def texto_de_pasajes(lineas: list[str]) -> list[str]:
    """El apartado del pedido con los pasajes que eligió el programa."""
    return ["", "PASAJES DE LAS FUENTES DEL CURSO, elegidos por AulaLista para los temas y el vocabulario de la sesión. "
            "Una línea por pasaje, con la forma «[fuente · ubicación] texto». No tienes herramientas: todo lo que "
            "cites sale de aquí.", *(lineas or ["- (ninguno: no cites fuentes)"])]
