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
import shutil
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from app import agente, entrega, skill, tokens
from app.fichas import almacen, referencia, verificacion
from app.materiales import comun, docx, estilo
from app.materiales.contenido import ESQUEMA_LECTURA, Lectura
from app.validacion import excel, pasada2, revision, revisor, verificador
from app.validacion.pasajes import FICHA_DE_LA_SESION, FICHA_DEL_CURSO, Corpus

MATERIAL = "Lectura"
CLAVE = "lectura"
VUELTAS_DEL_VERIFICADOR = 3   # correcciones de fallas mecánicas antes de dejarlas abiertas (PLAN.md §0, decisión 22)
FICHAS = (FICHA_DEL_CURSO, FICHA_DE_LA_SESION)
PALABRAS_MAX = 1500  # sin material de referencia: orientación para no pasar de seis páginas con portada
BLOQUES_SIN_REFERENCIA = (2, 4)
# Secciones de SKILL.md que usa la redacción. Se comprueban antes de gastar tokens, junto con las de la revisión
# y las del revisor (propuesta 1).
SECCIONES_DE_LA_SKILL = ("Reglas comunes", "Paso 3 · Vocabulario de la sesión", "Material 1 · Lectura")

ESQUEMA_CORRECCION = comun.esquema_de_correccion("lectura", ESQUEMA_LECTURA)
ESQUEMA_CAMBIOS = comun.ESQUEMA_CAMBIOS

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
    return comun.estado(carpeta_curso, sesion, CLAVE)


def _actualizar(carpeta_curso: Path, sesion: int, **cambios) -> dict:
    return comun.actualizar(carpeta_curso, sesion, CLAVE, **cambios)


def _avance(carpeta_curso: Path, sesion: int, texto: str) -> None:
    comun.avance(carpeta_curso, sesion, CLAVE, texto)


# ---------- Pedidos al agente ----------

def _referencia(carpeta_curso: Path, sesion: int) -> tuple[list[referencia.Tramo], list[str]]:
    """Tramos del material de referencia y exclusiones de la ficha de la sesión (decisión 23)."""
    ficha = almacen.cargar(carpeta_curso, "sesion", sesion)
    return referencia.interpretar(carpeta_curso, ficha)[0], referencia.exclusiones(ficha)


def _contexto(carpeta_curso: Path, sesion: int) -> str:
    ficha_curso = almacen.ruta_ficha(carpeta_curso, "curso", extension=".md").read_text(encoding="utf-8")
    ficha_sesion = almacen.ruta_ficha(carpeta_curso, "sesion", sesion, ".md").read_text(encoding="utf-8")
    fuentes = verificacion.fuentes_utilizables(carpeta_curso)
    tramos, excluir = _referencia(carpeta_curso, sesion)
    lineas_referencia = []
    if tramos:
        lineas_referencia = [
            "", "MATERIAL DE REFERENCIA DE LA SESIÓN (en los .jsonl, cada pasaje trae su «pagina»):",
            *[f"- {t.describir()}" for t in tramos],
            "EXCLUSIONES (no las uses):",
            *([f"- {e}" for e in excluir] or ["- Ninguna: usa todo el material de referencia."]),
        ]
    return "\n".join([
        "REGLAS DE LA SKILL (son obligatorias):",
        skill.secciones(*SECCIONES_DE_LA_SKILL),
        "",
        "FICHA DEL CURSO (confirmada):", ficha_curso,
        "FICHA DE LA SESIÓN (confirmada):", ficha_sesion,
        estilo.guia_de_tono(carpeta_curso),
        "FUENTES DEL CURSO que puedes citar (archivos .jsonl de esta carpeta, un pasaje por línea con su ubicación):",
        *([f"- {f}" for f in fuentes] or ["- (ninguna: no cites fuentes)"]),
        *lineas_referencia,
    ])


