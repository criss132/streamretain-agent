# Análisis de resultados (Fase 3)

**Fuente:** `results/resultados.csv` y `results/detalle_por_caso.csv`, generados por `python scripts/run_evaluation.py` (commit `2dbc2c8`). Son 130 casos: 13 escenarios × 10 semillas de prueba. Los umbrales se congelaron antes de probar (tag `umbrales-congelados`) y no se cambió nada después de ver los resultados. **Todos los datos son sintéticos.**

| Medida | Umbral | Resultado (media ± d.e.) | ¿Cumple? | Casos que lo alcanzan |
|---|---|---|---|---|
| M1 Accuracy (SMART original) | ≥ 75 % | 74,5 % ± 1,2 % | No | 44 % |
| M1R Precisión balanceada (SMART reformulada) | ≥ 75 % | 69,3 % ± 0,9 % | No | 0 % |
| M2 Recall de "cancela" | ≥ 60 % | 61,1 % ± 2,5 % | Sí | 65 % |
| M3 Precisión en el top-10 % | ≥ 50 % | 57,7 % ± 12,7 % | Sí | 89 % |
| M4 AUC-ROC | ≥ 0,80 | 0,761 ± 0,011 | No | 0 % |
| M5 Robustez ante fallas | 100 % | 100 % ± 0 | Sí | 100 % |
| M6 Latencia por ciclo | ≤ 10 s | 1,73 s ± 0,39 s (máx. 3,65 s) | Sí | 100 % |

## Lo que se cumplió

- **M5 (robustez).** No hubo ni una excepción en 130 ejecuciones. Todas las fallas se manejaron como indica el protocolo:
  - los 51.194 registros inválidos se rechazaron con su motivo;
  - las 68.640 predicciones de usuarios sin historial se marcaron como de baja confianza, sin historial inventado;
  - los 12.441 fallos o timeouts de la API se reintentaron o se dejaron en cola.
- **M6 (latencia).** El ciclo tarda 1,7 s de media y 3,65 s como máximo, medido con 5 procesos en paralelo. El escenario más lento es F2 (2,9 s), porque la base crece con los usuarios nuevos.
- **M2 (recall)** se cumple **por poco** (61,1 %, y solo el 65 % de los casos llega al umbral). En L3 (tasa base del 40 %) baja a 56,6 %, porque τ se eligió en validación con una tasa del 15 %.
- **M3 (precisión en el top-10 %)** se cumple en promedio, pero depende de la tasa base: 39 % en N1 (tasa 10 %), 55 % en N2 y 94 % en L3. Con pocas cancelaciones, el top-10 % no alcanza a llenarse de casos reales.

## Lo que no se cumplió y por qué

- **M1 (accuracy, 74,5 %).** Queda por debajo del baseline trivial "nadie cancela", que logra 83,9 % de media en los 130 casos (85 % en N2). Es el efecto que anticipamos en el CP2 (por eso existe M1R): τ maximiza el índice de Youden, es decir, acepta falsos positivos para detectar a quien sí cancela. Un τ que maximizara la accuracy se acercaría a "nadie cancela" y no serviría para retener a nadie.
- **M1R (69,3 %) y M4 (0,761): la causa principal es la falta de señal.** Cruzamos cada predicción con el estado interno del simulador:
  - Solo el **57,4 %** de quienes cancelan en las 4 semanas siguientes ya mostraba alguna señal cuando se hizo la predicción.
  - El resto todavía no había decidido cancelar: el consumo empieza a caer 3 semanas antes de la baja, así que quien cancela en la semana t+4 aún no ha cambiado en t.
  - Otro grupo cancela sin ninguna señal previa, que es el 25 % configurado en el simulador.
  - El agente detecta al **80 %** de los que tienen señal y solo al **36 %** de los que no la tienen.
  - El AUC es casi idéntico en los 13 escenarios (d.e. 0,011). Eso apunta a un techo de información de los sensores, no a un error del modelo ni a sobreajuste.
- **Estabilidad.** La precisión balanceada se mantiene entre 68,8 % y 70,3 % en todos los escenarios, incluidos los límite y los de falla. La deriva de comportamiento (L4) solo baja la accuracy a 72,5 %.

## Comparación con los baselines (media de los 130 casos)

| | Precisión balanceada | Recall | Precisión top-K | AUC |
|---|---|---|---|---|
| **Agente** (gradient boosting con variables de tendencia) | **69,3 %** | **61,1 %** | **54,2 %** | **0,761** |
| Regresión logística sin tendencia | 68,1 % | 55,1 % | 50,9 % | 0,747 |
| "Nadie cancela" | 50,0 % | 0 % | — | 0,500 |

La memoria del agente y sus variables de tendencia aportan una mejora real pero modesta: +6 puntos de recall y +0,014 de AUC. En cuanto al aprendizaje, la compuerta aceptó 58 reentrenamientos y rechazó 82. Esto muestra que no acepta modelos peores, pero también que los datos nuevos sin intervención mejoran poco al modelo.

## Qué cambiaríamos

1. **Más sensores que anticipen la decisión**, por ejemplo visitas a la página de cancelación, tickets de soporte o pagos rechazados. Es lo único que puede subir el techo de M1R y M4.
2. **Alinear el horizonte con la señal:** predecir a 2 semanas, o medir M1R solo sobre los usuarios con al menos 2 semanas de comportamiento observable. Habría que declararlo como reformulación, no como ajuste a los resultados.
3. **τ adaptativo a la tasa base** (recalibrar con los resultados que van llegando) para no perder recall cuando la cancelación sube, como en L3.
4. **Memoria más larga:** una línea base individual de 8 o más semanas, en lugar de la ventana de 4.
5. **Grupo de control** en producción, para medir sin la ventaja de la etiqueta sin intervención que tiene el simulador.
