"""Identidad visual de los materiales, tomada de la ficha del curso (SKILL.md, «Diseño común»).

- Máximo tres colores (principal, acento y advertencia), más los fondos de recuadro y el texto.
- Si un color no alcanza el contraste mínimo como texto, se oscurece solo en el texto.
- Si la ficha no trae paleta, se usa una sobria de tres colores y se avisa en la entrega.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from app.fichas import almacen

PALETA_SOBRIA = {
    "principal": "0F4C5C",
    "acento": "B7791F",
    "advertencia": "A3261F",
    "fondo": "F2F4F5",
    "texto": "1F2933",
}
GRIS_FILA_ALTERNA = "F5F5F5"
BLANCO = "FFFFFF"
CONTRASTE_MINIMO = 4.5
TIPOGRAFIA_POR_OMISION = "Calibri"
EXTENSIONES_LOGO = (".png", ".jpg", ".jpeg")


@dataclass
class Identidad:
    principal: str
    acento: str
    advertencia: str
    fondo: str
    texto: str
    tipografia: str
    logo: Path | None
    avisos: list[str] = field(default_factory=list)

    def colores_permitidos(self) -> set[str]:
        """Todos los colores que un material puede usar (prueba de diseño uniforme)."""
        base = {self.principal, self.acento, self.advertencia, self.fondo, self.texto, GRIS_FILA_ALTERNA, BLANCO}
        return base | {para_texto(c) for c in (self.principal, self.acento, self.advertencia)}


def _hex(texto: str) -> str | None:
    coincidencia = re.search(r"#?\b([0-9A-Fa-f]{6})\b", texto or "")
    return coincidencia.group(1).upper() if coincidencia else None


def _luminancia(color: str) -> float:
    def canal(valor: int) -> float:
        c = valor / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (int(color[i:i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def contraste(color: str, fondo: str = BLANCO) -> float:
    a, b = sorted((_luminancia(color), _luminancia(fondo)), reverse=True)
    return (a + 0.05) / (b + 0.05)


def para_texto(color: str, fondo: str = BLANCO) -> str:
    """El mismo color, oscurecido lo justo para leerse como texto sobre el fondo."""
    actual = color.upper()
    while contraste(actual, fondo) < CONTRASTE_MINIMO:
        actual = "".join(f"{max(0, int(int(actual[i:i + 2], 16) * 0.9)):02X}" for i in (0, 2, 4))
    return actual


def _buscar_logo(carpeta_curso: Path, nombre: str) -> Path | None:
    nombre = (nombre or "").strip().strip('"«»')
    if not nombre or nombre.lower() == "sin logo":
        return None
    for carpeta in (carpeta_curso, carpeta_curso / "fuentes"):
        ruta = carpeta / Path(nombre).name
        if ruta.exists() and ruta.suffix.lower() in EXTENSIONES_LOGO:
            return ruta
    return None


def desde_ficha(carpeta_curso: Path) -> Identidad:
    ficha = almacen.cargar(carpeta_curso, "curso")
    leidos = {
        clave: _hex(almacen.valor(ficha, f"visual.{campo}"))
        for clave, campo in (("principal", "principal"), ("acento", "acento"), ("advertencia", "advertencia"),
                             ("fondo", "fondos"), ("texto", "texto"))
    }
    avisos = []
    if not any(leidos[c] for c in ("principal", "acento", "advertencia")):
        avisos.append("La ficha no trae paleta. Usé una sobria de tres colores: "
                      f"#{PALETA_SOBRIA['principal']}, #{PALETA_SOBRIA['acento']} y #{PALETA_SOBRIA['advertencia']}. "
                      "Confírmala o escribe tus colores en la ficha del curso.")
    colores = {clave: leidos[clave] or PALETA_SOBRIA[clave] for clave in PALETA_SOBRIA}
    nombre_logo = almacen.valor(ficha, "visual.logo")
    logo = _buscar_logo(carpeta_curso, nombre_logo)
    if logo is None:
        if nombre_logo.strip() and nombre_logo.strip().lower() != "sin logo":
            avisos.append(f"No encontré el logo «{nombre_logo}» en la carpeta del curso. La portada va sin logo.")
        else:
            avisos.append("La ficha no trae logo. La portada va sin logo.")
    tipografia = almacen.valor(ficha, "visual.tipografia").strip() or TIPOGRAFIA_POR_OMISION
    return Identidad(tipografia=tipografia, logo=logo, avisos=avisos, **colores)
