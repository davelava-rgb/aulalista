"""Laboratorio limpio y laboratorios con errores puestos a propósito (PLAN.md §5.8).

Cada error lo detecta un programa antes de crear los archivos (app/materiales/practica.py) o el verificador.
El curso es el ficticio de Scrum de tests/fixtures/fichas.py: tres ejercicios, de Ventas, Almacén y Recursos Humanos.
"""

import copy

NOTA = "Usa estos datos como fuente única."


def _paso(texto, figura=None):
    return {"texto": texto, "figura": figura}


LIMPIO = {
    "antes_de_empezar": {
        "contexto": ["Trabajas para Comercial Los Volcanes, una empresa de venta minorista.",
                     "La fecha de referencia de todos los ejercicios es el lunes 5 de octubre de 2026."],
        "tablas": [],
        "reglas": ["Los pedidos se recogen en tienda."],
    },
    "ejercicios": [
        {
            "numero": 1, "area": "Ventas", "titulo": "Clasifica los pedidos de la semana",
            "situacion": "El área de Ventas de la Sucursal Centro revisa los pedidos de la semana. "
                         "Necesita saber cuáles se recogen en tienda.",
            "archivos": ["S1_E1_pedidos-semana.xlsx"],
            "pasos": [
                _paso("Abre el archivo S1_E1_pedidos-semana.xlsx."),
                _paso("Revisa la columna Entrega de la hoja Pedidos.",
                      {"archivo": "S1_E1_pedidos-semana.xlsx", "hoja": "Pedidos", "rango": "A1:C5",
                       "marcas": [{"lugar": "C1:C5", "numero": None}],
                       "descripcion": "La columna Entrega de la hoja Pedidos."}),
                _paso("Adjunta el archivo y copia el prompt del recuadro."),
            ],
            "copiar": [{"tipo": "prompt", "titulo": "Prompt", "explicacion": "", "lineas": [
                "Rol: eres analista del área de Ventas.",
                "Contexto: el archivo adjunto trae los pedidos de la semana.",
                "Tarea: marca los pedidos que se recogen en tienda.",
                "Formato de salida: una tabla con el número de pedido y la entrega.",
                "Restricciones: " + NOTA]}],
            "mejora": {"texto": "Pide que ordene la tabla por número de pedido.", "pasos": [], "copiar": []},
        },
        {
            "numero": 2, "area": "Almacén", "titulo": "Corrige el aviso del almacén",
            "situacion": "El área de Almacén prepara un aviso para el equipo. El aviso debe repetir la duración del Sprint.",
            "archivos": ["S1_E2_aviso-almacen.docx"],
            "pasos": [
                _paso("Abre el archivo S1_E2_aviso-almacen.docx."),
                _paso("Busca la oración que habla del Sprint.",
                      {"archivo": "S1_E2_aviso-almacen.docx", "hoja": "", "rango": "",
                       "marcas": [{"lugar": "El Sprint dura dos semanas", "numero": None}],
                       "descripcion": "La oración del aviso que habla del Sprint."}),
                _paso("Adjunta el archivo y copia el prompt del recuadro."),
            ],
            "copiar": [{"tipo": "prompt", "titulo": "Prompt", "explicacion": "", "lineas": [
                "Rol: eres responsable del área de Almacén.",
                "Contexto: el archivo adjunto es un aviso para el equipo.",
                "Tarea: revisa que el aviso sea claro.",
                "Formato de salida: el aviso corregido.",
                "Restricciones: " + NOTA]}],
            "mejora": {"texto": "Pide una versión más corta del aviso.", "pasos": [], "copiar": []},
        },
        {
            "numero": 3, "area": "Recursos Humanos", "titulo": "Suma las horas de capacitación",
            "situacion": "El área de Recursos Humanos registra las horas de capacitación del equipo. "
                         "Necesita el total del mes.",
            "archivos": ["S1_E3_capacitacion.xlsx"],
            "pasos": [
                _paso("Abre el archivo y entra a la hoja **Horas**."),
                _paso("Copia la fórmula 1 en la celda C2."),
                _paso("Copia la celda C2 hacia abajo, hasta la fila 3."),
            ],
            "copiar": [{"tipo": "formula", "titulo": "Fórmula 1 · Revisa las horas de cada persona",
                        "explicacion": "Avisa cuando una persona tiene menos de 5 horas.",
                        "lineas": ['=SI(B2<5,"REVISAR","OK")']}],
            "mejora": {"texto": "Agrega el promedio de horas del equipo.",
                       "pasos": ["Escribe **Promedio** en la celda A5.", "Copia la fórmula 2 en la celda B5."],
                       "copiar": [{"tipo": "formula", "titulo": "Fórmula 2 · Promedio de horas",
                                   "explicacion": "Calcula el promedio de horas.", "lineas": ["=PROMEDIO(B2:B3)"]}]},
        },
    ],
    "archivos": [
        {"nombre": "S1_E1_pedidos-semana.xlsx", "descripcion": "Pedidos de la semana de la Sucursal Centro.",
         "hojas": [{"nombre": "Pedidos", "encabezados": ["Pedido", "Cliente", "Entrega"],
                    "filas": [["P-101", "Cliente A", "Recoge en tienda"], ["P-102", "Cliente B", "Recoge en tienda"],
                              ["P-103", "Cliente C", "Envío"], ["P-104", "Cliente D", "Recoge en tienda"]]}],
         "parrafos": [], "tabla": None, "problema": "El pedido P-103 dice «Envío»."},
        {"nombre": "S1_E2_aviso-almacen.docx", "descripcion": "Aviso del área de Almacén para el equipo.",
         "hojas": [], "parrafos": [{"estilo": "titulo", "texto": "Aviso al equipo"},
                                   {"estilo": "texto", "texto": "El Sprint dura dos semanas."},
                                   {"estilo": "texto", "texto": "Los pedidos se recogen en tienda."}],
         "tabla": None, "problema": "El aviso no dice dónde se recogen los pedidos urgentes."},
        {"nombre": "S1_E3_capacitacion.xlsx", "descripcion": "Horas de capacitación del equipo.",
         "hojas": [{"nombre": "Horas", "encabezados": ["Persona", "Horas"],
                    "filas": [["Analista 1", 4], ["Analista 2", 6], ["Total", "=SUM(B2:B3)"]]}],
         "parrafos": [], "tabla": None, "problema": "Ninguno."},
    ],
    "pasajes": [],
    "decisiones": [{"texto": "Usé las tres áreas de la ficha.", "tipo": "nota"}],
}


