"""Servidor local. Responde solo a esta computadora (127.0.0.1)."""

import asyncio
import threading
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import agente, cursos, tokens
from app.config import RAIZ, FaltaClave
from app.fichas import almacen, controles, flujo
from app.fichas import plantillas as plantillas_fichas
from app.fuentes import convertir
from app.materiales import diapositivas, laboratorio, lectura

app = FastAPI(title="AulaLista")
app.mount("/estaticos", StaticFiles(directory=RAIZ / "web" / "estaticos"), name="estaticos")
plantillas = Jinja2Templates(directory=RAIZ / "web" / "plantillas")


def _carpeta(curso: str):
    try:
        return cursos.carpeta(curso)
    except cursos.ErrorDeCurso as error:
        raise HTTPException(404, str(error)) from error


def _ir_al_curso(curso: str, mensaje: str = "") -> RedirectResponse:
    destino = f"/cursos/{curso}" + (f"?mensaje={quote(mensaje)}" if mensaje else "")
    return RedirectResponse(destino, status_code=303)


def _nombre(curso: str) -> str:
    """El nombre del curso que se ve en la interfaz: el de la ficha del curso, que es el que llevan los materiales
    (vocabulario único). Sin ficha, el que se escribió al crearlo."""
    valor = (almacen.cargar(_carpeta(curso), "curso")["campos"].get("curso.nombre") or {}).get("valor", "").strip()
    return valor or cursos.nombre(curso)


def lector_de_imagenes(curso: str) -> convertir.LectorImagen:
    async def leer(imagen: bytes, tipo: str, etiqueta: str) -> list[str]:
        return await agente.leer_imagen(imagen, tipo, curso=curso, etiqueta=etiqueta)
    return leer


# ---------- Inicio y conexión ----------

@app.get("/")
def inicio(request: Request, mensaje: str = ""):
    lista = []
    for c in cursos.listar():
        panel = _panel(cursos.carpeta(c["curso"]), c["curso"], "inicio")
        materiales = [m for s in panel["sesiones"] for m in s["materiales"]]
        lista.append({**c, "nombre": _nombre(c["curso"]), "gasto": panel["gasto"], "sigue": _que_sigue(c["curso"], panel),
                      "sesiones": len(panel["sesiones"]), "materiales": len(materiales),
                      "aprobados": sum(1 for m in materiales if m["situacion"]["clase"] == "bien"),
                      "tramos": [m["situacion"]["clase"] for m in materiales],
                      "con_problema": [f"Sesión {s['numero']}: {m['corto'].lower()} {m['situacion']['texto'].lower()}"
                                       for s in panel["sesiones"] for m in s["materiales"]
                                       if m["situacion"]["clase"] == "error"]})
    sistema = tokens.total(tokens.CURSO_SISTEMA)
    total = {"llamadas": sistema["llamadas"] + sum(c["gasto"]["llamadas"] for c in lista),
             "costo_usd": sistema["costo_usd"] + sum(c["gasto"]["costo_usd"] for c in lista)}
    return plantillas.TemplateResponse(
        request,
        "inicio.html",
        {"gasto": sistema, "total": total, "cursos": lista, "mensaje": mensaje},
    )


@app.get("/ayuda")
def ayuda(request: Request):
    """Cómo funciona AulaLista: el flujo completo en una página."""
    return plantillas.TemplateResponse(request, "ayuda.html", {})


@app.post("/api/probar-conexion")
async def probar_conexion():
    try:
        respuesta = await agente.probar_conexion()
    except FaltaClave as error:
        return JSONResponse({"error": str(error)}, status_code=400)
    except agente.ErrorDeAgente as error:
        return JSONResponse({"error": str(error)}, status_code=502)
    respuesta["gasto"] = tokens.total(tokens.CURSO_SISTEMA)
    return respuesta


@app.get("/api/gasto")
def gasto():
    return tokens.total(tokens.CURSO_SISTEMA)


# ---------- Cursos y fuentes ----------

@app.post("/cursos")
def crear_curso(nombre: str = Form(...)):
    try:
        curso = cursos.crear(nombre)
    except cursos.ErrorDeCurso as error:
        return RedirectResponse(f"/?mensaje={quote(str(error))}", status_code=303)
    return _ir_al_curso(curso)


@app.get("/cursos/{curso}")
def ver_curso(request: Request, curso: str, mensaje: str = ""):
    carpeta = _carpeta(curso)
    indice = convertir.leer_indice(carpeta)
    archivos = sorted(r.name for r in (carpeta / "fuentes").glob("*") if r.is_file())
    fuentes = [{"archivo": a, **indice.get(a, {"estado": "sin convertir"})} for a in archivos]
    ficha_curso = almacen.cargar(carpeta, "curso")
    return plantillas.TemplateResponse(
        request,
        "curso.html",
        {
            "curso": curso,
            "nombre": _nombre(curso),
            "ficha_curso": ficha_curso,
            "ficha_curso_existe": almacen.ruta_ficha(carpeta, "curso").exists(),
            "fuentes": fuentes,
            "pendientes": sum(1 for f in fuentes if f["estado"] != convertir.CONVERTIDA),
            "costo_convertir": tokens.ultima_corrida(curso, "lectura_imagen"),
            "mensaje": mensaje,
            "panel": (panel := _panel(carpeta, curso, "curso")),
            "tablero": _tablero(carpeta, curso, panel),
        },
    )


@app.post("/cursos/{curso}/fuentes")
async def subir_fuentes(curso: str, archivos: list[UploadFile]):
    _carpeta(curso)
    guardados, rechazos = [], []
    for archivo in archivos:
        if not archivo.filename:
            continue
        try:
            guardados.append(cursos.guardar_fuente(curso, archivo.filename, await archivo.read()))
        except cursos.ErrorDeCurso as error:
            rechazos.append(str(error))
    mensaje = f"Archivos guardados: {len(guardados)}."
    if rechazos:
        mensaje += " " + " ".join(rechazos)
    return _ir_al_curso(curso, mensaje)


