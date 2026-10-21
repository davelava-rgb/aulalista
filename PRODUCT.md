# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Un solo usuario: el profesor que construye y usa AulaLista (confirmado el 2026-10-15). Trabaja en su propia computadora con Windows y abre la interfaz en el navegador. Conoce las reglas de la skill `material-de-clase`, así que la interfaz no necesita enseñarlas.

Los alumnos no usan el software. Solo reciben los archivos que el profesor entrega.

## Product Purpose

AulaLista genera el material completo de una sesión de un curso a partir de dos fichas: lectura, diapositivas, laboratorio con guía del profesor, práctica interactiva y evaluación práctica con su clave. Valida cada material antes de entregarlo, para que el profesor no tenga que revisarlo a mano.

El éxito es que el profesor recibe archivos listos para los alumnos, sin fallas abiertas del verificador, y sabe en todo momento qué falta.

## Positioning

Toda afirmación sobre una fuente sale de un pasaje copiado de una fuente del curso. Un verificador sin IA revisa cada material antes de cualquier revisión con IA, y cada error que reporta la IA se comprueba con un programa contra la fuente. Lo que no se puede probar se descarta.

## Operating Context

- Flujo: ficha del curso, fichas de las sesiones, fuentes convertidas a texto, y luego un material a la vez, en orden fijo. Cada material espera la aprobación del profesor.
- Pantallas actuales: inicio, curso nuevo, curso, ficha (del curso y de la sesión), fuente, material y ayuda, en `web/plantillas/`.
- Salidas en Word, PowerPoint, Excel y HTML, más un Excel de verificación por material, con el formato de `S1_Laboratorio_Verificacion.xlsx`.
- Cada llamada a Claude cuesta dinero. La interfaz muestra el gasto por curso.

## Capabilities and Constraints

- Sistema web local. El servidor escucha solo en `127.0.0.1`. No se publica en internet.
- Python 3.13 con plantillas HTML del servidor; Node solo para el diseñador de diapositivas.
- Todo se guarda en archivos dentro de `cursos/[curso]/`. Sin base de datos.
- La interfaz y los materiales están en español.
- La identidad visual de cada curso (logo, hasta tres colores, estilo) vive en su ficha y se aplica a los materiales, no a la interfaz.
- La página del alumno de la actividad web la diseña el agente diseñador, a medida, con el contenido ya aprobado (`PLAN.md` §0, decisión 57). Es un material, no una pantalla de la interfaz: no lleva la marca FuturaSoft ni sigue `DESIGN.md`.
- Las reglas de `CLAUDE.md`, `PLAN.md` y `SPEC.md` mandan sobre cualquier decisión de diseño.

## Brand Commitments

- La interfaz lleva la marca FuturaSoft (confirmado el 2026-10-15).
- Logo y colores oficiales de FuturaSoft entregados por el profesor el 2026-10-15, en `web/estaticos/marca/`: magenta #C537A0 para acciones y títulos; morado #1E0253 solo en la cabecera con el logo.
- Lenguaje claro en toda la interfaz: una idea por oración, sin jerga, cada término técnico definido la primera vez. Sin emojis ni lenguaje publicitario.

## Evidence on Hand

- Excel modelo de verificación: `S1_Laboratorio_Verificacion.xlsx`.
- Curso real de prueba: `cursos/gobernanza-de-datos/` (no se sube al repositorio).
- Logo y paleta de FuturaSoft: `web/estaticos/marca/`.

## Product Principles

1. **Control y claridad primero.** El profesor ve siempre en qué paso va cada sesión, qué falta, qué falló y cuánto se gastó.
2. **Nada sin prueba.** La interfaz muestra el resultado de la validación junto a cada material; una falla abierta nunca se ve como aprobada.
3. **Un paso a la vez.** El orden del flujo se respeta en pantalla; lo que todavía no se puede hacer se explica, no se esconde.
4. **El costo se ve.** Toda acción que llama a Claude lo dice antes de ejecutarse.
