"""Agente diseñador: el programa pptxgenjs se revisa, corre con Node y su PowerPoint se controla (decisión 32)."""

import pytest
from pptx import Presentation

from app.materiales import disenador, estilo
from app.materiales.contenido import Diapositivas
from app.materiales.docx import Portada
from tests.unidad.test_diapositivas import LIMPIAS

pytestmark = pytest.mark.skipif(not disenador.disponible(), reason="Node o los paquetes del diseñador no están instalados")

IDENTIDAD = estilo.Identidad(**estilo.PALETA_SOBRIA, tipografia="Calibri", logo=None)
PORTADA = Portada("Scrum Master con IA", "Sesión 1 · Fundamentos", "Diapositivas", docente="José Fernando Davelouis Mendía",
                  contacto="www.linkedin.com/in/jdavelouis; info@futurasoft.net")

# Un diseño simple, escrito a mano, como el que devolvería el agente: una diapositiva por parte, con íconos.
DISENO = r"""
module.exports = async (h) => {
  const C = h.colores, c = h.contenido;
  const texto = (s, t, x, y, w, alto, o = {}) => s.addText(t, { x, y, w, h: alto, fontFace: h.fuente, fontSize: 16,
    color: C.texto, isTextBox: true, valign: "top", ...o });
  const notas = (s, n) => s.addNotes(`Qué destacar: ${n.destacar}\nQué preguntar al grupo: ${n.preguntar}`);
  const icono = await h.icono("FaDatabase", C.blanco);

  let s = h.pres.addSlide();
  s.background = { color: C.principal };
  texto(s, h.portada.curso, 0.5, 1.5, 6, 1, { fontSize: 36, bold: true, color: C.blanco });
  texto(s, h.portada.sesion, 0.5, 2.6, 6, 0.6, { color: C.blanco });
  s.addImage({ data: icono, x: 7.5, y: 1.8, w: 1.2, h: 1.2 });
  notas(s, c.portada.notas);

  s = h.pres.addSlide();
  texto(s, "Idea central", 0.5, 0.4, 9, 0.6, { fontSize: 24, bold: true, color: C.principal });
  texto(s, c.idea_central.frases.join(" "), 0.5, 1.4, 9, 2);
  notas(s, c.idea_central.notas);

  for (const [i, d] of c.diapositivas.entries()) {
    s = h.pres.addSlide();
    s.addShape(h.pres.shapes.ROUNDED_RECTANGLE, { x: 0.5, y: 0.2, w: 1.4, h: 0.3, rectRadius: 0.1, fill: { color: C.acento } });
    texto(s, `${i + 1} · Bloque`, 0.5, 0.2, 1.4, 0.3, { fontSize: 12, color: C.blanco, margin: 0 });
    texto(s, d.titulo, 0.5, 0.6, 9, 0.7, { fontSize: 24, bold: true, color: C.principal });
    const partes = [...d.frases, ...d.columnas.flatMap((x) => [x.titulo, ...x.frases]),
                    ...(d.grafico ? d.grafico.elementos.map((e) => e.texto) : [])];
    texto(s, partes.map((p) => ({ text: p, options: { breakLine: true } })), 0.5, 1.5, 9, 3.5);
    notas(s, d.notas);
  }
  for (const [titulo, parte, lineas] of [["Aplícalo así", c.aplicalo, c.aplicalo.plantilla],
                                          ["Cuidado con", c.cuidado, c.cuidado.riesgos]]) {
    s = h.pres.addSlide();
    texto(s, titulo, 0.5, 0.4, 9, 0.7, { fontSize: 24, bold: true, color: C.principal });
    texto(s, lineas.map((p) => ({ text: p, options: { breakLine: true } })), 0.5, 1.4, 9, 3);
    notas(s, parte.notas);
  }
  s = h.pres.addSlide();
  texto(s, c.cierre.frase, 0.5, 1.5, 9, 1.5, { fontSize: 28, bold: true, color: C.principal });
  notas(s, c.cierre.notas);
};
"""


@pytest.fixture
def contenido():
    return Diapositivas.model_validate(LIMPIAS)


def correr(tmp_path, contenido, codigo=DISENO):
    datos = disenador.datos(contenido, IDENTIDAD, PORTADA, tmp_path)
    salida = tmp_path / "S1_Diapositivas.pptx"
    return disenador.correr(codigo, datos, tmp_path / "diseno", salida), salida


def test_el_diseno_corre_con_node_y_cumple_los_controles(tmp_path, contenido):
    corrida, salida = correr(tmp_path, contenido)
    assert corrida.ok, corrida.error
    assert corrida.iconos == ("FaDatabase",)
    assert len(Presentation(salida).slides) == contenido.total
    assert disenador.revisar_pptx(salida, contenido, PORTADA, IDENTIDAD) == []


def test_un_programa_con_require_o_process_se_rechaza_antes_de_correr():
    problemas = disenador.revisar_codigo('const fs = require("fs");\nmodule.exports = async (h) => { process.exit(0); };')
    assert any("require" in p and "process" in p for p in problemas)
    assert disenador.revisar_codigo("async function f(h) {}") != []


def test_node_no_deja_escribir_fuera_de_la_carpeta(tmp_path, contenido):
    """Aunque un programa se saltara la revisión, Node le niega los archivos fuera de su carpeta."""
    fuera = tmp_path.parent / "fuera_del_material.txt"
    codigo = ('module.exports = async (h) => { const m = h.pres.constructor.constructor("return this")().process;'
              f' m.mainModule.require("fs").writeFileSync({str(fuera)!r}, "x"); }};')
    corrida, _ = correr(tmp_path, contenido, codigo)
    assert not corrida.ok and not fuera.exists()
    assert "ERR_ACCESS_DENIED" in corrida.error or "restricted" in corrida.error, corrida.error


def test_un_error_del_programa_vuelve_como_problema(tmp_path, contenido):
    corrida, _ = correr(tmp_path, contenido, 'module.exports = async (h) => { await h.icono("FaNoExiste", "000000"); };')
    assert not corrida.ok and "No existe el ícono «FaNoExiste»" in corrida.error


def test_los_controles_detectan_texto_ajeno_letra_chica_colores_y_cantidad(tmp_path, contenido):
    malo = (DISENO
            .replace('texto(s, h.portada.sesion, 0.5, 2.6, 6, 0.6, { color: C.blanco });',
                     'texto(s, "Scrum nació en Japón en 1986 y lo usan todas las empresas.", 0.5, 2.6, 6, 0.6, '
                     '{ color: "00FF00", fontSize: 9 });')
            .replace("  s = h.pres.addSlide();\n  texto(s, c.cierre.frase", "  s = h.pres.addSlide();\n  s = h.pres.addSlide();\n  texto(s, c.cierre.frase"))
    corrida, salida = correr(tmp_path, contenido, malo)
    assert corrida.ok, corrida.error
    problemas = " ".join(disenador.revisar_pptx(salida, contenido, PORTADA, IDENTIDAD))
    assert "no está tal cual en el contenido aprobado" in problemas
    assert "letra de 9" in problemas
    assert "00FF00" in problemas
    assert f"deben ser {contenido.total}" in problemas