@app.post("/cursos/{curso}/convertir")
def convertir_fuentes(curso: str):
    # Función sin async: corre en un hilo aparte, donde Office y la IA pueden tardar sin trabar el servidor.
    carpeta = _carpeta(curso)
    antes = convertir.leer_indice(carpeta)
    indice = asyncio.run(convertir.convertir_curso(carpeta, lector_de_imagenes(curso)))
    cambiadas = [n for n, e in indice.items() if antes.get(n, {}).get("fecha") != e["fecha"]]
    fallidas = [n for n in cambiadas if indice[n]["estado"] == convertir.NO_SE_PUEDE_LEER]
    mensaje = f"Fuentes convertidas ahora: {len(cambiadas) - len(fallidas)}. Sin cambios: {len(indice) - len(cambiadas)}."
    if fallidas:
        mensaje += f" No se pudieron leer: {', '.join(fallidas)}."
    return _ir_al_curso(curso, mensaje)


@app.get("/cursos/{curso}/fuentes/{archivo}")
def ver_fuente(request: Request, curso: str, archivo: str):
    carpeta = _carpeta(curso)
    entrada = convertir.leer_indice(carpeta).get(archivo)
    if entrada is None:
        raise HTTPException(404, "Esa fuente no está convertida.")
    return plantillas.TemplateResponse(
        request,
        "fuente.html",
        {
            "curso": curso,
            "nombre": _nombre(curso),
            "archivo": archivo,
            "entrada": entrada,
            "pasajes": convertir.leer_pasajes(carpeta, archivo),
            "panel": _panel(carpeta, curso, "fuentes"),
        },
    )


@app.post("/cursos/{curso}/fuentes/{archivo}/revisada")
def marcar_revisada(curso: str, archivo: str):
    try:
        convertir.marcar_revisada(_carpeta(curso), archivo)
    except KeyError as error:
        raise HTTPException(404, "Esa fuente no está convertida.") from error
    return RedirectResponse(f"/cursos/{curso}/fuentes/{quote(archivo)}", status_code=303)


# ---------- Fichas ----------

TITULOS_FICHA = {"curso": "Ficha del curso", "sesion": "Ficha de la sesión"}


# Resultado de la última acción en cada ficha, para mostrarlo después de redirigir (post-redirect-get):
# recargar la página ya no reenvía «Proponer» ni «Completar», que gastan tokens. Un solo usuario: basta en memoria.
_AVISOS_FICHA: dict[str, tuple[str, list | None]] = {}


def _url_ficha(curso: str, sesion: int | None) -> str:
    return f"/cursos/{curso}/ficha" if sesion is None else f"/cursos/{curso}/sesiones/{sesion}/ficha"


def _pagina_ficha(request: Request, curso: str, tipo: str, sesion: int | None, mensaje: str = "", errores=None):
    carpeta = _carpeta(curso)
    ficha = almacen.cargar(carpeta, tipo, sesion)
    titulo = TITULOS_FICHA[tipo] + (f" {sesion}" if sesion else "")
    desactualizados = []
    if sesion is not None:
        claves = [n for n, m in almacen.cargar_estado(carpeta, sesion)["materiales"].items() if m.get("desactualizado")]
        desactualizados = _y([MATERIALES[n]["el"] if n in MATERIALES else n for n in claves])
        if errores is None:
            # Al volver a abrir la ficha, el motivo de que siga sin confirmar no se pierde.
            errores = flujo.problemas_de_ejercicios_guardados(ficha)
    # Los problemas de la revisión de los ejercicios los corrige la IA con un botón.
    corregibles = sesion is not None and bool(set(errores or []) & set(flujo.problemas_de_ejercicios_guardados(ficha)))
    # La herramienta de los ejercicios solo pide su respuesta si el curso usa IA (decisión 36).
    secciones = _indice_de_secciones(plantillas_fichas.vista(
        tipo, ficha["campos"],
        () if tipo == "curso" or "ia" in almacen.herramienta_de_los_ejercicios(carpeta) else ("pregunta_herramienta",)))
    # Lo que ya se generó y quedaría desactualizado si se guarda un cambio en una ficha confirmada.
    if sesion is None:
        generados = ["los materiales de todas las sesiones"] if any(
            m.get("estado") for s in almacen.sesiones_del_curso(ficha)
            for m in almacen.cargar_estado(carpeta, s["numero"])["materiales"].values()) else []
    else:
        generados = [d["el"] for c, d in MATERIALES.items()
                     if almacen.cargar_estado(carpeta, sesion)["materiales"].get(c, {}).get("estado")]
    costos = {"proponer": tokens.ultima_corrida(curso, f"propuesta ficha {tipo}"),
              "corregir": tokens.ultima_corrida(curso, "corrección de ejercicios"),
              **{f"completar.{c}": tokens.ultima_corrida(curso, f"completar ficha: {c}") for c in flujo.COMPLETAR}}
    return plantillas.TemplateResponse(request, "ficha.html", {
        "curso": curso, "nombre": _nombre(curso), "titulo": titulo, "sesion": sesion, "ficha": ficha,
        "propuesta": flujo.estado_propuesta(carpeta, tipo, sesion),
        "hay_propuestos": any((d or {}).get("estado") == almacen.PROPUESTO for d in ficha["campos"].values()),
        "secciones": secciones, "generados": generados, "generados_texto": _y(generados), "costos": costos,
        "url_propuesta": _url_ficha(curso, sesion) + "/propuesta",
        "preguntas": almacen.preguntas_pendientes(ficha),
        "errores": errores or [], "mensaje": mensaje, "corregibles": corregibles,
        "versiones": almacen.listar_versiones(carpeta, tipo, sesion),
        "url_restaurar": _url_ficha(curso, sesion) + "/restaurar",
        "panel": _panel(carpeta, curso, "ficha-curso" if sesion is None else f"ficha-{sesion}"),
        "desactualizados": desactualizados,
        "completar": {d["seccion"]: {"clave": c, **d} for c, d in flujo.COMPLETAR.items()} if tipo == "curso" else {},
    })


