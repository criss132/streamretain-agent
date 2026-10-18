"""Percepción: validación de los registros crudos que llegan cada semana.

Los registros inválidos no se descartan en silencio: se separan con su motivo para que el
agente los registre en memoria y en el log.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

PLANES_VALIDOS = ("basico", "estandar", "premium")
COLUMNAS = ("user_id", "semana", "horas_vistas", "dias_desde_ultimo_login",
            "tipo_plan", "cambio_metodo_pago")
RANGOS = {
    "horas_vistas": (0.0, 168.0),             # horas en una semana
    "dias_desde_ultimo_login": (0.0, 365.0),
}


def validar(lote: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Separa el lote en (válidos, rechazados). `rechazados` incluye la columna `motivo`."""
    faltantes = [c for c in COLUMNAS if c not in lote.columns]
    if faltantes:
        raise ValueError(f"El lote no tiene las columnas requeridas: {faltantes}")

    df = lote.loc[:, list(COLUMNAS)].copy()
    motivos = pd.Series("", index=df.index, dtype=object)

    def marcar(mascara: pd.Series, texto: str) -> None:
        nonlocal motivos
        motivos = motivos.where(~mascara, motivos.where(motivos == "", motivos + "; ") + texto)

    ids = df["user_id"].astype(object)
    marcar(ids.isna() | (ids.astype(str).str.strip() == ""), "user_id vacío")

    for col, (lo, hi) in RANGOS.items():
        valores = pd.to_numeric(df[col], errors="coerce")
        marcar(valores.isna(), f"{col} faltante o no numérico")
        marcar(valores.notna() & (valores < lo), f"{col} negativo")
        marcar(valores.notna() & (valores > hi), f"{col} fuera de rango (> {hi:g})")
        df[col] = valores

    marcar(~df["tipo_plan"].isin(PLANES_VALIDOS), "tipo_plan desconocido")
    pago = pd.to_numeric(df["cambio_metodo_pago"], errors="coerce")
    marcar(~pago.isin([0, 1]), "cambio_metodo_pago no binario")
    df["cambio_metodo_pago"] = pago

    invalido = motivos != ""
    rechazados = lote.loc[invalido, ["user_id", "semana"]].copy()
    rechazados["motivo"] = motivos[invalido].values
    validos = df.loc[~invalido].copy()
    validos["cambio_metodo_pago"] = validos["cambio_metodo_pago"].astype(int)
    validos["dias_desde_ultimo_login"] = validos["dias_desde_ultimo_login"].astype(float)
    validos["horas_vistas"] = validos["horas_vistas"].astype(float)
    validos["tipo_plan"] = validos["tipo_plan"].astype(str)
    validos["user_id"] = validos["user_id"].astype(str)
    return validos.reset_index(drop=True), rechazados.reset_index(drop=True)


def es_valido(registro: dict) -> bool:
    """Atajo para validar un único registro (útil en pruebas)."""
    v, _ = validar(pd.DataFrame([registro]))
    return len(v) == 1 and not np.isnan(v["horas_vistas"].iloc[0])
