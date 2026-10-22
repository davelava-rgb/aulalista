"""Qué usa cada material y si quedó desactualizado (PLAN.md §0, decisión 62).

Al generar un material se guarda lo que usó: los valores de las dos fichas y la huella de cada fuente. Después, al
confirmar una ficha o al convertir las fuentes, se compara solo lo que ese material usa. Sin IA.
"""

from pathlib import Path

from app.fichas import almacen, plantillas, referencia
from app.fuentes import convertir

TODOS = ("lectura", "diapositivas", "laboratorio", "actividad", "evaluacion")

# Qué materiales desactualiza cada grupo de campos. La clave es el comienzo del id del campo; gana la más larga.
# Un campo que no está aquí desactualiza todos: ante la duda, se avisa. Las preguntas de la evaluación solo la
# desactualizan a ella (decisión 64 g).
AFECTA = {
    "lectura.": ("lectura", "diapositivas"),
    "ejercicio.": ("laboratorio",),
    "herramientas.": ("laboratorio",),
    "portada.": ("lectura", "diapositivas", "laboratorio"),
    "evaluacion.": ("evaluacion",),
    "pregunta.": ("evaluacion",),
    "curso.horas": (),
    "curso.numero_sesiones": (),
    "materiales.cuales": (),
}
# Con reglas propias, más abajo: el renglón de la sesión en «Sesiones» y los datos fijos.
ESPECIALES = ("curso.sesiones", "datos.fijos")


def afecta(campo_id: str) -> tuple[str, ...]:
    claves = [k for k in AFECTA if campo_id == k or (k.endswith(".") and campo_id.startswith(k))]
    return AFECTA[max(claves, key=len)] if claves else TODOS


def _limpio(ficha: dict, campo_id: str) -> str:
    """El valor sin la marca «(propuesto)» ni espacios de más: eso no es un cambio de contenido."""
    return " ".join(almacen.sin_marcas(almacen.valor(ficha, campo_id)).split())


def _linea_de_la_sesion(ficha_curso: dict, sesion: int) -> str:
    return next((" ".join(s["texto"].split()) for s in almacen.sesiones_del_curso(ficha_curso) if s["numero"] == sesion), "")


def _datos_fijos(ficha_curso: dict) -> list[str]:
    return [" ".join(l.split()).lower() for l in almacen.sin_marcas(almacen.valor(ficha_curso, "datos.fijos")).split("\n")
            if l.strip()]


def _fuentes_de_la_sesion(carpeta_curso: Path, ficha_sesion: dict, indice: dict) -> dict[str, str]:
    """La huella de cada fuente que la sesión usa: las del material de referencia o, sin él, todas."""
    nombres = list(indice)
    lineas = [l for l in almacen.sin_marcas(almacen.valor(ficha_sesion, "sesion.referencia")).split("\n") if l.strip()]
    if lineas:
        usadas = {referencia._buscar_archivo((l.partition(":")[0] if ":" in l else l).strip(), nombres) for l in lineas}
        nombres = [n for n in nombres if n in usadas]
    return {n: indice[n].get("huella", "") for n in nombres}


def usado(carpeta_curso: Path, sesion: int, curso: dict | None = None, ficha_sesion: dict | None = None,
          con_fuentes: bool = True) -> dict:
    """Lo que un material usa al generarse. Con `curso` y `ficha_sesion`, el de esas versiones de las fichas."""
    curso = curso or almacen.cargar(carpeta_curso, "curso")
    ficha_sesion = ficha_sesion or almacen.cargar(carpeta_curso, "sesion", sesion)
    datos = {
        "curso": {c.id: _limpio(curso, c.id) for c, _ in plantillas.campos_de("curso") if c.id not in ESPECIALES},
        "sesion": {c.id: _limpio(ficha_sesion, c.id) for c, _ in plantillas.campos_de("sesion")},
        "linea_de_la_sesion": _linea_de_la_sesion(curso, sesion),
        "datos_fijos": _datos_fijos(curso),
    }
    if con_fuentes:
        datos["fuentes"] = _fuentes_de_la_sesion(carpeta_curso, ficha_sesion, convertir.leer_indice(carpeta_curso))
    return datos


def usado_en(carpeta_curso: Path, sesion: int, fecha: str) -> dict | None:
    """Para un material generado antes de la decisión 62: lo que usó, sacado de las versiones de las fichas guardadas
    en su fecha. Sin las fuentes, porque entonces no se guardó su huella. None si falta una versión."""
    curso = almacen.version_en(carpeta_curso, "curso", None, fecha)
    ficha_sesion = almacen.version_en(carpeta_curso, "sesion", sesion, fecha)
    if curso is None or ficha_sesion is None:
        return None
    return usado(carpeta_curso, sesion, curso, ficha_sesion, con_fuentes=False)


