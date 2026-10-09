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
3. **Ejecutar cada ejercicio "como un alumno".** Se ejecutan los prompts en una conversación nueva con Claude, sin herramientas. Se ejecutan las fórmulas de Excel con el Excel instalado. Los comandos y otros programas quedan en "Qué no pude probar".
4. **Ciclo sin fin.** El ciclo de corrección tiene un tope de cinco vueltas. Después, el software se detiene y muestra lo que queda abierto.
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

La skill se carga desde `.claude/skills/` con `setting_sources=["project"]`.

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
| 7b | Guía del profesor y ejecución | Cada respuesta coincide con lo que salió al ejecutar el ejercicio |
| 8 | Práctica interactiva | Un solo HTML que funciona en computadora y celular, en modo claro y oscuro |
| 9 | Evaluación y clave | Dos Word y un .zip aparte. Ningún otro material da una respuesta |

Reglas de las fichas (etapa 4):

- Los formularios usan los campos exactos de las plantillas de la skill.
- El software marca los campos obligatorios vacíos.
- Cada versión guardada queda en `fichas/versiones/` con su fecha.
- Si una ficha cambia después de generar un material, `verificacion.json` se crea de nuevo. El material queda "desactualizado" y no se entrega hasta validarlo otra vez.
- Ningún material empieza sin la ficha de la sesión confirmada.
- La propuesta desde las fuentes llena solo campos vacíos. Si dos archivos se contradicen, muestra las dos versiones. Hace como máximo cuatro preguntas por vez.

Curso de prueba: un curso ficticio pequeño en `tests/fixtures/`, con su ficha y fuentes propias. La prueba final del SPEC §13, con una sesión real, la hace el profesor al terminar la etapa 9.

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
| La cláusula existe | Busca el número en un índice de cláusulas o láminas creado desde `fuentes_texto` y anota el título | FALLA |
| La cita es exacta | Busca el texto entre comillas en las fuentes. Solo cambia espacios y tipos de comilla | FALLA |
| La operación es correcta | Detecta "a + b = c", "×", "÷" y "%" con cifras, y recalcula. Lee números escritos hasta "cien" | FALLA |
| El dato fijo usa su valor | Si aparece la etiqueta de un dato fijo con otro valor, lo marca | FALLA |
| Sin tiempos, puntajes ni emojis | Busca minutos, horas de actividad, cronómetros, puntos, notas, porcentajes y emojis. "Notas del profesor" está permitido | FALLA |
| Sin lo que nunca se incluye | Busca títulos como "Objetivos de aprendizaje", "Requisitos previos" y "Glosario" | FALLA |
| Sin variantes de un concepto | Busca cada variante prohibida | FALLA |
| El archivo mencionado existe | Busca nombres `S#_E#_` y `S#_P#_` y comprueba que existan. Comprueba también que cada archivo de la carpeta se mencione | FALLA |
| Límites del material | Cuenta páginas en Word, diapositivas, ejercicios, estaciones y preguntas. Revisa 250 palabras, 15 filas y "(opcional)" | FALLA |
| Oración larga | Más de 25 palabras, como en el modelo | AVISO |
| Relleno | Frases de `relleno.txt` | AVISO |
| Palabra imprecisa | Palabras de `imprecisas.txt` | AVISO |
| Lenguaje de IA | Frases de `lenguaje_ia.txt`. Dentro de una cita literal de una fuente baja a AVISO | FALLA |

Última línea impresa: `Oraciones: N · Fallas: F · Avisos: A`. Si hay fallas, termina con código 1.
Cada oración recibe una huella para saber cuáles son nuevas o cambiaron.

### 5.2 Primera pasada, veracidad (etapa 5b)

1. El programa busca para cada oración los tres pasajes más parecidos en `fuentes_texto` y en las fichas. En las diapositivas busca además en la lectura validada.
2. La IA recibe grupos de unas 20 oraciones con sus pasajes, no las fuentes completas.
3. Por cada oración, la IA responde en JSON: tipo, pasaje copiado, ubicación, veredicto y motivo.
4. En las normas, la IA compara las siete cosas que exige la skill. Son campos obligatorios del JSON.
5. El programa comprueba que el pasaje copiado exista tal cual en esa ubicación. Si no existe, la oración queda "sin fuente".
6. Comprobaciones sin IA: regla del curso con "en este curso", dato del caso igual a la ficha, cálculo rehecho con los datos del archivo.
7. Si los candidatos no sirven, la IA usa la herramienta `buscar_en_fuentes`.
8. "No coincide": el redactor reescribe la oración. "Sin fuente": la borra o la convierte en regla del curso.