ALERTAS = ("falta definir", "conflicto")


def _indice_de_secciones(secciones: list[dict]) -> list[dict]:
    """Agrega a cada sección su ancla y cuántos campos tiene en «Falta definir» o con dos versiones, para el
    índice de la ficha. Cada bloque repetido dice si está vacío, lleno o con alertas: los llenos se pliegan."""
    for numero, s in enumerate(secciones, 1):
        campos = []
        for e in s["elementos"]:
            if e.get("repetible"):
                for b in e["bloques"]:
                    b["situacion"] = ("alerta" if any(c["estado"] in ALERTAS for c in b["campos"])
                                      else "lleno" if any(c["valor"] for c in b["campos"]) else "vacio")
                    campos += b["campos"]
            elif e.get("grupo"):
                campos += e["campos"]
            else:
                campos.append(e)
        s["ancla"] = f"seccion-{numero}"
        s["alertas"] = sum(1 for c in campos if c["estado"] in ALERTAS)
        # La fuente que más se repite se dice una vez en la sección; cada campo dice solo la suya si es otra.
        origenes = [c["origen"] for c in campos if c.get("origen") and c["origen"] != "profesor"]
        comun = max(set(origenes), key=origenes.count) if origenes else ""
        if origenes.count(comun) < 2:
            comun = ""
        s["origen_comun"] = comun
        for c in campos:
            c["origen_visible"] = c["origen"] if c.get("origen") not in ("", None, "profesor", comun) else ""
    return secciones


@app.get("/cursos/{curso}/ficha/propuesta")
def propuesta_del_curso(curso: str):
    """Estado de la propuesta automática: la página lo consulta sin recargarse."""
    return flujo.estado_propuesta(_carpeta(curso), "curso") or {}


@app.get("/cursos/{curso}/sesiones/{sesion}/ficha/propuesta")
def propuesta_de_la_sesion(curso: str, sesion: int):
    return flujo.estado_propuesta(_carpeta(curso), "sesion", sesion) or {}


def _exigir_ficha_del_curso(carpeta, curso):
    if not almacen.cargar(carpeta, "curso")["confirmada"]:
        raise HTTPException(409, "Guarda primero la ficha del curso completa: así queda confirmada.")


async def _accion_ficha(request: Request, curso: str, tipo: str, sesion: int | None):
    carpeta = _carpeta(curso)
    # Los controles (casillas, listas, archivos) se convierten en el texto de la ficha (decisión 27).
    formulario = await controles.leer(await request.form(), carpeta)
    accion = formulario.pop("accion", "guardar")
    if accion == "confirmar":   # una página abierta antes de la decisión 28 todavía trae ese botón
        accion = "guardar"
    ficha = almacen.cargar(carpeta, tipo, sesion)
    if almacen.aplicar_formulario(ficha, formulario) or not almacen.ruta_ficha(carpeta, tipo, sesion).exists():
        almacen.guardar(carpeta, tipo, sesion, ficha, "editada por el profesor")
    mensaje, errores = "Ficha guardada.", []
    try:
        if accion == "aceptar":
            if flujo.aceptar_propuestos(ficha):
                ficha["confirmada"] = False
            almacen.guardar(carpeta, tipo, sesion, ficha, "propuesta aceptada")
            accion = "guardar"
        if accion == "proponer":
            resumen = await asyncio.to_thread(
                lambda: asyncio.run(flujo.proponer(carpeta, curso, tipo, sesion))
            )
            if resumen.get("sin_fuentes"):
                mensaje = "No hay fuentes convertidas que se puedan usar. Llena la ficha a mano o sube fuentes."
            else:
                mensaje = (f"Datos tomados de las fuentes: {resumen['de_las_fuentes']}. "
                           f"Propuestos: {resumen['propuestos']}. Con dos versiones: {resumen['conflictos']}.")
        elif accion.startswith("completar.") and tipo == "curso" and accion.removeprefix("completar.") in flujo.COMPLETAR:
            mensaje = await asyncio.to_thread(
                lambda: asyncio.run(flujo.completar(carpeta, curso, accion.removeprefix("completar.")))
            )
        elif accion == "corregir_ejercicios" and tipo == "sesion":
            # Una corrección y, enseguida, la revisión de nuevo: lo que quede, lo decide el profesor.
            corregido = await asyncio.to_thread(
                lambda: asyncio.run(flujo.corregir_ejercicios(carpeta, curso, sesion))
            )
            try:
                mensaje = corregido + " " + await _guardar_y_confirmar(carpeta, curso, tipo, sesion)
            except almacen.FichaIncompleta as error:
                mensaje, errores = corregido + " La revisión todavía encuentra problemas.", error.errores
        elif accion == "guardar":
            # Guardar también confirma: una ficha completa queda confirmada (decisión 28).
            mensaje = await _guardar_y_confirmar(carpeta, curso, tipo, sesion)
    except almacen.FichaIncompleta as error:
        mensaje, errores = "Ficha guardada. Todavía no está confirmada.", error.errores
    except flujo.FichaDelCursoSinConfirmar as error:
        mensaje = str(error)
    except (FaltaClave, agente.ErrorDeAgente) as error:
        mensaje = str(error)
    _AVISOS_FICHA[_url_ficha(curso, sesion)] = (mensaje, errores)
    return RedirectResponse(_url_ficha(curso, sesion), status_code=303)


async def _guardar_y_confirmar(carpeta, curso: str, tipo: str, sesion: int | None) -> str:
    """Confirma la ficha guardada si está completa. Si ya estaba confirmada y no cambió, no hace nada:
    confirmar de nuevo dejaría desactualizados los materiales sin motivo."""
    if almacen.cargar(carpeta, tipo, sesion)["confirmada"]:
        return "Ficha guardada. Sigue confirmada."
    if tipo == "curso":
        resultado = flujo.confirmar_curso(carpeta)
        sesiones = ", ".join(f"S{n}" for n in resultado["desactualizados"])
        return "Ficha del curso guardada y confirmada." + (
            f" Se actualizó la verificación de las sesiones {sesiones}." if sesiones else "")
    await asyncio.to_thread(lambda: asyncio.run(flujo.confirmar_sesion(carpeta, curso, sesion)))
    return "Ficha de la sesión guardada y confirmada. Se escribió verificacion.json."


