"""Campos de las dos fichas, copiados sin cambios de las plantillas de SKILL.md (SPEC §3).

Una prueba compara la ficha vacía con la plantilla de la skill, letra por letra.
Tipos de campo:
- "texto": una línea, "- Etiqueta: valor".
- "lineas": varias líneas, cada una en su renglón con sangría.
- "lista": como "lineas", pero la plantilla muestra renglones numerados vacíos.
- "grupo": una etiqueta seguida de subcampos con sangría (los bloques de la lectura).
"""

from dataclasses import dataclass, field

MAX_EJERCICIOS = 5
MAX_PREGUNTAS = 5


@dataclass(frozen=True)
class Campo:
    id: str
    etiqueta: str            # tal como está en la plantilla, sin el guion inicial
    tipo: str = "texto"
    obligatorio: bool = False
    dos_puntos: bool = True
    vacio: tuple[str, ...] = ()           # renglones que la plantilla muestra cuando está vacío
    subcampos: tuple["Campo", ...] = ()
    sangria: str = "- "

    @property
    def nombre(self) -> str:
        """Etiqueta para mostrar en la página, sin «(obligatorio)» ni notas entre paréntesis finales."""
        return self.etiqueta.replace(" (obligatorio)", "")


@dataclass(frozen=True)
class Repetible:
    """Bloque que se repite: un ejercicio del laboratorio o una pregunta de la evaluación."""
    prefijo: str              # "ejercicio" o "pregunta"
    maximo: int
    campos: tuple[Campo, ...]
    encabezado: str = ""      # renglón antes de los bloques, si la plantilla lo tiene
    sangria: str = "- "


@dataclass(frozen=True)
class Seccion:
    titulo: str
    elementos: tuple = field(default_factory=tuple)

    @property
    def obligatoria(self) -> bool:
        return "(obligatorio)" in self.titulo


def _c(id, etiqueta, **opciones):
    return Campo(id, etiqueta, obligatorio="(obligatorio)" in etiqueta, **opciones)


FICHA_DEL_CURSO = (
    "FICHA DEL CURSO",
    (
        Seccion("1. Curso", (
            _c("curso.nombre", "Nombre del curso (obligatorio)"),
            _c("curso.idioma", "Idioma del material"),
            _c("curso.sesiones", "Sesiones (obligatorio). Una línea por sesión: número, título y alcance.",
               tipo="lista", dos_puntos=False, vacio=("1.", "2.", "3.")),
        )),
        Seccion("2. Público", (
            _c("publico.quienes", "Quiénes son"),
            _c("publico.saben", "Qué saben ya del tema"),
            _c("publico.valoran", "Qué valoran"),
        )),
        Seccion("3. Caso del curso", (
            _c("caso.empresa", "Empresa o institución ficticia y rubro"),
            _c("caso.areas", "Áreas entre las que rotan los ejemplos"),
            _c("caso.moneda", "Moneda y país de los casos"),
        )),
        Seccion("4. Datos fijos del caso", (
            _c("datos.fecha", "Fecha de referencia para los ejercicios con plazos"),
            _c("datos.fijos", "Cifras, reglas y nombres que deben repetirse igual en todas las sesiones",
               tipo="lineas"),
        )),
        Seccion("5. Identidad visual", (
            _c("visual.logo", 'Logo (archivo en el proyecto o "sin logo")'),
            _c("visual.principal", "Color principal"),
            _c("visual.acento", "Color de acento"),
            _c("visual.advertencia", "Color de advertencia"),
            _c("visual.fondos", "Fondos de recuadro"),
            _c("visual.texto", "Color del texto"),
            _c("visual.tipografia", "Tipografía"),
        )),
        Seccion("6. Portada", (
            _c("portada.docente", "Docente"),
            _c("portada.contacto", "Enlaces o datos de contacto"),
        )),
        Seccion("7. Herramientas", (
            _c("herramientas.neutral", "¿Material neutral respecto a marcas? (sí o no)"),
            _c("herramientas.cual", "Si no es neutral, herramienta y versión que usan los alumnos"),
            _c("herramientas.adjuntos", "¿La herramienta de los alumnos acepta archivos adjuntos? (sí, no o no sé)"),
        )),
        Seccion("8. Materiales", (
            _c("materiales.por_sesion", "Materiales por sesión (por defecto, los seis)"),
            _c("materiales.nunca", "Lo que nunca se incluye (por defecto: tiempos, puntajes, objetivos de "
               "aprendizaje, requisitos previos, glosarios, relleno, emojis y lenguaje publicitario)"),
        )),
        Seccion("9. Modelos", (
            _c("modelos.aprobados", "Materiales ya aprobados que sirven de modelo de diseño y tono"),
        )),
    ),
)

