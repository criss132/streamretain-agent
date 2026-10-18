"""Modelo de riesgo de cancelación (elemento de desempeño del agente de aprendizaje).

Dos sub-modelos:
- `completo`: usa variables estáticas + de tendencia; se aplica a usuarios con historial suficiente.
- `sin_tendencia`: solo variables estáticas; se aplica a usuarios sin historial suficiente y su
  predicción se marca como de baja confianza.

Explicación local por oclusión: el aporte de una variable es cuánto cambia la probabilidad si
esa variable se reemplaza por su valor de referencia (mediana de entrenamiento). Se usa en lugar
de SHAP porque funciona igual con cualquier modelo calibrado y es rápido (ver sección 9.6).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .features import FEATURES_COMPLETAS, FEATURES_ESTATICAS

TIPOS = ("logistica", "gradient_boosting")
GRUPOS_EXPLICACION = {
    "horas vistas en la semana": ["horas_actual"],
    "días sin iniciar sesión": ["dias_sin_login"],
    "cambio reciente de método de pago": ["cambio_pago"],
    "tipo de plan": ["plan_basico", "plan_estandar", "plan_premium"],
    "variación semanal del consumo": ["variacion_semanal"],
    "promedio de consumo (4 semanas)": ["promedio_4s"],
    "consumo actual vs. semanas previas": ["ratio_vs_previo"],
    "pendiente del consumo (4 semanas)": ["pendiente_4s"],
    "semanas consecutivas en descenso": ["semanas_descenso"],
    "cambio en días sin login": ["delta_dias"],
}


def construir_estimador(tipo: str, semilla: int = 0):
    if tipo == "logistica":
        return make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    if tipo == "gradient_boosting":
        base = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08, max_leaf_nodes=31,
                                              l2_regularization=1.0, random_state=semilla)
        return CalibratedClassifierCV(base, method="isotonic", cv=3)
    raise ValueError(f"Tipo de modelo desconocido: {tipo}")


def elegir_tau(y: np.ndarray, p: np.ndarray) -> float:
    """Umbral que maximiza el índice de Youden (recall + especificidad − 1)."""
    fpr, tpr, thr = roc_curve(y, p)
    j = tpr - fpr
    k = int(np.argmax(j[1:])) + 1  # thr[0] es +inf
    return float(thr[k])


def precision_balanceada(y: np.ndarray, pred: np.ndarray) -> float:
    y, pred = np.asarray(y), np.asarray(pred)
    pos, neg = y == 1, y == 0
    rec = (pred[pos] == 1).mean() if pos.any() else np.nan
    esp = (pred[neg] == 0).mean() if neg.any() else np.nan
    return float(np.nanmean([rec, esp]))


@dataclass
class ModeloRiesgo:
    tipo: str
    completo: object
    sin_tendencia: object
    referencia: dict[str, float]
    tau: float = 0.5
    version: int = 1
    info: dict = field(default_factory=dict)
    muestra_base: pd.DataFrame | None = None   # muestra de entrenamiento para reentrenar

    # ------------------------------------------------------------ entrenamiento
    @classmethod
    def entrenar(cls, tipo: str, datos: pd.DataFrame, semilla: int = 0, tau: float = 0.5,
                 version: int = 1, guardar_muestra: int = 0) -> "ModeloRiesgo":
        """`datos` debe tener las columnas de FEATURES_COMPLETAS, `historial_suficiente` e `y`."""
        suf = datos["historial_suficiente"].astype(bool)
        completo = construir_estimador(tipo, semilla).fit(
            datos.loc[suf, FEATURES_COMPLETAS], datos.loc[suf, "y"].astype(int))
        sin_t = construir_estimador(tipo, semilla).fit(datos[FEATURES_ESTATICAS], datos["y"].astype(int))
        referencia = datos.loc[suf, FEATURES_COMPLETAS].median().to_dict()
        for c in ("plan_basico", "plan_estandar", "plan_premium"):
            referencia[c] = float(datos[c].mean())
        muestra = None
        if guardar_muestra:
            cols = FEATURES_COMPLETAS + ["historial_suficiente", "y"]
            muestra = datos[cols].sample(n=min(guardar_muestra, len(datos)), random_state=semilla)
        info = {"entrenado": dt.datetime.now().isoformat(timespec="seconds"),
                "filas": int(len(datos)), "filas_completo": int(suf.sum()),
                "tasa_positivos": float(datos["y"].mean())}
        return cls(tipo, completo, sin_t, referencia, tau, version, info, muestra)

    # ------------------------------------------------------------ inferencia
    def predecir(self, feats: pd.DataFrame) -> pd.DataFrame:
        """Probabilidad calibrada de cancelar en 4 semanas, sub-modelo usado y confianza."""
        out = pd.DataFrame(index=feats.index)
        out["probabilidad"] = np.nan
        suf = feats["historial_suficiente"].astype(bool).to_numpy()
        if suf.any():
            out.loc[suf, "probabilidad"] = self.completo.predict_proba(
                feats.loc[suf, FEATURES_COMPLETAS])[:, 1]
        if (~suf).any():
            out.loc[~suf, "probabilidad"] = self.sin_tendencia.predict_proba(
                feats.loc[~suf, FEATURES_ESTATICAS])[:, 1]
        out["modelo_usado"] = np.where(suf, "completo", "sin_tendencia")
        out["confianza"] = np.where(suf, "normal", "baja")
        return out

    def explicar(self, feats: pd.DataFrame, k: int = 3) -> list[list[dict]]:
        """Top-k factores por usuario (aporte con signo: + aumenta el riesgo)."""
        if feats.empty:
            return []
        base = self.predecir(feats)["probabilidad"].to_numpy()
        suf = feats["historial_suficiente"].astype(bool).to_numpy()
        aportes = {}
        for nombre, cols in GRUPOS_EXPLICACION.items():
            ocl = feats.copy()
            for c in cols:
                ocl[c] = self.referencia[c]
            p = self.predecir(ocl)["probabilidad"].to_numpy()
            ap = base - p
            if not set(cols) <= set(FEATURES_ESTATICAS):
                ap = np.where(suf, ap, np.nan)   # sin historial no hay variables de tendencia
            aportes[nombre] = ap
        A = pd.DataFrame(aportes, index=feats.index)
        salida = []
        for uid, fila in A.iterrows():
            top = fila.dropna().reindex(fila.dropna().abs().sort_values(ascending=False).index)[:k]
            salida.append([{"factor": n, "aporte": round(float(v), 4)} for n, v in top.items()])
        return salida

    # ------------------------------------------------------------ persistencia
    def guardar(self, ruta: Path) -> None:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, ruta, compress=3)

    @staticmethod
    def cargar(ruta: Path) -> "ModeloRiesgo":
        return joblib.load(ruta)


def auc(y, p) -> float:
    y = np.asarray(y)
    return float(roc_auc_score(y, p)) if 0 < y.sum() < len(y) else float("nan")
