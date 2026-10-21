"""Actividad web: un contenido limpio y errores puestos a propósito, uno por revisión (PLAN.md §4, fase 8a).

Cada caso cambia una sola cosa del contenido limpio y dice qué debe marcar la revisión del programa.
Las pruebas están en tests/unidad/test_actividad.py.
"""

import copy


def _opcion(texto, correcta, explicacion):
    return {"texto": texto, "correcta": correcta, "explicacion": explicacion}


def _pregunta(tipo, enunciado, puntos=1, **listas):
    return {"tipo": tipo, "enunciado": enunciado, "puntos": puntos, "opciones": listas.get("opciones", []),
            "elementos": listas.get("elementos", []), "pares": listas.get("pares", []),
            "categorias": listas.get("categorias", [])}


LIMPIA = {
    "titulo": "Scrum en la Sucursal Norte",
    "presentacion": ["Usted va a revisar cómo trabaja un equipo de ventas con Scrum."],
    "caso": {
        "titulo": "El caso: la Sucursal Norte",
        "parrafos": ["La Sucursal Norte registra sus pedidos de cada semana.", "El equipo revisa el registro cada viernes."],
        "tablas": [{"titulo": "Pedidos por semana", "encabezados": ["Semana", "Pedidos"],
                    "filas": [["Semana 1", "40"], ["Semana 2", "55"], ["Total", "95"]]}],
        "graficos": [{"titulo": "Pedidos por semana", "eje_x": "Semana", "eje_y": "Pedidos",
                      "categorias": ["Semana 1", "Semana 2"], "series": [{"nombre": "Pedidos", "valores": [40, 55]}]}],
    },
    "pasos": [
        {"titulo": "Reconozca los pilares", "introduccion": ["Scrum se apoya en sus pilares."],
         "recuerde": "Los pilares de Scrum son tres.",
         "preguntas": [_pregunta("opcion_unica", "¿Cuántos pilares tiene Scrum?", 2, opciones=[
             _opcion("Tres", True, "La lectura nombra tres pilares."),
             _opcion("Dos", False, "Faltaría un pilar: la lectura nombra tres."),
             _opcion("Cinco", False, "Cinco no es la cantidad de pilares: son tres.")])]},
        {"titulo": "Revise el cierre de la semana", "introduccion": ["El equipo cierra cada semana con una revisión."],
         "recuerde": "",
         "preguntas": [_pregunta("opcion_multiple", "¿Qué hace el equipo el viernes? Marque todas las que correspondan.",
                                 opciones=[
             _opcion("Revisa el registro de pedidos.", True, "El caso dice que revisa el registro cada viernes."),
             _opcion("Decide qué cambia la próxima semana.", True, "La revisión sirve para decidir un cambio."),
             _opcion("Cierra la sucursal.", False, "El caso no dice que la sucursal cierre."),
             _opcion("Borra el registro.", False, "El registro se revisa: no se borra.")])]},
        {"titulo": "Ordene la revisión", "introduccion": ["La revisión sigue un orden."], "recuerde": "",
         "preguntas": [_pregunta("ordenar", "Ordene los pasos de la revisión del viernes.", 2, elementos=[
             {"texto": "Leer el registro.", "explicacion": "Primero se mira lo que pasó.", "categoria": ""},
             {"texto": "Comparar las dos semanas.", "explicacion": "Después se comparan los datos.", "categoria": ""},
             {"texto": "Decidir un cambio.", "explicacion": "Al final se decide qué cambia.", "categoria": ""}])]},
        {"titulo": "Relacione y clasifique", "introduccion": ["Cada valor de Scrum se ve en una conducta."],
         "recuerde": "",
         "preguntas": [
             _pregunta("relacionar", "Relacione cada valor de Scrum con una conducta del equipo.", pares=[
                 {"izquierda": "Foco", "derecha": "Trabaja en un pedido a la vez.", "explicacion": "El foco evita dispersarse."},
                 {"izquierda": "Respeto", "derecha": "Escucha la opinión del almacén.", "explicacion": "El respeto valora al otro."},
                 {"izquierda": "Apertura", "derecha": "Muestra el registro a todos.", "explicacion": "La apertura hace visible el trabajo."}]),
             _pregunta("clasificar", "Clasifique cada conducta según el valor de Scrum que muestra.", 3,
                       categorias=["Foco", "Apertura"], elementos=[
                 {"texto": "Termina un pedido antes de tomar otro.", "explicacion": "Muestra foco.", "categoria": "Foco"},
                 {"texto": "Publica el tablero en la entrada.", "explicacion": "Muestra apertura.", "categoria": "Apertura"},
                 {"texto": "Cuenta los problemas en la reunión.", "explicacion": "Muestra apertura.", "categoria": "Apertura"}])]},
    ],
    "pasajes": [{"oracion": "Los pilares de Scrum son tres.", "fuente": "silabo.pdf", "ubicacion": "página 1",
                 "texto": "Scrum Master con IA"}],
    "decisiones": [{"texto": "Usé la Sucursal Norte como caso de la actividad.", "tipo": "decisión"}],
}
PUNTAJE_LIMPIO = 2 + 1 + 2 + 1 + 3


