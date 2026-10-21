"""Actividad web: el contenido como datos, sus revisiones sin IA y una vista para revisarlo (PLAN.md §0, decisión 57).

Fase 8a del plan. Flujo:
1. Comprueba las fichas y, si la sesión produce la lectura, que esté aprobada: la actividad sale de ella.
2. El agente redacta el contenido: el caso, los pasos y las preguntas cerradas con sus explicaciones y puntos.
3. Un programa revisa lo que el esquema no puede: de 4 a 6 pasos, una sola respuesta correcta, una explicación en
   cada opción, ninguna respuesta abierta y las filas «Total» de las tablas que suman.
4. El generador crea la vista del contenido en HTML y el verificador la revisa. Esta actividad sí muestra puntos;
   los tiempos siguen siendo FALLA. Las fallas se corrigen hasta VUELTAS_DEL_VERIFICADOR veces.
5. Entrega en el formato del SPEC §8. El profesor la aprueba desde la página.

La revisión del contenido con IA llega en la fase 8b y el diseño de la página del alumno, en la 8c.
"""

import asyncio
import html
import json
import re
from datetime import datetime
from pathlib import Path

from pydantic import ValidationError

from app import agente, entrega, skill, tokens
from app.fichas import almacen, referencia, verificacion
from app.materiales import comun, estilo, lectura
from app.materiales.contenido import ESQUEMA_ACTIVIDAD, PUNTOS_POR_PREGUNTA, Actividad, Lectura, Pregunta
from app.validacion import excel, verificador

MATERIAL = "Actividad web"
CLAVE = "actividad"
VUELTAS_DEL_VERIFICADOR = comun.VUELTAS_DEL_VERIFICADOR
PASOS = (4, 6)
SECCIONES_DE_LA_SKILL = ("Reglas comunes", "Paso 3 · Vocabulario de la sesión", "Actividad web")
NOTA_DEL_PUNTAJE = "El puntaje es una orientación. La nota la pone el profesor."

ESQUEMA_CORRECCION = comun.esquema_de_correccion("actividad", ESQUEMA_ACTIVIDAD)
ESQUEMA_CORRECCIONES = comun.esquema_de_correcciones(completa=ESQUEMA_CORRECCION, oraciones=comun.ESQUEMA_CAMBIOS)


class NoSePuedeEmpezar(RuntimeError):
    """Faltan fichas confirmadas o la lectura aprobada."""


class NoSePuedeRevisar(RuntimeError):
    """El revisor independiente de la actividad llega con la fase 8b."""


class NoSePuedeAprobar(RuntimeError):
    """La actividad tiene fallas abiertas, está desactualizada o no se generó."""


def archivos(carpeta_curso: Path, sesion: int) -> dict[str, Path]:
    carpeta = lectura.carpeta_materiales(carpeta_curso, sesion)
    trabajo = carpeta / comun.TRABAJO / CLAVE
    return {
        "vista": carpeta / f"S{sesion}_Actividad_Contenido.html",
        "excel": carpeta / f"S{sesion}_Actividad_Verificacion.xlsx",
        "verificacion_json": trabajo / "verificacion.json",
        "contenido": trabajo / "contenido.json",
        "explicaciones": trabajo / "explicaciones.json",
        "sistema": trabajo / "sistema_correccion.txt",
    }


def _estado(carpeta_curso: Path, sesion: int) -> dict:
    return comun.estado(carpeta_curso, sesion, CLAVE)


def _actualizar(carpeta_curso: Path, sesion: int, **cambios) -> dict:
    return comun.actualizar(carpeta_curso, sesion, CLAVE, **cambios)


def _avance(carpeta_curso: Path, sesion: int, texto: str) -> None:
    comun.avance(carpeta_curso, sesion, CLAVE, texto)


# ---------- La lectura como fuente ----------

def usa_lectura(carpeta_curso: Path, sesion: int) -> bool:
    """Si la sesión produce la lectura, la actividad sale de ella. Si no, de la referencia y de las fichas."""
    return lectura.CLAVE in almacen.materiales_de_la_sesion(almacen.cargar(carpeta_curso, "sesion", sesion))


def _lectura_lista(carpeta_curso: Path, sesion: int) -> list[str]:
    material = lectura.estado(carpeta_curso, sesion)
    if material.get("estado") != "aprobada":
        return ["Aprueba primero la lectura: la actividad sale de ella."]
    if material.get("desactualizado"):
        return ["La lectura está desactualizada: genérala y apruébala de nuevo."]
    if not lectura.archivos(carpeta_curso, sesion)["contenido"].exists():
        return ["No encuentro el contenido de la lectura aprobada. Genérala de nuevo."]
    return []