### 5.3 Segunda pasada, valor y funcionamiento (etapa 5c)

1. El programa lista cada cifra, nombre propio, fecha y término del vocabulario con sus oraciones. Así llena "Datos repetidos". Dos valores para el mismo dato crean un hallazgo de inconsistencia.
2. La IA responde las cuatro preguntas por cada bloque, ejercicio, estación o pregunta. Así llena "Segunda pasada". Una pregunta sin respuesta crea un hallazgo.
3. El ejecutor vuelve a ejecutar cada ejercicio y cada pregunta.
4. La IA responde la lista de verificación de la skill en JSON. Cada "no" crea un hallazgo.

### 5.4 Revisor independiente (etapa 5d)

1. Es una sesión nueva del SDK. No continúa la sesión del redactor.
2. Su carpeta de trabajo tiene solo el texto del material final con oraciones numeradas, `fuentes_texto` y las dos fichas.
3. Puede leer y buscar en esa carpeta. No puede escribir.
4. Recibe el pedido exacto de la skill y responde en JSON: número de oración, defecto y prueba.
5. El programa comprueba que cada prueba citada exista.
6. El redactor corrige el hallazgo o lo rechaza con el pasaje que lo contradice. Se anota en la columna "Revisor independiente".
7. Con tres hallazgos válidos o más, se corrige y se lanza un revisor nuevo. Máximo tres rondas.

### 5.5 Ciclo de corrección (etapa 5d)

Después de cada cambio:

1. Se generan los archivos de nuevo.
2. El verificador corre completo.
3. La primera pasada revisa solo las oraciones con huella nueva.
4. La segunda pasada revisa solo los bloques que cambiaron y vuelve a ejecutar sus ejercicios.
5. Si la corrección vino de un revisor con tres hallazgos o más, se lanza un revisor nuevo.

El ciclo termina cuando una vuelta completa no cambia ninguna oración: cero fallas, avisos explicados, ninguna oración "no coincide" ni "sin fuente" y un revisor con menos de tres hallazgos. Tope: cinco vueltas.

### 5.6 Cómo se llena el Excel

Formato del modelo: Arial 10, texto ajustado arriba, encabezado en negrita blanca sobre el color 0F4C5C, primera fila fija y los mismos anchos de columna.

**Hoja Oraciones**

| Columna | Quién la llena |
|---|---|
| N | Verificador |
| Diapositiva o sección | Verificador: "archivo · sección" o "archivo · diapositiva N" |
| Parte | Verificador: texto, tabla o recuadro, celda o notas |
| Oración | Verificador |
| Tipo de oración | Primera pasada: norma, dato del caso, cálculo, regla del curso, instrucción o sin afirmación |
| Pasaje de la fuente | Primera pasada, después de que el programa comprueba que existe |
| Fuente | Primera pasada: archivo y página, lámina o celda |
| Veredicto | Primera pasada: coincide, no coincide o sin fuente |
| Revisor independiente | Revisor: "Ronda R: defecto. Resuelto" o "Rechazado: pasaje" |

**Hoja Hallazgos** (Nivel, Diapositiva, Oración, Regla, Detalle, Cómo se resolvió): la llenan el verificador y las dos pasadas. El redactor escribe "Cómo se resolvió".

**Hoja Datos repetidos** (Término o cifra, Apariciones, Oraciones): la llena la segunda pasada. Una variante prohibida aparece con 0 apariciones.

**Hoja Segunda pasada** (Bloque y las cuatro preguntas): la llena la IA en la segunda pasada.

Hay cinco Excel por sesión, como en el modelo. El laboratorio y su guía comparten uno. La evaluación y su clave comparten otro. Cada archivo tiene sus propias filas y se valida por separado.

### 5.7 Qué valida cada material

