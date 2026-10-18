"""Módulo de decisión: umbral tau + presupuesto top-K.

- prediccion = 1 si p >= tau (clasificación usada en M1, M1R y M2).
- Se ofertan los usuarios con p >= tau de mayor riesgo, hasta K = presupuesto × base puntuada.
- Los usuarios en cola (oferta fallida en un ciclo anterior) se reenvían primero y consumen cupo.
- No se repite oferta a quien la recibió en las últimas `enfriamiento` semanas.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def decidir(pred: pd.DataFrame, tau: float, presupuesto_frac: float,
            cola: list[str] | None = None, recientes: set[str] | None = None) -> pd.DataFrame:
    """`pred` indexado por user_id con columna `probabilidad`. Devuelve una copia con
    prediccion, rango_riesgo, ofertar, prioridad y motivo."""
    df = pred.copy()
    cola = [u for u in (cola or []) if u in df.index]
    recientes = recientes or set()
    df["prediccion"] = (df["probabilidad"] >= tau).astype(int)
    df["rango_riesgo"] = df["probabilidad"].rank(ascending=False, method="first").astype(int)
    K = math.ceil(presupuesto_frac * len(df))
    elegibles = df[(df["prediccion"] == 1) & ~df.index.isin(recientes) & ~df.index.isin(cola)]
    nuevos = elegibles.sort_values("probabilidad", ascending=False).index[:max(K - len(cola), 0)]
    df["ofertar"] = df.index.isin(nuevos) | df.index.isin(cola)
    df["prioridad"] = np.select([df["ofertar"], df["prediccion"] == 1], ["alta", "media"], "baja")
    motivo = np.select(
        [df.index.isin(cola), df.index.isin(nuevos),
         (df["prediccion"] == 1) & df.index.isin(recientes), df["prediccion"] == 1],
        ["reintento de oferta en cola", f"p >= tau y dentro del top-{K}",
         "p >= tau, pero ya recibió oferta reciente", f"p >= tau, fuera del presupuesto top-{K}"],
        "p < tau")
    df["motivo"] = motivo
    return df
