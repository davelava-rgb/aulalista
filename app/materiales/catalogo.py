"""Paletas listas y estilos de los materiales (PLAN.md §0, decisión 27).

Un estilo cambia la portada, el tamaño de los títulos, el borde de los recuadros y el tono.
No cambia el cuerpo (11 pt, interlineado 1,15), los recuadros sombreados ni las reglas de lenguaje claro.
Sin estilo en la ficha vale «profesional», que es el diseño de siempre.
"""

from dataclasses import dataclass

# Cada paleta: principal, acento, advertencia, fondo de recuadro y texto. Tres colores, más fondo y texto.
PALETAS = {
    "Sobria": {"principal": "0F4C5C", "acento": "B7791F", "advertencia": "A3261F", "fondo": "F2F4F5", "texto": "1F2933"},
    "Azul institucional": {"principal": "1F4E79", "acento": "2E86AB", "advertencia": "B03A2E", "fondo": "EEF4FA", "texto": "1F2933"},
    "Verde": {"principal": "1E5631", "acento": "8A6D1D", "advertencia": "A3261F", "fondo": "F0F5F1", "texto": "1F2933"},
    "Vino": {"principal": "6D1A36", "acento": "9C7A1E", "advertencia": "B03A2E", "fondo": "F7F1F3", "texto": "2B2B2B"},
    "Grafito": {"principal": "2F3E46", "acento": "52796F", "advertencia": "B23A48", "fondo": "F1F3F4", "texto": "1F2933"},
    "Índigo": {"principal": "3B3B98", "acento": "C2571A", "advertencia": "A3261F", "fondo": "F2F2FA", "texto": "1F2933"},
}


@dataclass(frozen=True)
class Estilo:
    nombre: str
    descripcion: str
    tono: str
    titulo_pt: float          # título de la portada en el Word
    titulos_pt: tuple[float, float, float]   # Título 1, 2 y 3
    portada_centrada: bool = False
    franja: bool = False      # franja del color principal arriba de la portada
    linea_titulo1: bool = False   # línea fina del color principal bajo cada Título 1
    borde_recuadro: int = 24  # grosor del borde izquierdo, en octavos de punto (Word)
    acento_en_titulo2: bool = False


ESTILOS = {
    "profesional": Estilo(
        "profesional", "Directo y sobrio. Es el diseño de siempre.",
        "Directo y neutro. Habla al alumno con respeto y sin adornos.",
        26, (16, 13, 11.5)),
    "académico": Estilo(
        "académico", "Formal, con portada centrada y una línea bajo cada título.",
        "Formal y preciso. Prefiere la forma impersonal («se revisa», «conviene») y explica cada término con cuidado.",
        24, (15, 12.5, 11.5), portada_centrada=True, linea_titulo1=True, borde_recuadro=16),
    "moderno": Estilo(
        "moderno", "Títulos grandes y una franja de color en la portada.",
        "Ágil. Oraciones cortas que empiezan con un verbo de acción. Sin modas ni palabras en inglés innecesarias.",
        32, (18, 14, 12), franja=True, borde_recuadro=36),
    "corporativo": Estilo(
        "corporativo", "Franja de color en la portada y una línea bajo cada título.",
        "Sobrio y orientado al trabajo. Los ejemplos se ligan a los procesos de la empresa del caso.",
        28, (16, 13, 11.5), franja=True, linea_titulo1=True),
    "minimalista": Estilo(
        "minimalista", "Pocos elementos: títulos medianos y bordes finos.",
        "Lo mínimo necesario. Cada oración da una sola instrucción o un solo dato.",
        28, (15, 12, 11), borde_recuadro=12),
    "cercano": Estilo(
        "cercano", "Cálido: subtítulos en el color de acento y bordes gruesos.",
        "Cálido y cercano. Trata al alumno de tú y usa situaciones cotidianas del caso.",
        26, (17, 13.5, 12), borde_recuadro=30, acento_en_titulo2=True),
}
ESTILO_POR_OMISION = "profesional"


def estilo(nombre: str) -> Estilo:
    """El estilo de la ficha. Ignora mayúsculas y tildes; uno desconocido vale «profesional»."""
    clave = (nombre or "").strip().lower()
    sin_tildes = str.maketrans("áéíóú", "aeiou")
    for nombre_estilo, datos in ESTILOS.items():
        if clave and clave.translate(sin_tildes) == nombre_estilo.translate(sin_tildes):
            return datos
    return ESTILOS[ESTILO_POR_OMISION]
