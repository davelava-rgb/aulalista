"""Revisión del contenido, por bloque (PLAN.md §0, decisión 22).

Es la segunda de las dos pasadas. La primera es el verificador, sin IA.

1. El programa elige, para cada bloque del material, los pasajes de las fuentes y de las fichas más parecidos
   a sus oraciones, y los del redactor.
2. Una sola llamada a la IA lee los bloques con sus pasajes y reporta solo errores reales: lo que contradice
   la fuente, un dato inventado, un vacío, una ambigüedad o una inconsistencia. Decir lo mismo con otras
   palabras nunca es un error.
3. El programa comprueba cada error: la oración tiene que estar en el bloque, y la prueba de una contradicción
   o de una inconsistencia tiene que existir en una fuente, en una ficha o en el mismo material.
   Un error sin prueba real se descarta.

Después de una corrección, la revisión se repite solo en los bloques que cambiaron.
"""

from dataclasses import dataclass, field

from app import agente, herramientas
from app.validacion import pasada2, verificador
from app.validacion.pasajes import Corpus, literal

TIPOS = ["contradice la fuente", "dato inventado", "vacío", "ambigüedad", "inconsistencia"]
CON_PRUEBA = ("contradice la fuente", "inconsistencia")   # la prueba se comprueba con un programa
PASAJES_POR_BLOQUE = 12

ESQUEMA = {
    "type": "object",
    "properties": {"errores": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "bloque": {"type": "string"},
            "oracion": {"type": "string"},
            "tipo": {"type": "string", "enum": TIPOS},
            "explicacion": {"type": "string"},
            "prueba": {"type": "string"},
            "donde": {"type": "string"},
        },
        "required": ["bloque", "oracion", "tipo", "explicacion", "prueba", "donde"],
        "additionalProperties": False,
    }}},
    "required": ["errores"],
    "additionalProperties": False,
}

REGLAS = f"""QUÉ ES UN ERROR (solo estos cinco tipos):
- contradice la fuente: la oración dice algo distinto de lo que dice su fuente. Cambia una cifra o una cantidad,
  cambia «debe» por «puede», o afirma lo contrario.
- dato inventado: la oración afirma algo sobre el contenido de una fuente que ninguna fuente dice, o un dato del
  caso que no está en las fichas y que contradice o cambia lo que ellas dicen.
- vacío: falta algo que el alumno necesita para entender o aplicar el bloque, y no está en ninguna otra oración.
- ambigüedad: una oración se puede entender de dos maneras distintas. Escribe las dos lecturas en «explicacion».
- inconsistencia: el mismo dato aparece con dos valores en el material, o con un valor distinto al de las fichas.

QUÉ NO ES UN ERROR:
- Decir lo mismo que la fuente con otras palabras, con sinónimos, en otro orden o en un resumen.
- Un ejemplo ficticio del caso que no contradice las fichas.
- Una regla que dice «en este curso»: es del curso, no de una fuente.
- El estilo, una preferencia o una mejora posible. Si dudas, no lo reportes.

CÓMO RESPONDER: un elemento por error en «errores». Si no hay errores, devuelve la lista vacía.
- bloque: el nombre del bloque, tal como aparece entre corchetes.
- oracion: la oración copiada tal cual del bloque. En un vacío, la oración que va antes de lo que falta.
- tipo: uno de {", ".join(TIPOS)}.
- explicacion: el error en 25 palabras como máximo.
- prueba y donde: en «contradice la fuente» y en «inconsistencia», el texto que lo demuestra, copiado de un pasaje,
  de las fichas o de otra oración del material, y dónde está (el nombre de la fuente, «ficha del curso»,
  «ficha de la sesión» o «el material»). En los demás tipos, deja los dos vacíos.
- Puedes usar la herramienta buscar_en_fuentes si necesitas un pasaje que no está en la lista."""


@dataclass
class Error:
    bloque: str
    oracion: str
    tipo: str
    explicacion: str
    prueba: str = ""
    fuente: str = ""       # «fuente, ubicación» comprobada por el programa, o «el material»
    estado: str = "abierto"   # abierto, corregido o pendiente
    resolucion: str = ""

    def describir(self) -> str:
        texto = f"REVISIÓN · {self.tipo} · «{self.oracion}»: {self.explicacion}"
        if self.prueba:
            texto += f" Prueba: «{self.prueba}» ({self.fuente})."
        return texto


@dataclass
class Resultado:
    errores: list[Error] = field(default_factory=list)
    descartados: list[dict] = field(default_factory=list)
    bloques: list[str] = field(default_factory=list)   # los bloques que se revisaron


def _comparable(texto: str) -> str:
    return verificador._comparable(texto)


