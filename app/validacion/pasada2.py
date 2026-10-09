"""Segunda pasada · Valor y funcionamiento (SKILL.md y PLAN.md §5.3).

1. El programa lista cifras, fechas, nombres propios y términos con sus oraciones (hoja «Datos
   repetidos», la escribe el verificador) y marca las palabras que aparecen con dos cifras distintas.
2. La IA responde las cuatro preguntas de la skill por cada bloque que cambió (hoja «Segunda pasada»),
   juzga las posibles inconsistencias y repasa la lista de verificación.
3. El programa comprueba que cada defecto cite una oración que existe en el material.
Una sola llamada por vuelta. Los bloques que no cambiaron conservan sus respuestas.
"""

import hashlib
from dataclasses import dataclass, field

from app import agente, skill
from app.validacion import verificador
from app.validacion.pasajes import literal

DEFECTOS = ["vacío", "inconsistencia", "ambigüedad", "relleno"]
RESPUESTAS_LISTA = ["sí", "no", "no aplica"]
PREGUNTAS = ["¿Qué puede hacer el alumno con esto?", "¿Qué dato necesita y dónde está?",
             "¿Qué oración tiene dos lecturas?", "¿Qué decide si el caso no sale como el ejemplo?"]
CAMPOS = ["que_puede_hacer", "que_necesita", "dos_lecturas", "si_no_sale"]

ESQUEMA = {
    "type": "object",
    "properties": {
        "bloques": {"type": "array", "items": {
            "type": "object",
            "properties": {"bloque": {"type": "string"}, **{c: {"type": "string"} for c in CAMPOS}},
            "required": ["bloque", *CAMPOS], "additionalProperties": False,
        }},
        "defectos": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "tipo": {"type": "string", "enum": DEFECTOS},
                "bloque": {"type": "string"},
                "oracion": {"type": "string"},
                "detalle": {"type": "string"},
            },
            "required": ["tipo", "bloque", "oracion", "detalle"], "additionalProperties": False,
        }},
        "lista": {"type": "array", "items": {
            "type": "object",
            "properties": {"pregunta": {"type": "string"}, "respuesta": {"type": "string", "enum": RESPUESTAS_LISTA},
                           "detalle": {"type": "string"}},
            "required": ["pregunta", "respuesta", "detalle"], "additionalProperties": False,
        }},
    },
    "required": ["bloques", "defectos", "lista"],
    "additionalProperties": False,
}


@dataclass
class Bloque:
    nombre: str
    oraciones: list[str]

    @property
    def huella(self) -> str:
        return hashlib.sha256("\n".join(self.oraciones).encode("utf-8")).hexdigest()[:16]


@dataclass
class Resultado:
    respuestas: dict[str, dict] = field(default_factory=dict)   # bloque → respuestas a las cuatro preguntas
    defectos: list[dict] = field(default_factory=list)
    lista_no: list[dict] = field(default_factory=list)
    revisados: list[str] = field(default_factory=list)
    descartados: int = 0

    def guardar(self, bloques: list[Bloque]) -> dict:
        """Lo que se conserva para la próxima vuelta: solo los bloques sin defectos."""
        con_defecto = {d["bloque"] for d in self.defectos}
        return {b.nombre: {"huella": b.huella, "respuestas": self.respuestas[b.nombre]}
                for b in bloques if b.nombre in self.respuestas and b.nombre not in con_defecto}

    def filas_excel(self, bloques: list[Bloque]) -> list[list[str]]:
        return [[b.nombre, *[self.respuestas.get(b.nombre, {}).get(c, "") for c in CAMPOS]] for b in bloques]


def posibles_inconsistencias(bloques: list[Bloque]) -> list[str]:
    """Palabras que siguen a dos cifras distintas en el material, para que la IA decida si son el mismo dato."""
    textos = [(b.nombre, o) for b in bloques for o in b.oraciones]
    lineas = []
    for unidad, valores in verificador.verificar.unidades_con_cifras(textos).items():
        if len(valores) > 1:
            detalle = "; ".join(f"«{cifra} {unidad}» en: {' | '.join(lista[:2])}" for cifra, lista in valores.items())
            lineas.append(f"- {unidad}: {detalle}")
    return lineas


def _lista_de_verificacion() -> list[str]:
    return [l[2:].strip() for l in skill.secciones("Lista de verificación").splitlines() if l.startswith("- ")]