def _proponer_si_corresponde(curso: str, tipo: str, sesion: int | None) -> None:
    """Con fuentes convertidas, una ficha vacía se propone sola al abrirla (PLAN.md §0, decisión 17)."""
    carpeta = _carpeta(curso)
    if flujo.debe_proponer_sola(carpeta, tipo, sesion):
        flujo.marcar_propuesta_en_curso(carpeta, tipo, sesion)
        _trabajo_en_segundo_plano(flujo.proponer_sola, carpeta, curso, tipo, sesion)


@app.get("/cursos/{curso}/ficha")
def ver_ficha_del_curso(request: Request, curso: str):
    _proponer_si_corresponde(curso, "curso", None)
    return _pagina_ficha(request, curso, "curso", None, *_AVISOS_FICHA.pop(_url_ficha(curso, None), ("", None)))


@app.post("/cursos/{curso}/ficha")
async def accion_ficha_del_curso(request: Request, curso: str):
    return await _accion_ficha(request, curso, "curso", None)


@app.get("/cursos/{curso}/sesiones/{sesion}/ficha")
def ver_ficha_de_la_sesion(request: Request, curso: str, sesion: int):
    _exigir_ficha_del_curso(_carpeta(curso), curso)
    _proponer_si_corresponde(curso, "sesion", sesion)
    return _pagina_ficha(request, curso, "sesion", sesion, *_AVISOS_FICHA.pop(_url_ficha(curso, sesion), ("", None)))


@app.post("/cursos/{curso}/sesiones/{sesion}/ficha")
async def accion_ficha_de_la_sesion(request: Request, curso: str, sesion: int):
    _exigir_ficha_del_curso(_carpeta(curso), curso)
    return await _accion_ficha(request, curso, "sesion", sesion)


def _restaurar(curso: str, tipo: str, sesion: int | None, version: str):
    try:
        almacen.restaurar(_carpeta(curso), tipo, sesion, version)
    except FileNotFoundError as error:
        raise HTTPException(404, "Esa versión no existe.") from error
    return RedirectResponse(_url_ficha(curso, sesion), status_code=303)


@app.post("/cursos/{curso}/ficha/restaurar")
def restaurar_ficha_del_curso(curso: str, version: str = Form(...)):
    return _restaurar(curso, "curso", None, version)


@app.post("/cursos/{curso}/sesiones/{sesion}/ficha/restaurar")
def restaurar_ficha_de_la_sesion(curso: str, sesion: int, version: str = Form(...)):
    return _restaurar(curso, "sesion", sesion, version)


# ---------- Sesión y materiales ----------

# Trabajos que se pueden detener: (curso, sesión, material) → (bucle del hilo, tarea).
_TRABAJOS: dict[tuple, tuple[asyncio.AbstractEventLoop, asyncio.Task]] = {}
_CANDADO = threading.Lock()


def _trabajo_en_segundo_plano(funcion, *argumentos, clave: tuple | None = None) -> threading.Thread:
    """Corre un material en otro hilo. La página consulta el avance en estado.json.
    Con `clave`, el trabajo queda registrado para que el botón Detener lo pueda cancelar."""
    async def principal():
        if clave:
            with _CANDADO:
                _TRABAJOS[clave] = (asyncio.get_running_loop(), asyncio.current_task())
        try:
            await funcion(*argumentos)
        finally:
            if clave:
                with _CANDADO:
                    _TRABAJOS.pop(clave, None)

    def correr():
        try:
            asyncio.run(principal())
        except (Exception, asyncio.CancelledError):
            pass  # el error o la detención quedan escritos en estado.json y la página los muestra
    hilo = threading.Thread(target=correr, daemon=True)
    hilo.start()
    return hilo


# Materiales que ya se generan, en el orden de la skill. Cada módulo tiene las mismas funciones:
# estado, faltan, generar, marcar_detenida, revisar_con_revisor, aprobar y gasto_de_la_corrida.
# «o» es la terminación del género («aprobada», «aprobado») y «lo» el pronombre («generarla», «generarlo»).
MATERIALES = {
    lectura.CLAVE: {"modulo": lectura, "numero": 1, "titulo": "Lectura", "corto": "Lectura", "el": "la lectura",
                    "plural": False, "o": "a", "lo": "la",
                    "aprobado": "Lectura aprobada.", "generar": "Generar lectura"},
    diapositivas.CLAVE: {"modulo": diapositivas, "numero": 2, "titulo": "Diapositivas", "corto": "Diapositivas",
                         "el": "las diapositivas", "plural": True, "o": "a", "lo": "las",
                         "aprobado": "Diapositivas aprobadas.", "generar": "Generar diapositivas"},
    laboratorio.CLAVE: {"modulo": laboratorio, "numero": 3, "titulo": "Laboratorio y archivos de práctica",
                        "corto": "Laboratorio", "el": "el laboratorio", "plural": False, "o": "o", "lo": "lo",
                        "aprobado": "Laboratorio aprobado.", "generar": "Generar laboratorio"},
}

# La práctica interactiva, la guía del profesor y la evaluación no se generan (PLAN.md §0, decisiones 34, 35 y 37).


def _y(partes: list[str]) -> str:
    """«la lectura», «las diapositivas» → «la lectura y las diapositivas»."""
    return ", ".join(partes[:-1]) + " y " + partes[-1] if len(partes) > 1 else "".join(partes)


def _forma(datos: dict, raiz: str) -> str:
    """«Aprobad» → «Aprobada», «Aprobadas» o «Aprobado», según el material."""
    return raiz + datos.get("o", "a") + ("s" if datos.get("plural") else "")