def pasajes_del_bloque(bloque: pasada2.Bloque, corpus: Corpus, anclas: list[dict]) -> list[dict]:
    """Los pasajes del redactor para las oraciones del bloque y los más parecidos de las fuentes y las fichas."""
    elegidos, vistos = [], set()

    def agregar(p):
        clave = (p["fuente"], p["texto"][:80])
        if clave not in vistos and len(elegidos) < PASAJES_POR_BLOQUE:
            vistos.add(clave)
            elegidos.append(p)

    textos = {_comparable(o) for o in bloque.oraciones}
    for ancla in anclas:
        propia = _comparable(ancla.get("oracion", ""))
        if propia and any(propia in t or t in propia for t in textos):
            ubicacion = corpus.ubicar(ancla.get("fuente", ""), ancla.get("texto", ""))
            if ubicacion:
                agregar({"fuente": ancla["fuente"], "ubicacion": ubicacion, "texto": ancla["texto"]})
    for oracion in bloque.oraciones:
        for p in corpus.buscar(oracion, 2):
            agregar(p)
    return elegidos


def _pedido(bloques: list[pasada2.Bloque], corpus: Corpus, anclas: list[dict], material: str) -> str:
    partes = [
        f"Revisa el contenido de este material ({material}) bloque por bloque. Lo escribió otra persona.",
        "Compara cada bloque con sus pasajes de las fuentes y de las fichas.",
        "",
        REGLAS,
        "",
        "POSIBLES INCONSISTENCIAS que encontró el programa (decide si son el mismo dato con dos valores):",
        *(pasada2.posibles_inconsistencias(bloques) or ["- Ninguna."]),
    ]
    for bloque in bloques:
        partes += ["", f"[{bloque.nombre}]", *bloque.oraciones, "Pasajes de las fuentes y de las fichas:"]
        partes += [f"- ({p['fuente']} · {p['ubicacion']}) {p['texto']}"
                   for p in pasajes_del_bloque(bloque, corpus, anclas)] or ["- (ninguno)"]
    return "\n".join(partes)


def ubicar_prueba(prueba: str, corpus: Corpus, bloques: list[pasada2.Bloque]) -> str | None:
    """Dónde está la prueba: «fuente, ubicación» si está en una fuente o en una ficha, «el material» si es otra
    oración del material, o None si no existe."""
    encontrada = corpus.ubicar_en_cualquiera(prueba)
    if encontrada:
        return f"{encontrada[0]}, {encontrada[1]}"
    buscada = _comparable(prueba)
    if buscada and any(buscada in _comparable(o) for b in bloques for o in b.oraciones):
        return "el material"
    return None


def comprobar(respuesta: dict, bloques: list[pasada2.Bloque], corpus: Corpus) -> Resultado:
    resultado = Resultado(bloques=[b.nombre for b in bloques])
    por_nombre = {b.nombre: b for b in bloques}
    vistos = set()
    for r in respuesta.get("errores", []):
        bloque = por_nombre.get(r["bloque"].strip("[] "))
        buscada = _comparable(r["oracion"])
        oracion = None
        candidatos = bloque.oraciones if bloque else [o for b in bloques for o in b.oraciones]
        if buscada:
            oracion = next((o for o in candidatos if buscada == _comparable(o)), None) or \
                next((o for o in candidatos if buscada in _comparable(o) or _comparable(o) in buscada), None)
        if oracion is None:
            resultado.descartados.append({**r, "motivo": "La oración no está en el material."})
            continue
        if bloque is None:
            bloque = next(b for b in bloques if oracion in b.oraciones)
        fuente = ""
        prueba = literal(r["prueba"]).strip()
        if r["tipo"] in CON_PRUEBA:
            fuente = ubicar_prueba(prueba, corpus, bloques) if prueba else None
            if fuente is None:
                resultado.descartados.append({**r, "motivo": "La prueba no existe en las fuentes, las fichas ni el material."})
                continue
        if (oracion, r["tipo"]) in vistos:
            continue
        vistos.add((oracion, r["tipo"]))
        resultado.errores.append(Error(bloque=bloque.nombre, oracion=oracion, tipo=r["tipo"],
                                       explicacion=r["explicacion"].strip(),
                                       prueba=prueba if fuente else "", fuente=fuente or ""))
    return resultado


async def ejecutar(bloques: list[pasada2.Bloque], *, corpus: Corpus, anclas: list[dict] | None = None,
                   curso: str, sesion: int, material: str, nombre_material: str, etapa: str,
                   consulta=agente.query) -> Resultado:
    """Revisa los bloques en una sola llamada. Sin bloques, no llama a la IA."""
    if not bloques:
        return Resultado()
    servidor, _ = herramientas.servidor_de_busqueda(corpus)
    respuesta = await agente.consultar(
        _pedido(bloques, corpus, anclas or [], nombre_material), tarea="revision", esquema=ESQUEMA, curso=curso,
        etapa=etapa, sesion=f"S{sesion}", material=material,
        herramientas=(herramientas.BUSCAR,), servidores={herramientas.SERVIDOR: servidor}, consulta=consulta)
    return comprobar(respuesta, bloques, corpus)
