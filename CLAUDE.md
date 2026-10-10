# AulaLista · reglas fijas del proyecto

AulaLista genera el material de una sesión de un curso a partir de dos fichas y lo valida antes de entregarlo.
Documentos que mandan, en este orden:

1. `.claude/skills/material-de-clase/SKILL.md`: reglas de los materiales.
2. `PLAN.md`: decisiones aprobadas, arquitectura, etapas y pruebas. Sus excepciones a la skill (sección 0) valen.
3. `SPEC.md`: qué debe hacer el software.

Si encuentras una contradicción nueva entre estos documentos, avísale al profesor. No la resuelvas por tu cuenta.

## Forma de trabajo

- Una etapa a la vez, en el orden de `PLAN.md` §4. No empieces una etapa sin la aprobación del profesor.
- Cada etapa termina con sus pruebas en verde y un commit.
- Al cerrar una etapa, di qué puede probar el profesor y cómo.
- No cambies las decisiones de `PLAN.md` §0 sin preguntar.
- No inventes funciones del Agent SDK. Consulta su documentación antes de usar una opción nueva.
- Responde al profesor en español claro: una idea por oración, sin jerga, cada término técnico definido la primera vez.

## Decisiones fijas

- Un solo usuario. Sistema web local en Windows. El servidor escucha solo en `127.0.0.1`.
- Python 3.13. Versiones fijas en `requirements.txt`.
- Claude Agent SDK (`claude-agent-sdk`). Todo uso del SDK está en `app/agente.py`.
- La clave de API se lee del `.env` con `python-dotenv` y se pasa al SDK con la opción `env`. Nunca se define como variable de Windows. Sin clave, el programa se detiene y avisa. No hay respaldo con el plan Max.
- `.env` nunca se sube al repositorio. `cursos/` tampoco.
- Todo se guarda en archivos, en `cursos/[curso]/`. Sin base de datos.
- El verificador es `.claude/skills/material-de-clase/scripts/verificar.py`. No usa IA. El formato de `verificacion.json` está escrito al inicio de ese archivo.
- El agente escribe el contenido como datos estructurados. Los generadores de `app/materiales/` crean los archivos. El agente no escribe Word, PowerPoint ni HTML a mano.
- Office instalado (Word, PowerPoint, Excel) se controla con `pywin32` solo desde `app/office.py`. Siempre se cierra la aplicación al terminar.

## Reglas que no se negocian (SPEC §6)

Cada regla tiene una prueba automática. Si una regla no tiene prueba, la etapa no está terminada.

- Sin tiempos ni puntajes en ningún material.
- Lenguaje claro: una idea por oración, sin jerga, término inevitable definido la primera vez.
- Sin datos inventados: ni cifras reales, ni estudios, ni funciones de herramientas.
- Toda afirmación sobre el contenido de una fuente sale de un pasaje copiado de una fuente del curso. Se puede decir con otras palabras si no cambia el sentido (`PLAN.md` §0, decisiones 15 y 18).
- Toda regla propia del curso lleva "en este curso".
- Datos del caso ficticios y coherentes con los datos fijos de la ficha.
- Sin datos personales reales.
- Vocabulario único: mismo nombre y mismo orden en todos los materiales.
- Ejercicios y preguntas independientes, que funcionan tal cual.
- Respuestas solo en la guía del profesor y en la clave.
- Neutralidad de herramientas si la ficha la pide.
- Diseño uniforme: tres colores como máximo, mismos recuadros y tablas.
- Nunca se incluye, por defecto: objetivos de aprendizaje, requisitos previos, glosarios, relleno, emojis y lenguaje publicitario.

## Validación (dos pasadas, `PLAN.md` §0, decisión 22)

- Primera pasada: el verificador, sin IA. Ningún material se aprueba con una FALLA abierta. Un AVISO se corrige o se explica, salvo los de relleno y palabras imprecisas, que son informativos (`PLAN.md` §0, decisión 13).
- Segunda pasada: una revisión del contenido con IA, por bloque. Solo reporta errores reales: contradice la fuente, dato inventado, vacío, ambigüedad o inconsistencia. Decir lo mismo con otras palabras nunca es un error.
- La prueba de una contradicción o de una inconsistencia se comprueba con un programa contra la fuente, las fichas o el material. Sin prueba real, el error se descarta.
- Una sola corrección de los errores de la revisión. Después, el verificador otra vez y la revisión solo de los bloques que cambiaron. Lo que quede va a la entrega como pendiente y el profesor decide.
- El revisor independiente es opcional: lo lanza el profesor con un botón. Es una sesión nueva del SDK, sin acceso a borradores. No corrige.
- El Excel de verificación queda solo con la hoja Hallazgos, en el formato de `S1_Laboratorio_Verificacion.xlsx`.

## Costo

- El verificador corre antes que cualquier revisión con IA.
- Cada fuente se convierte a texto una sola vez.
- La IA recibe pasajes, no fuentes completas.
- Después de una corrección, solo se revisan de nuevo los bloques que cambiaron.
- Cada llamada al SDK registra sus tokens en `cursos/[curso]/tokens.jsonl` y tiene un tope con `max_budget_usd`.
- Los modelos por tarea están en `config/modelos.toml`.

## Pruebas

- `pytest`: pruebas sin IA y sin costo. Deben pasar siempre.
- `pytest -m ia`: pruebas que llaman a Claude. Se corren aparte y solo cuando hace falta.
- Todo error que detecta la validación tiene un material sembrado en `tests/sembrados/` que lo comprueba.
