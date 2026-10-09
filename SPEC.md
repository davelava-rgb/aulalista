# SPEC · AulaLista

Especificación del software basado en la skill `material-de-clase`.
La skill es la fuente de las reglas. Si este documento y la skill dicen cosas distintas, vale la skill.

## 1. Propósito

El software genera el material completo de una sesión de un curso a partir de dos fichas.
El profesor llena las fichas, aprueba cada material y recibe archivos listos para entregar a los alumnos.
El profesor no revisa el material a mano: el software lo valida antes de cada entrega.

## 2. Usuarios

- **Profesor:** llena las fichas, aprueba o pide cambios, descarga los materiales.
- **Alumno:** no usa el software. Solo recibe los materiales.

El software tiene un solo usuario: el profesor que lo construye. Es un sistema web que corre en su propia computadora y se abre en el navegador. No se publica en internet.

## 3. Entradas

| Entrada | Cuándo se llena | Contenido |
|---|---|---|
| Ficha del curso | Una vez por curso | Curso y sesiones, público, caso ficticio, datos fijos del caso, identidad visual, portada, herramientas, materiales, modelos |
| Ficha de la sesión | Una vez por sesión | Alcance, bloques de la lectura, vocabulario, ejercicios del laboratorio, estaciones de la práctica, preguntas de la evaluación |
| Fuentes del curso | Una vez por curso | Sílabos, normas, programas y materiales de sesiones anteriores. Formatos: PDF, Word, hojas de cálculo e imágenes |
| Logo y paleta | Una vez por curso | Archivo del logo y hasta tres colores |

Las plantillas de las dos fichas están al final de `SKILL.md`. El software las usa sin cambiar los campos.

Reglas de las fichas:

- El software lee primero los archivos del curso y llena la ficha con lo que encuentra.
- Cada dato lleva anotado el archivo del que salió.
- Un dato deducido se marca "(propuesto)". Un dato ausente se marca "Falta definir".
- Si dos archivos se contradicen, el software muestra las dos versiones y pregunta cuál vale.
- El software hace cuatro preguntas como máximo por vez.
- Ningún material empieza sin la ficha de la sesión confirmada.

## 4. Salidas

Por cada sesión, hasta seis materiales:

| N.º | Material | Formato | Límites |
|---|---|---|---|
| 1 | Lectura | Word, A4 | 6 páginas como máximo, de 2 a 4 bloques |
| 2 | Diapositivas | PowerPoint 16:9 | De 14 a 18 diapositivas, con notas del profesor |
| 3 | Guía de laboratorio y archivos de práctica | Word, más Excel y Word en un .zip | De 3 a 5 ejercicios |
| 4 | Guía del profesor | Word | Una sección por ejercicio |
| 5 | Práctica interactiva | Un solo archivo HTML | De 5 a 7 estaciones |
| 6 | Evaluación práctica (PBQ) y su clave | Dos Word, más un .zip aparte | 3 preguntas por defecto |

Cada material lleva además su archivo de verificación: `S[sesión]_[material]_Verificacion.xlsx`.

Nombres de archivo:

- Archivos de práctica: `S[sesión]_E[ejercicio]_[descripcion-corta]`.
- Archivos de la evaluación: `S[sesión]_P[pregunta]_[descripcion-corta]`.

## 5. Flujo de trabajo

1. El software arma o carga la ficha del curso y el profesor la confirma.
2. El software propone la ficha de la sesión y el profesor la confirma.
3. El software revisa cada ejercicio de la ficha con tres preguntas: ¿funciona solo?, ¿tiene definido su archivo y su problema sembrado?, ¿se ejecuta sin llenar nada a mano?
4. El software escribe el vocabulario de la sesión: un solo nombre y un solo orden por concepto.
5. El software produce un material a la vez, en este orden: lectura, diapositivas, laboratorio con guía del profesor, práctica interactiva, evaluación.
6. Cada material usa el anterior como fuente.
7. El software valida el material, lo entrega y espera la aprobación del profesor.
8. Si el profesor pide cambios, el software los aplica, valida de nuevo y vuelve a esperar.

## 6. Reglas que no se negocian

Estas reglas se convierten en pruebas automáticas del proyecto.

