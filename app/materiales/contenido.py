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

TIPOS_DE_TEXTO = ("frases", "ejemplo", "pasos", "columnas", "tabla")
# Solo los diagramas cuentan como recurso gráfico (PLAN.md §0, decisiones 29 y 30).
TIPOS_GRAFICOS = ("proceso", "ciclo", "organigrama", "mapa", "matriz", "tarjetas", "grafica", "cifras")
TIPOS_DE_DIAPOSITIVA = TIPOS_DE_TEXTO + TIPOS_GRAFICOS
# Cuántos elementos lleva cada recurso dibujado: (mínimo, máximo).
ELEMENTOS_POR_TIPO = {"proceso": (3, 6), "ciclo": (3, 6), "organigrama": (2, 5), "mapa": (3, 6), "matriz": (4, 4),
                      "tarjetas": (2, 6), "grafica": (2, 6), "cifras": (1, 3)}
CON_CIFRAS = ("grafica", "cifras")
MAX_PALABRAS = 30          # por diapositiva de concepto, sin el título (decisión 30)
MAX_TABLAS = 2


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
                  "matriz", "tarjetas", "grafica", "cifras"]
    frases: list[str] = Field(default_factory=list, max_length=6)
    columnas: list[Columna] = Field(default_factory=list, max_length=2)
    tabla: Tabla | None = None
    grafico: Grafico | None = None
    notas: Notas

    @property
    def es_grafica(self) -> bool:
        return self.tipo in TIPOS_GRAFICOS

    def textos_visibles(self) -> list[str]:
        """Lo que el alumno lee en la diapositiva, sin el título: para el límite de palabras."""
        textos = list(self.frases)
        for c in self.columnas:
            textos += [c.titulo, *c.frases]
        if self.tabla:
            textos += [self.tabla.titulo, *self.tabla.encabezados, *[celda for fila in self.tabla.filas for celda in fila]]
        if self.grafico:
            textos += [self.grafico.centro, *self.grafico.ejes]
            for e in self.grafico.elementos:
                textos += [e.texto, e.detalle, *e.hijos]
        return [t for t in textos if t]

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
            if self.tipo in CON_CIFRAS and any(e.valor is None for e in g.elementos):
                raise ValueError(f"cada elemento de «{self.tipo}» necesita su «valor»")
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


# ---------- Laboratorio (SKILL.md, «Material 3 · Laboratorio y archivos de práctica») ----------

Valor = str | int | float | None


class Hoja(BaseModel):
    """Una hoja de un Excel de práctica. Una celda que empieza con «=» es una fórmula."""
    nombre: str = Field(min_length=1, max_length=31)
    encabezados: list[str] = Field(min_length=1)
    filas: list[list[Valor]] = Field(default_factory=list)

    @field_validator("filas")
    @classmethod
    def mismas_columnas(cls, filas, info):
        columnas = len(info.data.get("encabezados", []))
        if any(len(f) != columnas for f in filas):
            raise ValueError("cada fila debe tener tantas celdas como encabezados")
        return filas


class Parrafo(BaseModel):
    """Un párrafo de un Word de práctica: «titulo», «texto» o «lista» (una viñeta)."""
    estilo: Literal["titulo", "texto", "lista"] = "texto"
    texto: str = Field(min_length=1)


class ArchivoPractica(BaseModel):
    """Un archivo de práctica. Su contenido lo escribe el redactor y un programa crea el archivo real."""
    nombre: str                          # S[sesión]_E[ejercicio]_[descripcion-corta].xlsx o .docx
    descripcion: str                     # lo que dice la tabla de archivos de la guía, en «Contenido»
    hojas: list[Hoja] = Field(default_factory=list)          # Excel
    parrafos: list[Parrafo] = Field(default_factory=list)    # Word
    tabla: Tabla | None = None                                # Word: una tabla después de los párrafos
    problema: str = ""                   # lo que trae a propósito; va a la guía del profesor, no a la del alumno

    @property
    def extension(self) -> str:
        return self.nombre.rsplit(".", 1)[-1].lower() if "." in self.nombre else ""


class Marca(BaseModel):
    """Lo que la figura señala en ámbar: una celda o un rango («C5», «B2:B9») o un trozo de texto del Word."""
    lugar: str = Field(min_length=1)
    numero: int | None = None


class Figura(BaseModel):
    """Una imagen hecha con un programa a partir del archivo de práctica real (SKILL.md, «Imágenes»)."""
    archivo: str
    hoja: str = ""                       # Excel: la hoja
    rango: str = ""                      # Excel: lo que se muestra, por ejemplo «A1:E8»
    marcas: list[Marca] = Field(min_length=1, max_length=4)
    descripcion: str = Field(min_length=1)   # la línea debajo de «Figura N»


