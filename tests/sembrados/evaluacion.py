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
            "situacion": "El equipo de Ventas anotó cuatro hechos de su último Sprint. Debes decir qué pilar de "
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
    ],
    "archivos": [
        {"nombre": "S1_P1_hechos-ventas.xlsx", "descripcion": "Cuatro hechos del Sprint de Ventas.",
         "hojas": [{"nombre": "Hechos", "encabezados": ["Hecho", "Descripción"],
                    "filas": [["Hecho 1", "El tablero muestra todas las tareas."],
                              ["Hecho 2", "El equipo cambió el plan del Sprint."],
                              ["Hecho 3", "El equipo revisó el avance cada día."]]}],
         "problema": "El hecho 3 parece de adaptación."},
        {"nombre": "S1_P2_eventos-compras.docx", "descripcion": "Los eventos del Sprint de Compras, sin orden.",
         "parrafos": [{"estilo": "lista", "texto": "Revisión del Sprint"},
                      {"estilo": "lista", "texto": "Planificación del Sprint"},
                      {"estilo": "lista", "texto": "Scrum diario"}]},
    ],
}


def limpio() -> dict:
    return copy.deepcopy(LIMPIO)