FORMATO_COMUN = """
CÓMO ENTREGAR LA LECTURA
- Devuelve solo los datos del esquema. Un programa crea el Word: la portada, el encabezado,
  el título «Idea central» y los títulos de los recuadros «Aplícalo así» y «Cuidado con» los pone él.
- idea_central: de 2 a 3 oraciones.
{bloques}
  El ejemplo usa un caso distinto al de los ejercicios del laboratorio y no da la respuesta de ningún ejercicio.
  Usa «tabla» solo si ayuda a entender; si no, déjala en null. Máximo 4 columnas.
- aplicalo.plantilla: la técnica o plantilla lista para copiar, una línea por elemento, sin espacios por llenar.
- cuidado: de 1 a 3 riesgos de una línea cada uno.
- pasajes: los pasajes de las fuentes que usaste, para que la revisión los compare: «oracion» de la lectura que
  sostiene, la fuente, la ubicación y en «texto» el pasaje copiado de la fuente, de 40 palabras como máximo.
  Puedes escribir con tus palabras si no cambias el sentido. Deja iguales los nombres del vocabulario,
  las cifras y «debe» o «puede».
- decisiones: una entrada por punto, con «texto» y «tipo»:
  - «sin fuente»: afirmas algo del tema que no está en ninguna fuente ni ficha: una definición, una deducción
    o una cifra propia. Copia la oración. El profesor decide si queda.
  - «decisión»: te apartas de las fichas o de las fuentes, o eliges algo que las fichas no definían y que cambia
    lo que lee el alumno: omites o agregas un tema, cambias el orden, agregas un dato ficticio del caso.
  - «nota»: solo describes lo que hiciste sin apartarte de las fichas ni de las fuentes.
- agrupacion: si hubo más temas que bloques, cómo los agrupaste. Si no, texto vacío.
{extension}
- Una idea por oración.
- Usa los nombres del vocabulario de la sesión tal cual y en su orden. No uses sus variantes.
- Usa comillas solo para copiar texto tal cual de una fuente.
- Si agrupas, resumes o cambias el orden de lo que dice una fuente, escribe «en este curso».
- Para afirmar algo de una fuente, apóyate en su pasaje: di lo mismo, con sus palabras o con otras más claras.
  No uses «en este curso» para evitar una fuente: úsalo solo en reglas propias del curso o para avisar que resumiste, agrupaste o reordenaste.
"""

SIN_REFERENCIA = {
    "bloques": "- bloques: de 2 a 4, en el orden de la ficha de la sesión. Cada uno con subtítulo, párrafos breves y un ejemplo.",
    "extension": f"- Unas {PALABRAS_MAX} palabras como máximo en total, para no pasar de seis páginas con portada.",
}
CON_REFERENCIA = {
    "bloques": ("- bloques: si la ficha de la sesión trae bloques, síguelos en su orden. Si no, agrupa los temas del\n"
                "  material de referencia en bloques, en el orden de la referencia, y explica la agrupación en «agrupacion».\n"
                "  Cada bloque con subtítulo, párrafos breves y un ejemplo."),
    "extension": ("- Cubre todos los temas del material de referencia, menos las exclusiones. No hay un máximo de páginas:\n"
                  "  la extensión sale de esos temas. Explica cada tema con lo necesario para entenderlo y aplicarlo, sin relleno.\n"
                  "  Si dejas fuera un tema que no está en las exclusiones, anótalo como «decisión»."),
}


def instrucciones_de_formato(con_referencia: bool) -> str:
    return FORMATO_COMUN.format(**(CON_REFERENCIA if con_referencia else SIN_REFERENCIA))


def _formato(carpeta_curso: Path, sesion: int) -> str:
    return instrucciones_de_formato(bool(_referencia(carpeta_curso, sesion)[0]))


# Los pedidos empiezan siempre con la misma parte fija (reglas, fichas y formato) y terminan con lo que
# cambia. Claude guarda unos minutos el comienzo de cada pedido y releerlo cuesta un 10 %.

