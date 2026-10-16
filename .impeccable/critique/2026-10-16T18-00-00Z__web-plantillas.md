---
target: interfaz web (web/plantillas)
total_score: 30
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 0
target_identity: "file:C:\\Users\\info\\OneDrive - FUTURASOFT\\Documentos\\aulalista\\web\\plantillas"
timestamp: 2026-10-16T18-00-00Z
slug: web-plantillas
closed: false
---
# Critique 3: interfaz web de AulaLista después de la decisión 38

Puntaje: 30/40 (Bueno; antes 24). P0: 0. P1: 0. P2: 3. P3: 2.

Método: revisión manual de las plantillas y de las páginas en el navegador (escritorio, celular de 375 px, modo claro y oscuro), con la misma tabla de las críticas 1 y 2. No se corrió el detector automático de impeccable, así que el puntaje no es del todo comparable con los anteriores.

| # | Heurística | Puntaje | Cambio | Problema principal que queda |
|---|---|---|---|---|
| 1 | Visibilidad del estado | 4 | = | Panel con el estado de todo el curso, recorrido por material, avance en vivo |
| 2 | Lenguaje del mundo real | 3 | = | "tokens", "verificador", "revisor independiente" y "PBQ" (ficha, sección 5) sin definir |
| 3 | Control y libertad | 3 | +1 | La ficha redirige y avisa antes de desactualizar; aprobar no se puede deshacer |
| 4 | Consistencia | 3 | +1 | Una sola navegación; el curso sigue con dos nombres («scrum master» y el de la ficha) |
| 5 | Prevención de errores | 3 | +1 | El revisor ya no se ofrece sobre material desactualizado; Generar de nuevo pide confirmación |
| 6 | Reconocer, no recordar | 4 | +1 | Panel, píldora «Sigue», lista de lo que ya se cumple antes de generar |
| 7 | Flexibilidad y eficiencia | 2 | +1 | El panel acorta la navegación; no hay atajos ni «ir al siguiente campo que falta» |
| 8 | Estética y minimalismo | 3 | +1 | Un solo color de acción, títulos en tinta, notas de una línea; la ficha sigue larga |
| 9 | Recuperación de errores | 3 | = | Lo que falta se dice con «!» y enlace a la ficha; el error de una corrida se muestra crudo |
| 10 | Ayuda | 2 | = | No hay un lugar que explique el flujo completo y los términos |

## Problemas que quedan
- [P2] La página de inicio no cambió: lista de cursos con su gasto, sin el estado de cada uno. Necesita una decisión del profesor. shape.
- [P2] Términos sin definir en la interfaz: tokens, verificador, revisor independiente, PBQ. clarify.
- [P2] El curso tiene dos nombres a la vista: el de la carpeta en el panel y el de la ficha en los materiales. polish.
- [P3] En la lectura aprobada, «Siguiente paso» y «Aprobada por ti el…» repiten lo que ya dice el recorrido. distill.
- [P3] El texto de un error de corrida (`e.error`) se muestra tal como llega. harden.

## Lo que mejoró desde la crítica 2
- Navegación: panel lateral en todas las páginas del curso; un material por página; la ruta de enlaces desapareció.
- Jerarquía: el magenta solo marca lo que se pulsa y dónde estás.
- Entrega: archivos en filas, decisiones pendientes visibles antes y después de aprobar, acciones juntas con un solo botón principal.
- Celular: ninguna página se sale de 375 px (antes la ficha medía 833 px por un texto sin cortes).
