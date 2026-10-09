"""Revisor independiente (SKILL.md y PLAN.md §5.4).

1. Es una sesión nueva del SDK: no continúa la sesión del redactor.
2. Su carpeta tiene solo tres cosas: el material final con sus oraciones numeradas, el texto de las
   fuentes del curso y las dos fichas. No recibe borradores, ni la tabla de verificación, ni notas.
3. Puede listar, leer y buscar en esa carpeta. No puede escribir.
4. Recibe el pedido exacto de la skill y responde en JSON: número de oración, defecto y prueba.
5. El programa comprueba que cada prueba exista tal cual en una fuente, en una ficha o en el material.
   Un hallazgo sin prueba real se descarta: no se puede corregir ni comprobar.
"""

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from app import agente, herramientas, skill
from app.fichas import almacen, verificacion
from app.fuentes import convertir
from app.validacion import verificador
from app.validacion.pasajes import FICHA_DE_LA_SESION, FICHA_DEL_CURSO, Corpus, literal

DEFECTOS = ["vacío", "inconsistencia", "ambigüedad", "imprecisión", "relleno"]
MATERIAL = "material.txt"
ARCHIVO_FICHA_CURSO = "ficha_del_curso.md"
ARCHIVO_FICHA_SESION = "ficha_de_la_sesion.md"
CARPETA_FUENTES = "fuentes"
NOMBRES_DE_FICHA = {ARCHIVO_FICHA_CURSO: FICHA_DEL_CURSO, ARCHIVO_FICHA_SESION: FICHA_DE_LA_SESION}

ESQUEMA = {
    "type": "object",
    "properties": {"hallazgos": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "n": {"type": "integer"},
            "oracion": {"type": "string"},
            "defecto": {"type": "string", "enum": DEFECTOS},
            "prueba": {"type": "string"},
            "donde": {"type": "string"},
            "explicacion": {"type": "string"},
        },
        "required": ["n", "oracion", "defecto", "prueba", "donde", "explicacion"],
        "additionalProperties": False,
    }}},
    "required": ["hallazgos"],
    "additionalProperties": False,
}


def pedido_de_la_skill() -> str:
    """El pedido que la skill manda hacer al revisor, copiado tal cual de SKILL.md."""
    texto = skill.subseccion("Revisor independiente")
    coincidencia = re.search(r'Pídele esto: "([^"]+)"', texto)
    if coincidencia is None:
        raise KeyError("SKILL.md no tiene el pedido del revisor independiente.")
    return coincidencia.group(1)


def definiciones_de_defectos() -> str:
    texto = skill.secciones("Validación doble antes de cada entrega")
    return "\n".join(l for l in texto.splitlines()
                     if l.startswith("- ") and l[2:].split(":")[0].lower() in DEFECTOS)


# ---------- Carpeta de trabajo ----------

def preparar_carpeta(carpeta: Path, carpeta_curso: Path, sesion: int, oraciones: list[dict]) -> Path:
    """Crea la carpeta del revisor desde cero con solo el material final, las fuentes y las fichas."""
    if carpeta.exists():
        shutil.rmtree(carpeta)
    (carpeta / CARPETA_FUENTES).mkdir(parents=True)
    (carpeta / MATERIAL).write_text(texto_numerado(oraciones), encoding="utf-8")
    shutil.copyfile(almacen.ruta_ficha(carpeta_curso, "curso", extension=".md"), carpeta / ARCHIVO_FICHA_CURSO)
    shutil.copyfile(almacen.ruta_ficha(carpeta_curso, "sesion", sesion, ".md"), carpeta / ARCHIVO_FICHA_SESION)
    for archivo in verificacion.fuentes_utilizables(carpeta_curso):
        lineas = [f"[{p['ubicacion']}] {p['texto']}" for p in convertir.leer_pasajes(carpeta_curso, archivo)]
        (carpeta / CARPETA_FUENTES / f"{archivo}.txt").write_text("\n".join(lineas), encoding="utf-8")
    return carpeta


def texto_numerado(oraciones: list[dict]) -> str:
    return "\n".join(f"{o['n']}. {o['texto']}" for o in oraciones)


def _pedido(carpeta: Path) -> str:
    fuentes = sorted(r.name for r in (carpeta / CARPETA_FUENTES).iterdir())
    return "\n".join([
        "Eres un revisor independiente. No escribiste este material y no conoces a quien lo escribió.",
        "",
        pedido_de_la_skill(),
        "",
        "QUÉ SIGNIFICA CADA DEFECTO:",
        definiciones_de_defectos(),
        "",
        "TU CARPETA DE TRABAJO tiene solo esto:",
        f"- {MATERIAL}: el material final, una oración por línea con su número.",
        f"- {ARCHIVO_FICHA_CURSO} y {ARCHIVO_FICHA_SESION}: las dos fichas. Los datos del caso salen de ellas.",
        f"- {CARPETA_FUENTES}/: el texto de cada fuente del curso, con su página, lámina o celda entre corchetes:",
        *([f"  - {CARPETA_FUENTES}/{f}" for f in fuentes] or ["  - (ninguna)"]),
        "Usa leer_archivo, buscar_texto y buscar_en_fuentes para comparar cada oración con las fuentes.",
        "",
        "CÓMO RESPONDER: un elemento por hallazgo en «hallazgos».",
        "- n: el número de la oración. oracion: la oración copiada tal cual del material.",
        "- defecto: vacío, inconsistencia, ambigüedad, imprecisión o relleno.",
        "- prueba: texto copiado tal cual, de 40 palabras como máximo, que demuestra el defecto: el pasaje de la fuente",
        "  o de la ficha que la oración contradice o no dice, u otra oración del material que dice otra cosa.",
        f"- donde: el archivo de la prueba, tal como aparece en tu carpeta (por ejemplo {MATERIAL} o {ARCHIVO_FICHA_CURSO}).",
        "- explicacion: el defecto en 25 palabras como máximo.",
        "- Los títulos y rótulos no son defectos. No reportes opiniones de estilo.",
        "- Si no encuentras errores, devuelve la lista vacía.",
        "",
        f"MATERIAL ({MATERIAL}):",
        (carpeta / MATERIAL).read_text(encoding="utf-8"),
    ])


