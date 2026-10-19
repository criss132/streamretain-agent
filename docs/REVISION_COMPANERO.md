# Guía de revisión para Levis (StreamRetain-Agent, Tarea 3)

Hola, Levis. Esta guía resume qué revisar antes de entregar y cómo hacer cambios sin perder nada.

- **Entrega:** lunes 19 de octubre de 2026, 07:00.
- **Aplicación:** https://streamretain-agent.streamlit.app/
- **Repositorio:** https://github.com/criss132/streamretain-agent

## 1. Qué revisar (en orden de prioridad)

| # | Qué | Dónde | Por qué te toca a ti |
|---|---|---|---|
| 1 | Secciones 1–8: que se mantenga tu texto original y que las correcciones sean correctas | PDF, páginas 5–8 | El documento base es tu Tarea 2 |
| 2 | Tabla de cambios | PDF, página 2 | Dice que no hubo retroalimentación del docente para StreamRetain. Si tú sí la recibiste, avísanos: hay que incluirla |
| 3 | Matriz de decisión: puntajes y evidencias de StreamRetain (columna B) | PDF, páginas 3–4, y `config/matriz.yaml` | Los propuso Claude y Christian los aprobó; revisa que estés de acuerdo |
| 4 | Medida reformulada (M1R) y nuevas medidas M2–M6 | PDF, sección 7 | Cambia tu medida SMART original (se conserva como M1) |
| 5 | Análisis de resultados y conclusiones | PDF, sección 9.7 y sección 10 | Lo defenderemos ambos |
| 6 | Probar la app: escenario N2, después F3, después la pestaña *Suite de pruebas* | URL de arriba | Es la evidencia de funcionamiento |
| 7 | Bitácora de IA: completar la columna «Verificación humana» | `docs/BITACORA_IA.md` | La guía la pide y debe hacerla la pareja |
| 8 | Abrir la plataforma sin sesión de administrador y confirmar acceso público hasta la calificación | Streamlit y SAVIO | La entrega usa la opción A de la guía; no se realizará video |

**Lo que NO se puede cambiar:**
- Los resultados de la tabla (salen de `scripts/run_evaluation.py`).
- Los umbrales de `config/umbrales.yaml`, que quedaron congelados con el tag `umbrales-congelados` antes de probar.

Si algún número te parece raro, dilo y lo revisamos, pero no se ajusta a mano.

## 2. Cómo hacer cambios

### Cómo registrar la verificación humana

Cada integrante revisa su nombre y código, los puntajes de la matriz y las conclusiones. Levis confirma si recibió retroalimentación del docente sobre su diseño; si existe, hay que incorporarla antes de entregar. Ambos deben poder explicar el ciclo del agente y por qué M1, M1R y M4 no alcanzan sus umbrales.

En una ventana privada del navegador, abrir Streamlit, ejecutar N2, luego F3 y la suite con N2/F3 y semilla 1001. Comprobar que aparecen predicciones, fallos manejados y resultados, y descargar un log. Esta comprobación confirma el acceso público y complementa las pruebas locales automáticas.

Después de revisar cada bloque de la bitácora, completar su última columna con nombre, fecha, qué se comprobó y resultado. Ejemplo de formato (solo después de hacerlo): «Levis, fecha: ejecuté N2 y F3, revisé predicciones, reintentos y descarga del log; conforme». No marcar como revisado un bloque que no se haya comprobado. Consultar con Christian los bloques históricos que él validó.

Confirmar en SAVIO la fecha de calificación, mantener disponible la aplicación hasta entonces y subir el PDF actualizado, los enlaces, los logs y la bitácora según `docs/ENTREGA.md`.

El PDF **se genera con un script** (`scripts/build_documento.py`) a partir de los resultados. Hay dos caminos:

- **A. Recomendado: anotar los cambios.** Pon comentarios en el PDF o escribe la lista de cambios (página, qué dice, qué debería decir). Los cambios se aplican en `scripts/build_documento.py` y se regenera el PDF para conservarlos en futuras versiones.
- **B. Editar el Word directamente:** abre `docs/Diseno_Ajustado_StreamRetain.docx`, activa **Control de cambios** (Revisar → Control de cambios) y, al terminar, devuélvelo. Ojo: si después se vuelve a correr el script, **esos cambios se pierden**. Usa este camino solo para retoques finales, cuando ya no se vaya a regenerar el documento.

**Cambios en el código (opcional):** clona el repo y sigue el README (sección 1). Antes de subir algo, corre `python -m pytest -q`. Si cambias el código del agente, habría que repetir la evaluación completa y el análisis.

## 3. Comprobación técnica del 18-oct-2026

Ejecutada por Codex en Windows, en un entorno temporal aislado con Python 3.13.16 y las versiones de `requirements.txt`.

- `python -m pytest -q`: **9 pruebas aprobadas** en 4,58 s. Cubren percepción, historial, reintentos, cola, compuerta de aprendizaje, log, separación de etiquetas y reproducibilidad.
- Interfaz ejecutada con `streamlit.testing.v1.AppTest`: arranque sin excepciones, ciclos N2, F1, F2 y F3 con semilla 2026, todos los ciclos de F3 y suite desde la interfaz con N2/F3 y semilla 1001. La suite terminó en 14 s sin excepciones de interfaz.
- N2: 1.988 usuarios puntuados, 199 ofertas activadas. F1: 196 registros inválidos rechazados. F2: 392 predicciones de baja confianza. F3: 197 ofertas activadas y 2 en cola. Latencias de estos primeros ciclos: 0,63–0,85 s; son comprobaciones locales, no reemplazan M6 de la evaluación oficial.
- La URL pública de Streamlit respondió HTTP 200. Esto comprueba acceso HTTP; la interacción remota en navegador privado queda en la revisión humana anterior.
- PDF y DOCX regenerados sin marcadores de video pendiente. Se comprobó que las cifras de `results/resultados.csv` permanecen idénticas a las originales; solo cambió la columna de evidencia.

Alcance: se ejecutaron pruebas unitarias e integración y una muestra funcional de la interfaz. No se repitió la evaluación oficial completa de 130 casos. Los datos, modelos, umbrales y resultados numéricos oficiales se conservaron.
