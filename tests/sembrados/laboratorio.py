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
                _paso("Abre el archivo y entra a la hoja **Horas**.",
                      {"archivo": "S1_E3_capacitacion.xlsx", "hoja": "Horas", "rango": "A1:B4",
                       "marcas": [{"lugar": "B2:B3", "numero": None}],
                       "descripcion": "Las horas de cada persona en la hoja Horas."}),
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
    "falta la figura": (lambda d: d["ejercicios"][0]["pasos"][1].update(figura=None),
                        "pide ubicar algo en el archivo y el ejercicio no tiene figura"),
    "espacio por llenar en una fórmula":(lambda d: d["ejercicios"][2]["copiar"][0].update(lineas=['=SI(B2<___,"X","OK")']),
                                          "«___» en lo que el alumno copia"),
}


# ---------- Curso sin IA ni Excel (PLAN.md §0, decisión 36) ----------
# El alumno hace la acción a mano en su archivo de práctica: los ejercicios no traen recuadros para copiar.

def _a_mano() -> dict:
    datos = limpio()
    primero, segundo, tercero = datos["ejercicios"]
    primero["pasos"][2] = _paso("Escribe **Recoge** o **Envía** en la columna Revisión de cada pedido.")
    segundo["pasos"][2] = _paso("Escribe debajo de esa oración dónde se recogen los pedidos urgentes.")
    tercero["pasos"] = [
        primero["pasos"][0] | {"texto": "Abre el archivo S1_E3_capacitacion.xlsx."},
        _paso("Revisa las horas de cada persona en la columna Horas de la hoja **Horas**.",
              tercero["pasos"][0]["figura"]),
        _paso("Escribe **REVISAR** en la columna Revisión de cada persona con menos de 5 horas."),
    ]
    for e in datos["ejercicios"]:
        e["copiar"] = []
    tercero["mejora"] = {"texto": "Escribe una nota que diga a quién se le pide completar sus horas.",
                         "pasos": ["Escribe la nota en la celda A6."], "copiar": []}
    return datos


A_MANO = _a_mano()


def a_mano() -> dict:
    return copy.deepcopy(A_MANO)


def con_a_mano(cambio) -> dict:
    datos = a_mano()
    cambio(datos)
    return datos


_PROMPT = {"tipo": "prompt", "titulo": "Prompt", "explicacion": "", "lineas": ["Tarea: clasifica los pedidos."]}
_FORMULA = {"tipo": "formula", "titulo": "Fórmula 1 · Revisa las horas", "explicacion": "Avisa si faltan horas.",
            "lineas": ['=SI(B2<5,"REVISAR","OK")']}

# Errores que solo son errores si el curso no usa IA ni Excel: (cambio, texto que debe aparecer en el problema).
SEMBRADOS_SIN_HERRAMIENTA = {
    "prompt en un curso sin IA": (lambda d: d["ejercicios"][0]["copiar"].append(dict(_PROMPT)),
                                  "trae un recuadro de prompt y el curso no usa IA"),
    "fórmula en un curso sin Excel": (lambda d: d["ejercicios"][2]["copiar"].append(dict(_FORMULA)),
                                      "trae un recuadro de fórmula y el curso no usa Excel"),
    "prompt en la mejora": (lambda d: d["ejercicios"][1]["mejora"]["copiar"].append(dict(_PROMPT)),
                            "trae un recuadro de prompt"),
    "paso que adjunta el archivo": (lambda d: d["ejercicios"][1]["pasos"].append(
                                        _paso("Adjunta el archivo y pide una revisión del aviso.")),
                                    "dice «Adjunta» y el curso no usa IA"),
    "paso que copia una fórmula": (lambda d: d["ejercicios"][2]["pasos"].append(
                                       _paso("Copia la fórmula 1 en la celda C2.")),
                                   "dice «fórmula» y el curso no usa Excel"),
}


# ---------- Listas de opciones (PLAN.md §0, decisión 60) ----------
# El primer archivo trae dos columnas donde el alumno elige: una con «Sí» y «No» y otra con conceptos del vocabulario.

CONCEPTOS = ["Manifiesto Ágil", "Pilares de Scrum", "Valores de Scrum"]


