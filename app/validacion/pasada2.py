"""Segunda pasada · Valor y funcionamiento (SKILL.md y PLAN.md §5.3).

Desde la etapa 5d la hace el revisor independiente (PLAN.md §0, decisión 12): responde las cuatro preguntas
por bloque y la lista de verificación de su material. Este módulo tiene las piezas comunes:

- los bloques del material y su huella;
- las palabras que aparecen con dos cifras distintas, para que el revisor decida si son el mismo dato
  (la hoja «Datos repetidos» la escribe el verificador);
- las cuatro preguntas y la lista de verificación de la skill, repartidas por material
  (PLAN.md §0, decisiones 11 y 20).
"""

import hashlib
from dataclasses import dataclass

from app import skill
from app.validacion import verificador

DEFECTOS = ["vacío", "inconsistencia", "ambigüedad", "relleno"]
RESPUESTAS_LISTA = ["cumple", "no cumple", "no aplica"]   # no dependen de cómo está escrita la pregunta
PREGUNTAS = ["¿Qué puede hacer el alumno con esto?", "¿Qué dato necesita y dónde está?",
             "¿Qué oración tiene dos lecturas?", "¿Qué decide si el caso no sale como el ejemplo?"]
CAMPOS = ["que_puede_hacer", "que_necesita", "dos_lecturas", "si_no_sale"]
NO_SE_APLICA = "No se aplica a este material."


@dataclass
class Bloque:
    nombre: str
    oraciones: list[str]

    @property
    def huella(self) -> str:
        return hashlib.sha256("\n".join(self.oraciones).encode("utf-8")).hexdigest()[:16]


def posibles_inconsistencias(bloques: list[Bloque]) -> list[str]:
    """Palabras que siguen a dos cifras distintas en el material, para que la IA decida si son el mismo dato."""
    textos = [(b.nombre, o) for b in bloques for o in b.oraciones]
    lineas = []
    for unidad, valores in verificador.verificar.unidades_con_cifras(textos).items():
        if len(valores) > 1:
            detalle = "; ".join(f"«{cifra} {unidad}» en: {' | '.join(lista[:2])}" for cifra, lista in valores.items())
            lineas.append(f"- {unidad}: {detalle}")
    return lineas


# ---------- Lista de verificación por material ----------

LECTURA, DIAPOSITIVAS, LABORATORIO = "Lectura", "Diapositivas", "Laboratorio"
GUIA, PRACTICA, EVALUACION = "Guía del profesor", "Práctica interactiva", "Evaluación"
TODOS = frozenset({LECTURA, DIAPOSITIVAS, LABORATORIO, GUIA, PRACTICA, EVALUACION})
CON_EJERCICIOS = frozenset({LABORATORIO, GUIA, PRACTICA, EVALUACION})
LO_REVISA_EL_PROGRAMA = frozenset()   # el verificador y las pruebas del diseño: no van a la IA
SIN_LECTURA_NI_DIAPOSITIVAS = TODOS - {LECTURA, DIAPOSITIVAS}   # PLAN.md §0, decisión 20

# Las cuatro preguntas por bloque. La segunda y la cuarta son para ejercicios y pasos que el alumno ejecuta:
# la lectura y las diapositivas solo responden la primera y la tercera (PLAN.md §0, decisión 20).
CAMPOS_POR_MATERIAL = {LECTURA: ["que_puede_hacer", "dos_lecturas"], DIAPOSITIVAS: ["que_puede_hacer", "dos_lecturas"]}


def campos_de(material: str) -> list[str]:
    return CAMPOS_POR_MATERIAL.get(material, CAMPOS)


def preguntas_de(material: str) -> list[str]:
    return [PREGUNTAS[CAMPOS.index(c)] for c in campos_de(material)]


# Cada pregunta de la skill, por su comienzo, con los materiales a los que se aplica.
APLICA_A = {
    "¿Cada sección aporta algo aplicable?": TODOS,
    "¿Hay alguna frase con dos ideas o con jerga?": TODOS,
    "¿Hay algo de la lista de lo que nunca se incluye?": SIN_LECTURA_NI_DIAPOSITIVAS,
    "¿Hay contenido de sesiones posteriores?": TODOS,
    "¿Ejecutaste cada ejercicio con sus archivos": CON_EJERCICIOS,
    "¿Algún ejercicio necesita el resultado de otro?": frozenset({LABORATORIO, PRACTICA, EVALUACION}),
    "¿Algún material da la respuesta de un ejercicio?": SIN_LECTURA_NI_DIAPOSITIVAS - {GUIA},   # la guía trae las respuestas
    "¿Los conceptos clave tienen el mismo nombre y orden": SIN_LECTURA_NI_DIAPOSITIVAS,
    "¿Las cifras, los nombres y la fecha de referencia coinciden": SIN_LECTURA_NI_DIAPOSITIVAS,
    "¿Un alumno del público descrito entiende los casos?": SIN_LECTURA_NI_DIAPOSITIVAS,
    "¿El diseño es uniforme?": LO_REVISA_EL_PROGRAMA,        # colores y recuadros: pruebas de los generadores
    "En el laboratorio:": frozenset({LABORATORIO}),
    "¿Algún material muestra minutos, puntos, notas o porcentajes?": LO_REVISA_EL_PROGRAMA,   # el verificador
    "En la evaluación:": frozenset({EVALUACION}),
}


def lista_completa() -> list[str]:
    return [l[2:].strip() for l in skill.secciones("Lista de verificación").splitlines() if l.startswith("- ")]


def lista_de_verificacion(material: str) -> list[str]:
    """Las preguntas de la lista de la skill que se aplican a este material. Si la skill agrega o cambia una
    pregunta, el programa se detiene: hay que decidir a qué materiales se aplica."""
    elegidas = []
    for pregunta in lista_completa():
        comienzo = next((c for c in APLICA_A if pregunta.startswith(c)), None)
        if comienzo is None:
            raise KeyError(f"La lista de verificación de SKILL.md tiene una pregunta nueva: «{pregunta}». "
                           "Agrégala a APLICA_A en app/validacion/pasada2.py.")
        if material in APLICA_A[comienzo]:
            elegidas.append(pregunta)
    return elegidas
