# Entrega en SAVIO: Segundo Parcial [Agentes Inteligentes]

- **Cierre:** lunes 19 de octubre de 2026, 07:00 (America/Bogotá).
- **Una sola entrega por pareja.** La sube la pareja; Claude Code no sube nada a SAVIO.

## Qué se sube (checklist de la guía)

- [ ] **Documento ajustado en PDF:** `docs/Diseno_Ajustado_StreamRetain.pdf`. Incluye la matriz de decisión y la sección 9 «Desarrollo del agente». Fuente editable: `docs/Diseno_Ajustado_StreamRetain.docx`.
- [ ] **Enlace al repositorio** con README e instrucciones de ejecución: https://github.com/criss132/streamretain-agent
- [ ] **Enlace a la plataforma desplegada:** _[pendiente: URL de Streamlit Cloud]_. Video de respaldo (≤ 20 min): _[pendiente]_.
- [ ] **Logs de las pruebas** (CSV, JSON o TXT) referenciados en la tabla de resultados:
  - `results/resultados.csv`: tabla obligatoria.
  - `results/detalle_por_caso.csv`: 130 casos con todas las métricas.
  - `results/resumen_ciclos.csv`: cada ciclo semanal de cada caso.
  - `logs/eval_20261018_1853_2dbc2c8/`: JSONL comprimido con gzip, uno por caso; el detalle completo está en la semilla 1001.
- [ ] **Bitácora de uso de IA:** `docs/BITACORA_IA.md`. La pareja debe completar la columna «Verificación humana».

## Antes de subir

1. Completar `docs/enlaces.yaml` con la URL del despliegue, el enlace del video y los minutos del video donde aparece cada medida.
2. Regenerar el documento con `python scripts/build_documento.py` (Word debe estar instalado).
3. Revisar que el PDF no tenga marcadores `[pendiente]`.
4. Hacer commit y push de los cambios finales.