- **Sin tiempos ni puntajes.** Ningún material muestra minutos, cronómetros, puntos, notas ni porcentajes.
- **Lenguaje claro.** Una idea por oración. Sin jerga. Todo término inevitable se define la primera vez.
- **Sin datos inventados.** El software no inventa cifras reales, estudios ni funciones de herramientas.
- **Fuentes copiadas.** Toda afirmación sobre una norma sale de un pasaje copiado de una fuente del curso.
- **"En este curso".** Toda regla propia del curso lleva escritas esas palabras.
- **Datos ficticios y coherentes.** Los datos del caso cuadran entre sí y con los datos fijos de la ficha.
- **Sin datos personales reales.** Las personas se nombran por su cargo o con un nombre ficticio.
- **Vocabulario único.** Cada concepto clave tiene el mismo nombre y el mismo orden en todos los materiales.
- **Ejercicios independientes.** Ningún ejercicio ni pregunta necesita el resultado de otro.
- **Ejercicios que funcionan tal cual.** Lo que el alumno copia no tiene espacios por llenar a mano.
- **Respuestas separadas.** Solo la guía del profesor y la clave de la evaluación traen respuestas.
- **Neutralidad de herramientas.** Si la ficha la pide, ningún material menciona marcas, botones ni menús.
- **Diseño uniforme.** Tres colores como máximo, los mismos recuadros y las mismas tablas en todos los materiales.
- **Lo que nunca se incluye.** Por defecto: objetivos de aprendizaje, requisitos previos, glosarios, relleno, emojis y lenguaje publicitario.

## 7. Validación

Ningún material se entrega con una falla abierta.

**Qué garantiza la validación:**

- **Veracidad.** Cada afirmación dice lo mismo que su fuente.
- **Sin contenido inventado.** Ninguna oración afirma algo que no está en una fuente del curso o en las fichas.
- **Consistencia.** El mismo dato, nombre, cifra u orden aparece igual en todos los materiales.
- **Sin vacíos.** No falta ningún paso, dato, archivo ni explicación que el alumno necesita.
- **Sin ambigüedades.** Ninguna instrucción ni pregunta se entiende de dos maneras.
- **Solo contenido de valor.** No hay relleno: toda frase le sirve al alumno para hacer algo.
- **Sin lenguaje de IA.** No hay frases hechas, muletillas ni adornos que delatan un texto generado. La lista de frases prohibidas vive en un archivo del proyecto y se puede ampliar.

**Archivo de verificación.** Es un Excel con una fila por cada oración del material. Cada fila muestra la oración, el pasaje de la fuente con el que se comparó, el archivo y la página o celda de ese pasaje, y el veredicto. El profesor puede abrirlo y comprobar cualquier oración contra su fuente.

El modelo del archivo es `S1_Laboratorio_Verificacion.xlsx`, que está en la carpeta del proyecto. Tiene cuatro hojas:

| Hoja | Columnas |
|---|---|
| Oraciones | N, Diapositiva o sección, Parte, Oración, Tipo de oración, Pasaje de la fuente, Fuente, Veredicto, Revisor independiente |
| Hallazgos | Nivel, Diapositiva, Oración, Regla, Detalle, Cómo se resolvió |
| Datos repetidos | Término o cifra, Apariciones, Oraciones |
| Segunda pasada | Bloque y las cuatro preguntas de la segunda pasada |

**Lectura de las fuentes.** El software extrae el texto de cada fuente antes de comparar: PDF, Word, hojas de cálculo e imágenes. El texto de una imagen se obtiene por reconocimiento de texto. Si una fuente no se puede leer, el material no la cita.

La validación tiene tres partes. El programa revisa lo que se puede comprobar de forma mecánica. Las dos pasadas y el revisor revisan el significado, que el programa no entiende.

**a. Programa verificador.** Recibe `verificacion.json` y los archivos del material. Separa el texto en oraciones y crea una tabla con una fila por oración. Revisa:

- que cada cláusula citada exista en la norma;
- que cada cita entre comillas aparezca tal cual en una fuente;
- que cada operación escrita dé el resultado escrito;
- que cada dato fijo use el valor de la ficha;
- que no haya tiempos, puntajes ni emojis;
- que no se usen variantes de un concepto clave;
- que cada archivo mencionado exista;
- las oraciones largas, las frases de relleno, las palabras imprecisas y las frases de la lista de lenguaje de IA.

Una FALLA se corrige siempre. Un AVISO se corrige o se explica.

**b. Dos pasadas oración por oración.**

- Primera pasada, veracidad: cada oración recibe un tipo, el pasaje de su fuente y un veredicto (coincide, no coincide o sin fuente). No queda ninguna oración "sin fuente".
- Segunda pasada, valor y funcionamiento: el software busca vacíos, inconsistencias, ambigüedades y relleno, y ejecuta de nuevo cada ejercicio.

**c. Revisor independiente.** Otro agente recibe solo el archivo final, las fuentes y las dos fichas. Si encuentra tres errores o más, se corrige y se lanza un revisor nuevo.

Después de cada corrección se repite la validación. El ciclo termina cuando una vuelta completa no cambia ninguna oración.

**Qué se valida en cada material.** Cada material se valida por separado. Validar la lectura no valida los demás.

