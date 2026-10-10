"""Pasajes de las fuentes y de las fichas, para la primera pasada (PLAN.md §5.2).

- buscar(): el programa elige los pasajes que más cubren las palabras de una oración, sin IA.
  La IA recibe esos pasajes y no la fuente completa (SPEC §9).
- ubicar(): comprueba que un pasaje copiado por la IA exista tal cual en la fuente
  y devuelve su ubicación real. Así la IA no puede inventar un pasaje.
"""

import bisect
import math
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from app.fichas import almacen, plantillas, verificacion
from app.fuentes import convertir

FICHA_DEL_CURSO = "ficha del curso"
FICHA_DE_LA_SESION = "ficha de la sesión"


def normal(texto: str) -> str:
    descompuesto = unicodedata.normalize("NFD", texto.lower())
    return " ".join("".join(c for c in descompuesto if unicodedata.category(c) != "Mn").split())


def literal(texto: str) -> str:
    """Igual que el verificador: solo cambian espacios, comillas y guiones."""
    reemplazos = {"“": '"', "”": '"', "«": '"', "»": '"', "‘": "'", "’": "'",
                  "–": "-", "—": "-", "­": "", " ": " ", "…": "..."}
    for viejo, nuevo in reemplazos.items():
        texto = texto.replace(viejo, nuevo)
    return " ".join(texto.split())


def flexible(texto: str) -> str:
    """Para ubicar un pasaje copiado con pequeñas diferencias (PLAN.md §0, decisión 18): sin tildes ni mayúsculas,
    sin signos, y con las palabras cortadas con guion al final de una línea unidas otra vez."""
    texto = re.sub(r"(\w)-\s+(\w)", r"\1\2", literal(texto))
    return " ".join(re.sub(r"[^\w\s]", " ", normal(texto)).split())


@dataclass
class Fuente:
    nombre: str
    pasajes: list[dict]
    continuo: str = ""
    inicios: list[int] = field(default_factory=list)

    def __post_init__(self):
        partes, posicion = [], 0
        for pasaje in self.pasajes:
            texto = literal(pasaje["texto"])
            self.inicios.append(posicion)
            partes.append(texto)
            posicion += len(texto) + 1
        self.continuo = " ".join(partes)
        self._minusculas = self.continuo.casefold()
        # Una palabra cortada con guion al final de un pasaje sigue en el siguiente: se une sin espacio.
        self._flexible, self._inicios_flexibles, cortada = "", [], False
        for pasaje in self.pasajes:
            if self._flexible and not cortada:
                self._flexible += " "
            self._inicios_flexibles.append(len(self._flexible))
            self._flexible += flexible(pasaje["texto"])
            cortada = bool(re.search(r"\w-$", literal(pasaje["texto"])))

    def ubicar(self, pasaje: str) -> str | None:
        buscado = literal(pasaje).strip(" .,;:\"'")
        if len(buscado) < 3:
            return None
        posicion = self.continuo.find(buscado)
        if posicion < 0:
            posicion = self._minusculas.find(buscado.casefold())
        if posicion >= 0:
            return self.pasajes[bisect.bisect_right(self.inicios, posicion) - 1]["ubicacion"]
        buscado = flexible(pasaje)
        if len(buscado) < 3:
            return None
        posicion = self._flexible.find(buscado)
        if posicion < 0:
            return None
        return self.pasajes[bisect.bisect_right(self._inicios_flexibles, posicion) - 1]["ubicacion"]


PALABRAS_VACIAS = set("""
a al algo ante antes como con contra cual cuando de del desde donde dos el ella ellas ellos en entre era es esa
ese eso esta este esto estos estas fue hay la las le les lo los mas me mi muy no nos o otra otro para pero por
que quien se ser si sin sobre su sus tambien te tiene tu un una uno unos unas y ya hace hacen cada todo toda
todos todas puede pueden debe deben son esta estan entonces asi aqui
""".split())


def raices(texto: str) -> set[str]:
    """Palabras con contenido, recortadas a 5 letras para que «inspección» e «inspeccionar» coincidan."""
    return {p[:5] for p in re.findall(r"[a-z0-9ñ]+", normal(texto)) if len(p) > 2 and p not in PALABRAS_VACIAS}


