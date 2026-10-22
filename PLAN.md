# PLAN · AulaLista

Plan aprobado por el profesor el 2026-10-08.
Fuentes del plan: `SPEC.md`, `.claude/skills/material-de-clase/SKILL.md` y `S1_Laboratorio_Verificacion.xlsx`.
Si el SPEC y la skill se contradicen, vale la skill, salvo las excepciones aprobadas que se listan en la sección 0.

Términos usados en este plan:

- **SDK:** librería que conecta el programa con Claude. Aquí es el Claude Agent SDK para Python.
- **API:** servicio de Anthropic que se paga por uso con una clave.
- **Servidor local:** programa que corre en la computadora del profesor y responde al navegador.
- **Orquestador:** componente que decide el siguiente paso y guarda el estado.
- **Generador de archivos:** programa que convierte un contenido ya escrito en Word, PowerPoint, Excel o HTML.
- **Herramienta propia:** función de Python que el agente puede llamar. El SDK la llama "herramienta MCP".
- **Huella:** código corto que cambia si cambia una sola letra de un texto.

## 0. Decisiones, contradicciones y límites

### Decisiones del profesor

| N.º | Decisión |
|---|---|
| 1 | El revisor independiente tiene un máximo de tres rondas. Es una excepción a la skill, que no pone tope. Después de la tercera ronda, el software se detiene y avisa |
| 2 | Filas sin pasaje en el Excel: títulos y encabezados de tabla llevan tipo "sin afirmación", pasaje "no aplica" y veredicto "coincide". Un dato del caso lleva como pasaje la línea de la ficha que lo contiene. Una instrucción lleva como pasaje el resultado de su ejecución |
| 3 | AulaLista usa solo la clave de API del `.env`. Sin clave, se detiene y avisa. No usa el plan Max como respaldo |
| 4 | El profesor llena las dos fichas en formularios de la página y las puede editar en cualquier momento. Un botón "Proponer desde las fuentes" llena los campos vacíos con datos de los archivos del curso, marcados "(propuesto)" y con su archivo de origen |
| 5 | La lista inicial de lenguaje de IA es la de la sección 10 de este plan |
| 6 | El redactor recibe las secciones de `SKILL.md` que necesita cada material, leídas por AulaLista. No se usa la carga de skills del SDK, porque con `setting_sources=["project"]` también carga el `CLAUDE.md` del proyecto (aprobado en la etapa 5a) |
| 7 | Al llegar al tope de cinco vueltas, el programa elimina las oraciones que siguen sin coincidir con su fuente o que la segunda pasada marcó como relleno o ambiguas, y valida de nuevo. Un vacío, una inconsistencia o un punto de la lista de verificación que siga abierto queda en «Decisiones pendientes» y el material no se entrega (aprobado en la etapa 5c) |
| 8 | Ahorro aprobado en la etapa 5b: correcciones por oración con Sonnet, pedidos con la parte fija primero, primera pasada en grupos de 40 con esfuerzo bajo, segunda pasada con esfuerzo alto solo en su primera revisión. La lectura se mantiene en 1.500 palabras como máximo (decisión del profesor en la etapa 5c) |
| 9 | Las pasadas tienen su tope de cinco vueltas. Después, cada ronda del revisor independiente tiene hasta dos vueltas para corregir sus hallazgos y lo que esa corrección rompa. Peor caso: 5 + 3 × 2 = 11 vueltas (aprobado en la etapa 5d) |
| 10 | Reglas aflojadas en la etapa 5d. Son excepciones a la skill. a) En el contenido de una fuente se comparan cuatro cosas: número de referencia, término, cantidades y "debe" o "puede". El orden, quién hace la acción y las palabras que generalizan ya no se comparan una por una; una oración que contradice al pasaje o le agrega una afirmación sigue siendo "no coincide". b) Un resumen de una norma que dice "en este curso" se juzga solo por si contradice o agrega algo. Igual necesita su pasaje copiado tal cual. c) Una oración de más de 25 palabras que sigue a su pasaje de una norma no se parte. Si su pasaje existe tal cual, el programa explica el aviso solo. Reemplazada por las decisiones 18 y 19 |
| 11 | La lista de verificación de la skill se aplica por material. Cada material recibe solo las preguntas que le corresponden: la lectura y las diapositivas reciben 3 de 14 (decisión 20). Las preguntas que ya revisa un programa (diseño uniforme; minutos, puntos y porcentajes) no van a la IA. Si la skill agrega una pregunta, el programa se detiene hasta repartirla (aprobado en la etapa 5d) |
| 12 | Dos jueces con IA, no tres. La primera pasada revisa la veracidad en cada vuelta. El revisor independiente hace también la segunda pasada: las cuatro preguntas por bloque, la lista de verificación y los errores que solo se ven al leer el documento completo. Ya no compara oración por oración con las fuentes. Es una excepción a la skill, que pide una segunda pasada propia y un revisor que compare cada oración con las fuentes (aprobado en la etapa 5d) |
| 13 | Los avisos de relleno y de palabras imprecisas se mantienen en la hoja Hallazgos, pero son informativos: no obligan a corregir ni a explicar (aprobado en la etapa 5d) |
| 14 | Oraciones aprobadas protegidas. En una corrección por oraciones, el programa rechaza el cambio a una oración que ya coincide con su fuente si ningún problema la nombra. Si algún problema no nombra oraciones (un punto de la lista de verificación), la protección no se aplica en esa corrección. La corrección completa del documento tampoco se protege. La entrega dice cuántos cambios se rechazaron (aprobado en la etapa 5d) |
| 15 | La skill es agnóstica al tipo de fuente. «Norma» pasa a ser «contenido de una fuente», y «cláusula o control» pasa a ser «número de referencia» (sección, cláusula, lámina o paso). El contenido de una fuente se puede decir con otras palabras si no cambia su sentido: el juez compara el sentido, no las palabras. Quedan exactos el pasaje que se cita como prueba, las citas entre comillas, los nombres del vocabulario, las cifras y «debe» o «puede». Se corrigió en SKILL.md, en el verificador y en AulaLista; no es una excepción (aprobado en la etapa 5d) |
| 16 | Campos de las fichas. En la ficha del curso, «Público» y «Empresa o institución ficticia y rubro» son opcionales; siguen obligatorios el nombre del curso y las sesiones. La ficha de la sesión se confirma con número y título, alcance y vocabulario. Los datos de cada material (bloques y riesgos de la lectura, ejercicios, estaciones, preguntas) se exigen al generar ese material, y la página dice qué falta. Se corrigió también en las plantillas de SKILL.md (aprobado en la etapa 5d) |
| 17 | Fichas desde las fuentes. Si el curso tiene fuentes convertidas, la ficha del curso se propone desde ellas cuando el profesor pulsa «Proponer desde las fuentes». Abrir una ficha nunca gasta: antes se proponía sola la primera vez que se abría, en segundo plano (cambiado el 2026-10-21). La propuesta llena todos los campos: lo que la fuente dice, tal cual y con su archivo; lo que deduce (sesiones por capítulo, público, temas, vocabulario) y los datos ficticios del caso, marcados «Propuesto». No propone la identidad visual ni los modelos, y el docente y el contacto solo se toman si la fuente los dice tal cual. El botón «Aceptar lo propuesto y confirmar» confirma en un paso. Sin fuentes, la ficha se llena a mano. Amplía la decisión 4 (aprobado en la etapa 5d) |
| 18 | Solo el sentido. Una oración con otras palabras, sinónimos u otro orden coincide con su fuente. Solo es «no coincide» si contradice al pasaje, le agrega una afirmación, cambia una cifra o una cantidad, o cambia «debe» por «puede». La IA ya no compara puntos uno por uno, y una comparación olvidada ya no hace fallar la oración. El programa ubica el pasaje copiado aunque cambien tildes, mayúsculas, signos o una palabra cortada con guion al final de una línea. Reemplaza la decisión 10 a) y b). Se corrigió en SKILL.md; no es una excepción (aprobado en la etapa 5d) |
| 19 | Se quitan tres avisos del verificador: oración larga, porcentaje y horas. Un porcentaje solo es una falla si pesa en la nota («el 20 % del curso», «vale el 30 %»). Siguen siendo fallas los minutos, segundos, cronómetros, puntos y notas. «Una idea por oración» la revisa el revisor independiente con la lista de verificación. Reemplaza la decisión 10 c) (aprobado en la etapa 5d) |
| 20 | Preguntas por material. La lectura y las diapositivas responden solo dos de las cuatro preguntas por bloque: «¿Qué puede hacer el alumno con esto?» y «¿Qué oración tiene dos lecturas?». Las otras dos son para ejercicios y pasos. De la lista de verificación, la lectura y las diapositivas reciben solo tres preguntas: si cada sección aporta, si hay frases con dos ideas o con jerga, y si hay contenido de sesiones posteriores. Amplía la decisión 11. Es una excepción a la skill, que hace las cuatro preguntas en todos los materiales (aprobado en la etapa 5d) |
| 21 | La lista de verificación es informativa. El revisor responde cada pregunta con «cumple», «no cumple» o «no aplica», y no con «sí» o «no»: así la respuesta no depende de cómo está escrita la pregunta. Un «no cumple» queda como AVISO en la hoja Hallazgos, con dónde está el problema, pero no se envía a corrección ni cuenta para lanzar otra ronda. Los hallazgos del revisor con prueba se siguen corrigiendo. Cambia la decisión 7 en lo que dice de la lista (aprobado en la etapa 5d) |
| 22 | Validación en dos pasadas. 1) El verificador, sin IA: sus fallas se corrigen hasta tres veces y una falla abierta no deja aprobar. 2) Una revisión del contenido con IA (Sonnet), por bloque y no por oración: recibe cada bloque con los pasajes de las fuentes y de las fichas que elige el programa, y reporta solo errores reales (contradice la fuente, dato inventado, vacío, ambigüedad, inconsistencia). Decir lo mismo con otras palabras nunca es un error. La prueba de una contradicción o de una inconsistencia se comprueba con un programa; sin prueba real, el error se descarta. Una sola corrección de esos errores; después, el verificador otra vez y la revisión solo de los bloques que cambiaron. Lo que quede abierto va a la entrega como pendiente y el profesor puede aprobar igual. El revisor independiente (Opus) pasa a ser opcional: lo lanza el profesor con un botón y no corrige. El Excel queda solo con la hoja Hallazgos. Reemplaza las decisiones 1, 2, 7, 9, 12, 14, 18 (en lo que dice de la primera pasada) y 21 (en lo que dice de las rondas). Se corrigió en SKILL.md, SPEC.md y CLAUDE.md; no es una excepción (aprobado en la etapa 5d) |
| 23 | Material de referencia por sesión. La ficha de la sesión tiene dos campos nuevos: «Material de referencia» (una línea por archivo de las fuentes, con sus páginas del PDF; sin páginas, el archivo completo) y «Exclusiones» (temas o páginas que no se usan; vacío, se usa todo). Con material de referencia, la lectura cubre todos sus temas menos las exclusiones, su extensión sale de esos temas y no tiene máximo de páginas ni de 2 a 4 bloques; los temas de la ficha son opcionales y, si se llenan, mandan. Sin material de referencia, siguen los temas obligatorios, de 2 a 4 bloques, seis páginas y unas 1.500 palabras. Un archivo que no es fuente del curso o unas páginas que no existen no dejan generar. Cambia la decisión 8 en lo que dice de las 1.500 palabras. Se corrigió en SKILL.md y SPEC.md; no es una excepción (aprobado en la etapa 5d) |
| 24 | Decisiones del redactor por tipo. El redactor anota cada decisión como «sin fuente» (afirma algo del tema que no está en ninguna fuente ni ficha), «decisión» (se aparta de las fichas o de las fuentes, o cambia lo que lee el alumno) o «nota» (solo describe el trabajo). Lo «sin fuente» va a «Decisiones pendientes» y deja la lectura «con pendientes»; el profesor puede aprobar igual. «Qué decidí por mi cuenta» muestra solo las «decisión». Las tres quedan en la hoja Hallazgos. No gasta tokens. Se corrigió en SKILL.md («Formato de cada entrega»); no es una excepción (aprobado en la etapa 5d) |
| 25 | Antes de gastar tokens, la lectura comprueba que SKILL.md tiene todas las secciones que usarán la redacción, la revisión y el revisor, y borra los archivos de la generación anterior (Word, Excel, entrega, contenido, explicaciones y la carpeta del revisor). Un archivo abierto que no se deja borrar se reescribe después (aprobado en la etapa 5d) |
| 26 | Diapositivas sin lectura. Si «Cuáles se producen» de la ficha de la sesión no incluye la lectura, las diapositivas salen del material de referencia (menos las exclusiones) y de las fichas, y se validan contra las fuentes del curso y las fichas, igual que la lectura: verificador, medición con PowerPoint y revisión del contenido. La ficha de la sesión necesita entonces lo mismo que pide la lectura: material de referencia o de 2 a 4 bloques de temas, y de 1 a 3 riesgos en «Cuidado con». El orden lo dan los bloques de la ficha o, si no hay, el orden de la referencia; el programa comprueba que las diapositivas de un bloque vayan juntas. Si la sesión produce la lectura, las diapositivas salen de la lectura aprobada, como dice la skill. Es una excepción a la skill («Cada material usa el anterior como fuente») y al SPEC §7 para las sesiones sin lectura (aprobado en la etapa 6) |
| 27 | Controles en las fichas. Los campos que tienen respuestas conocidas se llenan con controles en lugar de cuadros de texto: idioma, paleta de colores (seis paletas listas o personalizada), tipografía, logo (se sube el archivo), estilo, herramientas, materiales y modelos. Cada control escribe el mismo texto en la ficha, así que el verificador y los generadores la leen igual. a) Campo nuevo «Estilo» en la identidad visual: profesional, académico, moderno, corporativo, minimalista o cercano. Cambia el diseño de la portada, el tamaño de los títulos y el borde de los recuadros, y el tono del texto. El cuerpo (11 pt, interlineado 1,15), los recuadros sombreados, las reglas de lenguaje claro, sin publicidad y de tres colores como máximo se mantienen en todos los estilos. Sin estilo, vale «profesional», que es el diseño de siempre. b) Portada: el docente viene lleno con «José Fernando Davelouis Mendía» y el contacto con «www.linkedin.com/in/jdavelouis» e «info@futurasoft.net». Se pueden editar. La portada muestra el contacto. Cambia la decisión 17 en lo que dice del docente y el contacto. c) Modelos: se suben uno o varios PDF a `cursos/[curso]/modelos/`. Un programa saca de ellos, sin IA, los colores y la tipografía; el redactor recibe un pasaje corto del modelo solo como guía de tono. Las secciones de cada material siguen las de la skill. Lo que se elige en la ficha manda; el modelo llena solo lo que la ficha deja vacío. Cada modelo se analiza una sola vez. Se corrigió la plantilla de SKILL.md; no es una excepción (aprobado el 2026-10-12) |
| 28 | Ficha del curso más rápida. a) Campos nuevos en «1. Curso»: «Horas del curso» y «Número de sesiones». Las horas solo sirven para repartir el tema: no llegan al redactor y ningún material las muestra. La propuesta desde las fuentes los toma solo si la fuente los dice tal cual. b) Tres botones «Completar», que gastan tokens y llenan solo campos vacíos, marcados «Propuesto»: las sesiones (con el curso, las horas, el número de sesiones, el público y, si hay, las fuentes), el caso del curso (con el curso y el público) y los datos fijos (con el curso, el público y el caso). Un programa avisa si el número de sesiones no cuadra, si una línea de datos fijos no tiene la forma «Etiqueta: valor» o si aparece un tiempo. c) Sin botón «Confirmar ficha»: «Guardar» guarda y, si la ficha está completa, la confirma. Una ficha confirmada que no cambia sigue confirmada y no deja materiales desactualizados. En la ficha de la sesión, la revisión de ejercicios corre al guardar. «Aceptar lo propuesto y guardar» reemplaza a «Aceptar lo propuesto y confirmar». d) Con un modelo en PDF, la portada sigue la disposición de su carátula (título centrado o no, franja de color arriba y lugar del logo), que un programa saca sin IA de la primera página. Los colores, la tipografía y el logo siguen siendo los de la ficha: la identidad visual manda. En la portada, la carátula del modelo reemplaza lo que decide el estilo. Cambia las decisiones 4, 17 y 27. Se corrigió la plantilla de SKILL.md; no es una excepción (aprobado el 2026-10-12) |
| 29 | Diapositivas con diseño. a) Portada: un panel del color principal con el curso, la sesión, el docente y el contacto, y una línea del color de acento. Sin emblema; el logo va si la ficha lo trae. Sigue la disposición del modelo en PDF cuando la hay (decisión 28). b) Recursos gráficos, dibujados como formas de PowerPoint que se pueden editar: proceso, ciclo, organigrama, mapa mental, matriz 2×2, tablero de tarjetas y gráfica de barras, además de las tablas, las columnas y los pasos. Al menos la mitad de las diapositivas de concepto lleva uno de estos recursos (no cuentan las frases ni el ejemplo) y nunca hay más de dos diapositivas de concepto seguidas solo con texto. Una gráfica de barras solo usa cifras que están en la lectura o, sin lectura, en un pasaje copiado de una fuente. c) Diapositiva final de cierre, con el mismo diseño de la portada: una frase de la idea central (la idea que se llevan), el docente y el contacto. Es una excepción a la skill, que prohíbe las diapositivas de relleno: la frase sale del contenido, no es un «Gracias». d) Con el cierre, las fijas son cinco y el total va de 15 a 19 diapositivas, en lugar de 14 a 18. Es una excepción a la skill (aprobado el 2026-10-12) |
| 30 | Diapositivas menos cargadas y con más diseño. a) Cada diapositiva de concepto y la idea central muestran 30 palabras como máximo, sin contar el título. Lo que no cabe va a las notas del profesor y no es una decisión del redactor: la lectura tiene el detalle. b) Solo cuentan como recurso gráfico los diagramas: proceso, ciclo, organigrama, mapa mental, matriz, tarjetas, gráfica de barras y el tipo nuevo «cifras» (de 1 a 3 cifras grandes, solo con cifras de la lectura o de un pasaje copiado). Las tablas, las columnas y los pasos ya no cuentan, y hay dos tablas como máximo. La regla de la decisión 29 (al menos la mitad) se mide con esta lista. c) Nuevo diseño de las diapositivas: el nombre del bloque arriba del título, una marca de avance por bloque, la idea central sobre el fondo de recuadro, tarjetas con encabezado de color en lugar de recuadros con borde izquierdo, y marcas de color en las frases, en «Aplícalo así» y en «Cuidado con». Es una excepción a «Diseño común» de la skill, solo en las diapositivas: el Word sigue igual. d) Revisión visual con IA, una sola vez: después del verificador, Sonnet mira la imagen de cada diapositiva y señala las cargadas, las monótonas o las que piden otro recurso. Sus propuestas van a una corrección completa y el verificador corre otra vez (aprobado el 2026-10-12) |
| 31 | La fuente manda (aprobado el 2026-10-12). a) Las cifras de las fuentes y de las fichas se copian tal cual: no se quitan ni se cambian. Si una cifra parece ambigua, se mantiene y la duda va a la entrega. b) La neutralidad de herramientas prohíbe solo las marcas, botones y menús que no nombran las fuentes del curso ni las fichas. Cambia el SPEC §6 y la skill. c) Una variante prohibida del vocabulario solo se prohíbe como nombre del concepto. Un término que la fuente usa con su sentido se puede usar: si la variante va junto a la misma palabra con que la usa una fuente («jefe administrador de datos»), el verificador lo marca como AVISO informativo «término de la fuente», no como FALLA. La propuesta de la ficha no pone como variante un término de la fuente. d) Los temas siguen el orden de la fuente, también dentro de cada bloque, y el vocabulario de la ficha se propone en ese orden. Cambia la skill («Paso 3 · Vocabulario») y el SPEC §6. e) Un tema de una sesión posterior se puede nombrar en pocas oraciones si hace falta para entender la sesión o por razones pedagógicas. No se desarrolla y va a la entrega. La lista de verificación lo acepta como «cumple». f) Si una ficha contradice una fuente, se sigue la fuente y la diferencia va a la entrega. Un dato ficticio del caso que hace falta (un plazo, una cantidad) se puede agregar y va a los datos fijos. La revisión del contenido no marca nada de esto como error. g) Corrección por diapositivas: un problema que nombra diapositivas (desborde, palabras, notas, diseño, un recurso) se corrige devolviendo solo esas diapositivas, con Sonnet (`correccion_diapositivas` en `config/modelos.toml`). La cantidad, el orden, los bloques y los recursos o tablas en total siguen con la corrección completa. h) En el Excel de la lectura, la columna B de la hoja Hallazgos se llama «Sección»; en el de las diapositivas sigue «Diapositiva». Se corrigió en SKILL.md, SPEC.md y CLAUDE.md; no es una excepción |
| 32 | Agente diseñador de las diapositivas. a) El redactor escribe el contenido y la validación lo aprueba sobre una versión base que dibuja el programa de Python, como hasta ahora. b) Con el contenido aprobado, un agente diseñador (Opus) escribe un programa pptxgenjs que dibuja la presentación, con íconos de react-icons y solo los colores y la tipografía de la ficha. AulaLista lo rechaza si usa require, procesos, red o archivos, y lo corre con Node con permisos limitados (`app/disenador/ejecutar.js`). c) Controles del resultado: una diapositiva por parte del contenido; todo el texto tal cual del contenido aprobado, salvo etiquetas de cuatro palabras como máximo; letra de 12 puntos o más; solo los colores de la ficha; notas del contenido en todas. Después, medición con PowerPoint, verificador y revisión visual con Sonnet. El diseñador corrige hasta tres veces, contando la ronda de la revisión visual. Si no queda sin fallas, se entrega la versión base y el diseño va a «Decisiones pendientes». d) Se quitan el límite de 30 palabras, el tope de dos tablas, la regla de la mitad con diagramas y el mínimo de 18 puntos de la decisión 30, y el diseño propio de la decisión 30 queda solo en la versión base. El «tipo» de cada diapositiva pasa a ser una sugerencia para el diseñador. e) Cambia la regla de CLAUDE.md «el agente no escribe PowerPoint a mano», solo para el diseño de las diapositivas. Paquetes de Node con versiones fijas en `package.json` (aprobado el 2026-10-12) |
| 33 | Guía del laboratorio con la estructura de la referencia (`S2_Laboratorio_referencia.pdf`). a) «Antes de empezar»: el contexto del caso, la fecha de referencia, «Cada ejercicio funciona solo. Puedes hacerlos en cualquier orden.», las tablas y reglas que comparten los ejercicios, y la tabla de archivos con el nombre del .zip. b) Si algún ejercicio trae fórmulas, el recuadro «Antes de copiar una fórmula» con los nombres de las funciones en español y en inglés. c) Cada ejercicio: «Área:», «Situación», «Archivos de práctica» con las hojas de cada Excel, «Pasos» numerados, recuadros de prompt, de fórmula (título, una línea de explicación y la fórmula en letra monoespaciada) o de plantilla, y «Mejora el resultado (opcional)» con su texto, sus pasos y sus recuadros. d) Pie de página «Sesión N · Laboratorio · Página N». e) Una figura por ejercicio como máximo, y solo si hace falta: es obligatoria cuando un paso pide ubicar algo en el archivo (una columna, una celda, un rango o un apartado), y un programa lo revisa (aprobado el 2026-10-13). f) Se mantienen las reglas de la skill: sin «Cómo se ve un buen resultado» ni «Criterio de calidad», y «(opcional)» en «Mejora el resultado». La estructura queda en el generador: la referencia no se envía al redactor. Se corrigió en SKILL.md la regla de las imágenes; no es una excepción (aprobado el 2026-10-13) |
| 34 | Sin práctica interactiva. Se quita la etapa 8: AulaLista no genera la práctica web en HTML. Las fichas ya no piden sus estaciones y «Materiales de esta sesión» ofrece cinco materiales; «los seis» de una ficha anterior vale como todos. Es una excepción a la skill («Material 5») y al SPEC §3 (aprobado el 2026-10-13) |
| 35 | Sin guía del profesor; la ejecución pasa al laboratorio. a) AulaLista no genera la guía del profesor («Material 4» de la skill) y la etapa 7b queda solo como ejecución. «Materiales de esta sesión» ofrece cuatro materiales; «los cinco» o «los seis» de una ficha anterior valen como todos. b) Después de la revisión del contenido, cada ejercicio se ejecuta como un alumno: un programa sigue los pasos tal cual («Copia la fórmula N en la celda X», «Copia la celda X hacia abajo, hasta la fila N», «Escribe **texto** en la celda X») y Excel calcula; cada prompt va en una conversación nueva con Claude (Sonnet, `ejecucion` en `config/modelos.toml`), sin herramientas, con el texto de los archivos adjuntos en el mensaje, más la respuesta exacta del alumno si la ficha la trae y los prompts de «Mejora el resultado». c) Una fórmula con un valor de error es una FALLA: una corrección completa y una nueva ejecución de ese ejercicio; si sigue, el laboratorio queda con fallas. d) Lo que salió se compara con la respuesta correcta de la ficha (Sonnet, `comparacion_ejecucion`). Cada diferencia trae un trozo copiado de la ficha y otro de lo que salió; un programa los busca y descarta la diferencia sin prueba. Las que quedan van a la entrega como pendientes y el profesor decide. e) El registro de la ejecución queda en `S[N]_Laboratorio_Ejecucion.md`. Los problemas sembrados van a «Qué decidí por mi cuenta» de la entrega. Es una excepción a la skill («Material 4») y al SPEC §3 (aprobado el 2026-10-13) |
| 36 | La herramienta de los ejercicios sale del tema del curso. a) La ficha del curso trae «Herramienta de los ejercicios» en la sección 7: ninguna, Excel, IA o Excel e IA. Vacío vale «ninguna». La propone el agente por el tema del curso; los modelos y la referencia del laboratorio dan la estructura, no la herramienta. b) Los ejercicios practican el tema de la sesión. Un prompt solo va en un curso de IA y una fórmula solo en un curso de Excel. Con «ninguna», el alumno hace la acción a mano en su archivo de práctica y el ejercicio no trae recuadros, salvo una plantilla si completarla es el tema. Un programa da FALLA si un ejercicio trae un recuadro o nombra un prompt, una fórmula o un adjunto que el curso no usa. c) Sin IA no hay aviso de adjuntos, y la pregunta «Si la herramienta debe preguntar algo» no se muestra ni se usa. d) La ejecución de la decisión 35 sigue igual para prompts y fórmulas. Un ejercicio sin prompt ni fórmula lo hace Claude a mano como alumno: una conversación nueva, sin herramientas, con el texto de sus archivos, la situación y los pasos, sin la respuesta de la ficha. Lo que entrega se compara con la respuesta correcta de la ficha. e) Cambia la skill: «Ejercicios que se ejecutan», «Neutralidad» y el punto 5 de «Material 3» (los recuadros, solo si el ejercicio los necesita) (aprobado el 2026-10-15) |
| 37 | Sin evaluación ni clave. Se quita la etapa 9: AulaLista no genera la evaluación práctica (PBQ) ni su clave. La interfaz ya no la muestra como etapa posterior. Las fichas no cambian todavía. Es una excepción a la skill («Material 6») y al SPEC §4 (aprobado el 2026-10-16) |
| 38 | Entorno con panel lateral. a) Las páginas de un curso llevan a la izquierda un panel fijo con la preparación del curso (fuentes y ficha del curso), las sesiones con su ficha y sus materiales, el estado de cada uno con icono y palabra, el siguiente paso y el gasto del curso. b) Cada material se ve en su propia página, uno a la vez, con su recorrido: Generar, Verificar, Revisar y Aprobar. c) La página del curso queda como «Preparación del curso»; la tabla de sesiones pasa al panel. d) El magenta queda solo para lo que se puede pulsar y el material actual; los títulos van en tinta oscura y negrita. Se aplica en cuatro fases (panel, material, página del curso, estilo). Cambia la regla de DESIGN.md «no hay menú lateral» (aprobado el 2026-10-16) |
| 39 | Desbordes pequeños sin IA. Cuando, después de medir las diapositivas con PowerPoint, las únicas fallas abiertas son textos que se pasan de su recuadro 0.5 cm o menos, AulaLista recorta el margen interior de esos recuadros (el espacio entre el borde y el texto, arriba y abajo) solo lo necesario, sin IA ni costo, y mide de nuevo. La letra no cambia: sigue en su tamaño y nunca baja del mínimo legible. Si el margen no alcanza, la falla queda. Cada ajuste va a la entrega, en «Qué decidí por mi cuenta». Se probó con PowerPoint en la diapositiva 4 de Gobernanza de Datos S3: el desborde de 0.3 cm desapareció y la diapositiva se ve igual. Bajar la letra se descartó porque obligaba a ir de 18 a 16 puntos, bajo el mínimo legible (aprobado el 2026-10-16) |
| 40 | Reanudar las diapositivas desde lo guardado. Si las diapositivas quedaron «Con fallas», «Detenidas» o con «Error», y las fichas y la lectura no cambiaron desde esa corrida, la página ofrece «Reanudar desde lo guardado». AulaLista toma el contenido ya redactado y corregido (`contenido.json`) y sigue desde el armado del PowerPoint: medición, verificador (con el ajuste de la decisión 39), revisión del contenido, diseño y entrega. No repite la redacción ni las correcciones ya hechas, y gasta menos. El historial de las vueltas de la corrida anterior no pasa al Excel; la entrega lo dice. Si las fichas o la lectura cambiaron, solo se puede generar de nuevo. Vale para las diapositivas, la lectura y el laboratorio (aprobado el 2026-10-16; lectura y laboratorio el 2026-10-17) |
| 41 | Diseño de las diapositivas más barato, etapa A. Medición previa (sesión 3 de gobierno de datos): el diseño costaba unos 2 dólares de los 3 de la corrida y tardaba 11 minutos; dos tercios de lo que escribía el diseñador era razonamiento. Cambios: a) cada ronda del diseño guarda sus problemas en `diseno/rondas.json` y en el estado; b) arreglos sin IA antes de los controles: la letra menor que 12 puntos sube a 12, un color que no es de la ficha pasa al color de la ficha más parecido y las notas distintas a las del contenido se copian del contenido; el texto ajeno sigue volviendo al diseñador; c) los arreglos del diseñador son una corrección y van con Sonnet (tarea `arreglo_diseno`); el diseño inicial sigue con Opus, como dice la decisión 32; d) el diseño inicial usa esfuerzo medio; e) la guía y los datos del diseñador van en el mensaje de sistema, en un archivo, para que el SDK los guarde en caché. Ajusta la decisión 32 b) y c) solo en el modelo de los arreglos (aprobado el 2026-10-16) |
| 42 | En `materiales/` quedan solo los archivos del profesor: el Word, el PowerPoint, el ZIP de práctica, el Excel de verificación y el registro de la ejecución del laboratorio. Lo que usa AulaLista (contenido, explicaciones, imágenes, figuras, archivos de práctica sueltos, el JSON del verificador, el programa del diseñador) va en `materiales/_trabajo/[material]/`. No se borra: lo necesitan reanudar, la revisión y la versión base del diseño. Ya no se escribe `S[n]_[Material]_Entrega.md`: la página muestra la entrega. Al iniciar, AulaLista lleva los cursos anteriores a esta forma (aprobado el 2026-10-16) |
| 43 | Caché en las correcciones de la lectura, las diapositivas y el laboratorio. Cada corrección mandaba otra vez el contexto, el formato y las reglas de corrección (unos 30 000 a 45 000 tokens) y casi nada salía de la caché. Ahora esa parte fija va en el mensaje de sistema, en `_trabajo/[material]/sistema_correccion.txt`, igual para todas las correcciones de una corrida; el pedido lleva solo cómo entregar, el material actual y los problemas. La redacción no cambia: es una sola llamada y sus turnos ya reutilizan la caché. La calidad no cambia: el modelo recibe el mismo texto (aprobado el 2026-10-16) |
| 44 | El curso como tablero. Cambia la decisión 38 c). a) La página del curso deja de ser «Preparación del curso» y pasa a ser un tablero: arriba, «Lo que sigue», con el paso pendiente, su motivo y un botón; debajo, cada sesión numerada con sus materiales como fichas que cambian de forma según el estado (aprobado, desactualizado o con fallas, sin generar). b) La preparación (fuentes y ficha del curso) se pliega en una línea cuando está lista; si no lo está, va abierta y arriba. c) El panel lateral queda solo con las sesiones: número, título en una línea y cada material como un punto de color con su nombre; el siguiente paso lleva un anillo magenta. d) Se suman cuatro tonos claros de los colores que ya existen (magenta suave, magenta para texto, verde suave y rojo suave), con su versión de noche. Se aplica en cuatro fases: datos, tablero, panel y revisión (aprobado el 2026-10-16) |
| 45 | La ficha se lee primero y se edita por sección. a) Una ficha confirmada se abre en modo de lectura: cada sección es una tarjeta con el resumen de sus campos (etiqueta y valor) y un botón «Editar». El laboratorio y la evaluación muestran una fila por ejercicio o pregunta. b) Se edita una sección a la vez, con «Guardar esta sección», «Cancelar» y el aviso de cambios sin guardar. El formulario sigue siendo uno y el servidor guarda la ficha entera, como antes. c) Una ficha sin confirmar se abre en edición, y una sección con campos «Falta definir» o con dos versiones se abre siempre en edición. d) El índice muestra el estado de cada sección (completa, vacía, con alertas o «no se usa»); la evaluación va apagada y plegada por la decisión 37. e) Sin JavaScript, todo se ve en edición. f) Cada sección se pliega con su flecha o su título, y hay «Plegar todas» y «Desplegar todas»; al abrir la página, una ficha confirmada aparece plegada entera y una sin confirmar pliega solo las secciones completas. En la sección abierta, «Editar» dice «Cancelar» y revierte lo cambiado (2026-10-17). Se aplica en cuatro fases: datos, plantilla, comportamiento y revisión (aprobado el 2026-10-16) |
| 46 | Cuatro materiales: vuelve la evaluación práctica (PBQ). Cambia la decisión 37. Los materiales de una sesión son la lectura, las diapositivas, el laboratorio y la evaluación práctica (PBQ) con su clave. La etapa 9 vuelve al plan y se construye con su propio plan, aprobado antes de empezar. Mientras no esté construida, la interfaz sigue diciendo que la evaluación no se genera. El SPEC §13 se mide contra estos cuatro materiales (aprobado el 2026-10-17) |
| 47 | Oraciones sin fuente alineadas con el material. Cambia la regla del SPEC §13 «Ninguna queda sin fuente». Una oración puede quedar sin pasaje de fuente si está alineada con el material: no contradice las fuentes ni las fichas, y no agrega cifras, estudios ni funciones inventadas. Sigue apareciendo en la entrega como decisión pendiente para que el profesor la vea, pero no impide aprobar. Toda afirmación sobre el contenido de una fuente sigue saliendo de un pasaje (aprobado el 2026-10-17) |
| 48 | El Excel de verificación solo con hallazgos. Cambia la regla del SPEC §13 «Cada oración de cada material tiene en el Excel su pasaje de fuente y su veredicto». El Excel queda solo con la hoja Hallazgos, como ya dicen CLAUDE.md y la decisión 22 (aprobado el 2026-10-17) |
| 49 | La ficha del curso no pide los materiales. Se quita «Materiales por sesión» de la sección 8 de la ficha del curso: los materiales de cada sesión se eligen en su ficha de sesión («Materiales de esta sesión»), que es la única que usa AulaLista. Es una excepción a la plantilla de la skill (FICHA DE CURSO, «8. Materiales»). Un valor guardado antes en ese campo se conserva, pero no se muestra ni se usa (aprobado el 2026-10-17) |
| 50 | Diseño integrado: los cursos en el panel. Cambia la decisión 44 c) y la página de inicio. a) El panel lateral muestra todos los cursos. Arriba, «Cursos» y el botón «Nuevo». Cada curso ocupa una línea con su nombre y su avance: «5 de 16» materiales aprobados y vigentes, «Sin ficha» si la ficha del curso no está confirmada, o «Completo» si todo está aprobado. Un punto rojo marca el curso que tiene un material con fallas. b) El curso abierto se despliega con sus sesiones, igual que hoy (número, título, cada material como punto de color y el anillo magenta en lo que sigue). Los demás cursos quedan plegados en su línea, y su nombre lleva a su tablero. c) La línea de cada curso lleva a su tablero, nunca a una ficha, para no lanzar una propuesta pagada sin querer al cambiar de curso. El curso abierto conserva su enlace «Ficha» en cada sesión, como en la decisión 44 (aclarado por el profesor el 2026-10-17). d) La dirección de inicio abre el último curso usado, guardado en `cursos/_sistema/ultimo_curso.txt`. Si no hay cursos, o el último ya no existe, se ve la página de inicio con el formulario para crear el primero. «Nuevo» lleva a una página corta con ese mismo formulario. e) Al pie del panel van el gasto del curso abierto y el gasto total de AulaLista. f) En pantallas angostas, el panel se esconde detrás de un botón «Cursos» y se cierra al elegir. Sin JavaScript, el panel se ve entero arriba de la hoja. Se aplica en cuatro fases: datos, panel, inicio y curso nuevo, y revisión (§4, «Fases de la decisión 50») (aprobado el 2026-10-17) |
| 51 | Un solo esquema para las correcciones de cada material. Completa la decisión 43. El SDK manda el esquema de la respuesta antes del mensaje de sistema, y cada forma de corregir (completa, por diapositivas o por ejercicios, por oraciones) tenía su propio esquema. Por eso ninguna corrección leía la caché: en el laboratorio de S3 (19/10) cada una volvió a escribir unos 35 000 tokens. Se comprobó con tres llamadas cortas: con otro esquema la caché no se lee; con el mismo, se lee entera y la llamada cuesta unas siete veces menos. El nivel de esfuerzo no rompe la caché. Ahora cada material tiene un esquema con una parte por forma de corregir; la corrección llena solo la que se le pide y deja las demás en null. La calidad no cambia: el modelo recibe el mismo contexto y las mismas reglas (aprobado el 2026-10-19) |
| 52 | Panel de cursos replegable y con buscador. Completa la decisión 50. a) En pantallas anchas, un botón junto a «Nuevo» repliega el panel a una franja angosta y la hoja de trabajo ocupa el resto. El mismo botón lo vuelve a mostrar. La elección se recuerda en el navegador. En pantallas angostas sigue el botón «Cursos» de la decisión 50 f. b) Debajo de «Cursos», un buscador filtra los cursos por su nombre, sin distinguir tildes ni mayúsculas. Si ninguno coincide, lo dice. Enter abre el primero que coincide y Escape borra la búsqueda. c) Los dos los pone JavaScript; sin él, el panel se ve entero, como hoy. No gasta tokens (pedido por el profesor el 2026-10-19) |
| 53 | «Repartir las sesiones» y su cobertura. Cambia la decisión 28 b) para las sesiones y completa la 36 c). a) El botón «Completar las sesiones» pasa a llamarse «Repartir las sesiones». Pide el nombre, las horas y el número de sesiones, y reemplaza lo que haya en «Sesiones», marcado «Propuesto». b) Criterio: cubrir todo el contenido de las fuentes si cabe en las horas de cada sesión (horas del curso entre número de sesiones). Si no cabe, se eligen los temas más importantes y queda fuera lo secundario. Las sesiones siguen los capítulos y el orden de las fuentes. c) Por cada sesión, la IA devuelve los tramos de páginas de cada fuente que cubre. Un programa, no la IA, calcula la cobertura: páginas con texto cubiertas entre páginas con texto de las fuentes del curso. Descarta los tramos de archivos que no son fuentes del curso y las páginas que no existen. d) La ficha muestra debajo de «Sesiones» el porcentaje, las páginas que quedan fuera de cada fuente y las páginas de cada sesión. Si el profesor cambia las sesiones después, la ficha dice que la cobertura ya no vale. El porcentaje no llega a ningún material. e) En «Herramientas», la pregunta de los archivos adjuntos solo se muestra si la herramienta de los ejercicios es IA o Excel e IA. f) Una fuente con texto leído por la IA que el profesor no revisó no la recibe la IA, pero sus páginas cuentan en el total como no cubiertas. La ficha avisa antes de repartir, con un enlace a la fuente. g) El programa reconoce el nombre de la fuente aunque la IA cambie mayúsculas, espacios o la extensión. Los tramos que no cuentan se muestran con su motivo, y el mensaje avisa de cada sesión sin páginas. Gasta tokens solo al pulsar el botón (aprobado el 2026-10-20) |
| 54 | Ficha corta de la sesión. Es una excepción a la skill («Ficha de la sesión», paso 2: el profesor confirma lo propuesto antes de redactar). a) La ficha de la sesión muestra arriba solo lo que decide el profesor: la sección «1. Sesión» y «6. Materiales de esta sesión». b) Un programa, sin IA, llena los campos vacíos de «1. Sesión» con la ficha del curso al abrir la ficha: número y título, alcance, lo ya visto (títulos de las sesiones anteriores), lo que no se adelanta (títulos de las siguientes) y, si la cobertura de la decisión 53 sigue valiendo, el material de referencia con las páginas de la sesión. Se llenan antes de la propuesta, así la IA no los cambia. Lo que el profesor escribió no se toca, y una ficha confirmada no cambia. c) Lectura, vocabulario, laboratorio y evaluación forman el «Plan de la sesión»: lo prepara AulaLista y va plegado debajo. Se abre solo si tiene campos por definir o la ficha tiene errores, y el índice lo abre al ir a una de sus secciones. Las preguntas pendientes son solo de la ficha corta. d) Los campos del plan siguen en la ficha y en la plantilla de la skill: los materiales y el verificador los leen igual. e) Fase 2: en la ficha de la sesión, «Guardar» hace todo en un paso. Si falta algo de la ficha corta, lo dice sin gastar. Si el plan no alcanza para producir la lectura, las diapositivas o el laboratorio de la sesión, o le falta el vocabulario, la IA llena solo lo vacío. Después acepta lo propuesto, revisa los ejercicios y, si la revisión encuentra problemas, los corrige una vez, acepta la corrección y revisa de nuevo. Si todo cumple, confirma; si no, lo que quede se muestra y el botón «Corregir los ejercicios» sigue disponible. La ficha de la sesión ya no se propone sola al abrirla (cambia la decisión 17 para la sesión) y no tiene los botones «Aceptar lo propuesto y guardar» ni «Proponer desde las fuentes». El profesor no revisa el plan antes de redactar; queda disponible para revisarlo (aprobado el 2026-10-21) |
| 55 | Confirmar la ficha de la sesión no es un paso aparte. Completa la decisión 54. a) Para generar un material basta la ficha del curso confirmada. Si la ficha de la sesión no está confirmada, «Generar» primero la llena desde la ficha del curso y hace lo mismo que «Guardar» en ella: prepara el plan, lo acepta, revisa y corrige una vez los ejercicios y confirma. Después genera el material. b) Si algo impide confirmarla, no genera: lleva a la ficha de la sesión con lo que falta. c) La página del material avisa antes que ese paso gasta tokens y tarda unos minutos más, y el botón dice «Preparando la ficha de la sesión…» mientras trabaja. d) Al abrir una sesión se va a su material, no a su ficha. La regla de la skill «no empieces la lectura sin la ficha de la sesión confirmada» se sigue cumpliendo: la ficha se confirma antes de redactar (pedido por el profesor el 2026-10-21) |
| 56 | Diseño de las diapositivas con más libertad y menos descartes. Cambia las decisiones 30 d), 32 c) y d) y 41 c). Medición previa (Agilidad Empresarial S1): el diseño se descartó entero por una diapositiva que se pasaba 0,3 cm, la revisión visual nunca corrió y los arreglos con Sonnet no vieron la causa. a) Por diapositiva, no todo o nada: si al final quedan diapositivas con fallas y cada falla nombra la suya, esas van en su versión base y el resto queda diseñado; la mezcla se mide y se verifica, y lo abierto va a «Decisiones pendientes». Si no se puede, se entrega toda la versión base, como antes. Para que las dos versiones se puedan mezclar, el diseñador dibuja en el tamaño de la base (13,333 × 7,5 pulgadas). b) Revisión visual con Opus, hasta dos veces: la primera sobre el primer diseño que se mide, aunque tenga fallas; la segunda sobre un diseño sin fallas. Mira todas las diapositivas, también la portada y el cierre, y no propone quitar texto ni pasarlo a las notas. c) Los arreglos van con Opus y reciben la imagen de cada diapositiva con problemas; el programa se mide aunque falle un control. Hasta cuatro arreglos, contando los de la revisión visual. d) Etiquetas de ocho palabras como máximo. e) La guía del diseñador deja solo como reglas fijas los colores y la tipografía de la ficha, el color de advertencia en «Cuidado con», la letra mínima, los márgenes y que nada se salga de su recuadro. Los tamaños (hasta 44 puntos para una frase o una cifra destacada), las composiciones, los íconos, la etiqueta del bloque y el pie pasan a ser ideas, no obligaciones. f) El redactor escribe 40 palabras visibles como máximo por diapositiva de concepto y en la idea central, sin el título; lo demás va a las notas. En las cuatro sesiones generadas, la mediana iba de 42 a 60 palabras y las tablas llegaban a 123. g) La versión base dibuja la frase de introducción de las columnas y el título de las tablas, que omitía. Costo estimado: de 2 a 2,5 dólares más por sesión en las diapositivas (aprobado el 2026-10-21) |
| 57 | Actividad web con diseño a medida. Cambia la decisión 34. Referencia: «Del dato a la acción», Data Storytelling S1. a) Vuelve un quinto material, la «actividad web»: una página HTML que el alumno recorre por pasos para reforzar el tema de la sesión. Es distinta de la práctica interactiva de la skill («Material 5»): no tiene estaciones; tiene un caso propio y de 4 a 6 pasos. Los materiales de una sesión son la lectura, las diapositivas, el laboratorio, la actividad web y la evaluación práctica (PBQ). b) Solo preguntas cerradas: opción única, opción múltiple, ordenar, relacionar y clasificar. No hay respuestas abiertas ni IA en la página. Cada pregunta tiene una sola respuesta correcta y cada opción, correcta o incorrecta, trae su explicación. El alumno puede intentar otra vez. c) Puntajes solo en este material. Cada pregunta tiene sus puntos y la página los suma sola. La página dice que el puntaje es una orientación y que la nota la pone el profesor. Los tiempos siguen prohibidos: un minuto o una duración es FALLA, como en los demás materiales. Es una excepción al SPEC §6 y a la skill («Ningún material muestra tiempos ni puntajes»). d) Contenido como datos: el redactor escribe el caso, sus cifras, los pasos, las preguntas, las opciones, las explicaciones, la respuesta correcta, los puntos y los recuadros «Recuerde». El verificador y la revisión del contenido lo aprueban antes del diseño. La fuente de la revisión es la lectura validada y las fichas; el caso es ficticio, con sus cifras en los datos fijos. e) Diseño a medida, sin plantilla: con el contenido aprobado, un agente diseñador (Opus) escribe la página completa, con el CSS y el JavaScript dentro y solo los colores y la tipografía de la ficha. La página lleva el contenido aprobado tal cual en un bloque `<script type="application/json" id="contenido">` y lo dibuja desde ahí. f) Controles del diseño: el bloque de contenido es idéntico al aprobado; todo texto visible sale del contenido, salvo etiquetas de ocho palabras como máximo («Anterior», «Comprobar»); sin scripts ni hojas externas, salvo las fuentes de Google; sin `fetch`, `XMLHttpRequest`, `WebSocket`, `eval` ni `import`; sin tiempos. Después, Playwright recorre la página (sección 5.7). El diseñador corrige hasta tres veces; si quedan fallas, la actividad no se entrega y las fallas van a «Decisiones pendientes». g) Se entrega solo el archivo HTML en `materiales/`, sin publicar (contradicción 4). El avance se guarda en el navegador del alumno, con una clave por curso y sesión y dentro de `try/catch`. El último paso pide el nombre, muestra las respuestas, los intentos y el puntaje, y trae «Copiar mi entrega» y «Borrar mis respuestas» con confirmación. h) Cambia la regla de CLAUDE.md «el agente no escribe HTML a mano», solo para el diseño de la actividad web, y la regla «sin tiempos ni puntajes», solo para los puntajes de este material. CLAUDE.md, SPEC.md y SKILL.md se actualizan al aprobar esta decisión (aprobado el 2026-10-21) |
| 58 | Títulos en magenta, como pide la marca FuturaSoft. Cambia la decisión 38 d). Los títulos h1 y h2 de las páginas van en magenta y negrita. El magenta sigue siendo el color de lo que se puede pulsar; los títulos se distinguen por su tamaño, su peso y porque no llevan subrayado. Las etiquetas pequeñas (como «Cursos» en el panel) y los nombres de curso que son enlaces siguen en tinta (aprobado el 2026-10-21) |
| 59 | Puntaje de la actividad web sobre 100. Cambia la decisión 57 c) y d). El redactor sigue dando a cada pregunta un número entero de 1 a 3, que ahora es su peso frente a las demás. AulaLista, sin IA, convierte los pesos en puntos enteros que suman exactamente 100, en proporción a cada peso: cada pregunta recibe la parte entera de su proporción y los puntos que faltan van a las de mayor resto (a igual resto, a la primera). Ninguna pregunta queda en cero. La página del alumno y la vista del profesor muestran esos puntos, y la entrega dice, por ejemplo, «82 de 100 puntos». Las actividades ya generadas toman los puntos nuevos cuando se vuelve a diseñar su página (aprobado el 2026-10-21) |
| 60 | Listas de opciones en los Excel del laboratorio. Completa la sección «Material 3» de la skill. a) Una celda donde el alumno escribe su respuesta puede llevar una lista de opciones (validación de datos de Excel: la celda solo acepta un valor de la lista). Solo cuando la respuesta es una de un conjunto cerrado: una categoría, un concepto del vocabulario, un área del caso o «Sí» y «No». Las respuestas abiertas (una explicación, un cálculo, un texto) no llevan lista. b) La marca la pone el redactor en los datos, no se adivina: cada hoja del Excel puede traer «listas», y cada lista dice la columna (uno de sus encabezados) y sus opciones. Sin «listas», el archivo sale como hoy. c) Las opciones no delatan la respuesta: dos como mínimo, sin repetidas, y cada respuesta de la guía del profesor para esa columna está entre ellas. Cada opción sale del vocabulario de la sesión, de los datos fijos del caso o es «Sí» o «No», escrita igual. Las del vocabulario van en el orden de la fuente. d) El generador de `app/materiales/practica.py`, sin IA, pone las opciones en una hoja visible llamada «Opciones», una columna por lista con su encabezado, y aplica la lista a las filas de datos de esa columna. La celda puede quedar vacía. Si el alumno escribe otra cosa, Excel lo detiene con un mensaje fijo de AulaLista: «Elige una opción de la lista.». La hoja «Opciones» no cuenta como respuesta en la regla «respuestas solo en la guía del profesor y en la clave», porque trae todas las opciones y no dice cuál es la correcta. e) La guía del alumno dice en el paso que elige su respuesta de la lista de la celda, sin nombrar menús ni botones (neutralidad). Las figuras no cambian: se sacan del archivo real y no muestran la lista. f) No se ponen listas si la sesión enseña a crear listas o validación de datos en Excel: ahí la lista le haría el trabajo al alumno. El programa lo decide con el título y el alcance de la ficha de la sesión. g) Solo el laboratorio. La evaluación práctica (PBQ) y la actividad web no cambian. Los laboratorios ya generados cambian solo si se vuelven a generar. Costo: unas pocas líneas más en la respuesta del redactor. h) Pruebas sin IA (`pytest`): el modelo `Hoja` rechaza una lista con una columna que no existe, con menos de dos opciones o con opciones repetidas; el Excel creado, leído con `openpyxl`, tiene la hoja «Opciones» visible y en orden, la validación de tipo lista sobre las filas de la columna correcta, celdas vacías permitidas y el mensaje fijo; un archivo sin «listas» no tiene validaciones ni hoja «Opciones»; Excel abre el archivo con `app/office.py`, la celda tiene su lista y la aplicación se cierra. i) Sembrados en `tests/sembrados/laboratorio.py`, cada uno con un solo error y su FALLA o AVISO en la fila correcta: lista a la que le falta una respuesta de la guía del profesor (FALLA); lista con una sola opción (FALLA); opciones del vocabulario en otro orden que la fuente (FALLA); una opción con una variante prohibida del vocabulario (FALLA); una opción que no sale del vocabulario, de los datos fijos ni es «Sí» o «No» (FALLA); lista en una columna de respuesta abierta, con respuestas de más de cinco palabras o fuera de la lista (FALLA); lista en una sesión que enseña validación de datos (FALLA); paso de la guía que no dice que se elige de la lista (AVISO). Control limpio: un laboratorio con listas bien puestas queda con cero fallas, también en la regla de respuestas separadas (aprobado el 2026-10-21) |
| 61 | Opciones de las listas con menos restricciones. Cambia la decisión 60 c). La regla anterior pedía que cada opción fuera un concepto del vocabulario, un dato fijo, un área del caso, «Sí» o «No». Dejaba fuera listas útiles, como «Alto», «Medio» y «Bajo». a) Ahora una opción vale si aparece escrita en la ficha del curso o en la de la sesión, en «Antes de empezar» del laboratorio (sus tablas y reglas), o en los datos del mismo archivo de práctica. No importan las mayúsculas. Los pasos de la guía no cuentan, para que el redactor no justifique una opción que él mismo inventó. b) Una opción que no aparece en ninguno de esos lugares ya no es FALLA: es un AVISO del verificador, que se corrige o se explica. c) Siguen siendo FALLA: la respuesta que falta en la lista, una sola opción, las opciones repetidas, una variante prohibida del vocabulario, los conceptos fuera del orden de la fuente, la respuesta abierta y la lista en una sesión que enseña validación de datos. d) Pruebas: una opción tomada de la ficha, otra de una tabla de «Antes de empezar» y otra de los datos del archivo pasan sin avisos; una opción que no aparece en ningún lado da AVISO y no FALLA; una opción que solo aparece en un paso da AVISO (pedido por el profesor el 2026-10-21) |
| 62 | Orden de las opciones solo en los procesos. Cambia la decisión 60 c) y la 61 c). Las opciones de una lista ya no tienen que seguir el orden del vocabulario. El orden se exige solo cuando las opciones son los pasos de un proceso o de una secuencia ordenada. a) En la ficha de la sesión, el profesor escribe «(proceso)» junto a cada concepto del vocabulario que forma parte de un proceso: «2. Planificación del Sprint (proceso)». Los conceptos marcados seguidos forman un proceso, en el orden del vocabulario. La marca no es parte del nombre del concepto. b) También son procesos los pasos ordenados del material ya aprobado de la sesión: los pasos de una diapositiva de tipo «proceso» o «pasos», y las líneas numeradas («1.», «2.»…) de «Aplícalo así» de la lectura. c) Si dos o más opciones de una lista son pasos del mismo proceso, van en el orden de ese proceso; si no, es FALLA. Las demás opciones van en cualquier orden. d) Es una excepción, solo para las listas, a la regla «Vocabulario único: mismo nombre y mismo orden en todos los materiales». El nombre único sigue siendo obligatorio, y los demás materiales siguen con el orden de la fuente. e) Pruebas: la ficha lee la marca «(proceso)» y la quita del nombre; conceptos sin marca en otro orden pasan; conceptos marcados en otro orden dan FALLA; los pasos de una diapositiva de proceso aprobada en otro orden dan FALLA; las líneas numeradas de «Aplícalo así» forman un proceso (pedido por el profesor el 2026-10-21) |
| 63 | La ficha confirmada se abre desplegada. Cambia la decisión 45 f. a) Al abrir una ficha confirmada, todas sus secciones aparecen desplegadas en modo de lectura; solo la que no se usa (la evaluación, decisión 37) queda plegada. Una ficha sin confirmar sigue plegando solo las secciones completas. b) «Editar» se ve solo en una sección desplegada; plegada, la sección es su cabecera con el título y el estado en palabras. c) El índice fijo mide su alto real, para no tapar el inicio de la sección a la que lleva un enlace. d) Cada flecha de plegar dice a los lectores de pantalla el nombre de su sección. e) En el resumen, los elementos de un campo de varias líneas (sesiones, conceptos, archivos) se separan con «;» (crítica de la interfaz; aprobado el 2026-10-21) |
| 64 | Evaluación práctica (PBQ) y su clave (etapa 9). Completa la decisión 46. a) La evaluación se genera después de la lectura y del laboratorio aprobados y al día, si la sesión los incluye: no evalúa nada que no hayan enseñado. b) Contenido según la skill («Material 6»): 3 preguntas, o las de la ficha; cada una evalúa un concepto del vocabulario, usa el caso del curso con archivos y datos nuevos, pide una tarea de la lista de la skill, funciona sola y tiene una sola respuesta correcta o una lista cerrada en la clave. Sin minutos, puntos, notas ni porcentajes. c) Tamaño: un programa cuenta las palabras de la situación y de los archivos de texto de cada pregunta (250 como máximo), las filas de cada tabla (15 como máximo) y las celdas que el alumno llena en su tabla de respuesta: cada celda es una decisión (10 como máximo). d) Salidas: la hoja del alumno `S[N]_Evaluacion.docx`, la clave `S[N]_Evaluacion_Clave.docx`, los archivos `S[N]_P[pregunta]_[descripcion].xlsx` o `.docx` en `S[N]_Evaluacion_Archivos.zip`, aparte del .zip del laboratorio, y `S[N]_Evaluacion_Verificacion.xlsx`. e) Cada pregunta se resuelve como un alumno, igual que un ejercicio a mano (decisión 36 d): una conversación nueva con Claude, sin herramientas, con la situación, la tarea y el texto de sus archivos, sin la clave. Lo que sale se compara con la clave y con la respuesta de la ficha; cada diferencia trae su prueba copiada y la que no la tiene se descarta (decisión 35 d). f) Respuestas separadas: un programa comprueba que ninguna respuesta de la clave aparezca en la hoja del alumno, en sus archivos (salvo el problema sembrado), en la guía del laboratorio ni en la actividad web aprobada, y que ninguna pregunta use un archivo de práctica del laboratorio. g) Cambia la decisión 62 b) y d): los campos de la evaluación y sus preguntas desactualizan la evaluación, y una lectura o un laboratorio nuevos también. h) El plan de la sesión (decisión 54) cuenta las preguntas de la evaluación solo si la sesión la incluye, y la revisión de ejercicios al guardar revisa también las preguntas. i) La ficha deja de mostrar la evaluación como «No se usa» (aprobado el 2026-10-22, con las cuatro respuestas recomendadas: requisito de lectura y laboratorio, cambio de la decisión 62, plan de la sesión y celdas como decisiones) |
| 62 | Cada material se desactualiza solo por lo que usa. Cambia la regla de §2 «si una ficha cambia, el material queda desactualizado». a) Al generar un material, AulaLista guarda lo que usó: los valores de las dos fichas y la huella de cada fuente. b) Se compara solo lo que le corresponde. Desactualizan los cuatro materiales: título, alcance, «ya vieron», «no adelantar», material de referencia y exclusiones de la sesión; el renglón de esa sesión en «Sesiones»; el vocabulario; el público, el caso, el idioma y el nombre del curso; la identidad visual, los modelos y «lo que nunca se incluye»; la fecha de referencia; el contenido de una fuente que la sesión usa. Solo la lectura (y por ella las diapositivas): los bloques, el ejemplo, «Aplícalo así» y «Cuidado con». Solo el laboratorio: los ejercicios y las herramientas. Lectura, diapositivas y laboratorio: la portada. Ninguno: la evaluación y sus preguntas, las horas, el número de sesiones y «Materiales de esta sesión». c) Datos fijos: agregar una línea no desactualiza; cambiar o quitar una línea desactualiza los cuatro. d) Una lectura nueva desactualiza las diapositivas, el laboratorio y la actividad. e) Se revisa al confirmar una ficha y al convertir las fuentes; si lo usado vuelve a coincidir, el material deja de estar desactualizado. f) El aviso dice solo lo que lo desactualizó. Un material generado antes de esta decisión toma lo que usó de la versión de las fichas guardada en su fecha (aprobado el 2026-10-21) |

