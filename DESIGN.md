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
  borde: "#d5dade"
  verde-aprobado: "#1e6b3a"
  rojo-correccion: "#a3261f"
  magenta-noche: "#cd53ad"
  pizarra-noche: "#e4e7ea"
  papel-noche: "#14181b"
  niebla-noche: "#1f2529"
  borde-noche: "#333b41"
  verde-aprobado-noche: "#7fd19b"
  rojo-correccion-noche: "#f08c84"
  magenta-suave: "#f8e6f3"
  magenta-texto: "#9c2a7f"
  verde-suave: "#e6f2ea"
  rojo-suave: "#fbeceb"
  magenta-suave-noche: "#3a1d33"
  magenta-texto-noche: "#e07cc4"
  verde-suave-noche: "#1b3324"
  rojo-suave-noche: "#3d1f1d"
typography:
  headline:
    fontFamily: "Arial, sans-serif"
    fontWeight: "bold"
    fontSize: "1.75rem"
    lineHeight: 1.2
  title:
    fontFamily: "Arial, sans-serif"
    fontWeight: "bold"
    fontSize: "1.25rem"
    lineHeight: 1.3
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

La densidad es media. Dentro de un curso, la pantalla se divide en dos: a la izquierda, el panel del curso, como el índice del cuaderno; a la derecha, la hoja de trabajo, que se lee de arriba abajo. Cada material se trabaja en su propia hoja, uno a la vez (`PLAN.md` §0, decisión 38). No hay sombras, imágenes ni adornos. La jerarquía sale del tamaño y del peso del título y de recuadros con borde fino.

La interfaz lleva la marca FuturaSoft (logo y paleta oficiales entregados el 2026-10-15): una cabecera morada con el logo y el magenta como único color de acción. La estructura del cuaderno se mantiene.

**Key Characteristics:**
- Panel del curso a la izquierda y una hoja de trabajo a la derecha, de arriba abajo.
- Un material por hoja, con su recorrido: Generar, Verificar, Revisar y Aprobar.
- Un solo color de acción (magenta) más dos colores de estado (verde y rojo).
- Recuadros planos con borde fino; sin sombras.
- Anotaciones pequeñas de procedencia y costo junto a cada campo o acción.
- Modo claro y oscuro con los mismos papeles de color.

## Colors

Paleta sobria de tinta sobre papel, con el magenta de FuturaSoft como acento y dos colores que solo hablan de estado.