def pedido_de_redaccion(carpeta_curso: Path, sesion: int) -> str:
    return "\n".join([
        _contexto(carpeta_curso, sesion),
        _formato(carpeta_curso, sesion),
        "TAREA: redacta la lectura de la sesión. Actúa como diseñador instruccional y editor senior.",
        "Antes de redactar, busca con Grep en las fuentes y lee con Read los pasajes que vas a usar.",
        "Si la sesión tiene material de referencia, lee sus páginas y no uses las exclusiones.",
        "Redacta a partir de esos pasajes, no de memoria. No afirmes sobre el contenido de una fuente nada que no esté en un pasaje copiado.",
        "Antes de entregar, revisa cada bloque: qué puede hacer el alumno con él y qué oración tiene dos lecturas.",
        "Define cada término la primera vez que aparece. Corrige lo que falle.",
    ])


REGLAS_DE_CORRECCION = comun.REGLAS_DE_CORRECCION


def pedido_de_cambios(carpeta_curso: Path, sesion: int, contenido: dict, problemas: list[str]) -> str:
    """Corrección barata: devuelve solo las oraciones que cambian."""
    return "\n".join([
        _contexto(carpeta_curso, sesion),
        _formato(carpeta_curso, sesion),
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
        _formato(carpeta_curso, sesion),
        REGLAS_DE_CORRECCION,
        "Devuelve la lectura completa con el mismo esquema.",
        "",
        "LECTURA ACTUAL:",
        json.dumps(contenido, ensure_ascii=False),
        "",
        "PROBLEMAS QUE ENCONTRÓ LA VALIDACIÓN:",
        *[f"- {p}" for p in problemas],
    ])


def _validar(datos: dict, con_referencia: bool = False) -> tuple[Lectura | None, list[str]]:
    try:
        lectura = Lectura.model_validate(datos)
    except ValidationError as error:
        return None, [f"FALLA · estructura · {'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()]
    minimo, maximo = BLOQUES_SIN_REFERENCIA
    if not con_referencia and not minimo <= len(lectura.bloques) <= maximo:
        return None, [f"FALLA · estructura · bloques: tiene {len(lectura.bloques)}; sin material de referencia "
                      f"van de {minimo} a {maximo}."]
    return lectura, []




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
        contacto=almacen.valor(ficha_curso, "portada.contacto").strip(),
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
                entrega={}, aprobada="", revisor={}, corrida_desde=tokens.lineas(curso))
    try:
        return await _generar(carpeta_curso, curso, sesion, rutas, consulta, contar_paginas)
    except asyncio.CancelledError:
        marcar_detenida(carpeta_curso, sesion)
        raise
    except Exception as error:
        _actualizar(carpeta_curso, sesion, estado="error", error=str(error))
        raise


def gasto_de_la_corrida(carpeta_curso: Path, curso: str, sesion: int) -> dict | None:
    return comun.gasto_de_la_corrida(carpeta_curso, curso, sesion, CLAVE)


def marcar_detenida(carpeta_curso: Path, sesion: int) -> bool:
    return comun.marcar_detenida(carpeta_curso, sesion, CLAVE)


_leer_json, _guardar_json = comun.leer_json, comun.guardar_json

AVISOS_INFORMATIVOS, NOTA_INFORMATIVA = comun.AVISOS_INFORMATIVOS, comun.NOTA_INFORMATIVA
_hallazgos_abiertos, _texto_de = comun.hallazgos_abiertos, comun.texto_de
_cuantos = comun.cuantos


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


