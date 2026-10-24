"""Servidor local. Responde solo a esta computadora (127.0.0.1)."""

import asyncio
from datetime import datetime
import json
import re
import threading
import unicodedata
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import agente, cursos, tokens
from app.config import RAIZ, FaltaClave
from app.fichas import almacen, controles, dependencias, flujo
from app.fichas import plantillas as plantillas_fichas
from app.fuentes import convertir
from app.materiales import actividad, comun, diapositivas, evaluacion, laboratorio, lectura

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

def _resumen_de_curso(curso: str) -> dict:
    """Un curso en una línea, para la página de inicio y el panel de cursos (PLAN.md §0, decisión 50):
    su avance en palabras («5 de 16», «Sin ficha», «Completo») y si tiene un material con problemas."""
    panel = _panel(cursos.carpeta(curso), curso, "inicio")
    materiales = [m for s in panel["sesiones"] for m in s["materiales"]]
    aprobados = sum(1 for m in materiales if m["situacion"]["clase"] == "bien")
    if panel["ficha_curso"]["clase"] != "bien":
        avance = "Sin ficha"
    elif not materiales:
        avance = "Sin materiales"
    elif aprobados == len(materiales):
        avance = "Completo"
    else:
        avance = f"{aprobados} de {len(materiales)}"
    con_problema = [f"Sesión {s['numero']}: {m['corto'].lower()} {m['situacion']['texto'].lower()}"
                    for s in panel["sesiones"] for m in s["materiales"] if m["situacion"]["clase"] == "error"]
    return {"curso": curso, "nombre": _nombre(curso), "avance": avance, "alerta": bool(con_problema),
            "con_problema": con_problema, "aprobados": aprobados, "materiales": len(materiales),
            "sesiones": len(panel["sesiones"]), "tramos": [m["situacion"]["clase"] for m in materiales],
            "gasto": panel["gasto"], "sigue": _que_sigue(curso, panel)}


def _cursos_del_panel() -> list[dict]:
    """Todos los cursos, en el orden de sus carpetas, cada uno con su resumen."""
    return [_resumen_de_curso(c["curso"]) for c in cursos.listar()]


def _gasto_total(lista: list[dict]) -> dict:
    """Lo que gastó AulaLista entera: los cursos de la lista más las pruebas de conexión."""
    sistema = tokens.total(tokens.CURSO_SISTEMA)
    return {"llamadas": sistema["llamadas"] + sum(c["gasto"]["llamadas"] for c in lista),
            "costo_usd": sistema["costo_usd"] + sum(c["gasto"]["costo_usd"] for c in lista)}


@app.get("/")
def inicio(request: Request, mensaje: str = ""):
    """Abre el último curso usado (PLAN.md §0, decisión 50). Sin cursos, o si el último ya no existe, muestra la
    página de inicio con el formulario para crear uno."""
    ultimo = cursos.ultimo()
    if ultimo and not mensaje:
        return _ir_al_curso(ultimo)
    lista = _cursos_del_panel()
    sistema = tokens.total(tokens.CURSO_SISTEMA)
    total = _gasto_total(lista)
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

@app.get("/curso-nuevo")
def curso_nuevo(request: Request, mensaje: str = ""):
    """La página corta a la que lleva «Nuevo» en el panel: solo el formulario para crear un curso (decisión 50)."""
    return plantillas.TemplateResponse(request, "curso_nuevo.html", {"mensaje": mensaje, "ultimo": cursos.ultimo()})


@app.post("/cursos")
def crear_curso(nombre: str = Form(...)):
    try:
        curso = cursos.crear(nombre)
    except cursos.ErrorDeCurso as error:
        return RedirectResponse(f"/curso-nuevo?mensaje={quote(str(error))}", status_code=303)
    return _ir_al_curso(curso)


@app.get("/cursos/{curso}")
def ver_curso(request: Request, curso: str, mensaje: str = ""):
    carpeta = _carpeta(curso)
    cursos.guardar_ultimo(curso)
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
            # Lo que falta leer con IA: fuentes sin convertir, imágenes sueltas y páginas o láminas escaneadas.
            "pendientes": sum(1 for f in fuentes if f["estado"] != convertir.CONVERTIDA or f.get("falta_ia")),
            "imagenes_por_leer": _imagenes(n) if (n := sum(f.get("falta_ia", 0) for f in fuentes)) else "",
            "mensaje": mensaje,
            "panel": (panel := _panel(carpeta, curso, "curso")),
            "tablero": _tablero(carpeta, curso, panel),
        },
    )


def _convertir(carpeta, lector) -> tuple[dict, list[str]]:
    """Convierte lo nuevo o cambiado y devuelve el índice y las fuentes que cambiaron. Corre en un hilo aparte:
    Office y la IA pueden tardar sin trabar el servidor."""
    antes = convertir.leer_indice(carpeta)
    indice = asyncio.run(convertir.convertir_curso(carpeta, lector))
    cambiadas = [n for n, e in indice.items() if antes.get(n) != e]
    if cambiadas:
        # Una fuente con otro contenido desactualiza los materiales de las sesiones que la usan (decisión 62).
        for numero in almacen.sesiones_confirmadas(carpeta):
            dependencias.revisar(carpeta, numero)
    return indice, cambiadas


def _imagenes(n: int) -> str:
    return "Una imagen o página escaneada" if n == 1 else f"{n} imágenes o páginas escaneadas"


def _resumen_de_conversion(indice: dict, cambiadas: list[str], con_ia: bool) -> str:
    fallidas = [n for n in cambiadas if indice[n]["estado"] == convertir.NO_SE_PUEDE_LEER]
    esperan = [n for n in cambiadas if indice[n]["estado"] == convertir.ESPERA_IA]
    hechas = len(cambiadas) - len(fallidas) - len(esperan)
    if not cambiadas:
        mensaje = "No había nada nuevo que convertir."
    else:
        mensaje = f"Fuentes {'leídas con IA' if con_ia else 'convertidas'}: {hechas}."
    if fallidas:
        mensaje += f" No se pudieron leer: {', '.join(fallidas)}."
    paginas = sum(e.get("falta_ia", 0) for e in indice.values())
    if paginas:
        mensaje += f" {_imagenes(paginas)} se {'lee' if paginas == 1 else 'leen'} con IA cuando pulses «Leer con IA lo que falta»."
    return mensaje


