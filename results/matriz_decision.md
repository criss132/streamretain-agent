### Matriz de decisión ponderada

| Criterio | Peso (w) | Justificación del peso | A: puntaje | A: evidencia | B: puntaje | B: evidencia |
|---|---|---|---|---|---|---|
| Viabilidad técnica | 25 % | Mayor riesgo del proyecto: el agente debe funcionar y probarse en el tiempo disponible (entrega 19-oct-2026). | 3 | Exige simular bodega con operarios y robots y aprender una política de asignación y ruta (utilidad + aprendizaje); factible, pero con más componentes nuevos que construir. | 5 | Pipeline supervisado conocido (scikit-learn: preprocesamiento, clasificador, calibración) más un simulador semanal sencillo; todos los componentes ya los sabemos implementar. |
| Disponibilidad de datos o entorno | 20 % | Sin entorno o datos simulables no hay percepciones ni pruebas. | 3 | No hay WMS real; el simulador debe modelar rutas, tiempos estocásticos, picos de demanda y fallas de robots, sin datos de referencia para calibrarlo. | 4 | Las percepciones de la sección 5 (horas vistas, días sin login, plan, cambio de pago) se generan con un simulador semanal estocástico; no existe historial semanal real, por eso no es 5. |
| Medibilidad del desempeño | 20 % | El 20 % de la nota (pruebas) depende de medir con fórmula y umbral. | 4 | El tiempo promedio vs. línea base en simulador es objetivo, pero la medida SMART exige 2 semanas de operación real, que no es replicable y debe reformularse. | 5 | La medida SMART (precisión general ≥ 75 % = aciertos / predicciones) ya tiene fórmula y umbral, y se calcula sobre datos de prueba no usados en entrenamiento. |
| Complejidad de IA | 15 % | La asignatura exige razonamiento o aprendizaje real, pero no a costa de no terminar. | 5 | Agente de aprendizaje con elemento de desempeño basado en utilidad, ambiente multiagente y secuencial (Russell y Norvig). | 3 | Agente de aprendizaje con estado interno por usuario, pero la decisión es clasificación supervisada + regla de umbral; menos razonamiento secuencial. |
| Costo y recursos | 10 % | Cuenta gratuita de despliegue y sin APIs pagas: restricción real pero secundaria. | 5 | Todo corre local en Python con librerías libres; costo estimado COP 0 y sin llamadas a APIs pagas. | 5 | Todo corre local en Python con librerías libres; la API de marketing es un simulador; costo estimado COP 0. |
| Valor del problema | 10 % | Usuario y beneficio ya están descritos en ambos diseños; poco diferenciador. | 4 | Usuario: supervisor de bodega; beneficio: menos tiempo de preparación y desplazamiento (meta de −20 %). | 4 | Usuario: analista de retención; beneficio: anticipar cancelaciones a 4 semanas y proteger ingreso recurrente. |
| **Puntaje ponderado S** | **100 %** | | **3,80** | | **4,40** | |

A = PickFlow-Agent (optimización de picking en bodega) · B = StreamRetain-Agent (predicción de cancelación en streaming)

### Análisis de sensibilidad (± 10 puntos al peso, resto reajustado proporcionalmente)

| Criterio | Influencia \|w·(pA−pB)\| | Peso original → nuevo | S A | S B | Decisión |
|---|---|---|---|---|---|
| Viabilidad técnica **(más influyente)** | 0,50 | 25 % → 15 % | 3,91 | 4,32 | B |
| Viabilidad técnica **(más influyente)** | 0,50 | 25 % → 35 % | 3,69 | 4,48 | B |
| Disponibilidad de datos o entorno | 0,20 | 20 % → 10 % | 3,90 | 4,45 | B |
| Disponibilidad de datos o entorno | 0,20 | 20 % → 30 % | 3,70 | 4,35 | B |
| Medibilidad del desempeño | 0,20 | 20 % → 10 % | 3,77 | 4,33 | B |
| Medibilidad del desempeño | 0,20 | 20 % → 30 % | 3,82 | 4,47 | B |
| Complejidad de IA | 0,30 | 15 % → 5 % | 3,66 | 4,56 | B |
| Complejidad de IA | 0,30 | 15 % → 25 % | 3,94 | 4,24 | B |
| Costo y recursos | 0,00 | 10 % → 0 % | 3,67 | 4,33 | B |
| Costo y recursos | 0,00 | 10 % → 20 % | 3,93 | 4,47 | B |
| Valor del problema | 0,00 | 10 % → 0 % | 3,78 | 4,44 | B |
| Valor del problema | 0,00 | 10 % → 20 % | 3,82 | 4,36 | B |

### Punto de quiebre (peso que produciría empate S(A) = S(B))

| Criterio | Peso actual | Peso de empate |
|---|---|---|
| Viabilidad técnica | 25 % | no existe |
| Disponibilidad de datos o entorno | 20 % | no existe |
| Medibilidad del desempeño | 20 % | no existe |
| Complejidad de IA | 15 % | 35 % |
| Costo y recursos | 10 % | no existe |
| Valor del problema | 10 % | no existe |