_explicar_literales, _historial = comun.explicar_literales, comun.historial
aplicar_cambios = comun.aplicar_cambios


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
        self.tramos, self.exclusiones = _referencia(carpeta_curso, sesion)
        self.con_referencia = bool(self.tramos)
        # Con material de referencia no hay máximo de páginas (decisión 23): el verificador no las limita.
        self.limites = {} if self.con_referencia else None
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
            contenido, problemas = _validar(self.datos, self.con_referencia)
            completa = bool(problemas)            # la estructura solo se arregla con una corrección completa
            _guardar_json(self.rutas["contenido"], self.datos)
            if contenido is not None:
                self.contenido = contenido
                configuracion = verificador.configuracion_del_material(self.carpeta_sesion, MATERIAL, limites=self.limites)
                docx.generar_lectura(contenido, self.identidad, self.portada, self.rutas["word"])
                self.resultado = verificador.ejecutar(configuracion, [self.rutas["word"]], self.rutas["excel"],
                                                      self.explicaciones, self.contar_paginas)
                if self.con_referencia:
                    self.contar_paginas(self.rutas["word"])   # sin límite, pero la entrega dice cuántas son
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


def _limpiar(rutas: dict[str, Path]) -> None:
    """Borra lo que dejó la generación anterior, para que la carpeta muestre solo la lectura nueva (propuesta 6).
    Un archivo abierto en Word u OneDrive puede negar el borrado: se deja y la generación lo reescribe."""
    carpeta = rutas["contenido"].parent
    for ruta in (rutas["word"], rutas["excel"], rutas["excel"].with_suffix(".json"), rutas["entrega"],
                 rutas["contenido"], rutas["explicaciones"], carpeta / "pasada1.json"):
        try:
            ruta.unlink(missing_ok=True)
        except OSError:
            pass
    shutil.rmtree(rutas["revision"], ignore_errors=True)


async def _generar(carpeta_curso, curso, sesion, rutas, consulta, contar_paginas) -> dict:
    inicio = tokens.lineas(curso)   # para sumar solo lo que gasta esta generación
    # Antes de gastar tokens: la skill tiene todo lo que se usará y la configuración del verificador se lee.
    skill.comprobar(secciones=SECCIONES_DE_LA_SKILL + pasada2.SECCIONES_DE_LA_SKILL + revisor.SECCIONES_DE_LA_SKILL,
                    subsecciones=revisor.SUBSECCIONES_DE_LA_SKILL)
    trabajo = _Trabajo(carpeta_curso, curso, sesion, rutas, consulta, contar_paginas)
    configuracion = verificador.configuracion_del_material(trabajo.carpeta_sesion, MATERIAL, limites=trabajo.limites)
    verificador.verificar.leer_configuracion(configuracion)
    _limpiar(rutas)

    trabajo.avance("Leyendo las fuentes y redactando la lectura.")
    trabajo.datos = await agente.consultar(pedido_de_redaccion(carpeta_curso, sesion), tarea="redaccion",
                                           esquema=ESQUEMA_LECTURA, etapa="redacción", **trabajo.comun)

    # Primera pasada: el verificador. La IA solo revisa una lectura sin fallas mecánicas (SPEC §9).
    errores: list[revision.Error] = []
    revisados = 0
    if await trabajo.verificar():
        # Segunda pasada: la revisión del contenido, por bloque, con una sola corrección.
        errores, revisados = await comun.revisar_y_corregir(trabajo, bloques_de)

    pendientes = [e for e in errores if e.estado == "pendiente"]
    final = trabajo.contenido
    decisiones = final.decisiones if final else []
    # Lo que el redactor afirmó sin fuente lo decide el profesor (propuesta 4); sus notas van al Excel (propuesta 5).
    sin_fuente = [f"Afirmación sin fuente: {d.texto}" for d in decisiones if d.tipo == "sin fuente"]
    estado_final = "con fallas" if trabajo.fallas else ("con pendientes" if pendientes or sin_fuente else "verificada")
    if trabajo.resultado is not None:
        excel.solo_hallazgos(rutas["excel"])
        excel.agregar_historial(rutas["excel"], [
            {**h, "resolucion": f"Enviado a corrección en la vuelta {h['vuelta']}." + ("" if trabajo.fallas else " Resuelto.")}
            for h in trabajo.historial] + _filas_de_revision(errores, trabajo.descartados, rutas["word"].name)
            + _filas_de_decisiones(decisiones, rutas["word"].name))
    material = _actualizar(
        carpeta_curso, sesion,
        estado=estado_final,
        resumen=trabajo.resultado.resumen() if trabajo.resultado else "",
        problemas=trabajo.fallas + [e.describir() for e in pendientes] + sin_fuente,
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
        decisiones=[d.model_dump() for d in decisiones],
        referencia=[t.describir() for t in trabajo.tramos],
        exclusiones=trabajo.exclusiones,
        agrupacion=(final.agrupacion if final else ""),
        archivos={"word": rutas["word"].name, "excel": rutas["excel"].name, "entrega": rutas["entrega"].name},
        costo=tokens.total(curso, sesion=f"S{sesion}", material=CLAVE, desde_linea=inicio),
        fecha=datetime.now().isoformat(timespec="seconds"),
    )
    _escribir_entrega(carpeta_curso, sesion, material)
    trabajo.avance({"verificada": "Lectura lista para tu aprobación.",
                    "con pendientes": f"Lectura lista, con {_cuantos(len(pendientes) + len(sin_fuente), 'pendiente')} "
                                      "para que decidas.",
                    "con fallas": "La lectura quedó con fallas del verificador."}[estado_final])
    return _estado(carpeta_curso, sesion)