FICHA_DE_LA_SESION = (
    "FICHA DE LA SESIÓN",
    (
        Seccion("1. Sesión", (
            _c("sesion.numero_titulo", "Número y título (obligatorio)"),
            _c("sesion.alcance", "Alcance (obligatorio)"),
            _c("sesion.ya_vieron", "Lo que los alumnos ya vieron en sesiones anteriores"),
            _c("sesion.no_adelantar", "Temas de sesiones posteriores que no se deben adelantar"),
        )),
        Seccion("2. Lectura", (
            _c("lectura.temas", "Temas que debe cubrir (obligatorio), agrupados en 2 a 4 bloques", tipo="grupo",
               subcampos=tuple(Campo(f"lectura.bloque.{n}", f"Bloque {n}", sangria="  ") for n in range(1, 5))),
            _c("lectura.ejemplo", "Ejemplo completo que debe incluir, con un caso distinto al del laboratorio"),
            _c("lectura.aplicalo", 'Contenido de "Aplícalo así"'),
            _c("lectura.cuidado", 'Riesgos de "Cuidado con" (de 1 a 3)', tipo="lineas"),
        )),
        Seccion("3. Vocabulario de la sesión", (
            _c("vocabulario.conceptos", "Conceptos clave, con su nombre único y su orden", tipo="lineas"),
        )),
        Seccion("4. Laboratorio (de 3 a 5 ejercicios; repite este bloque por cada uno)", (
            Repetible("ejercicio", MAX_EJERCICIOS, (
                Campo("area", "Ejercicio [número] · Área"),
                Campo("accion", "Acción que realiza el alumno"),
                Campo("entregable", "Entregable que produce"),
                Campo("archivo", "Archivo de práctica: formato y contenido"),
                Campo("problema", "Problema que el archivo trae a propósito"),
                Campo("respuesta", "Respuesta correcta o resultado que debe salir"),
                Campo("pregunta_herramienta", "Si la herramienta debe preguntar algo, respuesta exacta del alumno"),
            )),
        )),
        Seccion("5. Práctica interactiva", (
            _c("practica.estaciones", "Estaciones (de 5 a 7): nombre y qué decide el alumno en cada una", tipo="lineas"),
            _c("practica.ultima", "Última estación: qué arma el alumno para su propio trabajo"),
        )),
        Seccion("6. Evaluación práctica (PBQ)", (
            _c("evaluacion.consulta", "Material que el alumno puede consultar durante la evaluación"),
            _c("evaluacion.entrega", "Forma de entrega de las respuestas"),
            Repetible("pregunta", MAX_PREGUNTAS, (
                Campo("concepto", "Pregunta [número] · Concepto que evalúa"),
                Campo("tarea", "Tarea que realiza el alumno"),
                Campo("archivo", "Archivo de la evaluación: formato y contenido"),
                Campo("problema", "Problema que el archivo trae a propósito"),
                Campo("respuesta", "Respuesta correcta"),
            ), encabezado="- Preguntas (por defecto, 3; repite este bloque por cada una)", sangria="  "),
        )),
        Seccion("7. Materiales de esta sesión", (
            _c("materiales.cuales", "Cuáles se producen (por defecto, los seis)"),
        )),
    ),
)

PLANTILLAS = {"curso": FICHA_DEL_CURSO, "sesion": FICHA_DE_LA_SESION}


def campos_de(tipo: str) -> list[tuple[Campo, Seccion]]:
    """Todos los campos que guardan un valor, con su sección, en el orden de la plantilla."""
    resultado = []
    for seccion in PLANTILLAS[tipo][1]:
        for elemento in seccion.elementos:
            if isinstance(elemento, Repetible):
                for numero in range(1, elemento.maximo + 1):
                    for campo in elemento.campos:
                        resultado.append((Campo(
                            f"{elemento.prefijo}.{numero}.{campo.id}",
                            campo.etiqueta.replace("[número]", str(numero)),
                            sangria=elemento.sangria,
                        ), seccion))
            elif elemento.tipo == "grupo":
                resultado.extend((sub, seccion) for sub in elemento.subcampos)
            else:
                resultado.append((elemento, seccion))
    return resultado


def es_obligatorio(campo: Campo, seccion: Seccion) -> bool:
    return campo.obligatorio or seccion.obligatoria


def _renglones(valor: str) -> list[str]:
    return [linea.strip() for linea in (valor or "").splitlines() if linea.strip()]


