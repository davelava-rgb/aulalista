"""Material 6 · Evaluación práctica (PBQ) y su clave (SKILL.md, «Material 6»; PLAN.md §0, decisión 64; etapa 9).

Fase 9a: el estado, los archivos y lo que hace falta para generarla. La redacción, la validación y la ejecución
llegan en las fases 9b y 9c; la página del material, en la 9d. Mientras tanto la evaluación no se registra en la
interfaz (decisión 46).

Flujo previsto, igual al del laboratorio:
1. Comprueba las dos fichas confirmadas, las preguntas de la ficha y la lectura y el laboratorio aprobados y al día
   (decisión 64 a): la evaluación no evalúa nada que no hayan enseñado.
2. El agente escribe las preguntas, sus archivos y la clave como datos (contenido.Evaluacion).
3. Un programa crea la hoja del alumno, la clave y el .zip de los archivos, y el verificador los revisa.
4. Revisión del contenido por pregunta, una sola corrección, y cada pregunta resuelta como un alumno.
"""

from pathlib import Path

from app.fichas import almacen, dependencias
from app.materiales import comun, laboratorio, lectura

MATERIAL = "Evaluacion"
CLAVE = "evaluacion"
CARPETA_ARCHIVOS = "materiales/_trabajo/evaluacion/archivos"   # relativa a la carpeta de la sesión, para el verificador


def archivos(carpeta_curso: Path, sesion: int) -> dict[str, Path]:
    """La hoja del alumno, la clave, el .zip de sus archivos (aparte del del laboratorio) y el Excel de verificación
    van a materiales/; lo que usa AulaLista, a su carpeta de trabajo (decisión 64 d)."""
    carpeta = lectura.carpeta_materiales(carpeta_curso, sesion)
    trabajo = carpeta / comun.TRABAJO / CLAVE
    return {
        "word": carpeta / f"S{sesion}_Evaluacion.docx",
        "clave": carpeta / f"S{sesion}_Evaluacion_Clave.docx",
        "zip": carpeta / f"S{sesion}_Evaluacion_Archivos.zip",
        "excel": carpeta / f"S{sesion}_Evaluacion_Verificacion.xlsx",
        "verificacion_json": trabajo / "verificacion.json",
        "archivos": trabajo / "archivos",
        "revision": trabajo / "revisor",
        "contenido": trabajo / "contenido.json",
        "ejecucion": trabajo / "ejecucion",
        "explicaciones": trabajo / "explicaciones.json",
        "sistema": trabajo / "sistema_correccion.txt",
    }


# ---------- Estado ----------

def estado(carpeta_curso: Path, sesion: int) -> dict:
    """El estado guardado. Si la lectura o el laboratorio se generaron de nuevo después de esta evaluación, queda
    desactualizada: los dos son su fuente (decisión 64 g)."""
    material = comun.estado(carpeta_curso, sesion, CLAVE)
    if dependencias.lectura_nueva(carpeta_curso, sesion, material) or \
            dependencias.laboratorio_nuevo(carpeta_curso, sesion, material):
        return {**material, "desactualizado": True}
    return material


def gasto_de_la_corrida(carpeta_curso: Path, curso: str, sesion: int) -> dict | None:
    return comun.gasto_de_la_corrida(carpeta_curso, curso, sesion, CLAVE)


def marcar_detenida(carpeta_curso: Path, sesion: int) -> bool:
    return comun.marcar_detenida(carpeta_curso, sesion, CLAVE)


def _aprobado_y_al_dia(modulo, carpeta_curso: Path, sesion: int, el: str, verbo: str) -> list[str]:
    """Lo que falta de un material que la evaluación usa como fuente: aprobado y sin cambios después."""
    material = modulo.estado(carpeta_curso, sesion)
    if material.get("estado") != "aprobada":
        return [f"Aprueba primero {el}: la evaluación no evalúa nada que no se haya enseñado."]
    if material.get("desactualizado"):
        return [f"{el[:1].upper()}{el[1:]} está desactualizad{'o' if el.startswith('el ') else 'a'}: {verbo} y "
                f"apruéba{'lo' if el.startswith('el ') else 'la'} de nuevo."]
    return []


def faltan(carpeta_curso: Path, sesion: int) -> dict[str, list[str]]:
    """En «ficha», lo que se completa en la ficha de la sesión. En «otros», la lectura y el laboratorio aprobados y al
    día, si la sesión los produce (decisión 64 a). Lo de la ficha va primero: sin preguntas, lo demás no importa."""
    ficha = almacen.faltantes_para(carpeta_curso, sesion, CLAVE)
    if ficha:
        return {"ficha": ficha, "otros": []}
    incluidos = almacen.materiales_de_la_sesion(almacen.cargar(carpeta_curso, "sesion", sesion))
    otros = []
    if lectura.CLAVE in incluidos:
        otros += _aprobado_y_al_dia(lectura, carpeta_curso, sesion, "la lectura", "genérala")
    if laboratorio.CLAVE in incluidos:
        otros += _aprobado_y_al_dia(laboratorio, carpeta_curso, sesion, "el laboratorio", "genéralo")
    return {"ficha": [], "otros": otros}
