"""Material 1 · Lectura: redacción, Word, validación completa y entrega (etapas 5a a 5d).

Flujo:
1. Comprueba que las dos fichas estén confirmadas.
2. El agente copia de las fuentes los pasajes que va a usar y redacta a partir de ellos.
3. El generador crea el Word con el diseño común.
4. Ciclo de corrección (PLAN.md §5.5): verificador y primera pasada. Lo que encuentran se corrige y se
   valida de nuevo, hasta MAX_CORRECCIONES veces.
5. Revisor independiente (PLAN.md §5.4): con la lectura limpia, una sesión nueva la revisa y hace también la
   segunda pasada: las cuatro preguntas por bloque y la lista de verificación (decisión 12). Sus hallazgos
   se corrigen o se rechazan con un pasaje, y el ciclo valida de nuevo, hasta VUELTAS_POR_RONDA veces.
   Con tres hallazgos o más se lanza otro revisor nuevo. Máximo MAX_RONDAS rondas.
6. Entrega en el formato del SPEC §8. El profesor la aprueba desde la página.
"""

import json
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from app import agente, entrega, skill, tokens
from app.fichas import almacen, verificacion
from app.materiales import docx, estilo
from app.materiales.contenido import ESQUEMA_LECTURA, Lectura
from app.validacion import excel, pasada1, pasada2, revisor, verificador
from app.validacion.pasajes import Corpus, literal

MATERIAL = "Lectura"
CLAVE = "lectura"
MAX_CORRECCIONES = 5  # tope de vueltas del ciclo de corrección (PLAN.md §5.5)
MAX_RONDAS = 3        # tope de rondas del revisor independiente (PLAN.md §0, decisión 1)
VUELTAS_POR_RONDA = 2  # vueltas para corregir lo que encontró una ronda del revisor (PLAN.md §0, decisión 9)
MINIMO_PARA_OTRA_RONDA = 3  # con tres hallazgos válidos o más se lanza otro revisor (SKILL.md)
DEFECTOS_QUE_SE_ELIMINAN = ("relleno", "ambigüedad")   # al tope, el programa puede borrar esas oraciones
INSTRUCCION_SIN_EJECUCION = "No aplica: la lectura no tiene archivos de práctica que ejecutar."
VUELTA_DE_ULTIMO_INTENTO = 3
ULTIMO_INTENTO = ("YA SE INTENTÓ CORREGIR: escribe la oración con las palabras exactas de su pasaje, "
                  "sin cambiar ningún término, o elimínala.")
PALABRAS_MAX = 1500  # orientación para no pasar de seis páginas con portada

