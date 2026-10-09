"""Primera pasada · Veracidad, oración por oración (SKILL.md y PLAN.md §5.2).

1. El programa elige para cada oración los tres pasajes más parecidos de las fuentes y las fichas.
2. La IA recibe grupos de unas 20 oraciones con sus pasajes y da a cada una un tipo, el pasaje
   copiado tal cual, su fuente y un veredicto. En las normas compara siete cosas, una por una.
3. El programa comprueba que cada pasaje exista tal cual y pone la ubicación real.
   Si no existe, la oración queda «sin fuente».
4. Sin IA: los títulos son «sin afirmación»; una regla del curso debe decir «en este curso».
Las oraciones que no cambiaron conservan su resultado anterior (SPEC §9).
"""

from dataclasses import dataclass, field

from app import agente, herramientas, skill
from app.validacion.pasajes import FICHA_DE_LA_SESION, FICHA_DEL_CURSO, Corpus, literal, normal

TIPOS = ["norma", "dato del caso", "cálculo", "regla del curso", "instrucción", "sin afirmación"]
VEREDICTOS = ["coincide", "no coincide", "sin fuente"]
COMPARACIONES = ["numero", "termino", "cantidades", "orden", "quien", "obligacion", "generalizacion"]
NO_APLICA = "no aplica"
FICHAS = (FICHA_DEL_CURSO, FICHA_DE_LA_SESION)
TAMANO_GRUPO = 40
PALABRAS_MINIMAS_PARA_APROBAR_SIN_IA = 5

ESQUEMA = {
    "type": "object",
    "properties": {"oraciones": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "n": {"type": "integer"},
            "tipo": {"type": "string", "enum": TIPOS},
            "fuente": {"type": "string"},
            "pasaje": {"type": "string"},
            "veredicto": {"type": "string", "enum": VEREDICTOS},
            "motivo": {"type": "string"},
            "comparacion": {
                "type": "object",
                "properties": {c: {"type": "string", "enum": ["igual", "distinto", NO_APLICA]} for c in COMPARACIONES},
                "required": COMPARACIONES, "additionalProperties": False,
            },
        },
        "required": ["n", "tipo", "fuente", "pasaje", "veredicto", "motivo"],
        "additionalProperties": False,
    }}},
    "required": ["oraciones"],
    "additionalProperties": False,
}

INSTRUCCIONES = f"""
Para cada oración devuelve:
- tipo: uno solo de {", ".join(TIPOS)}.
- fuente y pasaje: el pasaje copiado tal cual, en su idioma original, y el nombre exacto de su fuente
  (un archivo de la lista, «ficha del curso» o «ficha de la sesión»). Encuéntralo entre los candidatos
  o con la herramienta buscar_en_fuentes. No lo escribas de memoria. Copia solo palabras que están en la fuente.
  Copia solo el fragmento que sostiene la oración, de 40 palabras como máximo, sin cortar palabras.
- veredicto: coincide, no coincide o sin fuente.
- motivo: 12 palabras como máximo.
- comparacion: SOLO en el tipo norma, compara una por una las siete cosas con «igual», «distinto» o «no aplica»:
  numero (de cláusula o de control), termino (el nombre del término), cantidades, orden, quien (hace la acción),
  obligacion («debe» o «puede») y generalizacion («todos», «solo», «siempre», «las mismas»).
  Una sola diferencia es «no coincide». En los demás tipos, no escribas «comparacion».
Reglas por tipo:
- Norma: el pasaje sale de una fuente del curso, nunca de una ficha. Si la oración dice «en este curso» porque
  resume, agrupa o reordena la norma, compárala igual con su pasaje: coincide si no agrega ni contradice nada.
- Dato del caso: el pasaje es la línea de la ficha que contiene el dato. Si ninguna ficha lo contiene, es «sin fuente».
- Regla del curso: es una regla que ninguna fuente dice. La oración debe decir «en este curso». Deja el pasaje vacío.
- Instrucción: el pasaje es la línea de la ficha de la que sale. Si no sale de ninguna, deja el pasaje vacío.
- Sin afirmación: títulos, rótulos y oraciones que no afirman nada. Deja el pasaje vacío.
"""


@dataclass
class Resultado:
    filas: dict[str, dict] = field(default_factory=dict)       # huella → fila de la pasada
    enviadas_a_la_ia: int = 0
    aprobadas_por_programa: int = 0
    pasajes_fuera_de_candidatos: int = 0
    busquedas: int = 0

    def problemas(self, oraciones: list[dict]) -> list[dict]:
        return [{**o, **self.filas[o["huella"]]} for o in oraciones
                if o["huella"] in self.filas and self.filas[o["huella"]]["veredicto"] != "coincide"]