# ---------- Comprobación de las pruebas ----------

@dataclass
class Hallazgo:
    ronda: int
    n: int
    oracion: str
    defecto: str
    prueba: str
    fuente: str          # «archivo, ubicación» comprobada por el programa, o «el material»
    explicacion: str
    estado: str = "abierto"        # abierto, resuelto o rechazado
    resolucion: str = ""
    nueva: str = ""
    intentos: int = 0

    def describir(self) -> str:
        texto = (f"REVISOR INDEPENDIENTE · {self.defecto} · «{self.oracion}»: {self.explicacion} "
                 f"Prueba: «{self.prueba}» ({self.fuente}).")
        if self.intentos:
            texto += " Sigue abierto: corrígelo o recházalo con un pasaje que exista tal cual."
        return texto


@dataclass
class Resultado:
    ronda: int
    hallazgos: list[Hallazgo] = field(default_factory=list)
    descartados: list[dict] = field(default_factory=list)
    revisadas: dict[str, int] = field(default_factory=dict)   # huella → ronda


def _comparable(texto: str) -> str:
    return verificador._comparable(texto)


def _oracion(respuesta: dict, oraciones: list[dict]) -> dict | None:
    """La oración del hallazgo: por su número si el texto coincide; si no, por su texto."""
    buscada = _comparable(respuesta["oracion"])
    por_numero = next((o for o in oraciones if o["n"] == respuesta["n"]), None)
    if por_numero and buscada and (buscada in _comparable(por_numero["texto"]) or _comparable(por_numero["texto"]) in buscada):
        return por_numero
    if not buscada:
        return None
    return next((o for o in oraciones if buscada == _comparable(o["texto"])), None) or \
        next((o for o in oraciones if buscada in _comparable(o["texto"])), None)


def ubicar_prueba(prueba: str, donde: str, corpus: Corpus, oraciones: list[dict]) -> str | None:
    """Dónde está la prueba, comprobado por el programa. None si no existe tal cual."""
    texto = literal(prueba).strip(" .\"'")
    if len(texto) < 3:
        return None
    if Path(donde).name == MATERIAL or donde.strip().lower() in ("material", "el material"):
        buscada = _comparable(texto)
        return "el material" if any(buscada in _comparable(o["texto"]) for o in oraciones) else None
    nombre = NOMBRES_DE_FICHA.get(Path(donde).name, Path(donde).name.removesuffix(".txt"))
    ubicacion = corpus.ubicar(nombre, texto)
    if ubicacion:
        return f"{nombre}, {ubicacion}"
    encontrada = corpus.ubicar_en_cualquiera(texto)
    if encontrada:
        return f"{encontrada[0]}, {encontrada[1]}"
    buscada = _comparable(texto)
    return "el material" if any(buscada in _comparable(o["texto"]) for o in oraciones) else None


def comprobar(respuesta: dict, ronda: int, oraciones: list[dict], corpus: Corpus) -> Resultado:
    resultado = Resultado(ronda=ronda, revisadas={o["huella"]: ronda for o in oraciones})
    vistos = set()
    for r in respuesta["hallazgos"]:
        oracion = _oracion(r, oraciones)
        fuente = ubicar_prueba(r["prueba"], r["donde"], corpus, oraciones) if oracion else None
        if oracion is None or fuente is None:
            motivo = "La oración no está en el material." if oracion is None else "La prueba no aparece tal cual."
            resultado.descartados.append({**r, "motivo": motivo})
            continue
        if (oracion["n"], r["defecto"]) in vistos:
            continue
        vistos.add((oracion["n"], r["defecto"]))
        resultado.hallazgos.append(Hallazgo(
            ronda=ronda, n=oracion["n"], oracion=oracion["texto"], defecto=r["defecto"],
            prueba=literal(r["prueba"]).strip(), fuente=fuente, explicacion=r["explicacion"].strip()))
    return resultado


async def ejecutar(oraciones: list[dict], *, ronda: int, carpeta: Path, carpeta_curso: Path, curso: str,
                   sesion: int, material: str, consulta=agente.query) -> Resultado:
    """oraciones: las filas del verificador sobre el archivo final (n, huella, texto)."""
    preparar_carpeta(carpeta, carpeta_curso, sesion, oraciones)
    corpus = Corpus.del_curso(carpeta_curso, sesion)
    servidor, _ = herramientas.servidor_del_revisor(carpeta, corpus)
    respuesta = await agente.consultar(
        _pedido(carpeta), tarea="revisor", esquema=ESQUEMA, curso=curso, etapa=f"revisor independiente {ronda}",
        sesion=f"S{sesion}", material=material, cwd=carpeta, herramientas=herramientas.HERRAMIENTAS_REVISOR,
        servidores={herramientas.SERVIDOR_REVISOR: servidor}, consulta=consulta)
    return comprobar(respuesta, ronda, oraciones, corpus)