@app.post("/cursos/{curso}/fuentes")
async def subir_fuentes(curso: str, archivos: list[UploadFile]):
    carpeta = _carpeta(curso)
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
    if guardados:
        # Se convierte enseguida lo que no necesita IA (texto de PDF, Word, PowerPoint y Excel): no gasta.
        # Las imágenes y las páginas escaneadas quedan anotadas y se leen con IA solo si el profesor lo pide.
        indice, cambiadas = await asyncio.to_thread(_convertir, carpeta, None)
        mensaje += " " + _resumen_de_conversion(indice, cambiadas, con_ia=False)
    return _ir_al_curso(curso, mensaje)


@app.post("/cursos/{curso}/convertir")
def convertir_fuentes(curso: str):
    """Lee con IA las imágenes y las páginas escaneadas pendientes, y convierte lo que falte."""
    carpeta = _carpeta(curso)
    indice, cambiadas = _convertir(carpeta, lector_de_imagenes(curso))
    return _ir_al_curso(curso, _resumen_de_conversion(indice, cambiadas, con_ia=True))


PASAJES_POR_TRAMO = 100


def _plano(texto: str) -> str:
    """Para buscar sin distinguir tildes ni mayúsculas. Cada letra da una sola letra: las posiciones no cambian."""
    return "".join(unicodedata.normalize("NFD", c)[0].lower()[:1] for c in texto)


def _partes(texto: str, buscado: str) -> list[dict]:
    """El texto en partes, con lo que coincide con la búsqueda marcado, para resaltarlo en la página."""
    if not buscado:
        return [{"texto": texto, "marca": False}]
    plano, partes, desde = _plano(texto), [], 0
    while (i := plano.find(buscado, desde)) >= 0:
        partes += [{"texto": texto[desde:i], "marca": False}, {"texto": texto[i:i + len(buscado)], "marca": True}]
        desde = i + len(buscado)
    return partes + [{"texto": texto[desde:], "marca": False}]


