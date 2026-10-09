"""Contenido de cada material como datos estructurados.

El agente redactor escribe estos datos. Los generadores de archivos los convierten en Word,
PowerPoint, Excel o HTML con el mismo diseño (CLAUDE.md: el agente no escribe Word a mano).
"""

from pydantic import BaseModel, Field, field_validator


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
    fuente: str
    ubicacion: str
    texto: str


class Lectura(BaseModel):
    idea_central: list[str] = Field(min_length=1, max_length=3)
    bloques: list[Bloque] = Field(min_length=2, max_length=4)
    aplicalo: Aplicalo
    cuidado: list[str] = Field(min_length=1, max_length=3)
    pasajes: list[Pasaje] = Field(default_factory=list)       # pasajes copiados de las fuentes antes de redactar
    decisiones: list[str] = Field(default_factory=list)       # lo que las fichas no definían
    agrupacion: str = ""                                       # si hubo más temas que bloques, cómo se agruparon


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
        "fuente": {"type": "string"}, "ubicacion": {"type": "string"}, "texto": {"type": "string"}})},
    "decisiones": TEXTOS,
    "agrupacion": {"type": "string"},
})
