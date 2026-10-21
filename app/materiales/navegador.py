"""Prueba de la página del alumno en un navegador real (PLAN.md §5.7 y §4, fase 8d).

Playwright abre la página sin conexión, en computadora (1280 × 800) y en celular (375 × 812), en modo claro y oscuro,
y la recorre como un alumno con el contrato de atributos «data-» de la guía del diseñador:
- en cada pantalla, sin errores de JavaScript, sin desborde a los costados y con botones de 44 px como mínimo;
- todo correcto da el puntaje máximo y todo incorrecto da cero, y cada pregunta dice si acertó;
- con el teclado se llega al botón de avanzar, su foco se ve y Enter avanza;
- con movimiento reducido no corre ninguna animación;
- al recargar se recupera el avance, y «Copiar mi entrega» trae el nombre, las respuestas y el puntaje.
Cada falla dice en qué tamaño y modo, y en qué pantalla, pasó. Las capturas de las primeras fallas van al diseñador.
"""

from dataclasses import dataclass, field
from pathlib import Path

ALTO_MINIMO = 44
ESPERA_MS = 4000
CAPTURAS_MAXIMAS = 3
COMPUTADORA, CELULAR = {"width": 1280, "height": 800}, {"width": 375, "height": 812}
# (nombre, tamaño, modo, cómo responde): cada combinación recorre la página entera.
RECORRIDOS = [
    ("Computadora, modo claro", COMPUTADORA, "light", "correctas"),
    ("Celular, modo oscuro", CELULAR, "dark", "incorrectas"),
    ("Computadora, modo oscuro", COMPUTADORA, "dark", "incorrectas"),
    ("Celular, modo claro", CELULAR, "light", "correctas"),
]

_CHICOS = """() => {
  const vistos = [...document.querySelectorAll('button, select, a[href], input[type=text], textarea, [data-accion]')];
  return vistos.filter(e => {
    const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && r.height < 43.5;
  }).map(e => (e.getAttribute('aria-label') || e.textContent || e.tagName).trim().replace(/\\s+/g, ' ').slice(0, 40)
              + ' (' + Math.round(e.getBoundingClientRect().height) + ' px)');
}"""
_DESBORDE = "() => document.documentElement.scrollWidth - window.innerWidth"
_ORDEN = """q => { const v = []; q.querySelectorAll('[data-elemento]').forEach(e => {
  const n = +e.dataset.elemento; if (!v.includes(n)) v.push(n); }); return v; }"""
_FOCO = """() => { const e = document.activeElement; if (!e) return null; const s = getComputedStyle(e);
  return { accion: e.getAttribute('data-accion'),
           visible: (s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0) || s.boxShadow !== 'none' }; }"""
_ANIMACIONES = """() => document.getAnimations().filter(a => { const t = a.effect && a.effect.getComputedTiming();
  return a.playState === 'running' && t && t.duration > 50; }).length"""


@dataclass
class Informe:
    fallas: list[str] = field(default_factory=list)
    lineas: list[str] = field(default_factory=list)
    capturas: list[Path] = field(default_factory=list)


def disponible() -> bool:
    """Playwright y su navegador están instalados (requirements.txt y «playwright install chromium»)."""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False


