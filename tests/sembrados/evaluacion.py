"""Evaluación práctica de prueba (PLAN.md §0, decisión 64), con el curso ficticio de Scrum de tests/fixtures.

LIMPIO cumple el modelo. La fase 9b le suma los errores sembrados para el verificador.
"""

import copy

LIMPIO = {
    "indicaciones": {
        "consulta": "Puedes consultar la lectura y la guía del laboratorio de esta sesión.",
        "entrega": "Escribe cada respuesta en la tabla de su pregunta y entrega este documento.",
    },
    "preguntas": [
        {
            "numero": 1,
            "concepto": "Pilares de Scrum",
            "tarea": "clasificar",
            "titulo": "Clasifica los hechos del equipo de Ventas según su pilar",
            "situacion": "El equipo de Ventas anotó tres hechos de su último Sprint. Debes decir qué pilar de "
                         "Scrum muestra cada hecho.",
            "archivos": ["S1_P1_hechos-ventas.xlsx"],
            "pasos": ["Abre el archivo S1_P1_hechos-ventas.xlsx.", "Lee cada hecho de la hoja Hechos.",
                      "Escribe en la tabla el pilar de cada hecho."],
            "tabla_de_respuesta": {"titulo": "Pilar de cada hecho", "encabezados": ["Hecho", "Pilar"],
                                   "filas": [["Hecho 1", ""], ["Hecho 2", ""], ["Hecho 3", ""]]},
            "clave": {
                "respuesta": [["Hecho 1", "Transparencia"], ["Hecho 2", "Adaptación"], ["Hecho 3", "Inspección"]],
                "partes": ["Hecho 1: Transparencia.", "Hecho 2: Adaptación.", "Hecho 3: Inspección."],
                "problemas": ["El hecho 3 parece de adaptación, pero solo revisa el avance."],
                "errores_comunes": ["Marcar el hecho 3 como adaptación: revisar no es cambiar el plan."],
            },
        },
        {
            "numero": 2,
            "concepto": "Eventos de Scrum",
            "tarea": "ordenar",
            "titulo": "Ordena los eventos del Sprint de Compras",
            "situacion": "El equipo de Compras anotó sus eventos sin orden. Debes ponerlos en el orden en que "
                         "ocurren dentro del Sprint.",
            "archivos": ["S1_P2_eventos-compras.docx"],
            "pasos": ["Abre el archivo S1_P2_eventos-compras.docx.", "Escribe en la tabla el orden de cada evento."],
            "tabla_de_respuesta": {"titulo": "Orden de los eventos", "encabezados": ["Orden", "Evento"],
                                   "filas": [["1", ""], ["2", ""], ["3", ""]]},
            "clave": {
                "respuesta": [["1", "Planificación del Sprint"], ["2", "Scrum diario"], ["3", "Revisión del Sprint"]],
                "partes": ["Primero, la Planificación del Sprint.", "Después, el Scrum diario.",
                           "Al final, la Revisión del Sprint."],
                "errores_comunes": ["Poner la Revisión antes del Scrum diario."],
            },
        },
        {
            "numero": 3,
            "concepto": "Roles de Scrum",
            "tarea": "relacionar",
            "titulo": "Relaciona cada tarea del equipo de Finanzas con su rol",
            "situacion": "El equipo de Finanzas tiene tres tareas sin responsable. Debes decir qué rol de Scrum "
                         "hace cada tarea.",
            "archivos": ["S1_P3_tareas-finanzas.xlsx"],
            "pasos": ["Abre el archivo S1_P3_tareas-finanzas.xlsx.", "Escribe en la tabla el rol de cada tarea."],
            "tabla_de_respuesta": {"titulo": "Rol de cada tarea", "encabezados": ["Tarea", "Rol"],
                                   "filas": [["Tarea A", ""], ["Tarea B", ""], ["Tarea C", ""]]},
            "clave": {
                "respuesta": [["Tarea A", "Product Owner"], ["Tarea B", "Scrum Master"], ["Tarea C", "Equipo"]],
                "partes": ["Tarea A: Product Owner.", "Tarea B: Scrum Master.", "Tarea C: Equipo."],
                "errores_comunes": ["Dar la tarea B al Product Owner: quitar impedimentos es del Scrum Master."],
            },
        },
    ],
    "archivos": [
        {"nombre": "S1_P1_hechos-ventas.xlsx", "descripcion": "Tres hechos del Sprint de Ventas.",
         "hojas": [{"nombre": "Hechos", "encabezados": ["Hecho", "Descripción"],
                    "filas": [["Hecho 1", "El tablero muestra todas las tareas."],
                              ["Hecho 2", "El equipo cambió el plan del Sprint."],
                              ["Hecho 3", "El equipo revisó el avance cada día."]]}],
         "problema": "El hecho 3 parece de adaptación."},
        {"nombre": "S1_P2_eventos-compras.docx", "descripcion": "Los eventos del Sprint de Compras, sin orden.",
         "parrafos": [{"estilo": "lista", "texto": "Revisión del Sprint"},
                      {"estilo": "lista", "texto": "Planificación del Sprint"},
                      {"estilo": "lista", "texto": "Scrum diario"}]},
        {"nombre": "S1_P3_tareas-finanzas.xlsx", "descripcion": "Tres tareas del equipo de Finanzas.",
         "hojas": [{"nombre": "Tareas", "encabezados": ["Tarea", "Descripción"],
                    "filas": [["Tarea A", "Ordenar la lista de trabajo del producto."],
                              ["Tarea B", "Quitar lo que frena al equipo."],
                              ["Tarea C", "Construir el incremento del Sprint."]]}]},
    ],
}


