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

TIPOS_DE_DIAPOSITIVA = ("frases", "pasos", "columnas", "tabla", "ejemplo")


class Notas(BaseModel):
    """Notas del profesor de cada diapositiva: qué destacar y qué preguntar al grupo."""
    destacar: str = Field(min_length=1)
    preguntar: str = Field(min_length=1)

    def texto(self) -> str:
        return f"Qué destacar: {self.destacar}\nQué preguntar al grupo: {self.preguntar}"


class Columna(BaseModel):
    titulo: str
    frases: list[str] = Field(min_length=1, max_length=5)


class Diapositiva(BaseModel):
    """Una diapositiva de concepto. «bloque» es el subtítulo del bloque de la lectura al que pertenece:
    así el programa comprueba que las diapositivas sigan el orden de la lectura."""
    bloque: str
    titulo: str
    tipo: Literal["frases", "pasos", "columnas", "tabla", "ejemplo"]
    frases: list[str] = Field(default_factory=list, max_length=6)
    columnas: list[Columna] = Field(default_factory=list, max_length=2)
    tabla: Tabla | None = None
    notas: Notas

    @model_validator(mode="after")
    def segun_su_tipo(self):
        if self.tipo == "columnas" and len(self.columnas) != 2:
            raise ValueError("una diapositiva de columnas tiene dos columnas")
        if self.tipo == "tabla" and self.tabla is None:
            raise ValueError("una diapositiva de tabla necesita su tabla")
        if self.tipo in ("frases", "pasos", "ejemplo") and not self.frases:
            raise ValueError(f"una diapositiva de {self.tipo} necesita al menos una frase")
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


class Diapositivas(BaseModel):
    """Portada, idea central, una diapositiva por concepto y cierre con «Aplícalo así» y «Cuidado con».
    Las cuatro fijas más las de concepto suman de 14 a 18 (lo comprueba el programa)."""
    portada: PortadaDiapositiva
    idea_central: IdeaCentral
    diapositivas: list[Diapositiva] = Field(min_length=1, max_length=20)
    aplicalo: AplicaloDiapositiva
    cuidado: CuidadoDiapositiva
    pasajes: list[Pasaje] = Field(default_factory=list)       # de la lectura o de las fuentes, copiados tal cual
    decisiones: list[Decision] = Field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.diapositivas) + 4


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
        "notas": ESQUEMA_NOTAS,
    })},
    "aplicalo": _objeto({"frases": TEXTOS, "plantilla": TEXTOS, "notas": ESQUEMA_NOTAS}),
    "cuidado": _objeto({"riesgos": TEXTOS, "notas": ESQUEMA_NOTAS}),
    "pasajes": ESQUEMA_LECTURA["properties"]["pasajes"],
    "decisiones": ESQUEMA_LECTURA["properties"]["decisiones"],
})
