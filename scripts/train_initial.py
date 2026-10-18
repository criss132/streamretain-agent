"""Entrenamiento inicial del agente con "pre-historia" SINTÉTICA etiquetada.

Protocolo (config/umbrales.yaml):
- Entrena candidatos (regresión logística y gradient boosting calibrado) con las semillas de
  entrenamiento del escenario N2.
- Elige el candidato de mayor AUC-ROC en las semillas de validación de N2.
- tau = umbral que maximiza el índice de Youden en validación.
- Entrena también el baseline "regresión logística simple sin variables de tendencia".
Las semillas de prueba no se tocan aquí.

Salidas: models/modelo_agente.joblib, models/baseline_logistica.joblib, results/entrenamiento.json

Uso: python scripts/train_initial.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from streamretain.config import rango_semillas  # noqa: E402
from streamretain.datos import dataset  # noqa: E402
from streamretain.features import FEATURES_ESTATICAS  # noqa: E402
from streamretain.model import TIPOS, ModeloRiesgo, auc, elegir_tau, precision_balanceada  # noqa: E402

ESCENARIO = "N2"
MUESTRA_BASE = 20000


def main() -> None:
    t0 = time.time()
    entr = dataset(ESCENARIO, rango_semillas("entrenamiento"))
    val = dataset(ESCENARIO, rango_semillas("validacion"))
    print(f"Datos: entrenamiento {len(entr)} filas (tasa {entr.y.mean():.3f}), "
          f"validación {len(val)} filas (tasa {val.y.mean():.3f}) [{time.time() - t0:.0f} s]")

    candidatos, resumen = {}, {}
    for tipo in TIPOS:
        t1 = time.time()
        m = ModeloRiesgo.entrenar(tipo, entr, semilla=0, guardar_muestra=MUESTRA_BASE)
        p = m.predecir(val)["probabilidad"].to_numpy()
        candidatos[tipo] = (m, p)
        resumen[tipo] = {"auc_validacion": round(auc(val["y"], p), 4),
                         "segundos_entrenamiento": round(time.time() - t1, 1)}
        print(f"  {tipo:<18} AUC validación = {resumen[tipo]['auc_validacion']:.4f} "
              f"({resumen[tipo]['segundos_entrenamiento']} s)")

    elegido = max(resumen, key=lambda k: resumen[k]["auc_validacion"])
    modelo, p_val = candidatos[elegido]
    modelo.tau = elegir_tau(val["y"].to_numpy(), p_val)
    pred = (p_val >= modelo.tau).astype(int)
    modelo.info.update({"elegido_por": "mayor AUC en validación (N2, semillas 501-505)",
                        "auc_validacion": resumen[elegido]["auc_validacion"],
                        "tau_criterio": "Youden en validación"})
    modelo.guardar(RAIZ / "models" / "modelo_agente.joblib")

    # Baseline: regresión logística simple sin variables de tendencia
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    lr.fit(entr[FEATURES_ESTATICAS], entr["y"])
    p_lr = lr.predict_proba(val[FEATURES_ESTATICAS])[:, 1]
    tau_lr = elegir_tau(val["y"].to_numpy(), p_lr)
    joblib.dump({"modelo": lr, "tau": tau_lr, "features": FEATURES_ESTATICAS},
                RAIZ / "models" / "baseline_logistica.joblib", compress=3)

    salida = {
        "escenario": ESCENARIO,
        "semillas_entrenamiento": rango_semillas("entrenamiento"),
        "semillas_validacion": rango_semillas("validacion"),
        "filas_entrenamiento": len(entr), "filas_validacion": len(val),
        "tasa_positivos_entrenamiento": round(float(entr.y.mean()), 4),
        "candidatos": resumen,
        "modelo_elegido": elegido,
        "tau": round(modelo.tau, 6),
        "validacion_con_tau": {
            "precision_balanceada": round(precision_balanceada(val["y"], pred), 4),
            "recall": round(float(pred[val["y"].to_numpy() == 1].mean()), 4),
            "accuracy": round(float((pred == val["y"].to_numpy()).mean()), 4),
        },
        "baseline_logistica_sin_tendencia": {"auc_validacion": round(auc(val["y"], p_lr), 4),
                                             "tau": round(tau_lr, 6)},
        "baseline_nadie_cancela_accuracy_validacion": round(float(1 - val["y"].mean()), 4),
        "segundos_totales": round(time.time() - t0, 1),
    }
    (RAIZ / "results").mkdir(exist_ok=True)
    (RAIZ / "results" / "entrenamiento.json").write_text(json.dumps(salida, indent=2, ensure_ascii=False),
                                                         encoding="utf-8")
    print(json.dumps({k: salida[k] for k in ("modelo_elegido", "tau", "validacion_con_tau",
                                             "baseline_logistica_sin_tendencia")}, indent=2))
    print(f"Listo en {time.time() - t0:.0f} s")


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