def _texto_de_la_lectura(carpeta_curso: Path, sesion: int) -> list[str]:
    if not usa_lectura(carpeta_curso, sesion):
        return []
    contenido = Lectura.model_validate(comun.leer_json(lectura.archivos(carpeta_curso, sesion)["contenido"]))
    lineas = ["", "LECTURA APROBADA DE LA SESIÓN (la actividad sale de ella):", *contenido.idea_central]
    for b in contenido.bloques:
        lineas += [f"## {b.subtitulo}", *b.parrafos, f"Ejemplo: {b.ejemplo.titulo}", *b.ejemplo.parrafos]
    lineas += ["## Aplícalo así", *contenido.aplicalo.parrafos, *contenido.aplicalo.plantilla,
               "## Cuidado con", *contenido.cuidado,
               "PASAJES DE LAS FUENTES QUE USÓ LA LECTURA:",
               *[f"- {p.fuente}, {p.ubicacion}: «{p.texto}»" for p in contenido.pasajes]]
    return lineas


# ---------- Pedidos al agente ----------

def _contexto(carpeta_curso: Path, sesion: int) -> str:
    ficha_curso = almacen.texto_para_materiales(carpeta_curso, "curso")
    ficha_sesion = almacen.ruta_ficha(carpeta_curso, "sesion", sesion, ".md").read_text(encoding="utf-8")
    fuentes = verificacion.fuentes_utilizables(carpeta_curso)
    ficha = almacen.cargar(carpeta_curso, "sesion", sesion)
    tramos, excluir = referencia.interpretar(carpeta_curso, ficha)[0], referencia.exclusiones(ficha)
    lineas_referencia = []
    if tramos and not usa_lectura(carpeta_curso, sesion):
        lineas_referencia = ["", "MATERIAL DE REFERENCIA DE LA SESIÓN:", *[f"- {t.describir()}" for t in tramos],
                             "EXCLUSIONES (no las uses):", *([f"- {e}" for e in excluir] or ["- Ninguna."])]
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
        *_texto_de_la_lectura(carpeta_curso, sesion),
    ])


FORMATO = f"""
CÓMO ENTREGAR LA ACTIVIDAD WEB
- Devuelve solo los datos del esquema. Después, otro agente diseña la página con estos datos tal cual: escribe cada
  texto como lo verá el alumno.
- titulo: el nombre de la actividad, corto. presentacion: de 1 a 3 oraciones sobre lo que el alumno va a hacer.
- caso: el caso de la actividad, con «titulo», «parrafos» y sus datos en «tablas» o «graficos». Cada gráfico trae sus
  «categorias» (por ejemplo, rangos o meses) y de 1 a 3 «series», cada una con un valor por categoría. Si una tabla
  trae una fila «Total», esa fila es la suma de las demás.
- pasos: de {PASOS[0]} a {PASOS[1]}, en el orden del tema. Cada paso con «titulo», «introduccion», «recuerde» (vacío
  si no hace falta) y de 1 a 4 «preguntas».
- Cada pregunta trae «tipo», «enunciado» y «puntos» (entero de {PUNTOS_POR_PREGUNTA[0]} a {PUNTOS_POR_PREGUNTA[1]}).
  Llena solo la lista de su tipo y deja las otras vacías:
  - «opcion_unica»: «opciones», de 3 a 5, con una sola «correcta» en true.
  - «opcion_multiple»: «opciones», de 4 a 6, con al menos una correcta y una incorrecta. El enunciado avisa
    que se marcan todas las que correspondan.
  - «ordenar»: «elementos», de 3 a 6, en el orden correcto. La página los muestra mezclados.
  - «relacionar»: «pares», de 3 a 6, con «izquierda» y «derecha». Cada derecha es distinta.
  - «clasificar»: «categorias», de 2 a 4, y «elementos», de 3 a 8, cada uno con su «categoria» copiada tal cual.
    Cada categoría se usa al menos una vez.
- Cada opción, elemento o par trae su «explicacion»: por qué es correcta, o qué confunde y cuál es la idea correcta.
- pasajes: los pasajes de las fuentes que usaste: «oracion» de la actividad que sostiene, la fuente, la ubicación y en
  «texto» el pasaje copiado, de 40 palabras como máximo.
- decisiones: una entrada por punto, con «texto» y «tipo» («sin fuente», «decisión» o «nota»), como en los demás
  materiales.
- Una idea por oración. Usa los nombres del vocabulario de la sesión tal cual.
- No escribas tiempos ni la duración de la actividad.
"""


def pedido_de_redaccion(carpeta_curso: Path, sesion: int) -> str:
    return "\n".join([
        _contexto(carpeta_curso, sesion),
        FORMATO,
        "TAREA: redacta el contenido de la actividad web de la sesión. Actúa como diseñador instruccional y editor senior.",
        "La actividad refuerza lo que enseñó la lectura. Si necesitas un pasaje de una fuente, búscalo con Grep y léelo con Read.",
        "Antes de entregar, resuelve tú cada pregunta con los datos del caso: si admite dos respuestas, rediséñala.",
    ])


