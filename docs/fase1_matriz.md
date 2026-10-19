# Fase 1 — Selección justificada del agente

> **Estado: selección aplicada.** Matriz aprobada en CP1 según la fila 2 de `docs/BITACORA_IA.md`. StreamRetain-Agent es el agente implementado. Los pesos, puntajes y evidencias están en `config/matriz.yaml`.

**Agentes comparados:** A = PickFlow-Agent (optimización de picking en bodega, Christian Menco) · B = StreamRetain-Agent (predicción de cancelación en streaming, Levis Ortiz).

**Método.** Los pesos se fijaron antes de puntuar: son los seis criterios mínimos de la guía con su peso sugerido, y cada peso tiene su justificación en la matriz. Cada agente se puntuó de 1 a 5, con una frase de evidencia por puntaje. El puntaje ponderado es S = Σ (wᵢ · pᵢ), con Σ wᵢ = 1 y máximo 5. Todo se calcula con `scripts/matriz_decision.py` a partir de `config/matriz.yaml`, así que otra persona con los mismos datos obtiene la misma decisión. La matriz completa está en `results/matriz_decision.md` y `results/matriz_decision.csv`.

| Criterio | Peso | A | B |
|---|---|---|---|
| Viabilidad técnica | 25 % | 3 | 5 |
| Disponibilidad de datos o entorno | 20 % | 3 | 4 |
| Medibilidad del desempeño | 20 % | 4 | 5 |
| Complejidad de IA | 15 % | 5 | 3 |
| Costo y recursos | 10 % | 5 | 5 |
| Valor del problema | 10 % | 4 | 4 |
| **S ponderado** | 100 % | **3,80** | **4,40** |

**Agente elegido: StreamRetain-Agent (S = 4,40 frente a 3,80).** Gana en los tres criterios de mayor peso, porque:

- es un pipeline supervisado que ya sabemos construir;
- sus percepciones se pueden simular con un entorno semanal estocástico;
- su medida SMART ya trae fórmula y umbral (precisión general ≥ 75 %).

PickFlow solo gana en complejidad de IA. Empatan en costo (COP 0) y en valor del problema.

**Sensibilidad.** El criterio más influyente es la viabilidad técnica, con el mayor |w·(pA − pB)| = 0,50. Al moverlo ±10 puntos y reajustar los demás pesos en proporción, la decisión **se mantiene**:

- con 15 %: A = 3,91 y B = 4,32;
- con 35 %: A = 3,69 y B = 4,48.

Repetimos la prueba con los otros cinco criterios. En ninguna de las 12 variaciones cambia la decisión (`results/sensibilidad.csv`). El único criterio que puede invertir el resultado es la complejidad de IA, y para empatar tendría que pesar **35 %**, más del doble del peso sugerido. Darle ese peso supondría valorar la sofisticación por encima de terminar y probar el agente a tiempo.

**Qué perdemos al descartar PickFlow-Agent.**

- Un ambiente multiagente y secuencial, con decisiones de asignación y ruta que se encadenan.
- Un elemento de desempeño basado en utilidad (Russell y Norvig), más rico en razonamiento que una clasificación con umbral.
- Una medida de impacto operativo directo: −20 % de tiempo de preparación.

Lo compensamos así:

- StreamRetain conserva un estado interno por suscriptor (memoria de historial semanal).
- Aprende de los resultados de sus intervenciones, con una compuerta de reentrenamiento: solo acepta un modelo nuevo si mantiene o mejora la medida.
- Prioriza por riesgo con un presupuesto de intervenciones.
- Trabaja en un entorno estocástico con fallas inyectadas.
