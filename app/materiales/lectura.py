"""Material 1 · Lectura: redacción, Word, validación en dos pasadas y entrega (PLAN.md §0, decisión 22).

Flujo:
1. Comprueba que las dos fichas estén confirmadas.
2. El agente redacta a partir de los pasajes de las fuentes. Puede usar sus palabras si no cambia el sentido.
3. El generador crea el Word con el diseño común.
4. Primera pasada: el verificador, sin IA. Sus fallas se corrigen y se verifica de nuevo,
   hasta VUELTAS_DEL_VERIFICADOR veces. Una falla abierta no deja aprobar la lectura.
5. Segunda pasada: la revisión del contenido, por bloque, con IA (app/validacion/revision.py).
6. Una sola corrección de los errores encontrados. Después, el verificador otra vez y la revisión solo de los
   bloques que cambiaron. Lo que quede abierto va a la entrega como pendiente: el profesor decide.
7. Entrega en el formato del SPEC §8. El profesor la aprueba desde la página.
8. El revisor independiente (Opus) no corre solo: el profesor lo lanza con un botón si quiere una segunda opinión.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from app import agente, entrega, skill, tokens
from app.fichas import almacen, verificacion
from app.materiales import docx, estilo
from app.materiales.contenido import ESQUEMA_LECTURA, Lectura
from app.validacion import excel, pasada2, revision, revisor, verificador
from app.validacion.pasajes import FICHA_DE_LA_SESION, FICHA_DEL_CURSO, Corpus

MATERIAL = "Lectura"
CLAVE = "lectura"
VUELTAS_DEL_VERIFICADOR = 3   # correcciones de fallas mecánicas antes de dejarlas abiertas (PLAN.md §0, decisión 22)
FICHAS = (FICHA_DEL_CURSO, FICHA_DE_LA_SESION)
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

class NoSePuedeEmpezar(RuntimeError):
    """Faltan fichas confirmadas (SPEC §3: ningún material empieza sin la ficha de la sesión confirmada)."""


class NoSePuedeRevisar(RuntimeError):
    """El revisor independiente opcional necesita una lectura generada sin fallas abiertas."""


class NoSePuedeAprobar(RuntimeError):
    """La lectura tiene fallas abiertas, está desactualizada o no se generó."""


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
- pasajes: los pasajes de las fuentes que usaste, para que la revisión los compare: «oracion» de la lectura que
  sostiene, la fuente, la ubicación y en «texto» el pasaje copiado de la fuente, de 40 palabras como máximo.
  Puedes escribir con tus palabras si no cambias el sentido. Deja iguales los nombres del vocabulario,
  las cifras y «debe» o «puede».
- decisiones: cada dato o decisión que las fichas no definían.
- agrupacion: si hubo más temas que bloques, cómo los agrupaste. Si no, texto vacío.
- Unas {PALABRAS_MAX} palabras como máximo en total, para no pasar de seis páginas con portada.
- Una idea por oración.
- Usa los nombres del vocabulario de la sesión tal cual y en su orden. No uses sus variantes.
- Usa comillas solo para copiar texto tal cual de una fuente.
- Si agrupas, resumes o cambias el orden de lo que dice una fuente, escribe «en este curso».
- Para afirmar algo de una fuente, apóyate en su pasaje: di lo mismo, con sus palabras o con otras más claras.
  No uses «en este curso» para evitar una fuente: úsalo solo en reglas propias del curso o para avisar que resumiste, agrupaste o reordenaste.
"""


# Los pedidos empiezan siempre con la misma parte fija (reglas, fichas y formato) y terminan con lo que
# cambia. Claude guarda unos minutos el comienzo de cada pedido y releerlo cuesta un 10 %.

def pedido_de_redaccion(carpeta_curso: Path, sesion: int) -> str:
    return "\n".join([
        _contexto(carpeta_curso, sesion),
        INSTRUCCIONES_DE_FORMATO,
        "TAREA: redacta la lectura de la sesión. Actúa como diseñador instruccional y editor senior.",
        "Antes de redactar, busca con Grep en las fuentes y lee con Read los pasajes que vas a usar.",
        "Redacta a partir de esos pasajes, no de memoria. No afirmes sobre el contenido de una fuente nada que no esté en un pasaje copiado.",
        "Antes de entregar, revisa cada bloque: qué puede hacer el alumno con él y qué oración tiene dos lecturas.",
        "Define cada término la primera vez que aparece. Corrige lo que falle.",
    ])