def fila_sin_afirmacion(motivo: str = "Título o rótulo.") -> dict:
    return {"tipo": "sin afirmación", "pasaje": NO_APLICA, "fuente": "", "veredicto": "coincide", "motivo": motivo}


def _pedido(grupo: list[dict], candidatos: dict[int, list[dict]], fuentes: list[str]) -> str:
    bloques = []
    for o in grupo:
        lineas = [f"[{o['n']}] Sección: {o['seccion']} | Oración: {o['texto']}", "  Candidatos:"]
        lineas += [f"  - ({c['fuente']} · {c['ubicacion']}) {c['texto']}" for c in candidatos[o["n"]]] or ["  - (ninguno)"]
        bloques.append("\n".join(lineas))
    return "\n".join([
        "Revisa la veracidad de cada oración de este material, como dice la skill:",
        skill.subseccion("Primera pasada · Veracidad"),
        INSTRUCCIONES,
        "Fuentes disponibles: " + ", ".join(fuentes),
        "",
        "ORACIONES:",
        "\n\n".join(bloques),
    ])


def _revisar(o: dict, respuesta: dict, corpus: Corpus, candidatos: list[dict],
             instruccion_sin_ejecucion: str, resultado: Resultado) -> dict:
    """Comprobaciones del programa sobre lo que dijo la IA."""
    tipo, veredicto, motivo = respuesta["tipo"], respuesta["veredicto"], respuesta["motivo"]
    pasaje, fuente = respuesta["pasaje"].strip(), respuesta["fuente"].strip()

    if tipo == "sin afirmación":
        return fila_sin_afirmacion(motivo)
    if tipo == "regla del curso":
        if "en este curso" in normal(o["texto"]):
            return {"tipo": tipo, "pasaje": "Regla propia del curso: la oración dice «en este curso».",
                    "fuente": "", "veredicto": "coincide", "motivo": motivo}
        return {"tipo": tipo, "pasaje": "Regla propia del curso sin «en este curso».", "fuente": "",
                "veredicto": "no coincide", "motivo": "Una regla propia del curso debe decir «en este curso»."}
    if tipo == "instrucción" and not pasaje and instruccion_sin_ejecucion:
        return {"tipo": tipo, "pasaje": instruccion_sin_ejecucion, "fuente": "", "veredicto": "coincide", "motivo": motivo}

    if veredicto != "sin fuente" or pasaje:
        ubicacion = corpus.ubicar(fuente, pasaje) if pasaje else None
        if ubicacion is None and pasaje:
            otra = corpus.ubicar_en_cualquiera(pasaje)
            if otra:
                fuente, ubicacion = otra
        if ubicacion is None:
            return {"tipo": tipo, "pasaje": pasaje or "(sin pasaje)", "fuente": fuente, "veredicto": "sin fuente",
                    "motivo": "El pasaje no aparece tal cual en ninguna fuente ni ficha."}
        if tipo == "norma" and fuente in FICHAS:
            return {"tipo": tipo, "pasaje": pasaje, "fuente": f"{fuente}, {ubicacion}", "veredicto": "sin fuente",
                    "motivo": "Una norma se compara con una fuente del curso, no con una ficha."}
        if not any(literal(pasaje).casefold() in literal(c["texto"]).casefold() or
                   literal(c["texto"]).casefold() in literal(pasaje).casefold() for c in candidatos):
            resultado.pasajes_fuera_de_candidatos += 1
        fuente = f"{fuente}, {ubicacion}"

    if tipo == "norma" and veredicto == "coincide":
        comparacion = respuesta.get("comparacion")
        if not comparacion:
            return {"tipo": tipo, "pasaje": pasaje, "fuente": fuente, "veredicto": "no coincide",
                    "motivo": "Faltó comparar la oración con la norma en sus siete puntos."}
        distintas = [c for c, v in comparacion.items() if v == "distinto"]
        if distintas:
            veredicto = "no coincide"
            motivo = f"Difiere de la fuente en: {', '.join(distintas)}. {motivo}"
    if veredicto == "sin fuente":
        pasaje = pasaje or "(sin pasaje)"
    return {"tipo": tipo, "pasaje": pasaje, "fuente": fuente, "veredicto": veredicto, "motivo": motivo}


