"""Pruebas unitarias y de integración del agente StreamRetain."""

import datetime as dt

import numpy as np
import pandas as pd
import pytest

from streamretain import features as F
from streamretain.agent import ConfigAgente, StreamRetainAgent
from streamretain.env import MarketingAPI, MarketingAPIError, MarketingTimeout, StreamingEnv
from streamretain.evaluacion import ejecutar_caso
from streamretain.logging_utils import RegistroEjecucion
from streamretain.memory import Memoria
from streamretain.perception import validar


def _registro(uid, semana=0, horas=5.0, dias=2.0, plan="basico", pago=0):
    return {"user_id": uid, "semana": semana, "horas_vistas": horas,
            "dias_desde_ultimo_login": dias, "tipo_plan": plan, "cambio_metodo_pago": pago}


# ------------------------------------------------------------------ percepción
def test_perceive_rechaza_invalidos_con_motivo():
    lote = pd.DataFrame([
        _registro("U1"),
        _registro("U2", horas=np.nan),
        _registro("U3", horas=-2.0),
        _registro("U4", horas=500.0),
        _registro("U5", dias=-1.0),
        _registro("U6", plan="desconocido"),
    ])
    validos, rechazados = validar(lote)
    assert list(validos["user_id"]) == ["U1"]
    assert set(rechazados["user_id"]) == {"U2", "U3", "U4", "U5", "U6"}
    assert rechazados["motivo"].str.len().gt(0).all()
    assert "negativo" in rechazados.set_index("user_id").loc["U3", "motivo"]


def test_no_fabrica_historial_para_usuario_nuevo():
    mem = Memoria()
    mem.guardar_observaciones(validar(pd.DataFrame([_registro("U1", semana=0), _registro("U1", semana=1),
                                                    _registro("U2", semana=1)]))[0])
    f = F.construir(mem.ventana(1), 1, mem.semanas_historial(1))
    assert bool(f.loc["U1", "historial_suficiente"]) is True
    assert bool(f.loc["U2", "historial_suficiente"]) is False
    assert f.loc["U2", "n_semanas_historial"] == 1
    assert f.loc["U2", F.FEATURES_TENDENCIA].isna().all()   # tendencia vacía, no inventada


def test_usuario_sin_historial_recibe_baja_confianza(modelo_pequeno):
    mem = Memoria()
    mem.guardar_observaciones(validar(pd.DataFrame([_registro("U9", semana=3)]))[0])
    estado = F.construir(mem.ventana(3), 3, mem.semanas_historial(3))
    pred = modelo_pequeno.predecir(estado)
    assert pred.loc["U9", "confianza"] == "baja"
    assert pred.loc["U9", "modelo_usado"] == "sin_tendencia"


# ------------------------------------------------------------------ acción
class APIFalla:
    def __init__(self, fallos_antes_de_exito):
        self.fallos = fallos_antes_de_exito
        self.llamadas = 0

    def activate_offer(self, user_id, semana):
        self.llamadas += 1
        if self.llamadas <= self.fallos:
            raise (MarketingTimeout if self.llamadas % 2 else MarketingAPIError)("falla simulada")
        return {"user_id": user_id, "estado": "activada", "oferta_id": "OF-TEST"}


def _decision_un_usuario(uid="U1"):
    return pd.DataFrame({"ofertar": [True]}, index=pd.Index([uid], name="user_id"))


def test_act_reintenta_y_luego_activa(modelo_pequeno):
    api = APIFalla(fallos_antes_de_exito=2)
    ag = StreamRetainAgent(modelo_pequeno, api, config=ConfigAgente(max_reintentos=3))
    acciones = ag.act(_decision_un_usuario(), semana=5)
    assert acciones[0]["estado"] == "activada" and acciones[0]["intentos"] == 3
    fallos = [e for e in ag.registro.eventos if e["tipo"] == "accion" and e["resultado"] != "ok"]
    assert len(fallos) == 2 and all(e["siguiente"] == "reintentar" for e in fallos)


def test_act_registra_fallo_persistente_y_encola(modelo_pequeno):
    api = APIFalla(fallos_antes_de_exito=99)
    ag = StreamRetainAgent(modelo_pequeno, api, config=ConfigAgente(max_reintentos=3))
    acciones = ag.act(_decision_un_usuario("U7"), semana=5)
    assert acciones[0]["estado"] == "en_cola"
    assert api.llamadas == 4                                  # 1 intento + 3 reintentos
    assert ag.memoria.cola_pendiente() == ["U7"]
    assert any(e["tipo"] == "encolado" for e in ag.registro.eventos)
    intervenciones = ag.memoria.tabla("intervenciones")
    assert intervenciones.iloc[0]["estado"] == "en_cola"


