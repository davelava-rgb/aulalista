"""Contenido de cada material como datos estructurados.

El agente redactor escribe estos datos. Los generadores de archivos los convierten en Word,
PowerPoint, Excel o HTML con el mismo diseño (CLAUDE.md: el agente no escribe Word a mano).
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Tabla(BaseModel):
    titulo: str
    encabezados: list[str] = Field(min_length=2)
    filas: list[list[str]] = Field(min_length=1)

    @field_validator("filas")
    @classmethod
    def mismas_columnas(cls, filas, info):
        columnas = len(info.data.get("encabezados", []))
        if any(len(f) != columnas for f in filas):
            raise ValueError("cada fila debe tener tantas celdas como encabezados")
        return filas


class Ejemplo(BaseModel):
    titulo: str
    parrafos: list[str] = Field(min_length=1)


class Bloque(BaseModel):
    subtitulo: str
    parrafos: list[str] = Field(min_length=1)
    ejemplo: Ejemplo
    tabla: Tabla | None = None


class Aplicalo(BaseModel):
    parrafos: list[str] = Field(min_length=1)
    plantilla: list[str] = Field(min_length=1)  # técnica o plantilla lista para copiar, una línea por elemento


class Pasaje(BaseModel):
    """Ancla de una oración: el pasaje de la fuente que la sostiene, copiado tal cual."""
    oracion: str = ""
    fuente: str
    ubicacion: str
    texto: str


# Tipos de decisión del redactor (PLAN.md §0, decisión 24):
# - «sin fuente»: afirma algo del tema que no está en ninguna fuente ni ficha. Va a «Decisiones pendientes».
# - «decisión»: se aparta de las fichas o de las fuentes, o cambia lo que lee el alumno. Va a «Qué decidí».
# - «nota»: solo describe el trabajo. Va a la hoja Hallazgos.
TIPOS_DE_DECISION = ("sin fuente", "decisión", "nota")


class Decision(BaseModel):
    texto: str
    tipo: Literal["sin fuente", "decisión", "nota"] = "decisión"


class Lectura(BaseModel):
    idea_central: list[str] = Field(min_length=1, max_length=3)
    # De 2 a 4 sin material de referencia. Con referencia, los que pidan sus temas (decisión 23);
    # el tope solo frena una respuesta rota.
    bloques: list[Bloque] = Field(min_length=2, max_length=12)
    aplicalo: Aplicalo
    cuidado: list[str] = Field(min_length=1, max_length=3)
    pasajes: list[Pasaje] = Field(default_factory=list)       # pasajes copiados de las fuentes antes de redactar
    decisiones: list[Decision] = Field(default_factory=list)  # lo que las fichas no definían, con su tipo
    agrupacion: str = ""                                       # si hubo más temas que bloques, cómo se agruparon

    @field_validator("decisiones", mode="before")
    @classmethod
    def decisiones_de_texto(cls, valor):
        """Las lecturas anteriores a la decisión 24 guardaban cada decisión como texto."""
        return [{"texto": d} if isinstance(d, str) else d for d in (valor or [])]


def _objeto(propiedades: dict, requeridas: list[str] | None = None) -> dict:
    return {
        "type": "object",
        "properties": propiedades,
        "required": requeridas if requeridas is not None else list(propiedades),
        "additionalProperties": False,
    }


TEXTOS = {"type": "array", "items": {"type": "string"}}
ESQUEMA_TABLA = _objeto({"titulo": {"type": "string"}, "encabezados": TEXTOS,
                         "filas": {"type": "array", "items": TEXTOS}})
ESQUEMA_LECTURA = _objeto({
    "idea_central": TEXTOS,
    "bloques": {"type": "array", "items": _objeto({
        "subtitulo": {"type": "string"},
        "parrafos": TEXTOS,
        "ejemplo": _objeto({"titulo": {"type": "string"}, "parrafos": TEXTOS}),
        "tabla": {"anyOf": [ESQUEMA_TABLA, {"type": "null"}]},
    })},
    "aplicalo": _objeto({"parrafos": TEXTOS, "plantilla": TEXTOS}),
    "cuidado": TEXTOS,
    "pasajes": {"type": "array", "items": _objeto({
        "oracion": {"type": "string"}, "fuente": {"type": "string"},
        "ubicacion": {"type": "string"}, "texto": {"type": "string"}})},
    "decisiones": {"type": "array", "items": _objeto({
        "texto": {"type": "string"}, "tipo": {"type": "string", "enum": list(TIPOS_DE_DECISION)}})},
    "agrupacion": {"type": "string"},
})


# ---------- Diapositivas (SKILL.md, «Material 2 · Diapositivas») ----------

TIPOS_DE_TEXTO = ("frases", "ejemplo")
TIPOS_GRAFICOS = ("pasos", "columnas", "tabla", "proceso", "ciclo", "organigrama", "mapa", "matriz", "tarjetas",
                  "grafica")   # PLAN.md §0, decisión 29
TIPOS_DE_DIAPOSITIVA = TIPOS_DE_TEXTO + TIPOS_GRAFICOS
# Cuántos elementos lleva cada recurso dibujado: (mínimo, máximo).
ELEMENTOS_POR_TIPO = {"proceso": (3, 6), "ciclo": (3, 6), "organigrama": (2, 5), "mapa": (3, 6), "matriz": (4, 4),
                      "tarjetas": (2, 6), "grafica": (2, 6)}


class Notas(BaseModel):
    """Notas del profesor de cada diapositiva: qué destacar y qué preguntar al grupo."""
    destacar: str = Field(min_length=1)
    preguntar: str = Field(min_length=1)

    def texto(self) -> str:
        return f"Qué destacar: {self.destacar}\nQué preguntar al grupo: {self.preguntar}"


class Columna(BaseModel):
    titulo: str
    frases: list[str] = Field(min_length=1, max_length=5)


class Elemento(BaseModel):
    """Una pieza de un recurso dibujado: un paso del proceso, una rama del mapa, un cargo del organigrama,
    un cuadrante de la matriz, una tarjeta o una barra de la gráfica."""
    texto: str = Field(min_length=1)
    detalle: str = ""                                   # una frase corta debajo del texto
    hijos: list[str] = Field(default_factory=list, max_length=3)   # subramas o cargos que dependen de este
    valor: float | None = None                          # solo en la gráfica de barras


class Grafico(BaseModel):
    """Lo que dibuja el programa. «centro»: la idea central del mapa, el cargo de arriba del organigrama o la
    unidad de la gráfica. «ejes»: en la matriz, el eje horizontal y el vertical."""
    centro: str = ""
    elementos: list[Elemento] = Field(default_factory=list, max_length=6)
    ejes: list[str] = Field(default_factory=list, max_length=2)


class Diapositiva(BaseModel):
    """Una diapositiva de concepto. «bloque» es el subtítulo del bloque de la lectura al que pertenece:
    así el programa comprueba que las diapositivas sigan el orden de la lectura."""
    bloque: str
    titulo: str
    tipo: Literal["frases", "ejemplo", "pasos", "columnas", "tabla", "proceso", "ciclo", "organigrama", "mapa",
                  "matriz", "tarjetas", "grafica"]
    frases: list[str] = Field(default_factory=list, max_length=6)
    columnas: list[Columna] = Field(default_factory=list, max_length=2)
    tabla: Tabla | None = None
    grafico: Grafico | None = None
    notas: Notas

    @property
    def es_grafica(self) -> bool:
        return self.tipo in TIPOS_GRAFICOS

    @model_validator(mode="after")
    def segun_su_tipo(self):
        if self.tipo == "columnas" and len(self.columnas) != 2:
            raise ValueError("una diapositiva de columnas tiene dos columnas")
        if self.tipo == "tabla" and self.tabla is None:
            raise ValueError("una diapositiva de tabla necesita su tabla")
        if self.tipo in ("frases", "pasos", "ejemplo") and not self.frases:
            raise ValueError(f"una diapositiva de {self.tipo} necesita al menos una frase")
        if self.tipo in ELEMENTOS_POR_TIPO:
            minimo, maximo = ELEMENTOS_POR_TIPO[self.tipo]
            g = self.grafico
            if g is None or not minimo <= len(g.elementos) <= maximo:
                raise ValueError(f"una diapositiva de {self.tipo} lleva en «grafico» de {minimo} a {maximo} elementos")
            if self.tipo in ("mapa", "organigrama") and not g.centro.strip():
                raise ValueError(f"una diapositiva de {self.tipo} necesita «centro»")
            if self.tipo == "matriz" and len(g.ejes) != 2:
                raise ValueError("una matriz necesita sus dos ejes: el horizontal y el vertical")
            if self.tipo == "grafica" and any(e.valor is None for e in g.elementos):
                raise ValueError("cada barra de la gráfica necesita su «valor»")
        return self


class PortadaDiapositiva(BaseModel):
    notas: Notas


class IdeaCentral(BaseModel):
    frases: list[str] = Field(min_length=1, max_length=3)
    notas: Notas


class AplicaloDiapositiva(BaseModel):
    frases: list[str] = Field(default_factory=list, max_length=2)
    plantilla: list[str] = Field(min_length=1, max_length=6)
    notas: Notas


class CuidadoDiapositiva(BaseModel):
    riesgos: list[str] = Field(min_length=1, max_length=3)
    notas: Notas


class CierreDiapositiva(BaseModel):
    """La idea que se llevan: una frase de la idea central, con el docente y el contacto (decisión 29)."""
    frase: str = Field(min_length=1)
    notas: Notas


class Diapositivas(BaseModel):
    """Portada, idea central, una diapositiva por concepto, «Aplícalo así», «Cuidado con» y cierre.
    Las cinco fijas más las de concepto suman de 15 a 19 (lo comprueba el programa; decisión 29)."""
    portada: PortadaDiapositiva
    idea_central: IdeaCentral
    diapositivas: list[Diapositiva] = Field(min_length=1, max_length=20)
    aplicalo: AplicaloDiapositiva
    cuidado: CuidadoDiapositiva
    cierre: CierreDiapositiva
    pasajes: list[Pasaje] = Field(default_factory=list)       # de la lectura o de las fuentes, copiados tal cual
    decisiones: list[Decision] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.diapositivas) + FIJAS


FIJAS = 5   # portada, idea central, «Aplícalo así», «Cuidado con» y cierre


ESQUEMA_NOTAS = _objeto({"destacar": {"type": "string"}, "preguntar": {"type": "string"}})
ESQUEMA_DIAPOSITIVAS = _objeto({
    "portada": _objeto({"notas": ESQUEMA_NOTAS}),
    "idea_central": _objeto({"frases": TEXTOS, "notas": ESQUEMA_NOTAS}),
    "diapositivas": {"type": "array", "items": _objeto({
        "bloque": {"type": "string"},
        "titulo": {"type": "string"},
        "tipo": {"type": "string", "enum": list(TIPOS_DE_DIAPOSITIVA)},
        "frases": TEXTOS,
        "columnas": {"type": "array", "items": _objeto({"titulo": {"type": "string"}, "frases": TEXTOS})},
        "tabla": {"anyOf": [ESQUEMA_TABLA, {"type": "null"}]},
        "grafico": {"anyOf": [_objeto({
            "centro": {"type": "string"},
            "elementos": {"type": "array", "items": _objeto({
                "texto": {"type": "string"}, "detalle": {"type": "string"}, "hijos": TEXTOS,
                "valor": {"anyOf": [{"type": "number"}, {"type": "null"}]}})},
            "ejes": TEXTOS,
        }), {"type": "null"}]},
        "notas": ESQUEMA_NOTAS,
    })},
    "aplicalo": _objeto({"frases": TEXTOS, "plantilla": TEXTOS, "notas": ESQUEMA_NOTAS}),
    "cuidado": _objeto({"riesgos": TEXTOS, "notas": ESQUEMA_NOTAS}),
    "cierre": _objeto({"frase": {"type": "string"}, "notas": ESQUEMA_NOTAS}),
    "pasajes": ESQUEMA_LECTURA["properties"]["pasajes"],
    "decisiones": ESQUEMA_LECTURA["properties"]["decisiones"],
})