def sistema_de_correccion(carpeta_curso: Path, sesion: int) -> str:
    """El mensaje de sistema de todas las correcciones: igual en cada una, se lee de caché (decisión 43)."""
    return "\n".join([_contexto(carpeta_curso, sesion), FORMATO, comun.REGLAS_DE_CORRECCION])


def _pedido(contenido: dict, problemas: list[str], completa: bool) -> str:
    entregar = (["Devuelve la actividad completa con el mismo esquema."] if completa else [
        "CÓMO ENTREGAR LA CORRECCIÓN",
        "- En «cambios», una entrada por oración que cambias: «oracion» copiada tal cual de la actividad y «nueva» con el texto nuevo.",
        "- Para eliminar una oración, deja «nueva» vacío. No devuelvas las oraciones que no cambian."])
    return "\n".join(["Corrige el material según el contexto, el formato y las reglas de tus instrucciones.", *entregar,
                      "", "ACTIVIDAD ACTUAL:", json.dumps(contenido, ensure_ascii=False), "",
                      "PROBLEMAS QUE ENCONTRÓ LA VALIDACIÓN:", *[f"- {p}" for p in problemas]])


# ---------- Revisiones sin IA ----------

# Pedidos de escribir. «Describe» o «explica» solos no cuentan: «¿Qué opción describe mejor…?» es una pregunta cerrada.
ABIERTA = re.compile(r"\b(escriba|redacte|redacta|explique|justifique|justifica|describa|con sus palabras|con tus palabras|"
                     r"escribe (?:un|una|tu|su|en)|responda en|responde en)\b", re.I)
NUMERO = re.compile(r"-?\d+(?:[.,]\d+)*")
TOTAL = re.compile(r"^\s*total\b", re.I)


def _falla(donde: str, texto: str) -> str:
    return f"FALLA · actividad · {donde}: {texto}"


def _revisar_pregunta(p: Pregunta, donde: str) -> list[str]:
    fallas = []
    if ABIERTA.search(p.enunciado):
        fallas.append(_falla(donde, f"pide una respuesta abierta («{ABIERTA.search(p.enunciado).group(0)}»). "
                                    "Usa solo preguntas cerradas."))
    listas = {"opciones": p.opciones, "elementos": p.elementos, "pares": p.pares}
    propia = {"opcion_unica": "opciones", "opcion_multiple": "opciones", "ordenar": "elementos",
              "relacionar": "pares", "clasificar": "elementos"}[p.tipo]
    for nombre, lista in listas.items():
        if nombre != propia and lista:
            fallas.append(_falla(donde, f"es «{p.tipo}» y trae «{nombre}»: deja esa lista vacía."))
    if p.tipo != "clasificar" and p.categorias:
        fallas.append(_falla(donde, f"es «{p.tipo}» y trae «categorias»: deja esa lista vacía."))
    textos = ([o.texto for o in p.opciones] + [e.texto for e in p.elementos] + [x.izquierda for x in p.pares])
    if len({t.strip().lower() for t in textos}) != len(textos):
        fallas.append(_falla(donde, "tiene dos opciones o elementos con el mismo texto."))
    for item in [*p.opciones, *p.elementos, *p.pares]:
        if not item.explicacion.strip():
            nombre = getattr(item, "texto", None) or item.izquierda
            fallas.append(_falla(donde, f"«{nombre}» no trae su explicación."))
    if p.tipo in ("opcion_unica", "opcion_multiple"):
        correctas = sum(o.correcta for o in p.opciones)
        minimo, maximo = (3, 5) if p.tipo == "opcion_unica" else (4, 6)
        if not minimo <= len(p.opciones) <= maximo:
            fallas.append(_falla(donde, f"tiene {len(p.opciones)} opciones; van de {minimo} a {maximo}."))
        if p.tipo == "opcion_unica" and correctas != 1:
            fallas.append(_falla(donde, f"es de opción única y tiene {correctas} opciones correctas; va una sola."))
        if p.tipo == "opcion_multiple" and not 0 < correctas < len(p.opciones):
            fallas.append(_falla(donde, "es de opción múltiple: necesita al menos una opción correcta y una incorrecta."))
    elif p.tipo == "ordenar" and not 3 <= len(p.elementos) <= 6:
        fallas.append(_falla(donde, f"tiene {len(p.elementos)} elementos para ordenar; van de 3 a 6."))
    elif p.tipo == "relacionar":
        if not 3 <= len(p.pares) <= 6:
            fallas.append(_falla(donde, f"tiene {len(p.pares)} pares; van de 3 a 6."))
        derechas = [x.derecha.strip().lower() for x in p.pares]
        if len(set(derechas)) != len(derechas):
            fallas.append(_falla(donde, "dos pares tienen la misma derecha: cada una va con una sola izquierda."))
    elif p.tipo == "clasificar":
        if not 2 <= len(p.categorias) <= 4:
            fallas.append(_falla(donde, f"tiene {len(p.categorias)} categorías; van de 2 a 4."))
        if not 3 <= len(p.elementos) <= 8:
            fallas.append(_falla(donde, f"tiene {len(p.elementos)} elementos para clasificar; van de 3 a 8."))
        for e in p.elementos:
            if e.categoria not in p.categorias:
                fallas.append(_falla(donde, f"«{e.texto}» va en «{e.categoria}», que no es una de sus categorías."))
        sin_usar = [c for c in p.categorias if c not in {e.categoria for e in p.elementos}]
        if sin_usar:
            fallas.append(_falla(donde, f"ningún elemento va en «{'», «'.join(sin_usar)}»."))
    return fallas