REGLAS_DE_CORRECCION = """REGLAS DE CORRECCIÓN
- Una FALLA del verificador se corrige siempre. Un AVISO se corrige o se explica.
- REVISIÓN · contradice la fuente: reescribe la oración para que diga lo que dice la fuente. Puedes usar tus palabras.
- REVISIÓN · dato inventado: elimina la oración, o reescríbela con lo que dice una fuente. Si es un dato ficticio
  del caso que hace falta, agrégalo en «datos_nuevos» como «Etiqueta: valor». AulaLista lo guarda en los datos
  fijos de la ficha del curso, y todos los materiales lo usan igual.
- REVISIÓN · vacío: agrega lo que falta. Para agregar, reemplaza la oración indicada por ella misma seguida de la nueva.
- REVISIÓN · ambigüedad: reescribe la oración para que tenga una sola lectura.
- REVISIÓN · inconsistencia: usa el mismo dato en todas sus apariciones, el de la ficha si existe.
- Si no hay datos nuevos, deja «datos_nuevos» vacío.
- Si mantienes una oración con AVISO, agrega en «explicaciones» la regla y la oración copiadas tal cual del problema, y por qué se mantiene.
- Cambia solo lo necesario. No cambies oraciones que ningún problema nombra.
  Puedes buscar en las fuentes con Grep y Read si necesitas un pasaje.
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
    faltan = almacen.faltantes_para(carpeta_curso, sesion, CLAVE)
    if faltan:
        raise NoSePuedeEmpezar("Completa la ficha de la sesión antes de generar la lectura: " + " ".join(faltan))
    rutas = archivos(carpeta_curso, sesion)
    rutas["contenido"].parent.mkdir(parents=True, exist_ok=True)
    _actualizar(carpeta_curso, sesion, estado="trabajando", previo="", avance=[], error="", desactualizado=False,
                entrega={}, aprobada="", revisor={})
    try:
        return await _generar(carpeta_curso, curso, sesion, rutas, consulta, contar_paginas)
    except asyncio.CancelledError:
        marcar_detenida(carpeta_curso, sesion)
        raise
    except Exception as error:
        _actualizar(carpeta_curso, sesion, estado="error", error=str(error))
        raise


def marcar_detenida(carpeta_curso: Path, sesion: int) -> bool:
    """El profesor detuvo el trabajo con el botón Detener. También libera una lectura que quedó en
    «Trabajando» porque el servidor se cerró a mitad de camino. Si lo detenido era el revisor opcional,
    la lectura vuelve al estado que tenía. Devuelve False si no estaba trabajando."""
    material = _estado(carpeta_curso, sesion)
    if material.get("estado") != "trabajando":
        return False
    _avance(carpeta_curso, sesion, "Detenido por ti. Lo que se gastó hasta aquí queda en el registro de tokens.")
    _actualizar(carpeta_curso, sesion, estado=material.get("previo") or "detenida", previo="", error="")
    return True


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
    """La lectura por bloques: la revisión del contenido trabaja bloque por bloque."""
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


REGLAS_QUE_EXPLICA_EL_PROGRAMA = ("palabra imprecisa",)


def _explicar_literales(resultado, explicaciones: dict, corpus: Corpus) -> bool:
    """Un aviso de palabra imprecisa en una oración copiada tal cual de una fuente del curso se explica solo:
    cambiarla cambiaría lo que dice la fuente (así lo hace el Excel modelo)."""
    nuevas = False
    for h in resultado.hallazgos:
        if h.nivel != "AVISO" or h.regla not in REGLAS_QUE_EXPLICA_EL_PROGRAMA or not h.oracion:
            continue
        if verificador.buscar_explicacion(h.regla, h.oracion, explicaciones):
            continue
        texto = h.oracion.split(": ", 1)[-1]
        encontrada = corpus.ubicar_en_cualquiera(texto)
        if encontrada and encontrada[0] not in FICHAS:
            fuente, ubicacion = encontrada
            explicaciones[verificador.clave_de_hallazgo(h.regla, h.oracion)] = (
                f"Es un pasaje literal de la fuente ({fuente}, {ubicacion}). Cambiarlo cambiaría lo que dice. "
                "Lo comprobó el programa.")
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


class _Trabajo:
    """Lo que se acumula mientras se genera una lectura: los datos, el último resultado del verificador,
    las explicaciones de los avisos y el historial de lo corregido."""

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
        self.contenido: Lectura | None = None
        self.explicaciones: dict[str, str] = {}
        self.historial: list[dict] = []
        self.correcciones = {"verificador": 0, "revisión": 0}
        self.datos_agregados: list[str] = []
        self.resultado = None
        self.fallas: list[str] = []      # fallas del verificador que siguen abiertas
        self.descartados: list[dict] = []
        self.vuelta = 0

    def avance(self, texto: str) -> None:
        _avance(self.carpeta_curso, self.sesion, texto)

    def contar_paginas(self, ruta: Path) -> int:
        self.paginas = self._contar_paginas(ruta)
        return self.paginas

    def corpus(self) -> Corpus:
        return Corpus.del_curso(self.carpeta_curso, self.sesion)

    # ---------- Primera pasada: el verificador ----------

    async def verificar(self) -> bool:
        """Genera el Word y corre el verificador. Corrige sus fallas hasta VUELTAS_DEL_VERIFICADOR veces.
        Devuelve True si quedó sin fallas ni avisos por explicar."""
        for intento in range(VUELTAS_DEL_VERIFICADOR + 1):
            self.vuelta += 1
            contenido, problemas = _validar(self.datos)
            completa = bool(problemas)            # la estructura solo se arregla con una corrección completa
            _guardar_json(self.rutas["contenido"], self.datos)
            if contenido is not None:
                self.contenido = contenido
                configuracion = verificador.configuracion_del_material(self.carpeta_sesion, MATERIAL)
                docx.generar_lectura(contenido, self.identidad, self.portada, self.rutas["word"])
                self.resultado = verificador.ejecutar(configuracion, [self.rutas["word"]], self.rutas["excel"],
                                                      self.explicaciones, self.contar_paginas)
                if _explicar_literales(self.resultado, self.explicaciones, self.corpus()):
                    _guardar_json(self.rutas["explicaciones"], self.explicaciones)
                    verificador.anotar_explicaciones(self.rutas["excel"], self.explicaciones)
                excel.anotar_reglas(self.rutas["excel"], AVISOS_INFORMATIVOS, NOTA_INFORMATIVA)
                fallas, avisos = _hallazgos_abiertos(self.resultado, self.explicaciones)
                self.avance(f"Verificador, vuelta {self.vuelta}: {self.resultado.resumen()}.")
                problemas = [_texto_de(h) for h in fallas + avisos]
                completa = any(not h.oracion for h in fallas)   # páginas y otros problemas del documento entero
                self.historial += _historial(fallas + avisos, self.vuelta)
            self.fallas = problemas
            if not problemas:
                return True
            if intento == VUELTAS_DEL_VERIFICADOR:
                self.avance(f"Quedan {len(problemas)} fallas del verificador después de {VUELTAS_DEL_VERIFICADOR} "
                            "correcciones. No se puede aprobar la lectura con fallas.")
                return False
            self.correcciones["verificador"] += len(problemas)
            await self.corregir(problemas, completa)
        return False

    # ---------- Segunda pasada: la revisión del contenido ----------

    async def revisar(self, bloques: list[pasada2.Bloque], etapa: str) -> revision.Resultado:
        resultado = await revision.ejecutar(
            bloques, corpus=self.corpus(), anclas=[p.model_dump() for p in self.contenido.pasajes],
            curso=self.curso, sesion=self.sesion, material=CLAVE, nombre_material=MATERIAL, etapa=etapa,
            consulta=self.consulta)
        self.descartados += resultado.descartados
        return resultado

    # ---------- Corrección ----------

    async def corregir(self, problemas: list[str], completa: bool) -> None:
        vuelta = self.vuelta
        if completa:
            self.avance(f"Corrigiendo la lectura completa: {len(problemas)} problemas.")
            respuesta = await agente.consultar(pedido_de_correccion(self.carpeta_curso, self.sesion, self.datos, problemas),
                                               tarea="correccion", esquema=ESQUEMA_CORRECCION,
                                               etapa=f"corrección completa {vuelta}", **self.comun)
            self.datos = respuesta["lectura"]
        else:
            self.avance(f"Corrigiendo {_cuantos(len(problemas), 'problema')}.")
            respuesta = await agente.consultar(pedido_de_cambios(self.carpeta_curso, self.sesion, self.datos, problemas),
                                               tarea="correccion_oraciones", esquema=ESQUEMA_CAMBIOS,
                                               etapa=f"corrección {vuelta}", **self.comun)
            self.datos, no_encontradas = aplicar_cambios(self.datos, respuesta["cambios"])
            if no_encontradas:
                self.avance(f"{_cuantos(len(no_encontradas), 'oración')} a cambiar no se encontraron en la lectura.")
        for e in respuesta["explicaciones"]:
            self.explicaciones[verificador.clave_de_hallazgo(e["regla"], e["oracion"])] = e["explicacion"]
        _guardar_json(self.rutas["explicaciones"], self.explicaciones)
        nuevos = almacen.agregar_datos_fijos(self.carpeta_curso, respuesta.get("datos_nuevos", []), f"Lectura S{self.sesion}")
        if nuevos:
            self.datos_agregados += nuevos
            for numero in almacen.sesiones_confirmadas(self.carpeta_curso):
                verificacion.escribir(self.carpeta_curso, numero)
            self.avance(f"Datos nuevos del caso agregados a la ficha del curso: {len(nuevos)}.")


def _cambio(antes: dict[str, str], despues: list[pasada2.Bloque], nombre: str) -> bool:
    """Un bloque cambió si su texto es otro o si ya no está con ese nombre."""
    actual = next((b for b in despues if b.nombre == nombre), None)
    return actual is None or actual.huella != antes.get(nombre)


async def _generar(carpeta_curso, curso, sesion, rutas, consulta, contar_paginas) -> dict:
    inicio = tokens.lineas(curso)   # para sumar solo lo que gasta esta generación
    configuracion = verificador.configuracion_del_material(almacen.carpeta_sesion(carpeta_curso, sesion), MATERIAL)
    verificador.verificar.leer_configuracion(configuracion)  # si falla, falla antes de gastar tokens
    trabajo = _Trabajo(carpeta_curso, curso, sesion, rutas, consulta, contar_paginas)

    trabajo.avance("Leyendo las fuentes y redactando la lectura.")
    trabajo.datos = await agente.consultar(pedido_de_redaccion(carpeta_curso, sesion), tarea="redaccion",
                                           esquema=ESQUEMA_LECTURA, etapa="redacción", **trabajo.comun)

    # Primera pasada: el verificador. La IA solo revisa una lectura sin fallas mecánicas (SPEC §9).
    errores: list[revision.Error] = []
    revisados = 0
    if await trabajo.verificar():
        # Segunda pasada: la revisión del contenido, por bloque.
        bloques = bloques_de(trabajo.contenido)
        revisados = len(bloques)
        trabajo.avance(f"Revisión del contenido: {_cuantos(len(bloques), 'bloque')} con sus pasajes de las fuentes.")
        resultado = await trabajo.revisar(bloques, "revisión")
        errores = resultado.errores
        trabajo.avance(f"Revisión: {_cuantos(len(errores), 'error')} con prueba"
                       + (f", {len(resultado.descartados)} descartados porque su prueba no existe." if resultado.descartados else "."))
        if errores:
            # Una sola corrección. Después, el verificador y la confirmación de los bloques que cambiaron.
            antes = {b.nombre: b.huella for b in bloques}
            trabajo.correcciones["revisión"] += len(errores)
            await trabajo.corregir([e.describir() for e in errores], completa=False)
            if await trabajo.verificar():
                despues = bloques_de(trabajo.contenido)
                cambiados = [b for b in despues if _cambio(antes, despues, b.nombre)]
                confirmacion = await trabajo.revisar(cambiados, "confirmación") if cambiados else revision.Resultado()
                trabajo.avance(f"Confirmación: {_cuantos(len(cambiados), 'bloque')} corregidos revisados de nuevo, "
                               f"{_cuantos(len(confirmacion.errores), 'error')}.")
                nuevos = list(confirmacion.errores)
                for e in errores:
                    # El mismo error sigue si la confirmación lo encuentra otra vez en su oración, o en su bloque
                    # con el mismo tipo (la oración corregida tiene otro texto).
                    sigue = next((c for c in nuevos if c.tipo == e.tipo and (c.oracion == e.oracion or c.bloque == e.bloque)), None)
                    if sigue is not None:
                        nuevos.remove(sigue)
                        e.oracion, e.explicacion, e.prueba, e.fuente = sigue.oracion, sigue.explicacion, sigue.prueba, sigue.fuente
                        e.estado, e.resolucion = "pendiente", "Sigue después de la corrección. Pendiente: decides tú."
                    elif _cambio(antes, despues, e.bloque):
                        e.estado, e.resolucion = "corregido", "Corregido y confirmado por la revisión."
                    else:
                        e.estado, e.resolucion = "pendiente", "La corrección no cambió su bloque. Pendiente: decides tú."
                for c in nuevos:
                    c.estado, c.resolucion = "pendiente", "Apareció en la confirmación. Pendiente: decides tú."
                errores += nuevos
            else:
                for e in errores:
                    e.estado, e.resolucion = "pendiente", "No se confirmó: quedaron fallas del verificador."

    pendientes = [e for e in errores if e.estado == "pendiente"]
    estado_final = "con fallas" if trabajo.fallas else ("con pendientes" if pendientes else "verificada")
    if trabajo.resultado is not None:
        excel.solo_hallazgos(rutas["excel"])
        excel.agregar_historial(rutas["excel"], [
            {**h, "resolucion": f"Enviado a corrección en la vuelta {h['vuelta']}." + ("" if trabajo.fallas else " Resuelto.")}
            for h in trabajo.historial] + _filas_de_revision(errores, trabajo.descartados, rutas["word"].name))
    final = trabajo.contenido
    material = _actualizar(
        carpeta_curso, sesion,
        estado=estado_final,
        resumen=trabajo.resultado.resumen() if trabajo.resultado else "",
        problemas=trabajo.fallas + [e.describir() for e in pendientes],
        correcciones=trabajo.correcciones,
        revision={"bloques": revisados, "errores": len(errores), "corregidos": sum(e.estado == "corregido" for e in errores),
                  "pendientes": len(pendientes), "descartados": len(trabajo.descartados)},
        datos_agregados=trabajo.datos_agregados,
        avisos_de_diseno=trabajo.identidad.avisos,
        avisos_explicados=sum(1 for h in (trabajo.resultado.hallazgos if trabajo.resultado else [])
                              if h.nivel == "AVISO" and h.regla not in AVISOS_INFORMATIVOS),
        avisos_informativos=sum(1 for h in (trabajo.resultado.hallazgos if trabajo.resultado else [])
                                if h.nivel == "AVISO" and h.regla in AVISOS_INFORMATIVOS),
        paginas=trabajo.paginas,
        bloques=len(final.bloques) if final else 0,
        decisiones=(final.decisiones if final else []),
        agrupacion=(final.agrupacion if final else ""),
        archivos={"word": rutas["word"].name, "excel": rutas["excel"].name, "entrega": rutas["entrega"].name},
        costo=tokens.total(curso, sesion=f"S{sesion}", material=CLAVE, desde_linea=inicio),
        fecha=datetime.now().isoformat(timespec="seconds"),
    )
    _escribir_entrega(carpeta_curso, sesion, material)
    trabajo.avance({"verificada": "Lectura lista para tu aprobación.",
                    "con pendientes": f"Lectura lista, con {_cuantos(len(pendientes), 'pendiente')} para que decidas.",
                    "con fallas": "La lectura quedó con fallas del verificador."}[estado_final])
    return _estado(carpeta_curso, sesion)


def _filas_de_revision(errores: list[revision.Error], descartados: list[dict], seccion: str) -> list[dict]:
    """Filas de la hoja Hallazgos para la revisión del contenido."""
    filas = [{"nivel": "REVISIÓN", "seccion": f"{seccion} · {e.bloque}", "oracion": e.oracion,
              "regla": f"revisión: {e.tipo}",
              "detalle": e.explicacion + (f" Prueba: «{e.prueba}» ({e.fuente})." if e.prueba else ""),
              "resolucion": e.resolucion or "Pendiente: decides tú."} for e in errores]
    filas += [{"nivel": "REVISIÓN", "seccion": f"{seccion} · {d['bloque']}", "oracion": d["oracion"],
               "regla": f"revisión: {d['tipo']}", "detalle": d["explicacion"],
               "resolucion": f"Descartado por el programa: {d['motivo']}"} for d in descartados]
    return filas


def _escribir_entrega(carpeta_curso: Path, sesion: int, material: dict) -> dict:
    material = _actualizar(carpeta_curso, sesion, entrega=_entrega(material))
    archivos(carpeta_curso, sesion)["entrega"].write_text(
        entrega.a_markdown(material["entrega"], f"Entrega · {MATERIAL} · Sesión {sesion}"), encoding="utf-8")
    return material


# ---------- Revisor independiente opcional (PLAN.md §0, decisión 22) ----------

async def revisar_con_revisor(carpeta_curso: Path, curso: str, sesion: int, consulta=agente.query) -> dict:
    """Una sesión nueva de Opus revisa la lectura ya generada. No corrige: lo que encuentra queda como
    pendiente para que el profesor decida."""
    material = _estado(carpeta_curso, sesion)
    previo = material.get("estado")
    if previo not in ("verificada", "con pendientes", "aprobada"):
        raise NoSePuedeRevisar("El revisor independiente revisa una lectura generada y sin fallas del verificador.")
    rutas = archivos(carpeta_curso, sesion)
    contenido = Lectura.model_validate(_leer_json(rutas["contenido"]))
    oraciones = _leer_json(rutas["excel"].with_suffix(".json"))["oraciones"]
    inicio = tokens.lineas(curso)
    _actualizar(carpeta_curso, sesion, estado="trabajando", previo=previo)
    _avance(carpeta_curso, sesion, "Revisor independiente: una sesión nueva lee la lectura final, las fuentes y las fichas.")
    try:
        resultado = await revisor.ejecutar(
            oraciones, ronda=1, carpeta=rutas["revision"] / "ronda_1", carpeta_curso=carpeta_curso, curso=curso,
            sesion=sesion, material=CLAVE, nombre_material=MATERIAL, bloques=bloques_de(contenido), consulta=consulta)
    except asyncio.CancelledError:
        marcar_detenida(carpeta_curso, sesion)
        raise
    except Exception as error:
        _avance(carpeta_curso, sesion, f"El revisor independiente se detuvo por un error: {error}")
        _actualizar(carpeta_curso, sesion, estado=previo, previo="")
        raise
    hallazgos = resultado.hallazgos
    excel.agregar_historial(rutas["excel"], [
        {"nivel": "REVISOR", "seccion": rutas["word"].name, "oracion": h.oracion, "regla": f"revisor independiente: {h.defecto}",
         "detalle": f"{h.explicacion} Prueba: «{h.prueba}» ({h.fuente}).", "resolucion": "Pendiente: decides tú."}
        for h in hallazgos] + [
        {"nivel": "REVISOR", "seccion": rutas["word"].name, "oracion": "", "regla": "revisor independiente: lista de verificación",
         "detalle": f"{p['pregunta']} {p['detalle']}", "resolucion": "Informativo."} for p in resultado.lista_no])
    estado_final = "con pendientes" if hallazgos else previo
    material = _actualizar(
        carpeta_curso, sesion, estado=estado_final, previo="",
        aprobada="" if hallazgos else material.get("aprobada", ""),
        problemas=material.get("problemas", []) + [h.describir() for h in hallazgos],
        revisor={"hallazgos": len(hallazgos), "descartados": len(resultado.descartados), "lista": len(resultado.lista_no),
                 "costo": tokens.total(curso, sesion=f"S{sesion}", material=CLAVE, desde_linea=inicio)})
    _escribir_entrega(carpeta_curso, sesion, material)
    _avance(carpeta_curso, sesion, f"Revisor independiente: {_cuantos(len(hallazgos), 'hallazgo')} con prueba"
            + (", pendientes para que decidas." if hallazgos else "."))
    return _estado(carpeta_curso, sesion)


# ---------- Entrega (SPEC §8 y SKILL.md «Formato de cada entrega») ----------

def _cuantos(numero: int, palabra: str) -> str:
    if palabra.endswith("ón"):
        plural = palabra[:-2] + "ones"
    else:
        plural = palabra + ("es" if palabra[-1] in "rnl" else "s")
    return f"{numero} {palabra if numero == 1 else plural}"


def _entrega(material: dict) -> dict:
    archivos_ = material["archivos"]
    paginas = material.get("paginas")
    limite = verificador.LIMITES[MATERIAL]["paginas_max"]
    lineas_archivos = [
        f"{archivos_['word']}: la lectura" + (f", {paginas} páginas" if paginas else "")
        + f", con {material['bloques']} bloques.",
        f"{archivos_['excel']}: el archivo de verificación, con la hoja Hallazgos.",
        f"{archivos_['entrega']}: esta entrega, en texto.",
    ]
    probe = [f"Conté las páginas con Word: {paginas}. El máximo es {limite}." if paginas else
             "No se pudieron contar las páginas con Word.",
             "La lectura no tiene ejercicios ni archivos de práctica que ejecutar."]
    c = material["correcciones"]
    r = material.get("revision") or {}
    valide = [f"Verificador: {material['resumen']}." if material["resumen"] else "El verificador no llegó a correr.",
              *([f"Avisos explicados en la hoja Hallazgos: {material['avisos_explicados']}."]
                if material.get("avisos_explicados") else []),
              *([f"Avisos informativos de relleno o palabras imprecisas: {material['avisos_informativos']}. "
                 "Están en la hoja Hallazgos; no obligan a corregir."] if material.get("avisos_informativos") else []),
              f"Fallas del verificador corregidas: {c['verificador']}."]
    if r.get("bloques"):
        texto = f"Revisión del contenido: {_cuantos(r['bloques'], 'bloque')}, {_cuantos(r['errores'], 'error')} con prueba"
        if r["errores"]:
            texto += f" ({_cuantos(r['corregidos'], 'corregido')} y {_cuantos(r['pendientes'], 'pendiente')})"
        valide.append(texto + ".")
        if r.get("descartados"):
            valide.append(f"El programa descartó {_cuantos(r['descartados'], 'error')} de la revisión porque su prueba "
                          "no existe.")
    rev = material.get("revisor") or {}
    if rev:
        valide.append(f"Revisor independiente (lo pediste tú): {_cuantos(rev['hallazgos'], 'hallazgo')} con prueba"
                      + (f", {rev['descartados']} descartados" if rev.get("descartados") else "")
                      + f". Costo: {rev['costo']['costo_usd']:.2f} USD estimados.")
    costo = material["costo"]
    valide.append(f"Costo de esta lectura: {costo['llamadas']} llamadas, {costo['costo_usd']:.2f} USD estimados.")

    no_pude = []
    if not r.get("bloques"):
        no_pude.append("La revisión del contenido no corrió porque quedaron fallas del verificador.")
    if not paginas:
        no_pude.append("No pude contar las páginas con Word.")
    if not no_pude:
        no_pude.append("Nada: la lectura no tiene ejercicios que ejecutar.")

    decidi = list(material["decisiones"])
    if material["agrupacion"]:
        decidi.append(f"Agrupación de temas: {material['agrupacion']}")
    decidi += [f"Dato nuevo del caso, agregado a la ficha del curso: {d}" for d in material["datos_agregados"]]
    if not decidi:
        decidi.append("Nada: todo salió de las fichas y de las fuentes.")

    return entrega.componer(archivos=lineas_archivos, probe=probe, valide=valide,
                            pendientes=material["problemas"], no_pude=no_pude, decidi=decidi)


def aprobar(carpeta_curso: Path, sesion: int) -> dict:
    """El profesor aprueba la lectura desde la página (SPEC §5, paso 7). Una lectura con pendientes de la
    revisión también se puede aprobar: el profesor ya los vio. Las fallas del verificador no."""
    material = _estado(carpeta_curso, sesion)
    if material.get("estado") not in ("verificada", "con pendientes"):
        raise NoSePuedeAprobar("Solo se aprueba una lectura generada y sin fallas del verificador.")
    if material.get("desactualizado"):
        raise NoSePuedeAprobar("Las fichas cambiaron después de generar la lectura. Genérala de nuevo.")
    return _actualizar(carpeta_curso, sesion, estado="aprobada", aprobada=datetime.now().isoformat(timespec="seconds"))


def estado(carpeta_curso: Path, sesion: int) -> dict:
    return _estado(carpeta_curso, sesion)
