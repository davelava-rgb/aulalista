---
target: web/plantillas/material.html
total_score: 29
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\PROYECTOS\\aulalista\\web\\plantillas\\material.html"
target_fingerprint: "sha256:9e97a5eb13d35fe59c04433c66292cf9941de83c4d136ef36afddfd1d7d12d14"
target_path: "C:\\PROYECTOS\\aulalista\\web\\plantillas\\material.html"
timestamp: 2026-10-21T21-40-08Z
slug: web-plantillas-material-html
---
# Crítica: web/plantillas/material.html (segunda pasada)

## Puntaje (Nielsen)

| # | Heurística | Nota | Problema clave |
|---|---|---|---|
| 1 | Estado del sistema | 3 | Desactualizado se ve claro arriba; la Entrega abajo muestra los archivos viejos sin aviso. |
| 2 | Lenguaje del usuario | 4 | Vocabulario del profesor; «decisiones pendientes» después de aprobar suena contradictorio. |
| 3 | Control y libertad | 3 | El laboratorio aprobado no lleva a los materiales desactualizados: el siguiente paso no tiene enlace. |
| 4 | Consistencia | 2 | Títulos magenta del mismo color que los enlaces y el paso actual (decisión 58). |
| 5 | Prevención de errores | 2 | Los archivos de un material desactualizado se descargan como si estuvieran listos. |
| 6 | Reconocer, no recordar | 3 | «2 quedaron desactualizados» sin decir cuáles. |
| 7 | Eficiencia | 3 | Enlace de salto funciona; sin atajo S cuando el siguiente paso es un material desactualizado. |
| 8 | Diseño mínimo | 3 | Desactualizado dicho de cuatro formas distintas en la misma página. |
| 9 | Recuperación de errores | 3 | Desactualizado dice qué hacer, no qué cambió en la ficha. |
| 10 | Ayuda | 3 | «Cómo funciona» y «tokens» definidos; «Revisar: Con pendientes» con ✓ verde no se explica. |
| **Total** | | **29/40** | **Bueno** (antes 27) |

## Veredicto de especificidad

Hecha para AulaLista: recorrido de cuatro pasos real, un solo botón principal, costo junto a cada botón que gasta, estado con color, ícono y palabra. Riesgo nuevo: con los títulos en magenta, el título, el paso actual y el botón principal comparten color.

Detector: 3 avisos `design-system-color` (plantilla sin CSS; falsos positivos). Navegador: Arial (permitido), `cramped-padding` en enlaces del panel y botones secundarios (falsos positivos por min-height), y un `text-overflow` real: nombres de archivo largos se salen de su caja en «Detalles de la entrega» a 280px. Títulos: 4.74:1 en claro y 4.62:1 en oscuro; pasan AA por poco.

## Lo que funciona

1. El recorrido: lista ordenada real, estado en palabras para lector de pantalla, ✓ y ! además del color.
2. El costo honesto junto a cada botón que gasta, y la confirmación antes de rehacer un material aprobado.
3. Las FALLAS separadas de las decisiones aceptables: una falla abierta nunca parece aprobable.

## Problemas prioritarios

**[P1] Un material desactualizado todavía parece entregable.** Los archivos de la Entrega (material.html:65-71) se descargan sin marca; el título dice «Aprobaste con N decisiones pendientes». PLAN.md dice que un material desactualizado no se entrega hasta validarlo otra vez. Arreglo: aviso rojo sobre la Entrega («Estos archivos siguen la ficha anterior. No los entregues sin generarlos de nuevo.») y la palabra «versión anterior» en cada archivo. Comando: harden.

**[P1] Títulos magenta compiten con «estás aquí».** En un material sin generar, el h1, el paso Generar y el botón principal son magenta en 250px. Arreglo: el paso actual del recorrido con círculo relleno magenta, para que «estás aquí» no se confunda con un título. Comando: colorize.

**[P1] El siguiente paso no nombra ni enlaza los materiales desactualizados.** servidor.py arma «2 quedaron desactualizados» sin enlace; sin atajo S y sin botón en el cierre del material aprobado. Arreglo: nombrarlos («la lectura y las diapositivas») y enlazar el primero. Comando: clarify.

**[P2] Desactualizado se dice de cuatro formas.** Indicador, nota del recorrido, siguiente paso y recuadro de acciones, con palabras distintas; en celular el recuadro queda dos pantallas abajo. Arreglo: un solo aviso bajo el recorrido, con el botón. Comando: distill.

**[P2] Nombres de archivo largos se salen de su caja.** En «Detalles de la entrega», a 280px, un ítem se sale 65px. Arreglo: `overflow-wrap: anywhere` en `.lista li`. Comando: adapt.

## Señales por persona

- Alex (teclado): las dos primeras paradas en la hoja de un material desactualizado son descargas viejas; los enlaces usan el foco por defecto del navegador.
- Sam (lector de pantalla): al cargar, nada une «Desactualizada» con los enlaces de descarga; rojo y magenta son tonos cercanos para quien no distingue rojo.
- El profesor: puede descargar archivos viejos bajo «Aprobaste»; no sabe qué cambió en la ficha para decidir si gastar otra vez.

## Observaciones menores

- La lista «Las dos fichas están confirmadas» ✓ aparece en un material desactualizado, donde justo cambió una ficha.
- «Míralos abajo» en con pendientes: las decisiones están arriba del recuadro.
- El botón de modo no cambia su texto si Windows cambia de modo con la página abierta.
- «1 aviso de diseño» por «La ficha no trae logo» suma ruido al resumen.
- Generar no muestra un tope: hace varias llamadas, cada una con su tope, así que un solo número sería inventado.

## Preguntas

1. Si un material aprobado queda desactualizado, ¿sus archivos deben seguir descargables aquí?
2. Con los títulos en magenta, ¿cuál es la señal que dice «estás aquí»?
3. ¿Puede AulaLista decir qué cambió en la ficha antes de pedir gastar otra vez?
