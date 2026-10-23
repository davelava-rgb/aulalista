"""Piezas que comparten todos los materiales: estado y avance, correcciones por oración, hallazgos del
verificador, revisión del contenido con su confirmación y filas de la hoja Hallazgos.

Cada material (lectura, diapositivas…) arma sus pedidos, su archivo y su entrega. Lo demás sale de aquí,
para que todos sigan el mismo ciclo de validación (PLAN.md §0, decisión 22).
"""

import json
import os
import shutil
import stat
from datetime import datetime
from pathlib import Path

from app import agente, tokens
from app.fichas import almacen, dependencias
from app.validacion import pasada2, revision, verificador
from app.validacion.pasajes import FICHA_DE_LA_SESION, FICHA_DEL_CURSO, Corpus

FICHAS = (FICHA_DEL_CURSO, FICHA_DE_LA_SESION)

# Subcarpeta de materiales/ con lo que usa AulaLista y no el profesor: contenido, explicaciones, imágenes, el JSON
# del verificador, el programa del diseñador (decisión 42). En materiales/ quedan solo los archivos para el profesor.
TRABAJO = "_trabajo"
MATERIALES = {"Lectura": "lectura", "Diapositivas": "diapositivas", "Laboratorio": "laboratorio", "Actividad": "actividad",
              "Evaluacion": "evaluacion"}


def ordenar_materiales(carpeta: Path) -> None:
    """Lleva una carpeta materiales/ de la forma anterior a la de la decisión 42: mueve los archivos de trabajo a
    _trabajo/ y borra las entregas en Markdown, que la página ya muestra. Un archivo abierto que no se deja mover
    queda donde está."""
    trabajo = carpeta / TRABAJO
    mudanzas = [(carpeta / clave, trabajo / clave) for clave in MATERIALES.values()]
    mudanzas.append((carpeta / "practica", trabajo / "laboratorio" / "practica"))
    for origen, destino in mudanzas:
        if not origen.is_dir():
            continue
        destino.mkdir(parents=True, exist_ok=True)
        for hijo in list(origen.iterdir()):
            if not (destino / hijo.name).exists():
                try:
                    shutil.move(str(hijo), str(destino / hijo.name))
                except OSError:
                    pass
        try:
            os.chmod(origen, stat.S_IWRITE)     # OneDrive marca las carpetas como de solo lectura
            origen.rmdir()
        except OSError:
            pass
    for ruta in carpeta.glob("S*_*_Verificacion.json"):
        clave = MATERIALES.get(ruta.stem.split("_")[1])
        if clave and not (trabajo / clave / "verificacion.json").exists():
            (trabajo / clave).mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(ruta), str(trabajo / clave / "verificacion.json"))
            except OSError:
                pass
    for ruta in carpeta.glob("S*_*_Entrega.md"):
        try:
            ruta.unlink()
        except OSError:
            pass
    _quitar_entrega_md_del_estado(carpeta.parent / "estado.json")


def _quitar_entrega_md_del_estado(ruta: Path) -> None:
    """La entrega guardada de un material anterior nombra su Entrega.md, que ya no existe: la página lo mostraba
    como un enlace que no abre."""
    if not ruta.exists():
        return
    estado_ = json.loads(ruta.read_text(encoding="utf-8"))
    cambio = False
    for material in (estado_.get("materiales") or {}).values():
        if (material.get("archivos") or {}).pop("entrega", None) is not None:
            cambio = True
        for seccion in (material.get("entrega") or {}).get("secciones", []):
            lineas = [l for l in seccion["lineas"] if not l.endswith("_Entrega.md: esta entrega, en texto.")]
            if len(lineas) != len(seccion["lineas"]):
                seccion["lineas"], cambio = lineas, True
    if cambio:
        ruta.write_text(json.dumps(estado_, ensure_ascii=False, indent=2), encoding="utf-8")


