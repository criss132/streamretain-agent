"""StreamRetain-Agent: agente de aprendizaje (con estado interno por usuario).

Ciclo explícito percepción → decisión → acción (+ aprendizaje):

    perceive(lote, semana)   valida registros crudos, actualiza la memoria y arma el estado
    decide(estado, semana)   estima el riesgo, aplica tau + presupuesto y explica los factores
    act(decisiones, semana)  activa ofertas en la API de marketing con reintentos y cola
    learn(semana, env)       vincula predicción ↔ resultado a las 4 semanas y reentrena con
                             compuerta (solo acepta un modelo que mantenga o mejore la medida)
    run_cycle(env, semana)   orquesta el ciclo semanal y mide la latencia
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import features as F
from .decision import decidir
from .env.simulator import MarketingAPI, MarketingAPIError, MarketingTimeout, StreamingEnv
from .logging_utils import RegistroEjecucion
from .memory import Memoria
from .model import ModeloRiesgo, precision_balanceada
from .perception import validar

COLUMNAS_MEMORIA = F.FEATURES_COMPLETAS + ["historial_suficiente"]


@dataclass
class ConfigAgente:
    presupuesto_frac: float = 0.10     # K = 10 % de la base puntuada
    max_reintentos: int = 3            # reintentos tras el primer intento fallido
    espera_reintento_s: float = 0.0    # espera entre reintentos (0 en simulación)
    enfriamiento_semanas: int = 4      # no repetir oferta dentro de esta ventana
    vida_cola_semanas: int = 4         # una entrada de la cola vence a las 4 semanas
    reentreno_cada: int = 4            # ciclos entre intentos de reentrenamiento
    min_filas_reentreno: int = 500
    fraccion_holdout: float = 0.30
    explicar_top: int = 3
    semilla: int = 0


def _a_registros(df: pd.DataFrame) -> list[dict]:
    return df.astype(object).where(df.notna(), None).to_dict(orient="records")


class StreamRetainAgent:
    def __init__(self, modelo: ModeloRiesgo, api: MarketingAPI, memoria: Memoria | None = None,
                 registro: RegistroEjecucion | None = None, config: ConfigAgente | None = None):
        self.modelo = modelo
        self.api = api
        self.memoria = memoria or Memoria()
        self.registro = registro or RegistroEjecucion()
        self.cfg = config or ConfigAgente()
        self._ciclos = 0
        self._rng = np.random.default_rng(self.cfg.semilla)
        self.semanas_decididas: list[int] = []
        # último estado de cada etapa (lo usan la interfaz y la evaluación)
        self.ultimos_rechazos = pd.DataFrame()
        self.ultimas_decisiones = pd.DataFrame()
        self.ultimas_acciones: list[dict] = []
        self.historial_aprendizaje: list[dict] = []

    # ================================================================ PERCEPCIÓN
    def perceive(self, lote: pd.DataFrame, semana: int) -> pd.DataFrame:
        validos, rechazados = validar(lote)
        self.memoria.guardar_observaciones(validos)
        self.memoria.guardar_rechazos(rechazados)
        self.ultimos_rechazos = rechazados
        datos = {"n_recibidos": len(lote), "n_validos": len(validos), "n_rechazados": len(rechazados),
                 "rechazos": _a_registros(rechazados[["user_id", "motivo"]])}
        if self.registro.detalle:
            datos["registros"] = _a_registros(lote)
        self.registro.evento("percepcion", semana, **datos)
        return F.construir(self.memoria.ventana(semana, F.VENTANA), semana,
                           self.memoria.semanas_historial(semana))

    # ================================================================ DECISIÓN
    def decide(self, estado: pd.DataFrame, semana: int) -> pd.DataFrame:
        if estado.empty:
            self.ultimas_decisiones = pd.DataFrame()
            self.registro.evento("decision", semana, n_puntuados=0)
            return self.ultimas_decisiones
        pred = self.modelo.predecir(estado)
        self.memoria.purgar_cola(semana - self.cfg.vida_cola_semanas)
        recientes = self.memoria.ofertados_desde(semana - self.cfg.enfriamiento_semanas + 1)
        dec = decidir(pred, self.modelo.tau, self.cfg.presupuesto_frac,
                      cola=self.memoria.cola_pendiente(), recientes=recientes)
        dec = dec.join(estado[["n_semanas_historial", "historial_suficiente"]])
        a_explicar = dec.index[dec["ofertar"]]
        factores = dict(zip(a_explicar, self.modelo.explicar(estado.loc[a_explicar], self.cfg.explicar_top)))
        dec["factores"] = [factores.get(u) for u in dec.index]
        dec["semana"] = semana
        guardar = dec.reset_index().merge(estado[F.FEATURES_COMPLETAS].reset_index(), on="user_id")
        guardar["historial_suficiente"] = guardar["historial_suficiente"].astype(int)
        guardar["modelo"] = f"{self.modelo.tipo}-v{self.modelo.version}/" + guardar["modelo_usado"]
        self.memoria.guardar_predicciones(guardar, COLUMNAS_MEMORIA)
        self.ultimas_decisiones = dec
        self.semanas_decididas.append(semana)

        datos = {"n_puntuados": len(dec), "tau": self.modelo.tau,
                 "modelo": f"{self.modelo.tipo}-v{self.modelo.version}",
                 "n_prediccion_positiva": int(dec["prediccion"].sum()),
                 "n_baja_confianza": int((dec["confianza"] == "baja").sum()),
                 "baja_confianza": dec.index[dec["confianza"] == "baja"].tolist(),
                 "ofertar": dec.index[dec["ofertar"]].tolist()}
        if self.registro.detalle:
            cols = ["probabilidad", "prediccion", "rango_riesgo", "prioridad", "confianza",
                    "modelo_usado", "n_semanas_historial", "ofertar", "motivo", "factores"]
            tabla = dec[cols].copy()
            tabla["probabilidad"] = tabla["probabilidad"].round(4)
            datos["predicciones"] = _a_registros(tabla.reset_index())
        self.registro.evento("decision", semana, **datos)
        return dec

    # ================================================================ ACCIÓN
    def act(self, decisiones: pd.DataFrame, semana: int) -> list[dict]:
        acciones = []
        if decisiones.empty:
            self.ultimas_acciones = acciones
            return acciones
        for uid in decisiones.index[decisiones["ofertar"]]:
            resultado = None
            for intento in range(1, self.cfg.max_reintentos + 2):
                try:
                    resp = self.api.activate_offer(uid, semana)
                    resultado = {"user_id": uid, "estado": "activada", "intentos": intento,
                                 "oferta_id": resp["oferta_id"]}
                    self.registro.evento("accion", semana, user_id=uid, intento=intento,
                                         resultado="ok", oferta_id=resp["oferta_id"])
                    break
                except (MarketingAPIError, MarketingTimeout) as e:
                    tipo = "timeout" if isinstance(e, MarketingTimeout) else "error"
                    reintenta = intento <= self.cfg.max_reintentos
                    self.registro.evento("accion", semana, user_id=uid, intento=intento,
                                         resultado=tipo, detalle=str(e),
                                         siguiente="reintentar" if reintenta else "encolar")
                    if reintenta and self.cfg.espera_reintento_s:
                        time.sleep(self.cfg.espera_reintento_s)
            if resultado is None:
                resultado = {"user_id": uid, "estado": "en_cola", "intentos": self.cfg.max_reintentos + 1}
                self.memoria.encolar([uid], semana)
                self.registro.evento("encolado", semana, user_id=uid,
                                     detalle="fallo persistente de la API; se reintenta el próximo ciclo")
            else:
                self.memoria.desencolar([uid])
            self.memoria.guardar_intervencion(uid, semana, resultado["estado"], resultado["intentos"],
                                              resultado.get("oferta_id", ""))
            acciones.append(resultado)
        self.ultimas_acciones = acciones
        return acciones

    # ================================================================ APRENDIZAJE
    def learn(self, semana: int, env: StreamingEnv) -> dict | None:
        """Vincula las predicciones de hace 4 semanas con el resultado observado y, cada
        `reentreno_cada` ciclos, intenta reentrenar con compuerta."""
        t = semana - 4
        if t not in self.semanas_decididas:
            return None
        reales = env.resultados_reales(t)
        pred_t = self.memoria.predicciones_semana(t)
        reales = reales.reindex(pred_t["user_id"]).dropna().astype(int)
        intervenidos = self.memoria.intervenidos_en(t, semana - 1)
        res = pd.DataFrame({"user_id": reales.index, "semana_prediccion": t, "cancelo": reales.values,
                            "intervenido": [int(u in intervenidos) for u in reales.index]})
        self.memoria.guardar_resultados(res)
        info = {"semana_prediccion": t, "n_resultados": len(res), "cancelaciones": int(res["cancelo"].sum()),
                "intervenidos": int(res["intervenido"].sum())}
        self._ciclos += 1
        if self._ciclos % self.cfg.reentreno_cada == 0:
            info.update(self._reentrenar())
        self.registro.evento("aprendizaje", semana, **info)
        self.historial_aprendizaje.append({"semana": semana, **info})
        return info

    def _reentrenar(self) -> dict:
        datos = self.memoria.datos_aprendizaje()
        # Se excluyen los intervenidos: la oferta altera su resultado y sesgaría la etiqueta.
        datos = datos[datos["intervenido"] == 0]
        if len(datos) < self.cfg.min_filas_reentreno or datos["cancelo"].nunique() < 2:
            return {"reentreno": "omitido", "motivo": f"datos insuficientes ({len(datos)} filas)"}
        feats = pd.DataFrame([json.loads(f) for f in datos["features"]])
        feats["historial_suficiente"] = feats["historial_suficiente"].astype(bool)
        feats["y"] = datos["cancelo"].to_numpy()
        orden = self._rng.permutation(len(feats))
        n_hold = int(len(feats) * self.cfg.fraccion_holdout)
        hold, nuevo = feats.iloc[orden[:n_hold]], feats.iloc[orden[n_hold:]]
        base = self.modelo.muestra_base if self.modelo.muestra_base is not None else nuevo.iloc[:0]
        candidato = ModeloRiesgo.entrenar(self.modelo.tipo, pd.concat([base, nuevo], ignore_index=True),
                                          semilla=self.cfg.semilla, tau=self.modelo.tau,
                                          version=self.modelo.version + 1)
        candidato.muestra_base = self.modelo.muestra_base
        tau = self.modelo.tau
        m_actual = precision_balanceada(hold["y"], (self.modelo.predecir(hold)["probabilidad"] >= tau).astype(int))
        m_cand = precision_balanceada(hold["y"], (candidato.predecir(hold)["probabilidad"] >= tau).astype(int))
        aceptado = bool(m_cand >= m_actual)
        if aceptado:
            self.modelo = candidato
        return {"reentreno": "aceptado" if aceptado else "rechazado",
                "metrica_compuerta": "precision_balanceada", "holdout": n_hold,
                "actual": round(m_actual, 4), "candidato": round(m_cand, 4),
                "version_vigente": self.modelo.version}

    # ================================================================ ORQUESTACIÓN
    def observar_historial(self, env: StreamingEnv, semana: int) -> None:
        """Semanas previas al primer ciclo: el agente solo percibe y memoriza."""
        validos, rechazados = validar(env.observar())
        self.memoria.guardar_observaciones(validos)
        self.memoria.guardar_rechazos(rechazados)
        self.registro.evento("historial", semana, n_validos=len(validos), n_rechazados=len(rechazados),
                             rechazos=_a_registros(rechazados[["user_id", "motivo"]]))

    def run_cycle(self, env: StreamingEnv, semana: int) -> dict:
        t0 = time.perf_counter()
        lote = env.observar()                     # sensores
        estado = self.perceive(lote, semana)      # percepción
        decisiones = self.decide(estado, semana)  # decisión
        acciones = self.act(decisiones, semana)   # acción
        latencia = time.perf_counter() - t0
        aprendizaje = self.learn(semana, env)     # aprendizaje (fuera de la latencia, ver M6)
        resumen = {
            "semana": semana, "n_recibidos": len(lote), "n_rechazados": len(self.ultimos_rechazos),
            "n_puntuados": len(decisiones),
            "n_baja_confianza": int((decisiones["confianza"] == "baja").sum()) if len(decisiones) else 0,
            "n_prediccion_positiva": int(decisiones["prediccion"].sum()) if len(decisiones) else 0,
            "n_ofertas": len(acciones),
            "n_activadas": sum(a["estado"] == "activada" for a in acciones),
            "n_en_cola": sum(a["estado"] == "en_cola" for a in acciones),
            "intentos_api": sum(a["intentos"] for a in acciones),
            "latencia_s": round(latencia, 4),
            "modelo": f"{self.modelo.tipo}-v{self.modelo.version}",
            "reentreno": (aprendizaje or {}).get("reentreno", ""),
        }
        self.registro.evento("ciclo", semana, **resumen)
        return resumen
