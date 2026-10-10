"""Errores puestos a propósito, uno por revisión del verificador (PLAN.md §5.8).

Cada caso es una oración con un solo error, el nivel y la regla que el verificador debe marcar.
La configuración de prueba está en tests/unidad/test_verificador.py.
"""

CASOS_POR_ORACION = [
    # (identificador, oración con el error, nivel, regla)
    ("minutos", "Resuelve el ejercicio en 10 minutos.", "FALLA", "tiempo"),
    ("cronometro", "Activa el cronómetro antes de empezar.", "FALLA", "tiempo"),
    ("segundos", "Espera 30 segundos y vuelve a enviar el pedido.", "FALLA", "tiempo"),
    ("puntos", "Esta pregunta vale 5 puntos.", "FALLA", "puntaje"),
    ("puntaje", "El puntaje se suma al final.", "FALLA", "puntaje"),
    ("nota final", "La nota final sale de las tres preguntas.", "FALLA", "puntaje"),
    ("porcentaje de la nota", "El ejercicio representa el 20 % del curso.", "FALLA", "puntaje"),
    ("vale un porcentaje", "El informe vale el 30 % y se entrega al final.", "FALLA", "puntaje"),
    ("emoji", "Revisa el registro con cuidado ✅", "FALLA", "emoji"),
    ("nunca se incluye", "Objetivos de aprendizaje de la sesión.", "FALLA", "lo que nunca se incluye"),
    ("variante", "El equipo trabaja según el enfoque Agile.", "FALLA", "variante de un concepto"),
    ("dato fijo", "Fecha de referencia: lunes 5 de octubre de 2025.", "FALLA", "dato fijo"),
    ("cita", "La guía dice «Scrum es un marco para equipos grandes y complejos».", "FALLA", "cita sin fuente"),
    ("clausula", "Lo explica la lámina 99 del capítulo.", "FALLA", "referencia inexistente"),
    ("operacion", "El almacén tiene 3 × 4 = 13 estantes.", "FALLA", "operación"),
    ("operacion en palabras", "Doce más tres es igual a dieciséis.", "FALLA", "operación"),
    ("porcentaje mal calculado", "El 10 % de 200 es 30.", "FALLA", "operación"),
    ("archivo inexistente", "Adjunta el archivo S1_E9_no-existe.xlsx.", "FALLA", "archivo inexistente"),
    ("archivo de otra sesion", "Adjunta el archivo S2_E1_registro.xlsx.", "FALLA", "nombre de archivo"),
    ("relleno", "A continuación se presenta el registro del Sprint.", "AVISO", "relleno"),
    ("imprecisa", "Algunas situaciones contradicen el Manifiesto Ágil.", "AVISO", "palabra imprecisa"),
    ("lenguaje de IA", "Es importante destacar que el tablero se actualiza cada día.", "FALLA", "lenguaje de IA"),
]

# Oraciones correctas: el verificador no debe marcar nada en ellas (control limpio).
ORACIONES_LIMPIAS = [
    # Ya no son avisos (PLAN.md §0, decisión 19): un dato con horas o porcentaje y una oración larga.
    "La revisión dura 2 horas.",
    "El 20 % de los pedidos llega tarde.",
    "El equipo revisa cada pedido del almacén con el jefe del área y con el Scrum Master para "
    "decidir qué cambios hace antes del cierre del Sprint y cómo avisa a los clientes del retraso.",
    "Scrum tiene tres pilares.",
    "La guía dice «Scrum es gratuito y se aplica completo en cada equipo».",
    "Lo explica la lámina 43 del capítulo.",
    "Fecha de referencia: lunes 5 de octubre de 2026.",
    "El almacén tiene 3 × 4 = 12 estantes.",
    "Doce más tres es igual a quince.",
    "Adjunta el archivo S1_E1_registro-almacen.xlsx.",
    "El Manifiesto Ágil tiene cuatro aspectos.",
    "Lee las notas del profesor antes de la clase.",
    "El equipo estima con puntos de historia.",
    "En este curso, una situación contradice un aspecto solo cuando valora más el segundo elemento.",
]
