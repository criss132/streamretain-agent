"""Ejecución de un caso de prueba (escenario × semilla) y cálculo de las medidas M1–M6.

Las definiciones siguen config/umbrales.yaml (congelado con el tag `umbrales-congelados`):
- M1–M4 se calculan contra la etiqueta natural del simulador, agrupando todos los ciclos.
- M5 compara las fallas inyectadas por el entorno (verdad de terreno) con lo que registró el agente.
- M6 es la latencia media por ciclo (perceive + decide + act + log).
"""

from __future__ import annotations

import math
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

from .agent import ConfigAgente, StreamRetainAgent
from .config import parametros_escenario
from .env import MarketingAPI, StreamingEnv
from .features import FEATURES_ESTATICAS
from .logging_utils import RegistroEjecucion
from .memory import Memoria
from .model import ModeloRiesgo, auc, precision_balanceada


def _metricas_clasificacion(y: np.ndarray, pred: np.ndarray, prob: np.ndarray) -> dict:
    tp = int(((pred == 1) & (y == 1)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    return {
        "accuracy": float((pred == y).mean()),
        "balanced_accuracy": precision_balanceada(y, pred),
        "recall": tp / (tp + fn) if (tp + fn) else float("nan"),
        "auc": auc(y, prob),
    }


def _precision_top_k(df: pd.DataFrame, frac: float = 0.10) -> float:
    aciertos, total = 0, 0
    for _, g in df.groupby("semana"):
        k = math.ceil(frac * len(g))
        top = g.nlargest(k, "probabilidad")
        aciertos += int(top["y"].sum())
        total += k
    return aciertos / total if total else float("nan")


def ejecutar_caso(id_escenario: str, semilla: int, modelo: ModeloRiesgo, baseline: dict | None = None,
                  registro: RegistroEjecucion | None = None, config: ConfigAgente | None = None,
                  al_terminar_ciclo=None) -> dict:
    """Corre el agente desde cero en un escenario y devuelve métricas, ciclos y predicciones."""
    p = parametros_escenario(id_escenario)
    env = StreamingEnv(p, seed=semilla)
    api = MarketingAPI(env, p["api_tasa_fallo"], p["api_tasa_timeout"], seed=semilla)
    registro = registro or RegistroEjecucion(detalle=False)
    agente = StreamRetainAgent(modelo, api, Memoria(), registro, config or ConfigAgente(semilla=semilla))

    fin_ciclos = env.inicio_ciclos + int(p["ciclos"])
    ciclos, predicciones, semanas_error, errores = [], [], set(), []
    for w in range(env.horizonte):
        try:
            if w < env.inicio_ciclos:
                agente.observar_historial(env, w)
            elif w < fin_ciclos:
                resumen = agente.run_cycle(env, w)
                ciclos.append(resumen)
                d = agente.ultimas_decisiones
                if len(d):
                    tabla = d[["probabilidad", "prediccion", "confianza", "n_semanas_historial", "ofertar"]].copy()
                    if baseline is not None:
                        est = agente.ultimo_estado.loc[d.index]
                        tabla["prob_baseline"] = baseline["modelo"].predict_proba(est[FEATURES_ESTATICAS])[:, 1]
                    tabla["semana"] = w
                    predicciones.append(tabla.reset_index())
                if al_terminar_ciclo is not None:
                    al_terminar_ciclo(agente, resumen)
            else:
                env.observar()
        except Exception as e:  # una excepción invalida el manejo de las fallas de esa semana (M5)
            semanas_error.add(w)
            errores.append({"semana": w, "error": repr(e), "traza": traceback.format_exc(limit=3)})
            registro.evento("error", w, error=repr(e))
        env.avanzar()

    pred = pd.concat(predicciones, ignore_index=True) if predicciones else pd.DataFrame()
    if len(pred):
        etiquetas = pd.concat([env.etiquetas_naturales(t).rename("y").reset_index().assign(semana=t)
                               for t in sorted(pred["semana"].unique())])
        pred = pred.merge(etiquetas, on=["user_id", "semana"], how="left")
        pred["y"] = pred["y"].fillna(0).astype(int)

    m = {"escenario": id_escenario, "tipo": p["tipo_escenario"], "semilla": semilla,
         "n_predicciones": len(pred), "tasa_positivos": float(pred["y"].mean()) if len(pred) else float("nan"),
         "errores": len(errores)}
    if len(pred):
        y, pr, prob = pred["y"].to_numpy(), pred["prediccion"].to_numpy(), pred["probabilidad"].to_numpy()
        cm = _metricas_clasificacion(y, pr, prob)
        m.update({"M1_accuracy": cm["accuracy"], "M1R_balanced_accuracy": cm["balanced_accuracy"],
                  "M2_recall": cm["recall"], "M3_precision_top_k": _precision_top_k(pred),
                  "M4_auc": cm["auc"]})
        m["baseline_nadie_accuracy"] = float((y == 0).mean())
        m["baseline_nadie_balanced_accuracy"] = 0.5
        if baseline is not None:
            pb = pred["prob_baseline"].to_numpy()
            cb = _metricas_clasificacion(y, (pb >= baseline["tau"]).astype(int), pb)
            m.update({"baseline_lr_accuracy": cb["accuracy"], "baseline_lr_balanced_accuracy": cb["balanced_accuracy"],
                      "baseline_lr_recall": cb["recall"], "baseline_lr_auc": cb["auc"],
                      "baseline_lr_precision_top_k": _precision_top_k(pred.assign(probabilidad=pb))})

    m.update(_robustez(env, agente, registro, pred, fin_ciclos, semanas_error))
    lat = [c["latencia_s"] for c in ciclos]
    m["M6_latencia_media_s"] = float(np.mean(lat)) if lat else float("nan")
    m["latencia_max_s"] = float(np.max(lat)) if lat else float("nan")
    m["n_usuarios_inicial"] = int(p["n_usuarios"])
    m["reentrenos_aceptados"] = sum(a.get("reentreno") == "aceptado" for a in agente.historial_aprendizaje)
    m["reentrenos_rechazados"] = sum(a.get("reentreno") == "rechazado" for a in agente.historial_aprendizaje)
    return {"metricas": m, "ciclos": ciclos, "predicciones": pred, "errores": errores, "agente": agente}


def _robustez(env: StreamingEnv, agente: StreamRetainAgent, registro: RegistroEjecucion,
              pred: pd.DataFrame, fin_ciclos: int, semanas_error: set) -> dict:
    # (a) registros inválidos inyectados en semanas percibidas por el agente
    corr = pd.DataFrame(env.corrupciones)
    corr = corr[corr["semana"] < fin_ciclos] if len(corr) else corr
    rech = agente.memoria.tabla("rechazos")
    rech_set = {(u, int(s)) for u, s, mot in rech.itertuples(index=False) if str(mot).strip()}
    a_total = len(corr)
    a_ok = sum((u, int(s)) in rech_set and int(s) not in semanas_error
               for u, s in corr[["user_id", "semana"]].itertuples(index=False)) if a_total else 0

    # (b) usuarios sin historial suficiente que el agente puntuó: baja confianza, sin historial inventado
    b_total = b_ok = 0
    if len(pred):
        for t, g in pred.groupby("semana"):
            nuevos = env.usuarios_sin_historial(int(t))
            sub = g[g["user_id"].isin(nuevos)]
            b_total += len(sub)
            if int(t) not in semanas_error:
                b_ok += int(((sub["confianza"] == "baja") & (sub["n_semanas_historial"] <= 1)).sum())

    # (c) fallos o timeouts de la API: cada uno debe registrarse y seguirse de reintento o cola
    acciones = [e for e in registro.eventos if e["tipo"] in ("accion", "encolado")]
    c_total = c_ok = 0
    vistos = {(e["user_id"], e["semana"], e.get("intento")) for e in acciones if e["tipo"] == "accion"}
    encolados = {(e["user_id"], e["semana"]) for e in acciones if e["tipo"] == "encolado"}
    for e in acciones:
        if e["tipo"] == "accion" and e["resultado"] in ("error", "timeout"):
            c_total += 1
            siguiente = (e["user_id"], e["semana"], e["intento"] + 1) in vistos
            if (siguiente or (e["user_id"], e["semana"]) in encolados) and e["semana"] not in semanas_error:
                c_ok += 1
    total = a_total + b_total + c_total
    return {"M5_robustez": (a_ok + b_ok + c_ok) / total if total else float("nan"),
            "fallas_registros_inyectados": a_total, "fallas_registros_manejados": a_ok,
            "fallas_sin_historial": b_total, "fallas_sin_historial_manejadas": b_ok,
            "fallas_api": c_total, "fallas_api_manejadas": c_ok}


def cargar_modelos(raiz: Path) -> tuple[ModeloRiesgo, dict]:
    import joblib
    return (ModeloRiesgo.cargar(raiz / "models" / "modelo_agente.joblib"),
            joblib.load(raiz / "models" / "baseline_logistica.joblib"))
