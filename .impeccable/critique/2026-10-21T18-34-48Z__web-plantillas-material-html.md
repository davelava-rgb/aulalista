---
target: web/plantillas/material.html
total_score: 27
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\PROYECTOS\\aulalista\\web\\plantillas\\material.html"
target_fingerprint: "sha256:42f2242856d934cd130e1074d20fa51aca7a571772db1a13f0bbe03cdab6a8b2"
target_path: "C:\\PROYECTOS\\aulalista\\web\\plantillas\\material.html"
timestamp: 2026-10-21T18-34-48Z
slug: web-plantillas-material-html
---
# Crítica: web/plantillas/material.html

## Puntaje (Nielsen)

| # | Heurística | Nota | Problema clave |
|---|---|---|---|
| 1 | Estado del sistema | 2 | Material desactualizado: indicador rojo junto a cuatro pasos verdes y «Siguiente paso: los materiales están aprobados». |
| 2 | Lenguaje del usuario | 3 | Pendientes con etiquetas del programa («Afirmación sin fuente: …», líneas que empiezan con FALLA); fechas ISO. |
| 3 | Control y libertad | 3 | Hay Detener y confirmación al regenerar; aprobar con pendientes no pide confirmación. |
| 4 | Consistencia | 3 | El revisor muestra su tope; Generar no. «Decide si las aceptas» sugiere decisión por ítem, pero hay un solo botón. |
| 5 | Prevención de errores | 2 | Aprobar acepta N decisiones pendientes sin aviso (material.html:113-116). |
| 6 | Reconocer, no recordar | 3 | Desactualizado no dice qué cambió en la ficha. |
| 7 | Eficiencia | 2 | Sin enlace para saltar al contenido; unas 20 paradas de tabulador antes de la hoja. |
| 8 | Diseño mínimo | 3 | Limpio; el material aprobado termina en un recuadro que solo ofrece gastar otra vez. |
| 9 | Recuperación de errores | 3 | «Copia el detalle y envíalo» no dice a quién (l.44). |
| 10 | Ayuda | 3 | «Tokens» definido en su lugar; «sin ver borradores» del revisor sin explicar. |
| **Total** | | **27/40** | **Aceptable** |

## Veredicto de especificidad

Hecha para este producto. El recorrido Generar / Verificar «Sin IA» / Revisar «Con IA, por bloque» / Aprobar «Lo decides tú», la separación de «Lo que impide aprobar» y el costo junto a cada botón que gasta son propios de AulaLista. Genéricos: el recuadro de acciones final y la lista de archivos de la entrega. El problema principal no es visual: varias señales de estado se contradicen.

Detector: 3 avisos `design-system-color` (negro por defecto al leer la plantilla sin CSS; falsos positivos). En el navegador: Arial (permitido por la configuración), columna larga junto al panel fijo (esperado), dos `cramped-padding` en enlaces del panel y botones secundarios (falsos positivos: la altura sale de min-height). Coincide con la revisión: no hay problemas mecánicos de peso.

## Lo que funciona

1. Las notas del recorrido enseñan el modelo de confianza de un vistazo, con el estado también para lector de pantalla (material.html:21-22).
2. Las FALLAS van aparte, en «Lo que impide aprobar», nunca como decisiones aceptables (l.73-79).
3. El costo se ve junto a cada botón que gasta, y la actualización automática conserva el foco (l.184-217).

## Problemas prioritarios

**[P1] Un material desactualizado se ve terminado.** Lectura S1: «Desactualizada» en rojo junto a cuatro ✓ verdes (servidor.py:832-834) y «Siguiente paso: Los materiales de esta sesión están aprobados.» (servidor.py:650), aunque el panel muestra Lectura y Diapositivas en rojo. Que siga aprobado es una decisión del proyecto (servidor.py:637-639); el problema son las señales. Arreglo: el paso Aprobar con nota de cambio en rojo, no ✓; el siguiente paso dice «Aprobados; 2 están desactualizados: decide si los generas de nuevo»; el recuadro de acciones dice qué cambió y cuándo. Comando: clarify.

**[P1] Aprobar acepta los pendientes en silencio.** El botón «Aprobar la lectura» acepta todas las decisiones pendientes sin confirmación ni resumen junto al botón (material.html:109-116). Arreglo: junto al botón, «Al aprobar aceptas 4 decisiones pendientes», con enlace al Excel de verificación; título «Al aprobar, aceptas esto:». Después de aprobar, una línea de cierre con el siguiente material. Comando: clarify / harden.

**[P1] Teclado y lector de pantalla.** Sin enlace «Saltar a la hoja de trabajo»; unas 20 paradas antes del contenido y unas 28 hasta Aprobar. Al cambiar de estado durante la espera, la sección se reemplaza sin anuncio (l.205). Arreglo: enlace de salto, región role="status" que anuncie el nuevo estado. Comando: harden.

**[P2] El costo no se dice igual en todos los botones.** Generar da solo el costo anterior, sin tope; el revisor da «Tope: 2 USD». «Desde que pulsaste Generar: … USD» sigue días después y parece en vivo. Arreglo: una línea igual por botón: «Gasta tokens. Tope: X USD. La última vez: Y USD.» Comando: clarify.

**[P2] El material aprobado termina flojo.** El último recuadro solo ofrece gastar de nuevo («Generar de nuevo», «Pedir revisor»). En «No va en esta sesión», el siguiente paso queda pegado al título. Arreglo: cierre con el siguiente material como acción principal; las otras acciones plegadas. Comando: distill / layout.

## Señales por persona

- Alex (teclado, apurado): 20 paradas para llegar; la tecla S no sirve si el siguiente paso está en la misma página; puede aceptar pendientes a ciegas.
- Sam (lector de pantalla): el cambio de estado no se anuncia; el recorrido dice «(hecho)» cuatro veces en un material desactualizado. Contraste correcto.
- El profesor: «todo aprobado» con dos materiales desactualizados es el error que más teme; sin tope antes de Generar; sin enlace a los Hallazgos junto a la decisión.

## Observaciones menores

- Fechas ISO en el texto («El 2026-10-12»): mejor «12 de octubre».
- «Material 4 de 4» cuenta materiales que no van en la sesión.
- «1 aviso de diseño» contado en el resumen pero escondido en «Detalles…», cuyo título junta seis ideas.
- «Avance» sigue visible en materiales terminados.
- El párrafo de `puede_empezar=false` (l.26) no tiene estilo y repite el enlace.
- El texto «Preparando la ficha de la sesión… puede tardar unos minutos» dentro de un botón de 44px se parte mal (l.179).
- Tres vocabularios para el mismo paso: «Hecho», «Sin errores abiertos», «Con pendientes».

## Preguntas

1. ¿Debe un material desactualizado seguir «Aprobado», o volver a «Para aprobar» hasta que el profesor confirme?
2. Cada pendiente es algo que el profesor «decide». ¿Por qué el único instrumento es un botón que acepta todos?
3. ¿Qué debe ser lo último en la página de un material aprobado?
