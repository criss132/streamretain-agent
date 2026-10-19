# Guion del video de respaldo (≤ 20 min) — StreamRetain-Agent

Requisitos de la guía:
- cámara y voz de **ambos** integrantes;
- índice con minutos al inicio;
- agente ejecutándose **desde cero**;
- al menos un escenario típico y uno de falla esperada;
- ejecución de las pruebas y obtención de los valores de la tabla.

Publicación: YouTube no listado, o OneDrive / Drive con acceso habilitado.

**C** = Christian Menco · **L** = Levis Ortiz. Duración objetivo: 18 min, con 2 min de margen.

## Índice (mostrarlo en pantalla o en la descripción del video)

| Minuto | Tramo | Quién |
|---|---|---|
| 00:00 | Introducción y agente elegido | C y L |
| 01:30 | Matriz de decisión (resumen) | C |
| 03:30 | Arquitectura y ciclo percepción → decisión → acción en el código | L |
| 06:30 | Demo desde cero: escenario típico (N2) | C |
| 09:30 | Demo de falla esperada: F1 (inválidos) y F3 (API con 30 % de fallos) | L |
| 12:00 | Ejecución de las pruebas en vivo y valores de la tabla | C |
| 15:30 | Análisis de resultados y limitaciones | L |
| 17:30 | Cierre | C y L |

## Preparación (antes de grabar)

- [ ] Tener abierta la app desplegada. Como respaldo, la local: `streamlit run app/streamlit_app.py`.
- [ ] Tener abierta una terminal en la carpeta del repo con el entorno activado.
- [ ] Tener abiertos `src/streamretain/agent.py`, `config/umbrales.yaml` y `results/resultados.md`.
- [ ] Ambas cámaras encendidas, en recuadro (Teams/Zoom grabando o OBS).

## Tramos

**00:00 — Introducción (C y L).** Cada uno se presenta. Problema: anticipar cancelaciones a 4 semanas en streaming. Agente elegido: StreamRetain-Agent, un agente de aprendizaje con estado interno. Aclarar desde el inicio que **los datos son sintéticos**: el entorno es un simulador estocástico.

**01:30 — Matriz (C).** Mostrar `docs/fase1_matriz.md`:
- S = 4,40 frente a 3,80;
- la sensibilidad de ±10 puntos en la viabilidad no cambia la decisión;
- el único criterio que podría invertirla es la complejidad de IA, y tendría que pesar 35 %;
- qué perdimos al descartar PickFlow.

**03:30 — Arquitectura (L).** Mostrar `docs/diagramas/arquitectura.png` y luego `agent.py`, señalando `perceive()`, `decide()`, `act()`, `learn()` y `run_cycle()`. Mencionar:
- la memoria SQLite;
- el modelo completo frente al modelo sin tendencia (baja confianza);
- τ elegido en validación;
- el presupuesto top-10 %;
- la compuerta de reentrenamiento.

**06:30 — Demo típica (C).**
1. En la app, elegir el escenario N2 y una semilla nueva.
2. Pulsar **Reiniciar simulación** para arrancar desde cero.
3. Pulsar **Ejecutar ciclo semanal** y explicar la tabla de riesgo: probabilidad, prioridad, confianza y factores.
4. Ejecutar 4 o 5 ciclos más, hasta que aparezcan las métricas por semana y el aprendizaje (resultados a 4 semanas).
5. Descargar el log y mostrar que tiene percepción, decisión y acción con marca de tiempo.

**09:30 — Fallas esperadas (L).**
1. Escenario F1: mostrar los registros inválidos con su motivo, que no se descartan en silencio.
2. Escenario F3: mostrar los fallos y timeouts de la API, los reintentos y los usuarios en cola.
3. Mencionar F2: los usuarios sin historial reciben predicción de baja confianza y nunca historial inventado.

**12:00 — Pruebas en vivo (C).**
1. En la pestaña *Suite de pruebas*, ejecutar N2, L1, F1 y F3 con 2 semillas.
2. Mostrar cómo se calculan M1–M6 contra los umbrales congelados (`config/umbrales.yaml`, tag `umbrales-congelados`).
3. Mostrar la tabla oficial de 130 casos (`results/resultados.md`) y que sale de `python scripts/run_evaluation.py`. Opcional: correr en la terminal una evaluación parcial.

**15:30 — Análisis (L).** Leer `docs/analisis_resultados.md`:
- qué medidas se cumplen y cuáles no;
- la causa probable de cada falla;
- qué cambiaríamos;
- la comparación con los baselines.

**17:30 — Cierre (C y L).** Limitaciones (datos sintéticos; etiqueta sin intervención; grupo de control en producción), trabajo futuro y enlaces.

## Minutos para la columna "Evidencia" de la tabla de resultados

Después de grabar, anoten aquí el minuto real en que aparece cada medida y cópienlo a `results/resultados.csv` (columna Evidencia) y a la sección 9.7 del documento.

| Medida | Minuto en el video |
|---|---|
| M1 / M1R / M2 / M3 / M4 | _[pendiente]_ |
| M5 (fallas) | _[pendiente]_ |
| M6 (latencia) | _[pendiente]_ |
