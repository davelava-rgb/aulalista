"""Material 1 · Lectura: redacción, Word con la identidad visual y verificador (etapa 5a).

Flujo:
1. Comprueba que las dos fichas estén confirmadas.
2. El agente copia de las fuentes los pasajes que va a usar y redacta a partir de ellos.
3. El generador crea el Word con el diseño común.
4. El verificador revisa el Word. Si hay fallas o avisos sin explicar, el agente corrige
   y se vuelve a generar y verificar, hasta MAX_CORRECCIONES veces.
Las dos pasadas, el revisor independiente y el formato de entrega llegan en las etapas 5b a 5d.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from app import agente, skill
from app.fichas import almacen, verificacion
from app.materiales import docx, estilo
from app.materiales.contenido import ESQUEMA_LECTURA, Lectura
from app.validacion import excel, pasada1, pasada2, verificador
from app.validacion.pasajes import Corpus

MATERIAL = "Lectura"
CLAVE = "lectura"
MAX_CORRECCIONES = 5  # tope de vueltas del ciclo de corrección (PLAN.md §5.5)
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


class NoSePuedeEmpezar(RuntimeError):
    """Faltan fichas confirmadas (SPEC §3: ningún material empieza sin la ficha de la sesión confirmada)."""


def carpeta_materiales(carpeta_curso: Path, sesion: int) -> Path:
    return almacen.carpeta_sesion(carpeta_curso, sesion) / "materiales"


def archivos(carpeta_curso: Path, sesion: int) -> dict[str, Path]:
    carpeta = carpeta_materiales(carpeta_curso, sesion)
    return {
        "word": carpeta / f"S{sesion}_Lectura.docx",
        "excel": carpeta / f"S{sesion}_Lectura_Verificacion.xlsx",
        "contenido": carpeta / "lectura" / "contenido.json",
        "explicaciones": carpeta / "lectura" / "explicaciones.json",
        "pasada1": carpeta / "lectura" / "pasada1.json",
        "pasada2": carpeta / "lectura" / "pasada2.json",
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
- pasajes: cada pasaje que copiaste de una fuente, tal cual, con su fuente y su ubicación.
- decisiones: cada dato o decisión que las fichas no definían.
- agrupacion: si hubo más temas que bloques, cómo los agrupaste. Si no, texto vacío.
- Unas {PALABRAS_MAX} palabras como máximo en total, para no pasar de seis páginas con portada.
- Una idea por oración y 25 palabras como máximo por oración.
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
- SEGUNDA PASADA · relleno: elimina la oración. · ambigüedad: reescríbela para que tenga una sola lectura.
  · inconsistencia: usa el mismo dato en todas sus apariciones, el de la ficha si existe.
  · vacío: agrega lo que falta. Para agregar, reemplaza la oración indicada por ella misma seguida de la nueva.
- LISTA DE VERIFICACIÓN: corrige lo que la pregunta señala, con el menor cambio posible.
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
    _actualizar(carpeta_curso, sesion, estado="trabajando", avance=[], error="", desactualizado=False)
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


def _hallazgos_abiertos(resultado, explicaciones) -> tuple[list, list]:
    """Fallas del verificador y avisos todavía sin explicar."""
    fallas = [h for h in resultado.hallazgos if h.nivel == "FALLA"]
    avisos = [h for h in resultado.hallazgos
              if h.nivel == "AVISO" and not verificador.buscar_explicacion(h.regla, h.oracion, explicaciones)]
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


async def _generar(carpeta_curso, curso, sesion, rutas, consulta, contar_paginas) -> dict:
    carpeta_sesion = almacen.carpeta_sesion(carpeta_curso, sesion)
    identidad = estilo.desde_ficha(carpeta_curso)
    portada = _portada(carpeta_curso, sesion)
    configuracion = verificador.configuracion_del_material(carpeta_sesion, MATERIAL)
    verificador.verificar.leer_configuracion(configuracion)  # si falla, falla antes de gastar tokens
    comun = {"curso": curso, "sesion": f"S{sesion}", "material": CLAVE,
             "cwd": carpeta_curso / "fuentes_texto", "herramientas": ("Read", "Grep", "Glob"), "consulta": consulta}

    _avance(carpeta_curso, sesion, "Leyendo las fuentes y redactando la lectura.")
    datos = await agente.consultar(pedido_de_redaccion(carpeta_curso, sesion), tarea="redaccion",
                                   esquema=ESQUEMA_LECTURA, etapa="redacción", **comun)
    explicaciones: dict[str, str] = {}
    anteriores = _leer_json(rutas["pasada1"])   # solo guarda oraciones que coinciden con su fuente
    historial: list[dict] = []
    correcciones = {"verificador": 0, "primera pasada": 0, "segunda pasada": 0}
    anteriores2 = _leer_json(rutas["pasada2"])
    respuestas2: dict[str, dict] = {}
    bloques: list = []
    medida = {}
    datos_agregados: list[str] = []
    resultado, problemas = None, []
    for vuelta in range(1, MAX_CORRECCIONES + 2):
        contenido, problemas = _validar(datos)
        completa = bool(problemas)            # la estructura solo se arregla con una corrección completa
        _guardar_json(rutas["contenido"], datos)
        if contenido is not None:
            configuracion = verificador.configuracion_del_material(carpeta_sesion, MATERIAL)
            docx.generar_lectura(contenido, identidad, portada, rutas["word"])
            resultado = verificador.ejecutar(configuracion, [rutas["word"]], rutas["excel"], explicaciones, contar_paginas)
            fallas, avisos = _hallazgos_abiertos(resultado, explicaciones)
            _avance(carpeta_curso, sesion, f"Verificador, vuelta {vuelta}: {resultado.resumen()}.")
            if fallas:
                # Las fallas mecánicas se corrigen antes de usar IA para revisar (SPEC §9).
                problemas = [_texto_de(h) for h in fallas + avisos]
                completa = any(not h.oracion for h in fallas)   # páginas y otros problemas del documento entero
                historial += _historial(fallas + avisos, vuelta)
                correcciones["verificador"] += len(problemas)
            else:
                # Las dos pasadas corren juntas y sus problemas van en una sola corrección.
                oraciones = _leer_json(rutas["excel"].with_suffix(".json"))["oraciones"]
                bloques = bloques_de(contenido)
                pasada, segunda = await asyncio.gather(
                    pasada1.ejecutar(
                        oraciones, titulos=_titulos(contenido), corpus=Corpus.del_curso(carpeta_curso, sesion),
                        anteriores=anteriores, curso=curso, sesion=sesion, material=CLAVE,
                        instruccion_sin_ejecucion=INSTRUCCION_SIN_EJECUCION, consulta=consulta),
                    pasada2.ejecutar(
                        bloques, anteriores=anteriores2, contexto_fijo=_contexto(carpeta_curso, sesion),
                        curso=curso, sesion=sesion, material=MATERIAL, consulta=consulta),
                )
                anteriores = {h: f for h, f in pasada.filas.items() if f["veredicto"] == "coincide"}
                _guardar_json(rutas["pasada1"], anteriores)
                excel.llenar_oraciones(rutas["excel"], oraciones, pasada.filas)
                anteriores2 = segunda.guardar(bloques)
                _guardar_json(rutas["pasada2"], anteriores2)
                respuestas2 = segunda.respuestas

                veraces = pasada.problemas(oraciones)
                valor = ([f"SEGUNDA PASADA · {d['tipo']} · «{d['oracion']}»: {d['detalle']}" for d in segunda.defectos]
                         + [f"LISTA DE VERIFICACIÓN · {p['pregunta']}: {p['detalle']}" for p in segunda.lista_no])
                # Los avisos sin explicar van en la misma corrección: no gastan una vuelta propia.
                problemas = [_describir_veracidad(v) for v in veraces] + [_texto_de(h) for h in avisos] + valor
                historial += [{"nivel": "FALLA", "seccion": v["seccion"], "oracion": v["texto"],
                               "regla": f"veracidad: {v['veredicto']}", "detalle": v["motivo"], "vuelta": vuelta}
                              for v in veraces] + _historial(avisos, vuelta)
                historial += [{"nivel": "FALLA", "seccion": f"{rutas['word'].name} · {d['bloque']}", "oracion": d["oracion"],
                               "regla": f"segunda pasada: {d['tipo']}", "detalle": d["detalle"], "vuelta": vuelta}
                              for d in segunda.defectos]
                historial += [{"nivel": "FALLA", "seccion": rutas["word"].name, "oracion": "",
                               "regla": "lista de verificación", "detalle": f"{p['pregunta']} {p['detalle']}", "vuelta": vuelta}
                              for p in segunda.lista_no]
                correcciones["primera pasada"] += len(veraces)
                correcciones["verificador"] += len(avisos)
                correcciones["segunda pasada"] += len(valor)
                if pasada.enviadas_a_la_ia or pasada.aprobadas_por_programa:
                    medida = {"enviadas": pasada.enviadas_a_la_ia, "fuera_de_candidatos": pasada.pasajes_fuera_de_candidatos,
                              "busquedas": pasada.busquedas, "aprobadas_por_programa": pasada.aprobadas_por_programa}
                _avance(carpeta_curso, sesion, f"Primera pasada: {len(oraciones)} oraciones, "
                        f"{pasada.enviadas_a_la_ia} revisadas con IA, {pasada.aprobadas_por_programa} aprobadas por el programa, "
                        f"{len(veraces)} con problemas.")
                _avance(carpeta_curso, sesion, f"Segunda pasada: {len(segunda.revisados)} bloques revisados con IA, "
                        f"{len(segunda.defectos)} defectos, {len(segunda.lista_no)} puntos de la lista sin cumplir.")
        if not problemas:
            break
        if vuelta > MAX_CORRECCIONES:
            _avance(carpeta_curso, sesion, f"Quedan {len(problemas)} problemas después de {MAX_CORRECCIONES} correcciones.")
            break
        if vuelta >= VUELTA_DE_ULTIMO_INTENTO:
            # Una oración que sigue sin coincidir después de varias correcciones no se vuelve a reescribir libremente.
            problemas = [p + " " + ULTIMO_INTENTO if p.startswith("VERACIDAD") else p for p in problemas]
        if completa:
            _avance(carpeta_curso, sesion, f"Corrigiendo la lectura completa: {len(problemas)} problemas.")
            respuesta = await agente.consultar(pedido_de_correccion(carpeta_curso, sesion, datos, problemas),
                                               tarea="correccion", esquema=ESQUEMA_CORRECCION,
                                               etapa=f"corrección completa {vuelta}", **comun)
            datos = respuesta["lectura"]
        else:
            _avance(carpeta_curso, sesion, f"Corrigiendo {len(problemas)} oraciones.")
            respuesta = await agente.consultar(pedido_de_cambios(carpeta_curso, sesion, datos, problemas),
                                               tarea="correccion_oraciones", esquema=ESQUEMA_CAMBIOS,
                                               etapa=f"corrección {vuelta}", **comun)
            datos, no_encontradas = aplicar_cambios(datos, respuesta["cambios"])
            if no_encontradas:
                _avance(carpeta_curso, sesion, f"{len(no_encontradas)} oraciones a cambiar no se encontraron en la lectura.")
        for e in respuesta["explicaciones"]:
            explicaciones[verificador.clave_de_hallazgo(e["regla"], e["oracion"])] = e["explicacion"]
        _guardar_json(rutas["explicaciones"], explicaciones)
        nuevos = almacen.agregar_datos_fijos(carpeta_curso, respuesta.get("datos_nuevos", []), f"Lectura S{sesion}")
        if nuevos:
            datos_agregados += nuevos
            for numero in almacen.sesiones_confirmadas(carpeta_curso):
                verificacion.escribir(carpeta_curso, numero)
            _avance(carpeta_curso, sesion, f"Datos nuevos del caso agregados a la ficha del curso: {len(nuevos)}.")

    terminado = not problemas
    if resultado is not None and respuestas2 and bloques:
        excel.llenar_segunda_pasada(rutas["excel"], [[b.nombre, *[respuestas2.get(b.nombre, {}).get(c, "") for c in pasada2.CAMPOS]]
                                                     for b in bloques])
    if resultado is not None:
        excel.agregar_historial(rutas["excel"], [
            {**h, "resolucion": f"Enviado a corrección en la vuelta {h['vuelta']}." + (" Resuelto." if terminado else "")}
            for h in historial])
    final = Lectura.model_validate(datos) if not _validar(datos)[1] else None
    material = _actualizar(
        carpeta_curso, sesion,
        estado="verificada" if terminado else "con fallas",
        resumen=resultado.resumen() if resultado else "",
        problemas=problemas,
        correcciones=correcciones,
        medida_del_buscador=medida,
        datos_agregados=datos_agregados,
        avisos_de_diseno=identidad.avisos,
        decisiones=(final.decisiones if final else []),
        agrupacion=(final.agrupacion if final else ""),
        archivos={"word": rutas["word"].name, "excel": rutas["excel"].name},
        fecha=datetime.now().isoformat(timespec="seconds"),
    )
    _avance(carpeta_curso, sesion, "Lectura lista." if terminado else "La lectura quedó con problemas abiertos.")
    return material


def estado(carpeta_curso: Path, sesion: int) -> dict:
    return _estado(carpeta_curso, sesion)
