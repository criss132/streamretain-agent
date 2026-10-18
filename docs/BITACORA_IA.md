# Bitácora de uso de IA — StreamRetain-Agent (Tarea 3)

Pareja: Christian David Menco Galván (T00058749) · Levis Adrian Ortiz Cano (T00083674)

Regla: una fila por bloque de trabajo asistido por IA. Ninguna fila se inventa ni se borra. La columna **Verificación humana** la completa la pareja después de revisar el resultado.

| # | Fecha | Herramienta / modelo | Tarea | Prompt o instrucción (resumen) | Qué se usó del resultado | Verificación humana |
|---|---|---|---|---|---|---|
| 1 | 2026-10-18 | Claude Code (Claude Opus 5.5) | CP0 — lectura de la guía y de los diseños de Tarea 2; creación del repositorio, entorno virtual, estructura de carpetas, `.gitignore` y esta bitácora | "Lee PLAN_TAREA3.md, los PDFs de entradas/ y las capturas de la guía; ejecuta el CP0" | Estructura del repo, `.gitignore`, `docs/entradas_usuario.md`, esta bitácora | _(pendiente)_ |
| 2 | 2026-10-18 | Claude Code (Claude Opus 5.5) | Fase 1 — matriz de decisión ponderada: borrador de pesos, puntajes y evidencias; script de cálculo, sensibilidad ±10 pts y punto de quiebre; justificación | "Avanza a la Fase 1: config/matriz.yaml, scripts/matriz_decision.py y docs/fase1_matriz.md" | `config/matriz.yaml` (borrador), `scripts/matriz_decision.py`, `results/matriz_decision.{csv,md}`, `results/sensibilidad.csv`, `docs/fase1_matriz.md`. Los números salen del script, no del borrador del plan | Matriz aprobada por la pareja en CP1 (2026-10-18) sin cambios |
| 3 | 2026-10-18 | Claude Code (Claude Opus 5.5) | Diseño de pruebas antes de implementar: 13 escenarios (6 normales, 4 límite, 3 de falla), medidas M1–M6 con umbrales, protocolo de semillas, elección de tau en validación, etiqueta de evaluación y criterio de calibración del simulador | "Avanza al diseño de pruebas (escenarios y umbrales) para el CP2" | `config/escenarios.yaml`, `config/umbrales.yaml` (borrador CP2). Reformulación de M1 a precisión balanceada decidida antes de probar, por argumento matemático sobre el baseline | _(pendiente: la pareja valida umbrales en CP2)_ |