### Contradicciones encontradas

1. **Rondas del revisor.** El SPEC fija tres rondas y la skill no pone tope. Se resolvió con la decisión 1.
2. **Reconocimiento de texto.** El SPEC §7 pide reconocimiento de texto para imágenes. El SPEC §9 dice que la IA lee las imágenes. No hay programa de reconocimiento instalado. Claude lee las imágenes y el profesor revisa el resultado.
3. **Dónde buscar la ficha.** La skill busca en "instrucciones del proyecto", "memoria" y "adjuntos". En AulaLista se busca en la carpeta del curso.
4. **Publicar la práctica interactiva.** La skill la publica si el entorno lo permite. El Agent SDK no publica páginas. Se entrega solo el archivo HTML.
5. **Excel modelo contra la skill.** El modelo marca "coincide" en 387 filas sin pasaje. La skill lo prohíbe. Se resolvió con la decisión 2.
6. **Llenado de la ficha.** La skill dice que primero se leen los archivos. El profesor decidió llenar la ficha en un formulario. Se resolvió con la decisión 4: el formulario manda y la propuesta desde las fuentes es un botón.
7. **Guía del diseñador contra sus controles (decisión 32).** En Agilidad Empresarial S1 el diseño se descartó entero y nunca llegó a la revisión visual. Cuatro contradicciones, corregidas con la aprobación del profesor (2026-10-21), sin cambiar la decisión 32: a) la guía pedía etiquetas como «1 · Qué es el gobierno de datos» y el control contaba el número y el «·» como palabras: ahora no cuentan, y un tramo unido con «·» que sale del contenido o de la portada tampoco; b) la guía pedía el pie con el curso y la sesión y el control solo los aceptaba por separado: se resuelve con lo mismo; c) la guía pedía bullet en cada elemento y resaltar palabras con varios trozos, y pptxgenjs hace una viñeta por trozo: la guía dice ahora bullet solo en el primer trozo, y un control nuevo devuelve al diseñador la frase partida en varias viñetas; d) la revisión visual podía proponer pasar texto a las notas, que se copian del contenido sin IA, y el texto se perdía: la revisión ya no lo propone, y un control nuevo devuelve al diseñador el texto del contenido que no aparece en su diapositiva. Los encabezados de una tabla se pueden omitir.

