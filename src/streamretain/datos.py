"""Generación de conjuntos etiquetados SINTÉTICOS para entrenar, validar y calibrar.

Se corre el entorno sin intervenciones y se construyen las features con la misma función
que usa el agente (`features.construir`), para evitar diferencias entre entrenamiento y uso.
La etiqueta es la natural (cancelación programada en las 4 semanas siguientes).
"""

from __future__ import annotations

import pandas as pd

from . import features as F
from .config import parametros_escenario
from .env import StreamingEnv
from .perception import validar


def dataset_semilla(id_escenario: str, semilla: int, params: dict | None = None) -> pd.DataFrame:
    p = params or parametros_escenario(id_escenario)
    env = StreamingEnv(p, seed=semilla)
    obs: list[pd.DataFrame] = []
    filas: list[pd.DataFrame] = []
    conteo = pd.Series(dtype=int)
    ciclos = range(env.inicio_ciclos, env.inicio_ciclos + int(p["ciclos"]))
    for w in range(env.horizonte):
        validos, _ = validar(env.observar())
        obs.append(validos)
        conteo = conteo.add(validos.groupby("user_id").size(), fill_value=0)
        if w in ciclos:
            ventana = pd.concat(obs[-F.VENTANA:], ignore_index=True)
            f = F.construir(ventana, w, conteo.astype(int))
            f["semana"] = w
            filas.append(f)
        env.avanzar()
    X = pd.concat(filas).reset_index()
    y = pd.concat([env.etiquetas_naturales(w).rename("y").reset_index().assign(semana=w) for w in ciclos])
    X = X.merge(y, on=["user_id", "semana"], how="left")
    X["semilla"] = semilla
    X["escenario"] = id_escenario
    return X


def dataset(id_escenario: str, semillas: list[int], params: dict | None = None) -> pd.DataFrame:
    return pd.concat([dataset_semilla(id_escenario, s, params) for s in semillas], ignore_index=True)
