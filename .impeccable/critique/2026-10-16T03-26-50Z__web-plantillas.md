---
target: interfaz web (web/plantillas)
total_score: 22
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Users\\info\\OneDrive - FUTURASOFT\\Documentos\\aulalista\\web\\plantillas"
timestamp: 2026-10-16T03-26-50Z
slug: web-plantillas
closed: true
---
# Critique: interfaz web de AulaLista (web/plantillas)

Puntaje: 22/40 (Aceptable). P0: 0. P1: 3. P2: 2.

| # | Heurística | Puntaje | Problema principal |
|---|---|---|---|
| 1 | Visibilidad del estado | 2 | Tabla del curso sin estado de materiales; recarga completa cada 5 s mientras trabaja (sesion.html:102-104, ficha.html:212-214) |
| 2 | Lenguaje del mundo real | 3 | "Pasajes", "tokens", "decisión 32" sin definir |
| 3 | Control y libertad | 2 | "Generar de nuevo" sobre material aprobado sin confirmación (sesion.html:81-86) |
| 4 | Consistencia | 2 | Laboratorio aparece "Aprobada" (sesion.html:18; MATERIALES sin género) |
| 5 | Prevención de errores | 2 | Guardar ficha confirmada desactualiza materiales sin aviso previo |
| 6 | Reconocer, no recordar | 2 | Ficha de sesión: 72 campos sin índice; "las fichas cambiaron" sin decir qué |
| 7 | Flexibilidad y eficiencia | 1 | Sin salto a material ni "siguiente paso"; todo recarga la página |
| 8 | Estética y minimalismo | 2 | Sesión de 6 241 px; entrega siempre abierta |
| 9 | Recuperación de errores | 3 | "Para confirmarla falta" enlaza cada campo |
| 10 | Ayuda | 3 | Notas en línea claras pero largas |

## Especificidad
Texto propio del producto (entrega, procedencia de la ficha). Visual intercambiable: Arial, un solo azul verdoso, todo con el mismo recuadro. Sin marca FuturaSoft. El estado de validación no tiene forma visual.

Detector: CLI 0 hallazgos en plantillas. Navegador (modo oscuro): ai-color-palette en todo lo que usa --principal #6fb3c4; ~70 line-length (texto a 977 px, sin max-width); cramped-padding y overused-font son falsos positivos.

## Problemas prioritarios
- [P1] Acciones que gastan o pisan trabajo sin confirmar ni decir monto (Generar de nuevo, Guardar en ficha confirmada, Proponer). harden.
- [P1] Estado de validación sin forma visual; sin vista general de los 6 materiales. clarify + colorize.
- [P1] Ficha como muro de 72 campos: sin índice, sin aviso de cambios sin guardar. layout.
- [P2] Entrega como muro de texto, también cuando ya está aprobada; líneas de 120-140 caracteres. distill + typeset.
- [P2] Identidad y texto: sin FuturaSoft, h1 repite la ruta, género del laboratorio, materiales 4-6 ocultos. clarify.

## Personas
- Alex: 6 000 px hasta el laboratorio; sin atajos; "Convertir" activo con 0 pendientes.
- Sam: reload cada 5 s reinicia foco y lector; botón desactivado sin motivo enlazado; ruta sin nav ni aria-current.
- Profesor con apuro: el curso no dice qué sigue; "Aprobada… Desactualizada" sin qué cambió.

## Menores
Desborde de 10 px en móvil por ruta larga; button:disabled duplicado; #resultado sin uso; td en negrita global; gasto calculado y no mostrado en inicio.

## Preguntas
1. ¿Un material aprobado y desactualizado debe seguir viéndose aprobado?
2. ¿El inicio debería ser "qué sigue" en vez de una lista de cursos?
3. ¿Mostrar el costo de la última corrida en cada botón cambiaría lo que se pulsa con apuro?