_filas_de_revision, _filas_de_decisiones = comun.filas_de_revision, comun.filas_de_decisiones


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

def _entrega(material: dict) -> dict:
    archivos_ = material["archivos"]
    paginas = material.get("paginas")
    limite = verificador.LIMITES[MATERIAL]["paginas_max"]
    referencia_ = material.get("referencia") or []
    lineas_archivos = [
        f"{archivos_['word']}: la lectura" + (f", {paginas} páginas" if paginas else "")
        + f", con {material['bloques']} bloques.",
        f"{archivos_['excel']}: el archivo de verificación, con la hoja Hallazgos.",
        f"{archivos_['entrega']}: esta entrega, en texto.",
    ]
    if not paginas:
        conte = "No se pudieron contar las páginas con Word."
    elif referencia_:
        conte = (f"Conté las páginas con Word: {paginas}. No hay máximo: la extensión sale del material de "
                 f"referencia ({'; '.join(referencia_)})"
                 + (f", sin las exclusiones de la ficha: {'; '.join(material['exclusiones'])}."
                    if material.get("exclusiones") else "."))
    else:
        conte = f"Conté las páginas con Word: {paginas}. El máximo es {limite}."
    probe = [conte, "La lectura no tiene ejercicios ni archivos de práctica que ejecutar."]
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

    # Lecturas anteriores a la decisión 24 guardaban texto suelto: cuenta como «decisión».
    decisiones = [{"texto": d, "tipo": "decisión"} if isinstance(d, str) else d for d in material["decisiones"]]
    decidi = [d["texto"] for d in decisiones if d["tipo"] == "decisión"]
    if material["agrupacion"]:
        decidi.append(f"Agrupación de temas: {material['agrupacion']}")
    decidi += [f"Dato nuevo del caso, agregado a la ficha del curso: {d}" for d in material["datos_agregados"]]
    if not decidi:
        decidi.append("Nada que revisar: todo salió de las fichas y de las fuentes. Las notas del redactor están en "
                      "la hoja Hallazgos.")

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


def faltan(carpeta_curso: Path, sesion: int) -> dict[str, list[str]]:
    """Lo que falta para generar la lectura: en «ficha», lo que se completa en la ficha de la sesión."""
    return {"ficha": almacen.faltantes_para(carpeta_curso, sesion, CLAVE), "otros": []}