def aprobar_sin_ia(o: dict, corpus: Corpus) -> dict | None:
    """Una oración escrita tal cual en una fuente coincide con ella: el programa la aprueba sin IA.
    Si está tal cual en una fuente del curso, es una norma; si está en una ficha, es un dato del caso."""
    texto = o["texto"].strip()
    if len(texto.split()) < PALABRAS_MINIMAS_PARA_APROBAR_SIN_IA:
        return None
    encontrada = corpus.ubicar_en_cualquiera(texto)
    if encontrada is None:
        return None
    fuente, ubicacion = encontrada
    tipo = "dato del caso" if fuente in FICHAS else "norma"
    return {"tipo": tipo, "pasaje": texto.rstrip("."), "fuente": f"{fuente}, {ubicacion}", "veredicto": "coincide",
            "motivo": "Está escrita tal cual en la fuente; lo comprobó el programa."}


def _candidato_de_ancla(o: dict, anclas: list[dict], corpus: Corpus) -> dict | None:
    """El pasaje que el redactor dijo usar para esta oración, si existe tal cual en la fuente."""
    texto = normal(o["texto"]).strip(" .")
    for ancla in anclas:
        propia = normal(ancla.get("oracion", "")).strip(" .")
        if propia and (propia in texto or texto in propia):
            ubicacion = corpus.ubicar(ancla["fuente"], ancla["texto"])
            fuente = ancla["fuente"]
            if ubicacion is None:
                encontrada = corpus.ubicar_en_cualquiera(ancla["texto"])
                if encontrada is None:
                    continue   # el pasaje que dijo el redactor no existe tal cual: no se usa
                fuente, ubicacion = encontrada
            return {"fuente": fuente, "ubicacion": ubicacion, "texto": ancla["texto"], "parecido": 100}
    return None


async def ejecutar(oraciones: list[dict], *, titulos: set[str], corpus: Corpus, anteriores: dict,
                   curso: str, sesion: int, material: str, instruccion_sin_ejecucion: str = "",
                   anclas: list[dict] | None = None, consulta=agente.query) -> Resultado:
    """oraciones: las filas del verificador (con n, huella, sección y texto).
    anteriores: resultados guardados por huella; las oraciones sin cambios no van a la IA."""
    resultado = Resultado()
    pendientes = []
    for o in oraciones:
        if o["huella"] in anteriores:
            resultado.filas[o["huella"]] = anteriores[o["huella"]]
        elif o["texto"].strip() in titulos or o["seccion"].endswith(("· inicio", "· encabezado y pie")):
            resultado.filas[o["huella"]] = fila_sin_afirmacion()
        elif (literal := aprobar_sin_ia(o, corpus)) is not None:
            resultado.filas[o["huella"]] = literal
            resultado.aprobadas_por_programa += 1
        else:
            pendientes.append(o)
    if not pendientes:
        return resultado

    servidor, uso = herramientas.servidor_de_busqueda(corpus)
    fuentes = list(corpus.fuentes)
    for inicio in range(0, len(pendientes), TAMANO_GRUPO):
        grupo = pendientes[inicio:inicio + TAMANO_GRUPO]
        candidatos = {}
        for o in grupo:
            buscados = corpus.buscar(o["texto"])
            ancla = _candidato_de_ancla(o, anclas or [], corpus)
            candidatos[o["n"]] = ([ancla] + [c for c in buscados if c["texto"] != ancla["texto"]][:2]) if ancla else buscados
        respuesta = await agente.consultar(
            _pedido(grupo, candidatos, fuentes), tarea="pasada1", esquema=ESQUEMA, curso=curso,
            etapa="primera pasada", sesion=f"S{sesion}", material=material,
            herramientas=(herramientas.BUSCAR,), servidores={herramientas.SERVIDOR: servidor}, consulta=consulta,
        )
        por_numero = {r["n"]: r for r in respuesta["oraciones"]}
        for o in grupo:
            if o["n"] in por_numero:
                fila = _revisar(o, por_numero[o["n"]], corpus, candidatos[o["n"]], instruccion_sin_ejecucion, resultado)
            else:
                fila = {"tipo": "sin afirmación", "pasaje": "(sin revisar)", "fuente": "", "veredicto": "sin fuente",
                        "motivo": "La IA no devolvió esta oración."}
            resultado.filas[o["huella"]] = fila
        resultado.enviadas_a_la_ia += len(grupo)
    resultado.busquedas = uso["busquedas"]
    return resultado
