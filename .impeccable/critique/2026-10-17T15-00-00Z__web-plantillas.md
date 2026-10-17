---
target: interfaz web (web/plantillas)
total_score: 35
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 0
target_identity: "file:C:\Users\info\OneDrive - FUTURASOFT\Documentos\aulalista\web\plantillas"
timestamp: 2026-10-17T15-00-00Z
slug: web-plantillas
closed: false
---
# Critique 5: interfaz web de AulaLista después de la decisión 45

Puntaje: 35/40 (Bueno; antes 32). P0: 0. P1: 0. P2: 0. P3: 3.

Método: el mismo de las críticas 3 y 4. Revisión manual en el navegador (escritorio, celular de 375 px, modo claro y oscuro) sobre la ficha confirmada de la sesión 3 de Gestión y gobierno de datos, abriendo y cancelando secciones sin guardar. No se corrió el detector automático. No se abrieron fichas vacías.

| # | Heurística | Puntaje | Cambio | Lo que queda |
|---|---|---|---|---|
| 1 | Visibilidad del estado | 4 | = | La ficha dice el estado de cada sección en el índice y la sección abierta se marca en magenta |
| 2 | Lenguaje del mundo real | 4 | +1 | «corrida» desapareció; «pasajes», «tokens», «verificador» y «PBQ» se definen; hay ayuda |
| 3 | Control y libertad | 4 | +1 | Editar y Cancelar por sección; Cancelar devuelve lo guardado; aprobar sigue sin deshacerse |
| 4 | Consistencia | 4 | = | Ficha, tablero y material usan las mismas tarjetas, estados y botones |
| 5 | Prevención de errores | 3 | = | Una sección a la vez y aviso si quedan cambios en otra; la confirmación antes de desactualizar sigue |
| 6 | Reconocer, no recordar | 4 | = | El resumen muestra lo escrito sin abrir los campos |
| 7 | Flexibilidad y eficiencia | 3 | = | «Editar» en la fila de un ejercicio abre ese ejercicio; no hay atajos de teclado |
| 8 | Estética y minimalismo | 3 | = | La ficha bajó de 4 858 a 2 935 px y de 71 campos abiertos a ninguno; sigue en Arial |
| 9 | Recuperación de errores | 3 | = | Sin cambios |
| 10 | Ayuda | 3 | +1 | «Cómo funciona» explica el flujo y las situaciones frecuentes |

## Problemas encontrados y corregidos en esta revisión
- En el celular, el texto oculto para lectores de pantalla de las píldoras del índice ensanchaba la ficha a 866 px. Corregido: la píldora contiene su texto oculto.
- Al pulsar «Editar», el título de la sección quedaba debajo del índice fijo. Corregido con un margen de desplazamiento mayor.

## Problemas que quedan
- [P3] Sin atajos de teclado para «Lo que sigue» o para la siguiente sección. delight.
- [P3] En el resumen, las etiquetas largas («Material de referencia: una línea por archivo…») ocupan varias líneas en el celular. distill.
- [P3] La tipografía sigue en Arial por decisión del profesor (el Excel modelo usa Arial).