Defectos del Excel modelo que no se copian:

- En la hoja "Datos repetidos", cada oración empieza con una "L" de más: `LS1_Laboratorio.docx`.
- Los nombres de sección están cortados en 40 letras. AulaLista escribe el nombre completo.
- La columna "Revisor independiente" está vacía. AulaLista la llena.

### Lo que no se puede construir como está escrito

1. **Pagar con el plan Max.** La documentación del SDK dice: *"Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK."* Se resolvió con la decisión 3.
2. **"Créditos mensuales del plan Max".** No hay documentación de créditos de API incluidos en el plan Max. El profesor debe revisar la facturación en la consola de Anthropic.
3. **Ejecutar cada ejercicio "como un alumno".** Se ejecutan los prompts en una conversación nueva con Claude, sin herramientas. Se ejecutan las fórmulas de Excel con el Excel instalado. Un ejercicio a mano lo hace Claude como alumno, con el texto de sus archivos (decisión 36). Los comandos y otros programas quedan en "Qué no pude probar".
4. **Ciclo sin fin.** El verificador tiene un tope de tres correcciones y la revisión del contenido, una sola (decisión 22). Después, el software muestra lo que queda abierto.
5. **"El profesor no tiene que buscar ningún error".** La validación con IA no lo garantiza al 100 %. El plan mide cuántos errores puestos a propósito detecta.