### Primary
- **Magenta FuturaSoft** (`magenta`, #C537A0; de noche `magenta-noche`, #CD53AD): enlaces, botón principal, encabezado de las tablas de datos, el paso actual del recorrido y la marca del elemento actual en el panel. Es el único color que indica "se puede tocar" o "estás aquí". Los títulos no van en magenta. Contraste: 4.7:1 sobre papel; el de noche, 4.6:1 sobre papel-noche.
- **Magenta suave** (`magenta-suave`; de noche `magenta-suave-noche`): solo el fondo de la caja «Lo que sigue» del tablero.
- **Magenta para texto** (`magenta-texto`; de noche `magenta-texto-noche`): el texto magenta sobre un fondo de color (magenta suave o niebla), donde el magenta normal no llega a 4.5:1.

### Marca
- **Morado FuturaSoft** (`morado-marca`, #1E0253) con **gris de marca** (`gris-marca`, #E9E9E9): solo la cabecera con el logo, igual en los dos modos. Nunca en botones ni estados.
- **Logo:** `web/estaticos/marca/futurasoft-logo.png` (fondo transparente, para fondo oscuro), 36px de alto en una cabecera de 56px. Icono: `futurasoft-icono.png`.

### Neutral
- **Pizarra** (`pizarra`; de noche `pizarra-noche`): todo el texto, los títulos h1 y h2 en negrita, bordes de los campos y anillo de foco de los botones.
- **Papel** (`papel`; de noche `papel-noche`): fondo de la página, de los campos y del botón secundario.
- **Borde** (`borde`; de noche `borde-noche`): las líneas finas del panel del curso: su borde derecho y la separación entre grupos.
- **Niebla** (`niebla`; de noche `niebla-noche`): fondo del panel del curso, de mensajes y de las filas pares de las tablas, y borde de los bloques plegables.

### Estados
- **Verde aprobado** (`verde-aprobado`): solo para "confirmada" y resultados correctos.
- **Verde suave y rojo suave** (`verde-suave`, `rojo-suave`; con su versión de noche): fondos de las fichas de material del tablero según su estado. Siempre con la palabra del estado encima.
- **Rojo corrección** (`rojo-correccion`): solo para fallas, "Falta definir", conflictos entre versiones y fichas pendientes.

### Named Rules
**La regla de un solo acento.** El magenta es el único color de acción. Verde y rojo solo describen estados; nunca se usan para decorar ni para botones.

**La regla del color con palabra.** Un estado nunca se comunica solo con color: siempre va con su texto ("Confirmada", "Con fallas").

## Typography

**Body Font:** Arial (con sans-serif)

**Character:** Una sola familia, neutra y legible, la misma del Excel modelo de verificación. La jerarquía sale del tamaño y del color, no de cambiar de fuente.

### Hierarchy
- **Headline** (negrita, 1.75rem, 1.2): el h1 de cada página, en pizarra.
- **Title** (negrita, 1.125rem a 1.25rem, 1.3): el h2 de cada sección, en pizarra.
- **Body** (normal, 1rem, 1.5): texto, campos y botones. Las tablas de datos bajan a 0.9375rem.
- **Label** (normal, 0.875rem a 0.8125rem, 1.5): notas, ayudas, marcas de procedencia, la línea de ubicación sobre el título y avance. Las notas bajan su opacidad a 0.8.

### Named Rules
**La regla de la etiqueta en negrita.** El nombre de cada campo va en negrita sobre el campo; la ayuda va debajo, más pequeña.

## Layout

Fuera de un curso (la página de inicio), una columna centrada de 64rem como máximo. Dentro de un curso, una rejilla de dos columnas: el panel del curso de 17.5rem, fijo a la izquierda con fondo niebla y borde derecho fino, y la hoja de trabajo, de 50rem como máximo, con 2rem de margen arriba y 2.5rem a los lados. Bajo 52rem, el panel pasa arriba y muestra solo la sesión actual como una franja que se desliza de lado. Las secciones se separan 2rem y los campos 1rem. Las filas de controles usan flex con salto de línea y huecos de 0.5rem a 0.75rem.

Las casillas y las paletas usan una rejilla automática de columnas de 13rem a 14rem como mínimo. La barra de acciones de la ficha queda fija al pie de la pantalla, sobre fondo papel. Bajo 40rem, las celdas de ubicación de las tablas pueden partir línea.

## Elevation & Depth

Plana por completo: no hay sombras. La profundidad se marca con bordes finos de 1px (magenta en los recuadros de preguntas y de acción, borde en el panel del curso, niebla en los bloques plegables, rojo en los conflictos) y con el fondo niebla en mensajes y filas pares.

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
- **Página de material:** la hoja entera es el material, sin recuadro. Arriba, la línea de ubicación, el título con su indicador y el recorrido.
- **Recorrido:** cuatro pasos en fila (Generar, Verificar, Revisar y Aprobar), unidos por una línea de 2px. Es una secuencia de verdad, por eso lleva números en círculos de 1.375rem. Hecho: círculo y línea verde aprobado con ✓. Paso actual: borde y nombre magenta. Con problema: círculo rojo corrección con «!» y nota en rojo. Pendiente: borde fino. Cada paso lleva una nota corta debajo y su estado en palabras para los lectores de pantalla. Bajo 30rem, dos pasos por fila.
- **Bloque plegable:** `details` con borde niebla y un resumen en negrita de 44px de alto.
- **Mensaje:** borde magenta, fondo niebla, relleno de 0.75rem 1rem.
- **Shadow Strategy:** ninguna (ver Elevation & Depth).

### Inputs / Fields
- **Style:** borde pizarra de 1px, fondo papel, esquinas de 6px, 44px de alto; las áreas de texto ocupan todo el ancho.
- **Focus:** anillo de 3px en magenta, separado 2px.
- **Error:** el borde pasa a rojo corrección cuando el campo está en "Falta definir" o en conflicto.

### Navigation
- **Panel del curso:** fijo a la izquierda en todas las páginas de un curso, solo con las sesiones (`PLAN.md` §0, decisión 44). Arriba, "Todos los cursos" y el nombre del curso, que lleva al tablero. Luego, cada sesión: su número, el título en una línea y sus materiales como puntos de color con su nombre (verde aprobado, rojo con problema, borde fino pendiente); el siguiente paso lleva un anillo magenta y su nombre en magenta para texto. La ficha de la sesión va como enlace dentro de la sesión abierta. El elemento actual lleva fondo papel, negrita y una barra magenta de 4px a la izquierda. Al pie, el gasto del curso, una sola vez.
- **Tablero del curso:** la página del curso. Arriba, la caja «Lo que sigue»: fondo magenta suave, borde izquierdo magenta de 6px, esquinas de 10px, un ícono en círculo, la etiqueta en magenta para texto, el paso en 1.25rem negrita, su motivo en una línea y el botón principal. Debajo, una fila por sesión con su número en un círculo niebla de 2.5rem (las sesiones son una secuencia), su título, una frase de avance y sus materiales como fichas: ícono de 2.25rem, nombre, fecha y estado en palabras. Aprobada: ícono sobre verde suave. Desactualizada o con fallas: borde y fondo rojo suave. Sin generar: borde punteado sobre niebla y la acción en magenta para texto. Al final, la preparación plegada en una línea con ✓ verde; si no está lista, va abierta y arriba.
- **Ficha:** `PLAN.md` §0, decisión 45. Confirmada, se lee primero: cada sección es una tarjeta con borde fino y esquinas de 10px, una cabecera (título h2, la fuente en nota y el botón secundario «Editar») y el resumen como lista de definiciones en dos columnas (etiqueta en nota negrita de 13rem, valor en dos líneas como máximo; vacío en cursiva «Ninguno»). El laboratorio y la evaluación muestran una tabla con una fila por ejercicio o pregunta y «Editar» en cada fila. La sección en edición lleva borde magenta de 2px y cabecera magenta suave; al pie, «Guardar esta sección», «Cancelar» y «Hay cambios sin guardar» en rojo corrección. Una sección que no se usa (la evaluación) va con borde punteado sobre niebla y plegada. El índice de arriba son píldoras con un punto de estado: verde completa, rojo con alertas, borde fino vacía, punteada y apagada si no se usa; la sección actual, con fondo magenta suave.
- **Cómo funciona:** página de ayuda enlazada desde la cabecera de todas las páginas («Cómo funciona», en gris de marca, a la izquierda del alternador de modo). Sin panel. El flujo va en cinco pasos numerados (es una secuencia): número en un círculo de 2.25rem con fondo magenta suave y texto magenta para texto, unidos por una línea vertical de 2px en borde; cada paso con su título h2 de 1.125rem y una explicación corta. Debajo, «Situaciones frecuentes» como lista de definiciones: el caso en negrita y qué hacer debajo. Cada término propio («pasajes», «tokens») se define en negrita la primera vez.
- **Ubicación:** no hay ruta de enlaces. Dentro de un curso, el panel dice dónde estás y una línea pequeña sobre el título lo repite en palabras ("Sesión 1 · Material 2 de 3", "Preparación del curso"). No hay pestañas.
- **Siguiente paso:** una línea con enlace en la página de un material, solo si el siguiente paso está en otra página. Si es el mismo material, lo dicen el recorrido y el botón.
- **Notas de costo:** una línea corta junto al botón que gasta. El total del curso va una sola vez, al pie del panel.
- **Alternador de modo:** botón secundario a la derecha de la ruta ("Cambiar a modo claro" o "Cambiar a modo oscuro"). Sin elección guardada, la interfaz sigue el modo de Windows; la elección se guarda en el navegador.

### Tabla de datos
- **Style:** ancho completo, encabezado con fondo magenta y texto papel en negrita, filas pares en niebla, celdas con relleno de 0.5rem y alineadas arriba. Las filas leídas por IA van en cursiva.

## Do's and Don'ts

### Do:
- **Do** usar el magenta solo para lo que se puede tocar y para "estás aquí": enlaces, botones, encabezados de tabla, el paso actual y el elemento actual del panel.
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
