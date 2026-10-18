"""Construcción de variables a partir de la memoria (sección 8 del diseño, "Memoria").

Variables estáticas: consumo y recencia actuales, plan y cambio de pago.
Variables de tendencia (requieren >= 2 observaciones válidas en la ventana de 4 semanas):
variación semanal, promedio de 4 semanas, razón actual/promedio previo, pendiente,
semanas consecutivas en descenso y cambio en días sin login.
Si no hay historial suficiente, las variables de tendencia quedan en NaN: nunca se
rellenan con historial inventado.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

FEATURES_ESTATICAS = ["horas_actual", "dias_sin_login", "cambio_pago",
                      "plan_basico", "plan_estandar", "plan_premium"]
FEATURES_TENDENCIA = ["variacion_semanal", "promedio_4s", "ratio_vs_previo",
                      "pendiente_4s", "semanas_descenso", "delta_dias"]
FEATURES_COMPLETAS = FEATURES_ESTATICAS + FEATURES_TENDENCIA
VENTANA = 4
MIN_OBS_TENDENCIA = 2


def _ultimo_valido(m: np.ndarray) -> np.ndarray:
    """Último valor no-NaN por fila (NaN si no hay)."""
    out = np.full(m.shape[0], np.nan)
    for j in range(m.shape[1]):
        col = m[:, j]
        out = np.where(~np.isnan(col), col, out)
    return out


def construir(ventana: pd.DataFrame, semana: int, semanas_historial: pd.Series | None = None) -> pd.DataFrame:
    """Devuelve un DataFrame indexado por user_id con las features de los usuarios que tienen
    observación válida en `semana`. Incluye `n_obs_ventana`, `n_semanas_historial` e
    `historial_suficiente`."""
    columnas = FEATURES_COMPLETAS + ["n_obs_ventana", "n_semanas_historial", "historial_suficiente"]
    actual = ventana[ventana["semana"] == semana].set_index("user_id")
    if actual.empty:
        return pd.DataFrame(columns=columnas, index=pd.Index([], name="user_id"))
    usuarios = actual.index
    semanas = list(range(semana - VENTANA + 1, semana + 1))
    v = ventana[ventana["user_id"].isin(usuarios)]
    H = (v.pivot_table(index="user_id", columns="semana", values="horas_vistas", aggfunc="last")
         .reindex(index=usuarios, columns=semanas).to_numpy(dtype=float))
    D = (v.pivot_table(index="user_id", columns="semana", values="dias_desde_ultimo_login", aggfunc="last")
         .reindex(index=usuarios, columns=semanas).to_numpy(dtype=float))

    h_t, d_t = H[:, -1], D[:, -1]
    h_prev, d_prev = _ultimo_valido(H[:, :-1]), _ultimo_valido(D[:, :-1])
    validos = ~np.isnan(H)
    n_obs = validos.sum(axis=1)
    suficiente = n_obs >= MIN_OBS_TENDENCIA

    with np.errstate(invalid="ignore", divide="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)  # filas sin datos → NaN, es lo esperado
        promedio = np.nanmean(H, axis=1)
        previo = np.nanmean(H[:, :-1], axis=1) if H.shape[1] > 1 else np.full(len(h_t), np.nan)
        x = np.arange(H.shape[1], dtype=float)[None, :].repeat(H.shape[0], axis=0)
        x = np.where(validos, x, np.nan)
        mx, my = np.nanmean(x, axis=1, keepdims=True), np.nanmean(H, axis=1, keepdims=True)
        pendiente = np.nansum((x - mx) * (H - my), axis=1) / np.nansum((x - mx) ** 2, axis=1)

    descenso = np.zeros(len(h_t))
    sigue = np.ones(len(h_t), dtype=bool)
    for j in range(H.shape[1] - 1, 0, -1):
        baja = validos[:, j] & validos[:, j - 1] & (H[:, j] < H[:, j - 1])
        sigue &= baja
        descenso += sigue

    plan = actual["tipo_plan"].astype(str)
    out = pd.DataFrame({
        "horas_actual": h_t,
        "dias_sin_login": d_t,
        "cambio_pago": actual["cambio_metodo_pago"].astype(float).to_numpy(),
        "plan_basico": (plan == "basico").astype(float).to_numpy(),
        "plan_estandar": (plan == "estandar").astype(float).to_numpy(),
        "plan_premium": (plan == "premium").astype(float).to_numpy(),
        "variacion_semanal": (h_t - h_prev) / (h_prev + 1.0),
        "promedio_4s": promedio,
        "ratio_vs_previo": (h_t + 1.0) / (previo + 1.0),
        "pendiente_4s": pendiente,
        "semanas_descenso": descenso,
        "delta_dias": d_t - d_prev,
        "n_obs_ventana": n_obs,
    }, index=usuarios)
    out.loc[~suficiente, FEATURES_TENDENCIA] = np.nan
    if semanas_historial is not None:
        out["n_semanas_historial"] = semanas_historial.reindex(usuarios).fillna(0).astype(int).to_numpy()
    else:
        out["n_semanas_historial"] = n_obs
    out["historial_suficiente"] = suficiente
    return out