## 1. Arquitectura

```
 Navegador (página local)
        │  pedidos y avance en vivo
        ▼
 Servidor local (FastAPI)
        │
        ▼
 Orquestador ── estado.json de cada sesión
   │
   ├─► Conversor de fuentes ──► fuentes_texto/   (sin IA, salvo imágenes)
   ├─► Agente redactor (Agent SDK + skill)
   │       └─ escribe contenido.json de cada material
   ├─► Generadores de archivos ──► Word, PowerPoint, Excel, HTML, .zip
   ├─► Verificador (verificar.py, sin IA) ──► Excel de verificación
   ├─► Pasadas 1 y 2 (SDK, oraciones en grupos) ──► columnas del Excel
   ├─► Ejecutor de ejercicios (SDK sin herramientas, Excel)
   └─► Revisor independiente (sesión nueva del SDK, solo lectura)

 Office instalado (Word, PowerPoint, Excel): PDF, imagen de cada página o
 diapositiva, conteo de páginas y recálculo de fórmulas.
 Todo se guarda en cursos/[curso]/.
```

| Componente | Qué hace |
|---|---|
| Página local | Formularios de las fichas, avance de cada paso, aprobación y descarga |
| Servidor local | Recibe las acciones del profesor y envía el avance al navegador mientras ocurre |
| Orquestador | Sigue el flujo del SPEC §5. Guarda en `estado.json` el paso de cada material. Si el programa se cierra, continúa desde ese paso |
| Agente redactor | Escribe el contenido de cada material como datos estructurados, no como Word |
| Generadores de archivos | Aplican siempre el mismo diseño. Una corrección cambia solo el texto |
| Conversor de fuentes | Convierte cada fuente a texto una sola vez. Guarda cada pasaje con su página, lámina o celda |
| Verificador | Revisa lo mecánico. No usa IA y no cuesta tokens |
| Pasadas y revisor | Revisan el significado con IA |
| Ejecutor | Ejecuta cada ejercicio y cada pregunta con sus archivos |

