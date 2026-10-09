"""Servidor local. Responde solo a esta computadora (127.0.0.1)."""

import asyncio
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import agente, cursos, tokens
from app.config import RAIZ, FaltaClave
from app.fuentes import convertir

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
    return plantillas.TemplateResponse(
        request,
        "curso.html",
        {
            "curso": curso,
            "nombre": cursos.nombre(curso),
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
