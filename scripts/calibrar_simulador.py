"""Verifica el criterio de dificultad del simulador congelado en config/umbrales.yaml.

Regresión logística simple sin variables de tendencia, entrenada en las semillas 1–10 y medida
en las 11–20 del escenario N2 (solo semillas de ENTRENAMIENTO). Criterio: 0,70 <= AUC <= 0,90.
Escribe results/calibracion_simulador.json.

Uso: python scripts/calibrar_simulador.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from streamretain.config import cargar_yaml  # noqa: E402
from streamretain.datos import dataset  # noqa: E402
from streamretain.features import FEATURES_ESTATICAS  # noqa: E402
from streamretain.model import auc  # noqa: E402


def main() -> None:
    entrenamiento = dataset("N2", list(range(1, 11)))
    prueba = dataset("N2", list(range(11, 21)))
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    lr.fit(entrenamiento[FEATURES_ESTATICAS], entrenamiento["y"])
    valor = auc(prueba["y"], lr.predict_proba(prueba[FEATURES_ESTATICAS])[:, 1])
    cumple = 0.70 <= valor <= 0.90
    salida = {
        "criterio": "0.70 <= AUC(LR sin tendencia, semillas 1-10 -> 11-20, N2) <= 0.90",
        "auc": round(valor, 4),
        "cumple": cumple,
        "tasa_positivos_entrenamiento": round(float(entrenamiento["y"].mean()), 4),
        "filas_entrenamiento": len(entrenamiento),
        "filas_prueba": len(prueba),
        "senal": cargar_yaml("escenarios.yaml")["senal"],
    }
    (RAIZ / "results").mkdir(exist_ok=True)
    (RAIZ / "results" / "calibracion_simulador.json").write_text(
        json.dumps(salida, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(salida, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