def _numero(celda: str, decimal: str) -> float | None:
    """El número de una celda («S/ 2.560», «14 %»), o None si no trae uno solo."""
    hallados = NUMERO.findall(celda)
    if len(hallados) != 1:
        return None
    try:
        return verificador.verificar._a_numero(hallados[0], decimal)
    except ValueError:
        return None


def _revisar_totales(actividad: Actividad, decimal: str) -> list[str]:
    """Cada fila «Total» es la suma de las demás filas de su tabla, columna por columna."""
    fallas = []
    for tabla in actividad.caso.tablas:
        totales = [f for f in tabla.filas if TOTAL.match(f[0])]
        filas = [f for f in tabla.filas if not TOTAL.match(f[0])]
        for total in totales:
            for columna in range(1, len(tabla.encabezados)):
                escrito = _numero(total[columna], decimal)
                valores = [_numero(f[columna], decimal) for f in filas]
                if escrito is None or not valores or None in valores:
                    continue
                suma = sum(valores)
                if abs(suma - escrito) > 0.005 * max(1, abs(escrito)):
                    fallas.append(_falla(f"Caso, tabla «{tabla.titulo}»",
                                         f"la fila «{total[0]}» dice {total[columna]} en «{tabla.encabezados[columna]}», "
                                         f"pero las filas suman {suma:g}."))
    return fallas


def revisar(actividad: Actividad, decimal: str = ",") -> list[str]:
    """Lo que el esquema no puede comprobar (decisión 57 b). Cada falla dice dónde está."""
    fallas = []
    if not PASOS[0] <= len(actividad.pasos) <= PASOS[1]:
        fallas.append(_falla("Pasos", f"tiene {len(actividad.pasos)}; van de {PASOS[0]} a {PASOS[1]}."))
    for i, paso in enumerate(actividad.pasos, start=1):
        for j, pregunta in enumerate(paso.preguntas, start=1):
            fallas += _revisar_pregunta(pregunta, f"Paso {i}, pregunta {j}")
    return fallas + _revisar_totales(actividad, decimal)


