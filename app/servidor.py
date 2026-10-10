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
from app.fichas import almacen, flujo
from app.fichas import plantillas as plantillas_fichas
from app.fuentes import convertir
from app.materiales import lectura

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


def lector_de_imagenes(curso: str) -> convertir.LectorImagen:
    async def leer(imagen: bytes, tipo: str, etiqueta: str) -> list[str]:
        return await agente.leer_imagen(imagen, tipo, curso=curso, etiqueta=etiqueta)
    return leer


# ---------- Inicio y conexión ----------

@app.get("/")
def inicio(request: Request, mensaje: str = ""):
    return plantillas.TemplateResponse(
        request,
        "inicio.html",
        {"gasto": tokens.total(tokens.CURSO_SISTEMA), "cursos": cursos.listar(), "mensaje": mensaje},
    )


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
    sesiones = []
    for s in almacen.sesiones_del_curso(ficha_curso):
        ficha_sesion = almacen.cargar(carpeta, "sesion", s["numero"])
        sesiones.append({**s, "confirmada": ficha_sesion["confirmada"],
                         "existe": almacen.ruta_ficha(carpeta, "sesion", s["numero"]).exists()})
    return plantillas.TemplateResponse(
        request,
        "curso.html",
        {
            "curso": curso,
            "nombre": cursos.nombre(curso),
            "ficha_curso": ficha_curso,
            "ficha_curso_existe": almacen.ruta_ficha(carpeta, "curso").exists(),
            "sesiones": sesiones,
            "fuentes": fuentes,
            "pendientes": sum(1 for f in fuentes if f["estado"] != convertir.CONVERTIDA),
            "gasto": tokens.total(curso),
            "mensaje": mensaje,
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
            "nombre": cursos.nombre(curso),
            "archivo": archivo,
            "entrada": entrada,
            "pasajes": convertir.leer_pasajes(carpeta, archivo),
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


def _url_ficha(curso: str, sesion: int | None) -> str:
    return f"/cursos/{curso}/ficha" if sesion is None else f"/cursos/{curso}/sesiones/{sesion}/ficha"


def _pagina_ficha(request: Request, curso: str, tipo: str, sesion: int | None, mensaje: str = "", errores=None):
    carpeta = _carpeta(curso)
    ficha = almacen.cargar(carpeta, tipo, sesion)
    titulo = TITULOS_FICHA[tipo] + (f" {sesion}" if sesion else "")
    desactualizados = []
    if sesion is not None:
        desactualizados = [n for n, m in almacen.cargar_estado(carpeta, sesion)["materiales"].items() if m.get("desactualizado")]
    return plantillas.TemplateResponse(request, "ficha.html", {
        "curso": curso, "nombre": cursos.nombre(curso), "titulo": titulo, "ficha": ficha,
        "propuesta": flujo.estado_propuesta(carpeta, tipo, sesion),
        "hay_propuestos": any((d or {}).get("estado") == almacen.PROPUESTO for d in ficha["campos"].values()),
        "secciones": plantillas_fichas.vista(tipo, ficha["campos"]),
        "preguntas": almacen.preguntas_pendientes(ficha),
        "errores": errores or [], "mensaje": mensaje,
        "versiones": almacen.listar_versiones(carpeta, tipo, sesion),
        "url_restaurar": _url_ficha(curso, sesion) + "/restaurar",
        "desactualizados": desactualizados,
    })


def _exigir_ficha_del_curso(carpeta, curso):
    if not almacen.cargar(carpeta, "curso")["confirmada"]:
        raise HTTPException(409, "Confirma primero la ficha del curso.")


async def _accion_ficha(request: Request, curso: str, tipo: str, sesion: int | None):
    carpeta = _carpeta(curso)
    formulario = dict(await request.form())
    accion = formulario.pop("accion", "guardar")
    ficha = almacen.cargar(carpeta, tipo, sesion)
    if almacen.aplicar_formulario(ficha, formulario) or not almacen.ruta_ficha(carpeta, tipo, sesion).exists():
        almacen.guardar(carpeta, tipo, sesion, ficha, "editada por el profesor")
    mensaje, errores = "Ficha guardada.", []
    try:
        if accion == "aceptar":
            flujo.aceptar_propuestos(ficha)
            almacen.guardar(carpeta, tipo, sesion, ficha, "propuesta aceptada")
            accion = "confirmar"
        if accion == "proponer":
            resumen = await asyncio.to_thread(
                lambda: asyncio.run(flujo.proponer(carpeta, curso, tipo, sesion))
            )
            if resumen.get("sin_fuentes"):
                mensaje = "No hay fuentes convertidas que se puedan usar. Llena la ficha a mano o sube fuentes."
            else:
                mensaje = (f"Datos tomados de las fuentes: {resumen['de_las_fuentes']}. "
                           f"Propuestos: {resumen['propuestos']}. Con dos versiones: {resumen['conflictos']}.")
        if accion == "confirmar":
            if tipo == "curso":
                resultado = flujo.confirmar_curso(carpeta)
                sesiones = ", ".join(f"S{n}" for n in resultado["desactualizados"])
                mensaje = "Ficha del curso confirmada." + (
                    f" Se actualizó la verificación de las sesiones {sesiones}." if sesiones else "")
            else:
                await asyncio.to_thread(lambda: asyncio.run(flujo.confirmar_sesion(carpeta, curso, sesion)))
                mensaje = "Ficha de la sesión confirmada. Se escribió verificacion.json."
    except almacen.FichaIncompleta as error:
        mensaje, errores = "La ficha no se confirmó.", error.errores
    except flujo.FichaDelCursoSinConfirmar as error:
        mensaje = str(error)
    except (FaltaClave, agente.ErrorDeAgente) as error:
        mensaje = str(error)
    return _pagina_ficha(request, curso, tipo, sesion, mensaje, errores)


def _proponer_si_corresponde(curso: str, tipo: str, sesion: int | None) -> None:
    """Con fuentes convertidas, una ficha vacía se propone sola al abrirla (PLAN.md §0, decisión 17)."""
    carpeta = _carpeta(curso)
    if flujo.debe_proponer_sola(carpeta, tipo, sesion):
        flujo.marcar_propuesta_en_curso(carpeta, tipo, sesion)
        _trabajo_en_segundo_plano(flujo.proponer_sola, carpeta, curso, tipo, sesion)


@app.get("/cursos/{curso}/ficha")
def ver_ficha_del_curso(request: Request, curso: str):
    _proponer_si_corresponde(curso, "curso", None)
    return _pagina_ficha(request, curso, "curso", None)


@app.post("/cursos/{curso}/ficha")
async def accion_ficha_del_curso(request: Request, curso: str):
    return await _accion_ficha(request, curso, "curso", None)


@app.get("/cursos/{curso}/sesiones/{sesion}/ficha")
def ver_ficha_de_la_sesion(request: Request, curso: str, sesion: int):
    _exigir_ficha_del_curso(_carpeta(curso), curso)
    _proponer_si_corresponde(curso, "sesion", sesion)
    return _pagina_ficha(request, curso, "sesion", sesion)


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


@app.get("/cursos/{curso}/sesiones/{sesion}")
def ver_sesion(request: Request, curso: str, sesion: int, mensaje: str = ""):
    carpeta = _carpeta(curso)
    _exigir_ficha_del_curso(carpeta, curso)
    return plantillas.TemplateResponse(request, "sesion.html", {
        "curso": curso, "nombre": cursos.nombre(curso), "sesion": sesion, "mensaje": mensaje,
        "puede_empezar": almacen.puede_empezar_material(carpeta, sesion),
        "faltan_lectura": almacen.faltantes_para(carpeta, sesion, lectura.CLAVE)
        if almacen.puede_empezar_material(carpeta, sesion) else [],
        "lectura": lectura.estado(carpeta, sesion),
        "gasto": tokens.total(curso),
    })


@app.post("/cursos/{curso}/sesiones/{sesion}/materiales/lectura")
def generar_lectura(curso: str, sesion: int):
    carpeta = _carpeta(curso)
    destino = f"/cursos/{curso}/sesiones/{sesion}"
    if not almacen.puede_empezar_material(carpeta, sesion):
        return RedirectResponse(destino + "?mensaje=" + quote("Confirma las dos fichas antes de generar."), status_code=303)
    faltan = almacen.faltantes_para(carpeta, sesion, lectura.CLAVE)
    if faltan:
        return RedirectResponse(destino + "?mensaje=" + quote("Falta en la ficha de la sesión: " + " ".join(faltan)),
                                status_code=303)
    if lectura.estado(carpeta, sesion).get("estado") == "trabajando":
        return RedirectResponse(destino, status_code=303)
    _trabajo_en_segundo_plano(lectura.generar, carpeta, curso, sesion, clave=(curso, sesion, lectura.CLAVE))
    return RedirectResponse(destino, status_code=303)


@app.post("/cursos/{curso}/sesiones/{sesion}/materiales/lectura/revisor")
def revisor_de_la_lectura(curso: str, sesion: int):
    """El revisor independiente opcional (PLAN.md §0, decisión 22): lo pide el profesor."""
    carpeta = _carpeta(curso)
    destino = f"/cursos/{curso}/sesiones/{sesion}"
    if lectura.estado(carpeta, sesion).get("estado") not in ("verificada", "con pendientes", "aprobada"):
        return RedirectResponse(destino + "?mensaje=" + quote("El revisor revisa una lectura generada y sin fallas."),
                                status_code=303)
    _trabajo_en_segundo_plano(lectura.revisar_con_revisor, carpeta, curso, sesion, clave=(curso, sesion, lectura.CLAVE))
    return RedirectResponse(destino, status_code=303)


@app.post("/cursos/{curso}/sesiones/{sesion}/materiales/lectura/detener")
def detener_lectura(curso: str, sesion: int):
    """Cancela la generación en curso. Si no hay ninguna (el servidor se cerró a mitad de camino),
    libera la lectura que quedó en «Trabajando»."""
    destino = f"/cursos/{curso}/sesiones/{sesion}"
    with _CANDADO:
        trabajo = _TRABAJOS.get((curso, sesion, lectura.CLAVE))
    if trabajo:
        bucle, tarea = trabajo
        bucle.call_soon_threadsafe(tarea.cancel)
        mensaje = "Deteniendo la lectura. La llamada a Claude en curso se corta."
    elif lectura.marcar_detenida(_carpeta(curso), sesion):
        mensaje = "Trabajo detenido."
    else:
        mensaje = "La lectura no estaba trabajando."
    return RedirectResponse(destino + "?mensaje=" + quote(mensaje), status_code=303)


@app.post("/cursos/{curso}/sesiones/{sesion}/materiales/lectura/aprobar")
def aprobar_lectura(curso: str, sesion: int):
    destino = f"/cursos/{curso}/sesiones/{sesion}"
    try:
        lectura.aprobar(_carpeta(curso), sesion)
    except lectura.NoSePuedeAprobar as error:
        return RedirectResponse(destino + "?mensaje=" + quote(str(error)), status_code=303)
    return RedirectResponse(destino + "?mensaje=" + quote("Lectura aprobada."), status_code=303)


@app.get("/cursos/{curso}/sesiones/{sesion}/descargar/{archivo}")
def descargar(curso: str, sesion: int, archivo: str):
    carpeta = lectura.carpeta_materiales(_carpeta(curso), sesion)
    ruta = carpeta / Path(archivo).name
    if not ruta.is_file():
        raise HTTPException(404, "Ese archivo no existe.")
    return FileResponse(ruta, filename=ruta.name)