class _Recorrido:
    def __init__(self, pagina, datos: dict, nombre: str, informe: Informe, capturas: Path | None):
        self.pagina, self.datos, self.nombre, self.informe, self.carpeta = pagina, datos, nombre, informe, capturas
        self.errores_js: list[str] = []
        pagina.on("pageerror", lambda e: self.errores_js.append(str(e).splitlines()[0][:160]))

    def falla(self, pantalla: str, texto: str) -> None:
        self.informe.fallas.append(f"{self.nombre}, {pantalla}: {texto}")
        if self.carpeta is not None and len(self.informe.capturas) < CAPTURAS_MAXIMAS:
            self.carpeta.mkdir(parents=True, exist_ok=True)
            ruta = self.carpeta / f"falla_{len(self.informe.capturas) + 1}.png"
            try:
                self.pagina.screenshot(path=str(ruta))
                self.informe.capturas.append(ruta)
            except Exception:
                pass

    def revisar_pantalla(self, pantalla: str) -> None:
        if self.errores_js:
            self.falla(pantalla, "error de JavaScript: " + " | ".join(self.errores_js))
            self.errores_js.clear()
        desborde = self.pagina.evaluate(_DESBORDE)
        if desborde > 1:
            self.falla(pantalla, f"la página se desborda {desborde} px a los costados.")
        chicos = self.pagina.evaluate(_CHICOS)
        if chicos:
            self.falla(pantalla, f"controles de menos de {ALTO_MINIMO} px de alto: {', '.join(chicos[:4])}.")

    def visible(self, paso: str) -> bool:
        try:
            self.pagina.locator(f'[data-paso="{paso}"]').first.wait_for(state="visible", timeout=ESPERA_MS)
            return True
        except Exception:
            return False

    def avanzar(self, pantalla: str, destino: str) -> bool:
        try:
            self.pagina.locator('[data-accion="siguiente"]:visible').first.click(timeout=ESPERA_MS)
        except Exception:
            self.falla(pantalla, "no encuentro un botón data-accion=\"siguiente\" visible.")
            return False
        if not self.visible(destino):
            self.falla(pantalla, f"después de «Siguiente» no se ve la pantalla data-paso=\"{destino}\".")
            return False
        return True

    # ---------- Responder una pregunta ----------

    def responder(self, q, pregunta: dict, correctas: bool) -> None:
        tipo = pregunta["tipo"]
        if tipo in ("opcion_unica", "opcion_multiple"):
            buenas = [k for k, o in enumerate(pregunta["opciones"]) if o["correcta"]]
            malas = [k for k, o in enumerate(pregunta["opciones"]) if not o["correcta"]]
            for k in (buenas if correctas else malas[:1]):
                q.locator(f'input[value="{k}"]').first.check(force=True, timeout=ESPERA_MS)
        elif tipo == "ordenar" and correctas:
            for destino in range(len(pregunta["elementos"])):
                for _ in range(len(pregunta["elementos"])):
                    orden = q.evaluate(_ORDEN)
                    if orden.index(destino) <= destino:
                        break
                    q.locator(f'[data-elemento="{destino}"] [data-accion="subir"]').first.click(timeout=ESPERA_MS)
        elif tipo == "relacionar":
            total = len(pregunta["pares"])
            for k in range(total):
                valor = k if correctas else (k + 1) % total
                q.locator(f'select[data-izquierda="{k}"]').first.select_option(value=str(valor), timeout=ESPERA_MS)
        elif tipo == "clasificar":
            categorias = pregunta["categorias"]
            for k, e in enumerate(pregunta["elementos"]):
                valor = e["categoria"] if correctas else next(c for c in categorias if c != e["categoria"])
                q.locator(f'select[data-elemento="{k}"]').first.select_option(value=valor, timeout=ESPERA_MS)

    def pregunta(self, pantalla: str, numero: str, pregunta: dict, correctas: bool) -> None:
        q = self.pagina.locator(f'[data-pregunta="{numero}"]').first
        try:
            if pregunta["tipo"] == "ordenar" and q.evaluate(_ORDEN) == list(range(len(pregunta["elementos"]))):
                self.falla(pantalla, f"la pregunta {numero} muestra los elementos ya en el orden correcto.")
            self.responder(q, pregunta, correctas)
            q.locator('[data-accion="comprobar"]').first.click(timeout=ESPERA_MS)
            resultado = q.locator('[data-resultado="correcta"], [data-resultado="incorrecta"]').first
            resultado.wait_for(timeout=ESPERA_MS)
            obtenido = resultado.get_attribute("data-resultado")
        except Exception as error:
            self.falla(pantalla, f"no pude responder la pregunta {numero} ({pregunta['tipo']}): "
                                 f"{str(error).splitlines()[0][:160]}")
            return
        esperado = "correcta" if correctas else "incorrecta"
        if obtenido != esperado:
            self.falla(pantalla, f"la pregunta {numero} ({pregunta['tipo']}) respondida {'bien' if correctas else 'mal'} "
                                 f"dice «{obtenido}».")

    # ---------- La página entera ----------

    def recorrer(self, correctas: bool) -> int | None:
        """Responde todo bien o todo mal y devuelve el puntaje que muestra la entrega."""
        if not self.visible("0"):
            self.falla("inicio", "no se ve la pantalla data-paso=\"0\".")
            return None
        self.revisar_pantalla("inicio")
        for i, paso in enumerate(self.datos["pasos"], start=1):
            pantalla = f"paso {i}"
            if not self.avanzar("inicio" if i == 1 else f"paso {i - 1}", str(i)):
                return None
            self.revisar_pantalla(pantalla)
            for j, pregunta in enumerate(paso["preguntas"], start=1):
                self.pregunta(pantalla, f"{i}.{j}", pregunta, correctas)
            self.revisar_pantalla(pantalla)
        if not self.avanzar(f"paso {len(self.datos['pasos'])}", "entrega"):
            return None
        try:
            self.pagina.locator('[data-campo="nombre"]').first.fill("Ana Prueba", timeout=ESPERA_MS)
        except Exception:
            self.falla("entrega", "no encuentro el campo data-campo=\"nombre\".")
        self.revisar_pantalla("entrega")
        return self.puntaje()

    def puntaje(self) -> int | None:
        try:
            texto = self.pagina.locator("[data-puntaje]").first.inner_text(timeout=ESPERA_MS)
            return int("".join(c for c in texto if c.isdigit()))
        except Exception:
            self.falla("entrega", "no encuentro el número del puntaje en data-puntaje.")
            return None