ESQUEMA_CORRECCION = {
    "type": "object",
    "properties": {
        "lectura": ESQUEMA_LECTURA,
        "explicaciones": {"type": "array", "items": {
            "type": "object",
            "properties": {"regla": {"type": "string"}, "oracion": {"type": "string"}, "explicacion": {"type": "string"}},
            "required": ["regla", "oracion", "explicacion"], "additionalProperties": False,
        }},
        "datos_nuevos": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["lectura", "explicaciones", "datos_nuevos"],
    "additionalProperties": False,
}

ESQUEMA_CAMBIOS = {
    "type": "object",
    "properties": {
        "cambios": {"type": "array", "items": {
            "type": "object",
            "properties": {"oracion": {"type": "string"}, "nueva": {"type": "string"}},
            "required": ["oracion", "nueva"], "additionalProperties": False,
        }},
        "explicaciones": ESQUEMA_CORRECCION["properties"]["explicaciones"],
        "datos_nuevos": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["cambios", "explicaciones", "datos_nuevos"],
    "additionalProperties": False,
}

# Con hallazgos del revisor independiente, el redactor también puede rechazar un hallazgo con un pasaje.
ESQUEMA_CAMBIOS_REVISOR = {
    **ESQUEMA_CAMBIOS,
    "properties": {
        **ESQUEMA_CAMBIOS["properties"],
        "rechazos": {"type": "array", "items": {
            "type": "object",
            "properties": {"oracion": {"type": "string"}, "pasaje": {"type": "string"}, "fuente": {"type": "string"}},
            "required": ["oracion", "pasaje", "fuente"], "additionalProperties": False,
        }},
    },
    "required": [*ESQUEMA_CAMBIOS["required"], "rechazos"],
}


class NoSePuedeEmpezar(RuntimeError):
    """Faltan fichas confirmadas (SPEC §3: ningún material empieza sin la ficha de la sesión confirmada)."""


class NoSePuedeAprobar(RuntimeError):
    """La lectura tiene problemas abiertos, está desactualizada o no se generó."""


def carpeta_materiales(carpeta_curso: Path, sesion: int) -> Path:
    return almacen.carpeta_sesion(carpeta_curso, sesion) / "materiales"


def archivos(carpeta_curso: Path, sesion: int) -> dict[str, Path]:
    carpeta = carpeta_materiales(carpeta_curso, sesion)
    return {
        "word": carpeta / f"S{sesion}_Lectura.docx",
        "excel": carpeta / f"S{sesion}_Lectura_Verificacion.xlsx",
        "entrega": carpeta / f"S{sesion}_Lectura_Entrega.md",
        "revision": carpeta / "lectura" / "revisor",
        "contenido": carpeta / "lectura" / "contenido.json",
        "explicaciones": carpeta / "lectura" / "explicaciones.json",
        "pasada1": carpeta / "lectura" / "pasada1.json",
    }


# ---------- Estado y avance (la página lo consulta mientras se trabaja) ----------

def _estado(carpeta_curso: Path, sesion: int) -> dict:
    return almacen.cargar_estado(carpeta_curso, sesion)["materiales"].get(CLAVE, {})


def _actualizar(carpeta_curso: Path, sesion: int, **cambios) -> dict:
    estado = almacen.cargar_estado(carpeta_curso, sesion)
    material = estado["materiales"].setdefault(CLAVE, {"avance": []})
    material.update(cambios)
    almacen.guardar_estado(carpeta_curso, sesion, estado)
    return material


def _avance(carpeta_curso: Path, sesion: int, texto: str) -> None:
    estado = almacen.cargar_estado(carpeta_curso, sesion)
    material = estado["materiales"].setdefault(CLAVE, {"avance": []})
    material.setdefault("avance", []).append(f"{datetime.now():%H:%M:%S} · {texto}")
    almacen.guardar_estado(carpeta_curso, sesion, estado)


# ---------- Pedidos al agente ----------

def _contexto(carpeta_curso: Path, sesion: int) -> str:
    ficha_curso = almacen.ruta_ficha(carpeta_curso, "curso", extension=".md").read_text(encoding="utf-8")
    ficha_sesion = almacen.ruta_ficha(carpeta_curso, "sesion", sesion, ".md").read_text(encoding="utf-8")
    fuentes = verificacion.fuentes_utilizables(carpeta_curso)
    return "\n".join([
        "REGLAS DE LA SKILL (son obligatorias):",
        skill.secciones("Reglas comunes", "Paso 3 · Vocabulario de la sesión", "Material 1 · Lectura"),
        "",
        "FICHA DEL CURSO (confirmada):", ficha_curso,
        "FICHA DE LA SESIÓN (confirmada):", ficha_sesion,
        "FUENTES DEL CURSO que puedes citar (archivos .jsonl de esta carpeta, un pasaje por línea con su ubicación):",
        *([f"- {f}" for f in fuentes] or ["- (ninguna: no cites fuentes)"]),
    ])


INSTRUCCIONES_DE_FORMATO = f"""
CÓMO ENTREGAR LA LECTURA
- Devuelve solo los datos del esquema. Un programa crea el Word: la portada, el encabezado,
  el título «Idea central» y los títulos de los recuadros «Aplícalo así» y «Cuidado con» los pone él.
- idea_central: de 2 a 3 oraciones.
- bloques: de 2 a 4, en el orden de la ficha de la sesión. Cada uno con subtítulo, párrafos breves y un ejemplo.
  El ejemplo usa un caso distinto al de los ejercicios del laboratorio y no da la respuesta de ningún ejercicio.
  Usa «tabla» solo si ayuda a entender; si no, déjala en null. Máximo 4 columnas.
- aplicalo.plantilla: la técnica o plantilla lista para copiar, una línea por elemento, sin espacios por llenar.
- cuidado: de 1 a 3 riesgos de una línea cada uno.
- pasajes: una entrada por cada oración que afirma algo de una norma o de una fuente: «oracion» copiada
  tal cual de la lectura, la fuente, la ubicación y en «texto» el pasaje que la sostiene, copiado tal cual,
  de 40 palabras como máximo. Escribe cada una de esas oraciones a partir de su pasaje, sin cambiar sus términos.
- decisiones: cada dato o decisión que las fichas no definían.
- agrupacion: si hubo más temas que bloques, cómo los agrupaste. Si no, texto vacío.
- Unas {PALABRAS_MAX} palabras como máximo en total, para no pasar de seis páginas con portada.
- Una idea por oración y 25 palabras como máximo por oración. Excepción: si partir una oración que sigue a su
  pasaje de una norma cambiaría lo que dice la norma, no la partas y anótala en «pasajes».
- Usa los nombres del vocabulario de la sesión tal cual y en su orden. No uses sus variantes.
- Usa comillas solo para copiar texto tal cual de una fuente.
- Si agrupas, resumes o cambias el orden de lo que dice una norma, escribe «en este curso».
- Para afirmar algo de una norma, usa las palabras de su pasaje. No uses «en este curso» para evitar
  una fuente: úsalo solo en reglas propias del curso o para avisar que resumiste, agrupaste o reordenaste.
"""


# Los pedidos empiezan siempre con la misma parte fija (reglas, fichas y formato) y terminan con lo que
# cambia. Claude guarda unos minutos el comienzo de cada pedido y releerlo cuesta un 10 %.

def pedido_de_redaccion(carpeta_curso: Path, sesion: int) -> str:
    return "\n".join([
        _contexto(carpeta_curso, sesion),
        INSTRUCCIONES_DE_FORMATO,
        "TAREA: redacta la lectura de la sesión. Actúa como diseñador instruccional y editor senior.",
        "Antes de redactar, busca con Grep en las fuentes y lee con Read los pasajes que vas a usar.",
        "Redacta a partir de esos pasajes, no de memoria. No afirmes sobre una norma nada que no esté en un pasaje copiado.",
        "Antes de entregar, revisa cada bloque con las cuatro preguntas de la segunda pasada de la skill:",
        "qué puede hacer el alumno, qué dato necesita y dónde está, qué oración tiene dos lecturas, y qué decide",
        "si su caso no sale como el ejemplo. Define cada término la primera vez que aparece. Corrige lo que falle.",
    ])


REGLAS_DE_CORRECCION = """REGLAS DE CORRECCIÓN
- Una FALLA se corrige siempre. Un AVISO se corrige o se explica.
- VERACIDAD · no coincide: reescribe la oración para que diga lo que dice su pasaje.
- VERACIDAD · sin fuente en una norma: busca su pasaje con Grep y reescribe la oración con las palabras de la fuente.
  No agregues «en este curso» para escapar de la fuente. Si ninguna fuente lo dice, elimina la oración.
- VERACIDAD · sin fuente en otra oración: elimínala, o conviértela en una regla del curso que diga «en este curso».
  Si es un dato ficticio del caso que hace falta, agrégalo en «datos_nuevos» como «Etiqueta: valor».
  AulaLista lo guarda en los datos fijos de la ficha del curso, y todos los materiales lo usan igual.
- Si no hay datos nuevos, deja «datos_nuevos» vacío.
- Si mantienes una oración con AVISO, agrega en «explicaciones» la regla y la oración copiadas tal cual del problema, y por qué se mantiene.
- REVISOR INDEPENDIENTE · relleno: elimina la oración. · ambigüedad: reescríbela para que tenga una sola lectura.
  · inconsistencia: usa el mismo dato en todas sus apariciones, el de la ficha si existe.
  · imprecisión: reescríbela para que diga lo que dice su pasaje.
  · vacío: agrega lo que falta. Para agregar, reemplaza la oración indicada por ella misma seguida de la nueva.
- LISTA DE VERIFICACIÓN: corrige lo que la pregunta señala, con el menor cambio posible.
- REVISOR INDEPENDIENTE: corrige cada hallazgo con el menor cambio posible. Si no estás de acuerdo, no cambies
  la oración: agrega en «rechazos» la oración tal cual, el pasaje de una fuente que contradice el hallazgo,
  copiado tal cual, y el nombre de esa fuente. Sin un pasaje que exista tal cual, el rechazo no vale.
- Cambia solo lo necesario. Puedes buscar en las fuentes con Grep y Read si necesitas un pasaje.
"""


def pedido_de_cambios(carpeta_curso: Path, sesion: int, contenido: dict, problemas: list[str]) -> str:
    """Corrección barata: devuelve solo las oraciones que cambian."""
    return "\n".join([
        _contexto(carpeta_curso, sesion),
        INSTRUCCIONES_DE_FORMATO,
        REGLAS_DE_CORRECCION,
        "CÓMO ENTREGAR LA CORRECCIÓN",
        "- En «cambios», una entrada por oración que cambias: «oracion» copiada tal cual de la lectura y «nueva» con el texto nuevo.",
        "- Para eliminar una oración, deja «nueva» vacío. No devuelvas las oraciones que no cambian.",
        *(["- En «rechazos», los hallazgos del revisor independiente que no aceptas, con su pasaje. Si no hay, déjalo vacío."]
          if any(p.startswith("REVISOR INDEPENDIENTE") for p in problemas) else []),
        "",
        "LECTURA ACTUAL:",
        json.dumps(contenido, ensure_ascii=False),
        "",
        "PROBLEMAS QUE ENCONTRÓ LA VALIDACIÓN:",
        *[f"- {p}" for p in problemas],
    ])


def pedido_de_correccion(carpeta_curso: Path, sesion: int, contenido: dict, problemas: list[str]) -> str:
    """Corrección completa: solo para problemas de estructura o de extensión, que no son de una oración."""
    return "\n".join([
        _contexto(carpeta_curso, sesion),
        INSTRUCCIONES_DE_FORMATO,
        REGLAS_DE_CORRECCION,
        "Devuelve la lectura completa con el mismo esquema.",
        "",
        "LECTURA ACTUAL:",
        json.dumps(contenido, ensure_ascii=False),
        "",
        "PROBLEMAS QUE ENCONTRÓ LA VALIDACIÓN:",
        *[f"- {p}" for p in problemas],
    ])


def _describir(resultado, explicaciones: dict) -> list[str]:
    problemas = []
    for h in resultado.hallazgos:
        if h.nivel == "AVISO" and verificador.buscar_explicacion(h.regla, h.oracion, explicaciones):
            continue
        donde = f"«{h.oracion}»" if h.oracion else h.seccion
        problemas.append(f"{h.nivel} · {h.regla} · {donde}: {h.detalle}")
    return problemas


def _validar(datos: dict) -> tuple[Lectura | None, list[str]]:
    try:
        return Lectura.model_validate(datos), []
    except ValidationError as error:
        return None, [f"FALLA · estructura · {'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()]


# ---------- Generación ----------

def _portada(carpeta_curso: Path, sesion: int) -> docx.Portada:
    ficha_curso = almacen.cargar(carpeta_curso, "curso")
    ficha_sesion = almacen.cargar(carpeta_curso, "sesion", sesion)
    titulo = almacen.valor(ficha_sesion, "sesion.numero_titulo").strip()
    return docx.Portada(
        curso=almacen.valor(ficha_curso, "curso.nombre").strip(),
        sesion=titulo if titulo.lower().startswith("sesión") else f"Sesión {titulo}",
        material=MATERIAL,
        docente=almacen.valor(ficha_curso, "portada.docente").strip(),
    )


async def generar(carpeta_curso: Path, curso: str, sesion: int, consulta=agente.query, contar_paginas=None) -> dict:
    if not almacen.puede_empezar_material(carpeta_curso, sesion):
        raise NoSePuedeEmpezar("Confirma la ficha del curso y la ficha de la sesión antes de generar la lectura.")
    rutas = archivos(carpeta_curso, sesion)
    rutas["contenido"].parent.mkdir(parents=True, exist_ok=True)
    _actualizar(carpeta_curso, sesion, estado="trabajando", avance=[], error="", desactualizado=False,
                entrega={}, aprobada="")
    try:
        return await _generar(carpeta_curso, curso, sesion, rutas, consulta, contar_paginas)
    except Exception as error:
        _actualizar(carpeta_curso, sesion, estado="error", error=str(error))
        raise


def _titulos(contenido: Lectura) -> set[str]:
    """Textos que son títulos o rótulos: van a la tabla como «sin afirmación», sin IA."""
    titulos = {"Idea central", "Aplícalo así", "Cuidado con"}
    for bloque in contenido.bloques:
        titulos |= {bloque.subtitulo, bloque.ejemplo.titulo}
        if bloque.tabla is not None:
            titulos |= {bloque.tabla.titulo, *bloque.tabla.encabezados}
    return {t.strip() for t in titulos if t.strip()}


def _historial_del_verificador(resultado, explicaciones, vuelta) -> list[dict]:
    return [
        {"nivel": h.nivel, "seccion": h.seccion, "oracion": h.oracion, "regla": h.regla, "detalle": h.detalle, "vuelta": vuelta}
        for h in resultado.hallazgos
        if not (h.nivel == "AVISO" and verificador.buscar_explicacion(h.regla, h.oracion, explicaciones))
    ]


def _describir_veracidad(v: dict) -> str:
    return (f"VERACIDAD · {v['veredicto']} · «{v['texto']}»: {v['motivo']} "
            f"Pasaje: «{v['pasaje']}»" + (f" ({v['fuente']})" if v["fuente"] else "") + ".")


def _leer_json(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def _guardar_json(ruta: Path, datos) -> None:
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


# Avisos que se muestran en la hoja Hallazgos pero no obligan a corregir ni a explicar (PLAN.md §0, decisión 13).
AVISOS_INFORMATIVOS = ("relleno", "palabra imprecisa")
NOTA_INFORMATIVA = "Aviso informativo: no obliga a corregir ni a explicar (PLAN.md §0, decisión 13)."


def _hallazgos_abiertos(resultado, explicaciones) -> tuple[list, list]:
    """Fallas del verificador y avisos todavía sin explicar. Los avisos informativos no cuentan."""
    fallas = [h for h in resultado.hallazgos if h.nivel == "FALLA"]
    avisos = [h for h in resultado.hallazgos
              if h.nivel == "AVISO" and h.regla not in AVISOS_INFORMATIVOS
              and not verificador.buscar_explicacion(h.regla, h.oracion, explicaciones)]
    return fallas, avisos


def _texto_de(h) -> str:
    donde = f"«{h.oracion}»" if h.oracion else h.seccion
    return f"{h.nivel} · {h.regla} · {donde}: {h.detalle}"


def bloques_de(contenido: Lectura) -> list[pasada2.Bloque]:
    """La lectura por bloques, para las cuatro preguntas de la segunda pasada."""
    separar = verificador.verificar.separar_oraciones

    def oraciones(*parrafos):
        return [o for p in parrafos for o in separar(p)]

    bloques = [pasada2.Bloque("Idea central", oraciones(*contenido.idea_central))]
    for b in contenido.bloques:
        filas = [" | ".join(f) for f in b.tabla.filas] if b.tabla else []
        bloques.append(pasada2.Bloque(b.subtitulo, oraciones(*b.parrafos, b.ejemplo.titulo, *b.ejemplo.parrafos, *filas)))
    bloques.append(pasada2.Bloque("Aplícalo así", oraciones(*contenido.aplicalo.parrafos, *contenido.aplicalo.plantilla)))
    bloques.append(pasada2.Bloque("Cuidado con", oraciones(*contenido.cuidado)))
    return bloques


REGLAS_QUE_EXPLICA_EL_PROGRAMA = ("oración larga", "palabra imprecisa")


def _pasaje_de_la_oracion(oracion: str, anclas: list[dict], corpus: Corpus) -> tuple[str, str] | None:
    """La fuente y la ubicación del pasaje que el redactor dijo usar para esta oración, si existe tal cual
    en una fuente del curso (no en una ficha)."""
    buscada = _comparable(oracion)
    for ancla in anclas:
        propia = _comparable(ancla.get("oracion", ""))
        if not propia or not (propia in buscada or buscada in propia):
            continue
        ubicacion = corpus.ubicar(ancla["fuente"], ancla["texto"])
        encontrada = (ancla["fuente"], ubicacion) if ubicacion else corpus.ubicar_en_cualquiera(ancla["texto"])
        if encontrada and encontrada[0] not in pasada1.FICHAS:
            return encontrada
    return None


def _explicar_literales(resultado, explicaciones: dict, corpus: Corpus, anclas: list[dict] | None = None) -> bool:
    """Un aviso de oración larga o de palabra imprecisa en una oración copiada tal cual de una fuente del
    curso se explica solo: cambiarla cambiaría lo que dice la fuente (así lo hace el Excel modelo).
    Un aviso de oración larga en una oración escrita a partir de su pasaje de una norma también se explica
    solo: partirla puede cambiar lo que dice la norma (PLAN.md §0, decisión 10)."""
    nuevas = False
    for h in resultado.hallazgos:
        if h.nivel != "AVISO" or h.regla not in REGLAS_QUE_EXPLICA_EL_PROGRAMA or not h.oracion:
            continue
        if verificador.buscar_explicacion(h.regla, h.oracion, explicaciones):
            continue
        texto = h.oracion.split(": ", 1)[-1]
        encontrada = corpus.ubicar_en_cualquiera(texto)
        if encontrada and encontrada[0] not in pasada1.FICHAS:
            fuente, ubicacion = encontrada
            explicaciones[verificador.clave_de_hallazgo(h.regla, h.oracion)] = (
                f"Es un pasaje literal de la fuente ({fuente}, {ubicacion}). Cambiarlo cambiaría lo que dice. "
                "Lo comprobó el programa.")
            nuevas = True
        elif h.regla == "oración larga" and (anclada := _pasaje_de_la_oracion(texto, anclas or [], corpus)):
            fuente, ubicacion = anclada
            explicaciones[verificador.clave_de_hallazgo(h.regla, h.oracion)] = (
                f"Sigue a su pasaje de la norma ({fuente}, {ubicacion}). Partirla puede cambiar lo que dice la norma. "
                "El programa comprobó que el pasaje existe; la primera pasada compara la oración con él.")
            nuevas = True
    return nuevas


def _historial(hallazgos, vuelta) -> list[dict]:
    return [{"nivel": h.nivel, "seccion": h.seccion, "oracion": h.oracion, "regla": h.regla,
             "detalle": h.detalle, "vuelta": vuelta} for h in hallazgos]


def aplicar_cambios(datos: dict, cambios: list[dict]) -> tuple[dict, list[str]]:
    """Reemplaza cada oración corregida dentro de la lectura. «nueva» vacía elimina la oración.
    Devuelve la lectura nueva y las oraciones que no se encontraron."""
    datos = json.loads(json.dumps(datos))
    no_encontradas = []
    for cambio in cambios:
        buscada = " ".join(cambio["oracion"].split())
        nueva = " ".join(cambio["nueva"].split())
        if not buscada or not _reemplazar(datos, buscada, nueva):
            no_encontradas.append(cambio["oracion"])
    return datos, no_encontradas


CAMPOS_QUE_NO_SE_CORRIGEN = {"pasajes", "decisiones", "agrupacion"}


def _reemplazar(nodo, buscada: str, nueva: str, borrar: bool = True) -> bool:
    """borrar=False dentro de una tabla: una celda vacía se queda, para no descuadrar las columnas."""
    if isinstance(nodo, dict):
        return any(_reemplazar_en(nodo, clave, buscada, nueva, borrar and clave != "tabla") for clave in list(nodo)
                   if clave not in CAMPOS_QUE_NO_SE_CORRIGEN)
    if isinstance(nodo, list):
        return any(_reemplazar_en(nodo, i, buscada, nueva, borrar) for i in range(len(nodo) - 1, -1, -1))
    return False


def _reemplazar_en(contenedor, clave, buscada: str, nueva: str, borrar: bool) -> bool:
    valor = contenedor[clave]
    if not isinstance(valor, str):
        return _reemplazar(valor, buscada, nueva, borrar)
    normal = " ".join(valor.split())
    if buscada not in normal:
        return False
    texto = " ".join(normal.replace(buscada, nueva, 1).split())
    if not texto and borrar and isinstance(contenedor, list):
        del contenedor[clave]   # el párrafo quedó vacío: se elimina
    else:
        contenedor[clave] = texto
    return True


def _comparable(texto: str) -> str:
    return verificador._comparable(texto)


def _oraciones_de(nodo) -> set[str]:
    """Las oraciones de la lectura que se pueden corregir, en forma comparable, para saber si una oración
    sigue en ella. Se compara oración por oración: una oración corregida suele contener a la anterior."""
    if isinstance(nodo, dict):
        return set().union(*[_oraciones_de(v) for k, v in nodo.items() if k not in CAMPOS_QUE_NO_SE_CORRIGEN])
    if isinstance(nodo, list):
        return set().union(*[_oraciones_de(v) for v in nodo])
    if isinstance(nodo, str):
        return {_comparable(o) for o in verificador.verificar.separar_oraciones(nodo)} | {_comparable(nodo)}
    return set()


class _Ciclo:
    """Estado del ciclo de corrección de una lectura (PLAN.md §5.5).

    El ciclo corre una vez después de la redacción y otra vez después de cada ronda del revisor
    independiente. Las huellas, las explicaciones y el historial se conservan entre una y otra.
    """

    def __init__(self, carpeta_curso, curso, sesion, rutas, consulta, contar_paginas):
        self.carpeta_curso, self.curso, self.sesion, self.rutas = carpeta_curso, curso, sesion, rutas
        self.consulta = consulta
        self._contar_paginas = contar_paginas or verificador.verificar._contar_paginas_con_word
        self.paginas: int | None = None
        self.carpeta_sesion = almacen.carpeta_sesion(carpeta_curso, sesion)
        self.identidad = estilo.desde_ficha(carpeta_curso)
        self.portada = _portada(carpeta_curso, sesion)
        self.comun = {"curso": curso, "sesion": f"S{sesion}", "material": CLAVE, "cwd": carpeta_curso / "fuentes_texto",
                      "herramientas": ("Read", "Grep", "Glob"), "consulta": consulta}
        self.datos: dict = {}
        self.explicaciones: dict[str, str] = {}
        self.anteriores = _leer_json(rutas["pasada1"])   # solo guarda oraciones que coinciden con su fuente
        self.historial: list[dict] = []
        self.correcciones = {"verificador": 0, "primera pasada": 0}
        self.respuestas2: dict[str, dict] = {}
        self.bloques: list = []
        self.medida: dict = {}
        self.datos_agregados: list[str] = []
        self.resultado = None
        self.oraciones: list[dict] = []   # filas del verificador sobre el último Word generado
        self.problemas: list[str] = []
        self.eliminadas: list[str] = []
        self.vuelta = 0
        self.hallazgos_del_revisor: list[revisor.Hallazgo] = []
        self.revisadas: dict[str, int] = {}   # huella de cada oración que vio un revisor → su última ronda

    def avance(self, texto: str) -> None:
        _avance(self.carpeta_curso, self.sesion, texto)

    def contar_paginas(self, ruta: Path) -> int:
        self.paginas = self._contar_paginas(ruta)
        return self.paginas

    def abiertos_del_revisor(self) -> list[str]:
        return [h.describir() for h in self.hallazgos_del_revisor if h.estado == "abierto"]

    # ---------- Una vuelta de validación ----------

    async def validar(self, cierre_hecho: bool, pendientes_del_cierre: list[str]) -> tuple[list[str], bool, list[str], list[str]]:
        """Genera el Word y lo valida. Devuelve (problemas, corrección completa, borrables, no borrables)."""
        self.vuelta += 1
        vuelta, rutas = self.vuelta, self.rutas
        borrables: list[str] = []   # oraciones que el programa puede eliminar si se llega al tope
        no_borrables: list[str] = []
        contenido, problemas = _validar(self.datos)
        completa = bool(problemas)            # la estructura solo se arregla con una corrección completa
        _guardar_json(rutas["contenido"], self.datos)
        if contenido is None:
            return problemas + self.abiertos_del_revisor(), completa, borrables, no_borrables
        configuracion = verificador.configuracion_del_material(self.carpeta_sesion, MATERIAL)
        docx.generar_lectura(contenido, self.identidad, self.portada, rutas["word"])
        self.resultado = verificador.ejecutar(configuracion, [rutas["word"]], rutas["excel"], self.explicaciones,
                                              self.contar_paginas)
        corpus = Corpus.del_curso(self.carpeta_curso, self.sesion)
        if _explicar_literales(self.resultado, self.explicaciones, corpus, [p.model_dump() for p in contenido.pasajes]):
            _guardar_json(rutas["explicaciones"], self.explicaciones)
            verificador.anotar_explicaciones(rutas["excel"], self.explicaciones)
        excel.anotar_reglas(rutas["excel"], AVISOS_INFORMATIVOS, NOTA_INFORMATIVA)
        self.oraciones = _leer_json(rutas["excel"].with_suffix(".json"))["oraciones"]
        fallas, avisos = _hallazgos_abiertos(self.resultado, self.explicaciones)
        self.avance(f"Verificador, vuelta {vuelta}: {self.resultado.resumen()}.")
        abiertos = self.abiertos_del_revisor()
        if fallas:
            # Las fallas mecánicas se corrigen antes de usar IA para revisar (SPEC §9).
            problemas = [_texto_de(h) for h in fallas + avisos] + abiertos
            completa = any(not h.oracion for h in fallas)   # páginas y otros problemas del documento entero
            self.historial += _historial(fallas + avisos, vuelta)
            self.correcciones["verificador"] += len(fallas + avisos)
            return problemas, completa, borrables, abiertos

        # Primera pasada en cada vuelta. La segunda la hace el revisor independiente (PLAN.md §0, decisión 12).
        self.bloques = bloques_de(contenido)
        pasada = await pasada1.ejecutar(
            self.oraciones, titulos=_titulos(contenido), corpus=corpus,
            anteriores=self.anteriores, curso=self.curso, sesion=self.sesion, material=CLAVE,
            anclas=[p.model_dump() for p in contenido.pasajes],
            instruccion_sin_ejecucion=INSTRUCCION_SIN_EJECUCION, consulta=self.consulta)
        self.anteriores = {h: f for h, f in pasada.filas.items() if f["veredicto"] == "coincide"}
        _guardar_json(rutas["pasada1"], self.anteriores)
        excel.llenar_oraciones(rutas["excel"], self.oraciones, pasada.filas)

        veraces = pasada.problemas(self.oraciones)
        # Los avisos sin explicar van en la misma corrección: no gastan una vuelta propia.
        problemas = [_describir_veracidad(v) for v in veraces] + [_texto_de(h) for h in avisos] + abiertos
        self.historial += [{"nivel": "FALLA", "seccion": v["seccion"], "oracion": v["texto"],
                            "regla": f"veracidad: {v['veredicto']}", "detalle": v["motivo"], "vuelta": vuelta}
                           for v in veraces] + _historial(avisos, vuelta)
        self.correcciones["primera pasada"] += len(veraces)
        self.correcciones["verificador"] += len(avisos)
        # Al tope, el programa puede eliminar lo que sigue sin fuente y lo que el revisor marcó como relleno o ambiguo.
        abiertos_borrables = [h for h in self.hallazgos_del_revisor
                              if h.estado == "abierto" and h.defecto in DEFECTOS_QUE_SE_ELIMINAN]
        borrables = [v["texto"] for v in veraces] + [h.oracion for h in abiertos_borrables]
        no_borrables = [h.describir() for h in self.hallazgos_del_revisor
                        if h.estado == "abierto" and h not in abiertos_borrables]
        if cierre_hecho:
            problemas += pendientes_del_cierre
        if pasada.enviadas_a_la_ia or pasada.aprobadas_por_programa:
            self.medida = {"enviadas": pasada.enviadas_a_la_ia, "fuera_de_candidatos": pasada.pasajes_fuera_de_candidatos,
                           "busquedas": pasada.busquedas, "aprobadas_por_programa": pasada.aprobadas_por_programa}
        self.avance(f"Primera pasada: {len(self.oraciones)} oraciones, "
                    f"{pasada.enviadas_a_la_ia} revisadas con IA, {pasada.aprobadas_por_programa} aprobadas por el programa, "
                    f"{len(veraces)} con problemas.")
        return problemas, completa, borrables, no_borrables

    # ---------- Corrección ----------

    async def corregir(self, problemas: list[str], completa: bool) -> None:
        vuelta = self.vuelta
        con_revisor = any(p.startswith("REVISOR INDEPENDIENTE") for p in problemas)
        if completa:
            self.avance(f"Corrigiendo la lectura completa: {len(problemas)} problemas.")
            respuesta = await agente.consultar(pedido_de_correccion(self.carpeta_curso, self.sesion, self.datos, problemas),
                                               tarea="correccion", esquema=ESQUEMA_CORRECCION,
                                               etapa=f"corrección completa {vuelta}", **self.comun)
            self.datos = respuesta["lectura"]
        else:
            self.avance(f"Corrigiendo {len(problemas)} oraciones.")
            respuesta = await agente.consultar(pedido_de_cambios(self.carpeta_curso, self.sesion, self.datos, problemas),
                                               tarea="correccion_oraciones",
                                               esquema=ESQUEMA_CAMBIOS_REVISOR if con_revisor else ESQUEMA_CAMBIOS,
                                               etapa=f"corrección {vuelta}", **self.comun)
            self.datos, no_encontradas = aplicar_cambios(self.datos, respuesta["cambios"])
            if no_encontradas:
                self.avance(f"{len(no_encontradas)} oraciones a cambiar no se encontraron en la lectura.")
        for e in respuesta["explicaciones"]:
            self.explicaciones[verificador.clave_de_hallazgo(e["regla"], e["oracion"])] = e["explicacion"]
        _guardar_json(self.rutas["explicaciones"], self.explicaciones)
        nuevos = almacen.agregar_datos_fijos(self.carpeta_curso, respuesta.get("datos_nuevos", []), f"Lectura S{self.sesion}")
        if nuevos:
            self.datos_agregados += nuevos
            for numero in almacen.sesiones_confirmadas(self.carpeta_curso):
                verificacion.escribir(self.carpeta_curso, numero)
            self.avance(f"Datos nuevos del caso agregados a la ficha del curso: {len(nuevos)}.")
        if con_revisor:
            self.resolver_hallazgos(respuesta.get("cambios", []), respuesta.get("rechazos", []), enviados=True)

    def borrar_sin_romper(self, oraciones: list[str]) -> tuple[list[str], list[str]]:
        """Elimina las oraciones una por una mientras la lectura siga con su estructura completa.
        Devuelve (eliminadas, las que no se pudieron eliminar)."""
        eliminadas, no_se_pueden = [], []
        for o in oraciones:
            candidato, no_encontradas = aplicar_cambios(self.datos, [{"oracion": o, "nueva": ""}])
            if no_encontradas or _validar(candidato)[1]:
                no_se_pueden.append(o)
            else:
                self.datos = candidato
                eliminadas.append(o)
        return eliminadas, no_se_pueden

    def resolver_hallazgos(self, cambios: list[dict], rechazos: list[dict], enviados: bool) -> None:
        """Un hallazgo queda resuelto si su oración ya no está en la lectura, y rechazado si el redactor
        dio un pasaje que existe tal cual en una fuente. Si no, sigue abierto."""
        actuales = _oraciones_de(self.datos)
        corpus = Corpus.del_curso(self.carpeta_curso, self.sesion) if rechazos else None
        for h in self.hallazgos_del_revisor:
            if h.estado != "abierto":
                continue
            if enviados:
                h.intentos += 1
            buscada = _comparable(h.oracion)
            if buscada not in actuales:
                cambio = next((c for c in cambios if _comparable(c["oracion"]) and (
                    _comparable(c["oracion"]) in buscada or buscada in _comparable(c["oracion"]))), None)
                h.nueva = (cambio or {}).get("nueva", "")
                h.estado = "resuelto"
                if not enviados:
                    h.resolucion = f"Ronda {h.ronda}: {h.defecto}. Resuelto: el programa eliminó la oración al llegar al tope."
                elif cambio is not None and not h.nueva:
                    h.resolucion = f"Ronda {h.ronda}: {h.defecto}. Resuelto: se eliminó la oración."
                else:
                    h.resolucion = f"Ronda {h.ronda}: {h.defecto}. Resuelto en la vuelta {self.vuelta}."
                continue
            for r in rechazos:
                comparable = _comparable(r["oracion"])
                if not comparable or not (comparable in buscada or buscada in comparable):
                    continue
                pasaje = literal(r["pasaje"]).strip()
                ubicacion = corpus.ubicar(r["fuente"], pasaje)
                fuente = r["fuente"]
                if ubicacion is None:
                    encontrada = corpus.ubicar_en_cualquiera(pasaje)
                    if encontrada is None:
                        continue   # sin un pasaje que exista tal cual, el rechazo no vale
                    fuente, ubicacion = encontrada
                h.estado = "rechazado"
                h.resolucion = f"Ronda {h.ronda}: {h.defecto}. Rechazado: «{pasaje}» ({fuente}, {ubicacion})."
                break

    # ---------- El ciclo ----------

    async def correr(self, tope: int, iniciales: list[str] | None = None) -> bool:
        """Valida y corrige hasta `tope` veces. Con `iniciales`, la primera corrección es la de esos problemas.
        Al llegar al tope, el programa elimina lo que se puede eliminar y valida otra vez (PLAN.md §0,
        decisión 7). Devuelve True si la lectura quedó sin problemas."""
        cierre_hecho, pendientes_del_cierre = False, []
        # Una vuelta más que las correcciones, y otra para validar el cierre por programa.
        for paso in range(1, tope + 3):
            if paso == 1 and iniciales:
                problemas, completa, borrables, no_borrables = iniciales, False, [], []
            else:
                problemas, completa, borrables, no_borrables = await self.validar(cierre_hecho, pendientes_del_cierre)
            self.problemas = problemas
            if not problemas:
                return True
            if paso > tope:
                if not cierre_hecho and borrables:
                    # Cierre por programa (SKILL.md: «Sin fuente: elimina la oración»). Sin IA y sin costo.
                    # No se borra una oración si deja vacía una parte obligatoria: esa queda pendiente.
                    borrables, no_se_pueden = self.borrar_sin_romper(borrables)
                    no_borrables = no_borrables + [
                        f"CIERRE POR PROGRAMA · «{o}»: sigue con problemas y no se puede eliminar sin dejar vacía "
                        "una parte obligatoria de la lectura." for o in no_se_pueden
                        # un hallazgo del revisor que no se pudo borrar ya queda pendiente con su propia descripción
                        if not any(h.estado == "abierto" and h.oracion == o for h in self.hallazgos_del_revisor)]
                    self.historial += [{"nivel": "FALLA", "seccion": self.rutas["word"].name, "oracion": o,
                                        "regla": "cierre por programa", "vuelta": self.vuelta,
                                        "detalle": "Seguía sin coincidir con su fuente, o era relleno o ambigua, "
                                                   "al llegar al tope de vueltas."} for o in borrables]
                    self.resolver_hallazgos([], [], enviados=False)
                    cierre_hecho, pendientes_del_cierre = True, no_borrables
                    self.eliminadas += borrables
                    self.avance(f"Tope de vueltas: el programa eliminó {len(borrables)} oraciones "
                                "que seguían sin coincidir o eran relleno o ambiguas. Se valida de nuevo.")
                    continue
                self.avance(f"Quedan {len(problemas)} problemas después de {tope} correcciones. "
                            "Quedan como decisiones pendientes.")
                return False
            if paso >= VUELTA_DE_ULTIMO_INTENTO:
                # Una oración que sigue sin coincidir después de varias correcciones no se vuelve a reescribir libremente.
                problemas = [p + " " + ULTIMO_INTENTO if p.startswith("VERACIDAD") else p for p in problemas]
            await self.corregir(problemas, completa)
        return not self.problemas

    # ---------- Archivo de verificación ----------

    def columna_del_revisor(self, rondas: list) -> dict[int, str]:
        """Columna «Revisor independiente» de la hoja Oraciones (PLAN.md §5.6)."""
        valores = {}
        for o in self.oraciones:
            if not rondas:
                valores[o["n"]] = "No pasó por el revisor: la lectura quedó con problemas abiertos."
                continue
            texto = _comparable(o["texto"])
            notas, ultima = [], 0
            for h in sorted(self.hallazgos_del_revisor, key=lambda h: h.ronda):
                if h.estado != "resuelto" and _comparable(h.oracion) == texto:
                    notas.append(h.resolucion if h.estado == "rechazado"
                                 else f"Ronda {h.ronda}: {h.defecto}. Abierto: queda en decisiones pendientes.")
                elif h.estado == "resuelto" and h.nueva and texto in _oraciones_de(h.nueva):
                    notas.append(f"Ronda {h.ronda}: {h.defecto}. Resuelto.")
                else:
                    continue
                ultima = h.ronda
            if self.revisadas.get(o["huella"], 0) > ultima:
                notas.append(f"Ronda {self.revisadas[o['huella']]}: sin hallazgos.")
            valores[o["n"]] = " ".join(notas) or \
                "Texto nuevo después del revisor: lo validaron el verificador y la primera pasada."
        return valores

    def historial_del_revisor(self, rondas: list) -> list[dict]:
        filas = []
        for h in self.hallazgos_del_revisor:
            filas.append({"nivel": "FALLA", "seccion": self.rutas["word"].name, "oracion": h.oracion,
                          "regla": f"revisor independiente: {h.defecto}",
                          "detalle": f"Ronda {h.ronda}. {h.explicacion} Prueba: «{h.prueba}» ({h.fuente}).",
                          "resolucion": h.resolucion or "Abierto: queda en decisiones pendientes."})
        for r in rondas:
            filas += [{"nivel": "AVISO", "seccion": self.rutas["word"].name, "oracion": d["oracion"],
                       "regla": f"revisor independiente: {d['defecto']}",
                       "detalle": f"Ronda {r.ronda}. {d['explicacion']} Prueba: «{d['prueba']}» ({d['donde']}).",
                       "resolucion": f"Descartado por el programa: {d['motivo']}"} for d in r.descartados]
            filas += [{"nivel": "FALLA", "seccion": self.rutas["word"].name, "oracion": "",
                       "regla": "revisor independiente: lista de verificación",
                       "detalle": f"Ronda {r.ronda}. {p['pregunta']} {p['detalle']}",
                       "resolucion": f"Enviado a corrección en la ronda {r.ronda}."} for p in r.lista_no]
        return filas


def _resumen_de_rondas(rondas: list, hallazgos: list) -> list[dict]:
    resumen = []
    for r in rondas:
        propios = [h for h in hallazgos if h.ronda == r.ronda]
        resumen.append({"ronda": r.ronda, "hallazgos": len(propios), "descartados": len(r.descartados),
                        "lista": len(r.lista_no),
                        **{estado: sum(1 for h in propios if h.estado == estado)
                           for estado in ("resuelto", "rechazado", "abierto")}})
    return resumen


async def _generar(carpeta_curso, curso, sesion, rutas, consulta, contar_paginas) -> dict:
    inicio = tokens.lineas(curso)   # para sumar solo lo que gasta esta generación
    configuracion = verificador.configuracion_del_material(almacen.carpeta_sesion(carpeta_curso, sesion), MATERIAL)
    verificador.verificar.leer_configuracion(configuracion)  # si falla, falla antes de gastar tokens
    ciclo = _Ciclo(carpeta_curso, curso, sesion, rutas, consulta, contar_paginas)

    ciclo.avance("Leyendo las fuentes y redactando la lectura.")
    ciclo.datos = await agente.consultar(pedido_de_redaccion(carpeta_curso, sesion), tarea="redaccion",
                                         esquema=ESQUEMA_LECTURA, etapa="redacción", **ciclo.comun)
    limpia = await ciclo.correr(MAX_CORRECCIONES)

    # Revisor independiente: solo con la lectura limpia (PLAN.md §5.4).
    rondas: list[revisor.Resultado] = []
    aviso_del_revisor = ""
    for ronda in range(1, MAX_RONDAS + 1):
        if not limpia:
            break
        ciclo.avance(f"Revisor independiente, ronda {ronda}: una sesión nueva lee la lectura final, las fuentes y las "
                     "fichas, y hace la segunda pasada.")
        resultado = await revisor.ejecutar(
            ciclo.oraciones, ronda=ronda, carpeta=rutas["revision"] / f"ronda_{ronda}", carpeta_curso=carpeta_curso,
            curso=curso, sesion=sesion, material=CLAVE, nombre_material=MATERIAL, bloques=ciclo.bloques,
            consulta=consulta)
        rondas.append(resultado)
        ciclo.revisadas.update(resultado.revisadas)
        ciclo.respuestas2.update(resultado.respuestas)
        ciclo.avance(f"Revisor independiente, ronda {ronda}: {len(resultado.hallazgos)} hallazgos con prueba, "
                     f"{len(resultado.lista_no)} puntos de la lista sin cumplir"
                     + (f", {len(resultado.descartados)} descartados porque su prueba no existe tal cual."
                        if resultado.descartados else "."))
        if not resultado.encontrados:
            break
        ciclo.hallazgos_del_revisor += resultado.hallazgos
        lista = [f"LISTA DE VERIFICACIÓN · {p['pregunta']}: {p['detalle']}" for p in resultado.lista_no]
        limpia = await ciclo.correr(VUELTAS_POR_RONDA, iniciales=[h.describir() for h in resultado.hallazgos] + lista)
        if not limpia or resultado.encontrados < MINIMO_PARA_OTRA_RONDA:
            break
        if ronda == MAX_RONDAS:
            aviso_del_revisor = (f"El revisor de la ronda {MAX_RONDAS} encontró {resultado.encontrados} errores. "
                                 "Se corrigieron y se validaron con el verificador y la primera pasada, pero el tope es de "
                                 f"{MAX_RONDAS} rondas: ningún revisor nuevo revisó esas correcciones.")
            ciclo.avance(aviso_del_revisor)

    terminado = limpia and not ciclo.problemas
    if ciclo.resultado is not None and ciclo.respuestas2 and ciclo.bloques:
        excel.llenar_segunda_pasada(rutas["excel"], [[b.nombre, *[ciclo.respuestas2.get(b.nombre, {}).get(c, "") for c in pasada2.CAMPOS]]
                                                     for b in ciclo.bloques])
    if ciclo.resultado is not None:
        excel.agregar_historial(rutas["excel"], [
            {**h, "resolucion": f"Enviado a corrección en la vuelta {h['vuelta']}." + (" Resuelto." if terminado else "")}
            for h in ciclo.historial] + ciclo.historial_del_revisor(rondas))
        excel.llenar_revisor(rutas["excel"], ciclo.columna_del_revisor(rondas))
    final = Lectura.model_validate(ciclo.datos) if not _validar(ciclo.datos)[1] else None
    material = _actualizar(
        carpeta_curso, sesion,
        estado="verificada" if terminado else "con fallas",
        resumen=ciclo.resultado.resumen() if ciclo.resultado else "",
        problemas=ciclo.problemas,
        eliminadas_por_el_programa=ciclo.eliminadas,
        correcciones=ciclo.correcciones,
        revisor=_resumen_de_rondas(rondas, ciclo.hallazgos_del_revisor),
        aviso_del_revisor=aviso_del_revisor,
        medida_del_buscador=ciclo.medida,
        datos_agregados=ciclo.datos_agregados,
        avisos_de_diseno=ciclo.identidad.avisos,
        avisos_explicados=sum(1 for h in (ciclo.resultado.hallazgos if ciclo.resultado else [])
                              if h.nivel == "AVISO" and h.regla not in AVISOS_INFORMATIVOS),
        avisos_informativos=sum(1 for h in (ciclo.resultado.hallazgos if ciclo.resultado else [])
                                if h.nivel == "AVISO" and h.regla in AVISOS_INFORMATIVOS),
        paginas=ciclo.paginas,
        bloques=len(final.bloques) if final else 0,
        decisiones=(final.decisiones if final else []),
        agrupacion=(final.agrupacion if final else ""),
        archivos={"word": rutas["word"].name, "excel": rutas["excel"].name, "entrega": rutas["entrega"].name},
        costo=tokens.total(curso, sesion=f"S{sesion}", material=CLAVE, desde_linea=inicio),
        fecha=datetime.now().isoformat(timespec="seconds"),
    )
    material = _actualizar(carpeta_curso, sesion, entrega=_entrega(material))
    rutas["entrega"].write_text(entrega.a_markdown(material["entrega"], f"Entrega · {MATERIAL} · Sesión {sesion}"),
                                encoding="utf-8")
    ciclo.avance("Lectura lista para tu aprobación." if terminado else "La lectura quedó con problemas abiertos.")
    return _estado(carpeta_curso, sesion)


# ---------- Entrega (SPEC §8 y SKILL.md «Formato de cada entrega») ----------

def _cuantos(numero: int, palabra: str) -> str:
    return f"{numero} {palabra}" + ("" if numero == 1 else "s")


def _entrega(material: dict) -> dict:
    archivos = material["archivos"]
    paginas = material.get("paginas")
    limite = verificador.LIMITES[MATERIAL]["paginas_max"]
    lineas_archivos = [
        f"{archivos['word']}: la lectura" + (f", {paginas} páginas" if paginas else "")
        + f", con {material['bloques']} bloques.",
        f"{archivos['excel']}: el archivo de verificación, con una fila por oración y las hojas Hallazgos, "
        "Datos repetidos y Segunda pasada.",
        f"{archivos['entrega']}: esta entrega, en texto.",
    ]
    probe = [f"Conté las páginas con Word: {paginas}. El máximo es {limite}." if paginas else
             "No se pudieron contar las páginas con Word.",
             "La lectura no tiene ejercicios ni archivos de práctica que ejecutar."]
    c = material["correcciones"]
    valide = [f"Verificador: {material['resumen']}." if material["resumen"] else "El verificador no llegó a correr.",
              *([f"Avisos explicados en la hoja Hallazgos: {material['avisos_explicados']}."]
                if material.get("avisos_explicados") else []),
              *([f"Avisos informativos de relleno o palabras imprecisas: {material['avisos_informativos']}. "
                 "Están en la hoja Hallazgos; no obligan a corregir."] if material.get("avisos_informativos") else []),
              f"Errores corregidos: verificador {c['verificador']}, primera pasada {c['primera pasada']}."]
    for r in material["revisor"]:
        texto = f"Revisor independiente, ronda {r['ronda']}: {_cuantos(r['hallazgos'], 'hallazgo')}"
        if r["hallazgos"]:
            texto += (f" ({_cuantos(r['resuelto'], 'corregido')}, {_cuantos(r['rechazado'], 'rechazado')} con su pasaje, "
                      f"{_cuantos(r['abierto'], 'abierto')})")
        if r.get("lista"):
            texto += f" y {r['lista']} {'punto' if r['lista'] == 1 else 'puntos'} de la lista de verificación sin cumplir"
        texto += "."
        if r["descartados"]:
            texto += (f" El programa descartó {_cuantos(r['descartados'], 'hallazgo')} más, "
                      "porque su prueba no existe tal cual.")
        valide.append(texto)
    if material["eliminadas_por_el_programa"]:
        valide.append(f"El programa eliminó {len(material['eliminadas_por_el_programa'])} oraciones al llegar al tope de "
                      "vueltas. Están en la hoja Hallazgos con la regla «cierre por programa».")
    costo = material["costo"]
    valide.append(f"Costo de esta lectura: {costo['llamadas']} llamadas, {costo['costo_usd']:.2f} USD estimados.")

    no_pude = []
    if material.get("aviso_del_revisor"):
        no_pude.append(material["aviso_del_revisor"])
    if not material["revisor"]:
        no_pude.append("La lectura no pasó por el revisor independiente porque quedó con problemas abiertos.")
    if not paginas:
        no_pude.append("No pude contar las páginas con Word.")
    if not no_pude:
        no_pude.append("Nada: la lectura no tiene ejercicios que ejecutar, y cada oración tiene su pasaje y su veredicto.")

    decidi = list(material["decisiones"])
    if material["agrupacion"]:
        decidi.append(f"Agrupación de temas: {material['agrupacion']}")
    decidi += [f"Dato nuevo del caso, agregado a la ficha del curso: {d}" for d in material["datos_agregados"]]
    if not decidi:
        decidi.append("Nada: todo salió de las fichas y de las fuentes.")

    return entrega.componer(archivos=lineas_archivos, probe=probe, valide=valide,
                            pendientes=material["problemas"], no_pude=no_pude, decidi=decidi)


def aprobar(carpeta_curso: Path, sesion: int) -> dict:
    """El profesor aprueba la lectura desde la página (SPEC §5, paso 7)."""
    material = _estado(carpeta_curso, sesion)
    if material.get("estado") != "verificada":
        raise NoSePuedeAprobar("Solo se aprueba una lectura verificada, sin decisiones pendientes.")
    if material.get("desactualizado"):
        raise NoSePuedeAprobar("Las fichas cambiaron después de generar la lectura. Genérala de nuevo.")
    return _actualizar(carpeta_curso, sesion, estado="aprobada", aprobada=datetime.now().isoformat(timespec="seconds"))


def estado(carpeta_curso: Path, sesion: int) -> dict:
    return _estado(carpeta_curso, sesion)