def _situacion(datos: dict, estado: dict, incluido: bool) -> dict:
    """Indicador de un material: clase (color e icono) y texto corto. El color nunca va sin su palabra."""
    e = estado.get("estado")
    if not incluido:
        return {"clase": "neutro", "texto": "No va en esta sesión"}
    if e == "trabajando":
        return {"clase": "trabajando", "texto": "Trabajando"}
    if estado.get("desactualizado") and e in ("aprobada", "verificada", "con pendientes"):
        return {"clase": "error", "texto": _forma(datos, "Desactualizad")}
    textos = {"aprobada": ("bien", _forma(datos, "Aprobad")),
              "verificada": ("espera", "Para aprobar"),
              "con pendientes": ("espera", "Con pendientes"),
              "con fallas": ("error", "Con fallas"),
              "error": ("error", "Error"),
              "detenida": ("neutro", _forma(datos, "Detenid"))}
    clase, texto = textos.get(e, ("neutro", "Sin generar"))
    return {"clase": clase, "texto": texto}


def _costo_de_referencia(carpeta, curso: str, sesion: int, clave: str, sesiones: list[int]) -> dict | None:
    """Lo que gastó la última corrida de este material: en esta sesión o, si nunca se generó aquí, en la sesión
    más reciente que lo tenga. Se muestra junto al botón Generar antes de pulsarlo."""
    modulo = MATERIALES[clave]["modulo"]
    for numero in [sesion] + sorted((n for n in sesiones if n != sesion), reverse=True):
        gasto = modulo.gasto_de_la_corrida(carpeta, curso, numero)
        if gasto and gasto["llamadas"]:
            return {**gasto, "sesion": numero}
    return None


def _vista_de_materiales(carpeta, curso: str, sesion: int, detalle: bool = False) -> dict:
    """Los materiales de una sesión con su indicador, y el siguiente paso. Con `detalle`, también lo que les
    falta y el costo de la última corrida (la página de la sesión)."""
    puede_empezar = almacen.puede_empezar_material(carpeta, sesion)
    incluidos = almacen.materiales_de_la_sesion(almacen.cargar(carpeta, "sesion", sesion))
    numeros = [s["numero"] for s in almacen.sesiones_del_curso(almacen.cargar(carpeta, "curso"))] if detalle else []
    materiales, siguiente = [], None
    for clave, datos in MATERIALES.items():
        modulo = datos["modulo"]
        estado = modulo.estado(carpeta, sesion)   # calcula si quedó desactualizado
        incluido = clave in incluidos
        m = {**{k: v for k, v in datos.items() if k != "modulo"}, "clave": clave, "estado": estado,
             "incluido": incluido, "situacion": _situacion(datos, estado, incluido)}
        faltan = modulo.faltan(carpeta, sesion) if puede_empezar and incluido else {"ficha": [], "otros": []}
        if detalle:
            reanudable = hasattr(modulo, "se_puede_reanudar") and modulo.se_puede_reanudar(carpeta, sesion)
            m |= {"faltan": faltan, "reanudable": reanudable,
                  "gasto_corrida": modulo.gasto_de_la_corrida(carpeta, curso, sesion),
                  "costo_ref": _costo_de_referencia(carpeta, curso, sesion, clave, numeros)}
        materiales.append(m)
        if siguiente or not incluido:
            continue
        e, viejo = estado.get("estado"), estado.get("desactualizado")
        if not puede_empezar:
            siguiente = {"texto": "Guarda completas las dos fichas: así quedan confirmadas.", "ancla": "", "corto": "Fichas"}
        elif e == "trabajando":
            siguiente = {"texto": f"Espera: AulaLista trabaja en {datos['el']}.", "ancla": clave, "corto": datos["corto"]}
        elif e == "aprobada" and not viejo:
            continue
        elif e in ("verificada", "con pendientes") and not viejo:
            siguiente = {"texto": f"Revisa la entrega y aprueba {datos['el']}.", "ancla": clave, "corto": datos["corto"]}
        elif e == "con fallas":
            siguiente = {"texto": f"Resuelve las fallas de {datos['el']} en las fichas y genéra{datos['lo']} de nuevo.",
                         "ancla": clave, "corto": datos["corto"]}
        elif faltan["ficha"] or faltan["otros"]:
            siguiente = {"texto": f"Completa lo que falta para generar {datos['el']}.", "ancla": clave, "corto": datos["corto"]}
        else:
            siguiente = {"texto": f"Genera {datos['el']}.", "ancla": clave, "corto": datos["corto"]}
    if siguiente is None:
        siguiente = {"texto": "Los materiales de esta sesión están aprobados.", "ancla": "", "corto": "Listo"}
    return {"puede_empezar": puede_empezar, "materiales": materiales, "siguiente": siguiente}


def _estado_de_ficha(confirmada: bool, existe: bool) -> dict:
    if confirmada:
        return {"clase": "bien", "texto": "Confirmada"}
    return {"clase": "espera", "texto": "Sin confirmar"} if existe else {"clase": "neutro", "texto": "Sin llenar"}


def _estado_de_fuentes(carpeta) -> dict:
    """Una línea para todas las fuentes: cuántas están listas o qué falta hacer con ellas."""
    indice = convertir.leer_indice(carpeta)
    archivos = [r.name for r in (carpeta / "fuentes").glob("*") if r.is_file()]
    if not archivos:
        return {"clase": "neutro", "texto": "Sin subir"}
    sin_convertir = sum(1 for a in archivos if indice.get(a, {}).get("estado") != convertir.CONVERTIDA)
    if sin_convertir:
        return {"clase": "espera", "texto": f"{sin_convertir} sin convertir"}
    if any(indice[a].get("revisar") and not indice[a].get("revisada") for a in archivos):
        return {"clase": "espera", "texto": "Por revisar"}
    return {"clase": "bien", "texto": "1 lista" if len(archivos) == 1 else f"{len(archivos)} listas"}