def _validar(datos: dict, decimal: str) -> tuple[Actividad | None, list[str]]:
    try:
        actividad = Actividad.model_validate(datos)
    except ValidationError as error:
        return None, [f"FALLA · estructura · {'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in error.errors()]
    return actividad, revisar(actividad, decimal)


# ---------- Vista del contenido ----------

TIPOS = {"opcion_unica": "Opción única", "opcion_multiple": "Opción múltiple", "ordenar": "Ordenar",
         "relacionar": "Relacionar", "clasificar": "Clasificar"}


def _e(texto) -> str:
    return html.escape(str(texto))


def _cifra(valor: float, decimal: str) -> str:
    texto = f"{valor:g}"
    return texto.replace(".", ",") if decimal == "," else texto


def _tabla(encabezados: list[str], filas: list[list[str]], titulo: str = "") -> str:
    cabeza = "".join(f"<th>{_e(c)}</th>" for c in encabezados)
    cuerpo = "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in f) + "</tr>" for f in filas)
    leyenda = f"<caption>{_e(titulo)}</caption>" if titulo else ""
    return f"<table>{leyenda}<thead><tr>{cabeza}</tr></thead><tbody>{cuerpo}</tbody></table>"


def _pregunta(p: Pregunta, numero: int) -> str:
    partes = [f"<h3>Pregunta {numero}</h3>",
              f'<p class="meta">{TIPOS[p.tipo]} · {p.puntos} {"punto" if p.puntos == 1 else "puntos"}</p>',
              f"<p>{_e(p.enunciado)}</p>"]
    if p.tipo in ("opcion_unica", "opcion_multiple"):
        partes.append('<ul class="opciones">' + "".join(
            f'<li class="{"si" if o.correcta else "no"}"><p>{_e(o.texto)}</p>'
            f'<p class="por-que">{"Correcta" if o.correcta else "Incorrecta"}. {_e(o.explicacion)}</p></li>'
            for o in p.opciones) + "</ul>")
    elif p.tipo == "ordenar":
        partes.append('<p class="meta">Orden correcto:</p><ol class="opciones">' + "".join(
            f'<li><p>{_e(e.texto)}</p><p class="por-que">{_e(e.explicacion)}</p></li>' for e in p.elementos) + "</ol>")
    elif p.tipo == "relacionar":
        partes.append(_tabla(["Elemento", "Va con", "Por qué"], [[x.izquierda, x.derecha, x.explicacion] for x in p.pares]))
    else:
        partes.append(_tabla(["Elemento", "Categoría", "Por qué"], [[e.texto, e.categoria, e.explicacion] for e in p.elementos]))
    return "".join(partes)


def vista_html(actividad: Actividad, identidad: estilo.Identidad, decimal: str = ",") -> str:
    """Página para que el profesor lea el contenido con sus respuestas. No es la página del alumno: esa la diseña
    otro agente con este mismo contenido (decisión 57 e)."""
    estilos = (f"body{{font-family:'{identidad.tipografia}',Verdana,sans-serif;color:#{identidad.texto};max-width:860px;"
               f"margin:2rem auto;padding:0 1rem;line-height:1.5}}h1,h2{{color:#{identidad.principal}}}"
               f"h2{{margin-top:2.2rem;border-bottom:2px solid #{identidad.acento};padding-bottom:.2rem}}"
               f"table{{border-collapse:collapse;width:100%;margin:.8rem 0}}th,td{{text-align:left;padding:.4rem .5rem;"
               f"border-bottom:1px solid #{identidad.fondo}}}caption{{text-align:left;font-weight:bold;padding:.3rem 0}}"
               f".aviso,.recuerde{{background:#{identidad.fondo};border-left:4px solid #{identidad.acento};padding:.6rem .9rem}}"
               f".meta{{color:#{identidad.principal};font-weight:bold;margin-bottom:0}}.opciones li{{margin:.5rem 0}}"
               f".opciones p{{margin:.1rem 0}}.por-que{{font-size:.95rem}}li.si .por-que{{color:#{identidad.principal}}}"
               f"li.no .por-que{{color:#{identidad.advertencia}}}")
    partes = [f"<h1>{_e(actividad.titulo)}</h1>",
              '<p class="aviso">Vista del contenido para revisar, con sus respuestas. No es la página del alumno.</p>',
              *[f"<p>{_e(t)}</p>" for t in actividad.presentacion],
              f"<h2>{_e(actividad.caso.titulo)}</h2>", *[f"<p>{_e(t)}</p>" for t in actividad.caso.parrafos]]
    partes += [_tabla(t.encabezados, t.filas, t.titulo) for t in actividad.caso.tablas]
    for g in actividad.caso.graficos:
        filas = [[c, *[_cifra(s.valores[i], decimal) for s in g.series]] for i, c in enumerate(g.categorias)]
        partes.append(f'<p class="meta">Gráfico: {_e(g.titulo)}. Eje horizontal: {_e(g.eje_x)}. '
                      f'Eje vertical: {_e(g.eje_y)}.</p>' + _tabla([g.eje_x, *[s.nombre for s in g.series]], filas))
    numero = 0
    for i, paso in enumerate(actividad.pasos, start=1):
        partes += [f"<h2>Paso {i}. {_e(paso.titulo)}</h2>", *[f"<p>{_e(t)}</p>" for t in paso.introduccion]]
        if paso.recuerde.strip():
            partes.append(f'<p class="recuerde"><strong>Recuerde.</strong> {_e(paso.recuerde)}</p>')
        for pregunta in paso.preguntas:
            numero += 1
            partes.append(_pregunta(pregunta, numero))
    total = actividad.puntaje_total
    partes += ["<h2>Puntaje</h2>", f"<p>Puntaje total: {total} {'punto' if total == 1 else 'puntos'}.</p>",
               f"<p>{_e(NOTA_DEL_PUNTAJE)}</p>"]
    return ('<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f"<title>{_e(actividad.titulo)}</title><style>{estilos}</style></head><body>"
            + "".join(partes) + "</body></html>")


# ---------- Generación ----------

def _decimal(carpeta_curso: Path, sesion: int) -> str:
    base = almacen.carpeta_sesion(carpeta_curso, sesion) / "verificacion.json"
    return json.loads(base.read_text(encoding="utf-8")).get("separador_decimal", ",") if base.exists() else ","


def _limpiar(rutas: dict[str, Path]) -> None:
    """Borra lo que dejó la generación anterior. Un archivo abierto puede negar el borrado: se deja y se reescribe."""
    for clave in ("vista", "excel", "verificacion_json", "contenido", "explicaciones"):
        try:
            rutas[clave].unlink(missing_ok=True)
        except OSError:
            pass


async def generar(carpeta_curso: Path, curso: str, sesion: int, consulta=agente.query) -> dict:
    if not almacen.puede_empezar_material(carpeta_curso, sesion):
        raise NoSePuedeEmpezar("Guarda completas la ficha del curso y la ficha de la sesión antes de generar la "
                               "actividad web: así quedan confirmadas.")
    faltan_ = faltan(carpeta_curso, sesion)
    if faltan_["ficha"] or faltan_["otros"]:
        raise NoSePuedeEmpezar("Antes de generar la actividad web: " + " ".join(faltan_["ficha"] + faltan_["otros"]))
    rutas = archivos(carpeta_curso, sesion)
    rutas["contenido"].parent.mkdir(parents=True, exist_ok=True)
    _actualizar(carpeta_curso, sesion, estado="trabajando", previo="", avance=[], error="", desactualizado=False,
                entrega={}, aprobada="", revisor={}, corrida_desde=tokens.lineas(curso))
    try:
        return await _generar(carpeta_curso, curso, sesion, rutas, consulta)
    except asyncio.CancelledError:
        marcar_detenida(carpeta_curso, sesion)
        raise
    except Exception as error:
        _actualizar(carpeta_curso, sesion, estado="error", error=str(error))
        raise


class _Trabajo:
    """Lo que se acumula mientras se genera la actividad: los datos, el último resultado del verificador,
    las explicaciones de los avisos y el historial de lo corregido."""

    def __init__(self, carpeta_curso, curso, sesion, rutas, consulta):
        self.carpeta_curso, self.curso, self.sesion, self.rutas = carpeta_curso, curso, sesion, rutas
        self.carpeta_sesion = almacen.carpeta_sesion(carpeta_curso, sesion)
        self.identidad = estilo.desde_ficha(carpeta_curso)
        self.decimal = _decimal(carpeta_curso, sesion)
        self.comun = {"curso": curso, "sesion": f"S{sesion}", "material": CLAVE, "cwd": carpeta_curso / "fuentes_texto",
                      "herramientas": ("Read", "Grep", "Glob"), "consulta": consulta}
        self.datos: dict = {}
        self.contenido: Actividad | None = None
        self.explicaciones: dict[str, str] = {}
        self.historial: list[dict] = []
        self.correcciones = {"verificador": 0}
        self.datos_agregados: list[str] = []
        self.resultado = None
        self.fallas: list[str] = []
        self.vuelta = 0

    def avance(self, texto: str) -> None:
        _avance(self.carpeta_curso, self.sesion, texto)

    async def verificar(self) -> bool:
        """Revisa el contenido, genera la vista y corre el verificador. Corrige hasta VUELTAS_DEL_VERIFICADOR veces.
        Devuelve True si quedó sin fallas ni avisos por explicar."""
        for intento in range(VUELTAS_DEL_VERIFICADOR + 1):
            self.vuelta += 1
            contenido, problemas = _validar(self.datos, self.decimal)
            completa = bool(problemas)   # la estructura y las preguntas se arreglan con la actividad completa
            comun.guardar_json(self.rutas["contenido"], self.datos)
            if contenido is not None:
                self.contenido = contenido
                self.rutas["vista"].write_text(vista_html(contenido, self.identidad, self.decimal), encoding="utf-8")
                configuracion = verificador.configuracion_del_material(self.carpeta_sesion, MATERIAL)
                self.resultado = verificador.ejecutar(configuracion, [self.rutas["vista"]], self.rutas["excel"],
                                                      self.explicaciones, salida_json=self.rutas["verificacion_json"])
                excel.anotar_reglas(self.rutas["excel"], comun.AVISOS_INFORMATIVOS, comun.NOTA_INFORMATIVA)
                fallas, avisos = comun.hallazgos_abiertos(self.resultado, self.explicaciones)
                self.avance(f"Verificador, vuelta {self.vuelta}: {self.resultado.resumen()}"
                            + (f" Revisión de las preguntas: {comun.cuantos(len(problemas), 'falla')}." if problemas else "."))
                completa = completa or any(not h.oracion for h in fallas)
                problemas = problemas + [comun.texto_de(h) for h in fallas + avisos]
                self.historial += comun.historial(fallas + avisos, self.vuelta)
            self.fallas = problemas
            if not problemas:
                return True
            if intento == VUELTAS_DEL_VERIFICADOR:
                self.avance(f"Quedan {comun.cuantos(len(problemas), 'falla')} después de {VUELTAS_DEL_VERIFICADOR} "
                            "correcciones. No se puede aprobar la actividad con fallas.")
                return False
            self.correcciones["verificador"] += len(problemas)
            await self.corregir(problemas, completa)
        return False

    async def corregir(self, problemas: list[str], completa: bool) -> None:
        sistema = comun.escribir_sistema(self.rutas["sistema"], sistema_de_correccion(self.carpeta_curso, self.sesion))
        forma, tarea = ("completa", "correccion") if completa else ("oraciones", "correccion_oraciones")
        self.avance(f"Corrigiendo {'la actividad completa: ' if completa else ''}{comun.cuantos(len(problemas), 'problema')}.")
        respuesta = await comun.consultar_correccion(_pedido(self.datos, problemas, completa), forma, ESQUEMA_CORRECCIONES,
                                                     tarea=tarea, etapa=f"corrección {self.vuelta}", sistema=sistema,
                                                     **self.comun)
        if completa:
            self.datos = respuesta["actividad"]
        else:
            self.datos, no_encontradas = comun.aplicar_cambios(self.datos, respuesta["cambios"])
            if no_encontradas:
                self.avance(f"{comun.cuantos(len(no_encontradas), 'oración')} a cambiar no se encontraron en la actividad.")
        for e in respuesta["explicaciones"]:
            self.explicaciones[verificador.clave_de_hallazgo(e["regla"], e["oracion"])] = e["explicacion"]
        comun.guardar_json(self.rutas["explicaciones"], self.explicaciones)
        nuevos = almacen.agregar_datos_fijos(self.carpeta_curso, respuesta.get("datos_nuevos", []),
                                             f"Actividad web S{self.sesion}")
        if nuevos:
            self.datos_agregados += nuevos
            for numero in almacen.sesiones_confirmadas(self.carpeta_curso):
                verificacion.escribir(self.carpeta_curso, numero)
            self.avance(f"Datos nuevos del caso agregados a la ficha del curso: {len(nuevos)}.")


async def _generar(carpeta_curso, curso, sesion, rutas, consulta) -> dict:
    inicio = tokens.lineas(curso)
    skill.comprobar(secciones=SECCIONES_DE_LA_SKILL)   # antes de gastar tokens
    trabajo = _Trabajo(carpeta_curso, curso, sesion, rutas, consulta)
    verificador.verificar.leer_configuracion(verificador.configuracion_del_material(trabajo.carpeta_sesion, MATERIAL))
    _limpiar(rutas)

    trabajo.avance("Leyendo la lectura y las fichas, y redactando la actividad web.")
    trabajo.datos = await agente.consultar(pedido_de_redaccion(carpeta_curso, sesion), tarea="redaccion",
                                           esquema=ESQUEMA_ACTIVIDAD, etapa="redacción", **trabajo.comun)
    await trabajo.verificar()

    final = trabajo.contenido
    decisiones = final.decisiones if final else []
    sin_fuente = [f"Afirmación sin fuente: {d.texto}" for d in decisiones if d.tipo == "sin fuente"]
    estado_final = "con fallas" if trabajo.fallas else ("con pendientes" if sin_fuente else "verificada")
    if trabajo.resultado is not None:
        excel.solo_hallazgos(rutas["excel"], "Sección")
        excel.agregar_historial(rutas["excel"], [
            {**h, "resolucion": f"Enviado a corrección en la vuelta {h['vuelta']}." + ("" if trabajo.fallas else " Resuelto.")}
            for h in trabajo.historial] + comun.filas_de_decisiones(decisiones, rutas["vista"].name))
    material = _actualizar(
        carpeta_curso, sesion,
        estado=estado_final,
        resumen=trabajo.resultado.resumen() if trabajo.resultado else "",
        problemas=trabajo.fallas + sin_fuente,
        correcciones=trabajo.correcciones,
        datos_agregados=trabajo.datos_agregados,
        avisos_de_diseno=trabajo.identidad.avisos,
        avisos_explicados=sum(1 for h in (trabajo.resultado.hallazgos if trabajo.resultado else [])
                              if h.nivel == "AVISO" and h.regla not in comun.AVISOS_INFORMATIVOS),
        avisos_informativos=sum(1 for h in (trabajo.resultado.hallazgos if trabajo.resultado else [])
                                if h.nivel == "AVISO" and h.regla in comun.AVISOS_INFORMATIVOS),
        pasos=len(final.pasos) if final else 0,
        preguntas=sum(len(p.preguntas) for p in final.pasos) if final else 0,
        puntaje_total=final.puntaje_total if final else 0,
        decisiones=[d.model_dump() for d in decisiones],
        archivos={"vista": rutas["vista"].name, "excel": rutas["excel"].name},
        costo=tokens.total(curso, sesion=f"S{sesion}", material=CLAVE, desde_linea=inicio),
        fecha=datetime.now().isoformat(timespec="seconds"),
    )
    _actualizar(carpeta_curso, sesion, entrega=_entrega(material))
    trabajo.avance({"verificada": "Contenido de la actividad listo para tu aprobación.",
                    "con pendientes": f"Contenido listo, con {comun.cuantos(len(sin_fuente), 'pendiente')} para que decidas.",
                    "con fallas": "El contenido de la actividad quedó con fallas."}[estado_final])
    return _estado(carpeta_curso, sesion)


# ---------- Entrega (SPEC §8) ----------

def _entrega(material: dict) -> dict:
    archivos_ = material["archivos"]
    lineas_archivos = [
        f"{archivos_['vista']}: el contenido de la actividad con sus respuestas, para revisarlo: "
        f"{material['pasos']} pasos, {material['preguntas']} preguntas y {material['puntaje_total']} puntos en total.",
        f"{archivos_['excel']}: el archivo de verificación, con la hoja Hallazgos.",
    ]
    probe = ["Revisé cada pregunta con un programa: una sola respuesta correcta, una explicación en cada opción, "
             "ninguna respuesta abierta y las filas «Total» del caso que suman."]
    valide = [f"Verificador: {material['resumen']}." if material["resumen"] else "El verificador no llegó a correr.",
              *([f"Avisos explicados en la hoja Hallazgos: {material['avisos_explicados']}."]
                if material.get("avisos_explicados") else []),
              *([f"Avisos informativos: {material['avisos_informativos']}. Están en la hoja Hallazgos; no obligan a corregir."]
                if material.get("avisos_informativos") else []),
              f"Fallas corregidas: {material['correcciones']['verificador']}.",
              f"Costo de esta actividad: {material['costo']['llamadas']} llamadas, "
              f"{material['costo']['costo_usd']:.2f} USD estimados."]
    no_pude = ["La revisión del contenido con IA todavía no corre en la actividad: llega en la fase 8b del plan.",
               "La página del alumno todavía no se diseña: llega en la fase 8c del plan."]
    decisiones = material["decisiones"]
    decidi = [d["texto"] for d in decisiones if d["tipo"] == "decisión"]
    decidi += [f"Dato nuevo del caso, agregado a la ficha del curso: {d}" for d in material["datos_agregados"]]
    if not decidi:
        decidi.append("Nada que revisar: todo salió de las fichas, de la lectura y de las fuentes. Las notas del "
                      "redactor están en la hoja Hallazgos.")
    return entrega.componer(archivos=lineas_archivos, probe=probe, valide=valide,
                            pendientes=material["problemas"], no_pude=no_pude, decidi=decidi)


async def revisar_con_revisor(carpeta_curso: Path, curso: str, sesion: int, consulta=agente.query) -> dict:
    raise NoSePuedeRevisar("El revisor independiente de la actividad web llega con la fase 8b del plan.")


def aprobar(carpeta_curso: Path, sesion: int) -> dict:
    """El profesor aprueba el contenido desde la página. Las fallas no dejan aprobar."""
    material = _estado(carpeta_curso, sesion)
    if material.get("estado") not in ("verificada", "con pendientes"):
        raise NoSePuedeAprobar("Solo se aprueba una actividad generada y sin fallas.")
    if material.get("desactualizado"):
        raise NoSePuedeAprobar("Las fichas cambiaron después de generar la actividad. Genérala de nuevo.")
    return _actualizar(carpeta_curso, sesion, estado="aprobada", aprobada=datetime.now().isoformat(timespec="seconds"))


def estado(carpeta_curso: Path, sesion: int) -> dict:
    return _estado(carpeta_curso, sesion)


def faltan(carpeta_curso: Path, sesion: int) -> dict[str, list[str]]:
    """En «ficha», lo que se completa en la ficha de la sesión; en «otros», la lectura aprobada si la sesión la produce."""
    ficha = almacen.faltantes_para(carpeta_curso, sesion, CLAVE)
    otros = _lectura_lista(carpeta_curso, sesion) if not ficha and usa_lectura(carpeta_curso, sesion) else []
    return {"ficha": ficha, "otros": otros}


def gasto_de_la_corrida(carpeta_curso: Path, curso: str, sesion: int) -> dict | None:
    return comun.gasto_de_la_corrida(carpeta_curso, curso, sesion, CLAVE)


def marcar_detenida(carpeta_curso: Path, sesion: int) -> bool:
    return comun.marcar_detenida(carpeta_curso, sesion, CLAVE)