def limpio() -> dict:
    return copy.deepcopy(LIMPIO)


def con(cambio) -> dict:
    datos = limpio()
    cambio(datos)
    return datos


def _filas(n: int, vacias: bool = True):
    def cambio(d):
        tabla, clave = d["preguntas"][0]["tabla_de_respuesta"], d["preguntas"][0]["clave"]
        tabla["filas"] = [[f"Hecho {i}", "" if vacias else "x"] for i in range(1, n + 1)]
        clave["respuesta"] = [[f"Hecho {i}", "Transparencia"] for i in range(1, n + 1)]
    return cambio


def _texto_largo(d):
    d["preguntas"][0]["situacion"] = " ".join(["Ventas anota hechos del Sprint."] * 52)   # 260 palabras


def _respuesta_en_la_hoja(d):
    d["preguntas"][0]["situacion"] += " Por ejemplo, Hecho 1 Transparencia."


def _mal_nombrado(d):
    viejo, nuevo = "S1_P1_hechos-ventas.xlsx", "S2_P1_hechos-ventas.xlsx"
    d["archivos"][0]["nombre"] = nuevo
    d["preguntas"][0]["archivos"] = [nuevo]
    d["preguntas"][0]["pasos"][0] = d["preguntas"][0]["pasos"][0].replace(viejo, nuevo)


def _puntaje(d):
    d["preguntas"][1]["situacion"] += " Esta pregunta vale 5 puntos."


def _tiempo(d):
    d["indicaciones"]["consulta"] += " Tienes 30 minutos."


# Nombre: (cambio, regla del hallazgo, parte del detalle). Cada uno es un error solo (PLAN.md §5.8).
SEMBRADOS = {
    "respuesta en la hoja del alumno": (_respuesta_en_la_hoja, "respuesta fuera de la clave", "hoja del alumno"),
    "260 palabras": (_texto_largo, "tamaño de la pregunta", "260 palabras"),
    "16 filas": (_filas(16), "tamaño de la pregunta", "16 filas"),
    "11 celdas por llenar": (_filas(11), "tamaño de la pregunta", "llena 11 celdas"),
    "archivo mal nombrado": (_mal_nombrado, "nombre de archivo", ""),
    "puntaje": (_puntaje, "puntaje", ""),
    "tiempo": (_tiempo, "tiempo", ""),
}