def _con_listas() -> dict:
    datos = limpio()
    hoja = datos["archivos"][0]["hojas"][0]
    hoja["encabezados"] += ["¿Recoge en tienda?", "Concepto"]
    for fila in hoja["filas"]:
        fila += [None, None]
    hoja["listas"] = [
        {"columna": "¿Recoge en tienda?", "opciones": ["Sí", "No"], "respuestas": ["Sí", "Sí", "No", "Sí"]},
        {"columna": "Concepto", "opciones": list(CONCEPTOS),
         "respuestas": ["Pilares de Scrum", "Valores de Scrum", "Pilares de Scrum", ""]},
    ]
    datos["ejercicios"][0]["pasos"].insert(2, _paso(
        "Elige **Sí** o **No** de la lista de la celda en la columna ¿Recoge en tienda? de cada pedido."))
    return datos


CON_LISTAS = _con_listas()


def con_listas() -> dict:
    return copy.deepcopy(CON_LISTAS)


def con_listas_y(cambio) -> dict:
    datos = con_listas()
    cambio(datos)
    return datos


def _lista(d, n):
    return d["archivos"][0]["hojas"][0]["listas"][n]


# Cada error sembrado en una lista: (cambio, texto que debe aparecer en el problema). Todos son FALLA.
SEMBRADOS_LISTAS = {
    "falta una respuesta": (lambda d: _lista(d, 1).update(opciones=CONCEPTOS[:2]),
                            "a la lista le falta la respuesta «Valores de Scrum»"),
    "una sola opción": (lambda d: _lista(d, 0).update(opciones=["Sí"]), "at least 2"),
    "otro orden": (lambda d: _lista(d, 1).update(opciones=[CONCEPTOS[1], CONCEPTOS[0], CONCEPTOS[2]]),
                   "los conceptos van en el orden de la fuente"),
    "variante prohibida": (lambda d: _lista(d, 1).update(opciones=["Agile", *CONCEPTOS[1:]]),
                           "la opción «Agile» es una variante prohibida"),
    "respuesta abierta": (lambda d: _lista(d, 0).update(respuestas=[
                              "Sí, porque el cliente vive cerca de la tienda", "Sí", "No", "Sí"]),
                          "es abierta"),
}

# La sesión enseña validación de datos: cualquier lista es una FALLA (decisión 60 f).
LISTA_EN_SESION_DE_VALIDACION = "la sesión enseña listas o validación de datos"

# El paso no dice que el alumno elige de la lista: AVISO del verificador (decisión 60 e).
SIN_PASO_DE_LA_LISTA = (lambda d: d["ejercicios"][0]["pasos"].pop(2), "ningún paso dice que el alumno elige")

# Decisión 61: una opción que no aparece escrita en las fichas, en «Antes de empezar» ni en los datos de su archivo es
# un AVISO, no una FALLA. Los pasos de la guía no cuentan. (cambio, opción que debe salir en el aviso)
OPCIONES_CON_AVISO = {
    "opción que no aparece en ningún lado": (lambda d: _lista(d, 0).update(opciones=["Sí", "No", "Tal vez"]), "Tal vez"),
    "opción que solo aparece en un paso": (lambda d: (
        _lista(d, 0).update(opciones=["Sí", "No", "Pendiente"]),
        d["ejercicios"][0]["pasos"].append(_paso("Elige **Pendiente** de la lista si no estás seguro."))), "Pendiente"),
}

# Opciones que valen sin aviso: salen de la ficha, de una tabla de «Antes de empezar» o de los datos del archivo.
OPCIONES_SIN_AVISO = {
    "de la ficha": lambda d: _lista(d, 0).update(opciones=["Sí", "No", "Sucursal Centro"]),
    "de una tabla de Antes de empezar": lambda d: (
        d["antes_de_empezar"]["tablas"].append({"titulo": "Criterios de riesgo", "encabezados": ["Nivel", "Cuándo"],
                                                 "filas": [["Alto", "Pedido urgente"], ["Bajo", "Pedido normal"]]}),
        _lista(d, 0).update(opciones=["Alto", "Bajo"], respuestas=["Alto", "Alto", "Bajo", "Alto"])),
    "de los datos del archivo": lambda d: _lista(d, 0).update(opciones=["Recoge en tienda", "Envío"],
                                                             respuestas=["Envío", "Envío", "Recoge en tienda", "Envío"]),
}