class Corpus:
    """Fuentes utilizables del curso, la ficha del curso y la ficha de la sesión.

    La búsqueda mide qué parte de las palabras de la oración cubre cada pasaje, con más peso para
    las palabras raras. Cada pasaje se considera también unido al siguiente de la misma página:
    así un título y la definición que lo sigue se encuentran juntos.
    """

    def __init__(self, fuentes: list[Fuente]):
        self.fuentes = {f.nombre: f for f in fuentes}
        self._ventanas = []
        for f in fuentes:
            for i, pasaje in enumerate(f.pasajes):
                self._ventanas.append((f.nombre, pasaje["ubicacion"], pasaje["texto"]))
                siguiente = f.pasajes[i + 1] if i + 1 < len(f.pasajes) else None
                if siguiente and siguiente["ubicacion"] == pasaje["ubicacion"]:
                    self._ventanas.append((f.nombre, pasaje["ubicacion"], f"{pasaje['texto']} {siguiente['texto']}"))
        self._raices = [raices(texto) for _, _, texto in self._ventanas]
        frecuencia: dict[str, int] = {}
        for conjunto in self._raices:
            for raiz in conjunto:
                frecuencia[raiz] = frecuencia.get(raiz, 0) + 1
        total = max(1, len(self._raices))
        self._peso = {raiz: math.log(1 + total / veces) for raiz, veces in frecuencia.items()}

    @classmethod
    def del_curso(cls, carpeta_curso: Path, sesion: int, extras: list[Fuente] | None = None) -> "Corpus":
        fuentes = []
        for archivo in verificacion.fuentes_utilizables(carpeta_curso):
            fuentes.append(Fuente(archivo, convertir.leer_pasajes(carpeta_curso, archivo)))
        for nombre, ruta in ((FICHA_DEL_CURSO, almacen.ruta_ficha(carpeta_curso, "curso", extension=".md")),
                             (FICHA_DE_LA_SESION, almacen.ruta_ficha(carpeta_curso, "sesion", sesion, ".md"))):
            fuentes.append(Fuente(nombre, _lineas_de_ficha(ruta)))
        return cls(fuentes + (extras or []))

    def buscar(self, texto: str, cantidad: int = 3) -> list[dict]:
        buscadas = raices(texto)
        if not buscadas or not self._ventanas:
            return []
        maximo = math.log(1 + max(1, len(self._raices)))
        peso_total = sum(self._peso.get(r, maximo) for r in buscadas)
        puntajes = []
        for i, conjunto in enumerate(self._raices):
            comunes = buscadas & conjunto
            if comunes:
                cobertura = sum(self._peso[r] for r in comunes) / peso_total
                puntajes.append((cobertura, -len(conjunto), i))
        puntajes.sort(reverse=True)
        resultado, vistos = [], set()
        for cobertura, _, i in puntajes:
            fuente, ubicacion, texto_ventana = self._ventanas[i]
            clave = (fuente, ubicacion, texto_ventana[:60])
            if clave in vistos:
                continue
            vistos.add(clave)
            resultado.append({"fuente": fuente, "ubicacion": ubicacion, "texto": texto_ventana,
                              "parecido": round(100 * cobertura)})
            if len(resultado) == cantidad:
                break
        return resultado

    def ubicar(self, fuente: str, pasaje: str) -> str | None:
        if fuente in self.fuentes:
            return self.fuentes[fuente].ubicar(pasaje)
        return None

    def ubicar_en_cualquiera(self, pasaje: str) -> tuple[str, str] | None:
        for nombre, fuente in self.fuentes.items():
            ubicacion = fuente.ubicar(pasaje)
            if ubicacion:
                return nombre, ubicacion
        return None


NOTAS = re.compile(r"\s*(?:\(propuesto\)\s*)?(?:\(fuente: .*\))?\s*$")  # el nombre del archivo puede traer paréntesis


def _sin_notas(texto: str) -> str:
    return NOTAS.sub("", texto).strip()


def _etiquetas(tipo: str) -> list[str]:
    """Etiquetas de la plantilla, de la más larga a la más corta (algunas tienen «:» dentro)."""
    etiquetas = {c.etiqueta for c, _ in plantillas.campos_de(tipo)}
    for seccion in plantillas.PLANTILLAS[tipo][1]:
        for elemento in seccion.elementos:
            if isinstance(elemento, plantillas.Campo):
                etiquetas.add(elemento.etiqueta)
    return sorted(etiquetas, key=len, reverse=True)


def _lineas_de_ficha(ruta: Path) -> list[dict]:
    """Cada valor de la ficha es un pasaje. Su ubicación es la etiqueta del campo.

    Los renglones con sangría son, o bien subcampos de la plantilla («Bloque 1:»), o bien
    elementos de un campo de varias líneas, que se guardan completos.
    """
    if not ruta.exists():
        return []
    etiquetas = _etiquetas("curso" if ruta.name.startswith("ficha_del_curso") else "sesion")
    pasajes, actual, bloque = [], "ficha", ""
    de_bloque = {c.etiqueta for s in plantillas.PLANTILLAS["sesion"][1] for e in s.elementos
                 if isinstance(e, plantillas.Repetible) for c in e.campos[1:]}

    def separar(cuerpo: str):
        for etiqueta in etiquetas:
            if cuerpo == etiqueta or cuerpo.startswith(etiqueta + ":") or cuerpo.startswith(etiqueta + " "):
                return etiqueta, cuerpo[len(etiqueta):].lstrip(":").strip()
        return None, cuerpo

    def agregar(texto, donde):
        nonlocal bloque
        inicio_de_bloque = re.match(r"^(Ejercicio|Pregunta) \d+", donde)
        if inicio_de_bloque:
            bloque = inicio_de_bloque.group(0)
        elif donde in de_bloque and bloque:
            donde = f"{bloque} · {donde}"
        texto = _sin_notas(texto)
        if texto and texto != "Falta definir" and not texto.startswith("Conflicto:"):
            pasajes.append({"texto": texto, "ubicacion": donde})

    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if not linea.strip():
            continue
        if linea.startswith("- "):
            etiqueta, valor = separar(linea[2:].strip())
            actual = etiqueta or linea[2:].strip()
            if etiqueta:
                agregar(valor, etiqueta)
        elif linea.startswith("  "):
            etiqueta, valor = separar(linea.strip())
            if etiqueta:
                agregar(valor, etiqueta)
            else:
                agregar(linea.strip(), actual)
    return pasajes
