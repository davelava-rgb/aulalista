"""La segunda pasada marca relleno, ambigüedad, vacío e inconsistencia puestos a propósito (PLAN.md §5.8).
Gasta tokens. Se corre con: pytest -m ia"""

import asyncio

import pytest

from app.validacion import pasada2

LIMPIO = pasada2.Bloque("Pilares de Scrum", [
    "Scrum tiene tres pilares: transparencia, inspección y adaptación.",
    "La transparencia pide que el trabajo sea visible para quienes lo hacen y quienes lo reciben.",
    "La inspección pide revisar con frecuencia el avance hacia los objetivos acordados.",
    "La adaptación pide ajustar el trabajo cuando la revisión muestra un problema.",
    "Ejemplo: el equipo de Almacén cuelga su tablero en la pared y lo actualiza cada mañana.",
    "Cada viernes, el jefe de Almacén revisa el tablero y pasa al primer lugar cada pedido atrasado.",
])
SEMBRADOS = pasada2.Bloque("Aplícalo así", [
    "Este tema es muy importante y conviene tenerlo siempre presente.",                    # relleno
    "Abre el archivo y copia la tabla en un documento nuevo.",                             # vacío: qué archivo
    "Marca en el tablero el pedido anterior al último que revisaste.",                     # ambigüedad
    "El Sprint del equipo de Almacén dura dos semanas.",
    "Al cierre, el equipo revisa los pedidos de su Sprint de tres semanas.",               # inconsistencia
])
ESPERADOS = {
    "relleno": "Este tema es muy importante",
    "vacío": "Abre el archivo y copia la tabla",
    "ambigüedad": "pedido anterior al último",
    "inconsistencia": "semanas",
}


@pytest.mark.ia
def test_la_segunda_pasada_marca_cada_defecto_sembrado():
    resultado = asyncio.run(pasada2.ejecutar(
        [LIMPIO, SEMBRADOS], anteriores={}, contexto_fijo="Curso: Scrum Master con IA. Público: jefes de área.",
        curso="_sistema", sesion=1, material="Lectura"))
    encontrados = {d["tipo"]: d["oracion"] for d in resultado.defectos}
    # Una oración sembrada cuenta como marcada aunque el tipo sea otro defecto: igual se corrige.
    faltan = [tipo for tipo, texto in ESPERADOS.items() if not any(texto in d["oracion"] for d in resultado.defectos)]
    assert faltan == [], f"Defectos sembrados sin marcar: {faltan}. Marcó: {encontrados}"
    assert not [d for d in resultado.defectos if d["bloque"] == "Pilares de Scrum"], "Marcó defectos en el bloque limpio"
    assert set(resultado.respuestas) == {"Pilares de Scrum", "Aplícalo así"}