| Material | Qué se valida |
|---|---|
| Lectura | Cada oración contra las fuentes del curso |
| Diapositivas | Cada frase contra la lectura ya validada, más las notas del profesor. Una frase que cita una norma se compara otra vez con la norma |
| Laboratorio y archivos | Datos del caso, cálculos, nombres de archivo y ejecución de cada ejercicio |
| Guía del profesor | Que cada respuesta sea la que sale al ejecutar el ejercicio |
| Práctica interactiva | Que cada caso tenga una sola respuesta y que la página funcione |
| Evaluación y clave | Datos nuevos, cálculos, ejecución de cada pregunta y que ningún otro material dé la respuesta |

Las revisiones del programa se aplican a todos los materiales. Sin archivo de verificación completo, el software no entrega el material.

## 8. Formato de cada entrega

1. Una línea por archivo, con lo que contiene.
2. "Qué probé".
3. "Qué validé": oraciones, fallas, avisos y hallazgos del revisor.
4. "Decisiones pendientes", solo si hay alguna.
5. "Qué no pude probar".
6. "Qué decidí por mi cuenta".
7. Una sola pregunta: "¿Apruebas este material para pasar a la siguiente etapa?".

## 9. Tecnología y costo

**Tecnología:**

- AulaLista usa el Claude Agent SDK. El SDK carga la skill desde `.claude/skills/`, ejecuta el programa verificador y lanza el revisor independiente.
- El programa verificador se escribe en Python.
- La interfaz es una página web local. El profesor llena las fichas, sigue el avance, aprueba cada material y descarga los archivos desde el navegador.
- Todo se guarda en archivos, sin base de datos. Cada curso tiene su carpeta:

```
cursos/[curso]/
├── ficha_del_curso.md
├── fuentes/            archivos originales del curso
├── fuentes_texto/      texto de cada fuente, con su página o celda
└── sesiones/S[número]/
    ├── ficha_de_la_sesion.md
    ├── verificacion.json
    └── materiales/     los seis materiales y sus archivos de verificación
```

**Quién paga el uso:**

- AulaLista paga con una clave de API. Así usa los créditos mensuales del plan Max y no consume el límite del plan.
- La clave se guarda en un archivo `.env`. No se define como variable de Windows.
- El archivo `.env` está en `.gitignore` y nunca se sube al repositorio.
- Si se borra la clave del `.env`, AulaLista paga con el inicio de sesión del plan Max.

**Reglas para gastar menos:**

- El programa verificador corre primero. Lo que detecta se corrige antes de usar IA para revisar.
- Un programa convierte cada fuente a texto una sola vez y guarda el resultado con su página o celda. La IA solo lee imágenes y PDF escaneados, y el profesor revisa ese resultado.
- El programa busca en la fuente el pasaje de cada oración. La IA recibe ese pasaje, no la fuente completa.
- Después de una corrección se validan solo las oraciones que cambiaron.
- El revisor independiente tiene un máximo de tres rondas. Si no alcanza, el software se detiene y avisa.
- El software registra los tokens que gasta cada etapa de cada material.

## 10. Fuera de alcance en esta versión

- Guías de laboratorio sueltas, sin el resto de la sesión.
- Calificación de alumnos y registro de notas.
- Edición de los materiales dentro del software.
- Cuentas de usuario, pagos y uso por varias instituciones.

## 11. Decisiones pendientes

| Decisión | Opciones |
|---|---|
| Programa verificador | `scripts/verificar.py` no está en la copia de la skill del proyecto. Si no se recupera, se escribe de nuevo con `S1_Laboratorio_Verificacion.xlsx` como modelo |
| Lista de lenguaje de IA | El profesor define las frases iniciales |
| Curso de prueba | El profesor elige un curso real, con su ficha y sus fuentes |

## 12. Etapas de construcción

Cada etapa termina con sus pruebas en verde y un commit.

1. Base del proyecto: Agent SDK, lectura de la clave desde `.env`, registro de tokens y página web local mínima.
2. Conversión de las fuentes a texto, con su página o celda.
3. Fichas: plantillas, lectura de archivos del curso y confirmación.
4. Programa verificador y `verificacion.json`.
5. Lectura en Word, con la identidad visual, las dos pasadas, el revisor independiente y el formato de entrega.
6. Diapositivas.
7. Laboratorio, archivos de práctica, imágenes y guía del profesor.
8. Práctica interactiva en HTML.
9. Evaluación práctica y clave.

## 13. El software está listo cuando

- Genera los seis materiales de una sesión real a partir de sus dos fichas.
- El programa verificador termina sin fallas en los seis materiales.
- Ningún material contiene tiempos ni puntajes.
- Cada oración de cada material tiene en el Excel su pasaje de fuente y su veredicto. Ninguna queda "sin fuente".
- Ningún material contiene relleno ni frases de la lista de lenguaje de IA.
- Cada ejercicio y cada pregunta se ejecuta de principio a fin con sus archivos.
- Los nombres de archivo coinciden entre las guías y los archivos.
- El profesor no tiene que buscar ningún error por su cuenta.