def _panel(carpeta, curso: str, actual: str) -> dict:
    """El panel del curso que va a la izquierda de cada página del curso (PLAN.md §0, decisión 38).
    `actual` dice qué página se ve: «curso», «fuentes», «ficha-curso», «ficha-N» o «[material]-N»."""
    ficha_curso = almacen.cargar(carpeta, "curso")
    sesiones = []
    if ficha_curso["confirmada"]:
        for s in almacen.sesiones_del_curso(ficha_curso):
            n = s["numero"]
            vista = _vista_de_materiales(carpeta, curso, n)
            incluidos = [m for m in vista["materiales"] if m["incluido"]]
            sesiones.append({
                "numero": n, "texto": s["texto"],
                "abierta": actual in [f"ficha-{n}"] + [f"{c}-{n}" for c in MATERIALES],
                "ficha": _estado_de_ficha(almacen.cargar(carpeta, "sesion", n)["confirmada"],
                                          almacen.ruta_ficha(carpeta, "sesion", n).exists()),
                "materiales": [{"clave": m["clave"], "corto": m["corto"], "el": m["el"], "plural": m["plural"],
                                "situacion": m["situacion"], "estado": m["estado"].get("estado") or "",
                                "desactualizado": bool(m["estado"].get("desactualizado")),
                                "aprobada": (m["estado"].get("aprobada") or "")[:10],
                                "sigue": m["clave"] == vista["siguiente"]["ancla"]} for m in incluidos],
                "hechos": sum(1 for m in incluidos if m["situacion"]["clase"] == "bien"),
                "van": len(incluidos),
                "siguiente": vista["siguiente"], "puede_empezar": vista["puede_empezar"],
            })
    return {
        "actual": actual,
        "fuentes": _estado_de_fuentes(carpeta),
        "ficha_curso": _estado_de_ficha(ficha_curso["confirmada"], almacen.ruta_ficha(carpeta, "curso").exists()),
        "sesiones": sesiones,
        "gasto": tokens.total(curso),
    }


MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre")


def _fecha(iso: str) -> str:
    """«2026-10-12» → «12 de octubre»."""
    return f"{int(iso[8:10])} de {MESES[int(iso[5:7]) - 1]}" if len(iso) >= 10 else ""


def _motivo(m: dict) -> str:
    """Por qué un material es el paso que sigue, en una oración."""
    los = "las" if m["plural"] else ("lo" if m["el"].startswith("el ") else "la")
    sigue = "siguen" if m["plural"] else "sigue"
    if m["desactualizado"]:
        return f"La ficha cambió después de generar{los}: ya no la {sigue}."
    return {"trabajando": "AulaLista trabaja en esto ahora. La página se actualiza sola.",
            "verificada": "Está listo: revisa la entrega y decide si lo apruebas.",
            "con pendientes": "Está listo, con decisiones pendientes: revísalas y decide si lo apruebas.",
            "con fallas": "Tiene fallas del verificador y no se puede aprobar así.",
            "error": "Se detuvo por un error antes de terminar.",
            "detenida": "Lo detuviste antes de terminar.",
            }.get(m["estado"], "Todavía no se generó.")


def _que_sigue(curso: str, panel: dict) -> dict | None:
    """El primer paso pendiente del curso, en el orden del trabajo: fuentes, ficha del curso y, sesión por sesión,
    su ficha y sus materiales. None si todo está aprobado. Lo enlazan la página de inicio y el tablero, que además
    muestra su motivo y el texto del botón (PLAN.md §0, decisión 44)."""
    base = f"/cursos/{curso}"
    fuentes = panel["fuentes"]["texto"]
    if fuentes == "Sin subir":
        return {"texto": "Sube las fuentes del curso.", "url": base + "#fuentes", "boton": "Ir a las fuentes",
                "motivo": "AulaLista saca de las fuentes todo lo que dicen los materiales."}
    if fuentes.endswith("sin convertir"):
        return {"texto": "Convierte las fuentes a texto.", "url": base + "#fuentes", "boton": "Ir a las fuentes",
                "motivo": f"Hay {fuentes}. AulaLista solo lee fuentes convertidas."}
    if fuentes == "Por revisar":
        return {"texto": "Revisa el texto que la IA leyó de las imágenes.", "url": base + "#fuentes",
                "boton": "Ir a las fuentes", "motivo": "Antes de usarlo, compáralo con el original."}
    if panel["ficha_curso"]["clase"] != "bien":
        return {"texto": "Confirma la ficha del curso.", "url": base + "/ficha", "boton": "Ir a la ficha del curso",
                "motivo": "Las sesiones aparecen al confirmarla."}
    for s in panel["sesiones"]:
        if not s["puede_empezar"]:
            return {"texto": f"Sesión {s['numero']}: confirma su ficha.", "url": f"{base}/sesiones/{s['numero']}/ficha",
                    "boton": "Ir a la ficha de la sesión", "motivo": "Ningún material de la sesión empieza sin ella."}
        if s["siguiente"]["ancla"]:
            m = next(x for x in s["materiales"] if x["clave"] == s["siguiente"]["ancla"])
            texto = s["siguiente"]["texto"]
            if m["desactualizado"] and m["estado"] in ("aprobada", "verificada", "con pendientes"):
                texto = texto.rstrip(".") + " de nuevo."
            return {"texto": f"Sesión {s['numero']}: {texto[:1].lower()}{texto[1:]}",
                    "url": f"{base}/sesiones/{s['numero']}/materiales/{m['clave']}",
                    "boton": f"Ir a {m['el']}", "material": m["clave"], "sesion": s["numero"],
                    "motivo": (f"Falta información para generar{'las' if m['plural'] else ('lo' if m['el'].startswith('el ') else 'la')}. "
                               "La página del material dice qué.") if texto.startswith("Completa") else _motivo(m)}
    return None


