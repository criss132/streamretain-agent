"""Interfaz Streamlit de StreamRetain-Agent (evidencia de funcionamiento).

Ejecuta el agente DESDE CERO sobre el entorno simulado (datos sintéticos): ciclo semanal
percepción → decisión → acción → aprendizaje, con registro descargable, y corre en vivo
una suite de pruebas contra los umbrales congelados.

Local:  streamlit run app/streamlit_app.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "scripts"))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from streamretain.agent import ConfigAgente, StreamRetainAgent  # noqa: E402
from streamretain.config import escenarios, parametros_escenario, umbrales  # noqa: E402
from streamretain.env import MarketingAPI, StreamingEnv  # noqa: E402
from streamretain.evaluacion import cargar_modelos, ejecutar_caso  # noqa: E402
from streamretain.logging_utils import RegistroEjecucion  # noqa: E402
from streamretain.memory import Memoria  # noqa: E402
from streamretain.model import precision_balanceada  # noqa: E402

st.set_page_config(page_title="StreamRetain-Agent", page_icon="📉", layout="wide")


@st.cache_resource(show_spinner="Cargando modelo entrenado…")
def modelos():
    return cargar_modelos(RAIZ)


def texto_factores(f) -> str:
    if not isinstance(f, list) or not f:
        return ""
    return "; ".join(f"{x['factor']} ({x['aporte']:+.3f})" for x in f)


def reiniciar(id_esc: str, semilla: int, n_usuarios: int) -> None:
    modelo, _ = modelos()
    p = parametros_escenario(id_esc)
    p["n_usuarios"] = n_usuarios
    env = StreamingEnv(p, seed=semilla)
    api = MarketingAPI(env, p["api_tasa_fallo"], p["api_tasa_timeout"], seed=semilla)
    registro = RegistroEjecucion(run_id=f"app-{id_esc}-s{semilla}", detalle=True,
                                 contexto={"escenario": id_esc, "semilla": semilla})
    agente = StreamRetainAgent(modelo, api, Memoria(), registro, ConfigAgente(semilla=semilla))
    for w in range(env.inicio_ciclos):           # semanas de historial: solo percibe
        agente.observar_historial(env, w)
        env.avanzar()
    st.session_state.update(env=env, agente=agente, params=p, ciclos=[], metricas=[],
                            config=(id_esc, semilla, n_usuarios))


def ejecutar_un_ciclo() -> None:
    env: StreamingEnv = st.session_state.env
    agente: StreamRetainAgent = st.session_state.agente
    w = env.semana
    resumen = agente.run_cycle(env, w)
    st.session_state.ciclos.append(resumen)
    env.avanzar()
    # Evaluación (el agente NO ve estas etiquetas): ciclos cuya ventana de 4 semanas ya venció
    t = env.semana - 4
    if t >= env.inicio_ciclos:
        y = env.etiquetas_naturales(t)
        pred = agente.memoria.predicciones_semana(t).set_index("user_id")
        y = y.reindex(pred.index).fillna(0).astype(int)
        st.session_state.metricas.append({
            "semana_prediccion": t,
            "accuracy": float((pred["prediccion"] == y).mean()),
            "precision_balanceada": precision_balanceada(y.to_numpy(), pred["prediccion"].to_numpy()),
            "recall": float(pred.loc[y == 1, "prediccion"].mean()) if (y == 1).any() else float("nan"),
            "tasa_real": float(y.mean()),
        })


# ============================================================== barra lateral
ESC = escenarios()
st.sidebar.title("StreamRetain-Agent")
st.sidebar.caption("Agente de aprendizaje que predice cancelaciones a 4 semanas y activa ofertas de "
                   "retención. **Datos 100 % sintéticos** (simulador).")
id_esc = st.sidebar.selectbox("Escenario", list(ESC), index=list(ESC).index("N2"),
                              format_func=lambda e: f"{e} ({ESC[e]['tipo']}) — {ESC[e]['descripcion']}")
semilla = st.sidebar.number_input("Semilla", min_value=0, max_value=100000, value=2026, step=1)
n_usuarios = st.sidebar.select_slider("Suscriptores iniciales", options=[300, 500, 1000, 2000],
                                      value=int(parametros_escenario(id_esc)["n_usuarios"]))
if st.sidebar.button("Reiniciar simulación", width="stretch") or "env" not in st.session_state \
        or st.session_state.get("config") != (id_esc, semilla, n_usuarios):
    reiniciar(id_esc, int(semilla), int(n_usuarios))

env: StreamingEnv = st.session_state.env
p = st.session_state.params
fin_ciclos = env.inicio_ciclos + int(p["ciclos"])
quedan = fin_ciclos - env.semana
c1, c2 = st.sidebar.columns(2)
if c1.button("Ejecutar ciclo semanal", type="primary", disabled=quedan <= 0, width="stretch"):
    ejecutar_un_ciclo()
if c2.button("Todos los ciclos", disabled=quedan <= 0, width="stretch"):
    for _ in range(fin_ciclos - env.semana):
        ejecutar_un_ciclo()
st.sidebar.markdown(f"Semana simulada: **{env.semana}** · ciclos restantes: **{max(fin_ciclos - env.semana, 0)}**")
st.sidebar.markdown("**Casos sugeridos:** `N2` típico · `F1` entradas inválidas · `F2` usuarios sin "
                    "historial · `F3` API de marketing con 30 % de fallos · `L3` tasa base 40 %")

# ============================================================== contenido
st.title("StreamRetain-Agent · ciclo percepción → decisión → acción")
tab_ciclo, tab_hist, tab_pruebas, tab_info = st.tabs(
    ["Ciclo actual", "Historial y aprendizaje", "Suite de pruebas", "Cómo funciona"])

agente: StreamRetainAgent = st.session_state.agente
with tab_ciclo:
    if not st.session_state.ciclos:
        st.info("Pulse **Ejecutar ciclo semanal** en la barra lateral. Las semanas de historial previo "
                f"({env.inicio_ciclos}) ya fueron percibidas y memorizadas.")
    else:
        r = st.session_state.ciclos[-1]
        k = st.columns(6)
        k[0].metric("Registros recibidos", r["n_recibidos"])
        k[1].metric("Inválidos rechazados", r["n_rechazados"])
        k[2].metric("Puntuados", r["n_puntuados"])
        k[3].metric("Baja confianza (sin historial)", r["n_baja_confianza"])
        k[4].metric("Ofertas activadas / en cola", f"{r['n_activadas']} / {r['n_en_cola']}")
        k[5].metric("Latencia del ciclo", f"{r['latencia_s']:.2f} s")

        st.subheader(f"Tabla de riesgo — semana {r['semana']} (τ = {agente.modelo.tau:.3f}, presupuesto top-10 %)")
        st.caption("La probabilidad es una **estimación**, no una cancelación confirmada.")
        d = agente.ultimas_decisiones.reset_index()
        d["factores principales"] = d["factores"].map(texto_factores)
        filtro = st.radio("Mostrar", ["Ofertados", "Todos"], horizontal=True)
        if filtro == "Ofertados":
            d = d[d["ofertar"]]
        st.dataframe(d.sort_values("probabilidad", ascending=False)[
            ["user_id", "probabilidad", "prioridad", "confianza", "n_semanas_historial", "motivo",
             "factores principales"]].head(300), width="stretch", hide_index=True,
            column_config={"probabilidad": st.column_config.ProgressColumn(format="%.3f", min_value=0, max_value=1)})

        a, b = st.columns(2)
        with a:
            st.subheader("API de marketing")
            ev = [e for e in agente.registro.eventos if e["tipo"] in ("accion", "encolado") and e["semana"] == r["semana"]]
            if ev:
                tabla = pd.DataFrame(ev)
                fallos = tabla[(tabla["tipo"] == "accion") & (tabla["resultado"] != "ok")]
                st.write(f"Intentos: **{(tabla['tipo'] == 'accion').sum()}** · fallos/timeouts: **{len(fallos)}** · "
                         f"encolados: **{(tabla['tipo'] == 'encolado').sum()}**")
                if len(fallos):
                    st.dataframe(fallos[["user_id", "intento", "resultado", "siguiente", "detalle"]],
                                 hide_index=True, width="stretch")
        with b:
            st.subheader("Registros inválidos detectados")
            st.dataframe(agente.ultimos_rechazos, hide_index=True, width="stretch")

with tab_hist:
    if st.session_state.ciclos:
        st.subheader("Resumen por ciclo")
        st.dataframe(pd.DataFrame(st.session_state.ciclos), hide_index=True, width="stretch")
    if st.session_state.metricas:
        st.subheader("Evaluación por semana (etiquetas del simulador; el agente no las ve)")
        m = pd.DataFrame(st.session_state.metricas).set_index("semana_prediccion")
        st.line_chart(m[["accuracy", "precision_balanceada", "recall"]])
        st.dataframe(m, width="stretch")
    else:
        st.caption("Las métricas aparecen cuando vence la ventana de 4 semanas del primer ciclo.")
    if agente.historial_aprendizaje:
        st.subheader("Aprendizaje (resultados a 4 semanas y compuerta de reentrenamiento)")
        st.dataframe(pd.DataFrame(agente.historial_aprendizaje), hide_index=True, width="stretch")
    st.download_button("Descargar log de esta ejecución (JSONL)", agente.registro.jsonl().encode("utf-8"),
                       file_name=f"log_{id_esc}_s{semilla}.jsonl", mime="application/json")

with tab_pruebas:
    cfg = umbrales()
    st.markdown("Corre el agente **desde cero** en los escenarios elegidos y calcula las medidas M1–M6 contra "
                "los umbrales congelados (`config/umbrales.yaml`, tag `umbrales-congelados`).")
    sel = st.multiselect("Escenarios", list(ESC), default=["N2", "L1", "F1", "F3"])
    sem = st.multiselect("Semillas de prueba", list(range(1001, 1011)), default=[1001, 1002])
    st.caption(f"{len(sel) * len(sem)} casos · ~15–25 s por caso en un equipo de escritorio.")
    if st.button("Ejecutar suite de pruebas", type="primary", disabled=not sel or not sem):
        from run_evaluation import tabla_resultados
        modelo, baseline = modelos()
        filas, barra, t0 = [], st.progress(0.0), time.time()
        casos = [(e, s) for e in sel for s in sem]
        for i, (e, s) in enumerate(casos, 1):
            barra.progress(i / len(casos), text=f"Caso {i}/{len(casos)}: {e} semilla {s}")
            m = ejecutar_caso(e, s, modelo, baseline)["metricas"]
            m["log"] = "(en vivo)"
            filas.append(m)
        casos_df = pd.DataFrame(filas)
        cfg_vivo = {"medidas": [dict(med, aplica_a=[x for x in med["aplica_a"] if x in sel]) for med in cfg["medidas"]]}
        cfg_vivo["medidas"] = [med for med in cfg_vivo["medidas"] if med["aplica_a"]]
        st.success(f"Suite terminada en {time.time() - t0:.0f} s")
        st.dataframe(tabla_resultados(casos_df, cfg_vivo).drop(columns=["media", "de", "Evidencia"]),
                     hide_index=True, width="stretch")
        st.dataframe(casos_df, hide_index=True, width="stretch")
    oficial = RAIZ / "results" / "resultados.csv"
    if oficial.exists():
        st.subheader("Resultados oficiales guardados (130 casos: 13 escenarios × 10 semillas)")
        st.dataframe(pd.read_csv(oficial).drop(columns=["Evidencia"], errors="ignore"),
                     hide_index=True, width="stretch")

with tab_info:
    st.markdown("""
**Ciclo del agente** (`src/streamretain/agent.py`):
1. `perceive()` valida los registros crudos (rechaza NaN, negativos, fuera de rango o plan desconocido, con motivo), guarda en memoria SQLite y arma el estado por usuario. Nunca inventa historial.
2. `decide()` estima la probabilidad de cancelar en 4 semanas (gradient boosting calibrado; sin historial suficiente usa un modelo sin variables de tendencia y marca *baja confianza*), aplica el umbral τ y el presupuesto top-10 %, y explica los 3 factores principales.
3. `act()` activa ofertas en la API de marketing (simulada) con hasta 3 reintentos; si falla, registra el error y deja al usuario en cola.
4. `learn()` vincula cada predicción con el resultado a 4 semanas y reentrena con compuerta: solo acepta un modelo que mantenga o mejore la precisión balanceada.

**Entorno**: simulador estocástico con semilla (`src/streamretain/env/simulator.py`). Datos sintéticos, no reales.
""")
