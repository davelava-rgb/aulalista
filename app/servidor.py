"""Servidor local. Responde solo a esta computadora (127.0.0.1)."""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import agente, tokens
from app.config import RAIZ, FaltaClave

app = FastAPI(title="AulaLista")
app.mount("/estaticos", StaticFiles(directory=RAIZ / "web" / "estaticos"), name="estaticos")
plantillas = Jinja2Templates(directory=RAIZ / "web" / "plantillas")


@app.get("/")
def inicio(request: Request):
    return plantillas.TemplateResponse(
        request, "inicio.html", {"gasto": tokens.total(tokens.CURSO_SISTEMA)}
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