def _frase_de_sesion(s: dict) -> str:
    """El avance de una sesión en una oración, para su fila del tablero."""
    problemas = [m for m in s["materiales"] if m["situacion"]["clase"] == "error"]
    faltan = [m for m in s["materiales"] if m["situacion"]["clase"] == "neutro"]
    if not s["puede_empezar"]:
        return "Falta confirmar su ficha."
    if s["hechos"] == s["van"]:
        return "Lista: " + ("su material está aprobado." if s["van"] == 1 else "todos sus materiales están aprobados.")
    frase = f"{s['hechos']} de {s['van']} {'aprobado' if s['van'] == 1 else 'aprobados'}."
    desactualizados = [m for m in problemas if m["desactualizado"]]
    if desactualizados:
        n = len(desactualizados)
        frase += f" La ficha cambió: {'un material quedó desactualizado' if n == 1 else f'{n} materiales quedaron desactualizados'}."
    elif problemas:
        frase += f" {'Un material tiene' if len(problemas) == 1 else f'{len(problemas)} materiales tienen'} problemas."
    if faltan:
        verbo = "Falta" if len(faltan) == 1 and not faltan[0]["plural"] else "Faltan"
        frase += f" {verbo} " + " y ".join(m["el"] for m in faltan) + "."
    return frase


def _tablero(carpeta, curso: str, panel: dict) -> dict:
    """Lo que muestra el tablero del curso (decisión 44): lo que sigue con su costo, una fila por sesión y la
    preparación, que va plegada si está lista."""
    sigue = _que_sigue(curso, panel)
    if sigue and sigue.get("material"):
        gasto = MATERIALES[sigue["material"]]["modulo"].gasto_de_la_corrida(carpeta, curso, sigue["sesion"])
        if gasto and gasto["llamadas"]:
            sigue["costo"] = f"La última vez gastó {gasto['costo_usd']:.2f} USD estimados."
    sesiones = [{**s, "frase": _frase_de_sesion(s),
                 "materiales": [{**m, "fecha": _fecha(m["aprobada"])} for m in s["materiales"]]}
                for s in panel["sesiones"]]
    lista = panel["fuentes"]["clase"] == "bien" and panel["ficha_curso"]["clase"] == "bien"
    return {"sigue": sigue, "sesiones": sesiones, "preparacion_lista": lista,
            "materiales": sum(s["van"] for s in sesiones), "aprobados": sum(s["hechos"] for s in sesiones)}


def _material(material: str) -> dict:
    if material not in MATERIALES:
        raise HTTPException(404, "Ese material no existe.")
    return MATERIALES[material]


def _url_material(curso: str, sesion: int, material: str) -> str:
    return f"/cursos/{curso}/sesiones/{sesion}/materiales/{material}"


# Pasos del recorrido de un material (PLAN.md §0, decisión 38). Cada paso: «hecho», «ahora», «falla» o «pendiente».
PASOS = ("Generar", "Verificar", "Revisar", "Aprobar")


def _recorrido(datos: dict, estado: dict) -> list[dict]:
    """Dónde está el material entre Generar, Verificar, Revisar y Aprobar, con una nota corta por paso.
    Mientras trabaja no se sabe en qué paso va: se muestra «En curso» en Generar."""
    e = estado.get("estado")
    notas = ["Pendiente", "Sin IA", "Con IA, por bloque", "Lo decides tú"]
    clases = ["ahora", "pendiente", "pendiente", "pendiente"]
    if estado.get("desactualizado") and e in ("aprobada", "verificada", "con pendientes"):
        notas[0] = "Las fichas cambiaron"
    elif e == "trabajando":
        notas[0] = "En curso"
    elif e == "detenida":
        notas[0] = _forma(datos, "Detenid") + " por ti"
    elif e == "error":
        clases[0], notas[0] = "falla", "Se detuvo por un error"
    elif e == "con fallas":
        clases[:2], notas[:2] = ["hecho", "falla"], ["Listo", "Con fallas"]
    elif e in ("verificada", "con pendientes", "aprobada"):
        clases = ["hecho", "hecho", "hecho", "hecho" if e == "aprobada" else "ahora"]
        notas[:3] = ["Listo", "Sin fallas", "Con pendientes" if estado.get("entrega") and any(
            s["clave"] == "pendientes" and s["lineas"] for s in estado["entrega"]["secciones"]) else "Sin errores abiertos"]
        if e == "aprobada":
            notas[3] = "El " + (estado.get("aprobada") or "")[:10]
    return [{"paso": p, "clase": c, "nota": n} for p, c, n in zip(PASOS, clases, notas)]


def _listos(carpeta, sesion: int, material: dict, puede_empezar: bool) -> list[str]:
    """Lo que ya se cumple para generar un material. Se muestra con ✓ junto a lo que falta, para que el profesor
    vea que el botón está listo por algo y no tenga que adivinarlo."""
    listos = ["Las dos fichas están confirmadas."] if puede_empezar else []
    if puede_empezar and not material["faltan"]["ficha"]:
        listos.append(f"La ficha de la sesión tiene lo que {'piden' if material['plural'] else 'pide'} {material['el']}.")
    if (puede_empezar and material["clave"] == diapositivas.CLAVE and not material["faltan"]["otros"]
            and diapositivas.usa_lectura(carpeta, sesion)):
        listos.append("La lectura está aprobada.")
    return listos


@app.get("/cursos/{curso}/sesiones/{sesion}")
def ver_sesion(curso: str, sesion: int):
    """La sesión abre en el material del siguiente paso; sin fichas confirmadas, en la ficha de la sesión."""
    carpeta = _carpeta(curso)
    _exigir_ficha_del_curso(carpeta, curso)
    vista = _vista_de_materiales(carpeta, curso, sesion)
    if not vista["puede_empezar"]:
        return RedirectResponse(_url_ficha(curso, sesion), status_code=303)
    incluidos = [m["clave"] for m in vista["materiales"] if m["incluido"]] or list(MATERIALES)
    return RedirectResponse(_url_material(curso, sesion, vista["siguiente"]["ancla"] or incluidos[0]), status_code=303)