def _bloque_repetible_lleno(repetible: Repetible, numero: int, valores: dict) -> bool:
    return any((valores.get(f"{repetible.prefijo}.{numero}.{c.id}") or {}).get("valor") for c in repetible.campos)


def renderizar(tipo: str, valores: dict, anotar=lambda campo_id: "") -> str:
    """Escribe la ficha con el texto exacto de la plantilla.

    valores: {id: {"valor": ...}}. `anotar` devuelve la nota de origen de un campo,
    por ejemplo «(fuente: silabo.pdf)». Con valores vacíos, el resultado es la plantilla.
    """
    titulo, secciones = PLANTILLAS[tipo]
    lineas = [titulo]

    def valor(campo_id):
        return (valores.get(campo_id) or {}).get("valor", "")

    def linea_simple(campo: Campo, campo_id: str, sangria: str):
        texto = valor(campo_id).strip()
        nota = anotar(campo_id)
        lineas.append(f"{sangria}{campo.etiqueta}:" + (f" {texto}" if texto else "") + (f" {nota}" if nota else ""))

    for seccion in secciones:
        lineas += ["", seccion.titulo]
        for elemento in seccion.elementos:
            if isinstance(elemento, Repetible):
                if elemento.encabezado:
                    lineas.append(elemento.encabezado)
                llenos = [n for n in range(1, elemento.maximo + 1) if _bloque_repetible_lleno(elemento, n, valores)]
                if not llenos:
                    for campo in elemento.campos:
                        lineas.append(f"{elemento.sangria}{campo.etiqueta}:")
                for numero in llenos:
                    for campo in elemento.campos:
                        etiqueta = campo.etiqueta.replace("[número]", str(numero))
                        linea_simple(Campo(campo.id, etiqueta), f"{elemento.prefijo}.{numero}.{campo.id}", elemento.sangria)
            elif elemento.tipo == "grupo":
                lineas.append(f"- {elemento.etiqueta}:")
                for sub in elemento.subcampos:
                    linea_simple(sub, sub.id, "  ")
            elif elemento.tipo in ("lista", "lineas"):
                nota = anotar(elemento.id)
                cabeza = f"- {elemento.etiqueta}" + (":" if elemento.dos_puntos else "") + (f" {nota}" if nota else "")
                lineas.append(cabeza)
                renglones = _renglones(valor(elemento.id))
                if renglones:
                    lineas += [f"  {r}" for r in renglones]
                else:
                    lineas += [f"  {r}" for r in elemento.vacio]
            else:
                linea_simple(elemento, elemento.id, "- ")
    return "\n".join(lineas) + "\n"


def vista(tipo: str, campos: dict) -> list[dict]:
    """Estructura para el formulario de la página: secciones con sus campos y bloques repetidos."""
    def dato(campo: Campo, campo_id: str, seccion: Seccion, etiqueta: str | None = None) -> dict:
        guardado = campos.get(campo_id) or {}
        return {
            "id": campo_id,
            "etiqueta": etiqueta or campo.etiqueta,
            "multilinea": campo.tipo in ("lista", "lineas"),
            "obligatorio": campo.obligatorio or seccion.obligatoria,
            "valor": guardado.get("valor", ""),
            "origen": guardado.get("origen", ""),
            "estado": guardado.get("estado", ""),
            "versiones": guardado.get("versiones", []),
        }

    secciones = []
    for seccion in PLANTILLAS[tipo][1]:
        elementos = []
        for elemento in seccion.elementos:
            if isinstance(elemento, Repetible):
                bloques = []
                for numero in range(1, elemento.maximo + 1):
                    bloques.append({"numero": numero, "campos": [
                        dato(c, f"{elemento.prefijo}.{numero}.{c.id}", seccion, c.etiqueta.replace("[número]", str(numero)))
                        for c in elemento.campos
                    ]})
                elementos.append({"repetible": True, "nombre": elemento.prefijo, "encabezado": elemento.encabezado.lstrip("- "), "bloques": bloques})
            elif elemento.tipo == "grupo":
                # Desde la decisión 16, los temas de la lectura se exigen al generarla, no al confirmar la ficha.
                etiqueta = elemento.etiqueta.replace("(obligatorio)", "(obligatorio para generar la lectura)")
                elementos.append({"grupo": True, "etiqueta": etiqueta,
                                  "campos": [dato(s, s.id, seccion) | {"obligatorio": False} for s in elemento.subcampos]})
            else:
                elementos.append(dato(elemento, elemento.id, seccion))
        secciones.append({"titulo": seccion.titulo, "elementos": elementos})
    return secciones