def _texto_copiado(pagina) -> str:
    try:
        return pagina.evaluate("navigator.clipboard.readText()") or ""
    except Exception:
        pass
    for area in pagina.locator("textarea").all():
        try:
            if area.is_visible() and area.input_value():
                return area.input_value()
        except Exception:
            continue
    return ""


def probar(ruta: Path, datos: dict, capturas: Path | None = None) -> Informe:
    """Recorre la página en las cuatro combinaciones y hace las pruebas de teclado, movimiento, recarga y copia."""
    from playwright.sync_api import sync_playwright

    informe = Informe()
    url = ruta.resolve().as_uri()
    total = datos["puntaje_total"]
    primera_correcta = next(o["texto"] for p in datos["pasos"] for q in p["preguntas"] for o in q["opciones"]
                            if o["correcta"]) if any(q["opciones"] for p in datos["pasos"] for q in p["preguntas"]) else ""
    with sync_playwright() as p:
        navegador = p.chromium.launch()
        try:
            for nombre, tamano, modo, respuestas in RECORRIDOS:
                contexto = navegador.new_context(viewport=tamano, color_scheme=modo,
                                                 permissions=["clipboard-read", "clipboard-write"])
                # Sin conexión: la página tiene que funcionar sin las fuentes de Google.
                contexto.route("**/*", lambda r: r.abort() if r.request.url.startswith("http") else r.continue_())
                pagina = contexto.new_page()
                recorrido = _Recorrido(pagina, datos, nombre, informe, capturas)
                pagina.goto(url)
                correctas = respuestas == "correctas"
                obtenido = recorrido.recorrer(correctas)
                esperado = total if correctas else 0
                if obtenido is not None and obtenido != esperado:
                    recorrido.falla("entrega", f"con todas las respuestas {'correctas' if correctas else 'incorrectas'} "
                                               f"el puntaje dice {obtenido}; debe decir {esperado}.")
                if nombre == RECORRIDOS[0][0] and obtenido is not None:
                    pagina.reload()
                    if not recorrido.visible("entrega") or recorrido.puntaje() != obtenido:
                        recorrido.falla("recarga", "al recargar la página no se recupera el avance (la entrega y su puntaje).")
                    try:
                        pagina.locator('[data-accion="copiar"]').first.click(timeout=ESPERA_MS)
                        pagina.wait_for_timeout(300)
                    except Exception:
                        recorrido.falla("entrega", "no encuentro el botón data-accion=\"copiar\".")
                    copiado = _texto_copiado(pagina)
                    faltan = [d for d, t in (("el nombre", "Ana Prueba"), ("el puntaje", str(obtenido)),
                                             ("las respuestas", primera_correcta)) if t and t not in copiado]
                    if faltan:
                        recorrido.falla("entrega", f"«Copiar mi entrega» no trae {', '.join(faltan)}.")
                informe.lineas.append(f"{nombre}: recorrido con todas las respuestas {respuestas}, puntaje "
                                      f"{obtenido if obtenido is not None else 'sin leer'} de {total}.")
                contexto.close()
            _teclado_y_movimiento(navegador, url, datos, informe, capturas)
        finally:
            navegador.close()
    if not informe.fallas:
        informe.lineas.append("En cada pantalla: sin errores de JavaScript, sin desborde a los costados y con controles "
                              f"de {ALTO_MINIMO} px o más. El teclado llega a «Siguiente» con el foco visible, el "
                              "movimiento reducido detiene las animaciones, la recarga recupera el avance y la copia "
                              "trae el nombre, las respuestas y el puntaje.")
    return informe


def _teclado_y_movimiento(navegador, url: str, datos: dict, informe: Informe, capturas: Path | None) -> None:
    contexto = navegador.new_context(viewport=COMPUTADORA, reduced_motion="reduce")
    contexto.route("**/*", lambda r: r.abort() if r.request.url.startswith("http") else r.continue_())
    pagina = contexto.new_page()
    recorrido = _Recorrido(pagina, datos, "Teclado y movimiento reducido", informe, capturas)
    pagina.goto(url)
    if not recorrido.visible("0"):
        recorrido.falla("inicio", "no se ve la pantalla data-paso=\"0\".")
        contexto.close()
        return
    foco = None
    for _ in range(40):
        pagina.keyboard.press("Tab")
        foco = pagina.evaluate(_FOCO)
        if foco and foco["accion"] == "siguiente":
            break
    if not foco or foco["accion"] != "siguiente":
        recorrido.falla("inicio", "con la tecla Tab no se llega al botón «Siguiente».")
    else:
        if not foco["visible"]:
            recorrido.falla("inicio", "el botón «Siguiente» no muestra el foco del teclado.")
        pagina.keyboard.press("Enter")
        if not recorrido.visible("1"):
            recorrido.falla("inicio", "Enter sobre «Siguiente» no lleva al paso 1.")
        elif pagina.evaluate(_ANIMACIONES):
            recorrido.falla("paso 1", "con movimiento reducido sigue corriendo una animación.")
    contexto.close()