def _pedido(bloques: list[Bloque], a_revisar: list[Bloque], contexto_fijo: str, inconsistencias: list[str],
            material: str) -> str:
    texto = "\n\n".join(f"[{b.nombre}]\n" + "\n".join(b.oraciones) for b in bloques)
    return "\n".join([
        contexto_fijo,
        "SEGUNDA PASADA, como dice la skill:",
        skill.subseccion("Segunda pasada · Valor y funcionamiento"),
        "LISTA DE VERIFICACIÓN:",
        *[f"- {p}" for p in _lista_de_verificacion()],
        "",
        "CÓMO RESPONDER",
        "- bloques: solo los bloques de la lista «BLOQUES A REVISAR», con las cuatro respuestas.",
        "  Cada respuesta, 25 palabras como máximo. Si no hay oración con dos lecturas, escribe «Ninguna».",
        "- defectos: cada relleno, vacío, ambigüedad o inconsistencia, solo en los bloques a revisar.",
        "  «oracion» es la oración del material copiada tal cual. En un vacío, es la oración después de la cual",
        "  falta lo que necesita el alumno. «detalle»: qué falta o cuáles son las dos lecturas, en 25 palabras como máximo.",
        "  No reportes opiniones de estilo. Solo lo que le impide al alumno entender o actuar.",
        "- La cuarta pregunta (qué decide el alumno si el caso no sale como el ejemplo) se aplica a las instrucciones",
        "  y pasos que el alumno ejecuta. Un ejemplo ilustra una idea: no es un vacío que no cubra otros casos.",
        "- lista: cada pregunta de la lista de verificación con «sí», «no» o «no aplica». «no» solo si encontraste",
        f"  el problema en los bloques a revisar de este material ({material}). Lo que es de otros materiales es «no aplica».",
        "  Si el problema ya está en «defectos», responde «sí»: no lo repitas. «no» es para lo que no se puede señalar",
        "  en una sola oración. Juntar dos sujetos con «y» no es tener dos ideas.",
        "",
        "POSIBLES INCONSISTENCIAS que encontró el programa (decide si son el mismo dato con dos valores):",
        *(inconsistencias or ["- Ninguna."]),
        "",
        f"MATERIAL ({material}), por bloques:",
        texto,
        "",
        "BLOQUES A REVISAR: " + ", ".join(f"[{b.nombre}]" for b in a_revisar),
    ])


def _existe(oracion: str, bloques: list[Bloque]) -> bool:
    buscada = verificador._comparable(oracion)
    return bool(buscada) and any(buscada in verificador._comparable(o) or verificador._comparable(o) in buscada
                                 for b in bloques for o in b.oraciones)


async def ejecutar(bloques: list[Bloque], *, anteriores: dict, contexto_fijo: str, curso: str, sesion: int,
                   material: str, consulta=agente.query) -> Resultado:
    resultado = Resultado()
    a_revisar = []
    for b in bloques:
        guardado = anteriores.get(b.nombre)
        if guardado and guardado["huella"] == b.huella:
            resultado.respuestas[b.nombre] = guardado["respuestas"]
        else:
            a_revisar.append(b)
    if not a_revisar:
        return resultado

    respuesta = await agente.consultar(
        _pedido(bloques, a_revisar, contexto_fijo, posibles_inconsistencias(bloques), material),
        tarea="pasada2", esquema=ESQUEMA, curso=curso, etapa="segunda pasada", sesion=f"S{sesion}",
        material=material.lower(), consulta=consulta)

    nombres = {b.nombre for b in a_revisar}
    for fila in respuesta["bloques"]:
        nombre = fila["bloque"].strip("[] ")
        if nombre in nombres:
            resultado.respuestas[nombre] = {c: fila[c] for c in CAMPOS}
    for b in a_revisar:
        resultado.respuestas.setdefault(b.nombre, {c: "(sin respuesta)" for c in CAMPOS})
    for defecto in respuesta["defectos"]:
        nombre = defecto["bloque"].strip("[] ")
        if nombre in nombres and _existe(defecto["oracion"], bloques):
            resultado.defectos.append({**defecto, "bloque": nombre, "oracion": literal(defecto["oracion"])})
        else:
            resultado.descartados += 1   # sin una oración real del material no se puede corregir ni comprobar
    resultado.lista_no = [p for p in respuesta["lista"] if p["respuesta"] == "no"]
    resultado.revisados = sorted(nombres)
    return resultado
