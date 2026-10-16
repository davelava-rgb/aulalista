---
target: interfaz web (web/plantillas)
total_score: 24
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\Users\\info\\OneDrive - FUTURASOFT\\Documentos\\aulalista\\web\\plantillas"
timestamp: 2026-10-16T07-00-40Z
slug: web-plantillas
---
# Critique 2: interfaz web de AulaLista (web/plantillas)

Puntaje: 24/40 (Aceptable; antes 22). P0: 0. P1: 2. P2: 2. P3: 1.

| # | Heurística | Puntaje | Problema principal |
|---|---|---|---|
| 1 | Visibilidad del estado | 4 | Icono + palabra, franja, avance en vivo, gasto por corrida |
| 2 | Lenguaje del mundo real | 3 | "tokens", "PBQ", "verificador", "revisor independiente" sin definir |
| 3 | Control y libertad | 2 | POST de la ficha sin redirección: recargar reenvía; Guardar y Recuperar sin confirmación |
| 4 | Consistencia | 2 | Nombre del curso en dos formas; fichas ofrecen Evaluación; "Segoe ui" |
| 5 | Prevención de errores | 2 | Revisor (hasta 2 USD) ofrecido sobre material desactualizado |
| 6 | Reconocer, no recordar | 3 | Índice, "Responde primero", motivos junto a botones bloqueados |
| 7 | Flexibilidad y eficiencia | 1 | Sin atajos ni "siguiente campo que falta" |
| 8 | Estética y minimalismo | 2 | 60 marcas "Fuente: dama-dmbok…" iguales; gasto repetido |
| 9 | Recuperación de errores | 3 | Lista "Para confirmarla falta"; error crudo en sesion.html:48 |
| 10 | Ayuda | 2 | Sin lugar único que explique el flujo y los términos |

Detector: CLI 6 avisos design-system-color (falso positivo: sin CSS). Navegador 13 (antes ~130): desaparecieron ai-color-palette y line-length. Real: "Azul institucional" se sale 19 px de su recuadro. cramped-padding, overused-font y text-occlusion son falsos positivos.

## Problemas prioritarios
- [P1] Guardar una ficha confirmada desactualiza materiales aprobados sin confirmar; el POST no redirige y recargar reenvía Proponer/Completar (gasta). harden.
- [P1] En cada material, "Pedir revisor" va antes de Generar/Aprobar y se ofrece sobre material desactualizado. layout + distill.
- [P2] Ficha de sesión pesada: 60 marcas de fuente iguales, barra fija de 212 px en móvil. distill.
- [P2] Las fichas piden evaluación sin decir que no se usa (decisión 37); "se producen los cuatro" es falso. clarify.
- [P3] Nombre del curso en dos formas, "Segoe ui", ficha confirmada sin icono, "Azul institucional" desborda. polish.
