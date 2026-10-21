// Ejecuta el diseño de las diapositivas que escribió el agente diseñador (PLAN.md §0, decisión 32).
//
// Uso: node ejecutar.js <diseno.js> <datos.json> <salida.pptx>
//
// El diseño del agente es un módulo que exporta una función asíncrona:
//     module.exports = async (h) => { ... }
// No usa require, fs ni red: todo lo que necesita está en «h». AulaLista lo revisa antes de correrlo
// y Node lo corre con permisos limitados (solo lee sus librerías y la carpeta del material, y solo
// escribe el PowerPoint).

const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");
const React = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const sharp = require("sharp");

// Colecciones de react-icons que puede usar el diseñador, por el prefijo del nombre del ícono.
const COLECCIONES = {
  Fa: ["fa", "fa6"], Md: ["md"], Lu: ["lu"], Hi: ["hi", "hi2"], Tb: ["tb"], Bi: ["bi"], Ri: ["ri"],
  Pi: ["pi"], Io: ["io5", "io"], Bs: ["bs"], Gi: ["gi"], Fi: ["fi"], Ai: ["ai"], Gr: ["gr"],
};
const cargadas = {};

function buscarIcono(nombre) {
  const prefijo = (nombre.match(/^[A-Z][a-z]+/) || [""])[0];
  for (const coleccion of COLECCIONES[prefijo] || []) {
    cargadas[coleccion] = cargadas[coleccion] || require(`react-icons/${coleccion}`);
    if (cargadas[coleccion][nombre]) return cargadas[coleccion][nombre];
  }
  return null;
}

function colorValido(color) {
  const limpio = String(color || "").replace(/^#/, "").toUpperCase();
  if (!/^[0-9A-F]{6}$/.test(limpio)) throw new Error(`Color no válido: «${color}». Usa los de h.colores.`);
  return limpio;
}

async function main() {
  const [rutaDiseno, rutaDatos, rutaSalida] = process.argv.slice(2);
  const datos = JSON.parse(fs.readFileSync(rutaDatos, "utf-8"));
  const disenar = require(path.resolve(rutaDiseno));
  if (typeof disenar !== "function") throw new Error("El diseño debe exportar una función: module.exports = async (h) => { ... }");

  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";          // 13,333 × 7,5 pulgadas: el tamaño de la versión base (decisión 56)
  pres.theme = { headFontFace: datos.tipografia, bodyFontFace: datos.tipografia };
  const iconosUsados = new Set();

  const h = Object.freeze({
    pres,
    ancho: 13.333,
    alto: 7.5,
    colores: Object.freeze({ ...datos.colores }),
    fuente: datos.tipografia,
    minimo: datos.letra_minima,
    portada: Object.freeze({ ...datos.portada }),
    logo: datos.logo || null,
    contenido: datos.contenido,
    // Ícono de react-icons («FaDatabase», «LuUsers», «MdGavel»…) como imagen PNG lista para addImage({ data }).
    async icono(nombre, color, tamano = 256) {
      const Icono = buscarIcono(String(nombre));
      if (!Icono) throw new Error(`No existe el ícono «${nombre}». Usa un nombre de react-icons con su prefijo (Fa, Lu, Md, Hi, Tb…).`);
      iconosUsados.add(nombre);
      const svg = renderToStaticMarkup(React.createElement(Icono, { color: "#" + colorValido(color), size: tamano }));
      const png = await sharp(Buffer.from(svg)).png().toBuffer();
      return "image/png;base64," + png.toString("base64");
    },
  });

  await disenar(h);
  await pres.writeFile({ fileName: rutaSalida });
  process.stdout.write(JSON.stringify({ ok: true, iconos: [...iconosUsados] }));
}

main().catch((error) => {
  process.stderr.write(String(error && error.stack ? error.stack : error));
  process.exit(1);
});