def limpio() -> dict:
    return copy.deepcopy(LIMPIO)


def con(cambio) -> dict:
    """Una copia del laboratorio limpio con un cambio: cambio(datos) modifica la copia."""
    datos = limpio()
    cambio(datos)
    return datos


# Cada error sembrado: (cambio, texto que debe aparecer en el problema).
SEMBRADOS = {
    "nombre con mayúsculas": (lambda d: (d["archivos"][0].update(nombre="S1_E1_Pedidos.xlsx"),
                                         d["ejercicios"][0].update(archivos=["S1_E1_Pedidos.xlsx"]),
                                         d["ejercicios"][0]["pasos"][1].update(figura=None)),
                              "el formato es S1_E[ejercicio]_[descripcion-corta]"),
    "archivo de otro ejercicio": (lambda d: d["ejercicios"][2]["archivos"].append("S1_E1_pedidos-semana.xlsx"),
                                  "que es de otro ejercicio"),
    "usa el resultado de otro": (lambda d: d["ejercicios"][1]["pasos"].append(
                                     {"texto": "Usa el resultado del ejercicio 1.", "figura": None}),
                                 "usa el resultado del ejercicio 1"),
    "espacio por llenar": (lambda d: d["ejercicios"][0]["copiar"][0]["lineas"].append("Cliente: [nombre del cliente]"),
                           "«[nombre del cliente]» en lo que el alumno copia"),
    "misma área seguida": (lambda d: d["ejercicios"][1].update(area="Ventas"), "las áreas rotan"),
    "marca fuera del rango": (lambda d: d["ejercicios"][0]["pasos"][1]["figura"]["marcas"][0].update(lugar="F9"),
                              "la marca «F9» no es una celda o un rango dentro"),
    "rango muy grande": (lambda d: d["ejercicios"][0]["pasos"][1]["figura"].update(rango="A1:C30"),
                         "se sale de los datos de la hoja"),
    "texto marcado que no está": (lambda d: d["ejercicios"][1]["pasos"][1]["figura"]["marcas"][0].update(
                                      lugar="El Sprint dura un mes"), "no está tal cual en el archivo"),
    "plazo sin fecha en el archivo": (lambda d: d["ejercicios"][0]["pasos"].append(
                                          {"texto": "Marca los pedidos con plazo vencido.", "figura": None}),
                                      "no trae la fecha de referencia"),
    "faltan ejercicios": (lambda d: d["ejercicios"].pop(), "at least 3"),
    "dos figuras en un ejercicio": (lambda d: d["ejercicios"][0]["pasos"][0].update(figura={
                                        "archivo": "S1_E1_pedidos-semana.xlsx", "hoja": "Pedidos", "rango": "A1:C5",
                                        "marcas": [{"lugar": "A1", "numero": None}], "descripcion": "La hoja."}),
                                    "tiene 2 figuras; va una como máximo"),
    "espacio por llenar en una fórmula": (lambda d: d["ejercicios"][2]["copiar"][0].update(lineas=['=SI(B2<___,"X","OK")']),
                                          "«___» en lo que el alumno copia"),
}
