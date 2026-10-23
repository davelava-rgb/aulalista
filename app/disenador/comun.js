// Código común fijo del diseñador de diapositivas (PLAN.md §0, decisión 68 d).
//
// Lo escribe AulaLista una vez. El agente diseñador escribe solo el código de cada diapositiva y usa estas ayudas
// con «A». Así escribe menos, tarda menos y la caché de su guía se lee en vez de escribirse otra vez.
// AulaLista lo pega dentro de «module.exports = async (h) => { ... }», antes de las diapositivas: «h» ya existe.
// No usa nada fuera de «h»: ni archivos, ni red, ni módulos.
const A = (() => {
  const C = h.colores, F = h.fuente, MIN = h.minimo;
  const W = h.ancho, H = h.alto, M = 0.5;
  const base = (o) => {
    const { fontSize, ...resto } = o;
    return { fontSize: Math.max(MIN, fontSize || 16), color: C.texto, isTextBox: true, valign: "top", ...resto, fontFace: F };
  };
  const texto = (s, t, x, y, w, alto, o = {}) => s.addText(t, { x, y, w, h: alto, ...base(o) });
  const lineas = (items) => items.map((p) => ({ text: p, options: { breakLine: true } }));
  const vinetas = (items) => items.map((p) => ({ text: p, options: { bullet: true, breakLine: true } }));
  const rect = (s, x, y, w, alto, color, o = {}) =>
    s.addShape(h.pres.shapes.RECTANGLE, { x, y, w, h: alto, fill: { color }, line: { color, width: 0 }, ...o });
  const redondo = (s, x, y, w, alto, color, o = {}) =>
    s.addShape(h.pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: alto, rectRadius: 0.08, fill: { color }, line: { color, width: 0 }, ...o });
  const icono = async (s, nombre, x, y, tam = 0.6, color = C.principal) =>
    s.addImage({ data: await h.icono(nombre, color), x, y, w: tam, h: tam });
  const pie = (s, numero) =>
    texto(s, `${h.portada.curso}  ·  ${h.portada.sesion}` + (numero ? `  ·  ${numero}` : ""), M, H - 0.45, W - 2 * M, 0.3,
          { fontSize: MIN, transparency: 40 });
  const etiqueta = (s, t, x, y, w = 2.2, color = C.acento) => {
    redondo(s, x, y, w, 0.34, color);
    texto(s, t, x, y, w, 0.34, { fontSize: MIN, color: C.blanco, bold: true, align: "center", valign: "middle", margin: 0 });
  };
  const titulo = (s, t, bloque, numero) => {
    if (bloque) etiqueta(s, bloque, M, 0.35, Math.min(6, 0.11 * bloque.length + 0.8));
    const y = bloque ? 0.8 : 0.5;
    texto(s, t, M, y, W - 2 * M, 1.0, { fontSize: 30, bold: true, color: C.principal, valign: "middle" });
    rect(s, M, y + 1.05, 1.2, 0.07, C.acento);
    if (numero) pie(s, numero);
    return y + 1.3;
  };
  const tarjetas = async (s, items, y = 2.1, alto = 4.4, iconos = []) => {
    const n = items.length, gap = 0.3, w = (W - 2 * M - gap * (n - 1)) / n;
    for (let i = 0; i < n; i++) {
      const x = M + i * (w + gap);
      redondo(s, x, y, w, alto, C.fondo);
      rect(s, x, y, w, 0.12, C.acento);
      let ty = y + 0.35;
      if (iconos[i]) { await icono(s, iconos[i], x + 0.3, ty, 0.6); ty += 0.8; }
      texto(s, items[i].texto, x + 0.3, ty, w - 0.6, 0.8, { fontSize: 20, bold: true, color: C.principal });
      if (items[i].detalle) texto(s, items[i].detalle, x + 0.3, ty + 0.9, w - 0.6, alto - (ty - y) - 1.1, { fontSize: 16 });
    }
  };
  const columnas = (s, izq, der, y = 2.1, alto = 4.4, vs = "vs") => {
    const w = (W - 2 * M - 1.0) / 2;
    [[izq, M], [der, M + w + 1.0]].forEach(([col, x]) => {
      redondo(s, x, y, w, alto, C.fondo);
      texto(s, col.titulo, x + 0.3, y + 0.25, w - 0.6, 0.7, { fontSize: 22, bold: true, color: C.principal });
      texto(s, lineas(col.frases), x + 0.3, y + 1.1, w - 0.6, alto - 1.4, { fontSize: 18 });
    });
    if (vs) {
      redondo(s, W / 2 - 0.4, y + alto / 2 - 0.4, 0.8, 0.8, C.acento);
      texto(s, vs, W / 2 - 0.4, y + alto / 2 - 0.4, 0.8, 0.8,
            { fontSize: 18, bold: true, color: C.blanco, align: "center", valign: "middle", margin: 0 });
    }
  };
  const pasos = (s, items, y = 2.1, alto = 4.4) => {
    const n = items.length, gap = 0.25, w = (W - 2 * M - gap * (n - 1)) / n;
    items.forEach((p, i) => {
      const x = M + i * (w + gap);
      redondo(s, x, y, 0.6, 0.6, C.principal);
      texto(s, String(i + 1), x, y, 0.6, 0.6, { fontSize: 18, bold: true, color: C.blanco, align: "center", valign: "middle", margin: 0 });
      texto(s, p, x, y + 0.8, w, alto - 0.8, { fontSize: 18 });
      if (i < n - 1) texto(s, "›", x + w - 0.05, y + 0.05, 0.3, 0.5, { fontSize: 28, bold: true, color: C.acento, margin: 0 });
    });
  };
  const frases = (s, items, y = 2.1, alto = 4.4, tam = 22) => {
    const una = items.length === 1;
    return texto(s, una ? items[0] : vinetas(items), M + 0.2, y, W - 2 * M - 0.4, alto,
                 { fontSize: una ? 32 : tam, bold: una, color: una ? C.principal : C.texto, valign: una ? "middle" : "top",
                   paraSpaceAfter: 10 });
  };
  const cita = (s, t, y = 2.1, alto = 4.4) => {
    rect(s, M, y, W - 2 * M, alto, C.principal);
    texto(s, t, M + 0.6, y + 0.3, W - 2 * M - 1.2, alto - 0.6, { fontSize: 30, bold: true, color: C.blanco, valign: "middle" });
  };
  const tabla = (s, t, y = 2.1, alto = 4.4) => {
    const filas = [
      t.encabezados.map((e) => ({ text: e, options: { bold: true, color: C.blanco, fill: { color: C.principal } } })),
      ...t.filas.map((f, i) => f.map((c) => ({ text: c, options: { fill: { color: i % 2 ? C.gris : C.blanco } } }))),
    ];
    s.addTable(filas, { x: M, y, w: W - 2 * M, fontFace: F, fontSize: Math.max(MIN, 16), color: C.texto,
                        border: { type: "solid", color: C.gris, pt: 0.5 }, rowH: Math.min(0.6, alto / filas.length) });
  };
  const docente = (s, y) =>
    texto(s, lineas([h.portada.docente, ...h.portada.contacto].filter(Boolean)), M, y, W - 2 * M, 1.4,
          { fontSize: 16, color: C.blanco });
  const portada = async (s) => {
    s.background = { color: C.principal };
    rect(s, M, 2.35, 1.6, 0.09, C.acento);
    texto(s, h.portada.curso, M, 0.9, W - 2 * M - 2.5, 1.4, { fontSize: 40, bold: true, color: C.blanco, valign: "bottom" });
    texto(s, h.portada.sesion, M, 2.6, W - 2 * M - 2.5, 0.9, { fontSize: 26, color: C.blanco });
    texto(s, h.portada.material, M, 3.5, W - 2 * M - 2.5, 0.6, { fontSize: 18, color: C.blanco, transparency: 30 });
    docente(s, H - 2.0);
    if (h.logo) s.addImage({ path: h.logo, x: W - M - 2.0, y: 0.7, w: 2.0, h: 1.2, sizing: { type: "contain", w: 2.0, h: 1.2 } });
  };
  const cierre = (s) => {
    s.background = { color: C.principal };
    etiqueta(s, "La idea que te llevas", M, 0.8, 3.4);
    texto(s, h.contenido.cierre.frase, M, 1.5, W - 2 * M, 3.6, { fontSize: 36, bold: true, color: C.blanco, valign: "middle" });
    rect(s, M, 5.25, 1.6, 0.09, C.acento);
    docente(s, H - 2.0);
  };
  return Object.freeze({ texto, lineas, vinetas, rect, redondo, icono, pie, etiqueta, titulo, tarjetas, columnas, pasos,
                         frases, cita, tabla, portada, cierre, W, H, M });
})();