# ------------------------------------------------------------------ aprendizaje
class ModeloFijo:
    """Modelo de prueba: probabilidad = valor de una columna (perfecto o constante)."""
    tipo, version, tau, muestra_base = "logistica", 1, 0.5, None

    def __init__(self, perfecto):
        self.perfecto = perfecto

    def predecir(self, feats):
        p = feats["horas_actual"].to_numpy() if self.perfecto else np.zeros(len(feats))
        return pd.DataFrame({"probabilidad": p}, index=feats.index)


def test_compuerta_rechaza_modelo_peor(monkeypatch):
    ag = StreamRetainAgent(ModeloFijo(perfecto=True), api=None,
                           config=ConfigAgente(min_filas_reentreno=50))
    rng = np.random.default_rng(0)
    y = rng.integers(0, 2, 200)
    feats = pd.DataFrame({c: 0.0 for c in F.FEATURES_COMPLETAS}, index=range(200))
    feats["horas_actual"] = y.astype(float)    # el modelo vigente acierta todo
    feats["historial_suficiente"] = 1
    preds = feats.assign(user_id=[f"U{i}" for i in range(200)], semana=4, probabilidad=0.5, prediccion=0,
                         prioridad="baja", confianza="normal", modelo="x")
    ag.memoria.guardar_predicciones(preds, F.FEATURES_COMPLETAS + ["historial_suficiente"])
    ag.memoria.guardar_resultados(pd.DataFrame({"user_id": preds["user_id"], "semana_prediccion": 4,
                                                "cancelo": y, "intervenido": 0}))
    from streamretain import agent as modulo
    monkeypatch.setattr(modulo.ModeloRiesgo, "entrenar", classmethod(lambda cls, *a, **k: ModeloFijo(False)))
    info = ag._reentrenar()
    assert info["reentreno"] == "rechazado"
    assert info["candidato"] < info["actual"]
    assert isinstance(ag.modelo, ModeloFijo) and ag.modelo.perfecto   # sigue el modelo vigente


# ------------------------------------------------------------------ integración
def test_ciclo_completo_registra_percepcion_decision_accion(params_pequenos, modelo_pequeno):
    env = StreamingEnv(params_pequenos, seed=777)
    api = MarketingAPI(env, 0.3, 0.1, seed=777)
    ag = StreamRetainAgent(modelo_pequeno, api, registro=RegistroEjecucion(detalle=True))
    for w in range(env.inicio_ciclos):
        ag.observar_historial(env, w)
        env.avanzar()
    resumen = ag.run_cycle(env, env.inicio_ciclos)
    tipos = [e["tipo"] for e in ag.registro.eventos]
    for t in ("percepcion", "decision", "accion", "ciclo"):
        assert t in tipos, t
    for e in ag.registro.eventos:
        dt.datetime.fromisoformat(e["ts"])                     # marca de tiempo válida
    assert resumen["n_puntuados"] > 0 and resumen["latencia_s"] > 0


def test_el_agente_no_ve_la_etiqueta_natural(params_pequenos, modelo_pequeno, monkeypatch):
    def prohibido(*a, **k):
        raise AssertionError("el agente consultó la etiqueta natural")
    monkeypatch.setattr(StreamingEnv, "etiquetas_naturales", prohibido)
    env = StreamingEnv(params_pequenos, seed=778)
    ag = StreamRetainAgent(modelo_pequeno, MarketingAPI(env, 0, 0, seed=778))
    for w in range(env.horizonte - 4):
        if w < env.inicio_ciclos:
            ag.observar_historial(env, w)
        else:
            ag.run_cycle(env, w)
        env.avanzar()


def test_reproducibilidad_misma_semilla(params_pequenos, modelo_pequeno, monkeypatch):
    from streamretain import evaluacion
    monkeypatch.setattr(evaluacion, "parametros_escenario", lambda _id: dict(params_pequenos))
    r1 = ejecutar_caso("N2", 1234, modelo_pequeno)
    r2 = ejecutar_caso("N2", 1234, modelo_pequeno)
    cols = ["user_id", "semana", "probabilidad", "prediccion", "y"]
    pd.testing.assert_frame_equal(r1["predicciones"][cols], r2["predicciones"][cols])
    m1 = {k: v for k, v in r1["metricas"].items() if "latencia" not in k}
    m2 = {k: v for k, v in r2["metricas"].items() if "latencia" not in k}
    assert m1 == pytest.approx(m2, nan_ok=True)
