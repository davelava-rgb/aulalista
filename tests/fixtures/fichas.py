"""Fichas completas y válidas para las pruebas (curso ficticio de Scrum)."""

CURSO = {
    "curso.nombre": "Scrum Master con IA",
    "curso.idioma": "Español",
    "curso.sesiones": "1. Agilidad y fundamentos de Scrum: manifiesto, pilares y valores\n2. Roles de Scrum: responsabilidades",
    "publico.quienes": "Jefes de área de una empresa comercial",
    "publico.saben": "Nada de Scrum",
    "publico.valoran": "Ejemplos de su trabajo diario",
    "caso.empresa": "Comercial Los Volcanes, venta minorista",
    "caso.areas": "Ventas, Almacén, Recursos Humanos y Finanzas",
    "datos.fecha": "lunes 5 de octubre de 2026",
    "datos.fijos": "Duración de cada Sprint: dos semanas\nTienda principal: Sucursal Centro\nLos pedidos se recogen en tienda",
    "materiales.nunca": "",
}

SESION = {
    "sesion.numero_titulo": "1 · Agilidad y fundamentos de Scrum",
    "sesion.alcance": "Manifiesto Ágil, pilares y valores de Scrum",
    "lectura.bloque.1": "Manifiesto Ágil",
    "lectura.bloque.2": "Pilares de Scrum",
    "lectura.cuidado": "Confundir pilares con valores",
    "vocabulario.conceptos": "1. Manifiesto Ágil (no usar: Agile, manifiesto agile)\n2. Pilares de Scrum\n3. Valores de Scrum",
    "practica.estaciones": "Estación 1\nEstación 2\nEstación 3\nEstación 4\nEstación 5",
    "materiales.cuales": "los seis",
}
for _n in (1, 2, 3):
    SESION.update({
        f"ejercicio.{_n}.area": ["Ventas", "Almacén", "Recursos Humanos"][_n - 1],
        f"ejercicio.{_n}.accion": "Clasificar situaciones",
        f"ejercicio.{_n}.entregable": "Tabla clasificada",
        f"ejercicio.{_n}.archivo": f"Word con seis situaciones del ejercicio {_n}",
        f"ejercicio.{_n}.problema": "Una situación contradice un aspecto",
        f"ejercicio.{_n}.respuesta": "La situación 4 contradice",
        f"pregunta.{_n}.concepto": "Pilares de Scrum",
        f"pregunta.{_n}.tarea": "Clasificar hechos",
        f"pregunta.{_n}.archivo": "Excel con un registro nuevo",
        f"pregunta.{_n}.problema": "Un hecho no cumple la inspección",
        f"pregunta.{_n}.respuesta": "Hecho 3: inspección",
    })


def ficha(tipo: str, valores: dict, confirmada: bool = False) -> dict:
    return {
        "tipo": tipo, "confirmada": confirmada, "fecha_confirmacion": "",
        "campos": {i: {"valor": v, "origen": "profesor", "estado": ""} for i, v in valores.items() if v},
    }
