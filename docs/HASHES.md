# Equivalencia de hashes de commits (reescritura del historial, 18-oct-2026)

El 18 de octubre de 2026, después del CP4 y a pedido de la pareja, se reescribió el historial de git para quitar de los mensajes de commit la línea de coautoría `Co-Authored-By: Claude …`. El uso de IA sigue declarado en `docs/BITACORA_IA.md`.

Con `git filter-branch --msg-filter` solo cambiaron los mensajes. **El contenido de cada commit (archivos), los autores, las fechas y el orden son idénticos**, pero cambian los hashes. El tag `umbrales-congelados` se movió al mismo commit del CP2 (antes `f79ba73`, ahora `52b67be`) y conserva su fecha original (18-oct-2026 18:29).

Algunos archivos citan hashes **anteriores** a la reescritura, por ejemplo `results/entorno_evaluacion.json` (`"commit": "2dbc2c8"`), la carpeta `logs/eval_20261018_1853_2dbc2c8/`, la bitácora y el análisis. Esta tabla permite encontrar el commit actual equivalente:

| Hash anterior | Hash actual | Fecha | Commit |
|---|---|---|---|
| 92170cc | 210db17 | 2026-10-18 18:17 | CP0: estructura inicial del repositorio, .gitignore y bitácora de IA |
| bdddc87 | b7c8cac | 2026-10-18 18:23 | Fase 1: matriz de decisión ponderada, sensibilidad y justificación (borrador CP1) |
| f28e448 | 439e3dc | 2026-10-18 18:26 | Diseño de pruebas: escenarios y umbrales (borrador CP2, sin congelar) |
| f79ba73 | 52b67be | 2026-10-18 18:29 | CP2: umbrales, escenarios y protocolo aprobados y congelados (**tag `umbrales-congelados`**) |
| 47d092e | 9bb5736 | 2026-10-18 18:38 | Fase 2: simulador, percepción, memoria, features y modelo; calibración del simulador |
| 358168a | 4413b34 | 2026-10-18 18:43 | Corrige simulador (semanas_decaimiento_previo) y revierte la calibración previa |
| 55d2ae3 | 3c8c497 | 2026-10-18 18:49 | Fase 2: decisión, agente, log, entrenamiento inicial, núcleo de evaluación y pruebas |
| 2dbc2c8 | e8b855f | 2026-10-18 18:53 | Fase 3: script de evaluación (**commit con el que se corrió la evaluación final**) |
| e39cd0d | 255fecf | 2026-10-18 19:04 | Fase 3: resultados (130 casos), logs, análisis, app, diagramas, README y guion |
| 039f687 | 66ae88d | 2026-10-18 19:14 | Documento de diseño ajustado (DOCX/PDF) |
| 1e69a2d | 798088e | 2026-10-18 19:37 | Corrige .gitignore (paquete src/streamretain/env) |
| 67269a4 | 5c38d27 | 2026-10-18 19:41 | CP4: URL del despliegue en README, enlaces, ENTREGA y PDF |
| ddc45c9 | ce3e1cd | 2026-10-18 19:45 | Guía de revisión para el compañero |

Se puede verificar que la evaluación final corrió **después** del congelamiento de los umbrales con:

```
git log --oneline umbrales-congelados..e8b855f
```
