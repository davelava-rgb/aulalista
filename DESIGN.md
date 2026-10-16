---
name: AulaLista
description: Interfaz local para preparar y validar el material de una sesión de un curso.
colors:
  magenta: "#c537a0"
  morado-marca: "#1e0253"
  gris-marca: "#e9e9e9"
  pizarra: "#1f2933"
  papel: "#ffffff"
  niebla: "#f2f4f5"
  verde-aprobado: "#1e6b3a"
  rojo-correccion: "#a3261f"
  magenta-noche: "#cd53ad"
  pizarra-noche: "#e4e7ea"
  papel-noche: "#14181b"
  niebla-noche: "#1f2529"
  verde-aprobado-noche: "#7fd19b"
  rojo-correccion-noche: "#f08c84"
typography:
  headline:
    fontFamily: "Arial, sans-serif"
    fontSize: "2.25rem"
    lineHeight: 1.2
  title:
    fontFamily: "Arial, sans-serif"
    fontSize: "1.5rem"
    lineHeight: 1.2
  body:
    fontFamily: "Arial, sans-serif"
    fontSize: "1rem"
    lineHeight: 1.5
  label:
    fontFamily: "Arial, sans-serif"
    fontSize: "0.875rem"
    lineHeight: 1.5
rounded:
  md: "6px"
  pill: "999px"
spacing:
  xs: "0.25rem"
  sm: "0.5rem"
  md: "1rem"
  lg: "2rem"
components:
  button-primary:
    backgroundColor: "{colors.magenta}"
    textColor: "{colors.papel}"
    rounded: "{rounded.md}"
    padding: "0 1.25rem"
    height: "44px"
  button-secondary:
    backgroundColor: "{colors.papel}"
    textColor: "{colors.magenta}"
    rounded: "{rounded.md}"
    padding: "0 1.25rem"
    height: "44px"
  input-text:
    backgroundColor: "{colors.papel}"
    textColor: "{colors.pizarra}"
    rounded: "{rounded.md}"
    padding: "0.5rem 0.75rem"
    height: "44px"
  chip-marca:
    textColor: "{colors.pizarra}"
    rounded: "{rounded.pill}"
    padding: "0.1rem 0.5rem"
  table-header:
    backgroundColor: "{colors.magenta}"
    textColor: "{colors.papel}"
    padding: "0.5rem"
  card-material:
    backgroundColor: "{colors.papel}"
    rounded: "{rounded.md}"
    padding: "0.5rem 1rem 1rem"
---

# Design System: AulaLista

## Overview

**Creative North Star: "El cuaderno del profesor"**

AulaLista se ve como un cuaderno de trabajo ordenado: hojas blancas, tinta oscura, un solo color para lo que se puede tocar y anotaciones al margen que dicen de dónde salió cada dato. Nada compite por la atención; lo importante es el texto y el estado de cada material.

La densidad es media y la lectura va de arriba abajo, en una sola columna de 64rem como máximo. No hay sombras, imágenes ni adornos. La jerarquía sale del tamaño del título, del color magenta y de recuadros con borde fino.

La interfaz lleva la marca FuturaSoft (logo y paleta oficiales entregados el 2026-10-15): una cabecera morada con el logo y el magenta como único color de acción. La estructura del cuaderno se mantiene.

**Key Characteristics:**
- Una sola columna, de arriba abajo, con un paso del flujo por sección.
- Un solo color de acción (magenta) más dos colores de estado (verde y rojo).
- Recuadros planos con borde fino; sin sombras.
- Anotaciones pequeñas de procedencia y costo junto a cada campo o acción.
- Modo claro y oscuro con los mismos papeles de color.

## Colors

Paleta sobria de tinta sobre papel, con un acento frío y dos colores que solo hablan de estado.