Comunicación:

- El orquestador llama a cada componente como función de Python.
- El agente usa tres herramientas propias: `buscar_en_fuentes`, `leer_ficha` y `verificar`.
- El orquestador ejecuta el verificador directamente, sin tokens. El agente también puede llamarlo como herramienta.

## 2. Tecnología

| Pieza | Elección y versión | Razón |
|---|---|---|
| Lenguaje | Python 3.13 | Un solo lenguaje para todo. El verificador tiene que ser Python |
| SDK | `claude-agent-sdk` 0.2.165 | Pedido en el SPEC. Incluye Claude Code, así que no hace falta Node |
| Clave | `python-dotenv` 1.2.4 | Lee el `.env` y pasa la clave al SDK con su opción `env`, sin variable de Windows |
| Servidor | `fastapi` 0.143.0, `uvicorn` 0.54.0, `jinja2` 3.1.6 | Es la forma más simple de tener una página local con Python |
| Avance en vivo | `sse-starlette` 3.5.0 | El servidor manda mensajes al navegador sin que este pregunte cada segundo |
| Página | HTML y JavaScript simples, sin framework | Un solo usuario y pocas pantallas |
| Word | `python-docx` 1.2.0 | Lee y escribe .docx con estilos reales de título |
| PowerPoint | `python-pptx` 1.0.2 | Lee y escribe .pptx con notas del profesor |
| Excel | `openpyxl` 3.1.5 | Escribe el archivo de verificación con el formato del modelo |
| PDF | `pymupdf` 1.28.2 | Texto por página e imagen de páginas escaneadas. Su licencia AGPL no afecta el uso personal |
| Office | `pywin32` 312 | Controla el Word, PowerPoint y Excel instalados: PDF, imágenes, páginas, desbordes y recálculo |
| Búsqueda de pasajes | `rapidfuzz` 3.14.6 | Encuentra el pasaje más parecido a cada oración sin IA |
| Imágenes del laboratorio | `pillow` 12.3.0 | Dibuja la tabla real del archivo de práctica con marcas de color ámbar |
| Prueba de la página HTML | `playwright` 1.63.0 | Prueba la práctica en tamaño computadora y celular, en modo claro y oscuro |
| Datos y esquemas | `pydantic` 2.14.0 | Comprueba que lo que escribe la IA tiene la forma esperada |
| Pruebas | `pytest` 9.1.1 | Pruebas automáticas |