def razones(carpeta_curso: Path, sesion: int, clave: str, antes: dict, ahora: dict | None = None) -> list[str]:
    """Por qué el material `clave` ya no sigue a las fichas y fuentes de ahora, en frases para el profesor.
    Vacío si todo lo que usa sigue igual."""
    ahora = ahora or usado(carpeta_curso, sesion)
    frases = []
    for tipo, donde in (("sesion", "En la ficha de la sesión"), ("curso", "En la ficha del curso")):
        nombres = [plantillas.etiqueta_corta(tipo, c.id) for c, _ in plantillas.campos_de(tipo)
                   if c.id in antes[tipo] and clave in afecta(c.id) and antes[tipo][c.id] != ahora[tipo].get(c.id, "")]
        if tipo == "curso" and antes["linea_de_la_sesion"] != ahora["linea_de_la_sesion"]:
            nombres.insert(0, "el renglón de esta sesión en Sesiones")
        if tipo == "curso" and set(antes["datos_fijos"]) - set(ahora["datos_fijos"]):
            # Agregar un dato fijo no desactualiza; cambiar o quitar uno sí.
            nombres.append("Datos fijos del caso (se cambió o quitó una línea)")
        if len(nombres) > 6:
            nombres = nombres[:5] + [f"{len(nombres) - 5} campos más"]
        if nombres:
            frases.append(f"{donde}: {_y(nombres)}.")
    for nombre, huella in (antes.get("fuentes") or {}).items():
        if (ahora.get("fuentes") or {}).get(nombre, huella) != huella:
            frases.append(f"Cambió el contenido de la fuente {nombre}.")
    return frases


def _y(partes: list[str]) -> str:
    return ", ".join(partes[:-1]) + " y " + partes[-1] if len(partes) > 1 else "".join(partes)


def revisar(carpeta_curso: Path, sesion: int, anterior: dict | None = None) -> list[str]:
    """Revisa cada material generado de la sesión: queda desactualizado, con sus razones, si cambió algo que usa; si
    todo vuelve a coincidir, deja de estarlo. Del que no se sabe qué usó, se aplica la regla de antes: ante la duda,
    se avisa. Devuelve los que quedaron desactualizados con este cambio."""
    ahora = usado(carpeta_curso, sesion)
    marcados = []
    with almacen.CANDADO_ESTADO:
        estado = almacen.cargar_estado(carpeta_curso, sesion)
        viejo = None   # la regla de antes, calculada una sola vez y solo si hace falta
        for clave, material in estado["materiales"].items():
            if material.get("estado") in (None, "", "trabajando") or clave not in TODOS:
                continue
            antes = material.get("usado")
            if antes is None and material.get("fecha"):
                antes = usado_en(carpeta_curso, sesion, material["fecha"])
                if antes is not None:
                    material["usado"] = antes   # ya no hace falta buscar en las versiones la próxima vez
            if antes is None:
                material["sin_usado"] = True   # no se vuelve a buscar en las versiones
                if viejo is None:
                    viejo = almacen.cambiaron_las_fichas(carpeta_curso, sesion, estado, anterior)
                if viejo:
                    material["desactualizado"] = True
                    marcados.append(clave)
                continue
            ya_estaba = bool(material.get("desactualizado"))
            material["razones"] = razones(carpeta_curso, sesion, clave, antes, ahora)
            material["desactualizado"] = bool(material["razones"])
            if material["desactualizado"] and not ya_estaba:
                marcados.append(clave)   # como antes: se nombran los que quedan desactualizados con este cambio
        almacen.guardar_estado(carpeta_curso, sesion, estado)
    return marcados


def _fuente_nueva(carpeta_curso: Path, sesion: int, material: dict, fuente: str) -> bool:
    """El material `fuente` se generó de nuevo después de este material, que lo usaba."""
    usada = material.get(f"{fuente}_usada")
    if not usada or material.get("estado") in (None, "", "trabajando"):
        return False
    return usada != almacen.cargar_estado(carpeta_curso, sesion)["materiales"].get(fuente, {}).get("fecha", "")


def lectura_nueva(carpeta_curso: Path, sesion: int, material: dict) -> bool:
    """La lectura se generó de nuevo después de este material, que la usaba (decisión 62 d)."""
    return _fuente_nueva(carpeta_curso, sesion, material, "lectura")


def laboratorio_nuevo(carpeta_curso: Path, sesion: int, material: dict) -> bool:
    """El laboratorio se generó de nuevo después de la evaluación, que lo usaba (decisión 64 g)."""
    return _fuente_nueva(carpeta_curso, sesion, material, "laboratorio")


def por_migrar(estado_sesion: dict) -> bool:
    """Hay un material generado antes de la decisión 62 al que aún no se le buscó lo que usó."""
    return any(m.get("estado") not in (None, "", "trabajando") and "usado" not in m and not m.get("sin_usado")
               and m.get("fecha") for c, m in estado_sesion["materiales"].items() if c in TODOS)
