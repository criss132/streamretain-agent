# StreamRetain-Agent

Agente inteligente **de aprendizaje** (con estado interno por suscriptor) que cada semana estima qué suscriptores de una plataforma de streaming cancelarán en las próximas 4 semanas, prioriza los de mayor riesgo y activa ofertas de retención mediante una API de marketing. Además aprende de los resultados.

Tarea 3, Inteligencia Artificial, Universidad Tecnológica de Bolívar. Docente: Edwin Alexander Puertas Del Castillo.
Pareja: Christian David Menco Galván (T00058749) y Levis Adrian Ortiz Cano (T00083674).

> **Todos los datos son sintéticos.** No tenemos acceso a una plataforma real, así que el entorno es un simulador estocástico con semilla (`src/streamretain/env/simulator.py`). Genera las percepciones de la sección 5 del diseño y respeta las propiedades de ambiente de la sección 3. Ningún resultado de este repositorio proviene de usuarios reales.

- **Repositorio con código e instrucciones:** [criss132/streamretain-agent](https://github.com/criss132/streamretain-agent).
- **Aplicación desplegada (evidencia de funcionamiento):** [StreamRetain en Streamlit](https://streamretain-agent.streamlit.app/).
- **Documento ajustado en PDF:** [Diseno_Ajustado_StreamRetain.pdf](docs/Diseno_Ajustado_StreamRetain.pdf). Incluye la matriz de decisión y la sección 9 «Desarrollo del agente».
- **Tabla de resultados y evidencia:** [resultados.md](results/resultados.md) y [resultados.csv](results/resultados.csv).
- **Logs de las 130 pruebas:** [carpeta de evaluación](logs/eval_20261018_1853_2dbc2c8/). El [detalle por caso](results/detalle_por_caso.csv) contiene la ruta individual en la columna `log`; el [resumen por ciclo](logs/eval_20261018_1853_2dbc2c8/resumen_ciclos.csv) se puede consultar directamente en GitHub.
- **Bitácora de uso de IA y revisiones humanas:** [BITACORA_IA.md](docs/BITACORA_IA.md).

Los logs individuales están comprimidos como `.jsonl.gz`: GitHub permite descargarlos, pero no muestra su contenido como texto. Para leerlos, descomprimir con 7-Zip o usar el comando Python de la sección 5. Ejemplos: [N2, semilla 1001](logs/eval_20261018_1853_2dbc2c8/detalle_N2_s1001.jsonl.gz) y [F3, semilla 1001](logs/eval_20261018_1853_2dbc2c8/detalle_F3_s1001.jsonl.gz).

---

## 1. Instalación (Windows / PowerShell)

Requiere Python 3.13; probado con 3.13.0. Conviene crear el entorno virtual **fuera de OneDrive**:

```powershell
git clone https://github.com/criss132/streamretain-agent.git
cd streamretain-agent
py -3.13 -m venv C:\dev\venvs\agente
C:\dev\venvs\agente\Scripts\Activate.ps1
pip install -r requirements.txt
```

En Linux o macOS: `python3.13 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.

## 2. Ejecución

| Qué | Comando | Tiempo aprox. |
|---|---|---|
| Interfaz (evidencia de funcionamiento) | `streamlit run app/streamlit_app.py` | inmediato |
| Pruebas unitarias e integración | `python -m pytest -q` | 10 s |
| Matriz de decisión (Fase 1) | `python scripts/matriz_decision.py` | 1 s |
| Criterio de dificultad del simulador | `python scripts/calibrar_simulador.py` | 1 min |
| Entrenamiento inicial (regenera `models/`) | `python scripts/train_initial.py` | 1–2 min |
| Evaluación completa (130 casos) | `python scripts/run_evaluation.py --jobs 5` | ~12 min con 5 procesos |
| Evaluación parcial | `python scripts/run_evaluation.py --escenarios N2 F3 --semillas 1001 1002 --jobs 2 --salida results_parcial` | ~1 min |
| Diagramas Mermaid → PNG (requiere internet y Chrome o Edge) | `python scripts/render_diagramas.py` | 30 s |

### Uso de la interfaz
1. En la barra lateral elija un escenario, una semilla y el número de suscriptores. Las semanas de historial previo se perciben de forma automática.
2. **Ejecutar ciclo semanal** corre un ciclo percepción → decisión → acción → aprendizaje. **Todos los ciclos** corre el resto de la simulación.
3. La pestaña *Ciclo actual* muestra la tabla de riesgo con los factores principales, el estado de la API de marketing y los registros inválidos detectados.
4. La pestaña *Historial y aprendizaje* muestra las métricas por semana, los reentrenamientos con su compuerta y la descarga del log JSONL.
5. La pestaña *Suite de pruebas* corre en vivo los casos que se elijan y calcula M1–M6 contra los umbrales congelados.

**Casos sugeridos:**
- `N2`: escenario típico.
- `F1`: 10 % de registros inválidos.
- `F2`: 20 % de usuarios nuevos por semana, sin historial.
- `F3`: la API de marketing falla el 30 % de las veces.
- `L3`: tasa base de cancelación del 40 %.

## 3. Dónde está el ciclo percepción → decisión → acción

| Etapa | Archivo y método |
|---|---|
| Sensores (lote semanal crudo) | `src/streamretain/env/simulator.py` → `StreamingEnv.observar()` |
| **Percepción** | `src/streamretain/agent.py` → `StreamRetainAgent.perceive()`. Usa `perception.validar()`, `memory.Memoria` y `features.construir()` |
| **Decisión** | `agent.py` → `StreamRetainAgent.decide()`. Usa `model.ModeloRiesgo.predecir()/explicar()` y `decision.decidir()` |
| **Acción** | `agent.py` → `StreamRetainAgent.act()`. Llama a `MarketingAPI.activate_offer()` con reintentos y cola |
| **Aprendizaje** | `agent.py` → `StreamRetainAgent.learn()` y `_reentrenar()` (compuerta) |
| Orquestación y latencia | `agent.py` → `StreamRetainAgent.run_cycle()` |
| Log con marca de tiempo | `src/streamretain/logging_utils.py` → `RegistroEjecucion.evento()` |

## 4. Qué razona nuestro código y qué hace cada librería

- **Código propio:**
  - simulador del entorno y mock de la API;
  - validación de percepciones;
  - memoria por usuario y construcción de variables de tendencia;
  - regla de decisión (τ + presupuesto + cola + enfriamiento);
  - reintentos y manejo de fallas;
  - vínculo predicción ↔ resultado y compuerta de reentrenamiento;
  - explicación por oclusión;
  - evaluación M1–M6.
- **scikit-learn:** ajusta los clasificadores (regresión logística y `HistGradientBoostingClassifier` calibrado con `CalibratedClassifierCV`) y calcula el AUC y la curva ROC.
- **pandas / numpy / scipy:** manipulación de datos y muestreo aleatorio.
- **SQLite** (biblioteca estándar): memoria del agente.
- **Streamlit:** interfaz.
- **matplotlib:** figuras.
- **PyYAML:** configuración.
- **No se usa ningún LLM.**

## 5. Protocolo de pruebas (resumen)

- Umbrales, escenarios y protocolo: `config/umbrales.yaml` y `config/escenarios.yaml`. Se **congelaron antes de probar** con el tag git `umbrales-congelados` (CP2, 2026-10-18).
- **13 escenarios:** 6 normales, 4 límite y 3 de falla esperada. Cada uno se corre con **10 semillas de prueba** (1001–1010), lo que da 130 casos.
- **Semillas disjuntas:** entrenamiento 1–20, validación 501–505 y prueba 1001–1010. El modelo y el umbral τ se eligieron en validación.
- **Resultados:**
  - tabla obligatoria en `results/resultados.csv` y `results/resultados.md`;
  - detalle en `results/detalle_por_caso.csv`;
  - análisis en `docs/analisis_resultados.md`;
  - logs en `logs/eval_*/` (JSONL comprimido con gzip; se abre con 7-Zip o con `python -c "import gzip;print(gzip.open('archivo.jsonl.gz','rt',encoding='utf-8').read()[:2000])"`).

## 6. Estructura

```
config/        umbrales.yaml (congelado), escenarios.yaml, matriz.yaml
src/streamretain/
  env/simulator.py   entorno estocástico + MarketingAPI (mock con fallas)
  perception.py      validación de registros
  memory.py          memoria SQLite
  features.py        variables estáticas y de tendencia
  model.py           modelo de riesgo, umbral τ, explicación
  decision.py        τ + presupuesto top-K
  agent.py           StreamRetainAgent: perceive / decide / act / learn / run_cycle
  evaluacion.py      un caso de prueba y medidas M1–M6
scripts/       matriz_decision.py, calibrar_simulador.py, train_initial.py, run_evaluation.py, render_diagramas.py
app/           streamlit_app.py
models/        modelo_agente.joblib, baseline_logistica.joblib
tests/         pytest
results/       resultados, figuras, matriz, entrenamiento
logs/          logs de la evaluación final
docs/          fase 1, análisis, diagramas, bitácora de IA, revisión y documento ajustado
```

## 7. Despliegue en Streamlit Community Cloud

Repositorio `criss132/streamretain-agent`, rama `main`, archivo principal `app/streamlit_app.py` y Python 3.13 (en *Advanced settings*). No requiere secretos. El modelo ya entrenado viene en `models/`, así que la app arranca sin reentrenar.