El separador de oraciones es propio, de unas 60 líneas. `pysbd` no se actualiza desde 2021 y el texto lo generamos nosotros con una puntuación controlada.

Funciones del SDK confirmadas en su documentación:

- `query()` y `ClaudeSDKClient`;
- las opciones `setting_sources`, `allowed_tools`, `model`, `max_turns`, `max_budget_usd`, `output_format`, `env`, `agents` y `mcp_servers`;
- los decoradores `@tool` y `create_sdk_mcp_server`;
- el campo `usage` y el costo estimado `total_cost_usd` en el resultado final.

La skill no se carga con el SDK: AulaLista lee de `SKILL.md` las secciones de cada material y se las pasa al redactor (decisión 6).

## 3. Estructura de carpetas

```
aulalista/
├── .env  .env.example  .gitignore  CLAUDE.md  PLAN.md  SPEC.md  requirements.txt
├── .claude/skills/material-de-clase/
│   ├── SKILL.md
│   └── scripts/verificar.py        donde la skill lo espera
├── config/
│   ├── lenguaje_ia.txt             frases prohibidas, se puede ampliar
│   ├── relleno.txt  imprecisas.txt
│   └── modelos.toml                modelo y tope de gasto por tarea
├── app/
│   ├── servidor.py  orquestador.py  agente.py  herramientas.py  tokens.py  office.py
│   ├── fuentes/convertir.py
│   ├── fichas/                     formularios, versiones y propuesta desde fuentes
│   ├── materiales/                 contenido.py (esquemas), docx.py, pptx.py,
│   │                               xlsx.py, html.py, imagenes.py, zip.py
│   ├── validacion/                 pasada1.py, pasada2.py, revisor.py,
│   │                               ejecutor.py, ciclo.py, excel.py
│   └── entrega.py                  formato de entrega del SPEC §8
├── web/plantillas/  web/estaticos/
├── tests/
│   ├── unidad/  integracion/
│   ├── fixtures/                   curso ficticio pequeño
│   ├── sembrados/                  materiales con errores puestos a propósito
│   └── ia/                         pruebas que gastan tokens, se corren aparte
└── cursos/[curso]/                 lo que pide el SPEC §9, más tokens.jsonl
                                    y fichas/versiones/
```

`cursos/` no se sube al repositorio. Tiene fuentes con derechos de autor y archivos pesados.

## 4. Etapas

Cada etapa termina con sus pruebas en verde y un commit.
Respecto del SPEC §12, el orden cambia en dos puntos:

- **El verificador va antes que las fichas.** No usa IA y es el centro de la validación. La etapa de fichas escribe un `verificacion.json` que ya se puede comprobar.
- **Las etapas 5 y 7 se dividen.** Así cada etapa es pequeña.

| N.º | Etapa | Lo que el profesor puede probar |
|---|---|---|
| 1 | Base: SDK, `.env`, registro de tokens, página mínima | Abre la página, pulsa "Probar conexión" y ve la respuesta de Claude con los tokens que gastó |
| 2 | Fuentes a texto | Sube un PDF, un Word, un Excel, un PowerPoint y una imagen. Ve cada pasaje con su página, lámina o celda |
| 3 | Verificador y `verificacion.json` | Corre `python verificar.py` sobre un Word de prueba y recibe el Excel de cuatro hojas igual al modelo |
| 4 | Fichas: formularios, edición con versiones y propuesta desde las fuentes | Llena, guarda, edita y recupera una versión anterior. El botón propone datos marcados "(propuesto)" con su archivo |
| 5a | Lectura en Word | Recibe la lectura con la identidad visual, en seis páginas como máximo y sin fallas del verificador |
| 5b | Primera pasada | Cada oración trae tipo, pasaje y veredicto en el Excel |
| 5c | Segunda pasada | Las hojas "Datos repetidos" y "Segunda pasada" quedan llenas |
| 5d | Revisor, ciclo y entrega | Recibe la lectura en el formato del SPEC §8 y la aprueba desde la página |
| 6 | Diapositivas | Recibe un PowerPoint de 14 a 18 diapositivas, con notas y sin texto desbordado |
| 7a | Laboratorio, archivos e imágenes | Recibe la guía, el .zip y las figuras sacadas de los archivos reales |
| 7b | Ejecución de los ejercicios (sin guía del profesor, decisión 35) | La entrega del laboratorio dice qué coincide con la ficha y el registro muestra lo que salió al ejecutar cada ejercicio |
| 8 | Actividad web (decisión 57) | Recibe una página HTML con diseño propio, solo preguntas cerradas y puntaje, que funciona sin conexión en computadora y celular |
| 9 | Evaluación y clave | Vuelve con la decisión 46. Pendiente: se construye con su propio plan aprobado |

Fases de la etapa 8 (decisión 57). Cada fase termina con sus pruebas en verde y un commit. Ninguna empieza sin la aprobación del profesor.