@app.get("/cursos/{curso}/sesiones/{sesion}/materiales/{material}")
def ver_material(request: Request, curso: str, sesion: int, material: str, mensaje: str = ""):
    _material(material)
    carpeta = _carpeta(curso)
    _exigir_ficha_del_curso(carpeta, curso)
    vista = _vista_de_materiales(carpeta, curso, sesion, detalle=True)
    m = next(x for x in vista["materiales"] if x["clave"] == material)
    return plantillas.TemplateResponse(request, "material.html", {
        "curso": curso, "nombre": _nombre(curso), "sesion": sesion, "mensaje": mensaje,
        "m": m, "recorrido": _recorrido(m, m["estado"]), "total": len(vista["materiales"]),
        "listos": _listos(carpeta, sesion, m, vista["puede_empezar"]),
        "puede_empezar": vista["puede_empezar"], "siguiente": vista["siguiente"],
        "costo_revisor": tokens.ultima_corrida(curso, "revisor independiente"),
        "panel": _panel(carpeta, curso, f"{material}-{sesion}"),
    })


@app.post("/cursos/{curso}/sesiones/{sesion}/materiales/{material}")
def generar_material(curso: str, sesion: int, material: str):
    modulo = _material(material)["modulo"]
    carpeta = _carpeta(curso)
    destino = _url_material(curso, sesion, material)
    if not almacen.puede_empezar_material(carpeta, sesion):
        return RedirectResponse(destino + "?mensaje=" + quote("Guarda completas las dos fichas antes de generar: así quedan confirmadas."), status_code=303)
    faltan = modulo.faltan(carpeta, sesion)
    if faltan["ficha"]:
        mensaje = "Falta en la ficha de la sesión: " + " ".join(faltan["ficha"])
        return RedirectResponse(destino + "?mensaje=" + quote(mensaje), status_code=303)
    if faltan["otros"]:
        return RedirectResponse(destino + "?mensaje=" + quote(" ".join(faltan["otros"])), status_code=303)
    if modulo.estado(carpeta, sesion).get("estado") == "trabajando":
        return RedirectResponse(destino, status_code=303)
    _trabajo_en_segundo_plano(modulo.generar, carpeta, curso, sesion, clave=(curso, sesion, material))
    return RedirectResponse(destino, status_code=303)


@app.post("/cursos/{curso}/sesiones/{sesion}/materiales/{material}/reanudar")
def reanudar_material(curso: str, sesion: int, material: str):
    """Sigue desde el contenido guardado de la corrida anterior (PLAN.md §0, decisión 40)."""
    modulo = _material(material)["modulo"]
    carpeta = _carpeta(curso)
    destino = _url_material(curso, sesion, material)
    if not hasattr(modulo, "reanudar") or not modulo.se_puede_reanudar(carpeta, sesion):
        mensaje = "No hay un trabajo guardado que se pueda reanudar. Genera el material de nuevo."
        return RedirectResponse(destino + "?mensaje=" + quote(mensaje), status_code=303)
    _trabajo_en_segundo_plano(modulo.reanudar, carpeta, curso, sesion, clave=(curso, sesion, material))
    return RedirectResponse(destino, status_code=303)


@app.post("/cursos/{curso}/sesiones/{sesion}/materiales/{material}/revisor")
def revisor_del_material(curso: str, sesion: int, material: str):
    """El revisor independiente opcional (PLAN.md §0, decisión 22): lo pide el profesor."""
    datos = _material(material)
    carpeta = _carpeta(curso)
    destino = _url_material(curso, sesion, material)
    if datos["modulo"].estado(carpeta, sesion).get("estado") not in ("verificada", "con pendientes", "aprobada"):
        generado = "generadas" if datos["plural"] else "generada"
        mensaje = f"El revisor revisa {datos['el']} ya {generado} y sin fallas."
        return RedirectResponse(destino + "?mensaje=" + quote(mensaje), status_code=303)
    _trabajo_en_segundo_plano(datos["modulo"].revisar_con_revisor, carpeta, curso, sesion, clave=(curso, sesion, material))
    return RedirectResponse(destino, status_code=303)


@app.post("/cursos/{curso}/sesiones/{sesion}/materiales/{material}/detener")
def detener_material(curso: str, sesion: int, material: str):
    """Cancela la generación en curso. Si no hay ninguna (el servidor se cerró a mitad de camino),
    libera el material que quedó en «Trabajando»."""
    datos = _material(material)
    destino = _url_material(curso, sesion, material)
    with _CANDADO:
        trabajo = _TRABAJOS.get((curso, sesion, material))
    if trabajo:
        bucle, tarea = trabajo
        bucle.call_soon_threadsafe(tarea.cancel)
        mensaje = f"Deteniendo {datos['el']}. La llamada a Claude en curso se corta."
    elif datos["modulo"].marcar_detenida(_carpeta(curso), sesion):
        mensaje = "Trabajo detenido."
    else:
        mensaje = f"{datos['el'].capitalize()} no {'estaban' if datos['plural'] else 'estaba'} trabajando."
    return RedirectResponse(destino + "?mensaje=" + quote(mensaje), status_code=303)


@app.post("/cursos/{curso}/sesiones/{sesion}/materiales/{material}/aprobar")
def aprobar_material(curso: str, sesion: int, material: str):
    datos = _material(material)
    destino = _url_material(curso, sesion, material)
    try:
        datos["modulo"].aprobar(_carpeta(curso), sesion)
    except datos["modulo"].NoSePuedeAprobar as error:
        return RedirectResponse(destino + "?mensaje=" + quote(str(error)), status_code=303)
    return RedirectResponse(destino + "?mensaje=" + quote(datos["aprobado"]), status_code=303)


@app.get("/cursos/{curso}/sesiones/{sesion}/descargar/{archivo}")
def descargar(curso: str, sesion: int, archivo: str):
    carpeta = lectura.carpeta_materiales(_carpeta(curso), sesion)
    ruta = carpeta / Path(archivo).name
    if not ruta.is_file():
        raise HTTPException(404, "Ese archivo no existe.")
    return FileResponse(ruta, filename=ruta.name)