### Primary
- **Magenta FuturaSoft** (`magenta`, #C537A0; de noche `magenta-noche`, #CD53AD): títulos h1 y h2, enlaces, botón principal, encabezado de las tablas de datos y borde de los recuadros de material. Es el único color que indica "se puede tocar". Contraste: 4.7:1 sobre papel; el de noche, 4.6:1 sobre papel-noche.

### Marca
- **Morado FuturaSoft** (`morado-marca`, #1E0253) con **gris de marca** (`gris-marca`, #E9E9E9): solo la cabecera con el logo, igual en los dos modos. Nunca en botones ni estados.
- **Logo:** `web/estaticos/marca/futurasoft-logo.png` (fondo transparente, para fondo oscuro), 44px de alto en la cabecera. Icono: `futurasoft-icono.png`.

### Neutral
- **Pizarra** (`pizarra`; de noche `pizarra-noche`): todo el texto, bordes de los campos y anillo de foco de los botones.
- **Papel** (`papel`; de noche `papel-noche`): fondo de la página, de los campos y del botón secundario.
- **Niebla** (`niebla`; de noche `niebla-noche`): fondo de mensajes, filas pares de las tablas y borde de los bloques plegables.

### Estados
- **Verde aprobado** (`verde-aprobado`): solo para "confirmada" y resultados correctos.
- **Rojo corrección** (`rojo-correccion`): solo para fallas, "Falta definir", conflictos entre versiones y fichas pendientes.

### Named Rules
**La regla de un solo acento.** El magenta es el único color de acción. Verde y rojo solo describen estados; nunca se usan para decorar ni para botones.

**La regla del color con palabra.** Un estado nunca se comunica solo con color: siempre va con su texto ("Confirmada", "Con fallas").

## Typography

**Body Font:** Arial (con sans-serif)

**Character:** Una sola familia, neutra y legible, la misma del Excel modelo de verificación. La jerarquía sale del tamaño y del color, no de cambiar de fuente.

### Hierarchy
- **Headline** (normal, 2.25rem, 1.2): el h1 de cada página, en magenta.
- **Title** (normal, 1.5rem, 1.2): el h2 de cada sección del flujo o material, en magenta.
- **Body** (normal, 1rem, 1.5): texto, campos y botones. Las tablas de datos bajan a 0.9375rem.
- **Label** (normal, 0.875rem a 0.8125rem, 1.5): notas, ayudas, marcas de procedencia, ruta de navegación y avance. Las notas bajan su opacidad a 0.8.

### Named Rules
**La regla de la etiqueta en negrita.** El nombre de cada campo va en negrita sobre el campo; la ayuda va debajo, más pequeña.

## Layout

Una columna centrada de 64rem como máximo, con 2rem de margen arriba y abajo y 1rem a los lados. Las secciones se separan 2rem y los campos 1rem. Las filas de controles usan flex con salto de línea y huecos de 0.5rem a 0.75rem.

Las casillas y las paletas usan una rejilla automática de columnas de 13rem a 14rem como mínimo. La barra de acciones de la ficha queda fija al pie de la pantalla, sobre fondo papel. Bajo 40rem, las celdas de ubicación de las tablas pueden partir línea.

## Elevation & Depth

Plana por completo: no hay sombras. La profundidad se marca con bordes finos de 1px (magenta en los recuadros de material y de preguntas, niebla en los bloques plegables, rojo en los conflictos) y con el fondo niebla en mensajes y filas pares.

### Named Rules
**La regla de la hoja plana.** Ningún elemento flota. Si algo necesita destacarse, cambia su borde o su fondo, nunca su sombra.

## Shapes

Esquinas suavemente redondeadas de 6px en botones, campos, mensajes y recuadros. Las marcas de procedencia son píldoras de borde fino (999px). Los cuadros de color de las paletas son rectángulos sin redondeo. Las secciones de "completar" se separan con una línea discontinua.

## Components

### Buttons
- **Shape:** esquinas de 6px, 44px de alto como mínimo.
- **Primary:** fondo magenta, texto papel, 1rem, relleno lateral de 1.25rem.
- **Secondary:** fondo papel, texto y borde magenta de 1px.
- **Focus:** anillo de 3px en pizarra, separado 2px.
- **Disabled:** opacidad 0.6 y cursor bloqueado; siempre con una nota cercana que explica qué falta.

### Chips (marcas de procedencia)
- **Style:** píldora con borde magenta de 1px, texto 0.8125rem, sin fondo.
- **State:** la variante de alerta usa borde y texto rojo corrección ("Falta definir", "Dos versiones").

### Cards / Containers
- **Recuadro de material:** borde magenta de 1px, esquinas de 6px, relleno de 0.5rem 1rem 1rem, 1.5rem de separación arriba.
- **Bloque plegable:** `details` con borde niebla y un resumen en negrita de 44px de alto.
- **Mensaje:** borde magenta, fondo niebla, relleno de 0.75rem 1rem.
- **Shadow Strategy:** ninguna (ver Elevation & Depth).

### Inputs / Fields
- **Style:** borde pizarra de 1px, fondo papel, esquinas de 6px, 44px de alto; las áreas de texto ocupan todo el ancho.
- **Focus:** anillo de 3px en magenta, separado 2px.
- **Error:** el borde pasa a rojo corrección cuando el campo está en "Falta definir" o en conflicto.

### Navigation
- **Ruta:** una línea de 0.875rem sobre el título ("AulaLista › curso › sesión"), con enlaces en magenta. No hay menú lateral ni pestañas.
- **Alternador de modo:** botón secundario a la derecha de la ruta ("Cambiar a modo claro" o "Cambiar a modo oscuro"). Sin elección guardada, la interfaz sigue el modo de Windows; la elección se guarda en el navegador.

### Tabla de datos
- **Style:** ancho completo, encabezado con fondo magenta y texto papel en negrita, filas pares en niebla, celdas con relleno de 0.5rem y alineadas arriba. Las filas leídas por IA van en cursiva.

## Do's and Don'ts

### Do:
- **Do** usar el magenta solo para lo que se puede tocar: enlaces, botones y encabezados de tabla.
- **Do** poner junto a cada acción bloqueada una nota que diga qué falta.
- **Do** acompañar cada color de estado con su palabra.
- **Do** mantener 44px de alto en todo control que se pueda tocar.
- **Do** definir cada color nuevo en `:root` y en su versión de noche.

### Don't:
- **Don't** agregar sombras, degradados ni imágenes decorativas.
- **Don't** usar verde o rojo en botones o adornos; solo describen estados.
- **Don't** cambiar Arial por otra fuente mientras el Excel modelo use Arial.
- **Don't** usar el morado de la marca fuera de la cabecera, ni otro logo que el de `web/estaticos/marca/`.
- **Don't** usar emojis ni lenguaje publicitario.
