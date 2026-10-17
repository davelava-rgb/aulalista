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
| 17 | Fichas desde las fuentes. Si el curso tiene fuentes convertidas, una ficha sin confirmar se propone sola la primera vez que se abre, en segundo plano. La propuesta llena todos los campos: lo que la fuente dice, tal cual y con su archivo; lo que deduce (sesiones por capítulo, público, temas, vocabulario) y los datos ficticios del caso, marcados «Propuesto». No propone la identidad visual ni los modelos, y el docente y el contacto solo se toman si la fuente los dice tal cual. El botón «Aceptar lo propuesto y confirmar» confirma en un paso. Sin fuentes, la ficha se llena a mano. Amplía la decisión 4 (aprobado en la etapa 5d) |
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
| 45 | La ficha se lee primero y se edita por sección. a) Una ficha confirmada se abre en modo de lectura: cada sección es una tarjeta con el resumen de sus campos (etiqueta y valor) y un botón «Editar». El laboratorio y la evaluación muestran una fila por ejercicio o pregunta. b) Se edita una sección a la vez, con «Guardar esta sección», «Cancelar» y el aviso de cambios sin guardar. El formulario sigue siendo uno y el servidor guarda la ficha entera, como antes. c) Una ficha sin confirmar se abre en edición, y una sección con campos «Falta definir» o con dos versiones se abre siempre en edición. d) El índice muestra el estado de cada sección (completa, vacía, con alertas o «no se usa»); la evaluación va apagada y plegada por la decisión 37. e) Sin JavaScript, todo se ve en edición. Se aplica en cuatro fases: datos, plantilla, comportamiento y revisión (aprobado el 2026-10-16) |
| 46 | Cuatro materiales: vuelve la evaluación práctica (PBQ). Cambia la decisión 37. Los materiales de una sesión son la lectura, las diapositivas, el laboratorio y la evaluación práctica (PBQ) con su clave. La etapa 9 vuelve al plan y se construye con su propio plan, aprobado antes de empezar. Mientras no esté construida, la interfaz sigue diciendo que la evaluación no se genera. El SPEC §13 se mide contra estos cuatro materiales (aprobado el 2026-10-17) |
| 47 | Oraciones sin fuente alineadas con el material. Cambia la regla del SPEC §13 «Ninguna queda sin fuente». Una oración puede quedar sin pasaje de fuente si está alineada con el material: no contradice las fuentes ni las fichas, y no agrega cifras, estudios ni funciones inventadas. Sigue apareciendo en la entrega como decisión pendiente para que el profesor la vea, pero no impide aprobar. Toda afirmación sobre el contenido de una fuente sigue saliendo de un pasaje (aprobado el 2026-10-17) |
| 48 | El Excel de verificación solo con hallazgos. Cambia la regla del SPEC §13 «Cada oración de cada material tiene en el Excel su pasaje de fuente y su veredicto». El Excel queda solo con la hoja Hallazgos, como ya dicen CLAUDE.md y la decisión 22 (aprobado el 2026-10-17) |
| 49 | La ficha del curso no pide los materiales. Se quita «Materiales por sesión» de la sección 8 de la ficha del curso: los materiales de cada sesión se eligen en su ficha de sesión («Materiales de esta sesión»), que es la única que usa AulaLista. Es una excepción a la plantilla de la skill (FICHA DE CURSO, «8. Materiales»). Un valor guardado antes en ese campo se conserva, pero no se muestra ni se usa (aprobado el 2026-10-17) |

### Contradicciones encontradas

1. **Rondas del revisor.** El SPEC fija tres rondas y la skill no pone tope. Se resolvió con la decisión 1.
2. **Reconocimiento de texto.** El SPEC §7 pide reconocimiento de texto para imágenes. El SPEC §9 dice que la IA lee las imágenes. No hay programa de reconocimiento instalado. Claude lee las imágenes y el profesor revisa el resultado.
3. **Dónde buscar la ficha.** La skill busca en "instrucciones del proyecto", "memoria" y "adjuntos". En AulaLista se busca en la carpeta del curso.
4. **Publicar la práctica interactiva.** La skill la publica si el entorno lo permite. El Agent SDK no publica páginas. Se entrega solo el archivo HTML.
5. **Excel modelo contra la skill.** El modelo marca "coincide" en 387 filas sin pasaje. La skill lo prohíbe. Se resolvió con la decisión 2.
6. **Llenado de la ficha.** La skill dice que primero se leen los archivos. El profesor decidió llenar la ficha en un formulario. Se resolvió con la decisión 4: el formulario manda y la propuesta desde las fuentes es un botón.

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
| 8 | ~~Práctica interactiva~~ | Quitada (decisión 34) |
| 9 | Evaluación y clave | Vuelve con la decisión 46. Pendiente: se construye con su propio plan aprobado |

Reglas de las fichas (etapa 4):

- Los formularios usan los campos exactos de las plantillas de la skill.
- El software marca los campos obligatorios vacíos. Los datos de cada material se exigen al generar ese material (decisión 16).
- Cada versión guardada queda en `fichas/versiones/` con su fecha.
- Si una ficha cambia después de generar un material, `verificacion.json` se crea de nuevo. El material queda "desactualizado" y no se entrega hasta validarlo otra vez.
- Ningún material empieza sin la ficha de la sesión confirmada.
- La propuesta desde las fuentes llena solo campos vacíos. Si dos archivos se contradicen, muestra las dos versiones. Hace como máximo cuatro preguntas por vez.

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
| Laboratorio y archivos | Fichas y fuentes | Datos del caso, cálculos rehechos, nombres en guía, tabla y .zip, ejecución de cada ejercicio, figuras del archivo real |
| Guía del profesor | Registro de la ejecución | Cada respuesta es igual a lo que salió al ejecutar |
| Práctica interactiva | Laboratorio validado | Una sola respuesta por caso. Playwright revisa tamaños, modos, teclado, botones de 44 px y errores |
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