| Fase | Qué se hace | Pruebas | Lo que el profesor puede probar |
|---|---|---|---|
| 8a. Contenido | Modelo de datos de la actividad (`pydantic`): caso, cifras, pasos, preguntas por tipo, opciones con explicación, respuesta correcta, puntos y «Recuerde». La actividad web vuelve a «Materiales de esta sesión». Redactor con las reglas de la decisión 57 en SKILL.md. El verificador acepta puntos solo en este material y sigue dando FALLA por tiempos | Sin IA: un contenido válido pasa. Sembrados: un tiempo, un puntaje fuera de este material, una pregunta de opción única con dos correctas o sin ninguna, una opción sin explicación, puntos en cero, una cifra que no suma con el caso, una respuesta abierta | Genera el contenido de una sesión y lo lee en AulaLista, con sus cifras y su puntaje total |
| 8b. Validación del contenido | Primera y segunda pasada sobre el contenido, contra la lectura validada y las fichas, con una sola corrección (decisión 22). Un programa rehace las sumas y los porcentajes del caso | Sin IA: las sumas del caso. Con `pytest -m ia`: una pregunta con dos respuestas defendibles y un dato que contradice la lectura se detectan; una paráfrasis no se marca | Ve en la entrega los hallazgos de la revisión y lo que quedó pendiente |
| 8c. Diseñador | Agente diseñador (Opus) con su guía, que escribe la página completa. Controles estáticos de la decisión 57 f). Hasta tres correcciones con el informe de Playwright y una captura de cada paso con fallas | Sin IA: los controles rechazan una página con `fetch`, un script externo, un texto que no está en el contenido, un bloque de contenido cambiado y un tiempo. Con `pytest -m ia`: una página real pasa los controles | Abre la página en el navegador y la recorre completa |
| 8d. Pruebas en navegador | Playwright recorre la página (sección 5.7) y escribe su informe en la entrega | Sin IA: la referencia corregida pasa; sembrados con un botón de 30 px, un desborde en celular, un error de JavaScript, un puntaje mal sumado y un avance que no se recupera al recargar | Ve en la entrega qué revisó Playwright en cada tamaño y modo |
| 8e. Entrega e interfaz | El HTML en `materiales/`, la entrega del SPEC §8, el estado en el tablero y el costo de la corrida. Se actualizan CLAUDE.md, SPEC.md y SKILL.md | Pruebas de las páginas existentes en verde. El tablero muestra la actividad con su estado | Genera la actividad de una sesión real desde el tablero y la abre desde `materiales/` |

Costo: el diseñador escribe una página completa con Opus. Medido al cerrar la fase 8c, con el contenido de prueba de 4 pasos y 5 preguntas: 0,90 USD en 2 llamadas (diseño y un arreglo), unos 5 minutos. El recorrido en el navegador (fase 8d) no gasta tokens y tarda unos 10 segundos por página.

Estado: las fases 8a a 8e están terminadas (2026-10-21). CLAUDE.md, SPEC.md y SKILL.md ya dicen las dos excepciones de la decisión 57: los puntos de la actividad web y su página escrita en HTML por el diseñador.

Fases de la etapa 9 (decisión 64, aprobada el 2026-10-22). Cada fase termina con sus pruebas en verde y un commit. Ninguna empieza sin la aprobación del profesor. Las fases 9a y 9b no gastan tokens.

| Fase | Qué se hace | Pruebas | Lo que el profesor puede probar |
|---|---|---|---|
| 9a. Contenido y fichas | Modelo de datos (`pydantic`) de la evaluación: indicaciones (lo que se puede consultar y la forma de entrega), preguntas con concepto, título, situación, archivos, pasos y tabla de respuesta, y la clave de cada pregunta (respuesta completa, sus partes, los problemas sembrados y los errores comunes). La ficha deja de decir «No se usa». `dependencias.py` y el plan de la sesión cambian según la decisión 64 g) y h). `faltan` exige la lectura y el laboratorio aprobados y al día | Sin IA: el modelo rechaza puntos, tiempos y preguntas sin respuesta; una pregunta de la ficha que cambia desactualiza solo la evaluación; una lectura nueva la desactualiza; sin laboratorio aprobado, «Generar» dice qué falta | Abre la ficha de una sesión: la evaluación ya no está apagada. Cambia una pregunta: solo la evaluación queda desactualizada |
| 9b. Archivos y verificador | Hoja del alumno y clave en Word con el diseño de la lectura (`docx.py`); archivos de cada pregunta con `practica.py`, en su propio .zip. El verificador suma los límites de la decisión 64 c), los nombres `S[N]_P[pregunta]_`, la cantidad de preguntas y el control de respuestas separadas de la decisión 64 f). Materiales sembrados en `tests/sembrados/evaluacion.py` | Sin IA: una evaluación limpia queda sin fallas; cada error sembrado da su FALLA o AVISO: una respuesta en la hoja del alumno, 260 palabras, 16 filas, 11 celdas por llenar, un archivo mal nombrado, un archivo del laboratorio reutilizado, un puntaje y un tiempo | Recibe, desde un contenido de prueba, los dos Word, el .zip y el Excel de verificación, sin gastar |
| 9c. Redacción, validación y ejecución | El redactor (Opus) escribe el contenido con las fichas, la lectura y el laboratorio aprobados. Verificador con hasta tres vueltas, revisión del contenido por pregunta y una sola corrección (decisión 22). Cada pregunta se resuelve como un alumno y se compara con la clave (decisión 64 e) | Sin IA, con respuestas simuladas: el ciclo completo, una diferencia con prueba queda pendiente y una sin prueba se descarta. Con IA (`pytest -m ia`): una evaluación real de la sesión de prueba sin fallas | Genera la evaluación de una sesión real y lee la entrega: qué probó, qué validó y qué quedó pendiente |
| 9d. Entrega e interfaz | La página del material con su recorrido, el estado en el tablero y el panel, el costo, el revisor independiente y «Aprobar». La entrega del SPEC §8. Se actualizan CLAUDE.md, SPEC.md, SKILL.md y la ayuda | Las pruebas de las páginas existentes en verde; la evaluación aparece como quinto material; aprobarla deja la sesión lista | Genera, revisa y aprueba la evaluación desde la página, como los otros materiales |

Costo: el redactor y la ejecución se parecen a los del laboratorio. Un laboratorio costó entre 0,94 y 1,36 USD por corrida (de 2 a 15 llamadas). La evaluación tiene menos preguntas que ejercicios, así que se espera algo menos. Se mide al cerrar la fase 9c.

Estado: las fases 9a y 9b están terminadas (2026-10-22). En la 9b, una respuesta «aparece» fuera de la clave si aparece la fila completa de la clave que llena el alumno (por ejemplo «Hecho 1: Transparencia»), sin distinguir tildes, mayúsculas ni signos; una palabra suelta no basta, porque el vocabulario se repite en todos los materiales. La clave interna del material es «evaluacion», sin tilde, como las demás claves que van en direcciones y nombres de archivo. La evaluación todavía no se genera desde la interfaz (decisión 46): llega en la fase 9d.


Reglas de las fichas (etapa 4):

- Los formularios usan los campos exactos de las plantillas de la skill.
- El software marca los campos obligatorios vacíos. Los datos de cada material se exigen al generar ese material (decisión 16).
- Cada versión guardada queda en `fichas/versiones/` con su fecha.
- Si una ficha cambia después de generar un material, `verificacion.json` se crea de nuevo. El material queda "desactualizado" solo si cambió algo que usa (§0, decisión 62), y no se entrega hasta validarlo otra vez.
- Ningún material empieza sin la ficha de la sesión confirmada.
- La propuesta desde las fuentes llena solo campos vacíos. Si dos archivos se contradicen, muestra las dos versiones. Hace como máximo cuatro preguntas por vez.

Fases de la decisión 50 (diseño integrado). Cada fase termina con sus pruebas en verde y un commit. Ninguna gasta tokens.

| Fase | Qué se hace | Pruebas | Lo que el profesor puede probar |
|---|---|---|---|
| 1. Datos | Un resumen por curso para el panel: nombre, avance, «Sin ficha», «Completo» y si tiene fallas. Se calcula con lo que ya usa la página de inicio. Se guarda el último curso abierto en `cursos/_sistema/ultimo_curso.txt` | El resumen de cursos con material aprobado, con fallas, sin ficha y completo. El último curso se guarda al abrir un tablero, una sesión o un material, y se ignora si la carpeta ya no existe | Nada visible todavía |
| 2. Panel | El panel de `_entorno.html` muestra todos los cursos; el abierto, con sus sesiones; los demás, plegados. Botón «Nuevo». Gasto del curso y gasto total al pie. Estilo con los colores que ya existen | Cada curso aparece una vez y en orden. Solo el curso abierto muestra sesiones. La línea de cada curso lleva a su tablero, nunca a una ficha. El punto rojo sale solo con fallas. Sin JavaScript, el panel se ve entero | Abre un curso y cambia a otro desde el panel sin volver al inicio |
| 3. Inicio y curso nuevo | La dirección de inicio redirige al último curso. Sin cursos, o si el último no existe, se ve la página de inicio con el formulario. «Nuevo» abre la página corta para crear un curso. Se quita «Todos los cursos» del panel | Redirección con último curso válido, sin cursos y con un último curso borrado. Crear un curso desde «Nuevo» abre su tablero y lo deja como último | Cierra AulaLista, vuelve a abrirla y cae en el último curso que usó |
| 4. Revisión | Panel escondido detrás del botón «Cursos» en pantallas angostas. Se actualiza `DESIGN.md` (página de inicio, panel del curso, ubicación). Revisión del diseño en escritorio, teléfono y modo de noche | El botón abre y cierra el panel, y elegir un curso lo cierra. Pruebas de las páginas existentes en verde | Usa AulaLista en el teléfono y en modo de noche |

Curso de prueba: un curso ficticio pequeño en `tests/fixtures/`, con su ficha y fuentes propias. La prueba final del SPEC §13, con una sesión real, la hace el profesor al terminar la etapa 7b (decisión 37).

## 5. Validación

### 5.1 Programa verificador (etapa 3)

`verificacion.json` contiene:

- las fuentes y sus archivos;
- los datos fijos, cada uno con su etiqueta y su valor;
- el vocabulario, con su orden y las variantes prohibidas de cada concepto;
- lo que nunca se incluye;
- la carpeta de archivos de práctica;
- los límites de cada material.

El formato queda escrito al inicio de `verificar.py`, como dice la skill.

El programa extrae el texto de Word (párrafos, tablas, recuadros, encabezado y pie), de PowerPoint (textos y notas), de Excel (celda por celda) y de HTML (bloque de datos de los casos). Luego separa el texto en oraciones. Un título o una celda cuentan como una oración.

| Revisión | Cómo la hace | Nivel |
|---|---|---|
| La referencia existe | Busca el número de sección, cláusula, lámina o paso en un índice creado desde `fuentes_texto` y anota el título | FALLA |
| La cita es exacta | Busca el texto entre comillas en las fuentes. Solo cambia espacios y tipos de comilla | FALLA |
| La operación es correcta | Detecta "a + b = c", "×", "÷" y "%" con cifras, y recalcula. Lee números escritos hasta "cien" | FALLA |
| El dato fijo usa su valor | Si aparece la etiqueta de un dato fijo con otro valor, lo marca | FALLA |
| Sin tiempos, puntajes ni emojis | Busca minutos, segundos, cronómetros, puntos, notas, porcentajes que pesan en la nota y emojis. "Notas del profesor" está permitido. Las horas y los demás porcentajes son datos (decisión 19) | FALLA |
| Sin lo que nunca se incluye | Busca títulos como "Objetivos de aprendizaje", "Requisitos previos" y "Glosario" | FALLA |
| Sin variantes de un concepto | Busca cada variante prohibida. Junto a la palabra con que la usa una fuente es AVISO informativo «término de la fuente» (decisión 31) | FALLA |
| El archivo mencionado existe | Busca nombres `S#_E#_` y `S#_P#_` y comprueba que existan. Comprueba también que cada archivo de la carpeta se mencione | FALLA |
| Límites del material | Cuenta páginas en Word, diapositivas, ejercicios, estaciones y preguntas. Revisa 250 palabras, 15 filas y "(opcional)" | FALLA |
| Relleno | Frases de `relleno.txt` | AVISO |
| Palabra imprecisa | Palabras de `imprecisas.txt` | AVISO |
| Lenguaje de IA | Frases de `lenguaje_ia.txt`. Dentro de una cita literal de una fuente baja a AVISO | FALLA |

Última línea impresa: `Oraciones: N · Fallas: F · Avisos: A`. Si hay fallas, termina con código 1.
Cada oración recibe una huella para saber cuáles son nuevas o cambiaron.

### 5.2 Primera pasada: el verificador (decisión 22)

1. Corre sobre el Word generado (§5.1). Sus fallas y los avisos sin explicar se corrigen: por oración, o el documento completo si el problema es de estructura o de páginas.
2. Tope: tres correcciones. Si queda una FALLA, la lectura queda «con fallas», la revisión con IA no corre y no se puede aprobar.