class Paso(BaseModel):
    texto: str = Field(min_length=1)
    figura: Figura | None = None


class Recuadro(BaseModel):
    """Lo que el alumno copia (PLAN.md §0, decisión 33).
    - «prompt»: rol, contexto, tarea, formato de salida y restricciones.
    - «formula»: título («Fórmula 1 · Revisa si el riesgo se puede aceptar»), una línea de explicación y la fórmula.
    - «plantilla»: un texto que el alumno completa; sus espacios por llenar son el tema del ejercicio."""
    tipo: Literal["prompt", "formula", "plantilla"] = "prompt"
    titulo: str
    explicacion: str = ""
    lineas: list[str] = Field(min_length=1)


class Mejora(BaseModel):
    """«Mejora el resultado (opcional)»: un pedido de seguimiento que enseña a iterar, con sus pasos y recuadros."""
    texto: str = Field(min_length=1)
    pasos: list[str] = Field(default_factory=list, max_length=6)
    copiar: list[Recuadro] = Field(default_factory=list, max_length=2)


class AntesDeEmpezar(BaseModel):
    """Lo que comparten todos los ejercicios: el caso, la fecha de referencia, tablas y reglas (decisión 33)."""
    contexto: list[str] = Field(min_length=1, max_length=5)
    tablas: list[Tabla] = Field(default_factory=list, max_length=2)
    reglas: list[str] = Field(default_factory=list, max_length=8)


class Ejercicio(BaseModel):
    numero: int
    area: str
    titulo: str                          # con una acción concreta
    situacion: str                       # de 2 a 3 líneas que indican el área
    archivos: list[str] = Field(default_factory=list)
    pasos: list[Paso] = Field(min_length=2, max_length=20)
    copiar: list[Recuadro] = Field(default_factory=list, max_length=4)   # vacío si el alumno trabaja a mano
    mejora: Mejora


class Laboratorio(BaseModel):
    antes_de_empezar: AntesDeEmpezar
    ejercicios: list[Ejercicio] = Field(min_length=3, max_length=5)
    archivos: list[ArchivoPractica] = Field(default_factory=list)
    pasajes: list[Pasaje] = Field(default_factory=list)
    decisiones: list[Decision] = Field(default_factory=list)


_VALOR = {"anyOf": [{"type": "string"}, {"type": "number"}, {"type": "null"}]}
_ESQUEMA_RECUADRO = _objeto({"tipo": {"type": "string", "enum": ["prompt", "formula", "plantilla"]},
                             "titulo": {"type": "string"}, "explicacion": {"type": "string"}, "lineas": TEXTOS})
ESQUEMA_LABORATORIO = _objeto({
    "antes_de_empezar": _objeto({"contexto": TEXTOS, "tablas": {"type": "array", "items": ESQUEMA_TABLA},
                                 "reglas": TEXTOS}),
    "ejercicios": {"type": "array", "items": _objeto({
        "numero": {"type": "integer"},
        "area": {"type": "string"},
        "titulo": {"type": "string"},
        "situacion": {"type": "string"},
        "archivos": TEXTOS,
        "pasos": {"type": "array", "items": _objeto({
            "texto": {"type": "string"},
            "figura": {"anyOf": [_objeto({
                "archivo": {"type": "string"}, "hoja": {"type": "string"}, "rango": {"type": "string"},
                "marcas": {"type": "array", "items": _objeto({
                    "lugar": {"type": "string"}, "numero": {"anyOf": [{"type": "integer"}, {"type": "null"}]}})},
                "descripcion": {"type": "string"},
            }), {"type": "null"}]},
        })},
        "copiar": {"type": "array", "items": _ESQUEMA_RECUADRO},
        "mejora": _objeto({"texto": {"type": "string"}, "pasos": TEXTOS,
                           "copiar": {"type": "array", "items": _ESQUEMA_RECUADRO}}),
    })},
    "archivos": {"type": "array", "items": _objeto({
        "nombre": {"type": "string"},
        "descripcion": {"type": "string"},
        "hojas": {"type": "array", "items": _objeto({
            "nombre": {"type": "string"}, "encabezados": TEXTOS,
            "filas": {"type": "array", "items": {"type": "array", "items": _VALOR}}})},
        "parrafos": {"type": "array", "items": _objeto({
            "estilo": {"type": "string", "enum": ["titulo", "texto", "lista"]}, "texto": {"type": "string"}})},
        "tabla": {"anyOf": [ESQUEMA_TABLA, {"type": "null"}]},
        "problema": {"type": "string"},
    })},
    "pasajes": ESQUEMA_LECTURA["properties"]["pasajes"],
    "decisiones": ESQUEMA_LECTURA["properties"]["decisiones"],
})