| Material | Fuente de la primera pasada | Revisiones propias |
|---|---|---|
| Lectura | Fuentes del curso | Seis páginas como máximo, según Word. De 2 a 4 bloques. No da respuestas del laboratorio |
| Diapositivas | Lectura validada. Si una frase cita una norma, también la norma | De 14 a 18 diapositivas. Notas en todas. Sin desbordes, medido con PowerPoint. Mismo orden que la lectura |
| Laboratorio y archivos | Fichas y fuentes | Datos del caso, cálculos rehechos, nombres en guía, tabla y .zip, ejecución de cada ejercicio, figuras del archivo real |
| Guía del profesor | Registro de la ejecución | Cada respuesta es igual a lo que salió al ejecutar |
| Práctica interactiva | Laboratorio validado | Una sola respuesta por caso. Playwright revisa tamaños, modos, teclado, botones de 44 px y errores |
| Evaluación y clave | Fichas y fuentes | Datos nuevos, cálculos, ejecución, hasta 10 decisiones. Ningún otro material da la respuesta |

### 5.8 Prueba de que la validación detecta errores

- **Errores mecánicos** (`tests/sembrados/`): un material por cada revisión del verificador, con un solo error puesto. Cada prueba exige la FALLA o el AVISO esperado en la fila correcta.
- **Errores de significado** (`tests/ia/`): un material con errores puestos, como "cuatro pilares", "puede" en lugar de "debe", un "todos" que la fuente no dice, una regla sin "en este curso", una oración sin fuente, una instrucción con dos lecturas, un paso que falta y una frase de relleno. Las dos pasadas deben marcar el 100 %. Del revisor se mide y se reporta cuántos detecta.
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
| Fuentes copiadas | Toda oración de tipo norma tiene un pasaje que existe |
| "En este curso" | Toda regla del curso contiene esas palabras |
| Datos ficticios y coherentes | Datos fijos y "Datos repetidos" sin dos valores para el mismo dato |
| Sin datos personales reales | Los nombres propios del material están en la lista ficticia de la ficha |
| Vocabulario único | Variantes prohibidas y orden de conceptos entre materiales |
| Ejercicios independientes | Cada ejercicio se ejecuta solo, en una carpeta con sus archivos |
| Funcionan tal cual | Detección de "[ ]", "___" y "<...>" en lo que el alumno copia, más la ejecución |
| Respuestas separadas | Las respuestas de la guía del profesor y de la clave no aparecen en otros materiales |
| Neutralidad | Lista de marcas, botones y menús cuando la ficha la pide |
| Diseño uniforme | Los archivos generados usan solo los tres colores de la ficha |
| Lo que nunca se incluye | Verificador y emojis |

## 7. Costo

Gasto de tokens, de mayor a menor probable: primera pasada, redacción y correcciones, revisor, ejecución de ejercicios, segunda pasada, lectura de imágenes y propuesta de fichas.

| Regla del SPEC §9 | Cómo se aplica |
|---|---|
| El verificador va primero | La IA no se usa mientras haya fallas mecánicas |
| Cada fuente se convierte una sola vez | Huella del archivo. Si no cambia, no se convierte de nuevo. La IA solo lee imágenes y PDF escaneados |
| La IA recibe solo el pasaje | El programa elige tres pasajes por oración |
| Se valida solo lo que cambió | Las huellas de las oraciones guardan sus veredictos |
| Tope del revisor | Tres rondas |
| Registro de tokens | `tokens.jsonl` guarda curso, sesión, material, etapa, modelo, tokens y costo estimado. La página muestra el total |

Además:

- `modelos.toml` fija un modelo por tarea: Opus 5.5 para redactar y revisar, Sonnet 5.5 para las pasadas.
- `max_budget_usd` detiene cada llamada que supere su tope.
- Las oraciones sin afirmación no van a la IA.

## 8. Riesgos

| Riesgo | Cómo se detecta pronto |
|---|---|
| El buscador no encuentra el pasaje de una oración reescrita | En la etapa 5b se mide cuántas oraciones necesitan `buscar_en_fuentes`. Si son más del 20 %, se cambia el método |
| La IA inventa un pasaje | El programa comprueba que el pasaje exista tal cual |
| Controlar Office desde Python falla o deja programas abiertos | Prueba de apertura y cierre en la etapa 2 |
| El ciclo no converge | Tope de cinco vueltas y aviso |
| El costo por material es alto | En la etapa 5d se reporta el costo real de una lectura antes de seguir |
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