### 5.3 Segunda pasada: la revisión del contenido, por bloque (decisión 22)

1. El programa elige para cada bloque los pasajes de las fuentes y de las fichas más parecidos a sus oraciones, más los que el redactor dijo usar. Hasta doce por bloque.
2. Una sola llamada a Sonnet recibe todos los bloques con sus pasajes y las posibles inconsistencias de cifras que encontró el programa. Puede buscar más pasajes con `buscar_en_fuentes`.
3. Reporta solo errores reales: contradice la fuente, dato inventado, vacío, ambigüedad o inconsistencia. Decir lo mismo con otras palabras, sinónimos, otro orden o un resumen no es un error. El estilo tampoco.
4. El programa comprueba cada error. La oración tiene que estar en su bloque. La prueba de una contradicción o de una inconsistencia tiene que existir en una fuente, en una ficha o en el material. Si no, el error se descarta y queda anotado.

### 5.4 Corrección y confirmación (decisión 22)

1. Los errores de la revisión se corrigen en una sola llamada, por oración.
2. El verificador corre otra vez, con su tope de tres correcciones.
3. La revisión se repite solo en los bloques que cambiaron. Un error es «corregido» si su bloque cambió y la confirmación no lo encuentra otra vez.
4. Lo que sigue, lo que la corrección no tocó y lo que aparece en la confirmación queda «pendiente». La lectura queda «con pendientes»: la entrega los lista en «Decisiones pendientes» y el profesor puede aprobarla igual.

### 5.5 Revisor independiente opcional (decisión 22)

1. No corre solo. El profesor lo lanza con el botón «Pedir revisor independiente» sobre una lectura sin fallas.
2. Es una sesión nueva de Opus. Su carpeta tiene solo el material final con oraciones numeradas, el texto de las fuentes y las dos fichas. Lee y busca con cuatro herramientas propias que no salen de esa carpeta. No puede escribir.
3. El programa comprueba que cada prueba exista. Lo que encuentra no se corrige: queda pendiente y el profesor decide. Si la lectura ya estaba aprobada y el revisor encuentra algo, vuelve a «con pendientes».

### 5.6 Cómo se llena el Excel

Formato del modelo: Arial 10, texto ajustado arriba, encabezado en negrita blanca sobre el color 0F4C5C, primera fila fija y los mismos anchos de columna.

El Excel de la lectura queda solo con la hoja **Hallazgos** (Nivel, Sección, Oración, Regla, Detalle, Cómo se resolvió):

- FALLA y AVISO: los hallazgos del verificador, y cada uno que se envió a corrección, con su vuelta.
- REVISIÓN: los errores de la revisión del contenido, con su prueba y si quedaron corregidos o pendientes, y los que el programa descartó.
- REVISOR: lo que encontró el revisor independiente, si el profesor lo pidió.

Hay cinco Excel por sesión, como en el modelo. El laboratorio y su guía comparten uno. La evaluación y su clave comparten otro.

### 5.7 Qué valida cada material

| Material | Fuente de la revisión del contenido | Revisiones propias |
|---|---|---|
| Lectura | Fuentes del curso | Sin material de referencia: seis páginas como máximo, según Word, y de 2 a 4 bloques. Con material de referencia: sus temas, menos las exclusiones, sin máximo de páginas (decisión 23). No da respuestas del laboratorio |
| Diapositivas | Lectura validada. Si una frase cita una fuente del curso, también esa fuente | De 14 a 18 diapositivas. Notas en todas. Sin desbordes, medido con PowerPoint. Mismo orden que la lectura |
| Laboratorio y archivos | Fichas y fuentes | Datos del caso, cálculos rehechos, nombres en guía, tabla y .zip, ejecución de cada ejercicio, figuras del archivo real, listas de opciones (decisión 60) |
| Guía del profesor | Registro de la ejecución | Cada respuesta es igual a lo que salió al ejecutar |
| Actividad web (decisión 57) | Lectura validada y fichas | Una sola respuesta correcta por pregunta, explicación en cada opción, cifras del caso que suman, puntos solo aquí y sin tiempos. Controles del diseño de la decisión 57 f). Playwright, en computadora (1280 × 800) y celular (375 × 812), en modo claro y oscuro y sin conexión: sin errores de JavaScript, sin desborde a los costados, botones de 44 px como mínimo, foco visible y recorrido completo con el teclado, movimiento reducido respetado; todo correcto da el puntaje máximo y todo incorrecto da cero; el avance se recupera al recargar; «Copiar mi entrega» trae el nombre, las respuestas y el puntaje |
| Evaluación y clave | Fichas y fuentes | Datos nuevos, cálculos, ejecución, hasta 10 decisiones. Ningún otro material da la respuesta |

### 5.8 Prueba de que la validación detecta errores

- **Errores mecánicos** (`tests/sembrados/`): un material por cada revisión del verificador, con un solo error puesto. Cada prueba exige la FALLA o el AVISO esperado en la fila correcta.
- **Errores de significado** (`tests/ia/test_revision_sembrados.py`): un material con errores puestos, como "cuatro pilares", "puede" en lugar de "debe", un dato inventado, una cifra distinta a la ficha y una instrucción con dos lecturas, junto con paráfrasis correctas. La revisión no debe marcar ninguna paráfrasis y debe encontrar la mayoría de los errores. Del revisor opcional se mide y se reporta cuántos detecta.
- **Control limpio:** un material sin errores debe quedar con cero fallas.

## 6. Pruebas

`pytest` corre sin IA y sin costo. `pytest -m ia` llama a Claude y se corre aparte.

| Etapa | Prueba automática |
|---|---|
| 1 | La clave se lee del `.env`. Sin clave, el programa se detiene con un mensaje. El registro de tokens escribe una línea desde un resultado simulado. La página responde. (ia) Una llamada real devuelve texto y tokens |
| 2 | Cada formato devuelve pasajes con la ubicación correcta. Una segunda conversión no repite el trabajo. Una página escaneada queda marcada para revisión. Word, PowerPoint y Excel se abren y se cierran sin quedar abiertos |
| 3 | El Excel tiene hojas, encabezados, anchos y estilos del modelo. Pasan todos los sembrados mecánicos. Pasa el control limpio. El separador corta bien las oraciones del modelo |
| 4 | Los formularios tienen los campos exactos de la skill. Se guarda y se recupera una versión. Un cambio de ficha marca los materiales como desactualizados. Cada dato propuesto tiene su origen. Un conflicto muestra las dos versiones. Nunca hay más de cuatro preguntas. Sin ficha confirmada no empieza ningún material |
| 5a–5d | Lectura de seis páginas como máximo con estilos de título reales. Pasadas con los sembrados de significado. El ciclo termina y se detiene en el tope. La entrega tiene los siete puntos del SPEC §8 |
| 6 | De 14 a 18 diapositivas, notas en todas, sin desbordes, mismos conceptos y orden que la lectura |
| 7a–7b | Nombres iguales en guía, tabla y .zip. Figuras sacadas del archivo. Ningún ejercicio usa el resultado de otro. La guía del profesor coincide con la ejecución |
| 8 | Playwright en cuatro combinaciones de tamaño y modo, sin errores. El avance se guarda. No depende de la fecha del día |
| 9 | Tres preguntas, hasta 250 palabras y 15 filas. Ningún otro material da la respuesta |

Reglas del SPEC §6 como pruebas:

| Regla | Prueba |
|---|---|
| Sin tiempos ni puntajes | Verificador sobre los seis materiales y su sembrado |
| Lenguaje claro | Oraciones largas, lista de IA y sembrado de jerga en la segunda pasada |
| Sin datos inventados | Pasaje comprobado y sembrado de una cifra inventada |
| Fuentes copiadas | Toda oración de tipo contenido de una fuente tiene un pasaje que existe |
| "En este curso" | Toda regla del curso contiene esas palabras |
| Datos ficticios y coherentes | Datos fijos y "Datos repetidos" sin dos valores para el mismo dato |
| Sin datos personales reales | Los nombres propios del material están en la lista ficticia de la ficha |
| Vocabulario único | Variantes prohibidas y orden de conceptos entre materiales |
| Ejercicios independientes | Cada ejercicio se ejecuta solo, en una carpeta con sus archivos |
| Funcionan tal cual | Detección de "[ ]", "___" y "<...>" en lo que el alumno copia, más la ejecución |
| Respuestas separadas | Las respuestas de la guía del profesor y de la clave no aparecen en otros materiales |
| Neutralidad | Lista de marcas, botones y menús cuando la ficha la pide, salvo los que nombran las fuentes o las fichas (decisión 31) |
| Diseño uniforme | Los archivos generados usan solo los tres colores de la ficha |
| Lo que nunca se incluye | Verificador y emojis |

## 7. Costo

Gasto de tokens, de mayor a menor probable: redacción, revisión del contenido, corrección, ejecución de ejercicios, lectura de imágenes y propuesta de fichas. El revisor independiente solo gasta si el profesor lo pide.

| Regla del SPEC §9 | Cómo se aplica |
|---|---|
| El verificador va primero | La IA no se usa mientras haya fallas mecánicas |
| Cada fuente se convierte una sola vez | Huella del archivo. Si no cambia, no se convierte de nuevo. La IA solo lee imágenes y PDF escaneados |
| La IA recibe solo el pasaje | El programa elige hasta doce pasajes por bloque |
| Se valida solo lo que cambió | Después de la corrección, solo se revisan de nuevo los bloques que cambiaron |
| Tope de correcciones | Tres para el verificador y una para la revisión del contenido |
| Registro de tokens | `tokens.jsonl` guarda curso, sesión, material, etapa, modelo, tokens y costo estimado. La página muestra el total |

Además:

- `modelos.toml` fija un modelo por tarea: Opus 5.5 para redactar y para el revisor opcional, Sonnet 5.5 para la revisión del contenido y para todas las correcciones: por oración, por ejercicio, completas y los arreglos del diseñador (decisión del profesor, 15/10/2026; arreglos, decisión 41). El diseño inicial de las diapositivas va con Opus 5.5 y esfuerzo medio.
- `max_budget_usd` detiene cada llamada que supere su tope.
- Las oraciones sin afirmación no van a la IA.

## 8. Riesgos

| Riesgo | Cómo se detecta pronto |
|---|---|
| El buscador no encuentra el pasaje de una oración reescrita | En la etapa 5b se mide cuántas oraciones necesitan `buscar_en_fuentes`. Si son más del 20 %, se cambia el método |
| La IA inventa un pasaje | El programa comprueba que el pasaje exista tal cual |
| Controlar Office desde Python falla o deja programas abiertos | Prueba de apertura y cierre en la etapa 2 |
| El ciclo no converge | Tres correcciones del verificador, una de la revisión, y lo abierto queda pendiente |
| El costo por material es alto | En la etapa 5d se reporta el costo real de una lectura antes de seguir. Reportado al cerrar la 5d: la lectura de la sesión 1 de Scrum, con 10 páginas de material de referencia, costó 0,71 USD (redacción 0,63 y revisión del contenido 0,08) |
| El verificador marca errores falsos | Control limpio y revisión de los avisos del modelo |
| El Agent SDK cambia | Versión fija en `requirements.txt`. Todo el uso del SDK está en `agente.py` |
| La ejecución con Claude no es igual a la del alumno | La guía del profesor lo dice en "diferencias con otra herramienta" |

## 9. Preguntas

Resueltas. Ver la sección 0.

## 10. Lista inicial de lenguaje de IA

Va en `config/lenguaje_ia.txt`, una frase por línea. La búsqueda no distingue mayúsculas ni tildes.

```
es importante destacar
cabe destacar
cabe mencionar
vale la pena mencionar
es fundamental
es crucial
en el mundo actual
en la era digital
en el panorama actual
en el vertiginoso mundo
sumérgete
adentrémonos
exploremos
descubre cómo
desbloquea
al siguiente nivel
un mundo de posibilidades
juega un papel crucial
juega un rol clave
piedra angular
pilar fundamental
sin lugar a dudas
sin duda alguna
en resumen
en conclusión
en definitiva
por último, pero no menos importante
como hemos visto
a lo largo de este
espero que esto
excelente pregunta
navegar por
fascinante
apasionante
sinergia
de manera eficiente y eficaz
transformar la forma en que
revoluciona
herramienta poderosa
este viaje
en el corazón de
un sinfín de
una amplia gama
```