@app.get("/cursos/{curso}/fuentes/{archivo}")
def ver_fuente(request: Request, curso: str, archivo: str, q: str = "", pagina: str = "", tramo: int = 1):
    """Una fuente convertida, por tramos de pasajes. Se busca por texto (sin distinguir tildes ni mayúsculas) y por
    página, en el servidor: la página funciona sin JavaScript y no carga miles de filas de una vez."""
    carpeta = _carpeta(curso)
    entrada = convertir.leer_indice(carpeta).get(archivo)
    if entrada is None:
        raise HTTPException(404, "Esa fuente no está convertida.")
    todos = convertir.leer_pasajes(carpeta, archivo)
    q = " ".join(q.split())
    buscado = _plano(q)
    numero = int(pagina) if pagina.strip().isdigit() else None
    hallados = [p for p in todos if (numero is None or p.get("pagina") == numero)
                and (not buscado or buscado in _plano(p["texto"]))]
    tramos = max(1, -(-len(hallados) // PASAJES_POR_TRAMO))
    tramo = min(max(tramo, 1), tramos)
    desde = (tramo - 1) * PASAJES_POR_TRAMO
    pasajes = [{**p, "partes": _partes(p["texto"], buscado)} for p in hallados[desde:desde + PASAJES_POR_TRAMO]]
    paginas = [p["pagina"] for p in todos if isinstance(p.get("pagina"), int)]
    return plantillas.TemplateResponse(
        request,
        "fuente.html",
        {
            "curso": curso,
            "nombre": _nombre(curso),
            "archivo": archivo,
            "entrada": entrada,
            "pasajes": pasajes,
            "busqueda": {"q": q, "pagina": numero, "filtrada": bool(q or numero), "hallados": len(hallados),
                         "total": len(todos), "tramo": tramo, "tramos": tramos, "desde": desde + 1,
                         "hasta": desde + len(pasajes), "ultima_pagina": max(paginas) if paginas else None},
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
        # Cada uno con su enlace: la línea dice qué hay que generar de nuevo y lleva a hacerlo.
        claves = [n for n, m in almacen.cargar_estado(carpeta, sesion)["materiales"].items()
                  if m.get("desactualizado") and n in MATERIALES]
        desactualizados = [{"el": MATERIALES[n]["el"], "url": _url_material(curso, sesion, n)} for n in claves]
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
    return plantillas.TemplateResponse(request, "ficha.html", {
        "curso": curso, "nombre": _nombre(curso), "titulo": titulo, "sesion": sesion, "ficha": ficha,
        "hay_propuestos": any((d or {}).get("estado") == almacen.PROPUESTO for d in ficha["campos"].values()),
        "secciones": secciones, "modo_lectura": ficha["confirmada"], "generados": generados, "generados_texto": _y(generados),
        # En la sesión, Guardar llama a la IA (decisión 54): el botón lo dice, no solo la nota de abajo.
        "guardar_texto": ("Guardar" if not sesion else "Guardar y preparar el plan con IA"
                          if flujo.plan_por_preparar(ficha) else "Guardar y revisar con IA"),
        "campos_sin_efecto": list(almacen.CAMPOS_SIN_EFECTO),
        # En la sesión solo se pregunta por la ficha corta: el plan lo prepara AulaLista (decisión 54).
        "preguntas": [p for p in almacen.preguntas_pendientes(ficha, maximo=10_000)
                      if tipo == "curso" or p["id"] not in plantillas_fichas.ids_del_plan()
                      ][:almacen.MAX_PREGUNTAS_POR_VEZ],
        "errores": errores or [], "mensaje": mensaje, "corregibles": corregibles,
        "versiones": almacen.listar_versiones(carpeta, tipo, sesion),
        "url_restaurar": _url_ficha(curso, sesion) + "/restaurar",
        "panel": _panel(carpeta, curso, "ficha-curso" if sesion is None else f"ficha-{sesion}"),
        "desactualizados": desactualizados,
        "completar": {d["seccion"]: {"clave": c, **d} for c, d in flujo.COMPLETAR.items()} if tipo == "curso" else {},
        "base": json.dumps(almacen.valores_de(ficha), ensure_ascii=False),
        "cobertura": flujo.cobertura_vigente(ficha) if tipo == "curso" else None,
        "sin_revisar": flujo.fuentes_sin_revisar(carpeta) if tipo == "curso" else [],
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
        s["plan"] = s.get("titulo", "").startswith(plantillas_fichas.SECCIONES_DEL_PLAN)
        s["alertas"] = sum(1 for c in campos if c["estado"] in ALERTAS)
        # La fuente que más se repite se dice una vez en la sección; cada campo dice solo la suya si es otra.
        origenes = [c["origen"] for c in campos if c.get("origen") and c["origen"] != "profesor"]
        comun = max(set(origenes), key=origenes.count) if origenes else ""
        if origenes.count(comun) < 2:
            comun = ""
        s["origen_comun"] = comun
        for c in campos:
            c["origen_visible"] = c["origen"] if c.get("origen") not in ("", None, "profesor", comun) else ""
        _resumen_de_seccion(s, campos)
    # El número que se ve sigue el orden en pantalla: en la ficha de la sesión, las secciones del plan van al final,
    # plegadas (decisión 54). Sin esto se leía «1. Sesión» y después «6. Materiales de esta sesión».
    for orden, s in enumerate([s for s in secciones if not s["plan"]] + [s for s in secciones if s["plan"]], 1):
        s["orden"] = orden
        s["nombre"] = re.sub(r"^\d+\.\s*", f"{orden}. ", s.get("titulo", ""))
    return secciones


def _etiqueta_corta(etiqueta: str) -> str:
    """Para el resumen de la ficha: sin la explicación entre paréntesis ni la que va después de dos puntos.
    «Alcance (obligatorio)» → «Alcance»; «Material de referencia: una línea por archivo…» → «Material de referencia».
    La etiqueta completa sigue en el campo de edición y como texto emergente."""
    corta = re.split(r":\s| \(", etiqueta, maxsplit=1)[0].strip()
    return corta or etiqueta.strip()


def _resumen_de_seccion(s: dict, campos: list[dict]) -> None:
    """Lo que muestra la ficha en modo de lectura (PLAN.md §0, decisión 45): el estado de la sección, un resumen de
    sus campos y, si repite bloques (ejercicios o preguntas), una fila por bloque con datos."""
    s["estado"] = ("alerta" if s["alertas"] else "completa" if any(c["valor"].strip() for c in campos) else "vacia")
    s["resumen"], s["filas"], s["vacios"] = [], [], 0
    valores = {c.get("id", ""): c["valor"] for c in campos}
    for e in s["elementos"]:
        if e.get("repetible"):
            for b in e["bloques"]:
                if b["situacion"] == "vacio":
                    s["vacios"] += 1
                    continue
                valores = [" ".join(c["valor"].split()) for c in b["campos"]]
                s["filas"].append({"nombre": "Pregunta" if e.get("nombre") == "pregunta" else "Ejercicio",
                                   "numero": b["numero"], "situacion": b["situacion"],
                                   "titulo": valores[0] if valores else "", "detalle": valores[1] if len(valores) > 1 else ""})
        else:
            for c in (e["campos"] if e.get("grupo") else [e]):
                if not controles.se_muestra(c.get("id", ""), valores):
                    continue        # una pregunta que no aplica no se resume (por ejemplo, los adjuntos sin IA)
                # En un campo de varias líneas, cada línea es un elemento (una sesión, un concepto): se separan con
                # «;» para no leerlos pegados. En los demás, el salto de línea es solo de la escritura.
                lineas = [" ".join(linea.split()) for linea in c["valor"].splitlines() if linea.strip()]
                # «Ya vieron» y «No adelantar» son listas de títulos aunque se escriban en un campo de una línea.
                lista = c.get("multilinea") or c.get("id") in ("sesion.ya_vieron", "sesion.no_adelantar")
                s["resumen"].append({"etiqueta": _etiqueta_corta(c["etiqueta"]), "completa": c["etiqueta"],
                                     "valor": ("; " if lista else " ").join(lineas)})


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
    base = formulario.pop("base", None)
    if base:
        formulario = almacen.solo_lo_cambiado(formulario, json.loads(base))
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
        elif accion == "guardar" and tipo == "sesion" and not almacen.cargar(carpeta, tipo, sesion)["confirmada"]:
            # En la sesión, Guardar prepara el plan, lo acepta, revisa los ejercicios y confirma (decisión 54).
            resultado = await asyncio.to_thread(
                lambda: asyncio.run(flujo.preparar_y_confirmar(carpeta, curso, sesion))
            )
            mensaje = " ".join(resultado["mensajes"])
            if resultado["errores"]:
                mensaje = " ".join(["Ficha guardada.", *resultado["mensajes"], "Todavía no está confirmada."])
                errores = resultado["errores"]
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


@app.get("/cursos/{curso}/ficha")
def ver_ficha_del_curso(request: Request, curso: str):
    # Abrir la ficha nunca gasta: la propuesta desde las fuentes la pide el profesor con su botón (decisión 17).
    return _pagina_ficha(request, curso, "curso", None, *_AVISOS_FICHA.pop(_url_ficha(curso, None), ("", None)))


@app.post("/cursos/{curso}/ficha")
async def accion_ficha_del_curso(request: Request, curso: str):
    return await _accion_ficha(request, curso, "curso", None)


@app.get("/cursos/{curso}/sesiones/{sesion}/ficha")
def ver_ficha_de_la_sesion(request: Request, curso: str, sesion: int):
    _exigir_ficha_del_curso(_carpeta(curso), curso)
    # Lo que la ficha corta toma de la del curso, sin IA (decisión 54). La ficha ya no se propone sola al abrirla:
    # el plan lo prepara «Guardar», así abrir una ficha nunca gasta.
    llenados = flujo.llenar_desde_el_curso(_carpeta(curso), sesion)
    mensaje, errores = _AVISOS_FICHA.pop(_url_ficha(curso, sesion), ("", None))
    if llenados and not mensaje:
        # Se dice qué se llenó solo: si no, el profesor no nota que la ficha se completó sola (pedido del 2026-10-23).
        nombres = [plantillas_fichas.etiqueta_corta("sesion", c) for c in llenados]
        mensaje = (f"AulaLista llenó {_y(['«' + n + '»' for n in nombres])} con la ficha del curso. "
                   "Revisa esos campos antes de guardar: cámbialos si hace falta.")
    return _pagina_ficha(request, curso, "sesion", sesion, mensaje, errores)


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


def _trabajo_en_segundo_plano(funcion, *argumentos, clave: tuple | None = None, **opciones) -> threading.Thread:
    """Corre un material en otro hilo. La página consulta el avance en estado.json.
    Con `clave`, el trabajo queda registrado para que el botón Detener lo pueda cancelar. `opciones` van a la función
    por nombre (las casillas de Generar, decisión 74)."""
    async def principal():
        if clave:
            with _CANDADO:
                _TRABAJOS[clave] = (asyncio.get_running_loop(), asyncio.current_task())
        try:
            await funcion(*argumentos, **opciones)
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
    # «opciones»: casillas junto a Generar (decisión 74 c y d). «nombre» es el campo del formulario y «parametro» el
    # argumento de `generar` del módulo. Van apagadas salvo que el módulo sugiera otra cosa (`ejecucion_sugerida`).
    diapositivas.CLAVE: {"modulo": diapositivas, "numero": 2, "titulo": "Diapositivas", "corto": "Diapositivas",
                         "el": "las diapositivas", "plural": True, "o": "a", "lo": "las",
                         "aprobado": "Diapositivas aprobadas.", "generar": "Generar diapositivas",
                         "opciones": [{"nombre": "revision_visual", "parametro": "revision_visual",
                                       "etiqueta": "Revisión visual del diseño",
                                       "nota": "Opcional. Claude mira la imagen de cada diapositiva diseñada y propone "
                                               "cambios de composición; el diseñador los aplica. Usa IA."}]},
    laboratorio.CLAVE: {"modulo": laboratorio, "numero": 3, "titulo": "Laboratorio y archivos de práctica",
                        "corto": "Laboratorio", "el": "el laboratorio", "plural": False, "o": "o", "lo": "lo",
                        "aprobado": "Laboratorio aprobado.", "generar": "Generar laboratorio",
                        "opciones": [{"nombre": "ejecucion", "parametro": "ejecutar_ejercicios",
                                      "etiqueta": "Ejecutar cada ejercicio como un alumno",
                                      "nota": "Opcional. Las fórmulas corren en Excel y los prompts en Claude; lo que "
                                              "sale se compara con la respuesta de la ficha. Usa IA."}]},
    # Decisión 57: el contenido validado y su vista (fases 8a y 8b). La página del alumno llega en la fase 8c.
    actividad.CLAVE: {"modulo": actividad, "numero": 4, "titulo": "Actividad web", "corto": "Actividad",
                      "el": "la actividad web", "plural": False, "o": "a", "lo": "la",
                      "aprobado": "Actividad web aprobada.", "generar": "Generar actividad web"},
    # Decisión 64 (etapa 9): la evaluación práctica (PBQ) con su clave. Sale de la lectura y del laboratorio aprobados.
    evaluacion.CLAVE: {"modulo": evaluacion, "numero": 5, "titulo": "Evaluación práctica y clave", "corto": "Evaluación",
                       "el": "la evaluación", "plural": False, "o": "a", "lo": "la",
                       "aprobado": "Evaluación aprobada.", "generar": "Generar evaluación"},
}

# La práctica interactiva y la guía del profesor no se generan (PLAN.md §0, decisiones 34 y 35).


def _y(partes: list[str]) -> str:
    """«la lectura», «las diapositivas» → «la lectura y las diapositivas»."""
    return ", ".join(partes[:-1]) + " y " + partes[-1] if len(partes) > 1 else "".join(partes)


def _material_nombrado(otros: list[str], propio: str) -> str | None:
    """El material que nombra el primer motivo de bloqueo («Aprueba primero el laboratorio…»), sin contar el propio."""
    for texto in otros[:1]:
        for clave, datos in MATERIALES.items():
            if clave != propio and datos["el"] in texto.lower():
                return clave
    return None


def _a(el: str) -> str:
    """«el laboratorio» → «al laboratorio»; «la lectura» → «a la lectura»."""
    return "al " + el[3:] if el.startswith("el ") else "a " + el


def _de(el: str) -> str:
    """«el laboratorio» → «del laboratorio»; «la lectura» → «de la lectura»."""
    return "del " + el[3:] if el.startswith("el ") else "de " + el


def _forma(datos: dict, raiz: str) -> str:
    """«Aprobad» → «Aprobada», «Aprobadas» o «Aprobado», según el material."""
    return raiz + datos.get("o", "a") + ("s" if datos.get("plural") else "")


def _aceptadas(estado: dict) -> int:
    """Cuántas decisiones pendientes aceptó el profesor al aprobar. Una FALLA no cuenta: impide aprobar."""
    if estado.get("estado") != "aprobada" or not estado.get("entrega"):
        return 0
    return sum(1 for s in estado["entrega"]["secciones"] if s["clave"] == "pendientes"
               for linea in s["lineas"] if not linea.startswith("FALLA"))


def _decisiones(n: int) -> str:
    return f"{n} {'decisión pendiente' if n == 1 else 'decisiones pendientes'}"


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


def _vista_de_materiales(carpeta, curso: str, sesion: int, detalle: bool = False) -> dict:
    """Los materiales de una sesión con su indicador, y el siguiente paso. Con `detalle`, también lo que les
    falta y el costo de la última corrida (la página de la sesión)."""
    # Basta la ficha del curso confirmada: la de la sesión se prepara y confirma sola al generar (decisión 55).
    puede_empezar = almacen.cargar(carpeta, "curso")["confirmada"]
    sesion_lista = puede_empezar and almacen.cargar(carpeta, "sesion", sesion)["confirmada"]
    incluidos = almacen.materiales_de_la_sesion(almacen.cargar(carpeta, "sesion", sesion))
    if puede_empezar and dependencias.por_migrar(almacen.cargar_estado(carpeta, sesion)):
        # Materiales generados antes de la decisión 62: se busca una vez qué usaron y se revisan con la regla nueva.
        dependencias.revisar(carpeta, sesion)
    materiales, siguiente, viejos = [], None, []
    for clave, datos in MATERIALES.items():
        modulo = datos["modulo"]
        estado = modulo.estado(carpeta, sesion)   # calcula si quedó desactualizado
        incluido = clave in incluidos
        m = {**{k: v for k, v in datos.items() if k != "modulo"}, "clave": clave, "estado": estado,
             "incluido": incluido, "situacion": _situacion(datos, estado, incluido), "aceptadas": _aceptadas(estado)}
        faltan = modulo.faltan(carpeta, sesion) if sesion_lista and incluido else {"ficha": [], "otros": []}
        # Lo que falta «fuera de la ficha» es otro material aprobado y al día: la lectura, o el laboratorio en la
        # evaluación (decisión 64 a). El material espera por el primero que nombra lo que falta.
        espera = _material_nombrado(faltan["otros"], clave)
        m["espera"] = ({"clave": espera, "el": MATERIALES[espera]["el"], "ir": f"Ir {_a(MATERIALES[espera]['el'])}"}
                       if espera else None)
        # Cada motivo de bloqueo enlaza al material que nombra (la evaluación puede esperar dos).
        m["enlaces"] = [{"clave": c, "ir": f"Ir {_a(MATERIALES[c]['el'])}"} if c else None
                        for c in (_material_nombrado([t], clave) for t in faltan["otros"])]
        if detalle:
            reanudable = hasattr(modulo, "se_puede_reanudar") and modulo.se_puede_reanudar(carpeta, sesion)
            # El gasto de la última corrida va solo en la confirmación antes de generar de nuevo (decisión 68 f).
            m |= {"faltan": faltan, "reanudable": reanudable,
                  "gasto_corrida": modulo.gasto_de_la_corrida(carpeta, curso, sesion)}
        materiales.append(m)
        if siguiente or not incluido:
            continue
        e, viejo = estado.get("estado"), estado.get("desactualizado")
        if not puede_empezar:
            siguiente = {"texto": "Guarda completa la ficha del curso: así queda confirmada.", "ancla": "", "corto": "Ficha"}
        elif e == "trabajando":
            siguiente = {"texto": f"Espera: AulaLista trabaja en {datos['el']}.", "ancla": clave, "corto": datos["corto"]}
        elif e == "aprobada":
            # Un material aprobado no es un paso pendiente, aunque la ficha haya cambiado después: se marca como
            # desactualizado y el profesor decide si lo genera de nuevo.
            if viejo:
                viejos.append(m)
            continue
        elif e in ("verificada", "con pendientes") and not viejo:
            siguiente = {"texto": f"Revisa la entrega y aprueba {datos['el']}.", "ancla": clave, "corto": datos["corto"]}
        elif e == "con fallas":
            siguiente = {"texto": f"Resuelve las fallas {_de(datos['el'])} en las fichas y genéra{datos['lo']} de nuevo.",
                         "ancla": clave, "corto": datos["corto"]}
        elif not faltan["ficha"] and faltan["otros"] and (base := next(
                (v for v in viejos if v["clave"] == _material_nombrado(faltan["otros"], clave)), None)):
            # Lo bloquea un material aprobado que quedó desactualizado (la lectura, o el laboratorio en la
            # evaluación): el paso es ese material, no este, cuyo botón Generar está bloqueado.
            sale = "salen" if datos["plural"] else "sale"
            siguiente = {"texto": f"Genera de nuevo {base['el']} y apruéba{base['lo']}.", "ancla": base["clave"],
                         "corto": base["corto"], "boton": f"Ir {_a(base['el'])}",
                         "motivo": f"{datos['el'][:1].upper()}{datos['el'][1:]} {sale} {_de(base['el'])}. "
                                   f"La ficha cambió después de aprobar{base['lo']}."}
        else:
            # Uno que no se aprobó y quedó desactualizado se genera otra vez para que siga a la ficha.
            otra_vez = " de nuevo" if viejo and e in ("verificada", "con pendientes") else ""
            if faltan["ficha"] or faltan["otros"]:
                siguiente = {"texto": f"Completa lo que falta para generar {datos['el']}{otra_vez}.", "ancla": clave,
                             "corto": datos["corto"]}
            else:
                siguiente = {"texto": f"Genera {datos['el']}{otra_vez}.", "ancla": clave, "corto": datos["corto"]}
    if siguiente is None and viejos:
        # Aprobados, pero no todos al día: decirlo, para que «aprobados» no se lea como «listos para entregar».
        # Se nombran y el enlace lleva al primero, para no tener que buscarlos en el panel.
        # Una idea por oración: el paso en el texto y la causa en el motivo.
        nombres = _y([v["el"] for v in viejos])
        if len(viejos) == 1 and not viejos[0].get("plural"):
            lo = viejos[0]["lo"]
        else:
            lo = "las" if all(v.get("o", "a") == "a" for v in viejos) else "los"
        cambio = "La lectura o la ficha" if [v["clave"] for v in viejos] == [diapositivas.CLAVE] else "La ficha"
        siguiente = {"texto": f"Decide si generas de nuevo {nombres}.", "motivo": f"{cambio} cambió después de aprobar{lo}.",
                     "ancla": viejos[0]["clave"], "corto": viejos[0]["corto"], "boton": f"Ir {_a(viejos[0]['el'])}"}
    elif siguiente is None:
        siguiente = {"texto": "Los materiales de esta sesión están aprobados.", "ancla": "", "corto": "Listo"}
    return {"puede_empezar": puede_empezar, "ficha_por_preparar": puede_empezar and not sesion_lista,
            "materiales": materiales, "siguiente": siguiente}


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
    estados = [indice.get(a, {}).get("estado") for a in archivos]
    sin_convertir = sum(1 for e in estados if e not in (convertir.CONVERTIDA, convertir.ESPERA_IA))
    if sin_convertir:
        return {"clase": "espera", "texto": f"{sin_convertir} sin convertir"}
    # Una imagen suelta no tiene texto hasta que la IA la lea: esa fuente no se puede usar todavía.
    por_leer = sum(1 for e in estados if e == convertir.ESPERA_IA)
    if por_leer:
        return {"clase": "espera", "texto": f"{por_leer} por leer con IA"}
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
            # La línea de la sesión es «título: alcance (páginas)» (como la parte flujo al llenar la ficha): el título
            # va en el encabezado y el alcance aparte, para que un alcance largo no se vuelva un título de tres líneas.
            partes = almacen.partes_de_sesion(s["texto"])
            alcance = partes["alcance"] if ":" in s["texto"] else ""
            sesiones.append({
                "numero": n, "texto": s["texto"], "titulo": partes["titulo"],
                "alcance": alcance[:1].upper() + alcance[1:],
                "abierta": actual in [f"ficha-{n}"] + [f"{c}-{n}" for c in MATERIALES],
                "ficha": _estado_de_ficha(almacen.cargar(carpeta, "sesion", n)["confirmada"],
                                          almacen.ruta_ficha(carpeta, "sesion", n).exists()),
                "materiales": [{"clave": m["clave"], "corto": m["corto"], "el": m["el"], "plural": m["plural"],
                                "situacion": m["situacion"], "estado": m["estado"].get("estado") or "",
                                "desactualizado": bool(m["estado"].get("desactualizado")),
                                "aprobada": (m["estado"].get("aprobada") or "")[:10], "espera": m["espera"],
                                "aceptadas": m["aceptadas"],
                                "sigue": m["clave"] == vista["siguiente"]["ancla"]} for m in incluidos],
                "hechos": sum(1 for m in incluidos if m["situacion"]["clase"] == "bien"),
                "van": len(incluidos),
                "siguiente": vista["siguiente"], "puede_empezar": vista["puede_empezar"],
            })
    # El panel lista todos los cursos (decisión 50). El resumen de cada curso se arma con un panel «inicio», que
    # no los lista: así no se llama a sí mismo.
    todos = [] if actual == "inicio" else _cursos_del_panel()
    return {
        "actual": actual,
        "cursos": todos,
        "gasto_total": _gasto_total(todos) if todos else None,
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
        if m["clave"] == diapositivas.CLAVE:
            return f"La lectura o la ficha cambió después de generar{los}: ya no {sigue} a lo de ahora."
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
    if fuentes.endswith("por leer con IA"):
        return {"texto": "Lee con IA las imágenes que subiste, o quítalas.", "url": base + "#fuentes",
                "boton": "Ir a las fuentes", "motivo": f"Hay {fuentes}: una imagen no tiene texto hasta que la IA la lea."}
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
            texto = s["siguiente"]["texto"]   # ya dice «de nuevo» cuando hace falta
            motivo = s["siguiente"].get("motivo") or (
                (f"Falta información para generar{'las' if m['plural'] else ('lo' if m['el'].startswith('el ') else 'la')}. "
                 "La página del material dice qué.") if texto.startswith("Completa") else _motivo(m))
            return {"texto": f"Sesión {s['numero']}: {texto[:1].lower()}{texto[1:]}",
                    "url": f"{base}/sesiones/{s['numero']}/materiales/{m['clave']}",
                    "boton": s["siguiente"].get("boton") or f"Ir {_a(m['el'])}", "material": m["clave"],
                    "sesion": s["numero"], "motivo": motivo}
    return None


def _frase_de_sesion(s: dict) -> str:
    """El avance de una sesión en una oración, para su fila del tablero."""
    problemas = [m for m in s["materiales"] if m["situacion"]["clase"] == "error"]
    faltan = [m for m in s["materiales"] if m["situacion"]["clase"] == "neutro"]
    if not s["puede_empezar"]:
        return "Falta confirmar su ficha."
    # Lo aceptado al aprobar no es un problema, pero se dice: «Lista» no puede esconder decisiones pendientes.
    con_decisiones = [m for m in s["materiales"] if m.get("aceptadas")]
    aceptadas = ""
    if len(con_decisiones) == 1:
        m = con_decisiones[0]
        aceptadas = (f" {m['el'][:1].upper()}{m['el'][1:]} se {'aprobaron' if m['plural'] else 'aprobó'}"
                     f" con {_decisiones(m['aceptadas'])}.")
    elif con_decisiones:
        aceptadas = f" {len(con_decisiones)} materiales se aprobaron con decisiones pendientes."
    if s["hechos"] == s["van"]:
        return "Lista: " + ("su material está aprobado." if s["van"] == 1 else "todos sus materiales están aprobados.") + aceptadas
    frase = f"{s['hechos']} de {s['van']} {'aprobado' if s['van'] == 1 else 'aprobados'}." + aceptadas
    desactualizados = [m for m in problemas if m["desactualizado"]]
    if desactualizados:
        n = len(desactualizados)
        frase += f" La ficha cambió: {'un material quedó desactualizado' if n == 1 else f'{n} materiales quedaron desactualizados'}."
    elif problemas:
        frase += f" {'Un material tiene' if len(problemas) == 1 else f'{len(problemas)} materiales tienen'} problemas."
    if faltan:
        verbo = "Falta" if len(faltan) == 1 and not faltan[0]["plural"] else "Faltan"
        frase += f" {verbo} " + _y([m["el"] for m in faltan]) + "."
    return frase


def _tablero(carpeta, curso: str, panel: dict) -> dict:
    """Lo que muestra el tablero del curso (decisión 44): lo que sigue, una fila por sesión y la preparación, que
    va plegada si está lista. Sin costos: el gasto del curso va solo en el panel (decisión 73)."""
    sigue = _que_sigue(curso, panel)
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
    if estado.get("desactualizado") and e in ("verificada", "con pendientes"):
        # Las diapositivas salen de la lectura: también quedan desactualizadas si la lectura cambia.
        notas[0] = "La lectura o las fichas cambiaron" if datos.get("clave", "") == diapositivas.CLAVE else "Las fichas cambiaron"
    elif not e and datos.get("espera"):
        # Bloqueado por otro material: Generar no es el paso actual, porque no se puede pulsar.
        clases[0], notas[0] = "pendiente", f"Espera {datos['espera']['el']}"
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
            notas[3] = "El " + _fecha(estado.get("aprobada") or "")
            if _aceptadas(estado):    # cuántas, no solo «Con pendientes»: se aprobó aceptándolas
                notas[2] = "Con " + _decisiones(_aceptadas(estado))
        if e == "aprobada" and estado.get("desactualizado"):
            # Sigue aprobado, pero no al día. Lo que hay que rehacer es Generar: ahí va el «!»; los pasos de después
            # vuelven a quedar pendientes, y Aprobar recuerda cuándo se aprobó la versión anterior.
            cambio = "la lectura o la ficha" if datos.get("clave", "") == diapositivas.CLAVE else "la ficha"
            clases = ["falla", "pendiente", "pendiente", "pendiente"]
            notas = [f"Después cambió {cambio}", "Sin IA", "Con IA, por bloque",
                     f"{_forma(datos, 'Aprobad')} {notas[3].lower()}, antes del cambio"]
    return [{"paso": p, "clase": c, "nota": n} for p, c, n in zip(PASOS, clases, notas)]


def _que_cambio(carpeta, sesion: int, material: dict) -> list[str]:
    """Por qué un material quedó desactualizado, sin IA: lo que usa y ya no dice lo mismo (decisión 62), y si la
    lectura en que se basa se generó de nuevo. Vacío si no se sabe."""
    estado = material["estado"]
    if not estado.get("desactualizado"):
        return []
    frases = list(estado.get("razones") or [])
    usada = estado.get("lectura_fecha") if material["clave"] == diapositivas.CLAVE else estado.get("lectura_usada")
    if usada and lectura.estado(carpeta, sesion).get("fecha", "") != usada:
        frases.append("La lectura se generó de nuevo.")
    usado_lab = estado.get("laboratorio_usada")    # la evaluación también sale del laboratorio (decisión 64 g)
    if usado_lab and laboratorio.estado(carpeta, sesion).get("fecha", "") != usado_lab:
        frases.append("El laboratorio se generó de nuevo.")
    return frases


def _listos(carpeta, sesion: int, material: dict, puede_empezar: bool, ficha_por_preparar: bool = False) -> list[str]:
    """Lo que ya se cumple para generar un material. Se muestra con ✓ junto a lo que falta, para que el profesor
    vea que el botón está listo por algo y no tenga que adivinarlo."""
    if ficha_por_preparar:
        return ["La ficha del curso está confirmada."]
    listos = ["Las dos fichas están confirmadas."] if puede_empezar else []
    if puede_empezar and not material["faltan"]["ficha"]:
        listos.append(f"La ficha de la sesión tiene lo que {'piden' if material['plural'] else 'pide'} {material['el']}.")
    if (puede_empezar and material["clave"] == diapositivas.CLAVE and not material["faltan"]["otros"]
            and diapositivas.usa_lectura(carpeta, sesion)):
        listos.append("La lectura está aprobada.")
    faltan = material["faltan"]
    if puede_empezar and material["clave"] == evaluacion.CLAVE and not faltan["ficha"] and not faltan["otros"]:
        # La evaluación sale de la lectura y del laboratorio aprobados, si la sesión los produce (decisión 64 a).
        incluidos = almacen.materiales_de_la_sesion(almacen.cargar(carpeta, "sesion", sesion))
        fuentes = [MATERIALES[c]["el"] for c in (lectura.CLAVE, laboratorio.CLAVE) if c in incluidos]
        if fuentes:
            verbo = "están aprobados" if len(fuentes) > 1 else _forma(MATERIALES[
                lectura.CLAVE if fuentes[0] == "la lectura" else laboratorio.CLAVE], "está aprobad")
            texto = _y(fuentes)
            listos.append(f"{texto[:1].upper()}{texto[1:]} {verbo} y al día.")
    return listos


@app.get("/cursos/{curso}/sesiones/{sesion}")
def ver_sesion(curso: str, sesion: int):
    """La sesión abre en el material del siguiente paso; sin fichas confirmadas, en la ficha de la sesión."""
    carpeta = _carpeta(curso)
    _exigir_ficha_del_curso(carpeta, curso)
    cursos.guardar_ultimo(curso)
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
    cursos.guardar_ultimo(curso)
    vista = _vista_de_materiales(carpeta, curso, sesion, detalle=True)
    m = next(x for x in vista["materiales"] if x["clave"] == material)
    panel = _panel(carpeta, curso, f"{material}-{sesion}")
    # Con la sesión aprobada, el siguiente paso es lo pendiente del curso (otra sesión, un material desactualizado).
    sigue_curso = _que_sigue(curso, panel) if vista["puede_empezar"] and not vista["siguiente"]["ancla"] else None
    return plantillas.TemplateResponse(request, "material.html", {
        "curso": curso, "nombre": _nombre(curso), "sesion": sesion, "mensaje": mensaje,
        # «Material 2 de 3» cuenta solo los materiales que van en la sesión.
        "m": m, "recorrido": _recorrido(m, m["estado"]), "incluidos": [x["clave"] for x in vista["materiales"] if x["incluido"]],
        "opciones": _opciones_de_generar(carpeta, sesion, material, m["estado"]),
        "listos": _listos(carpeta, sesion, m, vista["puede_empezar"], vista["ficha_por_preparar"]),
        "que_cambio": _que_cambio(carpeta, sesion, m),
        "puede_empezar": vista["puede_empezar"], "ficha_por_preparar": vista["ficha_por_preparar"],
        "siguiente": vista["siguiente"], "sigue_curso": sigue_curso,
        "panel": panel,
    })


def _opciones_elegidas(material: str, formulario: dict[str, str | None]) -> dict[str, bool]:
    """Las casillas de Generar que tiene el material, como argumentos de su `generar` (decisión 74 c y d).
    Una casilla sin marcar no llega en el formulario: vale False."""
    return {o["parametro"]: bool(formulario.get(o["nombre"])) for o in _material(material).get("opciones", [])}


def _opciones_de_generar(carpeta, sesion: int, material: str, estado: dict) -> list[dict]:
    """Las casillas para la página, con su estado inicial: lo elegido la última vez o lo que sugiere el módulo."""
    anteriores = estado.get("opciones") or {}
    casillas = []
    for o in _material(material).get("opciones", []):
        if o["nombre"] in anteriores:
            marcada = bool(anteriores[o["nombre"]])
        else:
            marcada = laboratorio.ejecucion_sugerida(carpeta) if o["nombre"] == "ejecucion" else False
        casillas.append({**o, "marcada": marcada})
    return casillas


@app.post("/cursos/{curso}/sesiones/{sesion}/materiales/{material}")
def generar_material(curso: str, sesion: int, material: str, revision_visual: str | None = Form(None),
                     ejecucion: str | None = Form(None)):
    modulo = _material(material)["modulo"]
    carpeta = _carpeta(curso)
    destino = _url_material(curso, sesion, material)
    opciones = _opciones_elegidas(material, {"revision_visual": revision_visual, "ejecucion": ejecucion})
    if not almacen.cargar(carpeta, "curso")["confirmada"]:
        return RedirectResponse(destino + "?mensaje=" + quote("Guarda completa la ficha del curso antes de generar: así queda confirmada."), status_code=303)
    if not almacen.cargar(carpeta, "sesion", sesion)["confirmada"]:
        # La ficha de la sesión no se confirma aparte: se prepara y confirma aquí, como al guardarla (decisión 55).
        flujo.llenar_desde_el_curso(carpeta, sesion)
        try:
            resultado = asyncio.run(flujo.preparar_y_confirmar(carpeta, curso, sesion))
        except (flujo.FichaDelCursoSinConfirmar, FaltaClave, agente.ErrorDeAgente) as error:
            return RedirectResponse(destino + "?mensaje=" + quote(str(error)), status_code=303)
        if resultado["errores"]:
            _AVISOS_FICHA[_url_ficha(curso, sesion)] = (" ".join(
                ["Para generar, la ficha de la sesión tiene que quedar confirmada.", *resultado["mensajes"]]),
                resultado["errores"])
            return RedirectResponse(_url_ficha(curso, sesion), status_code=303)
    faltan = modulo.faltan(carpeta, sesion)
    if faltan["ficha"]:
        mensaje = "Falta en la ficha de la sesión: " + " ".join(faltan["ficha"])
        return RedirectResponse(destino + "?mensaje=" + quote(mensaje), status_code=303)
    if faltan["otros"]:
        return RedirectResponse(destino + "?mensaje=" + quote(" ".join(faltan["otros"])), status_code=303)
    if modulo.estado(carpeta, sesion).get("estado") == "trabajando":
        return RedirectResponse(destino, status_code=303)
    _marcar_trabajando(carpeta, sesion, material, "Empezando…")
    _trabajo_en_segundo_plano(modulo.generar, carpeta, curso, sesion, clave=(curso, sesion, material), **opciones)
    return RedirectResponse(destino, status_code=303)


def _marcar_trabajando(carpeta, sesion: int, material: str, paso: str) -> None:
    """Deja el material en «trabajando» antes de redirigir. Si no, la página vuelve antes de que el hilo escriba
    el estado, muestra el botón como si nada y el profesor tiene que pulsar Generar dos veces. Solo para Generar:
    Reanudar y el revisor leen el estado anterior al empezar y lo necesitan intacto."""
    comun.actualizar(carpeta, sesion, material, estado="trabajando", previo="",
                     avance=[f"{datetime.now():%H:%M:%S} · {paso}"], error="")


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
    if not datos.get("revisor", True):
        mensaje = f"El revisor independiente todavía no revisa {datos['el']}."
        return RedirectResponse(destino + "?mensaje=" + quote(mensaje), status_code=303)
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
    # Una página HTML se abre en el navegador, para leerla sin guardarla antes.
    en_linea = ruta.suffix.lower() == ".html"
    return FileResponse(ruta, filename=ruta.name, content_disposition_type="inline" if en_linea else "attachment")
