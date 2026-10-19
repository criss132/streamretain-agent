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
| 8 | ¿Grabamos el video corto (5–8 min, ambos en cámara)? | `docs/GUION_VIDEO.md` | Es opcional, pero quita la duda de «ambos integrantes participan» en la rúbrica |

**Lo que NO se puede cambiar:**
- Los resultados de la tabla (salen de `scripts/run_evaluation.py`).
- Los umbrales de `config/umbrales.yaml`, que quedaron congelados con el tag `umbrales-congelados` antes de probar.

Si algún número te parece raro, dilo y lo revisamos, pero no se ajusta a mano.

## 2. Cómo hacer cambios

El PDF **se genera con un script** (`scripts/build_documento.py`) a partir de los resultados. Hay dos caminos:

- **A. Recomendado: anotar los cambios.** Pon comentarios en el PDF o escribe la lista de cambios (página, qué dice, qué debería decir) y mándasela a Christian. Él los aplica en el script y regenera el PDF. Así no se pierden si hay que volver a generarlo, por ejemplo al agregar el enlace del video.
- **B. Editar el Word directamente:** abre `docs/Diseno_Ajustado_StreamRetain.docx`, activa **Control de cambios** (Revisar → Control de cambios) y, al terminar, devuélvelo. Ojo: si después se vuelve a correr el script, **esos cambios se pierden**. Usa este camino solo para retoques finales, cuando ya no se vaya a regenerar el documento.

**Cambios en el código (opcional):** clona el repo y sigue el README (sección 1). Antes de subir algo, corre `python -m pytest -q`. Si cambias el código del agente, habría que repetir la evaluación completa y el análisis.
