---
target: interfaz web (web/plantillas)
total_score: 32
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 0
target_identity: "file:C:\\Users\\info\\OneDrive - FUTURASOFT\\Documentos\\aulalista\\web\\plantillas"
timestamp: 2026-10-16T21-00-00Z
slug: web-plantillas
closed: false
---
# Critique 4: interfaz web de AulaLista después de la decisión 44

Puntaje: 32/40 (Bueno; antes 30). P0: 0. P1: 0. P2: 2. P3: 3.

Método: el mismo de la crítica 3. Revisión manual de las plantillas y de las páginas en el navegador (escritorio, celular de 375 px, modo claro y oscuro) y cálculo del contraste de cada par de colores con la fórmula WCAG. No se corrió el detector automático de impeccable. No se abrieron fichas vacías, porque abrirlas lanza una propuesta pagada.

| # | Heurística | Puntaje | Cambio | Lo que queda |
|---|---|---|---|---|
| 1 | Visibilidad del estado | 4 | = | Tablero con «Lo que sigue», fichas de material por estado, puntos en el panel, barra por curso en el inicio |
| 2 | Lenguaje del mundo real | 3 | = | «corrida» y «pasajes» siguen sin definir; «tokens», «verificador» y «PBQ» ya se definen |
| 3 | Control y libertad | 3 | = | Reanudar desde lo guardado; aprobar no se puede deshacer |
| 4 | Consistencia | 4 | +1 | Un solo nombre del curso, una sola forma de navegar, los mismos estados en inicio, tablero, panel y material |
| 5 | Prevención de errores | 3 | = | «Convertir» solo con algo por convertir; el inicio cierra solo la versión vieja si no trabaja |
| 6 | Reconocer, no recordar | 4 | = | El paso que sigue está a la vista en tres lugares, con su motivo |
| 7 | Flexibilidad y eficiencia | 3 | +1 | Del inicio y del tablero se llega en un clic al paso pendiente; no hay atajos de teclado |
| 8 | Estética y minimalismo | 3 | = | Más visual y ordenado; la ficha sigue larga y en Arial |
| 9 | Recuperación de errores | 3 | = | Errores con qué hacer y detalle plegado; el material desactualizado repite el aviso dos veces |
| 10 | Ayuda | 2 | = | No hay un lugar que explique el flujo completo |

## Contraste
Los 32 pares de colores de los dos modos pasan 4.5:1. El más bajo es el magenta sobre papel de noche (4.62). El texto con opacidad (números del panel, notas, motivo) queda en 5.3:1 o más.

## Problemas que quedan
- [P2] «corrida» y «pasajes» aparecen sin definir. clarify.
- [P2] No hay ayuda del flujo completo (fuentes, fichas, materiales, verificación y aprobación). clarify.
- [P3] La página de la ficha sigue siendo larga; es la pantalla que más tiempo usa el profesor. distill.
- [P3] En un material desactualizado, el recorrido y la frase roja dicen lo mismo. distill.
- [P3] Sin atajos de teclado para ir al paso que sigue. delight.

## Lo que mejoró desde la crítica 3
- La página del curso pasó de trámite a tablero: lo que sigue con motivo, costo y botón; sesiones con fichas por estado.
- El panel quedó solo con las sesiones y ya no repite la página.
- La página de inicio muestra el avance de cada curso y enlaza lo que sigue.
