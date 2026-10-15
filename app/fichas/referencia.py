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


# Hasta este largo, las páginas del material de referencia van dentro del pedido de redacción y el redactor no las
# busca con herramientas: buscarlas costaba de seis a diez vueltas, y en cada vuelta se paga de nuevo todo lo anterior.
CARACTERES_EN_EL_PEDIDO = 160_000


def paginas(carpeta_curso: Path, ficha_sesion: dict) -> list[str] | None:
    """Los pasajes de las páginas del material de referencia, copiados por un programa, sin IA, con la forma
    «[fuente · ubicación] texto». None si la sesión no tiene referencia o si es demasiado larga: entonces el
    redactor los busca con Grep y Read."""
    lineas = []
    for tramo in interpretar(carpeta_curso, ficha_sesion)[0]:
        for pasaje in convertir.leer_pasajes(carpeta_curso, tramo.archivo):
            pagina = pasaje.get("pagina") or 0
            if not tramo.rangos or any(desde <= pagina <= hasta for desde, hasta in tramo.rangos):
                lineas.append(f"[{tramo.archivo} · {pasaje['ubicacion']}] {pasaje['texto']}")
    if not lineas or sum(len(l) for l in lineas) > CARACTERES_EN_EL_PEDIDO:
        return None
    return lineas


def texto_de_paginas(lineas: list[str]) -> list[str]:
    """El apartado del pedido con las páginas ya copiadas."""
    return ["", "PÁGINAS DEL MATERIAL DE REFERENCIA, copiadas de la fuente por AulaLista. Una línea por pasaje, con la "
            "forma «[fuente · ubicación] texto». No las busques con Grep ni Read: están aquí.", *lineas]
