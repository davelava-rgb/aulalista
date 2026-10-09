Vas a planificar un proyecto nuevo llamado AulaLista. No escribas código todavía.

Lee completos estos tres archivos antes de responder:

1. `SPEC.md`: qué debe hacer el software.
2. `.claude/skills/material-de-clase/SKILL.md`: las reglas de los materiales. Si el SPEC y la skill se contradicen, vale la skill. Avísame de cada contradicción que encuentres.
3. `S1_Laboratorio_Verificacion.xlsx`: el modelo exacto del archivo de verificación. Ábrelo con un programa y revisa sus cuatro hojas.

Decisiones ya tomadas. No las cambies:

- Un solo usuario. Sistema web que corre en mi computadora con Windows y se abre en el navegador.
- Claude Agent SDK, con la clave de API leída desde un archivo `.env`.
- Programa verificador en Python.
- Todo se guarda en archivos, en una carpeta por curso. Sin base de datos.
- El programa `scripts/verificar.py` de la skill no está disponible. Hay que escribirlo de nuevo a partir de la skill y del Excel modelo.

Entrégame un plan con estas partes:

1. Arquitectura: los componentes, qué hace cada uno y cómo se comunican. Incluye un diagrama simple.
2. Tecnología: lenguaje, librerías y versiones, con la razón de cada elección. Propón la opción más simple que cumpla el SPEC.
3. Estructura de carpetas del proyecto.
4. Etapas: usa las etapas de la sección 12 del SPEC. Si propones otro orden, explica por qué. Cada etapa debe ser pequeña y dejar algo que yo pueda probar.
5. Validación: cómo construyes cada parte de la sección 7 del SPEC y en qué etapa queda lista. Explica por separado:
   - el programa verificador y cada una de sus revisiones;
   - la primera pasada, de veracidad, oración por oración;
   - la segunda pasada, de valor y funcionamiento;
   - el revisor independiente y sus rondas;
   - el ciclo de corrección: qué se vuelve a validar después de cada cambio y cuándo termina;
   - cómo se llena cada hoja y cada columna del Excel modelo;
   - qué valida cada uno de los seis materiales, según la tabla de la sección 7.
   Di también cómo pruebas que la validación detecta errores: prepara materiales con errores puestos a propósito y comprueba que cada uno queda marcado.
6. Pruebas: por cada etapa, qué prueba automática demuestra que funciona. Las reglas de la sección 6 del SPEC deben quedar como pruebas.
7. Costo: dónde se gastan tokens y cómo aplicas las reglas de ahorro de la sección 9.
8. Riesgos: lo que puede fallar y cómo lo detectamos pronto.
9. Preguntas: lo que necesitas que yo decida antes de empezar. Máximo cinco.

Reglas para tu respuesta:

- Escribe en español claro. Una idea por oración. Sin jerga. Si usas un término técnico, defínelo en una frase la primera vez.
- No inventes funciones del Agent SDK. Consulta su documentación antes de afirmar qué hace.
- Si algo del SPEC no se puede construir como está escrito, dilo.

Cuando yo apruebe el plan, guárdalo como `PLAN.md`. Después crea el `CLAUDE.md` con las reglas fijas del proyecto. No empieces la etapa 1 sin mi aprobación.