def _con(cambio) -> dict:
    datos = copy.deepcopy(LIMPIA)
    cambio(datos)
    return datos


def _pregunta_de(datos, paso, numero=0):
    return datos["pasos"][paso]["preguntas"][numero]


# (identificador, contenido con un solo error, texto que debe aparecer en la falla)
CASOS = [
    ("dos correctas", _con(lambda d: _pregunta_de(d, 0)["opciones"][1].update(correcta=True)),
     "tiene 2 opciones correctas"),
    ("ninguna correcta", _con(lambda d: _pregunta_de(d, 0)["opciones"][0].update(correcta=False)),
     "tiene 0 opciones correctas"),
    ("opcion sin explicacion", _con(lambda d: _pregunta_de(d, 0)["opciones"][2].update(explicacion=" ")),
     "«Cinco» no trae su explicación"),
    ("puntos en cero", _con(lambda d: _pregunta_de(d, 0).update(puntos=0)), "FALLA · estructura · pasos.0.preguntas.0.puntos"),
    ("cifra que no suma", _con(lambda d: d["caso"]["tablas"][0]["filas"][2].__setitem__(1, "90")),
     "la fila «Total» dice 90 en «Pedidos», pero las filas suman 95"),
    ("respuesta abierta", _con(lambda d: _pregunta_de(d, 2).update(enunciado="Escriba los pasos de la revisión del viernes.")),
     "pide una respuesta abierta"),
    ("tipo abierto", _con(lambda d: _pregunta_de(d, 2).update(tipo="abierta")), "FALLA · estructura · pasos.2.preguntas.0.tipo"),
    ("multiple sin incorrecta", _con(lambda d: [o.update(correcta=True) for o in _pregunta_de(d, 1)["opciones"]]),
     "necesita al menos una opción correcta y una incorrecta"),
    ("categoria inexistente", _con(lambda d: _pregunta_de(d, 3, 1)["elementos"][0].update(categoria="Coraje")),
     "va en «Coraje», que no es una de sus categorías"),
    ("derecha repetida", _con(lambda d: _pregunta_de(d, 3)["pares"][1].update(derecha="Trabaja en un pedido a la vez.")),
     "dos pares tienen la misma derecha"),
    ("lista de otro tipo", _con(lambda d: _pregunta_de(d, 0)["elementos"].append(
        {"texto": "Tres", "explicacion": "Son tres.", "categoria": ""})), "es «opcion_unica» y trae «elementos»"),
    ("pocos pasos", _con(lambda d: d["pasos"].pop()), "Pasos: tiene 3; van de 4 a 6"),
]


def _con_porcentajes(filas) -> dict:
    """El caso con una tabla de cifras y su porcentaje del total."""
    def cambio(d):
        d["caso"]["tablas"].append({"titulo": "Pedidos por canal", "encabezados": ["Canal", "Pedidos", "Parte del total"],
                                    "filas": filas})
    return _con(cambio)


CON_PORCENTAJES_LIMPIA = _con_porcentajes(
    [["Tienda", "60", "63 %"], ["Teléfono", "35", "37 %"], ["Total", "95", "100 %"]])

CASOS += [
    ("porcentaje mal calculado", _con_porcentajes(
        [["Tienda", "60", "70 %"], ["Teléfono", "35", "30 %"], ["Total", "95", "100 %"]]),
     "en «Tienda», «Parte del total» dice 70 %, pero 60 de 95 es el 63 %"),
    ("porcentajes que no suman cien", _con_porcentajes(
        [["Tienda", "60", "63 %"], ["Teléfono", "35", "37 %"], ["Total", "95", "90 %"]]),
     "la fila «Total» dice 90 % en «Parte del total», pero las filas suman 100"),
]