def escribir_sistema(ruta: Path, texto: str) -> Path:
    """Lo que no cambia entre las correcciones (contexto, formato y reglas) va en el mensaje de sistema, en un
    archivo: el SDK lo guarda en caché y cada corrección siguiente lo paga mucho más barato (decisión 43)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(texto, encoding="utf-8")
    return ruta


def ordenar_cursos(carpeta_cursos: Path) -> None:
    for carpeta in carpeta_cursos.glob("*/sesiones/*/materiales"):
        ordenar_materiales(carpeta)
VUELTAS_DEL_VERIFICADOR = 3   # correcciones de fallas mecánicas antes de dejarlas abiertas (PLAN.md §0, decisión 22)

# Avisos que se muestran en la hoja Hallazgos pero no obligan a corregir ni a explicar (PLAN.md §0, decisión 13).
# Un término que la fuente usa con su sentido tampoco obliga, aunque la ficha lo liste como variante (decisión 31).
AVISOS_INFORMATIVOS = ("relleno", "palabra imprecisa", "término de la fuente")
NOTA_INFORMATIVA = "Aviso informativo: no obliga a corregir ni a explicar (PLAN.md §0, decisiones 13 y 31)."

ESQUEMA_EXPLICACIONES = {"type": "array", "items": {
    "type": "object",
    "properties": {"regla": {"type": "string"}, "oracion": {"type": "string"}, "explicacion": {"type": "string"}},
    "required": ["regla", "oracion", "explicacion"], "additionalProperties": False,
}}

ESQUEMA_CAMBIOS = {
    "type": "object",
    "properties": {
        "cambios": {"type": "array", "items": {
            "type": "object",
            "properties": {"oracion": {"type": "string"}, "nueva": {"type": "string"}},
            "required": ["oracion", "nueva"], "additionalProperties": False,
        }},
        "explicaciones": ESQUEMA_EXPLICACIONES,
        "datos_nuevos": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["cambios", "explicaciones", "datos_nuevos"],
    "additionalProperties": False,
}


def esquema_de_correccion(clave: str, esquema_material: dict) -> dict:
    """La corrección completa devuelve el material entero con su esquema, más explicaciones y datos nuevos."""
    return {
        "type": "object",
        "properties": {clave: esquema_material, "explicaciones": ESQUEMA_EXPLICACIONES,
                       "datos_nuevos": {"type": "array", "items": {"type": "string"}}},
        "required": [clave, "explicaciones", "datos_nuevos"],
        "additionalProperties": False,
    }


def esquema_de_correcciones(**formas: dict) -> dict:
    """Un solo esquema para todas las correcciones de un material: una parte por forma de corregir, y la corrección
    llena solo la que se le pide. El SDK manda el esquema antes del mensaje de sistema; con un esquema distinto en
    cada forma, ninguna corrección leía la caché (decisión 51)."""
    return {
        "type": "object",
        "properties": {forma: {"anyOf": [esquema, {"type": "null"}]} for forma, esquema in formas.items()},
        "required": list(formas),
        "additionalProperties": False,
    }


async def consultar_correccion(pedido: str, forma: str, esquema: dict, **opciones) -> dict:
    """Pide la corrección en una de las formas del esquema común y devuelve solo esa parte."""
    otras = ", ".join(f"«{f}»" for f in esquema["properties"] if f != forma)
    pedido = f"{pedido}\nLlena solo «{forma}». Deja en null {otras}."
    respuesta = await agente.consultar(pedido, esquema=esquema, **opciones)
    if not isinstance(respuesta.get(forma), dict):
        raise agente.ErrorDeAgente(f"La corrección no devolvió «{forma}».")
    return respuesta[forma]


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


# ---------- Estado y avance (la página lo consulta mientras se trabaja) ----------

def estado(carpeta_curso: Path, sesion: int, clave: str) -> dict:
    return almacen.cargar_estado(carpeta_curso, sesion)["materiales"].get(clave, {})


def actualizar(carpeta_curso: Path, sesion: int, clave: str, **cambios) -> dict:
    with almacen.CANDADO_ESTADO:
        datos = almacen.cargar_estado(carpeta_curso, sesion)
        material = datos["materiales"].setdefault(clave, {"avance": []})
        material.update(cambios)
        if cambios.get("estado") == "trabajando" and not cambios.get("previo"):
            # Las fichas con que se genera: un cambio que no las toca no desactualiza este material.
            datos["huella_fichas"] = almacen.huella_de_fichas(carpeta_curso, sesion)
            if clave in dependencias.TODOS:
                # Lo que usa, para saber después qué cambio lo desactualiza y cuál no (decisión 62).
                material["usado"] = dependencias.usado(carpeta_curso, sesion)
                material["razones"] = []
                if clave != "lectura":
                    material["lectura_usada"] = datos["materiales"].get("lectura", {}).get("fecha", "")
                if clave == "evaluacion":   # la evaluación también sale del laboratorio (decisión 64 g)
                    material["laboratorio_usada"] = datos["materiales"].get("laboratorio", {}).get("fecha", "")
        almacen.guardar_estado(carpeta_curso, sesion, datos)
        return material


def avance(carpeta_curso: Path, sesion: int, clave: str, texto: str) -> None:
    with almacen.CANDADO_ESTADO:
        datos = almacen.cargar_estado(carpeta_curso, sesion)
        material = datos["materiales"].setdefault(clave, {"avance": []})
        material.setdefault("avance", []).append(f"{datetime.now():%H:%M:%S} · {texto}")
        almacen.guardar_estado(carpeta_curso, sesion, datos)


def gasto_de_la_corrida(carpeta_curso: Path, curso: str, sesion: int, clave: str) -> dict | None:
    """Lo que gastó el material desde que se pulsó Generar por última vez, aunque se haya detenido o
    terminado con error. Incluye el revisor independiente si se pidió después. None si nunca se generó."""
    desde = estado(carpeta_curso, sesion, clave).get("corrida_desde")
    if desde is None:
        return None
    return tokens.total(curso, sesion=f"S{sesion}", material=clave, desde_linea=desde)


def marcar_detenida(carpeta_curso: Path, sesion: int, clave: str) -> bool:
    """El profesor detuvo el trabajo con el botón Detener. También libera un material que quedó en
    «Trabajando» porque el servidor se cerró a mitad de camino. Si lo detenido era el revisor opcional,
    el material vuelve al estado que tenía. Devuelve False si no estaba trabajando."""
    material = estado(carpeta_curso, sesion, clave)
    if material.get("estado") != "trabajando":
        return False
    avance(carpeta_curso, sesion, clave, "Detenido por ti. Lo que se gastó hasta aquí queda en el registro de tokens.")
    actualizar(carpeta_curso, sesion, clave, estado=material.get("previo") or "detenida", previo="", error="")
    return True


def leer_json(ruta: Path) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def guardar_json(ruta: Path, datos) -> None:
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")


def cuantos(numero: int, palabra: str) -> str:
    if palabra.endswith("ón"):
        plural = palabra[:-2] + "ones"
    else:
        plural = palabra + ("es" if palabra[-1] in "rnl" else "s")
    return f"{numero} {palabra if numero == 1 else plural}"


# ---------- Hallazgos del verificador ----------

def hallazgos_abiertos(resultado, explicaciones) -> tuple[list, list]:
    """Fallas del verificador y avisos todavía sin explicar. Los avisos informativos no cuentan."""
    fallas = [h for h in resultado.hallazgos if h.nivel == "FALLA"]
    avisos = [h for h in resultado.hallazgos
              if h.nivel == "AVISO" and h.regla not in AVISOS_INFORMATIVOS
              and not verificador.buscar_explicacion(h.regla, h.oracion, explicaciones)]
    return fallas, avisos


def texto_de(h) -> str:
    donde = f"«{h.oracion}»" if h.oracion else h.seccion
    return f"{h.nivel} · {h.regla} · {donde}: {h.detalle}"


REGLAS_QUE_EXPLICA_EL_PROGRAMA = ("palabra imprecisa",)


def explicar_literales(resultado, explicaciones: dict, corpus: Corpus) -> bool:
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


def historial(hallazgos, vuelta) -> list[dict]:
    return [{"nivel": h.nivel, "seccion": h.seccion, "oracion": h.oracion, "regla": h.regla,
             "detalle": h.detalle, "vuelta": vuelta} for h in hallazgos]


# ---------- Corrección por oraciones ----------

CAMPOS_QUE_NO_SE_CORRIGEN = frozenset({"pasajes", "decisiones", "agrupacion"})


def aplicar_cambios(datos: dict, cambios: list[dict], excluir=CAMPOS_QUE_NO_SE_CORRIGEN) -> tuple[dict, list[str]]:
    """Reemplaza cada oración corregida dentro del material. «nueva» vacía elimina la oración.
    Devuelve el material nuevo y las oraciones que no se encontraron. Los campos de `excluir` no se tocan."""
    datos = json.loads(json.dumps(datos))
    no_encontradas = []
    for c in cambios:
        buscada = " ".join(c["oracion"].split())
        nueva = " ".join(c["nueva"].split())
        if not buscada or not _reemplazar(datos, buscada, nueva, excluir):
            no_encontradas.append(c["oracion"])
    return datos, no_encontradas


def _reemplazar(nodo, buscada: str, nueva: str, excluir, borrar: bool = True) -> bool:
    """borrar=False dentro de una tabla: una celda vacía se queda, para no descuadrar las columnas."""
    if isinstance(nodo, dict):
        return any(_reemplazar_en(nodo, clave, buscada, nueva, excluir, borrar and clave != "tabla")
                   for clave in list(nodo) if clave not in excluir)
    if isinstance(nodo, list):
        return any(_reemplazar_en(nodo, i, buscada, nueva, excluir, borrar) for i in range(len(nodo) - 1, -1, -1))
    return False


def _reemplazar_en(contenedor, clave, buscada: str, nueva: str, excluir, borrar: bool) -> bool:
    valor = contenedor[clave]
    if not isinstance(valor, str):
        return _reemplazar(valor, buscada, nueva, excluir, borrar)
    normal = " ".join(valor.split())
    if buscada not in normal:
        return False
    texto = " ".join(normal.replace(buscada, nueva, 1).split())
    if not texto and borrar and isinstance(contenedor, list):
        del contenedor[clave]   # el párrafo quedó vacío: se elimina
    else:
        contenedor[clave] = texto
    return True


# ---------- Revisión del contenido, corrección única y confirmación ----------

def cambio(antes: dict[str, str], despues: list[pasada2.Bloque], nombre: str) -> bool:
    """Un bloque cambió si su texto es otro o si ya no está con ese nombre."""
    actual = next((b for b in despues if b.nombre == nombre), None)
    return actual is None or actual.huella != antes.get(nombre)


async def revisar_y_corregir(trabajo, bloques_de) -> tuple[list[revision.Error], int]:
    """Segunda pasada sobre un material sin fallas del verificador.

    `trabajo` ofrece avance(), revisar(), corregir(), verificar(), `contenido` y `correcciones`;
    `bloques_de(contenido)` divide el material en bloques. Una sola corrección; después, el verificador
    y la confirmación solo de los bloques que cambiaron. Lo que sigue abierto queda pendiente.
    Devuelve los errores con su estado y cuántos bloques se revisaron."""
    bloques = bloques_de(trabajo.contenido)
    trabajo.avance(f"Revisión del contenido: {cuantos(len(bloques), 'bloque')} con sus pasajes de las fuentes.")
    resultado = await trabajo.revisar(bloques, "revisión")
    errores = resultado.errores
    trabajo.avance(f"Revisión: {cuantos(len(errores), 'error')} con prueba"
                   + (f", {len(resultado.descartados)} descartados porque su prueba no existe." if resultado.descartados else "."))
    if not errores:
        return errores, len(bloques)
    antes = {b.nombre: b.huella for b in bloques}
    trabajo.correcciones["revisión"] += len(errores)
    await trabajo.corregir([e.describir() for e in errores], completa=False)
    if not await trabajo.verificar():
        for e in errores:
            e.estado, e.resolucion = "pendiente", "No se confirmó: quedaron fallas del verificador."
        return errores, len(bloques)
    despues = bloques_de(trabajo.contenido)
    cambiados = [b for b in despues if cambio(antes, despues, b.nombre)]
    confirmacion = await trabajo.revisar(cambiados, "confirmación") if cambiados else revision.Resultado()
    trabajo.avance(f"Confirmación: {cuantos(len(cambiados), 'bloque')} corregidos revisados de nuevo, "
                   f"{cuantos(len(confirmacion.errores), 'error')}.")
    nuevos = list(confirmacion.errores)
    for e in errores:
        # El mismo error sigue si la confirmación lo encuentra otra vez en su oración, o en su bloque
        # con el mismo tipo (la oración corregida tiene otro texto).
        sigue = next((c for c in nuevos if c.tipo == e.tipo and (c.oracion == e.oracion or c.bloque == e.bloque)), None)
        if sigue is not None:
            nuevos.remove(sigue)
            e.oracion, e.explicacion, e.prueba, e.fuente = sigue.oracion, sigue.explicacion, sigue.prueba, sigue.fuente
            e.estado, e.resolucion = "pendiente", "Sigue después de la corrección. Pendiente: decides tú."
        elif cambio(antes, despues, e.bloque):
            e.estado, e.resolucion = "corregido", "Corregido y confirmado por la revisión."
        else:
            e.estado, e.resolucion = "pendiente", "La corrección no cambió su bloque. Pendiente: decides tú."
    for c in nuevos:
        c.estado, c.resolucion = "pendiente", "Apareció en la confirmación. Pendiente: decides tú."
    return errores + nuevos, len(bloques)


# ---------- Filas de la hoja Hallazgos ----------

def filas_de_revision(errores: list[revision.Error], descartados: list[dict], seccion: str) -> list[dict]:
    """Filas de la hoja Hallazgos para la revisión del contenido."""
    filas = [{"nivel": "REVISIÓN", "seccion": f"{seccion} · {e.bloque}", "oracion": e.oracion,
              "regla": f"revisión: {e.tipo}",
              "detalle": e.explicacion + (f" Prueba: «{e.prueba}» ({e.fuente})." if e.prueba else ""),
              "resolucion": e.resolucion or "Pendiente: decides tú."} for e in errores]
    filas += [{"nivel": "REVISIÓN", "seccion": f"{seccion} · {d['bloque']}", "oracion": d["oracion"],
               "regla": f"revisión: {d['tipo']}", "detalle": d["explicacion"],
               "resolucion": f"Descartado por el programa: {d['motivo']}"} for d in descartados]
    return filas


def filas_de_decisiones(decisiones: list, seccion: str) -> list[dict]:
    """Filas de la hoja Hallazgos con lo que anotó el redactor. El tipo «nota» ya no se pide (decisión 66 e); se
    conserva para leer los contenidos anteriores."""
    resolucion = {"sin fuente": "Pendiente: decides tú.", "decisión": "En «Qué decidí por mi cuenta».",
                  "nota": "Informativo."}
    return [{"nivel": "REDACTOR", "seccion": seccion, "oracion": "", "regla": f"redactor: {d.tipo}",
             "detalle": d.texto, "resolucion": resolucion[d.tipo]} for d in decisiones]
